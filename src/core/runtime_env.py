"""Bootstrap process environment for repo-managed runtime entrypoints.

Chainlit loads `.env` from the current working directory during import. Preload the
repo env files here so local overrides in `.env.local` win before Chainlit touches
``os.environ``.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv


def _env_flag_enabled(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _set_default_env(target: str, source: str) -> None:
    source_value = os.environ.get(source)
    if source_value and not os.environ.get(target):
        os.environ[target] = source_value


def _derive_chainlit_url_from_redirect_uri(redirect_uri: str | None) -> str | None:
    if not redirect_uri:
        return None

    parsed = urlsplit(redirect_uri)
    callback_suffix = "/auth/oauth/azure-ad/callback"
    if not parsed.scheme or not parsed.netloc or not parsed.path.endswith(callback_suffix):
        return None

    base_path = parsed.path[: -len(callback_suffix)]
    return urlunsplit((parsed.scheme, parsed.netloc, base_path.rstrip("/"), "", ""))


def _bootstrap_chainlit_oauth_environment() -> None:
    if not _env_flag_enabled(os.environ.get("CHAINLIT_ENABLE_AZURE_AD")):
        return

    _set_default_env("OAUTH_AZURE_AD_CLIENT_ID", "AZURE_AD_CLIENT_ID")
    _set_default_env("OAUTH_AZURE_AD_CLIENT_SECRET", "AZURE_AD_CLIENT_SECRET")
    _set_default_env("OAUTH_AZURE_AD_TENANT_ID", "AZURE_AD_TENANT_ID")
    if os.environ.get("AZURE_AD_TENANT_ID") and not os.environ.get(
        "OAUTH_AZURE_AD_ENABLE_SINGLE_TENANT"
    ):
        os.environ["OAUTH_AZURE_AD_ENABLE_SINGLE_TENANT"] = "true"

    redirect_uri = os.environ.get("AZURE_AD_REDIRECT_URI")
    if not os.environ.get("CHAINLIT_URL"):
        chainlit_url = _derive_chainlit_url_from_redirect_uri(redirect_uri)
        if chainlit_url:
            os.environ["CHAINLIT_URL"] = chainlit_url


def bootstrap_runtime_environment(repo_root: Path | None = None) -> None:
    """Load repo env files into ``os.environ`` with local overrides winning."""
    root = repo_root or Path(__file__).resolve().parents[2]

    default_env = root / ".env"
    local_env = root / ".env.local"

    if default_env.exists():
        load_dotenv(default_env, override=False)
    if local_env.exists():
        load_dotenv(local_env, override=True)

    _bootstrap_chainlit_oauth_environment()
