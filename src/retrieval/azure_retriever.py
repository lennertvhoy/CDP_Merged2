"""Azure AI Search retriever with citation-ready normalization."""

from __future__ import annotations

from typing import Any

from src.config import settings
from src.services.azure_search import AzureSearchClient


class AzureSearchRetriever:
    """Retrieves documents from Azure AI Search and normalizes output for tool contracts."""

    def __init__(self, client: AzureSearchClient | None = None) -> None:
        self.client = client or AzureSearchClient()

    async def retrieve(
        self,
        *,
        query_text: str,
        top_k: int | None = None,
        filter_expression: str | None = None,
    ) -> dict[str, Any]:
        raw = await self.client.search_documents(
            query_text=query_text,
            top=top_k or settings.AZURE_SEARCH_TOP_K,
            filter_expression=filter_expression,
        )

        values = raw.get("value", []) or []
        normalized_documents = [
            self._normalize_document(doc, idx) for idx, doc in enumerate(values)
        ]

        citations = [
            {
                "id": doc["id"],
                "title": doc["title"],
                "url": doc.get("url"),
                "snippet": doc.get("snippet", ""),
                "score": doc.get("score"),
            }
            for doc in normalized_documents
        ]

        return {
            "backend": "azure_ai_search",
            "total": int(raw.get("@odata.count", len(normalized_documents)) or 0),
            "returned": len(normalized_documents),
            "documents": normalized_documents,
            "citations": citations,
            "raw_metadata": {
                "api_version": settings.AZURE_SEARCH_API_VERSION,
            },
        }

    def _normalize_document(self, doc: dict[str, Any], index: int) -> dict[str, Any]:
        id_field = settings.AZURE_SEARCH_ID_FIELD
        title_field = settings.AZURE_SEARCH_TITLE_FIELD
        content_field = settings.AZURE_SEARCH_CONTENT_FIELD
        url_field = settings.AZURE_SEARCH_URL_FIELD

        snippet = (
            doc.get("@search.captions", [{}])[0].get("text")
            if isinstance(doc.get("@search.captions"), list)
            else None
        )

        return {
            "id": str(doc.get(id_field) or f"azure-doc-{index + 1}"),
            "title": str(doc.get(title_field) or doc.get("title") or "[Untitled]"),
            "content": str(doc.get(content_field) or ""),
            "url": doc.get(url_field) or doc.get("url"),
            "score": doc.get("@search.score"),
            "snippet": str(snippet or doc.get(content_field) or ""),
            "source": "azure_ai_search",
            "raw": doc,
        }
