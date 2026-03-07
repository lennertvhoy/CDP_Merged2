from __future__ import annotations

import importlib
import json
import zipfile
from pathlib import Path

import pytest

import_kbo_full_enriched = importlib.import_module("scripts.import_kbo_full_enriched")
kbo_runtime = importlib.import_module("scripts.kbo_runtime")


def test_resolve_kbo_zip_path_prefers_environment_override(tmp_path: Path):
    configured_zip = tmp_path / "custom-kbo.zip"

    resolved = kbo_runtime.resolve_kbo_zip_path({"KBO_ZIP_PATH": str(configured_zip)})

    assert resolved == configured_zip


def test_stream_enterprises_honors_limits_and_resume_checkpoint(tmp_path: Path):
    zip_path = tmp_path / "kbo.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("code.csv", "Category,Code,Description\nJuridicalForm,014,BV\n")
        zf.writestr(
            "enterprise.csv",
            (
                "EnterpriseNumber,Status,JuridicalForm,StartDate\n"
                "0123456789,AC,014,01-01-2020\n"
                "1123456789,AC,014,02-01-2020\n"
                "2123456789,AC,014,03-01-2020\n"
            ),
        )

    extractor = import_kbo_full_enriched.KBODataExtractor(zip_path)

    first_two = list(extractor.stream_enterprises(start_line=0, max_lines=2))
    resumed = list(extractor.stream_enterprises(start_line=2, max_lines=2))

    assert [row["EnterpriseNumber"] for _, row in first_two] == [
        "0123456789",
        "1123456789",
    ]
    assert [line_number for line_number, _ in resumed] == [3]
    assert [row["EnterpriseNumber"] for _, row in resumed] == ["2123456789"]


@pytest.mark.asyncio
async def test_import_to_postgresql_writes_canonical_company_columns():
    captured: dict[str, object] = {}

    class FakeConnection:
        async def copy_records_to_table(self, table_name, *, records, columns):
            captured["table_name"] = table_name
            captured["records"] = records
            captured["columns"] = columns

    companies = [
        {
            "kbo_number": "0123456789",
            "company_name": "Acme BV",
            "street_address": "Main Street 1",
            "city": "Gent",
            "postal_code": "9000",
            "country": "BE",
            "industry_nace_code": "62010",
            "all_nace_codes": ["62010", "63110"],
            "nace_descriptions": ["Software development", "Data processing"],
            "legal_form": "Besloten vennootschap",
            "legal_form_code": "014",
            "founded_date": None,
            "status": "AC",
            "juridical_situation": "Normal",
            "type_of_enterprise": "LEGAL_PERSON",
            "main_email": "hello@example.com",
            "main_phone": "+32 9 123 45 67",
            "main_fax": "+32 9 765 43 21",
            "website_url": "https://example.com",
            "source_system": "KBO_FULL",
            "source_id": "0123.456.789",
            "sync_status": "pending",
            "all_names": ["Acme BV", "Acme Belgium"],
            "establishment_count": 3,
        }
    ]

    inserted, skipped = await import_kbo_full_enriched.import_to_postgresql(
        companies,
        FakeConnection(),
    )

    assert inserted == 1
    assert skipped == 0
    assert captured["table_name"] == "companies"

    row = dict(zip(captured["columns"], captured["records"][0], strict=True))

    assert row["status"] == "AC"
    assert row["juridical_situation"] == "Normal"
    assert row["type_of_enterprise"] == "LEGAL_PERSON"
    assert row["legal_form_code"] == "014"
    assert row["main_fax"] == "+32 9 765 43 21"
    assert row["all_names"] == ["Acme BV", "Acme Belgium"]
    assert row["all_nace_codes"] == ["62010", "63110"]
    assert row["nace_descriptions"] == ["Software development", "Data processing"]
    assert row["establishment_count"] == 3
    assert row["nace_code"] == "62010"
    assert row["nace_description"] == "Software development"

    enrichment_data = json.loads(row["enrichment_data"])
    assert enrichment_data["status"] == "AC"
    assert enrichment_data["main_fax"] == "+32 9 765 43 21"


@pytest.mark.asyncio
async def test_import_to_postgresql_fallback_insert_matches_column_count():
    execute_calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeConnection:
        async def copy_records_to_table(self, table_name, *, records, columns):
            raise RuntimeError("duplicate key")

        async def execute(self, query, *args):
            execute_calls.append((query, args))
            return "INSERT 0 1"

    companies = [
        {
            "kbo_number": "0123456789",
            "company_name": "Acme BV",
            "street_address": "Main Street 1",
            "city": "Gent",
            "postal_code": "9000",
            "country": "BE",
            "industry_nace_code": "62010",
            "all_nace_codes": ["62010"],
            "nace_descriptions": ["Software development"],
            "legal_form": "Besloten vennootschap",
            "legal_form_code": "014",
            "status": "AC",
            "juridical_situation": "Normal",
            "type_of_enterprise": "LEGAL_PERSON",
            "main_email": "hello@example.com",
            "main_phone": "+32 9 123 45 67",
            "main_fax": "+32 9 765 43 21",
            "website_url": "https://example.com",
            "source_system": "KBO_FULL",
            "source_id": "0123.456.789",
            "sync_status": "pending",
            "all_names": ["Acme BV"],
            "establishment_count": 1,
        }
    ]

    inserted, skipped = await import_kbo_full_enriched.import_to_postgresql(
        companies,
        FakeConnection(),
    )

    assert inserted == 1
    assert skipped == 0
    assert len(execute_calls) == 1
    _, args = execute_calls[0]
    assert len(args) == 27
