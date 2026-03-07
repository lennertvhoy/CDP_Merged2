"""
Azure AI Search client wrapper.
"""

from __future__ import annotations

from typing import Any

import httpx

from src.config import settings
from src.core.azure_auth import AzureCredentialResolver
from src.core.logger import get_logger

logger = get_logger(__name__)


class AzureSearchClient:
    """Thin async wrapper around Azure AI Search REST API."""

    def __init__(self) -> None:
        self.endpoint = (settings.AZURE_SEARCH_ENDPOINT or "").rstrip("/")
        self.index_name = settings.AZURE_SEARCH_INDEX_NAME
        self.api_version = settings.AZURE_SEARCH_API_VERSION
        self.timeout = settings.AZURE_SEARCH_TIMEOUT_SECONDS

        auth = AzureCredentialResolver("azure_search").resolve(
            explicit_key=settings.AZURE_SEARCH_API_KEY,
            key_vault_secret_name=settings.AZURE_SEARCH_API_KEY_SECRET_NAME,
            token_scope="https://search.azure.com/.default",
            require_token_credential=True,
        )
        self.api_key = auth.api_key
        self.token_provider = auth.token_provider
        self.auth_source = auth.auth_source
        logger.info("azure_search_auth_initialized", auth_source=self.auth_source)

    def is_configured(self) -> bool:
        return bool(self.endpoint and self.index_name and (self.api_key or self.token_provider))

    async def search_documents(
        self,
        query_text: str,
        *,
        top: int | None = None,
        filter_expression: str | None = None,
    ) -> dict[str, Any]:
        """Execute a document search against Azure AI Search.

        Returns Azure-like payload with `value` list and optional `@odata.count`.
        """
        if not self.is_configured():
            logger.warning("azure_search_not_configured")
            return {"value": [], "@odata.count": 0}

        url = f"{self.endpoint}/indexes/{self.index_name}/docs/search"
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["api-key"] = str(self.api_key)
        elif self.token_provider is not None:
            token = self.token_provider()
            headers["Authorization"] = f"Bearer {token}"

        payload: dict[str, Any] = {
            "search": query_text or "*",
            "top": int(top or settings.AZURE_SEARCH_TOP_K),
            "count": True,
        }
        if filter_expression:
            payload["filter"] = filter_expression

        params = {"api-version": self.api_version}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, headers=headers, params=params, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                logger.error("azure_search_request_failed", error=str(exc))
                return {"value": [], "@odata.count": 0}
