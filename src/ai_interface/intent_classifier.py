"""Intent Classifier for CDP_Merged Chatbot.

Maps natural language queries to validated typed intents using:
1. Pattern matching for common query types (deterministic, fast)
2. LLM fallback for complex or ambiguous queries

Design principles:
- Common queries should be deterministic (no LLM latency/cost)
- Classification should be observable and auditable
- Confidence scores allow graceful degradation
"""

from __future__ import annotations

import re
from typing import Any

from src.ai_interface.intents import (
    AnyIntent,
    Company360Intent,
    CompanyCountIntent,
    CompanySearchIntent,
    GeographicDistributionIntent,
    HelpIntent,
    IdentityLinkQualityIntent,
    IndustryAnalyticsIntent,
    IntentClassificationResult,
    IntentType,
    SegmentCreateIntent,
    SegmentExportIntent,
    SegmentListIntent,
    UnknownIntent,
)
from src.core.logger import get_logger

logger = get_logger(__name__)


# Pattern-based classification rules
# Each rule: (pattern, intent_type, extractor_fn)
CLASSIFICATION_RULES: list[tuple[re.Pattern, IntentType, callable]] = []


def _compile_rules() -> None:
    """Compile regex patterns for classification."""
    global CLASSIFICATION_RULES

    # Count queries
    count_patterns = [
        r"how many (?:companies|businesses|firms)(?: are)? (?:in|from|at) ([a-zA-Z\s]+)",
        r"count (?:of )?(?:companies|businesses|firms)(?: in| from| at)? ([a-zA-Z\s]+)?",
        r"(?:number of|total) (?:companies|businesses|firms)(?: in| from| at)? ([a-zA-Z\s]+)?",
        r"(?:how many|count).*?(?:companies|businesses).*?(?:brussels|gent|antwerp|antwerpen|liege|namur)",
        r"(?:total number|total count) of (?:companies|businesses|firms)",
    ]

    for pattern in count_patterns:
        CLASSIFICATION_RULES.append(
            (re.compile(pattern, re.IGNORECASE), IntentType.COMPANY_COUNT, _extract_count_params)
        )

    # Search queries
    search_patterns = [
        r"(?:find|search|show|get|list) (?:me )?(?:all )?(?:companies|businesses|firms)(?: in| from| at)? ([a-zA-Z\s]+)?",
        r"(?:companies|businesses|firms) (?:in|from|at) ([a-zA-Z\s]+)",
        r"(?:software|restaurant|consulting|it) (?:companies|businesses|firms)(?: in| from| at)? ([a-zA-Z\s]+)?",
        r"^(?:software|restaurant|consulting|it|retail|healthcare) (?:companies|businesses|firms)$",
    ]

    for pattern in search_patterns:
        CLASSIFICATION_RULES.append(
            (re.compile(pattern, re.IGNORECASE), IntentType.COMPANY_SEARCH, _extract_search_params)
        )

    # 360 view queries
    view_patterns = [
        r"(?:360|full|complete|unified) view (?:of )?(?:company )?([0-9\.]*)",
        r"(?:tell me about|info on|details for|profile of) (?:company )?([0-9\.]+|[a-zA-Z][\w\s]+)",
        r"(?:kbo|enterprise number) ([0-9\.]+)",
    ]

    for pattern in view_patterns:
        CLASSIFICATION_RULES.append(
            (re.compile(pattern, re.IGNORECASE), IntentType.COMPANY_360, _extract_360_params)
        )

    # Industry analytics
    industry_patterns = [
        r"(?:pipeline|revenue).*?(?:industry|sector|nace)",
        r"(?:industry|sector).*?(?:pipeline|revenue|analytics)",
        r"(?:software|it|consulting|restaurant|retail).*?(?:pipeline|revenue|companies)",
        r"revenue for (?:software|it|consulting|restaurant|retail).*?companies",
        r"show me (?:the )?revenue for",
    ]

    for pattern in industry_patterns:
        CLASSIFICATION_RULES.append(
            (re.compile(pattern, re.IGNORECASE), IntentType.INDUSTRY_ANALYTICS, _extract_industry_params)
        )

    # Geographic distribution
    geo_patterns = [
        r"(?:revenue )?(?:distribution|by city|by location|geographic)",
        r"(?:companies|revenue) (?:in|by|across) (?:cities|locations|regions)",
        r"(?:where are|location of) (?:companies|revenue)",
    ]

    for pattern in geo_patterns:
        CLASSIFICATION_RULES.append(
            (re.compile(pattern, re.IGNORECASE), IntentType.GEOGRAPHIC_DISTRIBUTION, _extract_geo_params)
        )

    # Segment creation
    segment_create_patterns = [
        r"(?:create|make|build) (?:a )?(?:segment|list|audience)",
        r"save (?:this )?(?:search|filter|query) (?:as|to) (?:a )?segment",
    ]

    for pattern in segment_create_patterns:
        CLASSIFICATION_RULES.append(
            (re.compile(pattern, re.IGNORECASE), IntentType.SEGMENT_CREATE, _extract_segment_create_params)
        )

    # Segment list
    segment_list_patterns = [
        r"(?:list|show|get|view) (?:my |all )?(?:segments|audiences|lists)",
        r"(?:what|which) segments (?:do i have|exist|are there)",
    ]

    for pattern in segment_list_patterns:
        CLASSIFICATION_RULES.append(
            (re.compile(pattern, re.IGNORECASE), IntentType.SEGMENT_LIST, _extract_segment_list_params)
        )

    # Identity link quality
    link_patterns = [
        r"(?:kbo |identity )?(?:link|match|connection) (?:quality|rate|status)",
        r"how well.*?(?:linked|matched|connected).*?(?:kbo|sources)",
        r"(?:match rate|linkage quality|identity resolution)",
    ]

    for pattern in link_patterns:
        CLASSIFICATION_RULES.append(
            (re.compile(pattern, re.IGNORECASE), IntentType.IDENTITY_LINK_QUALITY, _extract_link_quality_params)
        )

    # Help
    help_patterns = [
        r"^(?:help|what can you do|how do i|instructions|guide)$",
        r"(?:help|assist).*?(?:me )?(?:with|using|understand)",
    ]

    for pattern in help_patterns:
        CLASSIFICATION_RULES.append(
            (re.compile(pattern, re.IGNORECASE), IntentType.HELP, _extract_help_params)
        )


def _extract_city(query: str) -> str | None:
    """Extract city name from query."""
    # Common Belgian cities
    cities = [
        "brussels", "bruxelles", "gent", "ghent", "antwerp", "antwerpen", "anvers",
        "liege", "luik", "namur", "namen", "leuven", "louvain", "brugge", "bruges",
        "hasselt", "mechelen", "malines", "kortrijk", "courtrai", "oostende",
    ]
    query_lower = query.lower()
    for city in cities:
        if city in query_lower:
            # Return canonical name
            canonical = {
                "bruxelles": "brussels",
                "ghent": "gent",
                "antwerpen": "antwerp",
                "anvers": "antwerp",
                "luik": "liege",
                "namen": "namur",
                "louvain": "leuven",
                "bruges": "brugge",
                "malines": "mechelen",
                "courtrai": "kortrijk",
            }
            return canonical.get(city, city)
    return None


def _extract_industry_keyword(query: str) -> str | None:
    """Extract industry keyword from query."""
    industries = [
        "software", "it", "consulting", "restaurant", "cafe", "construction",
        "retail", "healthcare", "finance", "insurance", "manufacturing",
        "transport", "logistics", "education", "legal", "accounting",
    ]
    query_lower = query.lower()
    for industry in industries:
        if industry in query_lower:
            return industry
    return None


def _extract_count_params(query: str, match: re.Match) -> dict[str, Any]:
    """Extract parameters for count intent."""
    city = _extract_city(query)
    industry = _extract_industry_keyword(query)

    params: dict[str, Any] = {"original_query": query}
    if city:
        params["city"] = city
    if industry:
        params["industry_keyword"] = industry

    return params


def _extract_search_params(query: str, match: re.Match) -> dict[str, Any]:
    """Extract parameters for search intent."""
    city = _extract_city(query)
    industry = _extract_industry_keyword(query)

    params: dict[str, Any] = {"original_query": query, "limit": 100}
    if city:
        params["city"] = city
    if industry:
        params["industry_keyword"] = industry

    return params


def _extract_360_params(query: str, match: re.Match) -> dict[str, Any]:
    """Extract parameters for 360 view intent."""
    params: dict[str, Any] = {"original_query": query}

    # Check for KBO number pattern
    kbo_match = re.search(r"(\d{4}\.?\d{3}\.?\d{3})", query.replace(" ", ""))
    if kbo_match:
        params["enterprise_number"] = kbo_match.group(1)
    else:
        # Try to extract company name (anything after certain keywords)
        name_match = re.search(r"(?:about|for|of) ([a-zA-Z][\w\s&]+?)(?:\?|$)", query, re.IGNORECASE)
        if name_match:
            params["company_name"] = name_match.group(1).strip()

    return params


def _extract_industry_params(query: str, match: re.Match) -> dict[str, Any]:
    """Extract parameters for industry analytics intent."""
    city = _extract_city(query)
    industry = _extract_industry_keyword(query)

    params: dict[str, Any] = {"original_query": query, "metric": "all"}
    if city:
        params["city"] = city
    if industry:
        params["industry"] = industry

    # Determine metric from query
    query_lower = query.lower()
    if "pipeline" in query_lower and "revenue" not in query_lower:
        params["metric"] = "pipeline"
    elif "revenue" in query_lower and "pipeline" not in query_lower:
        params["metric"] = "revenue"
    elif "count" in query_lower or "number" in query_lower:
        params["metric"] = "count"

    return params


def _extract_geo_params(query: str, match: re.Match) -> dict[str, Any]:
    """Extract parameters for geographic distribution intent."""
    city = _extract_city(query)

    params: dict[str, Any] = {"original_query": query, "metric": "count"}
    if city:
        params["city"] = city

    # Determine metric
    query_lower = query.lower()
    if "revenue" in query_lower:
        params["metric"] = "revenue" if "count" not in query_lower else "both"

    return params


def _extract_segment_create_params(query: str, match: re.Match) -> dict[str, Any]:
    """Extract parameters for segment creation intent."""
    params: dict[str, Any] = {"original_query": query, "name": "Untitled Segment"}

    # Try to extract a name from the query
    name_match = re.search(r'"([^"]+)"', query)
    if name_match:
        params["name"] = name_match.group(1)

    # Extract filters
    city = _extract_city(query)
    industry = _extract_industry_keyword(query)
    if city:
        params["city"] = city
    if industry:
        params["industry_keyword"] = industry

    return params


def _extract_segment_list_params(query: str, match: re.Match) -> dict[str, Any]:
    """Extract parameters for segment list intent."""
    return {"original_query": query, "limit": 50}


def _extract_segment_export_params(query: str, match: re.Match) -> dict[str, Any]:
    """Extract parameters for segment export intent."""
    params: dict[str, Any] = {"original_query": query, "format": "csv"}

    # Determine format
    query_lower = query.lower()
    if "resend" in query_lower:
        params["format"] = "resend"
    elif "flexmail" in query_lower:
        params["format"] = "flexmail"

    # Try to extract segment name
    name_match = re.search(r'"([^"]+)"', query)
    if name_match:
        params["segment_name"] = name_match.group(1)

    return params


def _extract_link_quality_params(query: str, match: re.Match) -> dict[str, Any]:
    """Extract parameters for identity link quality intent."""
    params: dict[str, Any] = {"original_query": query, "source_system": "all"}

    # Determine source system
    query_lower = query.lower()
    if "teamleader" in query_lower:
        params["source_system"] = "teamleader"
    elif "exact" in query_lower:
        params["source_system"] = "exact"
    elif "autotask" in query_lower:
        params["source_system"] = "autotask"

    return params


def _extract_help_params(query: str, match: re.Match) -> dict[str, Any]:
    """Extract parameters for help intent."""
    params: dict[str, Any] = {"original_query": query}

    # Try to extract topic
    topic_match = re.search(r"(?:with|about|using|understand) ([\w\s]+)", query, re.IGNORECASE)
    if topic_match:
        params["topic"] = topic_match.group(1).strip()

    return params


def classify_intent(query: str) -> IntentClassificationResult:
    """Classify a natural language query into a typed intent.

    Uses pattern matching first (deterministic), with LLM fallback for complex cases.

    Args:
        query: The user's natural language query

    Returns:
        IntentClassificationResult with validated intent and execution plan
    """
    query = query.strip()
    if not query:
        return IntentClassificationResult(
            intent=UnknownIntent(original_query=query, reason="Empty query"),
            processing_path="deterministic",
            execution_plan=["ask_for_clarification"],
        )

    # Try pattern matching first
    for pattern, intent_type, extractor in CLASSIFICATION_RULES:
        match = pattern.search(query)
        if match:
            try:
                params = extractor(query, match)
                intent = _create_intent(intent_type, params)
                plan = _build_execution_plan(intent)

                logger.info(
                    f"Intent classified (deterministic): {intent_type.value} "
                    f"for query: {query[:50]}..."
                )

                return IntentClassificationResult(
                    intent=intent,
                    processing_path="deterministic",
                    execution_plan=plan,
                )
            except Exception as e:
                logger.warning(f"Pattern match succeeded but extraction failed: {e}")
                continue

    # No pattern matched - return unknown intent
    # In future, this is where LLM fallback would go
    logger.info(f"No pattern match for query: {query[:50]}...")

    return IntentClassificationResult(
        intent=UnknownIntent(
            original_query=query,
            reason="No matching pattern found",
        ),
        processing_path="llm_fallback",
        execution_plan=["use_llm_tool_selection"],
    )


def _create_intent(intent_type: IntentType, params: dict[str, Any]) -> AnyIntent:
    """Create the appropriate intent object from extracted parameters."""
    match intent_type:
        case IntentType.COMPANY_COUNT:
            return CompanyCountIntent(**params)
        case IntentType.COMPANY_SEARCH:
            return CompanySearchIntent(**params)
        case IntentType.COMPANY_360:
            return Company360Intent(**params)
        case IntentType.INDUSTRY_ANALYTICS:
            return IndustryAnalyticsIntent(**params)
        case IntentType.GEOGRAPHIC_DISTRIBUTION:
            return GeographicDistributionIntent(**params)
        case IntentType.SEGMENT_CREATE:
            return SegmentCreateIntent(**params)
        case IntentType.SEGMENT_LIST:
            return SegmentListIntent(**params)
        case IntentType.SEGMENT_EXPORT:
            return SegmentExportIntent(**params)
        case IntentType.IDENTITY_LINK_QUALITY:
            return IdentityLinkQualityIntent(**params)
        case IntentType.HELP:
            return HelpIntent(**params)
        case _:
            return UnknownIntent(original_query=params.get("original_query", ""))


def _build_execution_plan(intent: AnyIntent) -> list[str]:
    """Build an execution plan for the intent."""
    match intent.intent_type:
        case IntentType.COMPANY_COUNT:
            return ["search_postgresql", "count_results", "format_response"]
        case IntentType.COMPANY_SEARCH:
            return ["search_postgresql", "format_results"]
        case IntentType.COMPANY_360:
            if intent.enterprise_number:
                return ["lookup_by_kbo", "fetch_360_view", "format_response"]
            else:
                return ["search_by_name", "fetch_360_view", "format_response"]
        case IntentType.INDUSTRY_ANALYTICS:
            return ["query_industry_summary", "format_response"]
        case IntentType.GEOGRAPHIC_DISTRIBUTION:
            return ["query_geo_distribution", "format_response"]
        case IntentType.SEGMENT_CREATE:
            return ["validate_filters", "create_segment", "return_segment_id"]
        case IntentType.SEGMENT_LIST:
            return ["query_segments", "format_list"]
        case IntentType.SEGMENT_EXPORT:
            return ["lookup_segment", "export_data", "return_result"]
        case IntentType.IDENTITY_LINK_QUALITY:
            return ["query_link_stats", "format_response"]
        case IntentType.HELP:
            return ["return_help_text"]
        case _:
            return ["use_llm_tool_selection"]


# Compile rules on module load
_compile_rules()
