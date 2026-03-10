from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from chainlit.types import Pagination, ThreadFilter
from chainlit.user import User

from src.services.chainlit_data_layer import PostgreSQLChainlitDataLayer


@pytest.mark.asyncio
async def test_create_user_returns_persisted_user(monkeypatch):
    layer = PostgreSQLChainlitDataLayer("postgresql://runtime")
    captured: dict[str, Any] = {}

    async def fake_execute_query(query: str, params: dict[str, Any] | None = None):
        captured["query"] = query
        captured["params"] = params
        return [
            {
                "user_id": "user-123",
                "identifier": "jane@example.com",
                "display_name": "Jane Doe",
                "metadata": {"provider": "azure-ad"},
                "created_at": datetime(2026, 3, 9, 21, 0, tzinfo=UTC),
            }
        ]

    monkeypatch.setattr(layer, "execute_query", fake_execute_query)

    persisted = await layer.create_user(
        User(
            identifier="jane@example.com",
            display_name="Jane Doe",
            metadata={"provider": "azure-ad"},
        )
    )

    assert persisted is not None
    assert persisted.id == "user-123"
    assert persisted.identifier == "jane@example.com"
    assert persisted.display_name == "Jane Doe"
    assert persisted.metadata == {"provider": "azure-ad"}
    assert captured["params"]["display_name"] == "Jane Doe"
    assert json.loads(captured["params"]["metadata"]) == {"provider": "azure-ad"}


@pytest.mark.asyncio
async def test_update_thread_merges_metadata_and_truncates_name(monkeypatch):
    layer = PostgreSQLChainlitDataLayer("postgresql://runtime")
    queries: list[tuple[str, dict[str, Any] | None]] = []

    async def fake_execute_query(query: str, params: dict[str, Any] | None = None):
        queries.append((query, params))
        if "SELECT metadata" in query:
            return [{"metadata": {"chat_profile": "marketing_manager", "keep": "yes", "drop": "x"}}]
        return []

    monkeypatch.setattr(layer, "execute_query", fake_execute_query)

    await layer.update_thread(
        thread_id="thread-123",
        name="x" * 300,
        user_id="user-123",
        metadata={"chat_profile": "sales_rep", "drop": None, "workspace": "private"},
        tags=["sales_rep"],
    )

    _, params = queries[-1]
    assert params is not None
    assert params["name"] == "x" * 255
    assert json.loads(params["metadata"]) == {
        "chat_profile": "sales_rep",
        "keep": "yes",
        "workspace": "private",
    }
    assert json.loads(params["tags"]) == ["sales_rep"]


@pytest.mark.asyncio
async def test_update_thread_defaults_metadata_and_tags_for_new_rows(monkeypatch):
    layer = PostgreSQLChainlitDataLayer("postgresql://runtime")
    queries: list[tuple[str, dict[str, Any] | None]] = []

    async def fake_execute_query(query: str, params: dict[str, Any] | None = None):
        queries.append((query, params))
        return []

    monkeypatch.setattr(layer, "execute_query", fake_execute_query)

    await layer.update_thread(thread_id="thread-blank")

    _, params = queries[-1]
    assert params is not None
    assert json.loads(params["metadata"]) == {}
    assert json.loads(params["tags"]) == []
    assert params["metadata_provided"] is False
    assert params["tags_provided"] is False


@pytest.mark.asyncio
async def test_get_thread_rehydrates_steps_elements_and_feedback(monkeypatch):
    layer = PostgreSQLChainlitDataLayer("postgresql://runtime")
    created_at = datetime(2026, 3, 9, 21, 15, tzinfo=UTC)

    async def fake_execute_query(query: str, params: dict[str, Any] | None = None):
        _ = params
        if "FROM app_chat_threads" in query:
            return [
                {
                    "thread_id": "thread-123",
                    "name": "Find software companies",
                    "user_id": "user-123",
                    "metadata": {"chat_profile": "data_analyst"},
                    "tags": ["data_analyst"],
                    "created_at": created_at,
                    "user_identifier": "jane@example.com",
                }
            ]
        if "FROM app_chat_steps" in query:
            return [
                {
                    "step_id": "step-user",
                    "thread_id": "thread-123",
                    "parent_step_id": None,
                    "step_json": {
                        "id": "step-user",
                        "threadId": "thread-123",
                        "type": "user_message",
                        "name": "user",
                        "input": "Find software companies",
                        "metadata": {"favorite": True},
                    },
                    "created_at": created_at,
                    "feedback_id": "feedback-1",
                    "feedback_value": 1,
                    "feedback_comment": "helpful",
                }
            ]
        if "FROM app_chat_elements" in query:
            return [
                {
                    "element_id": "element-1",
                    "thread_id": "thread-123",
                    "element_json": {
                        "id": "element-1",
                        "threadId": "thread-123",
                        "type": "file",
                        "name": "report.csv",
                        "display": "inline",
                        "forId": "step-user",
                    },
                }
            ]
        raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(layer, "execute_query", fake_execute_query)

    thread = await layer.get_thread("thread-123")

    assert thread is not None
    assert thread["id"] == "thread-123"
    assert thread["userIdentifier"] == "jane@example.com"
    assert thread["metadata"] == {"chat_profile": "data_analyst"}
    assert thread["tags"] == ["data_analyst"]
    assert len(thread["steps"]) == 1
    assert thread["steps"][0]["feedback"]["value"] == 1
    assert thread["steps"][0]["metadata"] == {"favorite": True}
    assert len(thread["elements"]) == 1
    assert thread["elements"][0]["name"] == "report.csv"


@pytest.mark.asyncio
async def test_list_threads_applies_user_filter(monkeypatch):
    layer = PostgreSQLChainlitDataLayer("postgresql://runtime")
    seen: dict[str, Any] = {}

    async def fake_execute_query(query: str, params: dict[str, Any] | None = None):
        seen["query"] = query
        seen["params"] = params
        return []

    monkeypatch.setattr(layer, "execute_query", fake_execute_query)

    response = await layer.list_threads(
        Pagination(first=10),
        ThreadFilter(userId="user-123", search="prospects"),
    )

    assert response.data == []
    assert "t.user_id = $1" in seen["query"]
    assert "ILIKE $2" in seen["query"]
    assert seen["params"]["user_id"] == "user-123"
    assert seen["params"]["search"] == "%prospects%"
    assert seen["params"]["limit"] == 11
