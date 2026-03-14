"""
Shared pytest fixtures for CDP_Merged test suite.
Provides mocked service clients, settings overrides, and sample data.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.search_engine.schema import ProfileSearchParams

# ─── Sample data ──────────────────────────────────────────────────────────────

SAMPLE_PROFILES: list[dict[str, Any]] = [
    {
        "id": "profile-001",
        "traits": {
            "name": "Acme NV",
            "city": "Gent",
            "status": "AC",
            "email": "info@acme.be",
            "phone": "+32 9 123 45 67",
            "nace_codes": "62010",
            "enterprise_number": "0207.446.759",
        },
    },
    {
        "id": "profile-002",
        "traits": {
            "name": "Tech BV",
            "city": "Brussel",
            "status": "AC",
            "email": "contact@tech.be",
            "nace_codes": "62020",
            "enterprise_number": "0542.123.456",
        },
    },
    {
        "id": "profile-003",
        "traits": {
            "name": "Old Corp SA",
            "city": "Gent",
            "status": "AC",
            "nace_codes": "62030",
        },
    },
]

MOCK_TRACARDI_SEARCH_RESPONSE: dict[str, Any] = {
    "total": len(SAMPLE_PROFILES),
    "result": SAMPLE_PROFILES,
}

MOCK_TRACARDI_PROFILE_RESPONSE: dict[str, Any] = {
    "id": "session-profile-001",
    "traits": {"name": "Session User"},
}

MOCK_FLEXMAIL_CONTACT: dict[str, Any] = {
    "id": "flexmail-contact-001",
    "email": "info@acme.be",
    "first_name": "Acme",
    "name": "NV",
    "language": "nl",
}

MOCK_FLEXMAIL_CUSTOM_FIELDS: list[dict[str, Any]] = [
    {"id": "field-001", "label": "tracardi_segment", "variable": "tracardi_segment"},
]

MOCK_FLEXMAIL_INTERESTS: list[dict[str, Any]] = [
    {"id": "interest-001", "name": "Tracardi"},
]


# ─── Settings fixture ─────────────────────────────────────────────────────────


@pytest.fixture
def test_settings() -> Settings:
    """Return Settings configured for testing (mock LLM, no external services)."""
    return Settings(
        LLM_PROVIDER="mock",
        LLM_MODEL="gpt-5",
        OPENAI_API_KEY="test-key",
        TRACARDI_API_URL="http://localhost:8686",
        TRACARDI_USERNAME="admin",
        TRACARDI_PASSWORD="admin",
        TRACARDI_SOURCE_ID="test-source",
        FLEXMAIL_ENABLED=False,
        FLEXMAIL_API_URL="http://localhost:8080/flexmail",
        FLEXMAIL_ACCOUNT_ID="test-account",
        FLEXMAIL_API_TOKEN="test-token",
        FLEXMAIL_WEBHOOK_SECRET="test-webhook-secret",
        LOG_LEVEL="WARNING",
        DEBUG=False,
    )


# ─── Tracardi mock ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_tracardi_client():
    """Mock TracardiClient with preset responses."""
    with patch("src.services.tracardi.TracardiClient") as mock_cls:
        instance = MagicMock()
        instance.search_profiles = AsyncMock(return_value=MOCK_TRACARDI_SEARCH_RESPONSE)
        instance.get_or_create_profile = AsyncMock(return_value=MOCK_TRACARDI_PROFILE_RESPONSE)
        instance.create_segment = AsyncMock(
            return_value={
                "id": "test-segment",
                "name": "test-segment",
                "profiles_added": 3,
            }
        )
        instance.add_profile_to_segment = AsyncMock(return_value=True)
        instance.delete_profile = AsyncMock(return_value=True)
        mock_cls.return_value = instance
        yield instance


@pytest.fixture
def mock_flexmail_client():
    """Mock FlexmailClient with preset responses."""
    with patch("src.services.flexmail.FlexmailClient") as mock_cls:
        instance = MagicMock()
        instance.get_custom_fields = AsyncMock(return_value=MOCK_FLEXMAIL_CUSTOM_FIELDS)
        instance.get_interests = AsyncMock(return_value=MOCK_FLEXMAIL_INTERESTS)
        instance.create_contact = AsyncMock(return_value=MOCK_FLEXMAIL_CONTACT)
        instance.update_contact = AsyncMock(return_value=True)
        instance.add_contact_to_interest = AsyncMock(return_value=True)
        instance.get_contact_by_email = AsyncMock(return_value=MOCK_FLEXMAIL_CONTACT)
        instance.get_contact_by_id = AsyncMock(return_value=MOCK_FLEXMAIL_CONTACT)
        mock_cls.return_value = instance
        yield instance


# ─── Basic search params ──────────────────────────────────────────────────────


@pytest.fixture
def city_params() -> ProfileSearchParams:
    """Minimal params with city and status."""
    return ProfileSearchParams(city="Gent", status="AC")


@pytest.fixture
def nace_params() -> ProfileSearchParams:
    """Params with NACE codes."""
    return ProfileSearchParams(nace_codes=["62010", "62020"])


@pytest.fixture
def full_params() -> ProfileSearchParams:
    """Params with many fields set."""
    return ProfileSearchParams(
        city="Gent",
        status="AC",
        nace_codes=["62010"],
        has_email=True,
        min_start_date="2020-01-01",
    )
