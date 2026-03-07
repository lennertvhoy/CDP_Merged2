"""
LangGraph Workflow for CDP_Merged.
Enhanced with Critic layer for tool call validation.
HITL for bulk operations is handled at the tool level.
"""

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from src.graph.nodes import agent_node, critic_node, router_node, tools_node
from src.graph.state import AgentState


def _route_after_agent(state: AgentState) -> str:
    """Route to critic after agent generates a response."""
    messages = state.get("messages", [])
    if not messages:
        return END

    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        return "critic"
    return END


def _route_after_critic(state: AgentState) -> str:
    """Route to tools if critic approved, or back to agent if rejected.

    The critic approves by returning an empty dict (no changes).
    The critic rejects by returning a feedback message.
    """
    messages = state.get("messages", [])
    if not messages:
        return "agent"

    last_message = messages[-1]

    # If the last message is an AI message with content but NO tool_calls,
    # it means the critic rejected and provided feedback.
    if isinstance(last_message, AIMessage):
        # If the message has content (feedback) and no tool_calls, critic rejected
        if getattr(last_message, "content", None) and not getattr(
            last_message, "tool_calls", None
        ):
            return "agent"  # Send feedback back to agent

        # If the message has tool_calls, critic approved (state unchanged)
        if getattr(last_message, "tool_calls", None):
            return "tools"

    return "agent"


def create_graph():
    """Constructs the LangGraph state machine with Critic layer."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("router", router_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("tools", tools_node)

    # Add edges
    workflow.add_edge(START, "router")
    workflow.add_edge("router", "agent")

    # Conditional edge: If agent requests tool -> critic, else -> END
    workflow.add_conditional_edges(
        "agent",
        _route_after_agent,
        {
            "critic": "critic",
            END: END,
        },
    )

    # Conditional edge: If critic approves -> tools, if rejects -> agent
    workflow.add_conditional_edges(
        "critic",
        _route_after_critic,
        {
            "tools": "tools",
            "agent": "agent",
        },
    )

    # From tools, go back to agent
    workflow.add_edge("tools", "agent")

    return workflow


def compile_workflow(checkpointer=None, interrupt_before: list[str] | None = None):
    """Compiles the graph with an optional checkpointer and HITL interrupts.

    Args:
        checkpointer: Optional checkpointer for persistence.
        interrupt_before: List of node names to interrupt before.
                         Use ["tools"] to enable HITL for all tool calls.
    """
    graph = create_graph()
    return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt_before or [])
