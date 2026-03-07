"""Tests for local analysis artifact generation."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai_interface.tools.artifact import create_data_artifact


@pytest.mark.asyncio
async def test_create_data_artifact_writes_markdown_search_report(tmp_path, monkeypatch):
    mock_service = MagicMock()
    mock_service.search_companies = AsyncMock(
        return_value={
            "total": 42,
            "result": [
                {
                    "kbo_number": "0123456789",
                    "company_name": "Example BV",
                    "city": "Gent",
                    "postal_code": "9000",
                    "status": "AC",
                    "industry_nace_code": "62010",
                    "legal_form": "BV",
                    "main_email": "info@example.be",
                    "main_phone": "+3291234567",
                    "website_url": "https://example.be",
                }
            ],
        }
    )
    monkeypatch.setattr("src.ai_interface.tools.artifact.get_search_service", lambda: mock_service)
    monkeypatch.setattr("src.ai_interface.tools.artifact.ARTIFACT_ROOT", tmp_path)

    result = json.loads(
        await create_data_artifact.ainvoke(
            {
                "title": "Gent Report",
                "artifact_type": "search_results",
                "output_format": "markdown",
                "city": "Gent",
                "max_rows": 10,
            }
        )
    )

    assert result["status"] == "ok"
    artifact_path = tmp_path / result["artifact_relative_path"].split("/")[-1]
    assert artifact_path.exists()
    content = artifact_path.read_text(encoding="utf-8")
    assert "# Gent Report" in content
    assert "Example BV" in content
    assert result["authoritative_total"] == 42


@pytest.mark.asyncio
async def test_create_data_artifact_writes_csv_coverage_report(tmp_path, monkeypatch):
    mock_service = MagicMock()
    mock_service.get_coverage_stats = AsyncMock(
        return_value={
            "status": "ok",
            "total_companies": 100,
            "coverage": {
                "email": {"count": 15, "percent": 15.0},
                "website": {"count": 9, "percent": 9.0},
            },
            "backend": "postgresql",
        }
    )
    monkeypatch.setattr("src.ai_interface.tools.artifact.get_search_service", lambda: mock_service)
    monkeypatch.setattr("src.ai_interface.tools.artifact.ARTIFACT_ROOT", tmp_path)

    result = json.loads(
        await create_data_artifact.ainvoke(
            {
                "title": "Coverage Snapshot",
                "artifact_type": "coverage_report",
                "output_format": "csv",
            }
        )
    )

    assert result["status"] == "ok"
    artifact_path = tmp_path / result["artifact_relative_path"].split("/")[-1]
    assert artifact_path.exists()
    content = artifact_path.read_text(encoding="utf-8")
    assert "field,count,percent" in content
    assert "email,15,15.0" in content
    assert result["spreadsheet_compatible"] is True
