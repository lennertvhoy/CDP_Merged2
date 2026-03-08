from pathlib import Path

import pytest

from src.core.database_url import database_config_source, resolve_database_url


def test_resolve_database_url_prefers_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://env-user:env-pass@env-host:5432/env-db")

    assert resolve_database_url(tmp_path) == "postgresql://env-user:env-pass@env-host:5432/env-db"
    assert database_config_source(tmp_path) == "env:DATABASE_URL"


def test_resolve_database_url_prefers_env_local_over_env_file(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_CONNECTION_STRING", raising=False)
    (tmp_path / ".env").write_text("DATABASE_URL=postgresql://env-file/db\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text(
        "DATABASE_URL=postgresql://env-local/db\n",
        encoding="utf-8",
    )

    assert resolve_database_url(tmp_path) == "postgresql://env-local/db"
    assert database_config_source(tmp_path) == "file:.env.local:DATABASE_URL"


def test_resolve_database_url_reads_env_database(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_CONNECTION_STRING", raising=False)
    (tmp_path / ".env.database").write_text(
        "[connection_string]\nurl = postgresql://env-database/db\n",
        encoding="utf-8",
    )

    assert resolve_database_url(tmp_path) == "postgresql://env-database/db"
    assert database_config_source(tmp_path) == "file:.env.database"


def test_resolve_database_url_builds_from_parts(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_CONNECTION_STRING", raising=False)
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_NAME", "cdp")
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWORD", "pass")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_SSLMODE", "require")

    assert (
        resolve_database_url(tmp_path)
        == "postgresql://user:pass@localhost:5433/cdp?sslmode=require"
    )
    assert database_config_source(tmp_path) == "env:DB_*"


def test_resolve_database_url_raises_without_configuration(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.delenv("DB_USER", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.delenv("DB_PORT", raising=False)
    monkeypatch.delenv("DB_SSLMODE", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        resolve_database_url(tmp_path)
