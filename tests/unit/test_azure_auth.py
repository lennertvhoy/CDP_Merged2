"""Unit tests for Azure MI/KV-first credential resolution."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.core.azure_auth import AzureCredentialResolver


class _DummyCredential:
    pass


def _make_settings(
    *,
    strict: bool = False,
    use_default_credential: bool = True,
    allow_key_fallback: bool = True,
    key_vault_url: str | None = None,
):
    class _S:
        AZURE_AUTH_STRICT_MI_KV_ONLY = strict
        AZURE_AUTH_USE_DEFAULT_CREDENTIAL = use_default_credential
        AZURE_AUTH_ALLOW_KEY_FALLBACK = allow_key_fallback
        AZURE_KEY_VAULT_URL = key_vault_url

    return _S()


def test_prefers_managed_identity_token_provider():
    resolver = AzureCredentialResolver("azure_search")

    with patch("src.core.azure_auth.settings", _make_settings()):
        with patch.object(resolver, "_create_default_credential", return_value=_DummyCredential()):
            with patch.object(
                resolver, "_build_bearer_token_provider", return_value=lambda: "token"
            ):
                auth = resolver.resolve(
                    explicit_key="explicit-key",
                    key_vault_secret_name=None,
                    token_scope="https://search.azure.com/.default",
                    require_token_credential=True,
                )

    assert auth.auth_source == "managed_identity"
    assert auth.api_key is None
    assert callable(auth.token_provider)


def test_uses_key_vault_secret_when_mi_token_provider_fails_and_secret_configured():
    resolver = AzureCredentialResolver("azure_openai")

    with patch(
        "src.core.azure_auth.settings",
        _make_settings(key_vault_url="https://vault.vault.azure.net"),
    ):
        with patch.object(resolver, "_create_default_credential", return_value=_DummyCredential()):
            with patch.object(
                resolver,
                "_build_bearer_token_provider",
                side_effect=ValueError("token provider unavailable"),
            ):
                with patch.object(resolver, "_resolve_secret", return_value="kv-secret-key"):
                    auth = resolver.resolve(
                        explicit_key="explicit-key",
                        key_vault_secret_name="aoai-api-key",
                        token_scope="https://cognitiveservices.azure.com/.default",
                        require_token_credential=False,
                    )

    assert auth.auth_source == "key_vault_secret"
    assert auth.api_key == "kv-secret-key"


def test_falls_back_to_explicit_key_when_allowed():
    resolver = AzureCredentialResolver("azure_openai")

    with patch("src.core.azure_auth.settings", _make_settings(use_default_credential=False)):
        auth = resolver.resolve(
            explicit_key="explicit-key",
            key_vault_secret_name=None,
            token_scope="https://cognitiveservices.azure.com/.default",
            require_token_credential=False,
        )

    assert auth.auth_source == "explicit_key"
    assert auth.api_key == "explicit-key"


def test_strict_mode_fails_without_resolvable_auth():
    resolver = AzureCredentialResolver("azure_openai")

    with patch(
        "src.core.azure_auth.settings",
        _make_settings(strict=True, use_default_credential=False, allow_key_fallback=True),
    ):
        with pytest.raises(
            ValueError, match="strict mode requires AZURE_AUTH_USE_DEFAULT_CREDENTIAL=true"
        ):
            resolver.resolve(
                explicit_key="explicit-key",
                key_vault_secret_name=None,
                token_scope="https://cognitiveservices.azure.com/.default",
                require_token_credential=False,
            )
