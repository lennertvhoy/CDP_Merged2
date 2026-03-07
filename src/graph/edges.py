"""
Edge condition functions for the CDP_Merged LangGraph workflow.

Extracted from workflow.py to make edge logic independently testable.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from src.graph.state import AgentState


def should_use_tools(state: AgentState) -> str:
    """Determine whether the agent should call tools or end the conversation.

    This is the conditional edge function used after the agent node.
    LangGraph's ``tools_condition`` is equivalent, but this version is
    explicit and independently unit-testable.

    Args:
        state: Current graph state.

    Returns:
        ``"tools"`` if the last AI message contains tool calls,
        ``"__end__"`` otherwise.
    """
    messages = state.get("messages", [])
    if not messages:
        return "__end__"

    last_message = messages[-1]
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        return "tools"
    return "__end__"


def route_after_router(state: AgentState) -> str:
    """Always route from router to agent node.

    Kept as a named function for future conditional routing (e.g., bypass
    agent for cached responses).

    Args:
        state: Current graph state.

    Returns:
        Always returns ``"agent"``.
    """
    return "agent"
