"""Shared auth helpers for the operator-shell access gate."""

from __future__ import annotations

from typing import Any, Literal

from chainlit.user import User
from fastapi import Request

from src.config import settings
from src.services.local_account_auth import (
    authenticate_local_account,
    normalize_local_account_identifier,
)

PasswordAuthMode = Literal["local-accounts", "shared-secret"]


def local_account_auth_enabled() -> bool:
    """Return whether PostgreSQL-backed local accounts are enabled."""
    return bool(settings.CHAINLIT_LOCAL_ACCOUNT_AUTH_ENABLED)


def legacy_shared_password_auth_enabled() -> bool:
    """Return whether the legacy shared-password fallback is enabled."""
    return bool(settings.CHAINLIT_DEV_AUTH_ENABLED and settings.CHAINLIT_DEV_AUTH_PASSWORD)


def password_auth_mode() -> PasswordAuthMode | None:
    """Return the single password-auth truth exposed to the shell."""
    if local_account_auth_enabled():
        return "local-accounts"
    if legacy_shared_password_auth_enabled():
        return "shared-secret"
    return None


def password_auth_enabled() -> bool:
    """Return whether any password-auth path is available."""
    return password_auth_mode() is not None


def operator_auth_enabled() -> bool:
    """Return whether operator requests must respect shell access-gate auth."""
    return password_auth_enabled()


def operator_auth_config() -> dict[str, Any]:
    """Describe the single shell-visible access-gate model."""
    return {
        "required": operator_auth_enabled(),
        "password_enabled": password_auth_enabled(),
        "password_mode": password_auth_mode(),
    }


def _normalize_password_auth_identifier(username: str) -> str | None:
    return normalize_local_account_identifier(username)


async def authenticate_password_user(username: str, password: str) -> User | None:
    """Authenticate the configured password-auth mode for the shell."""
    mode = password_auth_mode()
    if mode is None:
        return None

    if mode == "local-accounts":
        identifier = _normalize_password_auth_identifier(username)
        if identifier is None:
            return None
        account = await authenticate_local_account(identifier, password)
        if account is None:
            return None
        metadata: dict[str, Any] = {
            "provider": "local-account",
            "is_admin": account.is_admin,
        }
        return User(
            identifier=account.identifier,
            display_name=account.display_name or account.identifier,
            metadata=metadata,
        )

    expected_password = settings.CHAINLIT_DEV_AUTH_PASSWORD
    if not expected_password or password != expected_password:
        return None

    identifier = _normalize_password_auth_identifier(username) or "preview-access"

    return User(
        identifier=identifier,
        display_name=identifier,
        metadata={"provider": "dev-password"},
    )


def extract_request_user_context(request: Request) -> dict[str, Any] | None:
    """Resolve the authenticated Chainlit user from the auth cookie.

    The operator shell must follow the same user identity truth as Chainlit.
    We therefore decode Chainlit's signed auth cookie instead of trusting a
    browser-supplied user header.
    """
    if not operator_auth_enabled():
        return None

    try:
        from chainlit.auth import decode_jwt
        from chainlit.auth.cookie import get_token_from_cookies
    except Exception:
        return None

    token = get_token_from_cookies(request.cookies)
    if not token:
        return None

    try:
        user = decode_jwt(token)
    except Exception:
        return None

    metadata = getattr(user, "metadata", None)
    user_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    user_metadata.setdefault("source", "chainlit-auth-cookie")

    return {
        "identifier": user.identifier,
        "display_name": getattr(user, "display_name", None) or user.identifier,
        "metadata": user_metadata,
    }
