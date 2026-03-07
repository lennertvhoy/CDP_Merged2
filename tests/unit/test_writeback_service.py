from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.writeback import (
    WritebackResult,
    WritebackService,
    WritebackStatus,
)


class _AcquireContext:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _AcquireContext(self._conn)


def _build_service():
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock()
    conn.fetchrow = AsyncMock()

    postgresql = MagicMock()
    postgresql.connect = AsyncMock()
    postgresql.disconnect = AsyncMock()
    postgresql.ensure_connected = AsyncMock()
    postgresql.pool = _Pool(conn)

    service = WritebackService(postgresql_client=postgresql, tracardi_client=MagicMock())
    return service, postgresql, conn


def test_normalize_event_extracts_uid_timestamp_and_numeric_value():
    service, _, _ = _build_service()
    event = {
        "id": "evt-1",
        "type": "score.updated",
        "profile": {"id": "uid-1"},
        "properties": {"channel": "email", "score_value": "3.5"},
        "metadata": {"time": {"insert": "2026-03-03T12:30:00Z"}},
    }

    normalized = service._normalize_event(event)

    assert normalized == {
        "uid": "uid-1",
        "organization_uid": "uid-1",
        "event_type": "score.updated",
        "event_channel": "email",
        "event_source": "tracardi",
        "source_event_id": "evt-1",
        "occurred_at": datetime(2026, 3, 3, 12, 30),
        "event_value": 3.5,
        "attributes": '{"channel": "email", "score_value": "3.5"}',
    }


def test_normalize_event_skips_unsupported_or_uidless_events():
    service, _, _ = _build_service()

    assert service._normalize_event({"type": "custom.event"}) is None
    assert service._normalize_event({"type": "email.sent", "profile": {}}) is None


@pytest.mark.asyncio
async def test_extract_and_write_trait_persists_tag_assignment():
    service, postgresql, conn = _build_service()
    event = {
        "id": "evt-1",
        "type": "tag.assigned",
        "profile": {"id": "uid-1"},
        "properties": {"tag_name": "vip"},
    }

    result = await service._extract_and_write_trait(event)

    assert result is True
    postgresql.ensure_connected.assert_awaited_once()
    execute_args = conn.execute.await_args.args
    assert execute_args[1] == "uid-1"
    assert execute_args[2] == "tag_vip"
    assert execute_args[5] is True
    assert execute_args[7] == "tracardi_projection"
    assert execute_args[8] == "evt-1"


@pytest.mark.asyncio
async def test_extract_and_write_ai_decision_uses_metadata_timestamp():
    service, _, conn = _build_service()
    event = {
        "id": "evt-2",
        "type": "ai.decision",
        "profile": {"id": "uid-2"},
        "properties": {
            "decision_type": "segment",
            "decision_name": "upsell",
            "decision_value": "high",
            "confidence": 0.8,
            "model_name": "gpt-4o-mini",
            "model_version": "2026-03-01",
            "explanation": {"reason": "recent activity"},
        },
        "metadata": {"time": {"insert": "2026-03-03T09:15:00Z"}},
    }

    result = await service._extract_and_write_ai_decision(event)

    assert result is True
    execute_args = conn.execute.await_args.args
    assert execute_args[1] == "uid-2"
    assert execute_args[2] == "segment"
    assert execute_args[3] == "upsell"
    assert execute_args[4] == "high"
    assert execute_args[5] == 0.8
    assert execute_args[9] == datetime(2026, 3, 3, 9, 15)


@pytest.mark.asyncio
async def test_process_event_counts_written_records_and_handles_webhook():
    service, _, _ = _build_service()
    event = {"id": "evt-3", "type": "email.sent"}
    normalized = {"uid": "uid-1", "event_type": "email.sent"}

    service._normalize_event = MagicMock(return_value=normalized)
    service._write_event_fact = AsyncMock(return_value=True)
    service._extract_and_write_trait = AsyncMock(return_value=True)
    service._extract_and_write_ai_decision = AsyncMock(return_value=False)

    result = await service.handle_webhook({"event": event})

    assert result.event_id == "evt-3"
    assert result.status is WritebackStatus.SUCCESS
    assert result.records_written == 2


@pytest.mark.asyncio
async def test_process_event_returns_failed_on_exception():
    service, _, _ = _build_service()
    service._normalize_event = MagicMock(side_effect=RuntimeError("boom"))

    result = await service.process_event({"id": "evt-4", "type": "email.sent"})

    assert result.status is WritebackStatus.FAILED
    assert result.error_message == "boom"


@pytest.mark.asyncio
async def test_process_events_aggregates_success_failed_and_skipped_counts():
    service, _, _ = _build_service()
    service.process_event = AsyncMock(
        side_effect=[
            WritebackResult(event_id="evt-1", status=WritebackStatus.SUCCESS, records_written=1),
            WritebackResult(event_id="evt-2", status=WritebackStatus.FAILED, error_message="boom"),
            WritebackResult(event_id="evt-3", status=WritebackStatus.SKIPPED),
        ]
    )

    result = await service.process_events([{"id": "evt-1"}, {"id": "evt-2"}, {"id": "evt-3"}])

    assert result.total_events == 3
    assert result.success == 1
    assert result.failed == 1
    assert result.skipped == 1


@pytest.mark.asyncio
async def test_poll_and_process_returns_empty_batch_until_fetch_is_implemented():
    service, _, _ = _build_service()

    result = await service.poll_and_process(limit=25)

    assert result.total_events == 0
    assert result.success == 0
    assert result.failed == 0
    assert result.skipped == 0
    assert result.results == []


@pytest.mark.asyncio
async def test_sync_traits_returns_skipped_placeholder_result():
    service, _, _ = _build_service()

    result = await service.sync_traits("uid-123")

    assert result.uid == "uid-123"
    assert result.traits_synced == 0
    assert result.status is WritebackStatus.SKIPPED


@pytest.mark.asyncio
async def test_get_writeback_metrics_reads_event_trait_and_ai_counts():
    service, postgresql, conn = _build_service()
    conn.fetch.return_value = [
        {"event_type": "email.sent", "count": 2},
        {"event_type": "ai.decision", "count": 1},
    ]
    last_writeback_at = datetime(2026, 3, 3, 14, 0, 0)
    conn.fetchrow.side_effect = [
        {"count": 4},
        {"count": 1},
        {"last_at": last_writeback_at},
    ]

    metrics = await service.get_writeback_metrics()

    assert metrics.total_events_processed == 3
    assert metrics.events_by_type == {"email.sent": 2, "ai.decision": 1}
    assert metrics.traits_created == 4
    assert metrics.ai_decisions_created == 1
    assert metrics.last_writeback_at == last_writeback_at
    postgresql.ensure_connected.assert_awaited_once()
