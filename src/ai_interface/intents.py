"""Typed Intent System for CDP_Merged Chatbot.

This module provides validated intent schemas that convert natural language queries
to deterministic execution paths, reducing reliance on LLM tool selection for
common query patterns.

Intents are:
- Validated Pydantic models (type safety)
- Deterministic (same input → same structured output)
- Executable (map directly to service layer calls)
- Observable (logged for audit/debugging)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from src.core.logger import get_logger

logger = get_logger(__name__)


class IntentType(str, Enum):
    """Canonical intent types for CDP queries."""

    COMPANY_SEARCH = "company_search"
    COMPANY_COUNT = "company_count"
    COMPANY_360 = "company_360"
    INDUSTRY_ANALYTICS = "industry_analytics"
    GEOGRAPHIC_DISTRIBUTION = "geographic_distribution"
    SEGMENT_CREATE = "segment_create"
    SEGMENT_LIST = "segment_list"
    SEGMENT_EXPORT = "segment_export"
    IDENTITY_LINK_QUALITY = "identity_link_quality"
    HELP = "help"
    UNKNOWN = "unknown"


class BaseIntent(BaseModel):
    """Base class for all intents."""

    intent_type: IntentType
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    original_query: str = Field(description="The user's original natural language query")

    model_config = {"frozen": True}  # Immutable for safety


class CompanySearchIntent(BaseIntent):
    """Intent to search for companies with filters."""

    intent_type: Literal[IntentType.COMPANY_SEARCH] = IntentType.COMPANY_SEARCH
    keyword: str | None = Field(None, description="Company name or keyword to search")
    city: str | None = Field(None, description="City filter")
    zip_code: str | None = Field(None, description="Postal code filter")
    nace_code: str | None = Field(None, description="NACE industry code")
    industry_keyword: str | None = Field(None, description="Industry keyword (e.g., 'software', 'restaurant')")
    juridical_form: str | None = Field(None, description="Legal form filter")
    status: str | None = Field(None, description="Company status (e.g., 'AC' for active)")
    limit: int = Field(100, ge=1, le=1000, description="Maximum results to return")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Normalize status codes
        v = v.upper().strip()
        valid_statuses = {"AC", "AN", "ST", "DF", "DI", "LC", "PL"}
        if v not in valid_statuses:
            logger.warning(f"Unusual status code: {v}")
        return v


class CompanyCountIntent(BaseIntent):
    """Intent to count companies matching criteria."""

    intent_type: Literal[IntentType.COMPANY_COUNT] = IntentType.COMPANY_COUNT
    keyword: str | None = Field(None, description="Company name or keyword")
    city: str | None = Field(None, description="City filter")
    zip_code: str | None = Field(None, description="Postal code filter")
    nace_code: str | None = Field(None, description="NACE industry code")
    industry_keyword: str | None = Field(None, description="Industry keyword")
    juridical_form: str | None = Field(None, description="Legal form filter")
    status: str | None = Field(None, description="Company status filter")


class Company360Intent(BaseIntent):
    """Intent to retrieve a complete 360° view of a company."""

    intent_type: Literal[IntentType.COMPANY_360] = IntentType.COMPANY_360
    enterprise_number: str | None = Field(None, description="KBO enterprise number")
    company_name: str | None = Field(None, description="Company name (for lookup)")

    @field_validator("enterprise_number")
    @classmethod
    def normalize_kbo(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Normalize KBO format: remove dots and whitespace
        return v.replace(".", "").replace(" ", "").strip()


class IndustryAnalyticsIntent(BaseIntent):
    """Intent to get industry-level analytics (pipeline, revenue)."""

    intent_type: Literal[IntentType.INDUSTRY_ANALYTICS] = IntentType.INDUSTRY_ANALYTICS
    industry: str | None = Field(None, description="Industry name or NACE code")
    city: str | None = Field(None, description="City filter")
    metric: Literal["pipeline", "revenue", "count", "all"] = Field("all", description="Metric to analyze")


class GeographicDistributionIntent(BaseIntent):
    """Intent to get geographic distribution of companies/revenue."""

    intent_type: Literal[IntentType.GEOGRAPHIC_DISTRIBUTION] = IntentType.GEOGRAPHIC_DISTRIBUTION
    city: str | None = Field(None, description="Specific city (optional)")
    metric: Literal["revenue", "count", "both"] = Field("count", description="Distribution metric")


class SegmentCreateIntent(BaseIntent):
    """Intent to create a segment from search criteria."""

    intent_type: Literal[IntentType.SEGMENT_CREATE] = IntentType.SEGMENT_CREATE
    name: str = Field(description="Segment name")
    description: str | None = Field(None, description="Segment description")
    # Filters mirror CompanySearchIntent
    keyword: str | None = Field(None, description="Company name or keyword filter")
    city: str | None = Field(None, description="City filter")
    nace_code: str | None = Field(None, description="NACE industry code")
    industry_keyword: str | None = Field(None, description="Industry keyword")


class SegmentListIntent(BaseIntent):
    """Intent to list existing segments."""

    intent_type: Literal[IntentType.SEGMENT_LIST] = IntentType.SEGMENT_LIST
    limit: int = Field(50, ge=1, le=200)


class SegmentExportIntent(BaseIntent):
    """Intent to export a segment to CSV or external platform."""

    intent_type: Literal[IntentType.SEGMENT_EXPORT] = IntentType.SEGMENT_EXPORT
    segment_id: str | None = Field(None, description="Segment identifier")
    segment_name: str | None = Field(None, description="Segment name (for lookup)")
    format: Literal["csv", "resend", "flexmail"] = Field("csv", description="Export format")


class IdentityLinkQualityIntent(BaseIntent):
    """Intent to check identity linking quality/match rates."""

    intent_type: Literal[IntentType.IDENTITY_LINK_QUALITY] = IntentType.IDENTITY_LINK_QUALITY
    source_system: Literal["teamleader", "exact", "autotask", "all"] = Field("all")


class HelpIntent(BaseIntent):
    """Intent to get help with the system."""

    intent_type: Literal[IntentType.HELP] = IntentType.HELP
    topic: str | None = Field(None, description="Specific help topic")


class UnknownIntent(BaseIntent):
    """Fallback intent when classification fails."""

    intent_type: Literal[IntentType.UNKNOWN] = IntentType.UNKNOWN
    reason: str = Field("Could not classify query", description="Why classification failed")


# Union type for all intents
AnyIntent = (
    CompanySearchIntent
    | CompanyCountIntent
    | Company360Intent
    | IndustryAnalyticsIntent
    | GeographicDistributionIntent
    | SegmentCreateIntent
    | SegmentListIntent
    | SegmentExportIntent
    | IdentityLinkQualityIntent
    | HelpIntent
    | UnknownIntent
)


class IntentClassificationResult(BaseModel):
    """Result of intent classification."""

    intent: AnyIntent
    processing_path: Literal["deterministic", "llm_fallback"] = Field(
        "deterministic",
        description="Whether this uses deterministic rules or LLM fallback",
    )
    execution_plan: list[str] = Field(default_factory=list, description="Planned execution steps")

    model_config = {"frozen": True}
