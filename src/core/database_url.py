"""Helpers for resolving PostgreSQL connection configuration without inline defaults."""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_dotenv_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None

    value = dotenv_values(path).get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _runtime_env(repo_root: Path) -> dict[str, str]:
    merged: dict[str, str] = {}

    for path in (repo_root / ".env", repo_root / ".env.local"):
        if not path.exists():
            continue
        for key, value in dotenv_values(path).items():
            if isinstance(value, str) and value:
                merged[key] = value

    for key, value in os.environ.items():
        merged[key] = value

    return merged


def _env_database_url(repo_root: Path) -> str | None:
    env_database_path = repo_root / ".env.database"
    if not env_database_path.exists():
        return None

    config = configparser.ConfigParser()
    config.read(env_database_path)
    value = config.get("connection_string", "url", fallback=None)
    if value:
        return value
    return None


def database_config_source(repo_root: Path = REPO_ROOT) -> str | None:
    """Report the highest-priority available database config source."""
    if os.environ.get("DATABASE_URL"):
        return "env:DATABASE_URL"
    if os.environ.get("POSTGRES_CONNECTION_STRING"):
        return "env:POSTGRES_CONNECTION_STRING"

    if _read_dotenv_value(repo_root / ".env.local", "DATABASE_URL"):
        return "file:.env.local:DATABASE_URL"
    if _read_dotenv_value(repo_root / ".env.local", "POSTGRES_CONNECTION_STRING"):
        return "file:.env.local:POSTGRES_CONNECTION_STRING"
    if _read_dotenv_value(repo_root / ".env", "DATABASE_URL"):
        return "file:.env:DATABASE_URL"
    if _read_dotenv_value(repo_root / ".env", "POSTGRES_CONNECTION_STRING"):
        return "file:.env:POSTGRES_CONNECTION_STRING"
    if _env_database_url(repo_root):
        return "file:.env.database"

    runtime_env = _runtime_env(repo_root)
    required_parts = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    if all(runtime_env.get(key) for key in required_parts):
        if any(os.environ.get(key) for key in required_parts):
            return "env:DB_*"
        if any(_read_dotenv_value(repo_root / ".env.local", key) for key in required_parts):
            return "file:.env.local:DB_*"
        if any(_read_dotenv_value(repo_root / ".env", key) for key in required_parts):
            return "file:.env:DB_*"
        return "env:DB_*"

    return None


def resolve_database_url(repo_root: Path = REPO_ROOT) -> str:
    """Resolve the PostgreSQL URL from env, local config files, or DB_* parts."""
    runtime_env = _runtime_env(repo_root)

    for key in ("DATABASE_URL", "POSTGRES_CONNECTION_STRING"):
        value = runtime_env.get(key)
        if value:
            return value

    if env_database_url := _env_database_url(repo_root):
        return env_database_url

    host = runtime_env.get("DB_HOST")
    name = runtime_env.get("DB_NAME")
    user = runtime_env.get("DB_USER")
    password = runtime_env.get("DB_PASSWORD")
    port = runtime_env.get("DB_PORT", "5432")
    sslmode = runtime_env.get("DB_SSLMODE", "disable")

    if all([host, name, user, password]):
        return f"postgresql://{user}:{password}@{host}:{port}/{name}?sslmode={sslmode}"

    raise RuntimeError(
        "DATABASE_URL, POSTGRES_CONNECTION_STRING, local .env.database "
        "[connection_string] url, or DB_HOST/DB_NAME/DB_USER/DB_PASSWORD must be configured."
    )
