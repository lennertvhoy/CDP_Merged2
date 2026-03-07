"""Unit tests for ResendClient (all external calls mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import ResendError
from src.services.resend import ResendClient


class TestResendClientInitialization:
    def test_init_with_api_key_from_settings(self):
        """Test that client initializes with API key from settings."""
        with patch("src.services.resend.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "test-api-key"
            mock_settings.RESEND_FROM_EMAIL = "test@example.com"

            client = ResendClient()
            assert client.api_key == "test-api-key"
            assert client.from_email == "test@example.com"
            assert client.headers["Authorization"] == "Bearer test-api-key"

    def test_init_with_explicit_api_key(self):
        """Test that explicit API key overrides settings."""
        with patch("src.services.resend.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "settings-key"
            mock_settings.RESEND_FROM_EMAIL = "default@example.com"

            client = ResendClient(api_key="explicit-key")
            assert client.api_key == "explicit-key"
            assert client.headers["Authorization"] == "Bearer explicit-key"


class TestSendEmail:
    @pytest.mark.asyncio
    async def test_send_email_success(self):
        """Test successful single email send."""
        with patch("src.services.resend.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "test-key"
            mock_settings.RESEND_FROM_EMAIL = "from@example.com"

            client = ResendClient()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "msg_123", "to": "recipient@example.com"}
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_http

                result = await client.send_email(
                    to="recipient@example.com",
                    subject="Test Subject",
                    html="<p>Test</p>",
                )

        assert result["id"] == "msg_123"

    @pytest.mark.asyncio
    async def test_send_email_with_custom_from(self):
        """Test email send with custom from address."""
        with patch("src.services.resend.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "test-key"
            mock_settings.RESEND_FROM_EMAIL = "default@example.com"

            client = ResendClient()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "msg_124"}
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_http

                await client.send_email(
                    to="recipient@example.com",
                    subject="Test",
                    html="<p>Test</p>",
                    from_email="custom@example.com",
                )

                # Verify the correct from address was used
                call_args = mock_http.post.call_args
                assert call_args[1]["json"]["from"] == "custom@example.com"


class TestSendBulkEmails:
    @pytest.mark.asyncio
    async def test_send_bulk_emails_success(self):
        """Test successful bulk email send."""
        with patch("src.services.resend.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "test-key"
            mock_settings.RESEND_FROM_EMAIL = "from@example.com"

            client = ResendClient()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [
                    {"id": "msg_001", "to": "user1@example.com"},
                    {"id": "msg_002", "to": "user2@example.com"},
                ]
            }
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_http

                recipients = ["user1@example.com", "user2@example.com"]
                result = await client.send_bulk_emails(
                    recipients=recipients,
                    subject="Bulk Test",
                    html="<p>Bulk</p>",
                )

        assert len(result["data"]) == 2


class TestDomains:
    @pytest.mark.asyncio
    async def test_get_domains_success(self):
        """Test listing domains."""
        with patch("src.services.resend.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "test-key"
            mock_settings.RESEND_FROM_EMAIL = "from@example.com"

            client = ResendClient()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [
                    {"id": "domain_001", "name": "example.com", "status": "verified"},
                    {"id": "domain_002", "name": "test.com", "status": "pending"},
                ]
            }
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_http

                domains = await client.get_domains()

        assert len(domains) == 2
        assert domains[0]["name"] == "example.com"


class TestAudiences:
    @pytest.mark.asyncio
    async def test_get_audiences_success(self):
        """Test listing audiences."""
        with patch("src.services.resend.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "test-key"
            mock_settings.RESEND_FROM_EMAIL = "from@example.com"

            client = ResendClient()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [
                    {"id": "aud_001", "name": "Newsletter"},
                    {"id": "aud_002", "name": "Customers"},
                ]
            }
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_http

                audiences = await client.get_audiences()

        assert len(audiences) == 2
        assert audiences[0]["name"] == "Newsletter"

    @pytest.mark.asyncio
    async def test_create_audience_success(self):
        """Test creating an audience."""
        with patch("src.services.resend.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "test-key"
            mock_settings.RESEND_FROM_EMAIL = "from@example.com"

            client = ResendClient()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "aud_new", "name": "Test Audience"}
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_http

                result = await client.create_audience(name="Test Audience")

        assert result["id"] == "aud_new"
        assert result["name"] == "Test Audience"

    @pytest.mark.asyncio
    async def test_add_contact_to_audience_success(self):
        """Test adding contact to audience."""
        with patch("src.services.resend.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "test-key"
            mock_settings.RESEND_FROM_EMAIL = "from@example.com"

            client = ResendClient()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "contact_001",
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
            }
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_http

                result = await client.add_contact_to_audience(
                    email="user@example.com",
                    audience_id="aud_001",
                    first_name="John",
                    last_name="Doe",
                )

        assert result["id"] == "contact_001"
        assert result["email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_send_audience_email_success(self):
        """Test sending campaign to audience."""
        with patch("src.services.resend.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "test-key"
            mock_settings.RESEND_FROM_EMAIL = "from@example.com"

            client = ResendClient()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "campaign_001"}
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_http

                result = await client.send_audience_email(
                    audience_id="aud_001",
                    subject="Newsletter",
                    html="<p>Hello!</p>",
                )

        assert result["id"] == "campaign_001"


class TestResendErrorHandling:
    @pytest.mark.asyncio
    async def test_send_email_429_rate_limit(self):
        """Test that 429 errors raise ResendError."""

        with patch("src.services.resend.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "test-key"
            mock_settings.RESEND_FROM_EMAIL = "from@example.com"

            client = ResendClient()

            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.json.return_value = {"message": "Rate limit exceeded"}
            mock_response.raise_for_status = MagicMock(side_effect=Exception("Rate limit"))

            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_http

                # The actual exception handling is in the client
                # Mock the response to trigger the error path
                mock_response.raise_for_status.side_effect = None
                from httpx import HTTPStatusError
                from httpx import Request as HttpRequest

                mock_response.raise_for_status = MagicMock(
                    side_effect=HTTPStatusError(
                        "Rate limit",
                        request=HttpRequest("POST", "https://api.resend.com/emails"),
                        response=mock_response,
                    )
                )

                with pytest.raises(ResendError):
                    await client.send_email(
                        to="test@example.com",
                        subject="Test",
                        html="<p>Test</p>",
                    )

    @pytest.mark.asyncio
    async def test_empty_api_key_handling(self):
        """Test behavior with empty API key."""
        with patch("src.services.resend.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = ""
            mock_settings.RESEND_FROM_EMAIL = "from@example.com"

            client = ResendClient()
            assert client.api_key == ""
            assert client.headers["Authorization"] == "Bearer "
