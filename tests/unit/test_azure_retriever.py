"""Unit tests for Azure AI Search retriever normalization."""

from __future__ import annotations

import pytest

from src.retrieval.azure_retriever import AzureSearchRetriever


class _FakeAzureClient:
    async def search_documents(
        self, query_text: str, *, top: int | None = None, filter_expression=None
    ):
        return {
            "@odata.count": 2,
            "value": [
                {
                    "id": "doc-1",
                    "name": "Alpha Corp",
                    "content": "Alpha content",
                    "source_url": "https://example.com/a",
                    "@search.score": 2.1,
                },
                {
                    "id": "doc-2",
                    "name": "Beta Corp",
                    "content": "Beta content",
                    "@search.captions": [{"text": "Beta caption"}],
                    "@search.score": 1.9,
                },
            ],
        }


@pytest.mark.asyncio
async def test_azure_retriever_normalizes_documents_and_citations():
    retriever = AzureSearchRetriever(client=_FakeAzureClient())

    result = await retriever.retrieve(query_text="beta")

    assert result["backend"] == "azure_ai_search"
    assert result["total"] == 2
    assert result["returned"] == 2
    assert result["documents"][0]["title"] == "Alpha Corp"
    assert result["citations"][0]["id"] == "doc-1"
    assert result["citations"][1]["snippet"] == "Beta caption"
