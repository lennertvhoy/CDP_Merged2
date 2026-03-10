import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import HTTPStatusError, RequestError

from src.ai_interface.tools.email import (
    push_segment_to_resend,
    push_to_flexmail,
    send_bulk_emails_via_resend,
    send_campaign_via_resend,
    send_email_via_resend,
)


@pytest.fixture
def mock_tracardi(monkeypatch):
    mock = AsyncMock()
    # Mocking Tracardi Client response
    mock.search_profiles.return_value = {
        "result": [
            {"id": "p1", "traits": {"email": "test1@test.com", "name": "John Doe"}},
            {"id": "p2", "traits": {"email": "test2@test.com", "name": "Jane Doe"}},
            {"id": "no_email", "traits": {"name": "No Email"}},
        ]
    }
    monkeypatch.setattr("src.ai_interface.tools.email.TracardiClient", lambda: mock)
    return mock


@pytest.fixture
def mock_flexmail(monkeypatch):
    mock = AsyncMock()
    mock.get_custom_fields.return_value = [{"id": "cf1", "label": "tracardi_segment"}]
    mock.get_interests.return_value = [{"id": "int1", "name": "Tracardi"}]
    mock.create_contact.return_value = {"id": "c1"}
    monkeypatch.setattr("src.ai_interface.tools.email.FlexmailClient", lambda: mock)
    return mock


@pytest.fixture
def mock_resend(monkeypatch):
    mock = AsyncMock()
    mock.send_email.return_value = {"id": "msg_123"}
    mock.send_bulk_emails.return_value = {"data": [{"id": "msg_1"}, {"id": "msg_2"}]}
    mock.create_audience.return_value = {"id": "aud_1"}
    mock.send_audience_email.return_value = {"id": "msg_456"}
    monkeypatch.setattr("src.ai_interface.tools.email.ResendClient", lambda: mock)
    return mock


@pytest.mark.asyncio
async def test_push_to_flexmail(mock_tracardi, mock_flexmail):
    res = await push_to_flexmail.coroutine("seg1")
    assert "Pushed 2 profiles" in res
    assert mock_flexmail.create_contact.call_count == 2
    assert mock_flexmail.update_contact.call_count == 2
    assert mock_flexmail.add_contact_to_interest.call_count == 2


@pytest.mark.asyncio
async def test_push_to_flexmail_no_custom_fields(mock_tracardi, mock_flexmail):
    mock_flexmail.get_custom_fields.return_value = []
    mock_flexmail.get_interests.return_value = []
    res = await push_to_flexmail.coroutine("seg1")
    assert "Pushed 2 profiles" in res
    assert mock_flexmail.create_contact.call_count == 2
    assert mock_flexmail.update_contact.call_count == 0
    assert mock_flexmail.add_contact_to_interest.call_count == 0


@pytest.mark.asyncio
async def test_send_email_via_resend(mock_resend):
    res = await send_email_via_resend.coroutine("test@test.com", "Subj", "<p>Hi</p>")
    assert "Message ID: msg_123" in res


@pytest.mark.asyncio
async def test_send_email_via_resend_http_error(mock_resend):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resend.send_email.side_effect = HTTPStatusError(
        "err", request=MagicMock(), response=mock_resp
    )
    res = await send_email_via_resend.coroutine("test@test.com", "Subj", "<p>Hi</p>")
    assert "Failed to send email via Resend: HTTP 400" in res


@pytest.mark.asyncio
async def test_send_email_via_resend_request_error(mock_resend):
    mock_resend.send_email.side_effect = RequestError("conn failed", request=MagicMock())
    res = await send_email_via_resend.coroutine("test@test.com", "Subj", "<p>Hi</p>")
    assert "Request error" in res


@pytest.mark.asyncio
async def test_send_bulk_emails_via_resend(mock_resend):
    res = await send_bulk_emails_via_resend.coroutine(["a@a.com", "b@b.com"], "Subj", "<p>Hi</p>")
    assert "Bulk email sent to 2 recipients" in res


@pytest.mark.asyncio
async def test_send_bulk_emails_via_resend_http_error(mock_resend):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resend.send_bulk_emails.side_effect = HTTPStatusError(
        "err", request=MagicMock(), response=mock_resp
    )
    res = await send_bulk_emails_via_resend.coroutine(["a@a.com", "b@b.com"], "Subj", "<p>Hi</p>")
    assert "Failed to send bulk emails via Resend: HTTP 400" in res


@pytest.mark.asyncio
async def test_send_bulk_emails_via_resend_req_error(mock_resend):
    mock_resend.send_bulk_emails.side_effect = RequestError("conn failed", request=MagicMock())
    res = await send_bulk_emails_via_resend.coroutine(["a@a.com", "b@b.com"], "Subj", "<p>Hi</p>")
    assert "Failed to send bulk emails via Resend: Request error" in res


@pytest.mark.asyncio
async def test_send_bulk_emails_empty(mock_resend):
    res = await send_bulk_emails_via_resend.coroutine([], "Subj", "<p>Hi</p>")
    assert "No recipients provided" in res


@pytest.mark.asyncio
async def test_push_segment_to_resend(mock_tracardi, mock_resend):
    res = await push_segment_to_resend.coroutine("seg1")
    result = json.loads(res)
    assert result["status"] == "ok"
    assert result["segment_id"] == "seg1"
    assert result["counts"]["added_to_resend"] == 2
    assert mock_resend.create_audience.call_count == 1
    assert mock_resend.add_contact_to_audience.call_count == 2


@pytest.mark.asyncio
async def test_push_segment_to_resend_empty_segment(mock_tracardi, mock_resend):
    mock_tracardi.search_profiles.return_value = {"result": []}
    res = await push_segment_to_resend.coroutine("seg_empty")
    result = json.loads(res)
    assert result["status"] == "error"
    assert "empty" in result["error"].lower()


@pytest.mark.asyncio
async def test_push_segment_to_resend_no_audience(mock_tracardi, mock_resend):
    mock_resend.create_audience.return_value = {}
    res = await push_segment_to_resend.coroutine("seg1")
    assert "Failed to create Resend audience" in res


@pytest.mark.asyncio
async def test_push_segment_to_resend_http_error_on_add(mock_tracardi, mock_resend):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resend.add_contact_to_audience.side_effect = HTTPStatusError(
        "err", request=MagicMock(), response=mock_resp
    )
    res = await push_segment_to_resend.coroutine("seg1")
    result = json.loads(res)
    assert result["status"] == "ok"
    assert result["counts"]["added_to_resend"] == 0


@pytest.mark.asyncio
async def test_push_segment_to_resend_req_error_on_add(mock_tracardi, mock_resend):
    mock_resend.add_contact_to_audience.side_effect = RequestError("err", request=MagicMock())
    res = await push_segment_to_resend.coroutine("seg1")
    result = json.loads(res)
    assert result["status"] == "ok"
    assert result["counts"]["added_to_resend"] == 0


@pytest.mark.asyncio
async def test_push_segment_to_resend_exception(mock_tracardi, mock_resend):
    mock_resend.create_audience.side_effect = Exception("General Error")
    res = await push_segment_to_resend.coroutine("seg1")
    assert "Failed to push segment to Resend" in res


@pytest.mark.asyncio
async def test_send_campaign_via_resend(mock_resend):
    res = await send_campaign_via_resend.coroutine("aud_1", "Subj", "<p>Hi</p>")
    assert "Campaign sent successfully" in res
    assert "Message ID: msg_456" in res


@pytest.mark.asyncio
async def test_send_campaign_via_resend_http_error(mock_resend):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resend.send_audience_email.side_effect = HTTPStatusError(
        "err", request=MagicMock(), response=mock_resp
    )
    res = await send_campaign_via_resend.coroutine("aud_1", "Subj", "<p>Hi</p>")
    assert "Failed to send campaign via Resend: HTTP 400" in res


@pytest.mark.asyncio
async def test_send_campaign_via_resend_req_error(mock_resend):
    mock_resend.send_audience_email.side_effect = RequestError("conn failed", request=MagicMock())
    res = await send_campaign_via_resend.coroutine("aud_1", "Subj", "<p>Hi</p>")
    assert "Request error" in res
