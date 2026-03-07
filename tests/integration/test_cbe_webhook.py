"""
Integration tests for CBE Webhook Listener.

Tests the FastAPI webhook endpoint for receiving company change events.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Import after path setup
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "infra" / "cbe_webhook"))

from main import app


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_returns_200(self, client):
        """Health check should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "cbe-webhook"
        assert "timestamp" in data


class TestWebhookEndpoint:
    """Tests for CBE webhook endpoint."""

    def test_valid_payload_returns_200(self, client):
        """Valid payload should be accepted."""
        payload = {
            "company_number": "0200225413",
            "change_type": "update",
            "timestamp": "2026-03-03T23:00:00Z",
        }
        response = client.post("/webhook/cbe", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["company_number"] == "0200225413"
        assert "received_at" in data

    def test_9_digit_company_number_normalized(self, client):
        """9-digit company number should be padded to 10 digits."""
        payload = {
            "company_number": "200225413",
            "change_type": "create",
            "timestamp": "2026-03-03T23:00:00Z",
        }
        response = client.post("/webhook/cbe", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["company_number"] == "0200225413"

    def test_missing_company_number_returns_422(self, client):
        """Missing company_number should return 422 (FastAPI validation error)."""
        payload = {"change_type": "update", "timestamp": "2026-03-03T23:00:00Z"}
        response = client.post("/webhook/cbe", json=payload)
        assert response.status_code == 422

    def test_missing_change_type_returns_422(self, client):
        """Missing change_type should return 422 (FastAPI validation error)."""
        payload = {"company_number": "0200225413", "timestamp": "2026-03-03T23:00:00Z"}
        response = client.post("/webhook/cbe", json=payload)
        assert response.status_code == 422

    def test_invalid_change_type_returns_422(self, client):
        """Invalid change_type should return 422 (FastAPI validation error)."""
        payload = {
            "company_number": "0200225413",
            "change_type": "invalid_type",
            "timestamp": "2026-03-03T23:00:00Z",
        }
        response = client.post("/webhook/cbe", json=payload)
        assert response.status_code == 422

    def test_invalid_company_number_returns_422(self, client):
        """Invalid company number should return 422 (FastAPI validation error)."""
        payload = {
            "company_number": "123",  # Too short
            "change_type": "update",
            "timestamp": "2026-03-03T23:00:00Z",
        }
        response = client.post("/webhook/cbe", json=payload)
        assert response.status_code == 422

    def test_invalid_timestamp_returns_422(self, client):
        """Invalid timestamp should return 422 (FastAPI validation error)."""
        payload = {
            "company_number": "0200225413",
            "change_type": "update",
            "timestamp": "not-a-timestamp",
        }
        response = client.post("/webhook/cbe", json=payload)
        assert response.status_code == 422

    def test_create_change_type_accepted(self, client):
        """Create change type should be accepted."""
        payload = {
            "company_number": "0200225413",
            "change_type": "create",
            "timestamp": "2026-03-03T23:00:00Z",
        }
        response = client.post("/webhook/cbe", json=payload)
        assert response.status_code == 200

    def test_delete_change_type_accepted(self, client):
        """Delete change type should be accepted."""
        payload = {
            "company_number": "0200225413",
            "change_type": "delete",
            "timestamp": "2026-03-03T23:00:00Z",
        }
        response = client.post("/webhook/cbe", json=payload)
        assert response.status_code == 200
