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
        "total_count": 2,
        "rows": [
            {
                "company_name": "Acme BV",
                "main_email": "info@acme.be",
                "city": "Brussels",
                "postal_code": "1000",
                "status": "AC",
                "industry_nace_code": "62010",
                "legal_form": "BV",
                "website_url": "https://acme.be",
            },
            {
                "company_name": "Bravo NV",
                "main_email": "hello@bravo.be",
                "city": "Brussels",
                "postal_code": "1000",
                "status": "AC",
                "industry_nace_code": "62020",
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
    tracardi_cls.assert_not_called()
    files = list((tmp_path / "cdp_exports").glob("Brussels Software_*.csv"))
    assert files
    content = files[0].read_text()
    assert "Acme BV" in content
    assert "hello@bravo.be" in content


@pytest.mark.asyncio
async def test_push_segment_to_resend_prefers_canonical_segment_rows():
    canonical_service = AsyncMock()
    canonical_service.get_segment_members.return_value = {
        "segment_id": "seg-1",
        "segment_key": "brussels-software",
        "segment_name": "Brussels Software",
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
        result = await push_segment_to_resend.coroutine("Brussels Software")

    assert "Pushed 1/2 contacts" in result
    tracardi_cls.assert_not_called()
    resend.create_audience.assert_awaited_once()
    resend.add_contact_to_audience.assert_awaited_once_with(
        email="info@acme.be",
        audience_id="aud-1",
        first_name="Acme",
        last_name="BV",
    )
