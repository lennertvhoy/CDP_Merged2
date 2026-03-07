from __future__ import annotations

import importlib

import pytest

sync_kbo_to_tracardi = importlib.import_module("scripts.sync_kbo_to_tracardi")


def test_load_runtime_config_requires_credentials():
    with pytest.raises(RuntimeError, match="TRACARDI_USERNAME"):
        sync_kbo_to_tracardi.load_runtime_config({})

    with pytest.raises(RuntimeError, match="TRACARDI_PASSWORD"):
        sync_kbo_to_tracardi.load_runtime_config({"TRACARDI_USERNAME": "user@example.com"})


def test_load_runtime_config_supports_all_matching_mode(tmp_path):
    config = sync_kbo_to_tracardi.load_runtime_config(
        {
            "TRACARDI_USERNAME": "user@example.com",
            "TRACARDI_PASSWORD": "secret",
            "TRACARDI_TARGET_COUNT": "0",
            "TRACARDI_BATCH_SIZE": "25",
            "TRACARDI_VERIFY_ATTEMPTS": "3",
            "TRACARDI_VERIFY_DELAY_SECONDS": "0.5",
            "KBO_ZIP_PATH": str(tmp_path / "kbo.zip"),
        }
    )

    assert config.tracardi_username == "user@example.com"
    assert config.tracardi_password == "secret"
    assert config.target_count == 0
    assert config.batch_size == 25
    assert config.verify_attempts == 3
    assert config.verify_delay_seconds == 0.5
    assert config.kbo_zip_path == tmp_path / "kbo.zip"


def test_filter_poc_companies_returns_all_matches_when_target_count_is_zero():
    enterprises = {
        "1": {"status": "AC", "juridical_form": "BV"},
        "2": {"status": "AC", "juridical_form": "NV"},
        "3": {"status": "AC", "juridical_form": "VZW"},
        "4": {"status": "IN", "juridical_form": "BV"},
    }
    addresses = {
        "1": {"zipcode": "9000", "city": "Gent", "street": "A", "house_number": "1"},
        "2": {"zipcode": "9100", "city": "Sint-Niklaas", "street": "B", "house_number": "2"},
        "3": {"zipcode": "8500", "city": "Kortrijk", "street": "C", "house_number": "3"},
        "4": {"zipcode": "9000", "city": "Gent", "street": "D", "house_number": "4"},
    }
    activities = {
        "1": [{"nace_code": "62010", "classification": "MAIN"}],
        "2": [{"nace_code": "63110", "classification": "MAIN"}],
        "3": [{"nace_code": "47110", "classification": "MAIN"}],
        "4": [{"nace_code": "62020", "classification": "MAIN"}],
    }
    names = {
        "1": "Beta Systems",
        "2": "Alpha Cloud",
        "3": "Retail Corp",
        "4": "Inactive Tech",
    }

    companies = sync_kbo_to_tracardi.filter_poc_companies(
        enterprises,
        addresses,
        activities,
        names,
        target_count=0,
    )

    assert [company["company_name"] for company in companies] == [
        "Alpha Cloud",
        "Beta Systems",
    ]


def test_filter_poc_companies_applies_target_limit_after_sorting():
    enterprises = {
        "1": {"status": "AC", "juridical_form": "BV"},
        "2": {"status": "AC", "juridical_form": "NV"},
    }
    addresses = {
        "1": {"zipcode": "9000", "city": "Gent", "street": "A", "house_number": "1"},
        "2": {"zipcode": "9100", "city": "Sint-Niklaas", "street": "B", "house_number": "2"},
    }
    activities = {
        "1": [{"nace_code": "62010", "classification": "MAIN"}],
        "2": [{"nace_code": "63110", "classification": "MAIN"}],
    }
    names = {
        "1": "Zulu Tech",
        "2": "Alpha Cloud",
    }

    companies = sync_kbo_to_tracardi.filter_poc_companies(
        enterprises,
        addresses,
        activities,
        names,
        target_count=1,
    )

    assert len(companies) == 1
    assert companies[0]["company_name"] == "Alpha Cloud"


def test_transform_to_tracardi_sets_profile_time_fields_for_gui_queries():
    profile = sync_kbo_to_tracardi.transform_to_tracardi(
        {
            "kbo_number": "0123456789",
            "company_name": "Alpha Cloud",
            "street_address": "Example 1",
            "city": "Gent",
            "postal_code": "9000",
            "country": "BE",
            "province": "Oost-Vlaanderen",
            "legal_form": "BV",
            "nace_code": "62010",
            "status": "AC",
            "is_it_company": True,
        }
    )

    assert profile["id"] == "0123456789"
    assert profile["metadata"]["time"]["insert"]
    assert profile["metadata"]["time"]["create"]
    assert profile["metadata"]["time"]["update"]
    assert profile["metadata"]["time"]["create"] == profile["metadata"]["time"]["update"]


@pytest.mark.asyncio
async def test_get_tracardi_token_uses_form_auth_by_default():
    calls = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return FakeResponse(200, {"access_token": "token-from-form"})

    config = sync_kbo_to_tracardi.SyncConfig(
        tracardi_api_url="http://tracardi.test",
        tracardi_username="admin@admin.com",
        tracardi_password="secret",
        kbo_zip_path=sync_kbo_to_tracardi.DEFAULT_KBO_ZIP_PATH,
        batch_size=100,
        target_count=0,
        verify_attempts=1,
        verify_delay_seconds=0.1,
    )

    original_client = sync_kbo_to_tracardi.httpx.AsyncClient
    sync_kbo_to_tracardi.httpx.AsyncClient = lambda timeout: FakeClient()
    try:
        token = await sync_kbo_to_tracardi.get_tracardi_token(config)
    finally:
        sync_kbo_to_tracardi.httpx.AsyncClient = original_client

    assert token == "token-from-form"
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "http://tracardi.test/user/token"
    assert kwargs["data"] == {
        "username": "admin@admin.com",
        "password": "secret",
        "grant_type": "password",
        "scope": "",
    }
    assert kwargs["headers"]["Content-Type"] == "application/x-www-form-urlencoded"


@pytest.mark.asyncio
async def test_get_tracardi_token_falls_back_to_json_on_422():
    calls = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            if len(calls) == 1:
                return FakeResponse(422, {"detail": "invalid form"})
            return FakeResponse(200, {"access_token": "token-from-json"})

    config = sync_kbo_to_tracardi.SyncConfig(
        tracardi_api_url="http://tracardi.test",
        tracardi_username="admin@admin.com",
        tracardi_password="secret",
        kbo_zip_path=sync_kbo_to_tracardi.DEFAULT_KBO_ZIP_PATH,
        batch_size=100,
        target_count=0,
        verify_attempts=1,
        verify_delay_seconds=0.1,
    )

    original_client = sync_kbo_to_tracardi.httpx.AsyncClient
    sync_kbo_to_tracardi.httpx.AsyncClient = lambda timeout: FakeClient()
    try:
        token = await sync_kbo_to_tracardi.get_tracardi_token(config)
    finally:
        sync_kbo_to_tracardi.httpx.AsyncClient = original_client

    assert token == "token-from-json"
    assert len(calls) == 2
    assert "data" in calls[0][1]
    assert calls[1][1]["json"] == {
        "username": "admin@admin.com",
        "password": "secret",
    }
