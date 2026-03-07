"""
Chainlit UI for CDP_Merged.
Merges CDPT's working workflow with CDP's transparent assistant patterns.
"""

import os
import uuid
from pathlib import Path

import aiosqlite
import chainlit as cl
import httpx
from chainlit.oauth_providers import get_configured_oauth_providers
from chainlit.server import app as chainlit_server_app
from chainlit.user import User
from fastapi import Request
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.config import settings
from src.core.constants import MAX_QUERY_LENGTH
from src.core.exceptions import TracardiError
from src.core.logger import bind_trace_id, clear_trace_id, configure_logging, get_logger
from src.core.metrics import ERRORS_TOTAL, QUERY_REQUESTS_TOTAL
from src.graph.workflow import compile_workflow
from src.services.postgresql_search import get_search_service
from src.services.runtime_support_schema import ensure_runtime_support_schema
from src.services.tracardi import TracardiClient
from src.ui.actions import build_action_reply, build_welcome_actions
from src.ui.components import build_chat_profiles, build_starters
from src.ui.formatters import DEFAULT_CHAT_PROFILE, build_status_cards, build_welcome_markdown

# Configure structured logging on startup
configure_logging(settings.LOG_LEVEL)

logger = get_logger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE_ENDPOINT_PATHS = {
    "/healthz",
    "/project/healthz",
    "/readinessz",
    "/project/readinessz",
}


def _disabled_chainlit_data_layer():
    """Prevent Chainlit from auto-binding DATABASE_URL to its own persistence schema."""
    return None


cl.data_layer(_disabled_chainlit_data_layer)


def _oauth_display_name(raw_user_data: dict[str, str], default_user: User) -> str | None:
    return (
        raw_user_data.get("name")
        or raw_user_data.get("display_name")
        or raw_user_data.get("displayName")
        or raw_user_data.get("given_name")
        or raw_user_data.get("preferred_username")
        or default_user.display_name
    )


async def oauth_user_callback(
    provider_id: str,
    _token: str,
    raw_user_data: dict[str, str],
    default_user: User,
    _id_token: str | None = None,
) -> User | None:
    """Accept authenticated OAuth users and normalize basic profile fields.

    Args:
        provider_id: OAuth provider identifier (e.g., 'google', 'azure-ad')
        _token: Access token from the provider (unused but required by Chainlit)
        raw_user_data: User profile data from the OAuth provider
        default_user: Default user object from Chainlit with base identifier
        _id_token: Optional ID token (unused but required by Chainlit)

    Returns:
        User: Normalized user with display name and provider metadata,
              or None to reject the authentication.
    """
    if not default_user.identifier:
        logger.warning("oauth_callback_rejected", reason="missing_user_identifier")
        return None

    metadata = dict(default_user.metadata or {})
    metadata["provider"] = provider_id
    return User(
        identifier=default_user.identifier,
        display_name=_oauth_display_name(raw_user_data, default_user),
        metadata=metadata,
    )


def _register_oauth_callback() -> bool:
    """Register OAuth only when provider env vars exist; bare decorators raise otherwise."""
    try:
        configured_providers = tuple(get_configured_oauth_providers())
    except Exception as exc:
        logger.warning("oauth_provider_detection_failed", error=str(exc))
        return False

    if not configured_providers:
        return False

    cl.oauth_callback(oauth_user_callback)
    logger.info("oauth_callback_registered", providers=list(configured_providers))
    return True


OAUTH_CALLBACK_ENABLED = _register_oauth_callback()


def _safe_user_session_get(key: str, default=None):
    """Read Chainlit session state without failing when no request context exists."""
    try:
        return cl.user_session.get(key, default)
    except Exception:
        return default


@chainlit_server_app.middleware("http")
async def probe_endpoint_middleware(request: Request, call_next):
    """Serve probe endpoints before Chainlit's catch-all HTML route."""
    if request.url.path in PROBE_ENDPOINT_PATHS:
        if request.url.path.endswith("healthz"):
            return JSONResponse(status_code=200, content=await healthz())
        return await readinessz()

    return await call_next(request)


@chainlit_server_app.get("/project/healthz")
@chainlit_server_app.get("/healthz")
async def healthz():
    """Lightweight health endpoint for container probes."""
    return {"status": "ok", "service": "cdp-merged", "llm_provider": settings.LLM_PROVIDER}


def _database_config_source() -> str | None:
    """Report which runtime source will provide PostgreSQL connectivity."""
    if os.getenv("DATABASE_URL"):
        return "env:DATABASE_URL"

    env_database_path = REPO_ROOT / ".env.database"
    if env_database_path.exists():
        return "file:.env.database"

    return None


@chainlit_server_app.get("/project/readinessz")
@chainlit_server_app.get("/readinessz")
async def readinessz():
    """Probe the deployed chat runtime, including PostgreSQL-backed query readiness."""
    config_source = _database_config_source()

    checks: dict[str, dict[str, object]] = {
        "app": {
            "status": "ok",
            "service": "cdp-merged",
            "llm_provider": settings.LLM_PROVIDER,
        }
    }

    if not config_source:
        error = "DATABASE_URL is not configured and local .env.database is unavailable."
        checks["postgresql"] = {
            "status": "error",
            "configured": False,
            "error": error,
        }
        checks["tool_layer"] = {
            "status": "error",
            "backend": "postgresql",
            "error": error,
        }
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "service": "cdp-merged",
                "checks": checks,
            },
        )

    try:
        search_service = get_search_service()
        probe = await search_service.readiness_probe()
    except Exception as exc:
        logger.error("readiness_probe_failed", error=str(exc))
        checks["postgresql"] = {
            "status": "error",
            "configured": True,
            "source": config_source,
            "error": str(exc),
        }
        checks["tool_layer"] = {
            "status": "error",
            "backend": "postgresql",
            "error": str(exc),
        }
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "service": "cdp-merged",
                "checks": checks,
            },
        )

    checks["postgresql"] = {
        "status": "ok",
        "configured": True,
        "source": config_source,
        "companies_table": probe["companies_table"],
    }
    checks["tool_layer"] = {
        "status": "ok",
        "backend": probe["backend"],
        "query_plane": "ready",
    }
    # Verify action processing capability (basic import check)
    try:
        # Import check only - modules are already imported at module level
        # but we verify they can be accessed from this context
        _ = build_action_reply  # noqa: F841
        _ = build_welcome_actions  # noqa: F841
        checks["action_processing"] = {
            "status": "ok",
            "ui_actions_available": True,
        }
    except Exception as action_exc:
        checks["action_processing"] = {
            "status": "warning",
            "ui_actions_available": False,
            "error": str(action_exc),
        }

    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "service": "cdp-merged",
            "checks": checks,
        },
    )


@chainlit_server_app.on_event("startup")
async def ensure_runtime_postgresql_support_schema() -> None:
    """Backfill local/runtime support tables for already-initialized databases."""
    if not _database_config_source():
        return

    try:
        search_service = get_search_service()
        await search_service.ensure_connected()
        ensured = await ensure_runtime_support_schema(search_service._client)
        logger.info("runtime_support_schema_startup", ensured=ensured)
    except Exception as exc:
        logger.warning("runtime_support_schema_startup_failed", error=str(exc))


@cl.set_chat_profiles
async def set_chat_profiles(_current_user=None, _language=None):
    """Expose role-specific chat profiles in the launcher."""
    return build_chat_profiles()


@cl.set_starters
async def set_starters(_current_user=None, _language=None):
    """Provide profile-aware starter prompts."""
    return build_starters(_safe_user_session_get("chat_profile"))


@cl.on_chat_start
async def start():
    """Initialize the chat session."""
    # Generate a trace ID for this session
    trace_id = str(uuid.uuid4())
    bind_trace_id(trace_id)
    cl.user_session.set("trace_id", trace_id)

    # Initialize workflow with persistent SQLite checkpointer
    # This ensures state (like last_search_tql) persists across separate
    # graph invocations, fixing the segment creation bug.
    checkpointer_path = Path("./data/checkpoints/checkpoints.db")
    checkpointer_path.parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(checkpointer_path)
    checkpointer = AsyncSqliteSaver(conn)
    workflow = compile_workflow(checkpointer=checkpointer)
    cl.user_session.set("workflow", workflow)
    cl.user_session.set("checkpointer_conn", conn)

    # Set up thread ID for conversation tracking
    thread_id = cl.user_session.get("id")
    cl.user_session.set("thread_id", thread_id)
    chat_profile = cl.user_session.get("chat_profile") or DEFAULT_CHAT_PROFILE
    cl.user_session.set("chat_profile", chat_profile)

    # Initialize Tracardi profile, but keep chat startup resilient if unavailable.
    profile_id = None
    try:
        tracardi = TracardiClient()
        profile = await tracardi.get_or_create_profile(session_id=thread_id)
        profile_id = profile.get("id") if profile else None
    except (TracardiError, httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning("tracardi_profile_bootstrap_failed", error=str(exc))
    cl.user_session.set("profile_id", profile_id)

    logger.info(
        "session_started",
        thread_id=thread_id,
        profile_id=profile_id,
        chat_profile=chat_profile,
    )

    status_cards = build_status_cards(REPO_ROOT)
    welcome = build_welcome_markdown(chat_profile, status_cards)
    await cl.Message(
        content=welcome,
        actions=build_welcome_actions(chat_profile),
    ).send()


@cl.on_chat_end
async def end():
    """Close the per-session checkpointer connection cleanly."""
    conn = cl.user_session.get("checkpointer_conn")
    if conn:
        await conn.close()
    clear_trace_id()


@cl.on_message
async def main(message: cl.Message):
    """Handle user messages."""
    workflow = cl.user_session.get("workflow")
    thread_id = cl.user_session.get("thread_id")
    profile_id = cl.user_session.get("profile_id")

    # ─── Session state validation ────────────────────────────────────────────
    if not workflow:
        logger.error("workflow_not_initialized", thread_id=thread_id)
        await cl.Message(
            content="❌ Chat session not properly initialized. Please refresh the page and try again."
        ).send()
        return

    if not thread_id:
        logger.error("thread_id_missing")
        await cl.Message(
            content="❌ Session ID not found. Please refresh the page and try again."
        ).send()
        return

    # Re-bind trace ID for this session
    trace_id = cl.user_session.get("trace_id") or str(uuid.uuid4())
    bind_trace_id(trace_id)

    # ─── Input length guard ──────────────────────────────────────────────────
    if len(message.content) > MAX_QUERY_LENGTH:
        ERRORS_TOTAL.labels(error_type="query_too_long").inc()
        logger.warning(
            "query_too_long",
            length=len(message.content),
            max=MAX_QUERY_LENGTH,
        )
        await cl.Message(
            content=f"❌ Query too long ({len(message.content)} chars). Maximum is {MAX_QUERY_LENGTH} characters."
        ).send()
        return

    logger.info("message_received", thread_id=thread_id, query_length=len(message.content))

    inputs = {
        "messages": [HumanMessage(content=message.content)],
        "language": "",
        "profile_id": profile_id,
    }
    config = {"configurable": {"thread_id": thread_id}}

    async with cl.Step(name="🔍 Processing Query", type="run") as step:
        final_answer = ""
        tool_calls = []
        msg = cl.Message(content="")

        try:
            async for event in workflow.astream_events(inputs, config=config, version="v2"):
                kind = event["event"]
                name = event.get("name")

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if getattr(chunk, "content", None) and isinstance(chunk.content, str):
                        await msg.stream_token(chunk.content)
                        final_answer += chunk.content
                elif kind == "on_tool_start":
                    if name and name != "agent":
                        tool_calls.append(name)

            step.output = (
                f"Used {len(tool_calls)} tool call(s) to process your query."
                if tool_calls
                else "Query processed directly."
            )
            QUERY_REQUESTS_TOTAL.labels(status="success").inc()
            logger.info("query_complete", tool_calls=len(tool_calls))

        except Exception as exc:
            step.is_error = True
            step.output = f"Error during processing: {exc}"
            QUERY_REQUESTS_TOTAL.labels(status="error").inc()
            ERRORS_TOTAL.labels(error_type=type(exc).__name__).inc()
            logger.error("query_error", error=str(exc), exc_info=exc)
            await cl.Message(content=f"❌ Sorry, I encountered an error: {exc}").send()
            return

    if final_answer:
        await msg.send()
    else:
        await cl.Message(
            content="I apologize, but I couldn't generate a response. Please try again."
        ).send()

    clear_trace_id()


async def _send_action_reply(action_name: str):
    """Send action reply with comprehensive error handling."""
    try:
        chat_profile = _safe_user_session_get("chat_profile") or DEFAULT_CHAT_PROFILE
        reply = build_action_reply(action_name, chat_profile, REPO_ROOT)
        await _safe_send_message(reply.content, reply.actions)
    except Exception as exc:
        logger.error("action_reply_failed", action=action_name, error=str(exc), exc_info=True)
        await _safe_send_message(
            "❌ Sorry, I couldn't process that action. Please try typing your request instead."
        )


async def _safe_send_message(content: str, actions: list[cl.Action] | None = None) -> None:
    """Attempt to send a Chainlit message without surfacing callback-breaking exceptions."""
    try:
        await cl.Message(content=content, actions=actions or []).send()
    except Exception as exc:
        logger.error("message_send_failed", error=str(exc), exc_info=True)


async def _run_action_callback(action_name: str, action) -> None:
    """Run callback logic and swallow edge-case send/context errors."""
    _ = action
    try:
        await _send_action_reply(action_name)
    except Exception as exc:
        logger.error(
            "action_callback_unhandled",
            action=action_name,
            error=str(exc),
            exc_info=True,
        )


@cl.action_callback("ui_search_companies")
async def on_search_companies(action):
    """Handle company-search quick action."""
    await _run_action_callback("ui_search_companies", action)


@cl.action_callback("ui_create_segment")
async def on_ui_create_segment(action):
    """Handle segment-design quick action."""
    await _run_action_callback("ui_create_segment", action)


@cl.action_callback("ui_view_analytics")
async def on_view_analytics(action):
    """Handle analytics quick action."""
    await _run_action_callback("ui_view_analytics", action)


@cl.action_callback("ui_show_status")
async def on_show_status(action):
    """Handle system-status quick action."""
    await _run_action_callback("ui_show_status", action)


@cl.action_callback("create_segment")
async def on_create_segment(action):
    """Handle segment creation action."""
    await _run_action_callback("ui_create_segment", action)


@cl.action_callback("push_to_resend")
async def on_push_to_resend(action):
    """Handle Resend push action."""
    await _run_action_callback("push_to_resend", action)
