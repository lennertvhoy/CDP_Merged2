import asyncio
import json
import sys
from types import SimpleNamespace

from scripts import enrich_companies_batch, enrich_companies_chunked


def test_build_where_clause_uses_canonical_website_column():
    clause = enrich_companies_batch.build_where_clause(["website"])

    assert "website_url" in clause
    assert "enrichment_data" not in clause


def test_build_where_clause_combines_requested_enrichers():
    clause = enrich_companies_batch.build_where_clause(["cbe", "geocoding"])

    assert "industry_nace_code" in clause
    assert "geo_latitude" in clause
    assert " OR " in clause


def test_build_where_clause_requires_usable_nace_input_for_cbe():
    clause = enrich_companies_batch.build_where_clause(["cbe"])

    assert "nace_description" in clause
    assert "company_size IS NULL" in clause
    assert "employee_count IS NULL" in clause
    assert "jsonb_typeof(enrichment_data->'all_nace_codes')" in clause
    assert "jsonb_array_length(enrichment_data->'all_nace_codes') > 0" in clause
    assert "COALESCE(industry_nace_code, '') = ''" not in clause


def test_build_company_query_uses_cursor_before_limit():
    query, params = enrich_companies_batch.build_company_query(
        ["cbe"],
        limit=1000,
        start_after_id="00000000-0000-0000-0000-000000000123",
    )

    assert "AND id > $1" in query
    assert "LIMIT $2" in query
    assert params == ["00000000-0000-0000-0000-000000000123", 1000]


def test_process_company_reuses_shared_geocoding_enricher(monkeypatch):
    sentinel = object()

    async def fake_enrich_geocoding(company, enricher=None):
        assert enricher is sentinel
        return {"geo_latitude": 1.23}

    monkeypatch.setattr(enrich_companies_batch, "enrich_geocoding", fake_enrich_geocoding)

    company_id, updates = asyncio.run(
        enrich_companies_batch.process_company(
            {"id": "company-1"},
            ["geocoding"],
            enricher_instances={"geocoding": sentinel},
        )
    )

    assert company_id == "company-1"
    assert updates == {"geo_latitude": 1.23}


def test_run_chunk_passes_start_after_id(monkeypatch):
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, capture_output, text, env):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(enrich_companies_chunked.subprocess, "run", fake_run)

    enrich_companies_chunked.run_chunk(limit=1000, start_after_id="cursor-123")

    assert "--start-after-id" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--start-after-id") + 1] == "cursor-123"


def test_run_chunk_passes_enrichers_and_batch_size(monkeypatch):
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, capture_output, text, env):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(enrich_companies_chunked.subprocess, "run", fake_run)

    enrich_companies_chunked.run_chunk(
        limit=1000,
        enrichers="geocoding,website",
        batch_size=123,
    )

    assert captured["cmd"][captured["cmd"].index("--enrichers") + 1] == "geocoding,website"
    assert captured["cmd"][captured["cmd"].index("--batch-size") + 1] == "123"


def test_run_chunk_preserves_environment(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(cmd, capture_output, text, env):
        captured["env"] = env
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(enrich_companies_chunked.subprocess, "run", fake_run)
    monkeypatch.setenv("TEST_RUN_CHUNK_ENV", "present")
    monkeypatch.setenv("PYTHONPATH", "/tmp/original-pythonpath")

    enrich_companies_chunked.run_chunk(limit=10, enrichers="website")

    env = captured["env"]
    assert isinstance(env, dict)
    assert env["TEST_RUN_CHUNK_ENV"] == "present"
    assert env["PYTHONPATH"].startswith(str(enrich_companies_chunked.Path.cwd()))
    assert env["PYTHONPATH"].endswith("/tmp/original-pythonpath")


def test_parse_stats_extracts_last_company_id():
    stats = enrich_companies_chunked.parse_stats(
        "Total processed: 1,000\nLast company ID: abc-123\n"
    )

    assert stats["processed"] == 1000
    assert stats["last_company_id"] == "abc-123"


def test_parse_stats_handles_timestamp_prefixed_lines():
    stats = enrich_companies_chunked.parse_stats(
        "\n".join(
            [
                "2026-03-06 12:54:56 [info     ] Total processed: 2,000",
                "2026-03-06 12:54:56 [info     ] Enriched: 1,255",
                "2026-03-06 12:54:56 [info     ] Skipped: 745",
                "2026-03-06 12:54:56 [info     ] Failed: 0",
                "2026-03-06 12:54:56 [info     ] Last company ID: 0047e408-7a21-4603-8685-1cd1c54f140a",
            ]
        )
    )

    assert stats == {
        "processed": 2000,
        "enriched": 1255,
        "skipped": 745,
        "failed": 0,
        "last_company_id": "0047e408-7a21-4603-8685-1cd1c54f140a",
    }


def test_cursor_file_round_trip(tmp_path):
    cursor_file = tmp_path / "cursor.json"

    enrich_companies_chunked.save_cursor(cursor_file, "abc-123", completed=False)

    assert enrich_companies_chunked.load_cursor(cursor_file) == "abc-123"


def test_chunked_main_returns_non_zero_when_chunk_fails(monkeypatch, tmp_path):
    cursor_file = tmp_path / "cursor.json"

    monkeypatch.setattr(
        enrich_companies_chunked,
        "run_chunk",
        lambda *args, **kwargs: {"returncode": 1, "stdout": "", "stderr": "boom"},
    )
    monkeypatch.setattr(
        enrich_companies_chunked.sys,
        "argv",
        [
            "enrich_companies_chunked.py",
            "--enrichers",
            "website",
            "--chunk-size",
            "1000",
            "--cursor-file",
            str(cursor_file),
        ],
    )

    assert enrich_companies_chunked.main() == 1

    payload = json.loads(cursor_file.read_text())

    assert payload["start_after_id"] is None
    assert payload["completed"] is False
    assert payload["updated_at"]


def test_run_enrichment_counts_task_exceptions_without_crashing(monkeypatch):
    class FakeConnection:
        async def fetch(self, query, *params):
            return [{"id": "company-1"}]

        async def execute(self, query, *params):
            return "UPDATE 1"

        async def close(self):
            return None

    async def fake_connect(conn_url):
        return FakeConnection()

    async def fake_process_company(company, enrichers, enricher_instances=None):
        raise RuntimeError("boom")

    monkeypatch.setenv("DATABASE_URL", "postgresql://example.test/cdp")
    monkeypatch.setitem(sys.modules, "asyncpg", SimpleNamespace(connect=fake_connect))
    monkeypatch.setattr(enrich_companies_batch, "process_company", fake_process_company)
    monkeypatch.setattr(enrich_companies_batch, "create_enricher_instances", lambda enrichers: {})

    stats = asyncio.run(
        enrich_companies_batch.run_enrichment(
            limit=1,
            enrichers=["website"],
            batch_size=1,
        )
    )

    assert stats.processed == 1
    assert stats.errors == 1
    assert stats.enriched == 0
