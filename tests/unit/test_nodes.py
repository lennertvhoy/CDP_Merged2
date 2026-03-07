"""Unit tests for LangGraph router node logic."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import settings
from src.graph.nodes import (
    SYSTEM_PROMPTS,
    _build_azure_chat_model_kwargs,
    detect_language,
    router_node,
)
from src.graph.state import AgentState


class TestDetectLanguage:
    def test_english_default(self):
        assert detect_language("Find IT companies in Gent") == "en"

    def test_french_by_bonjour(self):
        assert detect_language("Bonjour, cherche des entreprises à Bruxelles") == "fr"

    def test_french_by_merci(self):
        assert detect_language("merci beaucoup") == "fr"

    def test_dutch_by_hallo(self):
        assert detect_language("Hallo, ik zoek bedrijven in Gent") == "nl"

    def test_dutch_by_dank(self):
        assert detect_language("dank u wel") == "nl"

    def test_case_insensitive(self):
        assert detect_language("BONJOUR") == "fr"


class TestRouterNode:
    @pytest.mark.asyncio
    async def test_injects_system_prompt(self):
        state: AgentState = {
            "messages": [HumanMessage(content="Find IT companies")],
            "language": "",
            "profile_id": None,
        }
        result = await router_node(state)
        assert result["language"] == "en"
        # Should inject a system message
        assert any(isinstance(m, SystemMessage) for m in result["messages"])

    @pytest.mark.asyncio
    async def test_does_not_duplicate_system_prompt(self):
        """If a system message exists, don't inject another."""
        state: AgentState = {
            "messages": [
                SystemMessage(content="Existing system prompt"),
                HumanMessage(content="Find IT companies"),
            ],
            "language": "en",
            "profile_id": None,
        }
        result = await router_node(state)
        new_system_msgs = [m for m in result["messages"] if isinstance(m, SystemMessage)]
        assert len(new_system_msgs) == 0  # No new system messages added

    @pytest.mark.asyncio
    async def test_detects_french(self):
        state: AgentState = {
            "messages": [HumanMessage(content="Bonjour, cherche entreprises IT")],
            "language": "",
            "profile_id": None,
        }
        result = await router_node(state)
        assert result["language"] == "fr"

    @pytest.mark.asyncio
    async def test_respects_preset_language(self):
        state: AgentState = {
            "messages": [HumanMessage(content="Find companies")],
            "language": "nl",  # Already set
            "profile_id": None,
        }
        result = await router_node(state)
        assert result["language"] == "nl"

    def test_prompt_enforces_authoritative_counts(self):
        prompt = SYSTEM_PROMPTS["en"]
        assert "counts.authoritative_total" in prompt
        assert "add counts across turns" in prompt.lower()
        assert "dataset_state.companies_table_empty=true" in prompt
        assert "Only set `status=\"AC\"` if the user explicitly asks" in prompt

    @pytest.mark.asyncio
    async def test_router_injects_citation_rules_when_flags_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "ENABLE_AZURE_SEARCH_RETRIEVAL", True)
        monkeypatch.setattr(settings, "ENABLE_CITATION_REQUIRED", True)

        state: AgentState = {
            "messages": [HumanMessage(content="Find IT companies")],
            "language": "",
            "profile_id": None,
        }
        result = await router_node(state)
        system_messages = [m for m in result["messages"] if isinstance(m, SystemMessage)]

        assert system_messages
        assert "GROUNDING & CITATIONS" in system_messages[0].content


def test_build_azure_chat_model_kwargs_bounds_retries_and_output(monkeypatch):
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://aoai.example.com")
    monkeypatch.setattr(settings, "AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_VERSION", "2024-02-01")
    monkeypatch.setattr(settings, "AZURE_OPENAI_TIMEOUT", 15.0)
    monkeypatch.setattr(settings, "AZURE_OPENAI_MAX_RETRIES", 0)
    monkeypatch.setattr(settings, "AZURE_OPENAI_MAX_TOKENS", 800)

    kwargs = _build_azure_chat_model_kwargs(api_key="secret-key")

    assert kwargs == {
        "azure_endpoint": "https://aoai.example.com",
        "azure_deployment": "gpt-4o-mini",
        "api_version": "2024-02-01",
        "temperature": 0,
        "timeout": 15.0,
        "max_retries": 0,
        "max_tokens": 800,
        "api_key": "secret-key",
    }
