"""Unit tests for environment-backed settings."""

from src.config import Settings


def test_azure_deployment_name_from_primary_env(monkeypatch):
    monkeypatch.setenv("TRACARDI_USERNAME", "admin")
    monkeypatch.setenv("TRACARDI_PASSWORD", "admin")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "primary-deployment")
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)

    settings = Settings(_env_file=None)

    assert settings.AZURE_OPENAI_DEPLOYMENT_NAME == "primary-deployment"


def test_azure_deployment_name_from_legacy_env(monkeypatch):
    monkeypatch.setenv("TRACARDI_USERNAME", "admin")
    monkeypatch.setenv("TRACARDI_PASSWORD", "admin")
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT_NAME", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "legacy-deployment")

    settings = Settings(_env_file=None)

    assert settings.AZURE_OPENAI_DEPLOYMENT_NAME == "legacy-deployment"


def test_azure_deployment_name_prefers_primary_env(monkeypatch):
    monkeypatch.setenv("TRACARDI_USERNAME", "admin")
    monkeypatch.setenv("TRACARDI_PASSWORD", "admin")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "primary-deployment")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "legacy-deployment")

    settings = Settings(_env_file=None)

    assert settings.AZURE_OPENAI_DEPLOYMENT_NAME == "primary-deployment"


def test_azure_search_feature_flags_default_safe(monkeypatch):
    monkeypatch.setenv("TRACARDI_USERNAME", "admin")
    monkeypatch.setenv("TRACARDI_PASSWORD", "admin")
    monkeypatch.delenv("ENABLE_AZURE_SEARCH_RETRIEVAL", raising=False)
    monkeypatch.delenv("ENABLE_AZURE_SEARCH_SHADOW_MODE", raising=False)
    monkeypatch.delenv("ENABLE_CITATION_REQUIRED", raising=False)

    settings = Settings(_env_file=None)

    assert settings.ENABLE_AZURE_SEARCH_RETRIEVAL is False
    assert settings.ENABLE_AZURE_SEARCH_SHADOW_MODE is False
    assert settings.ENABLE_CITATION_REQUIRED is False


def test_azure_search_runtime_defaults(monkeypatch):
    monkeypatch.setenv("TRACARDI_USERNAME", "admin")
    monkeypatch.setenv("TRACARDI_PASSWORD", "admin")
    monkeypatch.delenv("AZURE_SEARCH_TOP_K", raising=False)
    monkeypatch.delenv("AZURE_SEARCH_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("AZURE_SEARCH_API_VERSION", raising=False)

    settings = Settings(_env_file=None)

    assert settings.AZURE_SEARCH_TOP_K == 20
    assert settings.AZURE_SEARCH_TIMEOUT_SECONDS == 10.0
    assert settings.AZURE_SEARCH_API_VERSION == "2023-11-01"


def test_azure_auth_defaults_safe_for_rollout(monkeypatch):
    monkeypatch.setenv("TRACARDI_USERNAME", "admin")
    monkeypatch.setenv("TRACARDI_PASSWORD", "admin")
    monkeypatch.delenv("AZURE_AUTH_USE_DEFAULT_CREDENTIAL", raising=False)
    monkeypatch.delenv("AZURE_AUTH_ALLOW_KEY_FALLBACK", raising=False)
    monkeypatch.delenv("AZURE_AUTH_STRICT_MI_KV_ONLY", raising=False)
    monkeypatch.delenv("AZURE_KEY_VAULT_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.AZURE_AUTH_USE_DEFAULT_CREDENTIAL is True
    assert settings.AZURE_AUTH_ALLOW_KEY_FALLBACK is True
    assert settings.AZURE_AUTH_STRICT_MI_KV_ONLY is False
    assert settings.AZURE_KEY_VAULT_URL is None
