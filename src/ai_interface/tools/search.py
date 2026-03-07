"""Profile Search Tools - PostgreSQL-First Query Plane.

This module provides tools for searching and aggregating company data in the CDP.
PostgreSQL is the authoritative source for search, counts, analytics, and canonical
segment membership. Tracardi remains an operational runtime layer.

SEGMENT CREATION NOTE:
The segment creation flow relies on a persistent checkpointer (SQLite/Postgres)
to maintain last_search_tql across separate graph invocations. The default
MemorySaver does NOT persist state across separate astream_events calls.

Flow:
1. search_profiles returns results with TQL
2. tools_node extracts TQL and stores in state.last_search_tql
3. Persistent checkpointer saves state to SQLite
4. User asks to create segment (separate graph invocation)
5. checkpointer restores state including last_search_tql
6. tools_node injects stored TQL into create_segment arguments
7. create_segment uses the TQL, ensuring segment count matches search count
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from langchain_core.tools import tool

from src.ai_interface.tools.nace_resolver import (
    JURIDICAL_CODES,
    _get_nace_codes_from_keyword,
)
from src.config import settings
from src.core.logger import get_logger
from src.retrieval.azure_retriever import AzureSearchRetriever
from src.search_engine.factory import QueryFactory
from src.search_engine.schema import ProfileSearchParams
from src.services.postgresql_search import (
    CompanySearchFilters,
    get_search_service,
)
from src.services.canonical_segments import CanonicalSegmentService
from src.services.tracardi import TracardiClient

logger = get_logger(__name__)

CONVERSATIONAL_FOLLOWUP_TOKENS = {
    "again",
    "another",
    "be",
    "else",
    "few",
    "just",
    "many",
    "maybe",
    "more",
    "must",
    "perhaps",
    "please",
    "show",
    "some",
    "surely",
    "there",
}

DEFAULT_SAMPLE_LIMIT = 100
BROAD_QUERY_SAMPLE_LIMIT = 10


def _looks_like_conversational_followup(keyword: str | None) -> bool:
    if not keyword:
        return False
    tokens = re.findall(r"[a-z0-9]+", keyword.lower())
    return bool(tokens) and all(token in CONVERSATIONAL_FOLLOWUP_TOKENS for token in tokens)


def _validate_profile_match(profile: dict[str, Any], keyword: str | None) -> bool:
    """Validate that a profile actually matches the keyword using word boundaries.

    This filters out false positives from substring matching.
    """
    if not keyword:
        return True

    keyword_lower = keyword.lower().strip()
    if not keyword_lower:
        return True

    # Get name from PostgreSQL format or Tracardi format
    name = (profile.get("company_name") or "").lower()
    if not name:
        # Fallback to Tracardi format for backward compatibility
        traits = profile.get("traits") or {}
        name = (traits.get("name") or traits.get("kbo_name") or "").lower()

    # Word boundary regex - match as whole word or at word boundaries
    pattern = rf"\b{re.escape(keyword_lower)}\b"

    # Also check for common variations (plural, etc.)
    variations = {keyword_lower}
    if not keyword_lower.endswith("s"):
        variations.add(keyword_lower + "s")
    if keyword_lower.endswith("s"):
        variations.add(keyword_lower[:-1])

    # Check if any variation matches as whole word
    for variant in variations:
        pattern = rf"\b{re.escape(variant)}\b"
        if re.search(pattern, name):
            return True

    # Special case: allow substring match if keyword is at start of word
    if re.search(rf"\b{re.escape(keyword_lower)}", name):
        return True

    return False


def _filter_false_positives(
    profiles: list[dict[str, Any]], keyword: str | None, nace_codes: list[str] | None = None
) -> list[dict[str, Any]]:
    """Filter out false positives from search results."""
    if not keyword:
        return profiles

    keyword_lower = keyword.lower().strip()

    # For very short keywords (< 4 chars), be more permissive
    if len(keyword_lower) < 4:
        return profiles

    filtered = []
    for profile in profiles:
        # Check word boundaries
        if _validate_profile_match(profile, keyword):
            filtered.append(profile)
            continue

        # If NACE codes are specified, check if profile has matching NACE
        if nace_codes:
            # PostgreSQL format
            profile_nace = profile.get("industry_nace_code")
            # Tracardi format fallback
            if not profile_nace:
                traits = profile.get("traits") or {}
                profile_nace = traits.get("nace_code")
            if profile_nace:
                if isinstance(profile_nace, list):
                    if any(str(nc) in [str(c) for c in nace_codes] for nc in profile_nace):
                        filtered.append(profile)
                        continue
                elif str(profile_nace) in [str(c) for c in nace_codes]:
                    filtered.append(profile)
                    continue

    return filtered


def _build_recoverable_search_error_payload(
    *,
    error_message: str,
    backend: str,
    tql_query: str,
    sql_query: str,
    status_code: int | None = None,
    search_strategy: str | None = None,
    lexical_fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retryable = status_code is None or status_code >= 500
    return {
        "status": "error",
        "tool_contract": "search_profiles.v2",
        "error_type": "search_backend_failure",
        "error": error_message,
        "recoverable": True,
        "retryable": retryable,
        "degraded": True,
        "orchestration": {
            "can_continue": True,
            "state_safe": True,
            "next_action": "retry_or_broaden_search",
        },
        "ux": {
            "message_key": "search.recoverable_failure",
            "retry_hint": "Search is temporarily unavailable. Retry shortly or try broader filters.",
            "degraded_hint": "Results are unavailable for this turn; no authoritative zero count was assumed.",
        },
        "backend": backend,
        "search_strategy": search_strategy,
        "query": {"tql": tql_query, "sql": sql_query},
        "lexical_fallback": lexical_fallback
        or {
            "attempted": False,
            "used": None,
            "operator": None,
            "reason": None,
        },
    }


def _build_azure_query_text(
    original_keyword: str | None,
    city: str | None,
    zip_code: str | None,
    nace_codes: list[str] | None,
    juridical_codes: list[str] | None,
    email_domain: str | None = None,
) -> str:
    """Build a best-effort keyword query for Azure AI Search."""
    tokens: list[str] = []
    if original_keyword:
        tokens.append(original_keyword)
    if city:
        tokens.append(city)
    if zip_code:
        tokens.append(zip_code)
    if nace_codes:
        tokens.extend(nace_codes)
    if juridical_codes:
        tokens.extend(juridical_codes)
    if email_domain:
        tokens.append(email_domain)
    return " ".join(t for t in tokens if t).strip() or "*"


def _normalize_email_domain(email_domain: str | None) -> str | None:
    if not email_domain:
        return None

    normalized = email_domain.strip().lower()
    if normalized.startswith("@"):
        normalized = normalized[1:]
    if "@" in normalized:
        normalized = normalized.split("@", 1)[1]
    return normalized or None


@tool(args_schema=ProfileSearchParams)
async def search_profiles(
    keywords: str | None = None,
    enterprise_number: str | None = None,
    nace_codes: list[str] | None = None,
    nace_code: str | None = None,
    juridical_codes: list[str] | None = None,
    juridical_keyword: str | None = None,
    city: str | None = None,
    zip_code: str | None = None,
    status: str | None = None,
    min_start_date: str | None = None,
    has_phone: bool | None = False,
    has_email: bool | None = None,
    email_domain: str | None = None,
) -> str:
    """Search for companies in the CDP using PostgreSQL as the authoritative source.

    You can provide EITHER 'nace_codes' (if you know them) OR 'keywords'
    (to search by industry name like 'Restaurant').

    Args:
        keywords: Industry keyword; auto-resolved to NACE codes.
        enterprise_number: KBO enterprise number.
        nace_codes: List of NACE activity codes.
        nace_code: Single NACE code convenience alias.
        juridical_codes: List of juridical form codes.
        juridical_keyword: Optional keyword for Juridical Forms.
        city: City name.
        zip_code: Postal code.
        status: Optional company status, for example ``AC`` for active.
        min_start_date: ISO date string (YYYY-MM-DD).
        has_phone: Filter to companies with phone number.
        has_email: Filter to companies with email.
        email_domain: Optional email-domain filter, for example ``gmail.com``.

    Returns:
        JSON string with:
        - authoritative total count from PostgreSQL
        - returned sample row count
        - sample rows
        - applied filters and query metadata
    """
    original_keyword = keywords
    normalized_email_domain = _normalize_email_domain(email_domain)
    if nace_code and not nace_codes:
        nace_codes = [nace_code.strip()]
    resolution_mode = "activity_nace_codes" if nace_codes else "none"
    resolved_codes: list[str] = list(nace_codes or [])

    # NOTE: We intentionally do NOT clear keywords when nace_codes are resolved.
    # The original keyword is needed for name-based filtering
    search_keyword_for_tql = None if nace_codes else keywords

    if juridical_keyword and not juridical_codes:
        found_j_codes = [
            code
            for code, desc in JURIDICAL_CODES.items()
            if juridical_keyword.lower() in desc.lower()
        ]
        if found_j_codes:
            juridical_codes = found_j_codes
            logger.info("juridical_auto_resolved", keyword=juridical_keyword, codes=found_j_codes)

    # Auto-resolve category keywords to NACE activity codes first.
    if keywords and not nace_codes:
        if _looks_like_conversational_followup(keywords):
            resolution_mode = "name_lexical_fallback"
        else:
            found_codes = _get_nace_codes_from_keyword(keywords)
            if found_codes:
                logger.info("nace_auto_resolved", keyword=keywords, codes=found_codes)
                nace_codes = found_codes
                resolved_codes = found_codes
                resolution_mode = "activity_nace_codes"
                search_keyword_for_tql = None
            else:
                resolution_mode = "name_lexical_fallback"

    has_structured_filters = any(
        [
            search_keyword_for_tql,
            enterprise_number,
            nace_codes,
            juridical_codes,
            city,
            zip_code,
            min_start_date,
            bool(has_phone),
            bool(has_email),
            normalized_email_domain,
        ]
    )
    sample_limit = DEFAULT_SAMPLE_LIMIT if has_structured_filters else BROAD_QUERY_SAMPLE_LIMIT

    # Build search parameters
    pg_filters = CompanySearchFilters(
        keywords=search_keyword_for_tql,
        enterprise_number=enterprise_number,
        nace_codes=nace_codes,
        juridical_codes=juridical_codes,
        city=city,
        zip_code=zip_code,
        status=status,
        min_start_date=min_start_date,
        has_phone=has_phone,
        has_email=has_email,
        email_domain=normalized_email_domain,
        limit=sample_limit,
        offset=0,
    )

    # Also build TQL for segment creation compatibility
    params = ProfileSearchParams(
        keywords=search_keyword_for_tql,
        enterprise_number=enterprise_number,
        nace_codes=nace_codes,
        juridical_codes=juridical_codes,
        juridical_keyword=juridical_keyword,
        city=city,
        zip_code=zip_code,
        status=status,
        min_start_date=min_start_date,
        has_phone=has_phone,
        has_email=has_email,
        email_domain=normalized_email_domain,
    )
    queries = QueryFactory.generate_all(params)
    tql_query = queries.get("tql", "")

    azure_query_text = _build_azure_query_text(
        original_keyword,
        city,
        zip_code,
        nace_codes,
        juridical_codes,
        normalized_email_domain,
    )
    azure_retriever = AzureSearchRetriever()

    azure_primary_enabled = settings.ENABLE_AZURE_SEARCH_RETRIEVAL
    azure_shadow_enabled = settings.ENABLE_AZURE_SEARCH_SHADOW_MODE

    async def _fetch_azure() -> dict[str, Any] | None:
        if azure_primary_enabled or azure_shadow_enabled:
            return await azure_retriever.retrieve(query_text=azure_query_text)
        return None

    # PRIMARY: PostgreSQL search
    search_service = get_search_service()

    async def _fetch_postgresql() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        try:
            result = await search_service.search_companies(pg_filters)
            return result, None
        except Exception as exc:
            # Capture full error details for debugging
            error_msg = str(exc) or repr(exc) or "Unknown error"
            error_type = type(exc).__name__
            error_repr_str = repr(exc)

            logger.error(
                "postgresql_search_failed",
                error=error_msg,
                error_type=error_type,
                error_repr=error_repr_str,
                filters=vars(pg_filters),
                resolution_mode=resolution_mode,
                tql_query=tql_query,
                azure_query_text=azure_query_text,
            )

            # Attempt to reset connection for future calls
            try:
                from src.services.postgresql_search import close_search_service

                await close_search_service()
                logger.info("postgresql_search_reset_after_error", error_type=error_type)
            except Exception as reset_exc:
                logger.warning(
                    "postgresql_search_reset_failed",
                    reset_error=str(reset_exc),
                    original_error_type=error_type,
                )

            err_payload = _build_recoverable_search_error_payload(
                error_message=f"PostgreSQL search failed ({error_type}): {error_msg}",
                backend="postgresql",
                tql_query=tql_query,
                sql_query="",  # SQL is internal to search service
                search_strategy=resolution_mode,
            )
            return None, err_payload

    # Execute searches concurrently
    azure_result, (pg_result, pg_error_payload) = await asyncio.gather(
        _fetch_azure(), _fetch_postgresql()
    )

    if pg_error_payload:
        return json.dumps(pg_error_payload, ensure_ascii=False)

    if not isinstance(pg_result, dict):
        payload = _build_recoverable_search_error_payload(
            error_message="PostgreSQL returned malformed response.",
            backend="postgresql",
            tql_query=tql_query,
            sql_query="",
            search_strategy=resolution_mode,
        )
        return json.dumps(payload, ensure_ascii=False)

    profiles: list[dict[str, Any]] = pg_result.get("result", []) or []
    total_count: int = int(pg_result.get("total", 0) or 0)
    count_is_estimated = bool(pg_result.get("count_is_estimated", False))
    count_source = str(pg_result.get("count_source") or "exact_count")
    companies_table_empty = bool(pg_result.get("companies_table_empty", False))
    lexical_fallback: dict[str, Any] = {
        "attempted": False,
        "used": None,
        "operator": None,
        "reason": None,
    }

    # If NACE resolution returns zero, retry with lexical company-name matching.
    if total_count == 0 and original_keyword and resolved_codes:
        lexical_fallback = {
            "attempted": True,
            "used": None,
            "operator": "ILIKE",
            "reason": "nace_zero_results",
        }
        fallback_filters = CompanySearchFilters(
            keywords=original_keyword,
            enterprise_number=enterprise_number,
            nace_codes=None,
            juridical_codes=juridical_codes,
            city=city,
            zip_code=zip_code,
            status=status,
            min_start_date=min_start_date,
            has_phone=has_phone,
            has_email=has_email,
            email_domain=normalized_email_domain,
            limit=sample_limit,
            offset=0,
        )
        try:
            fallback_result = await search_service.search_companies(fallback_filters)
            fallback_total = int(fallback_result.get("total", 0) or 0)
            if fallback_total > 0:
                profiles = fallback_result.get("result", []) or []
                total_count = fallback_total
                count_is_estimated = bool(fallback_result.get("count_is_estimated", False))
                count_source = str(fallback_result.get("count_source") or "exact_count")
                resolution_mode = "nace_then_name_lexical_fallback"
                lexical_fallback["used"] = "company_name_ILIKE"
                lexical_fallback["fallback_total"] = fallback_total
                logger.info(
                    "lexical_fallback_used_after_nace_zero_results",
                    keyword=original_keyword,
                    fallback_total=fallback_total,
                )
            else:
                lexical_fallback["reason"] = "nace_zero_results_and_keyword_zero_results"
        except Exception as fallback_exc:
            lexical_fallback["reason"] = f"fallback_failed:{type(fallback_exc).__name__}"
            logger.warning(
                "lexical_fallback_failed",
                keyword=original_keyword,
                error=str(fallback_exc),
            )

    # FILTER FALSE POSITIVES from substring matching
    if original_keyword:
        filtered_profiles = _filter_false_positives(profiles, original_keyword, nace_codes)
        if len(filtered_profiles) < len(profiles):
            logger.info(
                "filtered_false_positives",
                keyword=original_keyword,
                original_count=len(profiles),
                filtered_count=len(filtered_profiles),
            )
        profiles = filtered_profiles

    returned_count = len(profiles)
    profile_samples: list[dict[str, Any]] = []

    # Calculate data quality metrics
    total_fields = 0
    filled_fields = 0
    email_count = 0
    phone_count = 0

    for p in profiles:
        # Check contact fields
        profile_has_email = bool(p.get("main_email"))
        profile_has_phone = bool(p.get("main_phone"))

        if profile_has_email:
            email_count += 1
        if profile_has_phone:
            phone_count += 1

        # Calculate completeness for data quality score
        fields_to_check = [
            "company_name",
            "city",
            "main_email",
            "main_phone",
            "website_url",
            "industry_nace_code",
        ]
        for field in fields_to_check:
            total_fields += 1
            if p.get(field):
                filled_fields += 1

        profile_samples.append(
            {
                "name": p.get("company_name") or "[No Name]",
                "city": p.get("city") or "Unknown",
                "status": p.get("status") or p.get("sync_status") or "Unknown",
                "has_email": profile_has_email,
                "has_phone": profile_has_phone,
                "kbo_number": p.get("kbo_number"),
            }
        )

    # Calculate data quality scores
    data_quality_score = round((filled_fields / total_fields) * 100, 1) if total_fields > 0 else 0
    email_coverage = round((email_count / returned_count) * 100, 1) if returned_count > 0 else 0
    phone_coverage = round((phone_count / returned_count) * 100, 1) if returned_count > 0 else 0

    used_keyword_fallback = bool(keywords) and (
        not bool(nace_codes) or bool(lexical_fallback.get("used"))
    )

    # Calculate validation metrics
    validation_info = {}
    if original_keyword and resolution_mode in {
        "name_lexical_fallback",
        "nace_then_name_lexical_fallback",
    }:
        validation_info = {
            "validation_applied": True,
            "validation_type": "word_boundary_filter",
            "original_keyword": original_keyword,
            "filtered_sample_count": returned_count,
        }

    count_guidance = "Use counts.authoritative_total for 'how many' answers."
    if count_is_estimated:
        count_guidance = (
            "counts.authoritative_total is an estimated total for this turn because "
            "the exact count timed out."
        )

    dataset_guidance = ""
    next_steps_suggestions = [
        f"Create a segment from these {total_count} results?",
        "Push these contacts to Resend for an email campaign?",
        "Show analytics breakdown (by city, juridical form, etc.)?",
        "Search for similar companies in other cities?",
    ]
    if companies_table_empty:
        dataset_guidance = (
            " The companies table is currently empty in this environment. Treat a zero result as "
            "missing local data, not as market truth."
        )
        next_steps_suggestions = [
            "Load or import company data before relying on this count.",
            "Verify DATABASE_URL points to the populated PostgreSQL instance you expect.",
            "Retry once the dataset is loaded, or point the chatbot at production data.",
        ]
    elif total_count == 0:
        next_steps_suggestions = [
            "Broaden the search by removing filters or using nearby cities.",
            "Try an alternate city spelling or language variant.",
            "If you want only active companies, ask explicitly for active companies.",
        ]

    payload = {
        "status": "ok",
        "tool_contract": "search_profiles.v2",
        "retrieval_backend": "postgresql",
        "search_strategy": resolution_mode,
        "used_keyword_fallback": used_keyword_fallback,
        "keyword": original_keyword,
        "resolved_nace_codes": resolved_codes,
        "validation": validation_info,
        "applied_filters": {
            "keywords": original_keyword if used_keyword_fallback else None,
            "city": city,
            "zip_code": zip_code,
            "status": status,
            "nace_codes": nace_codes or [],
            "juridical_codes": juridical_codes or [],
            "min_start_date": min_start_date,
            "has_phone": bool(has_phone),
            "has_email": bool(has_email),
            "email_domain": normalized_email_domain,
        },
        "counts": {
            "authoritative_total": total_count,
            "total_matches": total_count,
            "returned_samples": returned_count,
            "count_is_estimated": count_is_estimated,
            "count_source": count_source,
        },
        "dataset_state": {
            "companies_table_empty": companies_table_empty,
            "zero_result_reason": (
                "empty_dataset"
                if companies_table_empty
                else ("no_matching_rows" if total_count == 0 else None)
            ),
        },
        "data_quality": {
            "completeness_score_percent": data_quality_score,
            "email_coverage_percent": email_coverage,
            "phone_coverage_percent": phone_coverage,
            "profiles_with_email": email_count,
            "profiles_with_phone": phone_count,
        },
        "query": {"tql": tql_query, "sql": "internal"},
        "lexical_fallback": lexical_fallback,
        "profiles_sample": profile_samples,
        "next_steps_suggestions": next_steps_suggestions,
        "guidance": (
            f"{count_guidance}{dataset_guidance} "
            "profiles_sample is only a sample and must never be added across turns. "
            "To create a segment, simply call create_segment(name='My Segment')."
        ),
    }

    # Store this search for potential segment creation
    logger.info(
        "search_profiles_complete",
        tql=tql_query[:100] if tql_query else "",
        total_count=total_count,
        backend="postgresql",
        message="TQL will be captured by tools_node and stored in AgentState for segment creation",
    )

    if azure_shadow_enabled and azure_result is not None:
        payload["shadow_retrieval"] = {
            "enabled": True,
            "backend": "azure_ai_search",
            "counts": {
                "authoritative_total": int(azure_result.get("total", 0) or 0),
                "returned_samples": int(azure_result.get("returned", 0) or 0),
            },
            "citations": azure_result.get("citations", []),
        }

    return json.dumps(payload, ensure_ascii=False)


@tool
async def create_segment(
    name: str,
    condition: str | None = None,
    keywords: str | None = None,
    city: str | None = None,
    zip_code: str | None = None,
    status: str | None = None,
    nace_codes: list[str] | None = None,
    juridical_codes: list[str] | None = None,
    min_start_date: str | None = None,
    has_phone: bool | None = None,
    has_email: bool | None = None,
    email_domain: str | None = None,
    use_last_search: bool = True,
) -> str:
    """Create a named canonical segment from search criteria.

    This tool writes the canonical segment definition and membership to PostgreSQL first.
    When the exact last search context is available, the segment member count matches the
    authoritative PostgreSQL search results for that search.

    Args:
        name: Segment name.
        use_last_search: When True (default), uses TQL from previous search.
        condition: Raw TQL condition (used if use_last_search=False or no stored search).
        keywords: Industry keyword (only used if condition not provided).
        city: City name (only used if condition not provided).
        zip_code: Postal code filter.
        status: Company status (only used if condition not provided).
        nace_codes: Optional list of NACE codes.
        juridical_codes: Optional list of juridical-form codes.
        min_start_date: Optional founding-date lower bound.
        has_phone: Filter to companies with phone.
        has_email: Filter to companies with email (only used if condition not provided).
        email_domain: Optional email-domain filter.

    Returns:
        Success message with profile count, or error string.
    """
    canonical_service = CanonicalSegmentService()
    client = TracardiClient()

    if use_last_search and not condition:
        logger.warning(
            "create_segment_no_condition",
            name=name,
            message="use_last_search=True but no condition provided. "
            "tools_node should have injected TQL from state. "
            "Check if checkpointer is persistent (SQLite/Postgres).",
        )

    resolved_nace_codes = list(nace_codes or [])
    if keywords and not resolved_nace_codes:
        resolved_nace_codes = _get_nace_codes_from_keyword(keywords)

    if not condition:
        # Build TQL from structured params for traceability and fallback compatibility.
        params = ProfileSearchParams(
            keywords=None if resolved_nace_codes else keywords,
            enterprise_number=None,
            nace_codes=resolved_nace_codes or None,
            juridical_codes=juridical_codes,
            juridical_keyword=None,
            city=city,
            zip_code=zip_code,
            status=status,
            min_start_date=min_start_date,
            has_phone=has_phone,
            has_email=has_email,
        )
        queries = QueryFactory.generate_all(params)
        condition = queries["tql"]
        logger.warning("create_segment_fallback_to_manual_params", name=name, tql=condition[:100])

    filters = CompanySearchFilters(
        keywords=None if resolved_nace_codes else keywords,
        enterprise_number=None,
        nace_codes=resolved_nace_codes or None,
        juridical_codes=juridical_codes,
        city=city,
        zip_code=zip_code,
        status=status,
        min_start_date=min_start_date,
        has_phone=has_phone,
        has_email=has_email,
        email_domain=_normalize_email_domain(email_domain),
        limit=100,
        offset=0,
    )

    logger.info(
        "create_segment_executing",
        name=name,
        has_condition=bool(condition),
        condition_preview=condition[:100] if condition else None,
        use_last_search=use_last_search,
    )

    try:
        segment = await canonical_service.upsert_segment(
            name=name,
            filters=filters,
            condition=condition,
            description=f"Created by AI: {condition[:200]}",
        )
        count = int(segment["member_count"])
        if count == 0:
            return (
                f"Segment '{name}' created in PostgreSQL with 0 members. "
                "Broaden the search or verify the filters before exporting or activating it."
            )
        return (
            f"Segment '{name}' created in PostgreSQL with {count} members. "
            "Use export_segment_to_csv or get_segment_stats for authoritative segment data."
        )
    except ValueError as exc:
        return f"Segment '{name}' was not created: {exc}"
    except Exception as exc:
        logger.warning("canonical_segment_create_failed", name=name, error=str(exc))

    # Backward-compatible fallback for environments that only have Tracardi segment state.
    res = await client.create_segment(
        name,
        description=f"Created by AI: {condition[:200]}",
        condition=condition,
    )
    if not res:
        return (
            f"Failed to create segment '{name}'. "
            "The canonical PostgreSQL-first path was unavailable and the Tracardi fallback failed."
        )

    count = res.get("profiles_added", 0)
    if count == 0:
        return (
            f"Segment '{name}' was created via Tracardi fallback but contains 0 profiles. "
            "Re-run the search so the canonical PostgreSQL segment path has the filters it needs."
        )
    return (
        f"Segment '{name}' created via Tracardi fallback with {count} profiles. "
        "For authoritative counts and exports, re-create it through the PostgreSQL-first path."
    )


@tool
async def get_segment_stats(segment_id: str) -> str:
    """Get comprehensive statistics for a segment.

    PostgreSQL canonical segments are preferred. Tracardi is used only as a
    backward-compatible fallback when a canonical segment is unavailable.

    Args:
        segment_id: Segment name or ID.

    Returns:
        JSON string with profile count, email/phone coverage, and city distribution.
    """
    logger.info("get_segment_stats_start", segment=segment_id)

    try:
        canonical_service = CanonicalSegmentService()
        canonical_stats = await canonical_service.get_segment_stats(segment_id)
        if canonical_stats is not None:
            logger.info("get_segment_stats_complete", segment=segment_id, backend="postgresql")
            return json.dumps(canonical_stats, ensure_ascii=False)
    except Exception as exc:
        logger.warning("canonical_segment_stats_failed", segment=segment_id, error=str(exc))

    client = TracardiClient()
    query = f'segments="{segment_id}"'
    result = await client.search_profiles(query, limit=100)

    if not result:
        return json.dumps(
            {
                "status": "error",
                "segment_id": segment_id,
                "error": "Failed to retrieve segment data.",
            },
            ensure_ascii=False,
        )

    profiles = result.get("result", []) or []
    total_count = int(result.get("total", 0) or 0)

    if total_count == 0:
        return json.dumps(
            {
                "status": "ok",
                "segment_id": segment_id,
                "profile_count": 0,
                "message": "Segment exists but contains no profiles.",
            },
            ensure_ascii=False,
        )

    # Calculate metrics
    email_count = 0
    phone_count = 0
    city_distribution: dict[str, int] = {}
    status_distribution: dict[str, int] = {}
    juridical_form_distribution: dict[str, int] = {}

    for p in profiles:
        props = p.get("traits") or p.get("data", {}).get("properties", {})

        # Email/Phone coverage
        if props.get("email") or props.get("contact_email"):
            email_count += 1
        if props.get("phone") or props.get("contact_phone") or props.get("telephone"):
            phone_count += 1

        # City distribution
        city = props.get("city") or props.get("kbo_city") or "Unknown"
        city_distribution[city] = city_distribution.get(city, 0) + 1

        # Status distribution
        status = props.get("status") or "Unknown"
        status_distribution[status] = status_distribution.get(status, 0) + 1

        # Juridical form
        jur_form = props.get("juridical_form") or props.get("kbo_juridical_form") or "Unknown"
        if jur_form != "Unknown":
            juridical_form_distribution[jur_form] = (
                juridical_form_distribution.get(jur_form, 0) + 1
            )

    # Calculate percentages based on sample
    sample_size = len(profiles)
    email_coverage = round((email_count / sample_size) * 100, 1) if sample_size > 0 else 0
    phone_coverage = round((phone_count / sample_size) * 100, 1) if sample_size > 0 else 0

    # Get top cities
    top_cities = sorted(city_distribution.items(), key=lambda x: x[1], reverse=True)[:10]

    stats = {
        "status": "ok",
        "segment_id": segment_id,
        "profile_count": total_count,
        "sample_analyzed": sample_size,
        "note": "Stats from Tracardi segment. For authoritative counts, use search_profiles.",
        "contact_coverage": {
            "email_coverage_percent": email_coverage,
            "phone_coverage_percent": phone_coverage,
            "profiles_with_email": int(email_count * (total_count / sample_size))
            if sample_size > 0
            else 0,
            "profiles_with_phone": int(phone_count * (total_count / sample_size))
            if sample_size > 0
            else 0,
        },
        "top_cities": [{"city": city, "count": count} for city, count in top_cities],
        "status_distribution": status_distribution,
        "juridical_form_distribution": dict(
            sorted(juridical_form_distribution.items(), key=lambda x: x[1], reverse=True)[:5]
        ),
        "next_steps_suggestions": [
            f"Push these {total_count} contacts to Resend for an email campaign?",
            "Analyze a different segment?",
            "Create a more targeted sub-segment?",
        ],
    }

    logger.info("get_segment_stats_complete", segment=segment_id, count=total_count)
    return json.dumps(stats, ensure_ascii=False)


@tool
async def aggregate_profiles(
    group_by: str,
    filter_tql: str | None = None,
    keywords: str | None = None,
    city: str | None = None,
    zip_code: str | None = None,
    status: str | None = None,
    nace_codes: list[str] | None = None,
    nace_code: str | None = None,
    juridical_codes: list[str] | None = None,
    email_domain: str | None = None,
    limit_results: int = 20,
) -> str:
    """Aggregate and analyze profiles by a specific field using PostgreSQL.

    Use this for analytics queries like:
    - "Break down active restaurants in Antwerp by juridical form"
    - "Top 5 cities with most IT companies"
    - "Average employee count by industry"

    Args:
        group_by: Field to group by. Options: "city", "juridical_form", "legal_form",
                 "nace_code" (or "industry"), "status", "zip_code".
        filter_tql: Optional raw filter (ignored, kept for compatibility).
        keywords: Industry keyword to filter by (auto-resolved to NACE codes).
        city: Filter to specific city.
        zip_code: Filter to specific postal code.
        status: Optional company status filter, for example "AC" for active.
        nace_codes: List of NACE codes to filter by.
        nace_code: Single NACE code convenience alias.
        juridical_codes: List of juridical form codes to filter by.
        email_domain: Optional email-domain filter.
        limit_results: Maximum number of groups to return (default 20).

    Returns:
        JSON string with aggregated statistics including counts, email/phone coverage per group.
    """
    # Validate group_by parameter
    # Support both "nace_code" and "industry" (synonyms)
    valid_group_by = {
        "city",
        "juridical_form",
        "nace_code",
        "status",
        "zip_code",
        "legal_form",
        "industry",
    }
    if group_by not in valid_group_by:
        return json.dumps(
            {
                "status": "error",
                "error": f"Invalid group_by '{group_by}'. Valid options: {', '.join(sorted(valid_group_by))}",
            },
            ensure_ascii=False,
        )

    # Resolve keywords to NACE codes if provided
    if nace_code and not nace_codes:
        nace_codes = [nace_code.strip()]
    resolved_nace_codes = list(nace_codes or [])
    if keywords and not nace_codes:
        found_codes = _get_nace_codes_from_keyword(keywords)
        if found_codes:
            resolved_nace_codes = found_codes

    # Build filters
    filters = CompanySearchFilters(
        keywords=None,  # Already resolved to NACE
        enterprise_number=None,
        nace_codes=resolved_nace_codes if resolved_nace_codes else None,
        juridical_codes=juridical_codes,
        city=city,
        zip_code=zip_code,
        status=status,
        email_domain=_normalize_email_domain(email_domain),
    )

    # Use PostgreSQL search service for aggregation
    search_service = get_search_service()

    try:
        result = await search_service.aggregate_by_field(
            group_by=group_by,
            filters=filters,
            limit=limit_results,
        )

        # Add next steps suggestions
        groups = result.get("groups", [])
        result["next_steps_suggestions"] = [
            f"Create a segment from the top {groups[0]['group_value'] if groups else 'result'}?"
            if groups
            else "Create a segment?",
            "Push these contacts to Resend for an email campaign?",
            f"Get detailed stats for a specific {group_by}?",
            "Search for companies in a specific group?",
        ]

        return json.dumps(result, ensure_ascii=False)

    except Exception as exc:
        logger.error("aggregate_profiles_failed", error=str(exc))
        return json.dumps(
            {
                "status": "error",
                "error": f"Aggregation failed: {exc}",
            },
            ensure_ascii=False,
        )


@tool
async def get_data_coverage_stats() -> str:
    """Get data coverage statistics for the CDP.

    Returns:
        JSON string with coverage statistics for email, phone, website,
        geocoding, NACE codes, AI descriptions, etc.
    """
    search_service = get_search_service()

    try:
        stats = await search_service.get_coverage_stats()
        return json.dumps(stats, ensure_ascii=False)
    except Exception as exc:
        logger.error("get_coverage_stats_failed", error=str(exc))
        return json.dumps(
            {
                "status": "error",
                "error": f"Failed to get coverage stats: {exc}",
            },
            ensure_ascii=False,
        )


__all__ = [
    "search_profiles",
    "create_segment",
    "get_segment_stats",
    "aggregate_profiles",
    "get_data_coverage_stats",
]
