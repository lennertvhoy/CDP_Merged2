"""
Graph State for CDP_Merged.
From CDPT - Simple state management for LangGraph.
"""

import operator
from collections.abc import Sequence
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """State for the agent graph."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    language: str
    profile_id: str
    last_search_tql: str | None
    last_search_params: dict | None
