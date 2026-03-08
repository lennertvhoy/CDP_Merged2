import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_interface.tools.email import push_segment_to_resend
from src.ai_interface.tools.export import export_segment_to_csv


@pytest.mark.asyncio
async def test_export_segment_to_csv_prefers_canonical_segment_rows(tmp_path):
    canonical_service = AsyncMock()
    canonical_service.get_segment_members.return_value = {
        "segment_id": "seg-1",
        "segment_key": "brussels-software",
        "segment_name": "Brussels Software",
        "definition_json": {"filters": {"city": "Brussels", "nace_codes": ["62100", "62200"]}},
        "total_count": 2,
        "rows": [
            {
                "company_name": "Acme BV",
                "kbo_number": "0123456789",
                "main_email": "info@acme.be",
                "city": "Brussels",
                "postal_code": "1000",
                "status": "AC",
                "industry_nace_code": "62100",
                "all_nace_codes": ["62100"],
                "legal_form": "BV",
                "website_url": "https://acme.be",
            },
            {
                "company_name": "Bravo NV",
                "kbo_number": "0123456790",
                "main_email": "hello@bravo.be",
                "city": "Brussels",
                "postal_code": "1000",
                "status": "AC",
                "industry_nace_code": "62200",
                "all_nace_codes": ["62200"],
                "legal_form": "NV",
                "website_url": "https://bravo.be",
            },
        ],
    }

    with (
        patch("src.ai_interface.tools.export.CanonicalSegmentService", return_value=canonical_service),
        patch("src.ai_interface.tools.export.TracardiClient") as tracardi_cls,
        patch("tempfile.gettempdir", return_value=str(tmp_path)),
    ):
        result = json.loads(await export_segment_to_csv.ainvoke({"segment_id": "Brussels Software"}))

    assert result["status"] == "ok"
    assert result["backend"] == "postgresql"
    assert result["validation"]["validated"] is True
    assert result["validation"]["invalid_rows"] == 0
    tracardi_cls.assert_not_called()
    files = list((tmp_path / "cdp_exports").glob("Brussels Software_*.csv"))
    assert files
    content = files[0].read_text()
    assert "Acme BV" in content
    assert "hello@bravo.be" in content


@pytest.mark.asyncio
async def test_export_segment_to_csv_aborts_when_canonical_rows_drift(tmp_path):
    canonical_service = AsyncMock()
    canonical_service.get_segment_members.return_value = {
        "segment_id": "seg-1",
        "segment_key": "it-services-brussels",
        "segment_name": "IT services - Brussels",
        "definition_json": {"filters": {"city": "Brussels", "nace_codes": ["62100", "62200"]}},
        "total_count": 1,
        "rows": [
            {
                "company_name": "Off-Segment Co",
                "kbo_number": "0123456799",
                "main_email": "info@offsegment.be",
                "city": "Brussels",
                "postal_code": "1000",
                "status": "AC",
                "industry_nace_code": "68203",
                "all_nace_codes": ["68203"],
            }
        ],
    }

    with (
        patch("src.ai_interface.tools.export.CanonicalSegmentService", return_value=canonical_service),
        patch("src.ai_interface.tools.export.TracardiClient") as tracardi_cls,
        patch("tempfile.gettempdir", return_value=str(tmp_path)),
    ):
        result = json.loads(await export_segment_to_csv.ainvoke({"segment_id": "IT services - Brussels"}))

    assert result["status"] == "error"
    assert result["backend"] == "postgresql"
    assert result["validation"]["invalid_rows"] == 1
    assert result["validation"]["sample_invalid_rows"][0]["failed_filters"] == ["nace_codes"]
    tracardi_cls.assert_not_called()
    files = list((tmp_path / "cdp_exports").glob("IT services - Brussels_*.csv"))
    assert files == []


@pytest.mark.asyncio
async def test_push_segment_to_resend_prefers_canonical_segment_rows():
    canonical_service = AsyncMock()
    canonical_service.get_segment_members.return_value = {
        "segment_id": "seg-1",
        "segment_key": "brussels-software",
        "segment_name": "Brussels Software",
        "definition_json": {},
        "total_count": 2,
        "rows": [
            {"company_name": "Acme BV", "main_email": "info@acme.be"},
            {"company_name": "No Email BV", "main_email": ""},
        ],
    }
    resend = AsyncMock()
    resend.create_audience.return_value = {"id": "aud-1"}

    with (
        patch("src.ai_interface.tools.email.CanonicalSegmentService", return_value=canonical_service),
        patch("src.ai_interface.tools.email.TracardiClient") as tracardi_cls,
        patch("src.ai_interface.tools.email.ResendClient", Mock(return_value=resend)),
    ):
        result = json.loads(await push_segment_to_resend.coroutine("Brussels Software"))

    assert result["status"] == "ok"
    assert result["counts"]["added_to_resend"] == 1
    assert result["counts"]["segment_total"] == 2
    tracardi_cls.assert_not_called()
    resend.create_audience.assert_awaited_once()
    resend.add_contact_to_audience.assert_awaited_once_with(
        email="info@acme.be",
        audience_id="aud-1",
        first_name="Acme",
        last_name="BV",
    )
