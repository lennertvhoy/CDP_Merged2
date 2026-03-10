"""Repo-owned Chainlit persistence layer for private chat history."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import asyncpg
from chainlit.data.base import BaseDataLayer
from chainlit.data.utils import queue_until_user_message
from chainlit.element import Element, ElementDict
from chainlit.step import StepDict
from chainlit.types import (
    Feedback,
    FeedbackDict,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)
from chainlit.user import PersistedUser, User

from src.core.logger import get_logger
from src.services.runtime_support_schema import ensure_runtime_support_schema

logger = get_logger(__name__)

MAX_THREAD_NAME_LENGTH = 255


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _compact_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _parse_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def _isoformat(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _truncate_thread_name(name: str | None) -> str | None:
    if name is None:
        return None
    return name[:MAX_THREAD_NAME_LENGTH]


class PostgreSQLChainlitDataLayer(BaseDataLayer):
    """Store user-scoped Chainlit history in app-managed PostgreSQL tables."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self.pool is not None:
            return

        await ensure_runtime_support_schema(connection_url=self.database_url)
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=5,
            command_timeout=60,
        )

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        await self.connect()
        assert self.pool is not None

        async with self.pool.acquire() as connection:
            records = await connection.fetch(query, *(params or {}).values())
            return [dict(record) for record in records]

    async def get_user(self, identifier: str) -> PersistedUser | None:
        rows = await self.execute_query(
            """
            SELECT user_id, identifier, display_name, metadata, created_at
            FROM app_chat_users
            WHERE identifier = $1
            """,
            {"identifier": identifier},
        )
        if not rows:
            return None

        row = rows[0]
        return PersistedUser(
            id=str(row["user_id"]),
            identifier=str(row["identifier"]),
            display_name=row.get("display_name"),
            metadata=_parse_json(row.get("metadata"), {}),
            createdAt=_isoformat(row.get("created_at")) or "",
        )

    async def create_user(self, user: User) -> PersistedUser | None:
        now = _utcnow()
        rows = await self.execute_query(
            """
            INSERT INTO app_chat_users (
                user_id,
                identifier,
                display_name,
                metadata,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4::jsonb, $5, $5)
            ON CONFLICT (identifier) DO UPDATE
            SET display_name = EXCLUDED.display_name,
                metadata = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
            RETURNING user_id, identifier, display_name, metadata, created_at
            """,
            {
                "user_id": str(uuid.uuid4()),
                "identifier": user.identifier,
                "display_name": user.display_name,
                "metadata": json.dumps(user.metadata or {}),
                "now": now,
            },
        )
        if not rows:
            return None

        row = rows[0]
        return PersistedUser(
            id=str(row["user_id"]),
            identifier=str(row["identifier"]),
            display_name=row.get("display_name"),
            metadata=_parse_json(row.get("metadata"), {}),
            createdAt=_isoformat(row.get("created_at")) or "",
        )

    async def delete_feedback(self, feedback_id: str) -> bool:
        await self.execute_query(
            """
            DELETE FROM app_chat_feedback
            WHERE feedback_id = $1
            """,
            {"feedback_id": feedback_id},
        )
        return True

    async def upsert_feedback(self, feedback: Feedback) -> str:
        feedback_id = feedback.id or str(uuid.uuid4())
        now = _utcnow()
        await self.execute_query(
            """
            INSERT INTO app_chat_feedback (
                feedback_id,
                thread_id,
                step_id,
                value,
                comment,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $6)
            ON CONFLICT (feedback_id) DO UPDATE
            SET value = EXCLUDED.value,
                comment = EXCLUDED.comment,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "feedback_id": feedback_id,
                "thread_id": feedback.threadId,
                "step_id": feedback.forId,
                "value": int(feedback.value),
                "comment": feedback.comment,
                "now": now,
            },
        )
        return feedback_id

    @queue_until_user_message()
    async def create_element(self, element: Element) -> None:
        if not element.for_id:
            return

        if element.thread_id:
            await self.update_thread(thread_id=element.thread_id)

        now = _utcnow()
        await self.execute_query(
            """
            INSERT INTO app_chat_elements (
                element_id,
                thread_id,
                step_id,
                element_json,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4::jsonb, $5, $5)
            ON CONFLICT (element_id) DO UPDATE
            SET thread_id = COALESCE(EXCLUDED.thread_id, app_chat_elements.thread_id),
                step_id = COALESCE(EXCLUDED.step_id, app_chat_elements.step_id),
                element_json = app_chat_elements.element_json || EXCLUDED.element_json,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "element_id": element.id,
                "thread_id": element.thread_id,
                "step_id": element.for_id,
                "element_json": json.dumps(element.to_dict()),
                "now": now,
            },
        )

    async def get_element(
        self,
        thread_id: str,
        element_id: str,
    ) -> ElementDict | None:
        rows = await self.execute_query(
            """
            SELECT element_id, thread_id, element_json
            FROM app_chat_elements
            WHERE thread_id = $1 AND element_id = $2
            """,
            {
                "thread_id": thread_id,
                "element_id": element_id,
            },
        )
        if not rows:
            return None

        return self._convert_element_row_to_dict(rows[0])

    @queue_until_user_message()
    async def delete_element(self, element_id: str, thread_id: str | None = None) -> None:
        params: dict[str, Any] = {"element_id": element_id}
        query = """
            DELETE FROM app_chat_elements
            WHERE element_id = $1
        """
        if thread_id is not None:
            query += " AND thread_id = $2"
            params["thread_id"] = thread_id

        await self.execute_query(query, params)

    @queue_until_user_message()
    async def create_step(self, step_dict: StepDict) -> None:
        thread_id = step_dict.get("threadId")
        if thread_id:
            await self.update_thread(thread_id=thread_id)

        parent_id = step_dict.get("parentId")
        if parent_id:
            parent_rows = await self.execute_query(
                """
                SELECT step_id
                FROM app_chat_steps
                WHERE step_id = $1
                """,
                {"step_id": parent_id},
            )
            if not parent_rows:
                await self.create_step(
                    StepDict(
                        id=parent_id,
                        threadId=thread_id or "",
                        type="run",
                        metadata={},
                    )
                )

        payload = _compact_dict(dict(step_dict))
        now = _utcnow()
        await self.execute_query(
            """
            INSERT INTO app_chat_steps (
                step_id,
                thread_id,
                parent_step_id,
                step_json,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4::jsonb, $5, $5)
            ON CONFLICT (step_id) DO UPDATE
            SET thread_id = COALESCE(EXCLUDED.thread_id, app_chat_steps.thread_id),
                parent_step_id = COALESCE(EXCLUDED.parent_step_id, app_chat_steps.parent_step_id),
                step_json = app_chat_steps.step_json || EXCLUDED.step_json,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "step_id": step_dict["id"],
                "thread_id": thread_id,
                "parent_step_id": parent_id,
                "step_json": json.dumps(payload),
                "now": now,
            },
        )

    @queue_until_user_message()
    async def update_step(self, step_dict: StepDict) -> None:
        await self.create_step(step_dict)

    @queue_until_user_message()
    async def delete_step(self, step_id: str) -> None:
        await self.execute_query(
            """
            DELETE FROM app_chat_steps
            WHERE step_id = $1
            """,
            {"step_id": step_id},
        )

    async def get_thread_author(self, thread_id: str) -> str:
        rows = await self.execute_query(
            """
            SELECT u.identifier
            FROM app_chat_threads t
            LEFT JOIN app_chat_users u ON t.user_id = u.user_id
            WHERE t.thread_id = $1
            """,
            {"thread_id": thread_id},
        )
        if not rows:
            return ""
        return str(rows[0].get("identifier") or "")

    async def delete_thread(self, thread_id: str) -> None:
        await self.execute_query(
            """
            DELETE FROM app_chat_threads
            WHERE thread_id = $1
            """,
            {"thread_id": thread_id},
        )

    async def list_threads(
        self,
        pagination: Pagination,
        filters: ThreadFilter,
    ) -> PaginatedResponse[ThreadDict]:
        params: dict[str, Any] = {}
        param_index = 1
        clauses = ["1=1"]

        if filters.userId:
            clauses.append(f"t.user_id = ${param_index}")
            params["user_id"] = filters.userId
            param_index += 1

        if filters.search:
            clauses.append(f"COALESCE(t.name, '') ILIKE ${param_index}")
            params["search"] = f"%{filters.search}%"
            param_index += 1

        if filters.feedback is not None:
            clauses.append(
                "EXISTS ("
                "SELECT 1 FROM app_chat_feedback f "
                f"WHERE f.thread_id = t.thread_id AND f.value = ${param_index}"
                ")"
            )
            params["feedback"] = int(filters.feedback)
            param_index += 1

        if pagination.cursor:
            clauses.append(
                "t.updated_at < ("
                f"SELECT updated_at FROM app_chat_threads WHERE thread_id = ${param_index}"
                ")"
            )
            params["cursor"] = pagination.cursor
            param_index += 1

        query = f"""
            SELECT
                t.thread_id,
                t.name,
                t.user_id,
                t.metadata,
                t.tags,
                t.created_at,
                t.updated_at,
                u.identifier AS user_identifier
            FROM app_chat_threads t
            LEFT JOIN app_chat_users u ON t.user_id = u.user_id
            WHERE {" AND ".join(clauses)}
            ORDER BY t.updated_at DESC
            LIMIT ${param_index}
        """
        params["limit"] = pagination.first + 1

        rows = await self.execute_query(query, params)
        has_next_page = len(rows) > pagination.first
        if has_next_page:
            rows = rows[:-1]

        thread_dicts = [
            ThreadDict(
                id=str(row["thread_id"]),
                createdAt=_isoformat(row.get("updated_at")) or "",
                name=row.get("name"),
                userId=str(row["user_id"]) if row.get("user_id") else None,
                userIdentifier=row.get("user_identifier"),
                tags=_parse_json(row.get("tags"), []),
                metadata=_parse_json(row.get("metadata"), {}),
                steps=[],
                elements=[],
            )
            for row in rows
        ]

        return PaginatedResponse(
            pageInfo=PageInfo(
                hasNextPage=has_next_page,
                startCursor=thread_dicts[0]["id"] if thread_dicts else None,
                endCursor=thread_dicts[-1]["id"] if thread_dicts else None,
            ),
            data=thread_dicts,
        )

    async def get_thread(self, thread_id: str) -> ThreadDict | None:
        thread_rows = await self.execute_query(
            """
            SELECT
                t.thread_id,
                t.name,
                t.user_id,
                t.metadata,
                t.tags,
                t.created_at,
                u.identifier AS user_identifier
            FROM app_chat_threads t
            LEFT JOIN app_chat_users u ON t.user_id = u.user_id
            WHERE t.thread_id = $1
            """,
            {"thread_id": thread_id},
        )
        if not thread_rows:
            return None

        step_rows = await self.execute_query(
            """
            SELECT
                s.step_id,
                s.thread_id,
                s.parent_step_id,
                s.step_json,
                s.created_at,
                f.feedback_id,
                f.value AS feedback_value,
                f.comment AS feedback_comment
            FROM app_chat_steps s
            LEFT JOIN app_chat_feedback f ON s.step_id = f.step_id
            WHERE s.thread_id = $1
            ORDER BY s.created_at ASC
            """,
            {"thread_id": thread_id},
        )
        element_rows = await self.execute_query(
            """
            SELECT element_id, thread_id, element_json
            FROM app_chat_elements
            WHERE thread_id = $1
            ORDER BY created_at ASC
            """,
            {"thread_id": thread_id},
        )

        row = thread_rows[0]
        return ThreadDict(
            id=str(row["thread_id"]),
            createdAt=_isoformat(row.get("created_at")) or "",
            name=row.get("name"),
            userId=str(row["user_id"]) if row.get("user_id") else None,
            userIdentifier=row.get("user_identifier"),
            tags=_parse_json(row.get("tags"), []),
            metadata=_parse_json(row.get("metadata"), {}),
            steps=[self._convert_step_row_to_dict(step_row) for step_row in step_rows],
            elements=[
                self._convert_element_row_to_dict(element_row) for element_row in element_rows
            ],
        )

    async def update_thread(
        self,
        thread_id: str,
        name: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        merged_metadata = metadata
        if metadata is not None:
            rows = await self.execute_query(
                """
                SELECT metadata
                FROM app_chat_threads
                WHERE thread_id = $1
                """,
                {"thread_id": thread_id},
            )
            existing_metadata = _parse_json(rows[0].get("metadata"), {}) if rows else {}
            keys_to_remove = {key for key, value in metadata.items() if value is None}
            cleaned_existing = {
                key: value for key, value in existing_metadata.items() if key not in keys_to_remove
            }
            cleaned_incoming = {key: value for key, value in metadata.items() if value is not None}
            merged_metadata = {**cleaned_existing, **cleaned_incoming}

        metadata_payload = (
            json.dumps(merged_metadata) if merged_metadata is not None else json.dumps({})
        )
        tags_payload = json.dumps(tags) if tags is not None else json.dumps([])
        now = _utcnow()
        await self.execute_query(
            """
            INSERT INTO app_chat_threads (
                thread_id,
                name,
                user_id,
                metadata,
                tags,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $6)
            ON CONFLICT (thread_id) DO UPDATE
            SET name = COALESCE(EXCLUDED.name, app_chat_threads.name),
                user_id = COALESCE(EXCLUDED.user_id, app_chat_threads.user_id),
                metadata = CASE
                    WHEN $4::jsonb = '{}'::jsonb AND $7 = FALSE THEN app_chat_threads.metadata
                    ELSE EXCLUDED.metadata
                END,
                tags = CASE
                    WHEN $5::jsonb = '[]'::jsonb AND $8 = FALSE THEN app_chat_threads.tags
                    ELSE EXCLUDED.tags
                END,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "thread_id": thread_id,
                "name": _truncate_thread_name(name),
                "user_id": user_id,
                "metadata": metadata_payload,
                "tags": tags_payload,
                "now": now,
                "metadata_provided": metadata is not None,
                "tags_provided": tags is not None,
            },
        )

    async def build_debug_url(self) -> str:
        return ""

    async def get_favorite_steps(self, user_id: str) -> list[StepDict]:
        rows = await self.execute_query(
            """
            SELECT
                s.step_id,
                s.thread_id,
                s.parent_step_id,
                s.step_json,
                s.created_at
            FROM app_chat_steps s
            JOIN app_chat_threads t ON s.thread_id = t.thread_id
            WHERE t.user_id = $1
              AND COALESCE(s.step_json->'metadata'->>'favorite', 'false') = 'true'
            ORDER BY s.created_at DESC
            """,
            {"user_id": user_id},
        )
        return [self._convert_step_row_to_dict(row) for row in rows]

    def _convert_step_row_to_dict(self, row: dict[str, Any]) -> StepDict:
        payload = _parse_json(row.get("step_json"), {})
        feedback: FeedbackDict | None = None
        if row.get("feedback_id") is not None:
            feedback = cast(
                FeedbackDict,
                {
                    "forId": str(row["step_id"]),
                    "id": str(row["feedback_id"]),
                    "value": row.get("feedback_value"),
                    "comment": row.get("feedback_comment"),
                },
            )

        return StepDict(
            id=str(row["step_id"]),
            threadId=str(row.get("thread_id") or payload.get("threadId") or ""),
            parentId=row.get("parent_step_id") or payload.get("parentId"),
            name=payload.get("name"),
            type=payload.get("type", "run"),
            input=payload.get("input", ""),
            output=payload.get("output", ""),
            metadata=payload.get("metadata", {}),
            createdAt=payload.get("createdAt") or _isoformat(row.get("created_at")),
            start=payload.get("start"),
            end=payload.get("end"),
            showInput=payload.get("showInput"),
            isError=payload.get("isError"),
            feedback=feedback,
        )

    def _convert_element_row_to_dict(self, row: dict[str, Any]) -> ElementDict:
        payload = _parse_json(row.get("element_json"), {})
        return ElementDict(
            id=str(row["element_id"]),
            threadId=payload.get("threadId") or row.get("thread_id"),
            type=payload.get("type", "file"),
            url=payload.get("url"),
            name=payload.get("name", ""),
            mime=payload.get("mime"),
            objectKey=payload.get("objectKey"),
            forId=payload.get("forId"),
            chainlitKey=payload.get("chainlitKey"),
            display=payload.get("display", "inline"),
            size=payload.get("size"),
            language=payload.get("language"),
            page=payload.get("page"),
            autoPlay=payload.get("autoPlay"),
            playerConfig=payload.get("playerConfig"),
            props=payload.get("props"),
        )
