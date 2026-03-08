#!/usr/bin/env python3
"""
Unit tests for webhook gateway security features.

Tests cover:
- HMAC signature verification
- Svix signature verification (Resend)
- Replay protection (timestamp validation)
- Rate limiting (memory and Redis)
- IP allowlisting
- Webhook endpoint security
- Request ID tracing
"""

import hashlib
import hmac
import json
import os
import sys
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set up mock environment variables BEFORE any imports
os.environ["TEAMLEADER_WEBHOOK_SECRET"] = "test-teamleader-secret"
os.environ["BREVO_WEBHOOK_SECRET"] = "test-brevo-secret"
os.environ["RESEND_WEBHOOK_SECRET"] = "test-resend-secret"
os.environ["EVENTHUB_CONNECTION_STRING"] = "test-connection-string"
os.environ["WEBHOOK_RATE_LIMIT_REQUESTS"] = "5"
os.environ["WEBHOOK_RATE_LIMIT_WINDOW"] = "60"
os.environ["REPLAY_PROTECTION_WINDOW"] = "300"  # 5 minutes


# Mock azure.eventhub before importing the gateway
azure_mock = MagicMock()
sys.modules["azure"] = azure_mock
sys.modules["azure.eventhub"] = azure_mock.eventhub = MagicMock()
sys.modules["azure.eventhub.EventHubProducerClient"] = (
    azure_mock.eventhub.EventHubProducerClient
) = MagicMock()
sys.modules["azure.eventhub.EventData"] = azure_mock.eventhub.EventData = MagicMock()


class TestSignatureVerification:
    """Tests for HMAC signature verification."""

    def test_verify_signature_valid(self):
        """Test signature verification with valid signature."""
        from scripts.webhook_gateway import verify_signature

        payload = b'{"test": "data"}'
        secret = "test-secret"
        expected_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        assert verify_signature(payload, expected_sig, secret) is True

    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature."""
        from scripts.webhook_gateway import verify_signature

        payload = b'{"test": "data"}'
        secret = "test-secret"
        invalid_sig = "invalid-signature"

        assert verify_signature(payload, invalid_sig, secret) is False

    def test_verify_signature_missing_secret(self):
        """Test signature verification with missing secret."""
        from scripts.webhook_gateway import verify_signature

        payload = b'{"test": "data"}'
        signature = "some-signature"

        assert verify_signature(payload, signature, "") is False

    def test_verify_signature_missing_signature(self):
        """Test signature verification with missing signature."""
        from scripts.webhook_gateway import verify_signature

        payload = b'{"test": "data"}'
        secret = "test-secret"

        assert verify_signature(payload, None, secret) is False

    def test_verify_signature_timing_safe(self):
        """Test that signature verification is timing-safe."""
        from scripts.webhook_gateway import verify_signature

        payload = b'{"test": "data"}'
        secret = "test-secret"
        wrong_sig = "a" * 64  # Same length, wrong content

        # Should not raise, just return False
        result = verify_signature(payload, wrong_sig, secret)
        assert result is False


class TestResendSvixSignature:
    """Tests for Resend Svix signature verification."""

    def test_verify_resend_svix_valid(self):
        """Test Resend Svix signature verification with valid signature."""
        from scripts.webhook_gateway import verify_resend_svix_signature

        payload = b'{"type": "email.opened", "data": {"to": "test@example.com"}}'
        secret = "test-resend-secret"
        timestamp = str(int(time.time()))

        # Compute expected signature: HMACSHA256(secret, timestamp + "." + payload)
        signed_payload = f"{timestamp}.".encode() + payload
        signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()

        svix_header = f"v1,{timestamp},{signature}"

        is_valid, error = verify_resend_svix_signature(payload, svix_header, secret, "test-req")
        assert is_valid is True
        assert error == ""

    def test_verify_resend_svix_invalid_signature(self):
        """Test Resend Svix signature verification with invalid signature."""
        from scripts.webhook_gateway import verify_resend_svix_signature

        payload = b'{"type": "email.opened"}'
        secret = "test-resend-secret"
        timestamp = str(int(time.time()))

        svix_header = f"v1,{timestamp},invalid-signature"

        is_valid, error = verify_resend_svix_signature(payload, svix_header, secret, "test-req")
        assert is_valid is False
        assert error == "signature_mismatch"

    def test_verify_resend_svix_expired_timestamp(self):
        """Test Resend Svix signature with expired timestamp."""
        from scripts.webhook_gateway import verify_resend_svix_signature

        payload = b'{"type": "email.opened"}'
        secret = "test-resend-secret"
        # Timestamp from 10 minutes ago
        timestamp = str(int(time.time()) - 600)

        svix_header = f"v1,{timestamp},some-signature"

        is_valid, error = verify_resend_svix_signature(payload, svix_header, secret, "test-req")
        assert is_valid is False
        assert error == "timestamp_outside_replay_window"

    def test_verify_resend_svix_invalid_format(self):
        """Test Resend Svix signature with invalid format."""
        from scripts.webhook_gateway import verify_resend_svix_signature

        payload = b'{"type": "email.opened"}'
        secret = "test-resend-secret"

        # Missing parts
        is_valid, error = verify_resend_svix_signature(payload, "v1,timestamp", secret, "test-req")
        assert is_valid is False
        assert error == "invalid_svix_format"

        # Wrong version
        is_valid, error = verify_resend_svix_signature(
            payload, "v2,timestamp,sig", secret, "test-req"
        )
        assert is_valid is False
        assert error == "invalid_svix_format"

    def test_verify_resend_svix_missing_params(self):
        """Test Resend Svix signature with missing secret or header."""
        from scripts.webhook_gateway import verify_resend_svix_signature

        payload = b'{"type": "email.opened"}'

        is_valid, error = verify_resend_svix_signature(payload, "header", "", "test-req")
        assert is_valid is False
        assert error == "missing_secret_or_signature"

        is_valid, error = verify_resend_svix_signature(payload, None, "secret", "test-req")
        assert is_valid is False
        assert error == "missing_secret_or_signature"


class TestReplayProtection:
    """Tests for replay protection (timestamp validation)."""

    def test_verify_timestamp_valid(self):
        """Test timestamp verification with valid recent timestamp."""
        from scripts.webhook_gateway import verify_timestamp

        # Current timestamp
        timestamp = datetime.now(UTC).isoformat()

        is_valid, error = verify_timestamp(timestamp, "test-req")
        assert is_valid is True
        assert error == ""

    def test_verify_timestamp_unix_format(self):
        """Test timestamp verification with Unix timestamp."""
        from scripts.webhook_gateway import verify_timestamp

        timestamp = str(int(time.time()))

        is_valid, error = verify_timestamp(timestamp, "test-req")
        assert is_valid is True
        assert error == ""

    def test_verify_timestamp_expired(self):
        """Test timestamp verification with expired timestamp."""
        from scripts.webhook_gateway import verify_timestamp

        # Timestamp from 10 minutes ago
        old_time = datetime.now(UTC).timestamp() - 600
        timestamp = str(int(old_time))

        is_valid, error = verify_timestamp(timestamp, "test-req")
        assert is_valid is False
        assert "request_too_old" in error

    def test_verify_timestamp_future(self):
        """Test timestamp verification with future timestamp."""
        from scripts.webhook_gateway import verify_timestamp

        # Timestamp 10 minutes in the future
        future_time = datetime.now(UTC).timestamp() + 600
        timestamp = str(int(future_time))

        is_valid, error = verify_timestamp(timestamp, "test-req")
        assert is_valid is False
        assert "request_too_old" in error

    def test_verify_timestamp_empty(self):
        """Test timestamp verification with empty timestamp (should pass)."""
        from scripts.webhook_gateway import verify_timestamp

        is_valid, error = verify_timestamp(None, "test-req")
        assert is_valid is True
        assert error == ""

    def test_verify_timestamp_invalid(self):
        """Test timestamp verification with invalid format."""
        from scripts.webhook_gateway import verify_timestamp

        is_valid, error = verify_timestamp("not-a-timestamp", "test-req")
        assert is_valid is False
        assert error == "invalid_timestamp_format"


class TestNonceReuse:
    """Tests for nonce-based replay protection."""

    def test_check_nonce_new(self):
        """Test that new nonces are accepted."""
        from scripts.webhook_gateway import check_nonce_reuse

        nonce = "test-nonce-123"
        result = check_nonce_reuse(nonce, "test-req")
        assert result is True

    def test_check_nonce_reuse(self):
        """Test that reused nonces are rejected."""
        from scripts.webhook_gateway import check_nonce_reuse

        nonce = "test-nonce-456"
        # First use
        assert check_nonce_reuse(nonce, "test-req") is True
        # Second use should fail
        assert check_nonce_reuse(nonce, "test-req-2") is False

    def test_check_nonce_empty(self):
        """Test that empty nonces pass through."""
        from scripts.webhook_gateway import check_nonce_reuse

        result = check_nonce_reuse("", "test-req")
        assert result is True


class TestIPAllowlist:
    """Tests for IP allowlist functionality."""

    @pytest.fixture(autouse=True)
    def clear_allowlist_env(self):
        """Clear allowlist environment variable before tests."""
        with patch("scripts.webhook_gateway.WEBHOOK_IP_ALLOWLIST", ""):
            yield

    def test_is_ip_allowed_no_allowlist(self):
        """Test that all IPs are allowed when no allowlist is configured."""
        from scripts.webhook_gateway import is_ip_allowed

        assert is_ip_allowed("192.168.1.1") is True
        assert is_ip_allowed("10.0.0.1") is True
        assert is_ip_allowed("1.2.3.4") is True

    def test_is_ip_allowed_single_ip(self):
        """Test allowlist with single IP."""
        from scripts.webhook_gateway import is_ip_allowed

        with patch("scripts.webhook_gateway.WEBHOOK_IP_ALLOWLIST", "192.168.1.1"):
            assert is_ip_allowed("192.168.1.1") is True
            assert is_ip_allowed("192.168.1.2") is False

    def test_is_ip_allowed_cidr(self):
        """Test allowlist with CIDR range."""
        from scripts.webhook_gateway import is_ip_allowed

        with patch("scripts.webhook_gateway.WEBHOOK_IP_ALLOWLIST", "192.168.0.0/24"):
            assert is_ip_allowed("192.168.0.1") is True
            assert is_ip_allowed("192.168.0.255") is True
            assert is_ip_allowed("192.168.1.1") is False

    def test_is_ip_allowed_multiple_ranges(self):
        """Test allowlist with multiple IP ranges."""
        from scripts.webhook_gateway import is_ip_allowed

        with patch(
            "scripts.webhook_gateway.WEBHOOK_IP_ALLOWLIST", "192.168.1.0/24,10.0.0.0/8,172.16.0.1"
        ):
            assert is_ip_allowed("192.168.1.100") is True
            assert is_ip_allowed("10.1.2.3") is True
            assert is_ip_allowed("172.16.0.1") is True
            assert is_ip_allowed("1.2.3.4") is False

    def test_is_ip_allowed_ipv6(self):
        """Test allowlist with IPv6 addresses."""
        from scripts.webhook_gateway import is_ip_allowed

        with patch("scripts.webhook_gateway.WEBHOOK_IP_ALLOWLIST", "2001:db8::/32"):
            assert is_ip_allowed("2001:db8::1") is True
            assert is_ip_allowed("192.168.1.1") is False


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    @pytest.fixture(autouse=True)
    def clear_rate_limit_store(self):
        """Clear rate limit store before each test."""
        from scripts.webhook_gateway import _rate_limit_store

        _rate_limit_store.clear()
        yield
        _rate_limit_store.clear()

    def test_is_rate_limited_under_limit(self):
        """Test rate limiter allows requests under the limit."""
        from scripts.webhook_gateway import RATE_LIMIT_REQUESTS, is_rate_limited

        # Make requests under the limit
        limit = min(5, RATE_LIMIT_REQUESTS)
        for i in range(limit):
            assert is_rate_limited(f"client-{i}", f"req-{i}") is False

    def test_is_rate_limited_over_limit(self):
        """Test rate limiter blocks requests over the limit."""
        from scripts.webhook_gateway import _rate_limit_store, is_rate_limited

        # Use a fresh client ID
        client_id = "test-client-over-limit"
        _rate_limit_store[client_id] = []

        # Make many requests to exceed limit
        for i in range(100):
            is_rate_limited(client_id, f"req-{i}")

        # Should be rate limited now
        assert is_rate_limited(client_id, "req-final") is True

    def test_is_rate_limited_different_clients(self):
        """Test rate limiting is per-client."""
        from scripts.webhook_gateway import _rate_limit_store, is_rate_limited

        _rate_limit_store.clear()

        # Fill up client-1's quota
        for i in range(1000):
            is_rate_limited("client-rate-1", f"req-{i}")

        # client-rate-1 should be rate limited
        assert is_rate_limited("client-rate-1", "req-final") is True

        # client-rate-2 should still have full quota (at least first request allowed)
        assert is_rate_limited("client-rate-2", "req-1") is False


@pytest.fixture
def client():
    """Create test client for webhook gateway."""
    from fastapi.testclient import TestClient

    # Import after env vars are set
    from scripts.webhook_gateway import _rate_limit_store, app

    # Clear rate limit store
    _rate_limit_store.clear()

    with TestClient(app) as test_client:
        yield test_client

    _rate_limit_store.clear()


class TestTeamleaderWebhook:
    """Tests for Teamleader webhook endpoint."""

    def test_teamleader_valid_signature(self, client):
        """Test Teamleader webhook with valid signature."""
        payload = {"event_type": "company.created", "company_id": "12345"}
        body = json.dumps(payload).encode()

        # Generate valid signature
        secret = "test-teamleader-secret"
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

        with patch("scripts.webhook_gateway.send_to_eventhub"):
            response = client.post(
                "/webhook/teamleader", content=body, headers={"X-Teamleader-Signature": signature}
            )

        assert response.status_code == 200
        assert response.json()["status"] == "received"
        assert "request_id" in response.json()

    def test_teamleader_invalid_signature(self, client):
        """Test Teamleader webhook with invalid signature."""
        payload = {"event_type": "company.created", "company_id": "12345"}
        body = json.dumps(payload).encode()

        response = client.post(
            "/webhook/teamleader",
            content=body,
            headers={"X-Teamleader-Signature": "invalid-signature"},
        )

        assert response.status_code == 401

    def test_teamleader_missing_signature(self, client):
        """Test Teamleader webhook without signature."""
        payload = {"event_type": "company.created", "company_id": "12345"}
        body = json.dumps(payload).encode()

        response = client.post("/webhook/teamleader", content=body)

        # Should fail because secret is configured but no signature provided
        assert response.status_code == 401

    def test_teamleader_invalid_json(self, client):
        """Test Teamleader webhook with invalid JSON."""
        body = b"not-valid-json"

        # Need to bypass signature check for this test
        with patch("scripts.webhook_gateway.TEAMLEADER_WEBHOOK_SECRET", ""):
            response = client.post("/webhook/teamleader", content=body)

        assert response.status_code == 400

    def test_teamleader_replay_protection_expired(self, client):
        """Test Teamleader webhook with expired timestamp."""
        payload = {"event_type": "company.created", "company_id": "12345"}
        body = json.dumps(payload).encode()

        # Timestamp from 10 minutes ago
        old_timestamp = str(int(time.time()) - 600)

        response = client.post(
            "/webhook/teamleader",
            content=body,
            headers={
                "X-Teamleader-Timestamp": old_timestamp,
                "X-Teamleader-Signature": "dummy-sig",
            },
        )

        assert response.status_code == 401
        assert (
            "expired" in response.json()["detail"].lower()
            or response.json()["detail"] == "Request expired"
        )

    def test_teamleader_ip_allowlist_blocked(self, client):
        """Test Teamleader webhook with IP allowlist blocking."""
        payload = {"event_type": "company.created", "company_id": "12345"}
        body = json.dumps(payload).encode()

        with patch("scripts.webhook_gateway.WEBHOOK_IP_ALLOWLIST", "10.0.0.0/8"):
            # Client IP is not in 10.0.0.0/8, so should be blocked
            response = client.post(
                "/webhook/teamleader",
                content=body,
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

            assert response.status_code == 403


class TestBrevoWebhook:
    """Tests for Brevo webhook endpoint."""

    def test_brevo_valid_signature(self, client):
        """Test Brevo webhook with valid signature."""
        payload = {"event": "delivered", "email": "test@example.com"}
        body = json.dumps(payload).encode()

        # Generate valid signature
        secret = "test-brevo-secret"
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

        with patch("scripts.webhook_gateway.send_to_eventhub"):
            response = client.post(
                "/webhook/brevo", content=body, headers={"X-Brevo-Signature": signature}
            )

        assert response.status_code == 200
        assert response.json()["status"] == "received"
        assert "request_id" in response.json()

    def test_brevo_invalid_signature(self, client):
        """Test Brevo webhook with invalid signature."""
        payload = {"event": "delivered", "email": "test@example.com"}
        body = json.dumps(payload).encode()

        response = client.post(
            "/webhook/brevo", content=body, headers={"X-Brevo-Signature": "invalid-signature"}
        )

        assert response.status_code == 401

    def test_brevo_replay_protection(self, client):
        """Test Brevo webhook replay protection."""
        payload = {"event": "delivered", "email": "test@example.com"}
        body = json.dumps(payload).encode()

        old_timestamp = str(int(time.time()) - 600)

        response = client.post(
            "/webhook/brevo",
            content=body,
            headers={"X-Brevo-Timestamp": old_timestamp},
        )

        assert response.status_code == 401


class TestResendWebhook:
    """Tests for Resend webhook endpoint with Svix signatures."""

    def test_build_tracardi_forward_payload_uses_anonymous_profile_id(self):
        """The Tracardi payload should use opaque IDs and sanitized properties."""
        from scripts.webhook_gateway import build_tracardi_forward_payload

        event = {
            "source": "resend",
            "event_type": "email.clicked",
            "uid": "opaque-uid-123",
            "payload": {
                "email_id": "email-123",
                "recipient_hash": "abc123",
                "recipient_domain": "example.com",
                "sender_domain": "resend.dev",
                "subject_hash": "deadbeef",
                "click_domain": "resend.com",
            },
        }

        payload = build_tracardi_forward_payload(event)

        assert payload["profile"]["id"] == "opaque-uid-123"
        assert payload["profile"]["traits"] == {"recipient_domain": "example.com"}
        properties = payload["events"][0]["properties"]
        assert properties["recipient_hash"] == "abc123"
        assert "to" not in properties
        assert "from" not in properties
        assert "subject" not in properties

    def test_resend_valid_svix_signature(self, client):
        """Test Resend webhook with valid Svix signature."""
        payload = {
            "type": "email.opened",
            "created_at": "2024-01-01T00:00:00.000Z",
            "data": {"email_id": "test-id", "to": "test@example.com"},
        }
        body = json.dumps(payload).encode()

        # Generate valid Svix signature
        secret = "test-resend-secret"
        timestamp = str(int(time.time()))
        signed_payload = f"{timestamp}.".encode() + body
        signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        svix_header = f"v1,{timestamp},{signature}"

        with patch("scripts.webhook_gateway.send_to_eventhub"):
            with patch("scripts.webhook_gateway.forward_to_tracardi"):
                response = client.post(
                    "/webhook/resend", content=body, headers={"X-Resend-Signature": svix_header}
                )

        assert response.status_code == 200
        assert response.json()["status"] == "received"
        assert "request_id" in response.json()

    def test_resend_webhook_sanitizes_payload_before_forwarding(self, client):
        """The projected event should not retain raw email or subject fields."""
        payload = {
            "type": "email.clicked",
            "created_at": "2024-01-01T00:00:00.000Z",
            "data": {
                "email_id": "test-id",
                "to": "target@example.com",
                "from": "sender@resend.dev",
                "subject": "Sensitive Subject",
                "click": {"url": "https://resend.com/docs"},
                "user_agent": "pytest",
            },
        }
        body = json.dumps(payload).encode()

        secret = "test-resend-secret"
        timestamp = str(int(time.time()))
        signed_payload = f"{timestamp}.".encode() + body
        signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        svix_header = f"v1,{timestamp},{signature}"

        with (
            patch("scripts.webhook_gateway.send_to_eventhub") as send_to_eventhub,
            patch("scripts.webhook_gateway.forward_to_tracardi", new=AsyncMock()) as forward_to_tracardi,
        ):
            response = client.post(
                "/webhook/resend", content=body, headers={"X-Resend-Signature": svix_header}
            )

        assert response.status_code == 200
        event = send_to_eventhub.call_args.args[0]
        assert event["uid"] != "target@example.com"
        assert event["payload"]["recipient_domain"] == "example.com"
        assert event["payload"]["sender_domain"] == "resend.dev"
        assert event["payload"]["click_domain"] == "resend.com"
        assert "to" not in event["payload"]
        assert "from" not in event["payload"]
        assert "subject" not in event["payload"]
        forward_to_tracardi.assert_awaited_once()

    def test_resend_invalid_svix_signature(self, client):
        """Test Resend webhook with invalid Svix signature."""
        payload = {
            "type": "email.opened",
            "created_at": "2024-01-01T00:00:00.000Z",
            "data": {"email_id": "test-id", "to": "test@example.com"},
        }
        body = json.dumps(payload).encode()

        svix_header = "v1,1234567890,invalid-signature"

        response = client.post(
            "/webhook/resend", content=body, headers={"X-Resend-Signature": svix_header}
        )

        assert response.status_code == 401

    def test_resend_expired_timestamp(self, client):
        """Test Resend webhook with expired timestamp in signature."""
        payload = {
            "type": "email.opened",
            "created_at": "2024-01-01T00:00:00.000Z",
            "data": {"email_id": "test-id", "to": "test@example.com"},
        }
        body = json.dumps(payload).encode()

        # Timestamp from 10 minutes ago
        old_timestamp = str(int(time.time()) - 600)
        svix_header = f"v1,{old_timestamp},dummy-signature"

        response = client.post(
            "/webhook/resend", content=body, headers={"X-Resend-Signature": svix_header}
        )

        assert response.status_code == 401
        assert (
            "timestamp" in response.json()["detail"].lower()
            or "expired" in response.json()["detail"].lower()
        )

    def test_resend_invalid_json(self, client):
        """Test Resend webhook with invalid JSON."""
        body = b"not-valid-json"

        # Need to bypass signature check for this test
        with patch("scripts.webhook_gateway.RESEND_WEBHOOK_SECRET", ""):
            response = client.post("/webhook/resend", content=body)

        assert response.status_code == 400


class TestWebsiteWebhook:
    """Tests for Website webhook endpoint with rate limiting."""

    def test_website_webhook_accepts_valid_request(self, client):
        """Test website webhook accepts valid requests."""
        with patch("scripts.webhook_gateway.send_to_eventhub"):
            response = client.post(
                "/webhook/website", json={"event_type": "page_view", "anonymous_id": "user-1"}
            )
            assert response.status_code == 200
            assert "request_id" in response.json()

    def test_website_invalid_json(self, client):
        """Test website webhook with invalid JSON."""
        response = client.post("/webhook/website", content=b"not-valid-json")

        assert response.status_code == 400

    def test_website_rate_limiting(self, client):
        """Test website webhook rate limiting."""
        # Make many requests to trigger rate limit
        with patch("scripts.webhook_gateway.send_to_eventhub"):
            # Use a consistent client IP
            headers = {"X-Forwarded-For": "1.2.3.4"}

            # Make requests to exceed rate limit
            for i in range(100):
                response = client.post(
                    "/webhook/website",
                    json={"event_type": "page_view", "anonymous_id": f"user-{i}"},
                    headers=headers,
                )

            # The last request should be rate limited
            # Note: The exact request count threshold depends on the rate limit settings
            # So we just verify that rate limiting is working at some point
            rate_limited_seen = False
            for i in range(100, 110):
                response = client.post(
                    "/webhook/website",
                    json={"event_type": "page_view", "anonymous_id": f"user-{i}"},
                    headers=headers,
                )
                if response.status_code == 429:
                    rate_limited_seen = True
                    break

            assert rate_limited_seen, "Rate limiting should have triggered"


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check returns correct structure."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "security" in data

        # Check security section
        security = data["security"]
        assert "teamleader_signature_verification" in security
        assert "brevo_signature_verification" in security
        assert "resend_signature_verification" in security
        assert "replay_protection" in security
        assert "rate_limiting" in security
        assert "ip_allowlist" in security

        # Rate limiting details
        rate_limiting = security["rate_limiting"]
        assert rate_limiting["enabled"] is True
        assert "requests_per_window" in rate_limiting
        assert "window_seconds" in rate_limiting
        assert "backend" in rate_limiting

        # Replay protection details
        replay_protection = security["replay_protection"]
        assert replay_protection["enabled"] is True
        assert "window_seconds" in replay_protection

        # IP allowlist details
        ip_allowlist = security["ip_allowlist"]
        assert "enabled" in ip_allowlist
        assert "rules_count" in ip_allowlist


class TestEventHubIntegration:
    """Tests for Event Hub integration."""

    def test_send_to_eventhub_success(self):
        """Test successful Event Hub send."""
        from scripts.webhook_gateway import send_to_eventhub

        event = {"test": "event", "timestamp": "2024-01-01T00:00:00Z"}

        with patch("scripts.webhook_gateway.get_producer") as mock_get_producer:
            mock_producer = MagicMock()
            mock_batch = MagicMock()
            mock_producer.create_batch.return_value = mock_batch
            mock_get_producer.return_value = mock_producer

            # Should not raise
            send_to_eventhub(event)

            mock_producer.create_batch.assert_called_once()
            mock_batch.add.assert_called_once()
            mock_producer.send_batch.assert_called_once()

    def test_send_to_eventhub_failure(self):
        """Test Event Hub send failure handling."""
        from fastapi import HTTPException

        from scripts.webhook_gateway import send_to_eventhub

        event = {"test": "event"}

        with patch("scripts.webhook_gateway.get_producer") as mock_get_producer:
            mock_get_producer.side_effect = Exception("Connection failed")

            with pytest.raises(HTTPException) as exc_info:
                send_to_eventhub(event)

            assert exc_info.value.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
