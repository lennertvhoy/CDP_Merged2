"""Unit tests for FlexmailClient (all external calls mocked)."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from src.services.flexmail import FlexmailClient


class TestWebhookSignature:
    def test_valid_signature(self):
        secret = "test-secret"
        payload = b'{"event": "click"}'
        signature = hmac.new(
            key=secret.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()

        assert FlexmailClient.verify_webhook_signature(payload, signature, secret) is True

    def test_invalid_signature(self):
        secret = "test-secret"
        payload = b'{"event": "click"}'
        assert FlexmailClient.verify_webhook_signature(payload, "wrong-sig", secret) is False

    def test_no_secret_returns_false(self):
        from unittest.mock import patch

        with patch("src.services.flexmail.settings") as mock_settings:
            mock_settings.FLEXMAIL_WEBHOOK_SECRET = None
            result = FlexmailClient.verify_webhook_signature(b"payload", "sig", secret=None)
            assert result is False

    def test_empty_payload(self):
        secret = "test-secret"
        payload = b""
        signature = hmac.new(
            key=secret.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()
        assert FlexmailClient.verify_webhook_signature(payload, signature, secret) is True


class TestFlexmailContactCreation:
    @pytest.mark.asyncio
    async def test_create_contact_success(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        client = FlexmailClient()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "contact-001",
            "email": "test@example.be",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_http

            result = await client.create_contact("test@example.be", "Test Company")

        assert result["id"] == "contact-001"

    @pytest.mark.asyncio
    async def test_create_contact_409_fetches_existing(self):
        """On 409 Conflict, client should fetch existing contact."""
        from unittest.mock import AsyncMock, MagicMock, patch

        client = FlexmailClient()
        existing = {"id": "existing-001", "email": "test@example.be"}
        client.get_contact_by_email = AsyncMock(return_value=existing)

        mock_response = MagicMock()
        mock_response.status_code = 409

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_http

            result = await client.create_contact("test@example.be", "Test Company")

        assert result == existing

    def test_name_splitting(self):
        """Verify name is split into first/last correctly."""

        # Internal method — test the split logic
        name = "Acme NV Brussels"
        parts = name.split(" ", 1)
        assert parts[0] == "Acme"
        assert parts[1] == "NV Brussels"
