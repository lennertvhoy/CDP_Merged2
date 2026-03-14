"""Unit tests for the LLM provider factory and MockProvider."""

from __future__ import annotations

import pytest

from src.core.llm_provider import LLMMode, MockProvider, get_llm_provider


class TestLLMModeEnum:
    def test_values(self):
        assert LLMMode.OPENAI == "openai"
        assert LLMMode.AZURE_OPENAI == "azure_openai"
        assert LLMMode.OLLAMA == "ollama"
        assert LLMMode.MOCK == "mock"


class TestMockProvider:
    @pytest.mark.asyncio
    async def test_generate_returns_string(self):
        provider = MockProvider()
        messages = [{"role": "user", "content": "Hello!"}]
        response = await provider.generate(messages)
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_generate_echoes_user_content(self):
        provider = MockProvider()
        messages = [{"role": "user", "content": "Find companies in Gent"}]
        response = await provider.generate(messages)
        assert "Find companies in Gent" in response

    @pytest.mark.asyncio
    async def test_generate_structured_returns_model(self):
        from pydantic import BaseModel

        class TestModel(BaseModel):
            name: str = "test"

        provider = MockProvider()
        messages = [{"role": "user", "content": "test"}]
        result = await provider.generate_structured(messages, TestModel)
        assert isinstance(result, TestModel)

    @pytest.mark.asyncio
    async def test_generate_empty_messages(self):
        provider = MockProvider()
        response = await provider.generate([])
        assert isinstance(response, str)


class TestGetLLMProvider:
    def test_mock_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        # Need to reload settings for monkeypatch to take effect
        from unittest.mock import patch

        with patch("src.core.llm_provider.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "mock"
            provider = get_llm_provider()
            assert isinstance(provider, MockProvider)

    def test_unknown_provider_raises(self):
        from unittest.mock import patch

        with patch("src.core.llm_provider.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "unknown_provider"
            with pytest.raises(ValueError, match="Unsupported LLM provider"):
                get_llm_provider()

    def test_openai_without_key_raises(self):
        from unittest.mock import patch

        with patch("src.core.llm_provider.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = None
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                get_llm_provider()

    def test_azure_openai_uses_resolved_api_key(self):
        from unittest.mock import patch

        with patch("src.core.llm_provider.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "azure_openai"
            mock_settings.AZURE_OPENAI_ENDPOINT = "https://aoai.example.com"
            mock_settings.AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4o-mini"
            mock_settings.AZURE_OPENAI_API_VERSION = "2024-02-01"
            mock_settings.AZURE_OPENAI_API_KEY = "fallback-key"
            mock_settings.AZURE_OPENAI_API_KEY_SECRET_NAME = None

            with patch("src.core.llm_provider.AzureCredentialResolver") as mock_resolver_cls:
                mock_resolver = mock_resolver_cls.return_value
                mock_resolver.resolve.return_value.api_key = "resolved-key"
                mock_resolver.resolve.return_value.token_provider = None

                with patch("src.core.llm_provider.AzureOpenAIProvider") as mock_provider_cls:
                    get_llm_provider()

            mock_provider_cls.assert_called_once_with(
                endpoint="https://aoai.example.com",
                deployment_name="gpt-4o-mini",
                api_version="2024-02-01",
                api_key="resolved-key",
                azure_ad_token_provider=None,
            )

    def test_azure_openai_missing_auth_raises(self):
        from unittest.mock import patch

        with patch("src.core.llm_provider.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "azure_openai"
            mock_settings.AZURE_OPENAI_ENDPOINT = "https://aoai.example.com"
            mock_settings.AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4o-mini"
            mock_settings.AZURE_OPENAI_API_VERSION = "2024-02-01"
            mock_settings.AZURE_OPENAI_API_KEY = None
            mock_settings.AZURE_OPENAI_API_KEY_SECRET_NAME = None

            with patch("src.core.llm_provider.AzureCredentialResolver") as mock_resolver_cls:
                mock_resolver = mock_resolver_cls.return_value
                mock_resolver.resolve.return_value.api_key = None
                mock_resolver.resolve.return_value.token_provider = None

                with pytest.raises(ValueError, match="authentication is not configured"):
                    get_llm_provider()
