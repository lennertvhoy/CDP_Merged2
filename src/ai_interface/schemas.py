"""
Pydantic response schemas for AI tool outputs in CDP_Merged.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Result schema returned by the search_profiles tool."""

    total: int = Field(description="Total profiles matching the query")
    returned: int = Field(description="Number of profiles returned in this response")
    profiles: list[dict[str, Any]] = Field(default_factory=list, description="Profile summaries")
    query_tql: str = Field(default="", description="TQL query used")
    query_sql: str = Field(default="", description="SQL equivalent of the query")


class SegmentResult(BaseModel):
    """Result schema for segment creation."""

    id: str = Field(description="Segment identifier")
    name: str = Field(description="Human-readable segment name")
    condition: str = Field(description="TQL condition used")
    profiles_added: int = Field(description="Number of profiles added to the segment")
    success: bool = Field(default=True, description="Whether segment creation succeeded")


class FlexmailPushResult(BaseModel):
    """Result schema for Flexmail push operation."""

    segment_id: str = Field(description="Tracardi segment pushed")
    pushed_count: int = Field(description="Number of contacts pushed to Flexmail")
    interest_name: str = Field(default="", description="Flexmail interest targeted")
    success: bool = Field(default=True, description="Whether the push succeeded")


class ValidationResult(BaseModel):
    """Result schema from the query critic/validator."""

    valid: bool
    error: str = Field(default="", description="Error message if invalid")
    warning: str = Field(default="", description="Warning message")
    flags: list[str] = Field(default_factory=list, description="Security flags raised")
