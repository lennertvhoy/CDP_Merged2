from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.responses import JSONResponse

from src.core.exceptions import TracardiError
from tests.unit.chainlit_test_harness import load_modules_with_fake_chainlit


class FakeMetricChild:
    def __init__(self, parent: FakeMetric, labels: dict[str, Any]) -> None:
        self.parent = parent
        self.labels = labels

    def inc(self) -> None:
        self.parent.calls.append(self.labels)


class FakeMetric:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def labels(self, **labels: Any) -> FakeMetricChild:
        return FakeMetricChild(self, labels)


class FakeLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    def info(self, event: str, **kwargs: Any) -> None:
        self.events.append(("info", event, kwargs))

    def warning(self, event: str, **kwargs: Any) -> None:
        self.events.append(("warning", event, kwargs))

    def error(self, event: str, **kwargs: Any) -> None:
        self.events.append(("error", event, kwargs))


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeAsyncSqliteSaver:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn


class FakeWorkflow:
    def __init__(self, events: list[dict[str, Any]] | None = None, error: Exception | None = None):
        self.events = events or []
        self.error = error
        self.calls: list[tuple[Any, Any, Any]] = []

    async def astream_events(self, inputs: Any, *, config: Any, version: str):
        self.calls.append((inputs, config, version))
        if self.error is not None:
            raise self.error

        for event in self.events:
            yield event


@dataclass
class AppContext:
    app: Any
    chainlit: Any
    query_metric: FakeMetric
    error_metric: FakeMetric
    logger: FakeLogger
    trace_log: dict[str, Any]


@pytest.fixture
def app_context(monkeypatch) -> AppContext:
    modules, fake_chainlit, _ = load_modules_with_fake_chainlit(
        monkeypatch,
        "src.ui.actions",
        "src.ui.components",
        "src.app",
    )
    app = modules["src.app"]

    query_metric = FakeMetric()
    error_metric = FakeMetric()
    logger = FakeLogger()
    trace_log = {"bound": [], "cleared": 0}

    monkeypatch.setattr(app, "QUERY_REQUESTS_TOTAL", query_metric)
    monkeypatch.setattr(app, "ERRORS_TOTAL", error_metric)
    monkeypatch.setattr(app, "logger", logger)
    monkeypatch.setattr(app, "bind_trace_id", trace_log["bound"].append)
    monkeypatch.setattr(
        app,
        "clear_trace_id",
        lambda: trace_log.__setitem__("cleared", trace_log["cleared"] + 1),
    )

    return AppContext(
        app=app,
        chainlit=fake_chainlit,
        query_metric=query_metric,
        error_metric=error_metric,
        logger=logger,
        trace_log=trace_log,
    )


def _patch_start_dependencies(
    app_context: AppContext, monkeypatch, *, profile: dict[str, Any] | None
):
    app = app_context.app
    connection = FakeConnection()
    workflow = object()
    state: dict[str, Any] = {}

    async def fake_connect(path):
        state["checkpoint_path"] = path
        return connection

    class FakeTracardiClient:
        async def get_or_create_profile(self, session_id: str) -> dict[str, Any] | None:
            state["session_id"] = session_id
            return profile

    monkeypatch.setattr(app.uuid, "uuid4", lambda: "trace-123")
    monkeypatch.setattr(app.aiosqlite, "connect", fake_connect)
    monkeypatch.setattr(app, "AsyncSqliteSaver", FakeAsyncSqliteSaver)
    monkeypatch.setattr(app, "compile_workflow", lambda checkpointer: workflow)
    monkeypatch.setattr(app, "TracardiClient", FakeTracardiClient)
    monkeypatch.setattr(app, "build_status_cards", lambda repo_root: ["status-card"])
    monkeypatch.setattr(
        app,
        "build_welcome_markdown",
        lambda chat_profile, status_cards: f"{chat_profile}:{status_cards[0]}",
    )
    monkeypatch.setattr(
        app,
        "build_welcome_actions",
        lambda chat_profile: [
            app_context.chainlit.Action(
                name="ui_show_status",
                payload={"profile": chat_profile},
                label="System Status",
                tooltip="Inspect status",
            )
        ],
    )

    return connection, workflow, state


@pytest.mark.asyncio
async def test_healthz_returns_expected_payload(app_context: AppContext):
    response = await app_context.app.healthz()

    assert response == {
        "status": "ok",
        "service": "cdp-merged",
        "llm_provider": app_context.app.settings.LLM_PROVIDER,
    }


@pytest.mark.asyncio
async def test_readinessz_returns_ok_when_query_plane_is_ready(
    app_context: AppContext, monkeypatch
):
    app = app_context.app

    class FakeSearchService:
        async def readiness_probe(self):
            return {
                "status": "ok",
                "backend": "postgresql",
                "db_ping": 1,
                "companies_table": "companies",
            }

    monkeypatch.setattr(app, "_database_config_source", lambda: "env:DATABASE_URL")
    monkeypatch.setattr(app, "get_search_service", lambda: FakeSearchService())

    response = await app.readinessz()
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["service"] == "cdp-merged"
    assert payload["checks"]["app"]["status"] == "ok"
    assert payload["checks"]["postgresql"]["status"] == "ok"
    assert payload["checks"]["tool_layer"]["status"] == "ok"
    assert payload["checks"]["action_processing"]["status"] == "ok"


@pytest.mark.asyncio
async def test_readinessz_fails_when_database_config_is_missing(
    app_context: AppContext, monkeypatch
):
    app = app_context.app
    monkeypatch.setattr(app, "_database_config_source", lambda: None)

    response = await app.readinessz()
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["status"] == "error"
    assert payload["checks"]["postgresql"]["configured"] is False
    assert "DATABASE_URL is not configured" in payload["checks"]["postgresql"]["error"]
    assert payload["checks"]["tool_layer"]["status"] == "error"


@pytest.mark.asyncio
async def test_readinessz_fails_when_query_plane_probe_errors(
    app_context: AppContext, monkeypatch
):
    app = app_context.app

    class FakeSearchService:
        async def readiness_probe(self):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(app, "_database_config_source", lambda: "env:DATABASE_URL")
    monkeypatch.setattr(app, "get_search_service", lambda: FakeSearchService())

    response = await app.readinessz()
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["status"] == "error"
    assert payload["checks"]["postgresql"]["source"] == "env:DATABASE_URL"
    assert payload["checks"]["postgresql"]["error"] == "connection refused"
    assert payload["checks"]["tool_layer"]["error"] == "connection refused"


@pytest.mark.asyncio
async def test_probe_endpoint_middleware_short_circuits_readiness_path(
    app_context: AppContext, monkeypatch
):
    app = app_context.app

    class FakeSearchService:
        async def readiness_probe(self):
            return {
                "status": "ok",
                "backend": "postgresql",
                "db_ping": 1,
                "companies_table": "companies",
            }

    monkeypatch.setattr(app, "_database_config_source", lambda: "env:DATABASE_URL")
    monkeypatch.setattr(app, "get_search_service", lambda: FakeSearchService())
    delegated = False

    async def call_next(_request):
        nonlocal delegated
        delegated = True
        return JSONResponse({"status": "html-shell"})

    request = SimpleNamespace(url=SimpleNamespace(path="/project/readinessz"))

    response = await app.probe_endpoint_middleware(request, call_next)
    payload = json.loads(response.body)

    assert delegated is False
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["checks"]["postgresql"]["status"] == "ok"


@pytest.mark.asyncio
async def test_probe_endpoint_middleware_delegates_non_probe_path(app_context: AppContext):
    delegated = False

    async def call_next(_request):
        nonlocal delegated
        delegated = True
        return JSONResponse({"status": "html-shell"})

    request = SimpleNamespace(url=SimpleNamespace(path="/"))

    response = await app_context.app.probe_endpoint_middleware(request, call_next)
    payload = json.loads(response.body)

    assert delegated is True
    assert response.status_code == 200
    assert payload == {"status": "html-shell"}


@pytest.mark.asyncio
async def test_profile_hooks_delegate_to_builders(app_context: AppContext, monkeypatch):
    app = app_context.app
    expected_profiles = ["profiles"]
    expected_starters = ["starters"]

    app_context.chainlit.user_session.set("chat_profile", "sales_rep")
    monkeypatch.setattr(app, "build_chat_profiles", lambda: expected_profiles)
    monkeypatch.setattr(app, "build_starters", lambda profile: [profile, *expected_starters])

    assert await app.set_chat_profiles() == expected_profiles
    assert await app.set_starters() == ["sales_rep", *expected_starters]


def test_app_disables_chainlit_database_url_data_layer(app_context: AppContext):
    factory = app_context.chainlit._data_layer_factory

    assert callable(factory)
    assert factory() is None


def test_app_skips_oauth_registration_without_configured_provider(monkeypatch):
    modules, fake_chainlit, _ = load_modules_with_fake_chainlit(monkeypatch, "src.app")

    assert modules["src.app"].OAUTH_CALLBACK_ENABLED is False
    assert fake_chainlit._oauth_callback is None


def test_app_registers_oauth_callback_when_provider_is_configured(monkeypatch):
    modules, fake_chainlit, _ = load_modules_with_fake_chainlit(
        monkeypatch,
        "src.app",
        configured_oauth_providers=["google"],
    )

    assert modules["src.app"].OAUTH_CALLBACK_ENABLED is True
    assert fake_chainlit._oauth_callback is modules["src.app"].oauth_user_callback


@pytest.mark.asyncio
async def test_oauth_callback_normalizes_display_name_and_provider(monkeypatch):
    modules, _fake_chainlit, _ = load_modules_with_fake_chainlit(
        monkeypatch,
        "src.app",
        configured_oauth_providers=["google"],
    )
    app = modules["src.app"]
    default_user = app.User(identifier="jane@example.com", metadata={"image": "avatar"})

    resolved_user = await app.oauth_user_callback(
        "google",
        "token",
        {"name": "Jane Doe"},
        default_user,
        None,
    )

    assert resolved_user is not None
    assert resolved_user.identifier == "jane@example.com"
    assert resolved_user.display_name == "Jane Doe"
    assert resolved_user.metadata == {"image": "avatar", "provider": "google"}


@pytest.mark.asyncio
async def test_set_starters_falls_back_without_chainlit_context(
    app_context: AppContext, monkeypatch
):
    app = app_context.app
    monkeypatch.setattr(
        app_context.chainlit.user_session,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("no context")),
    )
    monkeypatch.setattr(app, "build_starters", lambda profile: [profile or "default"])

    assert await app.set_starters() == ["default"]


@pytest.mark.asyncio
async def test_start_initializes_session_and_sends_welcome(app_context: AppContext, monkeypatch):
    app = app_context.app
    app_context.chainlit.user_session.set("id", "thread-123")
    connection, workflow, state = _patch_start_dependencies(
        app_context,
        monkeypatch,
        profile={"id": "profile-123"},
    )

    await app.start()

    assert app_context.trace_log["bound"] == ["trace-123"]
    assert app_context.chainlit.user_session.get("trace_id") == "trace-123"
    assert app_context.chainlit.user_session.get("workflow") is workflow
    assert app_context.chainlit.user_session.get("checkpointer_conn") is connection
    assert app_context.chainlit.user_session.get("thread_id") == "thread-123"
    assert app_context.chainlit.user_session.get("chat_profile") == app.DEFAULT_CHAT_PROFILE
    assert app_context.chainlit.user_session.get("profile_id") == "profile-123"
    assert str(state["checkpoint_path"]).endswith("data/checkpoints/checkpoints.db")
    assert state["session_id"] == "thread-123"

    welcome_message = app_context.chainlit._messages[-1]
    assert welcome_message.sent is True
    assert welcome_message.content == "marketing_manager:status-card"
    assert [action.name for action in welcome_message.actions] == ["ui_show_status"]


@pytest.mark.asyncio
async def test_start_keeps_running_when_tracardi_bootstrap_fails(
    app_context: AppContext, monkeypatch
):
    app = app_context.app
    app_context.chainlit.user_session.set("id", "thread-456")
    connection, workflow, _ = _patch_start_dependencies(app_context, monkeypatch, profile=None)

    class FakeTracardiClient:
        async def get_or_create_profile(self, session_id: str) -> dict[str, Any] | None:
            raise TracardiError("boom")

    monkeypatch.setattr(app, "TracardiClient", FakeTracardiClient)

    await app.start()

    assert app_context.chainlit.user_session.get("workflow") is workflow
    assert app_context.chainlit.user_session.get("checkpointer_conn") is connection
    assert app_context.chainlit.user_session.get("profile_id") is None
    assert (
        "warning",
        "tracardi_profile_bootstrap_failed",
        {"error": "boom"},
    ) in app_context.logger.events


@pytest.mark.asyncio
async def test_end_closes_connection_and_clears_trace(app_context: AppContext):
    connection = FakeConnection()
    app_context.chainlit.user_session.set("checkpointer_conn", connection)

    await app_context.app.end()

    assert connection.closed is True
    assert app_context.trace_log["cleared"] == 1


@pytest.mark.asyncio
async def test_main_rejects_queries_over_max_length(app_context: AppContext, monkeypatch):
    app = app_context.app
    monkeypatch.setattr(app.uuid, "uuid4", lambda: "trace-msg")

    # Set up required session state
    app_context.chainlit.user_session.set("workflow", FakeWorkflow())
    app_context.chainlit.user_session.set("thread_id", "thread-test")

    await app.main(SimpleNamespace(content="x" * (app.MAX_QUERY_LENGTH + 1)))

    assert app_context.error_metric.calls == [{"error_type": "query_too_long"}]

    message = app_context.chainlit._messages[-1]
    assert message.sent is True
    assert "Query too long" in message.content


@pytest.mark.asyncio
async def test_main_streams_response_and_records_tool_usage(app_context: AppContext):
    workflow = FakeWorkflow(
        events=[
            {"event": "on_tool_start", "name": "agent"},
            {"event": "on_tool_start", "name": "search_profiles"},
            {"event": "on_chat_model_stream", "data": {"chunk": SimpleNamespace(content="Hello")}},
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": SimpleNamespace(content=" world")},
            },
        ]
    )
    app_context.chainlit.user_session.set("workflow", workflow)
    app_context.chainlit.user_session.set("thread_id", "thread-789")
    app_context.chainlit.user_session.set("profile_id", "profile-789")
    app_context.chainlit.user_session.set("trace_id", "trace-existing")

    await app_context.app.main(SimpleNamespace(content="find me prospects"))

    assert app_context.trace_log["bound"] == ["trace-existing"]
    assert app_context.trace_log["cleared"] == 1
    assert app_context.query_metric.calls == [{"status": "success"}]

    inputs, config, version = workflow.calls[0]
    assert version == "v2"
    assert inputs["profile_id"] == "profile-789"
    assert inputs["messages"][0].content == "find me prospects"
    assert config == {"configurable": {"thread_id": "thread-789"}}

    step = app_context.chainlit._steps[-1]
    assert step.output == "Used 1 tool call(s) to process your query."
    assert step.is_error is False

    streamed_message = app_context.chainlit._messages[-1]
    assert streamed_message.sent is True
    assert streamed_message.content == "Hello world"


@pytest.mark.asyncio
async def test_main_sends_fallback_when_no_text_is_generated(app_context: AppContext):
    workflow = FakeWorkflow(events=[{"event": "on_tool_start", "name": "agent"}])
    app_context.chainlit.user_session.set("workflow", workflow)
    app_context.chainlit.user_session.set("thread_id", "thread-000")
    app_context.chainlit.user_session.set("profile_id", "profile-000")
    app_context.chainlit.user_session.set("trace_id", "trace-empty")

    await app_context.app.main(SimpleNamespace(content="silent run"))

    assert app_context.query_metric.calls == [{"status": "success"}]
    assert app_context.chainlit._steps[-1].output == "Query processed directly."

    fallback_message = app_context.chainlit._messages[-1]
    assert fallback_message.sent is True
    assert "couldn't generate a response" in fallback_message.content


@pytest.mark.asyncio
async def test_main_reports_workflow_errors(app_context: AppContext):
    workflow = FakeWorkflow(error=RuntimeError("workflow exploded"))
    app_context.chainlit.user_session.set("workflow", workflow)
    app_context.chainlit.user_session.set("thread_id", "thread-err")
    app_context.chainlit.user_session.set("profile_id", "profile-err")
    app_context.chainlit.user_session.set("trace_id", "trace-error")

    await app_context.app.main(SimpleNamespace(content="break it"))

    assert app_context.query_metric.calls == [{"status": "error"}]
    assert app_context.error_metric.calls == [{"error_type": "RuntimeError"}]

    step = app_context.chainlit._steps[-1]
    assert step.is_error is True
    assert "workflow exploded" in step.output

    error_message = app_context.chainlit._messages[-1]
    assert error_message.sent is True
    assert "encountered an error" in error_message.content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("callback_name", "expected_action_name"),
    [
        ("on_search_companies", "ui_search_companies"),
        ("on_ui_create_segment", "ui_create_segment"),
        ("on_view_analytics", "ui_view_analytics"),
        ("on_show_status", "ui_show_status"),
        ("on_create_segment", "ui_create_segment"),
        ("on_push_to_resend", "push_to_resend"),
    ],
)
async def test_action_callbacks_send_expected_follow_up(
    app_context: AppContext,
    monkeypatch,
    callback_name: str,
    expected_action_name: str,
):
    app = app_context.app
    app_context.chainlit.user_session.set("chat_profile", "platform_admin")
    seen: dict[str, Any] = {}

    def fake_build_action_reply(action_name: str, profile_name: str | None, repo_root):
        seen["action_name"] = action_name
        seen["profile_name"] = profile_name
        seen["repo_root"] = repo_root
        return SimpleNamespace(
            content=f"reply:{action_name}",
            actions=[
                app_context.chainlit.Action(
                    name="ui_show_status",
                    payload={"profile": profile_name},
                    label="System Status",
                    tooltip="Inspect status",
                )
            ],
        )

    monkeypatch.setattr(app, "build_action_reply", fake_build_action_reply)

    await getattr(app, callback_name)(object())

    assert seen == {
        "action_name": expected_action_name,
        "profile_name": "platform_admin",
        "repo_root": app.REPO_ROOT,
    }

    sent_message = app_context.chainlit._messages[-1]
    assert sent_message.sent is True
    assert sent_message.content == f"reply:{expected_action_name}"


@pytest.mark.asyncio
async def test_safe_send_message_swallows_message_send_errors(
    app_context: AppContext, monkeypatch
):
    app = app_context.app

    class BrokenMessage:
        async def send(self):
            raise RuntimeError("send exploded")

    monkeypatch.setattr(app.cl, "Message", lambda *args, **kwargs: BrokenMessage())

    await app._safe_send_message("hello")

    assert (
        "error",
        "message_send_failed",
        {"error": "send exploded", "exc_info": True},
    ) in app_context.logger.events


@pytest.mark.asyncio
async def test_action_callbacks_swallow_unhandled_exceptions(app_context: AppContext, monkeypatch):
    app = app_context.app
    monkeypatch.setattr(app, "_send_action_reply", AsyncMock(side_effect=RuntimeError("boom")))

    await app.on_show_status(object())

    assert (
        "error",
        "action_callback_unhandled",
        {"action": "ui_show_status", "error": "boom", "exc_info": True},
    ) in app_context.logger.events
