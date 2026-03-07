from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.enrichment.postgresql_pipeline import PostgreSQLEnrichmentPipeline


def _build_pipeline():
    pipeline = object.__new__(PostgreSQLEnrichmentPipeline)
    pipeline.db = None
    pipeline.connection_url = None
    pipeline._auto_project_profiles = AsyncMock()
    return pipeline


class _FakeStats:
    def to_dict(self):
        return {"calls": 1}


class _FakeEnricher:
    def __init__(self) -> None:
        self.stats = _FakeStats()
        self.estimated_cost_usd = 0
        self.started = False
        self.finished = False

    def start(self) -> None:
        self.started = True

    def finish(self) -> None:
        self.finished = True

    def can_enrich(self, profile) -> bool:
        return True

    async def enrich_batch(self, profiles):
        return profiles


class _FakeProgress:
    def __init__(self, progress_dir: Path) -> None:
        self.progress_dir = progress_dir
        self.started: list[tuple[str, str, int]] = []
        self.completed: list[tuple[str, str | None]] = []
        self.incremented: list[tuple[str, bool]] = []

    def start_job(self, job_id: str, enricher_name: str, total: int) -> None:
        self.started.append((job_id, enricher_name, total))

    def complete_job(self, job_id: str, error_message: str | None = None) -> None:
        self.completed.append((job_id, error_message))

    def increment_progress(self, job_id: str, success: bool = True) -> None:
        self.incremented.append((job_id, success))


class _FakeCosts:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def record_cost(self, **kwargs) -> None:
        self.records.append(kwargs)

    def get_summary(self) -> dict:
        return {"records": len(self.records)}


def test_profile_to_dict_maps_database_fields_for_enrichers():
    pipeline = _build_pipeline()
    profile = {
        "id": "company-1",
        "kbo_number": "0123456789",
        "vat_number": "BE0123456789",
        "company_name": "Acme BV",
        "legal_form": "BV",
        "street_address": "Main Street 1",
        "city": "Gent",
        "postal_code": "9000",
        "country": "BE",
        "geo_latitude": 51.05,
        "geo_longitude": 3.72,
        "industry_nace_code": "62010",
        "nace_description": "Software",
        "company_size": "small",
        "employee_count": 12,
        "annual_revenue": "1M-5M",
        "founded_date": "2020-01-02",
        "website_url": "https://example.com",
        "main_phone": "+3200000000",
        "main_email": "info@example.com",
        "ai_description": "Description",
    }

    converted = pipeline._profile_to_dict(profile)

    assert converted["name"] == "Acme BV"
    assert converted["address"]["street"] == "Main Street 1"
    assert converted["geo"] == {"latitude": 51.05, "longitude": 3.72}
    assert converted["industry"] == {"nace_code": "62010", "description": "Software"}
    assert converted["_db_fields"] is profile


def test_extract_updates_maps_enrichment_fields_and_sync_metadata():
    pipeline = _build_pipeline()
    enriched_profile = {
        "website": "https://example.com",
        "phone": "+3200000000",
        "email": "sales@example.com",
        "geo": {"latitude": 51.05, "longitude": 3.72},
        "ai_description": "Great company",
        "industry": {"nace_code": "62010", "description": "Software"},
        "employee_count": 42,
        "annual_revenue": "1M-5M",
        "company_size": "medium",
        "main_email": "info@example.com",
    }

    updates = pipeline._extract_updates(enriched_profile)

    assert updates["website_url"] == "https://example.com"
    assert updates["main_phone"] == "+3200000000"
    assert updates["main_email"] == "info@example.com"
    assert updates["geo_latitude"] == 51.05
    assert updates["geo_longitude"] == 3.72
    assert updates["industry_nace_code"] == "62010"
    assert updates["nace_description"] == "Software"
    assert updates["employee_count"] == 42
    assert updates["annual_revenue"] == "1M-5M"
    assert updates["company_size"] == "medium"
    assert updates["sync_status"] == "enriched"
    assert isinstance(updates["last_sync_at"], datetime)
    assert updates["last_sync_at"].tzinfo is None
    assert isinstance(updates["ai_description_generated_at"], datetime)


@pytest.mark.asyncio
async def test_fetch_profiles_uses_search_query_when_present():
    pipeline = _build_pipeline()
    pipeline.db = MagicMock()
    pipeline.db.search_profiles = AsyncMock(
        return_value={
            "result": [{"id": "company-1", "company_name": "Acme BV", "geo_latitude": None}]
        }
    )
    pipeline.db.get_profiles = AsyncMock()

    profiles = await pipeline.fetch_profiles(query="acme", limit=25, offset=10)

    pipeline.db.search_profiles.assert_awaited_once_with("acme", limit=25, offset=10)
    pipeline.db.get_profiles.assert_not_called()
    assert profiles[0]["name"] == "Acme BV"
    assert profiles[0]["geo"] is None


@pytest.mark.asyncio
async def test_update_profiles_updates_database_and_triggers_projection():
    pipeline = _build_pipeline()
    pipeline.db = MagicMock()
    pipeline.db.update_profiles_batch = AsyncMock(return_value={"success": 2, "failed": 1})

    result = await pipeline.update_profiles(
        [
            {"id": "company-1", "website": "https://example.com"},
            {"id": "company-2", "phone": "+3200000000"},
            {"website": "missing-id"},
        ]
    )

    assert result == {"success": True, "updated": 2, "failed": 1}
    pipeline.db.update_profiles_batch.assert_awaited_once()
    updates = pipeline.db.update_profiles_batch.await_args.args[0]
    assert [profile_id for profile_id, _ in updates] == ["company-1", "company-2"]
    pipeline._auto_project_profiles.assert_awaited_once_with(updates)


@pytest.mark.asyncio
async def test_update_profiles_returns_error_when_batch_write_fails():
    pipeline = _build_pipeline()
    pipeline.db = MagicMock()
    pipeline.db.update_profiles_batch = AsyncMock(side_effect=RuntimeError("db down"))

    result = await pipeline.update_profiles(
        [{"id": "company-1", "website": "https://example.com"}]
    )

    assert result == {"success": False, "error": "db down"}
    pipeline._auto_project_profiles.assert_not_awaited()


@pytest.mark.asyncio
async def test_auto_project_profiles_batches_and_closes_projection_service(monkeypatch):
    pipeline = _build_pipeline()
    pipeline.db = MagicMock()
    captured = {}

    class FakeProjectionService:
        def __init__(self, postgresql_client):
            captured["postgresql_client"] = postgresql_client
            self.initialize = AsyncMock()
            self.close = AsyncMock()
            self.project_batch = AsyncMock(
                side_effect=[
                    SimpleNamespace(success=10, failed=0),
                    SimpleNamespace(success=2, failed=1),
                ]
            )
            captured["instance"] = self

    monkeypatch.setattr(
        "src.enrichment.postgresql_pipeline.ProjectionService",
        FakeProjectionService,
    )

    updates = [(f"company-{index}", {"sync_status": "enriched"}) for index in range(12)]

    await PostgreSQLEnrichmentPipeline._auto_project_profiles(pipeline, updates)

    service = captured["instance"]
    assert captured["postgresql_client"] is pipeline.db
    service.initialize.assert_awaited_once()
    assert service.project_batch.await_count == 2
    assert service.project_batch.await_args_list[0].args == (
        [f"company-{index}" for index in range(10)],
    )
    assert service.project_batch.await_args_list[1].args == (["company-10", "company-11"],)
    service.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_phase_streaming_returns_no_matches_without_fetching_rows(tmp_path):
    pipeline = object.__new__(PostgreSQLEnrichmentPipeline)
    pipeline.batch_size = 5
    pipeline.progress = _FakeProgress(tmp_path)
    pipeline.costs = _FakeCosts()
    pipeline.enrichers = {"contact_validation": _FakeEnricher()}
    db = MagicMock()
    db.get_profile_count = AsyncMock(return_value=0)
    db.get_profiles = AsyncMock()
    pipeline._get_db_client = AsyncMock(return_value=db)

    result = await pipeline.run_phase_streaming(
        phase_name="phase1_contact_validation",
        enricher_name="contact_validation",
        limit=10,
        dry_run=True,
    )

    assert result["completed"] is True
    assert result["status"] == "completed"
    assert result["exit_reason"] == "no_matches"
    assert result["total_profiles"] == 0
    assert len(pipeline.progress.started) == 1
    started_job_id, started_enricher, started_total = pipeline.progress.started[0]
    assert started_job_id.startswith("phase1_contact_validation_")
    assert (started_enricher, started_total) == ("contact_validation", 0)
    assert pipeline.progress.completed == [(started_job_id, None)]
    db.get_profiles.assert_not_awaited()
    assert pipeline.enrichers["contact_validation"].started is True
    assert pipeline.enrichers["contact_validation"].finished is True


@pytest.mark.asyncio
async def test_run_from_postgresql_stops_when_overall_limit_is_reached():
    pipeline = object.__new__(PostgreSQLEnrichmentPipeline)
    pipeline.costs = _FakeCosts()
    pipeline.run_phase_streaming = AsyncMock(
        return_value={
            "phase": "phase1_contact_validation",
            "total_profiles": 2,
            "completed": True,
            "status": "completed",
            "exit_reason": "limit_reached",
        }
    )

    result = await pipeline.run_from_postgresql(
        limit=2,
        phases=["contact_validation", "cbe_integration"],
        dry_run=True,
    )

    assert result["completed"] is True
    assert result["status"] == "completed"
    assert result["exit_reason"] == "overall_limit_reached"
    assert result["phases_run"] == 1
    assert result["total_processed_overall"] == 2
    pipeline.run_phase_streaming.assert_awaited_once()
