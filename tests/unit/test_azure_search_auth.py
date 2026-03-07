"""Unit tests for Azure Search auth integration behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.services.azure_search import AzureSearchClient


def test_azure_search_client_uses_api_key_auth_header():
    with patch("src.services.azure_search.settings") as mock_settings:
        mock_settings.AZURE_SEARCH_ENDPOINT = "https://search.example.windows.net"
        mock_settings.AZURE_SEARCH_INDEX_NAME = "profiles"
        mock_settings.AZURE_SEARCH_API_VERSION = "2023-11-01"
        mock_settings.AZURE_SEARCH_TIMEOUT_SECONDS = 10.0
        mock_settings.AZURE_SEARCH_TOP_K = 5
        mock_settings.AZURE_SEARCH_API_KEY = "fallback-key"
        mock_settings.AZURE_SEARCH_API_KEY_SECRET_NAME = None

        with patch("src.services.azure_search.AzureCredentialResolver") as mock_resolver_cls:
            mock_resolver = mock_resolver_cls.return_value
            mock_resolver.resolve.return_value.api_key = "resolved-key"
            mock_resolver.resolve.return_value.token_provider = None
            mock_resolver.resolve.return_value.auth_source = "explicit_key"

            client = AzureSearchClient()

        assert client.api_key == "resolved-key"
        assert client.token_provider is None
        assert client.is_configured() is True


@pytest.mark.asyncio
async def test_azure_search_client_uses_bearer_token_header():
    with patch("src.services.azure_search.settings") as mock_settings:
        mock_settings.AZURE_SEARCH_ENDPOINT = "https://search.example.windows.net"
        mock_settings.AZURE_SEARCH_INDEX_NAME = "profiles"
        mock_settings.AZURE_SEARCH_API_VERSION = "2023-11-01"
        mock_settings.AZURE_SEARCH_TIMEOUT_SECONDS = 10.0
        mock_settings.AZURE_SEARCH_TOP_K = 5
        mock_settings.AZURE_SEARCH_API_KEY = None
        mock_settings.AZURE_SEARCH_API_KEY_SECRET_NAME = None

        with patch("src.services.azure_search.AzureCredentialResolver") as mock_resolver_cls:
            mock_resolver = mock_resolver_cls.return_value
            mock_resolver.resolve.return_value.api_key = None
            mock_resolver.resolve.return_value.token_provider = lambda: "mi-token"
            mock_resolver.resolve.return_value.auth_source = "managed_identity"

            client = AzureSearchClient()

    response = Mock()
    response.raise_for_status = Mock()
    response.json = Mock(return_value={"value": [], "@odata.count": 0})

    post_mock = AsyncMock(return_value=response)
    async_client_ctx = Mock()
    async_client_ctx.__aenter__ = AsyncMock(return_value=Mock(post=post_mock))
    async_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("src.services.azure_search.httpx.AsyncClient", return_value=async_client_ctx):
        await client.search_documents(query_text="test")

    _, kwargs = post_mock.call_args
    assert kwargs["headers"].get("Authorization") == "Bearer mi-token"
    assert "api-key" not in kwargs["headers"]
