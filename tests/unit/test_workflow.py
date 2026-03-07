"""Unit tests for LangGraph workflow execution behavior."""

from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import HumanMessage

from src.config import settings
from src.graph.workflow import compile_workflow


@pytest.mark.asyncio
async def test_workflow_completes_in_mock_mode(monkeypatch):
    """Mock mode should complete without external LLM/network calls."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")

    workflow = compile_workflow()
    result = await asyncio.wait_for(
        workflow.ainvoke(
            {
                "messages": [HumanMessage(content="Quick smoke test")],
                "language": "",
                "profile_id": "",
            },
            config={"configurable": {"thread_id": "unit-workflow-thread"}},
        ),
        timeout=5,
    )

    messages = result.get("messages", [])
    assert messages
    assert "Mock response to:" in messages[-1].content
