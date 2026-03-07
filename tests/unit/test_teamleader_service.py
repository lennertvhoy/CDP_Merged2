from __future__ import annotations

import os
from pathlib import Path

import httpx

from src.services.teamleader import (
    TeamleaderClient,
    TeamleaderCredentials,
    load_teamleader_env_file,
)


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)
        self.request = httpx.Request("POST", "https://example.test")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self) -> dict:
        return self._payload


def test_load_teamleader_env_file_reads_simple_key_values(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env.teamleader"
    env_path.write_text(
        "TEAMLEADER_CLIENT_ID=client-id\n"
        "TEAMLEADER_CLIENT_SECRET='client-secret'\n"
        "# comment\n"
        "TEAMLEADER_REFRESH_TOKEN=refresh-token\n"
    )

    with monkeypatch.context() as context:
        context.setattr(os, "environ", {})
        assert load_teamleader_env_file(env_path) is True
        assert os.environ["TEAMLEADER_CLIENT_ID"] == "client-id"
        assert os.environ["TEAMLEADER_CLIENT_SECRET"] == "client-secret"
        assert os.environ["TEAMLEADER_REFRESH_TOKEN"] == "refresh-token"


def test_refresh_access_token_updates_client_and_env_file(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env.teamleader"
    env_path.write_text("TEAMLEADER_REFRESH_TOKEN=old-refresh\n")
    client = TeamleaderClient(
        TeamleaderCredentials(
            client_id="client-id",
            client_secret="client-secret",
            refresh_token="old-refresh",
        ),
        env_path=env_path,
    )

    def fake_post(url: str, *, data: dict, timeout: float) -> _FakeResponse:
        assert "oauth2/access_token" in url
        assert data["refresh_token"] == "old-refresh"
        assert timeout == 30.0
        return _FakeResponse(
            {"access_token": "new-access-token", "refresh_token": "new-refresh-token"}
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    access_token = client.refresh_access_token()

    assert access_token == "new-access-token"
    assert client.access_token == "new-access-token"
    assert client.credentials.refresh_token == "new-refresh-token"
    assert "TEAMLEADER_REFRESH_TOKEN=new-refresh-token" in env_path.read_text()


def test_first_record_uses_list_endpoint_payload(monkeypatch) -> None:
    client = TeamleaderClient(
        TeamleaderCredentials(
            client_id="client-id",
            client_secret="client-secret",
            refresh_token="refresh-token",
        )
    )
    client.access_token = "access-token"

    def fake_post(url: str, *, headers: dict, json: dict, timeout: float) -> _FakeResponse:
        assert url.endswith("/companies.list")
        assert headers["Authorization"] == "Bearer access-token"
        assert json == {"page": {"size": 1, "number": 1}}
        assert timeout == 30.0
        return _FakeResponse({"data": [{"id": "company-1", "name": "Live Company"}]})

    monkeypatch.setattr(httpx, "post", fake_post)

    first_record = client.first_record("companies.list")

    assert first_record == {"id": "company-1", "name": "Live Company"}
