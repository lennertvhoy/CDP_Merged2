from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.projection import (
    BatchProjectionResult,
    ProjectionResult,
    ProjectionService,
    ProjectionState,
    ProjectionStatus,
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
    tracardi = MagicMock()
    tracardi.import_profiles = AsyncMock()
    service = ProjectionService(postgresql_client=postgresql, tracardi_client=tracardi)
    return service, postgresql, tracardi, conn


def test_build_profile_payload_is_pii_light_and_hash_is_stable():
    service, _, _, _ = _build_service()

    org = {
        "id": "org-1",
        "kbo_number": "0123456789",
        "company_name": "Acme BV",
        "legal_form": "BV",
        "industry_nace_code": "62010",
        "nace_description": "Software",
        "city": "Gent",
        "postal_code": "9000",
        "country": "BE",
        "founded_date": date(2020, 1, 2),
        "main_email": "info@example.com",
        "main_phone": "+3200000000",
        "website_url": "https://example.com",
        "sync_status": "enriched",
        "last_sync_at": datetime(2026, 3, 3, 10, 0, 0),
        "employee_count": 25,
        "company_size": "small",
        "revenue_range": "1M-5M",
        "geo_latitude": 51.05,
        "geo_longitude": 3.72,
    }
    traits = [{"trait_name": "lead_score", "trait_value_number": 87}]
    segments = ["high_value"]

    payload = service._build_profile_payload(org, traits, segments)
    reversed_payload = {
        "traits": payload["traits"],
        "ids": payload["ids"],
        "id": payload["id"],
    }

    assert payload["traits"]["business"]["has_email"] is True
    assert payload["traits"]["business"]["has_phone"] is True
    assert payload["traits"]["business"]["has_website"] is True
    assert payload["traits"]["business"]["founded_date"] == "2020-01-02"
    assert payload["traits"]["location"]["latitude"] == 51.05
    assert payload["traits"]["ai"] == {"lead_score": 87}
    assert payload["traits"]["segments"] == ["high_value"]
    assert "main_email" not in payload["traits"]["business"]
    assert service._compute_hash(payload) == service._compute_hash(reversed_payload)


@pytest.mark.asyncio
async def test_project_profile_returns_failed_when_profile_missing():
    service, postgresql, tracardi, _ = _build_service()
    postgresql.get_profile_by_id = AsyncMock(return_value=None)
    postgresql.get_profile_by_kbo = AsyncMock(return_value=None)

    result = await service.project_profile("missing-uid")

    assert result.status is ProjectionStatus.FAILED
    assert result.error_message == "Profile not found in PostgreSQL"
    tracardi.import_profiles.assert_not_awaited()


@pytest.mark.asyncio
async def test_project_profile_skips_when_hash_matches_existing_state():
    service, postgresql, tracardi, _ = _build_service()
    org = {"id": "uid-1", "company_name": "Acme BV"}
    postgresql.get_profile_by_id = AsyncMock(return_value=org)
    service._get_traits = AsyncMock(return_value=[])
    service._get_segment_memberships = AsyncMock(return_value=[])

    projection_hash = service._compute_hash(service._build_profile_payload(org, [], []))
    service._get_projection_state = AsyncMock(
        return_value=ProjectionState(
            uid="uid-1",
            target_system="tracardi",
            last_projected_at=None,
            projection_hash=projection_hash,
            projection_status="success",
            last_error=None,
        )
    )

    result = await service.project_profile("uid-1")

    assert result == ProjectionResult(
        uid="uid-1",
        status=ProjectionStatus.SKIPPED,
        projection_hash=projection_hash,
    )
    tracardi.import_profiles.assert_not_awaited()


@pytest.mark.asyncio
async def test_project_profile_falls_back_to_kbo_and_records_success():
    service, postgresql, tracardi, _ = _build_service()
    org = {
        "id": "uid-1",
        "kbo_number": "0123456789",
        "company_name": "Acme BV",
        "main_email": "info@example.com",
        "main_phone": "+3200000000",
    }
    postgresql.get_profile_by_id = AsyncMock(return_value=None)
    postgresql.get_profile_by_kbo = AsyncMock(return_value=org)
    service._get_traits = AsyncMock(
        return_value=[{"trait_name": "lead_score", "trait_value_number": 91}]
    )
    service._get_segment_memberships = AsyncMock(return_value=["warm_leads"])
    service._get_projection_state = AsyncMock(return_value=None)
    service._record_projection_state = AsyncMock()
    service._update_tracardi_link = AsyncMock()
    tracardi.import_profiles.return_value = {"id": "tracardi-123"}

    result = await service.project_profile("uid-1")

    assert result.status is ProjectionStatus.SUCCESS
    assert result.tracardi_profile_id == "tracardi-123"
    assert set(result.projected_fields or []) == {"business", "enrichment", "ai", "segments"}
    postgresql.get_profile_by_kbo.assert_awaited_once_with("uid-1")
    tracardi.import_profiles.assert_awaited_once()

    payload = tracardi.import_profiles.await_args.args[0][0]
    assert payload["traits"]["business"]["has_email"] is True
    assert payload["traits"]["business"]["has_phone"] is True
    assert payload["traits"]["ai"] == {"lead_score": 91}
    assert payload["traits"]["segments"] == ["warm_leads"]

    service._record_projection_state.assert_awaited_once()
    service._update_tracardi_link.assert_awaited_once_with("uid-1", "tracardi-123")


@pytest.mark.asyncio
async def test_project_batch_aggregates_status_counts():
    service, _, _, _ = _build_service()
    service.project_profile = AsyncMock(
        side_effect=[
            ProjectionResult(uid="1", status=ProjectionStatus.SUCCESS),
            ProjectionResult(uid="2", status=ProjectionStatus.FAILED),
            ProjectionResult(uid="3", status=ProjectionStatus.SKIPPED),
        ]
    )

    result = await service.project_batch(["1", "2", "3"], batch_size=2)

    assert result.total == 3
    assert result.success == 1
    assert result.failed == 1
    assert result.skipped == 1


@pytest.mark.asyncio
async def test_project_segment_projects_members_and_marks_segment_projected():
    service, postgresql, _, conn = _build_service()
    conn.fetch.return_value = [{"uid": "uid-1"}, {"uid": "uid-2"}]
    service.project_batch = AsyncMock(
        return_value=BatchProjectionResult(
            total=2,
            success=1,
            failed=1,
            skipped=0,
            results=[
                ProjectionResult(uid="uid-1", status=ProjectionStatus.SUCCESS),
                ProjectionResult(uid="uid-2", status=ProjectionStatus.FAILED),
            ],
        )
    )

    result = await service.project_segment("warm_leads")

    assert result.segment_key == "warm_leads"
    assert result.total_members == 2
    assert result.projected == 1
    assert result.failed == 1
    postgresql.ensure_connected.assert_awaited_once()
    service.project_batch.assert_awaited_once_with(["uid-1", "uid-2"])
    execute_args = conn.execute.await_args.args
    assert execute_args[1] == ["uid-1", "uid-2"]
    assert execute_args[2] == "warm_leads"


@pytest.mark.asyncio
async def test_project_by_sync_status_fetches_ids_and_projects_batch():
    service, postgresql, _, conn = _build_service()
    conn.fetch.return_value = [{"id": "uid-1"}, {"id": "uid-2"}]
    expected = BatchProjectionResult(
        total=2,
        success=2,
        failed=0,
        skipped=0,
        results=[
            ProjectionResult(uid="uid-1", status=ProjectionStatus.SUCCESS),
            ProjectionResult(uid="uid-2", status=ProjectionStatus.SUCCESS),
        ],
    )
    service.project_batch = AsyncMock(return_value=expected)

    result = await service.project_by_sync_status(sync_status="enriched", limit=25)

    assert result == expected
    postgresql.ensure_connected.assert_awaited_once()
    fetch_args = conn.fetch.await_args.args
    assert fetch_args[1:] == ("enriched", 25)
    service.project_batch.assert_awaited_once_with(["uid-1", "uid-2"])


@pytest.mark.asyncio
async def test_get_projection_metrics_collects_counts_lag_and_pending():
    service, postgresql, _, conn = _build_service()
    conn.fetch.return_value = [
        {"projection_status": "success", "count": 3},
        {"projection_status": "failed", "count": 1},
    ]
    conn.fetchrow.side_effect = [
        {"avg_lag_seconds": 12.5, "max_lag_seconds": 30.0},
        {"count": 7},
    ]

    metrics = await service.get_projection_metrics()

    assert metrics == {
        "projection_counts": {"success": 3, "failed": 1},
        "avg_lag_seconds": 12.5,
        "max_lag_seconds": 30.0,
        "pending_projection": 7,
    }
    postgresql.ensure_connected.assert_awaited_once()
