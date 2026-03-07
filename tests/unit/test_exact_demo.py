from __future__ import annotations

import pytest

from scripts import demo_exact_integration as exact_demo_module
from scripts.demo_exact_integration import ExactOnlineDemo


async def _no_sleep(_: float) -> None:
    return None


@pytest.mark.asyncio
async def test_exact_demo_sync_metadata_stays_mock_contract_shaped(monkeypatch) -> None:
    monkeypatch.setattr(exact_demo_module.asyncio, "sleep", _no_sleep)

    demo = ExactOnlineDemo()
    enrichment = await demo.sync_to_cdp()
    metadata = enrichment["metadata"]

    assert demo.provenance == "mock"
    assert demo.mode_description.startswith("MOCK")
    assert metadata["provenance"] == "mock"
    assert metadata["mock_scenario_id"] == "exact-mock-financial-happy-path"
    assert metadata["contract_version"] == "2026-03-04"
    assert metadata["source_modes"] == {"financials": "mock", "invoices": "mock"}
    assert metadata["invoice_count"] == 3
    assert metadata["company"]["source_record_url"].startswith("https://start.exactonline.be")


@pytest.mark.asyncio
async def test_exact_demo_main_reports_current_mock_constraints(monkeypatch, capsys) -> None:
    monkeypatch.setattr(exact_demo_module.asyncio, "sleep", _no_sleep)

    await exact_demo_module.main()
    output = capsys.readouterr().out

    assert (
        "Mode: MOCK (no Exact trial/demo tenant verified; Exact-shaped fixture data only)"
        in output
    )
    assert "Request or activate an Exact trial/demo tenant" in output
    assert "docs/DEMO_SOURCE_MOCK_CONTRACT.md" in output
    assert "src/services/exact_online.py" not in output
    assert "scripts/sync_exact_to_cdp.py" not in output
    assert "docs/integrations/exact_online.md" not in output
