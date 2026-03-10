"""Unified 360° View Tools for Cross-Source Customer Insights.

These tools enable natural language queries against unified views combining
KBO, Teamleader CRM, Exact Online financial data, and Autotask support data.

Example queries:
- "What is the total pipeline value for software companies in Brussels?"
- "Show me IT companies in Gent with open deals over €10k"
- "Which high-value accounts have overdue invoices?"
- "Give me a 360° view of company KBO 0123.456.789"
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from langchain_core.tools import tool

from src.config import settings
from src.core.logger import get_logger
from src.services.unified_360_queries import Unified360Service

logger = get_logger(__name__)


def _serialize_for_json(obj: Any) -> Any:
    """Serialize objects for JSON output."""
    from datetime import date, datetime

    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    return obj


def _get_database_url() -> str:
    """Get database URL from settings."""
    database_url = settings.DATABASE_URL or settings.POSTGRES_CONNECTION_STRING
    if not database_url:
        raise ValueError("DATABASE_URL or POSTGRES_CONNECTION_STRING must be configured")
    return database_url


@tool
async def query_unified_360(
    query_type: str,
    kbo_number: str | None = None,
    company_name: str | None = None,
    city: str | None = None,
    nace_code: str | None = None,
    nace_prefix: str | None = None,
    min_pipeline_value: float | None = None,
    min_revenue_ytd: float | None = None,
    limit: int = 50,
) -> str:
    """Query unified 360° customer data combining KBO, Teamleader, Exact Online, and Autotask.

    USE THIS TOOL WHEN:
    - User asks for a "360° view" or "complete profile" of a specific company
    - User asks to search for companies by name across all source systems
    - User asks for detailed company information with cross-source data (KBO + CRM + financials + support)
    - User asks for activity timeline for a specific company
    - User asks about a specific company by KBO number

    DO NOT USE THIS TOOL WHEN:
    - User asks for aggregated industry statistics (use get_industry_summary instead)
    - User asks for geographic revenue distribution (use get_geographic_revenue_distribution instead)
    - User asks for simple company counts or lists without 360° context (use search_profiles)
    - User asks about high-value accounts with risk indicators (use find_high_value_accounts)
    - User asks about identity link quality (use get_identity_link_quality)

    QUERY TYPES:
    - "company_profile": Get complete 360° profile for a specific company (requires kbo_number)
    - "pipeline_summary": Find companies with pipeline/revenue data (optionally filter by city/NACE)
    - "activity_timeline": Get chronological activity for a company (requires kbo_number)
    - "search_by_name": Search companies across all source systems by name

    QUERY PATTERNS THAT REQUIRE THIS TOOL:
    - "Give me a 360° view of company KBO 0123.456.789"
    - "Show me the complete profile for company X"
    - "Search for company named Acme Corp"
    - "What is the activity timeline for KBO 0123.456.789?"
    - "Show me companies with pipeline in Brussels"

    QUERY PATTERNS THAT DO NOT REQUIRE THIS TOOL:
    - "What is the total pipeline for software companies?" → use get_industry_summary
    - "Revenue distribution by city" → use get_geographic_revenue_distribution
    - "How many restaurants in Gent?" → use search_profiles
    - "Which accounts have overdue invoices?" → use find_high_value_accounts

    Args:
        query_type: Type of query - "company_profile", "pipeline_summary", "activity_timeline", or "search_by_name"
        kbo_number: KBO number (required for company_profile and activity_timeline)
        company_name: Company name to search for (used in search_by_name)
        city: Filter by city name
        nace_code: Filter by specific NACE code
        nace_prefix: Filter by NACE prefix (e.g., '62' for software/IT)
        min_pipeline_value: Minimum open pipeline value (euros)
        min_revenue_ytd: Minimum year-to-date revenue (euros)
        limit: Maximum results to return (default 50)

    Returns:
        JSON string with query results including company data, pipeline, financials, support data, and activities.

    Examples:
        >>> query_unified_360(query_type="company_profile", kbo_number="0123.456.789")
        # Returns complete 360° profile with KBO, Teamleader, Exact, and Autotask data
        >>> query_unified_360(query_type="pipeline_summary", city="Brussels", nace_prefix="62")
        # Returns companies with pipeline data in Brussels, NACE 62xxx
        >>> query_unified_360(query_type="search_by_name", company_name="Acme Corp")
        # Returns search results for company name across all source systems
    """
    service = Unified360Service(database_url=_get_database_url())

    try:
        if query_type == "company_profile":
            if not kbo_number:
                return json.dumps(
                    {
                        "status": "error",
                        "error": "kbo_number is required for company_profile query type",
                    },
                    ensure_ascii=False,
                )

            profile = await service.get_company_360_profile(kbo_number=kbo_number)
            if not profile:
                return json.dumps(
                    {"status": "error", "error": f"No company found with KBO number {kbo_number}"},
                    ensure_ascii=False,
                )

            result = {
                "status": "ok",
                "query_type": query_type,
                "company": {
                    "company_uid": profile.company_uid,
                    "kbo_number": profile.kbo_number,
                    "vat_number": profile.vat_number,
                    "kbo_company_name": profile.kbo_company_name,
                    "legal_form": profile.legal_form,
                    "nace_code": profile.nace_code,
                    "nace_description": profile.nace_description,
                    "kbo_status": profile.kbo_status,
                    "kbo_city": profile.kbo_city,
                    "website_url": profile.website_url,
                    "employee_count": profile.employee_count,
                },
                "teamleader": {
                    "company_id": profile.tl_company_id,
                    "company_name": profile.tl_company_name,
                    "status": profile.tl_status,
                    "customer_type": profile.tl_customer_type,
                    "email": profile.tl_email,
                    "phone": profile.tl_phone,
                }
                if profile.tl_company_id
                else None,
                "exact": {
                    "customer_id": profile.exact_customer_id,
                    "company_name": profile.exact_company_name,
                    "status": profile.exact_status,
                    "credit_line": float(profile.exact_credit_line)
                    if profile.exact_credit_line
                    else None,
                    "payment_terms": profile.exact_payment_terms,
                    "account_manager": profile.exact_account_manager,
                }
                if profile.exact_customer_id
                else None,
                "autotask": {
                    "company_id": profile.autotask_company_id,
                    "company_name": profile.autotask_company_name,
                    "company_type": profile.autotask_company_type,
                    "phone": profile.autotask_phone,
                    "website": profile.autotask_website,
                    "total_tickets": profile.autotask_total_tickets,
                    "open_tickets": profile.autotask_open_tickets,
                    "last_ticket_at": profile.autotask_last_ticket_at.isoformat()
                    if profile.autotask_last_ticket_at
                    else None,
                    "total_contracts": profile.autotask_total_contracts,
                    "active_contracts": profile.autotask_active_contracts,
                    "total_contract_value": float(profile.autotask_total_contract_value)
                    if profile.autotask_total_contract_value
                    else 0,
                    "last_contract_start": profile.autotask_last_contract_start.isoformat()
                    if profile.autotask_last_contract_start
                    else None,
                }
                if profile.autotask_company_id
                else None,
                "pipeline": _serialize_for_json(profile.pipeline.__dict__)
                if profile.pipeline
                else None,
                "financials": _serialize_for_json(profile.financials.__dict__)
                if profile.financials
                else None,
                "identity_link_status": profile.identity_link_status,
                "total_source_count": profile.total_source_count,
                "data_sources": {
                    "kbo": True,
                    "teamleader": profile.has_teamleader,
                    "exact": profile.has_exact,
                    "autotask": profile.has_autotask,
                },
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        elif query_type == "pipeline_summary":
            from decimal import Decimal

            companies = await service.find_companies_with_pipeline(
                nace_codes=[nace_code] if nace_code else None,
                nace_prefix=nace_prefix,
                city=city,
                min_pipeline_value=Decimal(str(min_pipeline_value))
                if min_pipeline_value
                else None,
                min_revenue_ytd=Decimal(str(min_revenue_ytd)) if min_revenue_ytd else None,
                limit=limit,
            )

            return json.dumps(
                {
                    "status": "ok",
                    "query_type": query_type,
                    "filters_applied": {
                        "city": city,
                        "nace_code": nace_code,
                        "nace_prefix": nace_prefix,
                        "min_pipeline_value": min_pipeline_value,
                        "min_revenue_ytd": min_revenue_ytd,
                    },
                    "result_count": len(companies),
                    "companies": _serialize_for_json(companies),
                },
                ensure_ascii=False,
                indent=2,
            )

        elif query_type == "activity_timeline":
            if not kbo_number:
                return json.dumps(
                    {
                        "status": "error",
                        "error": "kbo_number is required for activity_timeline query type",
                    },
                    ensure_ascii=False,
                )

            activities = await service.get_company_activity_timeline(
                kbo_number=kbo_number, limit=limit
            )

            return json.dumps(
                {
                    "status": "ok",
                    "query_type": query_type,
                    "kbo_number": kbo_number,
                    "activity_count": len(activities),
                    "activities": [
                        {
                            "source_system": a.source_system,
                            "activity_type": a.activity_type,
                            "description": a.activity_description,
                            "date": a.activity_date.isoformat() if a.activity_date else None,
                        }
                        for a in activities
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )

        elif query_type == "search_by_name":
            if not company_name:
                return json.dumps(
                    {
                        "status": "error",
                        "error": "company_name is required for search_by_name query type",
                    },
                    ensure_ascii=False,
                )

            companies = await service.search_companies_unified(query=company_name, limit=limit)

            return json.dumps(
                {
                    "status": "ok",
                    "query_type": query_type,
                    "search_term": company_name,
                    "result_count": len(companies),
                    "companies": _serialize_for_json(companies),
                },
                ensure_ascii=False,
                indent=2,
            )

        else:
            return json.dumps(
                {
                    "status": "error",
                    "error": f"Unknown query_type: {query_type}. Valid types: company_profile, pipeline_summary, activity_timeline, search_by_name",
                },
                ensure_ascii=False,
            )

    except Exception as exc:
        logger.error("query_unified_360_failed", error=str(exc), query_type=query_type)
        return json.dumps(
            {"status": "error", "error": f"Query failed: {str(exc)}"}, ensure_ascii=False
        )

    finally:
        await service.close()


@tool
async def get_industry_summary(
    industry_category: str | None = None,
    nace_prefix: str | None = None,
    city: str | None = None,
    limit: int = 20,
) -> str:
    """Get industry-level pipeline value and revenue summary (cross-source: KBO + CRM + Exact).

    USE THIS TOOL WHEN:
    - User asks about "pipeline value" for an industry or category of companies
    - User asks about "total pipeline" or "pipeline summary" by industry
    - User asks about industry-level revenue, deals, or financial aggregates
    - User asks about "software companies" or any industry category with pipeline/revenue context
    - Query combines industry filtering with financial/pipeline metrics across sources

    DO NOT USE THIS TOOL WHEN:
    - User asks to search for specific companies by name (use search_profiles or query_unified_360)
    - User asks for simple company counts without pipeline/revenue (use search_profiles)
    - User asks about geographic distribution only (use get_geographic_revenue_distribution)
    - User asks about individual company details (use query_unified_360)
    - User asks to group by non-industry fields (use aggregate_profiles)

    QUERY PATTERNS THAT REQUIRE THIS TOOL:
    - "What is the total pipeline value for software companies in Brussels?"
    - "Pipeline value for software companies in Brussels?"
    - "Show me the pipeline summary for IT companies"
    - "What is the total revenue for retail companies?"
    - "Which industries have the most pipeline?"
    - "Show me industry breakdown with deal values"

    QUERY PATTERNS THAT DO NOT REQUIRE THIS TOOL:
    - "How many software companies are in Brussels?" → use search_profiles
    - "Show me software companies in Brussels" → use search_profiles
    - "Revenue distribution by city" → use get_geographic_revenue_distribution
    - "Find company named Acme" → use query_unified_360 with query_type="search_by_name"

    INDUSTRY CATEGORIES (auto-resolved from keywords):
    - "software" or "IT" -> NACE 62xxx (Software/IT Services)
    - "web" or "data" -> NACE 63xxx (Data Processing/Web)
    - "restaurant" or "food" -> NACE 56xxx (Food & Beverage)
    - "retail" -> NACE 47xxx (Retail)
    - "construction" -> NACE 41xxx-43xxx (Construction)
    - "legal" or "accounting" -> NACE 69xxx (Legal/Accounting)
    - "healthcare" -> NACE 86xxx (Healthcare)

    Args:
        industry_category: Industry name/category (e.g., "software", "restaurant", "retail")
        nace_prefix: Direct NACE code prefix (e.g., '62' for software, '56' for restaurants)
        city: Filter by city (e.g., "Brussels", "Gent", "Antwerpen")
        limit: Maximum number of industry segments to return

    Returns:
        JSON string with industry summary including:
        - company_count: Number of companies in this industry
        - total_pipeline_value: Sum of open deal values
        - total_won_value_ytd: Sum of won deals this year
        - total_revenue_ytd: Sum of revenue from Exact Online
        - total_outstanding: Total outstanding invoices
        - total_overdue: Total overdue amounts

    Examples:
        >>> get_industry_summary(industry_category="software", city="Brussels")
        # Returns pipeline and revenue for software companies in Brussels
        >>> get_industry_summary(nace_prefix="62")
        # Returns summary for NACE code 62xxx (IT/software)
        >>> get_industry_summary(industry_category="restaurant", city="Gent")
        # Returns summary for restaurants in Gent
    """
    service = Unified360Service(database_url=_get_database_url())

    try:
        # Map industry category to NACE prefix if provided
        prefix = nace_prefix
        if industry_category and not prefix:
            category_map = {
                "software": "62",
                "it": "62",
                "web": "63",
                "data": "63",
                "restaurant": "56",
                "food": "56",
                "retail": "47",
                "construction": "41",
                "legal": "69",
                "accounting": "69",
                "healthcare": "86",
                "medical": "86",
            }
            prefix = category_map.get(industry_category.lower())

        summaries = await service.get_industry_pipeline_summary(
            nace_prefix=prefix, city=city, limit=limit
        )

        if not summaries:
            return json.dumps(
                {
                    "status": "ok",
                    "message": "No industry data found for the specified criteria",
                    "filters": {
                        "industry_category": industry_category,
                        "nace_prefix": prefix,
                        "city": city,
                    },
                    "summaries": [],
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "status": "ok",
                "filters_applied": {
                    "industry_category": industry_category,
                    "nace_prefix": prefix,
                    "city": city,
                },
                "summary_count": len(summaries),
                "summaries": [
                    {
                        "industry_category": s.industry_category,
                        "nace_code": s.nace_code,
                        "nace_description": s.nace_description,
                        "city": s.city,
                        "company_count": s.company_count,
                        "total_pipeline_value": float(s.total_pipeline_value)
                        if s.total_pipeline_value
                        else 0,
                        "total_won_value_ytd": float(s.total_won_value_ytd)
                        if s.total_won_value_ytd
                        else 0,
                        "total_revenue_ytd": float(s.total_revenue_ytd)
                        if s.total_revenue_ytd
                        else 0,
                        "total_outstanding": float(s.total_outstanding)
                        if s.total_outstanding
                        else 0,
                        "total_overdue": float(s.total_overdue) if s.total_overdue else 0,
                    }
                    for s in summaries
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as exc:
        logger.error("get_industry_summary_failed", error=str(exc))
        return json.dumps(
            {"status": "error", "error": f"Query failed: {str(exc)}"}, ensure_ascii=False
        )

    finally:
        await service.close()


@tool
async def find_high_value_accounts(
    min_exposure: float | None = None,
    account_priority: str | None = None,
    city: str | None = None,
    has_overdue: bool | None = None,
    limit: int = 50,
) -> str:
    """Find high-value accounts with revenue, pipeline, or risk indicators.

    USE THIS TOOL WHEN:
    - User asks about "high-value accounts" or "high-value customers"
    - User asks about accounts with "overdue invoices" or "outstanding amounts"
    - User asks about "high-risk" or "at-risk" accounts
    - User asks about companies with "high pipeline" or "big deals"
    - User asks about accounts by exposure, risk level, or opportunity level
    - User mentions specific financial thresholds (€50k, €100k, etc.)

    DO NOT USE THIS TOOL WHEN:
    - User asks for simple company searches without risk/value context (use search_profiles)
    - User asks about industry-level aggregates (use get_industry_summary)
    - User asks about geographic distribution (use get_geographic_revenue_distribution)
    - User asks about a specific company by name/KBO (use query_unified_360)
    - User asks for identity link quality (use get_identity_link_quality)

    ACCOUNT PRIORITIES:
    - "high_risk": Accounts with >€10k overdue
    - "medium_risk": Accounts with some overdue
    - "high_opportunity": Accounts with >€50k pipeline
    - "medium_opportunity": Accounts with >€10k pipeline
    - "high_value": Accounts with >€100k revenue YTD
    - "standard": Other accounts with data

    QUERY PATTERNS THAT REQUIRE THIS TOOL:
    - "Which high-value accounts have overdue invoices?"
    - "Show me companies with high pipeline value"
    - "Find high-risk accounts in Brussels"
    - "List companies with total exposure over €50k"
    - "Show me accounts with overdue amounts"
    - "Find our biggest opportunities"

    QUERY PATTERNS THAT DO NOT REQUIRE THIS TOOL:
    - "How many companies in Brussels?" → use search_profiles
    - "What is the pipeline for software companies?" → use get_industry_summary
    - "Show me revenue by city" → use get_geographic_revenue_distribution

    Args:
        min_exposure: Minimum total exposure (pipeline + outstanding invoices) in euros
        account_priority: Filter by priority level (see above)
        city: Filter by city
        has_overdue: If True, only return accounts with overdue invoices
        limit: Maximum results to return

    Returns:
        JSON string with high-value accounts including:
        - Company identification (KBO, name, city)
        - Pipeline data (open deals, value)
        - Financial data (revenue, outstanding, overdue)
        - Account priority classification
        - Data completeness score

    Examples:
        >>> find_high_value_accounts(has_overdue=True)
        # Returns accounts with overdue invoices
        >>> find_high_value_accounts(min_exposure=50000, city="Brussels")
        # Returns high-exposure accounts in Brussels
        >>> find_high_value_accounts(account_priority="high_opportunity")
        # Returns accounts classified as high opportunity
    """
    from decimal import Decimal

    service = Unified360Service(database_url=_get_database_url())

    try:
        accounts = await service.get_high_value_accounts(
            min_exposure=Decimal(str(min_exposure)) if min_exposure else None,
            account_priority=account_priority,
            limit=limit,
        )

        # Filter by city if specified
        if city:
            accounts = [a for a in accounts if a.get("kbo_city", "").lower() == city.lower()]

        # Filter for overdue if specified
        if has_overdue:
            accounts = [a for a in accounts if (a.get("exact_overdue") or 0) > 0]

        if not accounts:
            return json.dumps(
                {
                    "status": "ok",
                    "message": "No high-value accounts found matching the criteria",
                    "filters_applied": {
                        "min_exposure": min_exposure,
                        "account_priority": account_priority,
                        "city": city,
                        "has_overdue": has_overdue,
                    },
                    "accounts": [],
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "status": "ok",
                "filters_applied": {
                    "min_exposure": min_exposure,
                    "account_priority": account_priority,
                    "city": city,
                    "has_overdue": has_overdue,
                },
                "result_count": len(accounts),
                "total_pipeline_value": sum(a.get("tl_pipeline_value", 0) or 0 for a in accounts),
                "total_outstanding": sum(a.get("exact_outstanding", 0) or 0 for a in accounts),
                "total_overdue": sum(a.get("exact_overdue", 0) or 0 for a in accounts),
                "accounts": _serialize_for_json(accounts),
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as exc:
        logger.error("find_high_value_accounts_failed", error=str(exc))
        return json.dumps(
            {"status": "error", "error": f"Query failed: {str(exc)}"}, ensure_ascii=False
        )

    finally:
        await service.close()


@tool
async def get_geographic_revenue_distribution(
    min_companies: int = 1,
    limit: int = 50,
) -> str:
    """Get geographic distribution of revenue, pipeline, and companies across cities.

    USE THIS TOOL WHEN:
    - User asks about "revenue distribution by city"
    - User asks about "geographic distribution" of customers/revenue/pipeline
    - User asks "which cities have the most revenue?"
    - User asks about "market penetration by city"
    - User asks about revenue, pipeline, or companies grouped by location
    - Query involves cross-source data (KBO + CRM + financials) aggregated by city

    DO NOT USE THIS TOOL WHEN:
    - User asks to aggregate/group companies by non-geographic fields (use aggregate_profiles instead)
    - User asks about industry breakdown (use get_industry_summary instead)
    - User asks for simple city counts without revenue context (use search_profiles instead)
    - User asks about a specific company or list of companies (use query_unified_360 or search_profiles)

    QUERY PATTERNS THAT REQUIRE THIS TOOL:
    - "Show me revenue distribution by city"
    - "Which cities have the most revenue?"
    - "What is our geographic distribution of customers?"
    - "Show me pipeline by city"
    - "What is the market penetration by location?"
    - "How is our revenue spread across different cities?"

    QUERY PATTERNS THAT DO NOT REQUIRE THIS TOOL:
    - "Group companies by industry" → use aggregate_profiles with group_by="industry"
    - "Show me software companies in Brussels" → use search_profiles
    - "What is the total pipeline for software companies?" → use get_industry_summary

    Args:
        min_companies: Minimum number of companies to include a city
        limit: Maximum number of cities to return

    Returns:
        JSON string with geographic summary including:
        - city: City name
        - total_companies: Total companies in the city
        - companies_with_crm: Companies with Teamleader data
        - companies_with_financials: Companies with Exact data
        - total_pipeline: Sum of pipeline values
        - total_revenue_ytd: Sum of YTD revenue
        - total_outstanding: Sum of outstanding invoices
        - market_penetration_pct: Percentage with CRM/financial data

    Examples:
        >>> get_geographic_revenue_distribution()
        # Returns revenue and pipeline distribution across all cities
        >>> get_geographic_revenue_distribution(min_companies=100, limit=20)
        # Returns top 20 cities with at least 100 companies
    """
    service = Unified360Service(database_url=_get_database_url())

    try:
        distribution = await service.get_geographic_distribution(
            min_companies=min_companies, limit=limit
        )

        if not distribution:
            return json.dumps(
                {
                    "status": "ok",
                    "message": "No geographic distribution data available",
                    "distribution": [],
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "status": "ok",
                "filters_applied": {
                    "min_companies": min_companies,
                },
                "city_count": len(distribution),
                "total_companies": sum(d.total_companies for d in distribution),
                "total_pipeline": sum(float(d.total_pipeline or 0) for d in distribution),
                "total_revenue_ytd": sum(float(d.total_revenue_ytd or 0) for d in distribution),
                "distribution": [
                    {
                        "city": d.city,
                        "province": d.province,
                        "total_companies": d.total_companies,
                        "companies_with_crm": d.companies_with_crm,
                        "companies_with_financials": d.companies_with_financials,
                        "total_pipeline": float(d.total_pipeline or 0),
                        "total_revenue_ytd": float(d.total_revenue_ytd or 0),
                        "total_outstanding": float(d.total_outstanding or 0),
                        "market_penetration_pct": d.market_penetration_pct,
                    }
                    for d in distribution
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as exc:
        logger.error("get_geographic_revenue_distribution_failed", error=str(exc))
        return json.dumps(
            {"status": "error", "error": f"Query failed: {str(exc)}"}, ensure_ascii=False
        )

    finally:
        await service.close()


@tool
async def get_identity_link_quality() -> str:
    """Get identity link quality metrics showing how well source systems are linked to KBO.

    USE THIS TOOL WHEN:
    - User asks about "linkage" between systems and KBO
    - User asks "how well are source systems linked to KBO?"
    - User asks about "identity link quality" or "matching coverage"
    - User asks about KBO matching rates for Teamleader or Exact
    - User asks how many CRM/financial records are matched to KBO companies

    DO NOT USE THIS TOOL WHEN:
    - User asks about data coverage statistics (use get_data_coverage_stats instead)
    - User asks about general database completeness (use get_data_coverage_stats instead)
    - User asks about field-level data quality (use get_data_coverage_stats instead)
    - User asks about enrichment progress (use get_data_coverage_stats instead)

    QUERY PATTERNS THAT REQUIRE THIS TOOL:
    - "How well are source systems linked to KBO?"
    - "What is the KBO match rate for Teamleader?"
    - "How many Exact records are matched to KBO companies?"
    - "Show me identity link quality"
    - "What percentage of CRM companies have KBO numbers?"

    QUERY PATTERNS THAT DO NOT REQUIRE THIS TOOL:
    - "What is the data coverage?" → use get_data_coverage_stats
    - "How complete is our data?" → use get_data_coverage_stats
    - "What percentage of companies have websites?" → use get_data_coverage_stats

    Returns:
        JSON string with quality metrics per source system:
        - source_system: "teamleader" or "exact"
        - total_records: Total records in source
        - with_kbo_number: Records matched by KBO
        - match_rate_pct: Percentage successfully matched
        - oldest_sync/newest_sync: Sync time range

    Examples:
        >>> get_identity_link_quality()
        # Returns: {"status": "ok", "source_count": 2, "quality_metrics": [...]}
    """
    service = Unified360Service(database_url=_get_database_url())

    try:
        quality = await service.get_identity_link_quality()
        quality_serialized = _serialize_for_json(quality)

        return json.dumps(
            {
                "status": "ok",
                "source_count": len(quality_serialized),
                "quality_metrics": quality_serialized,
                "summary": {
                    "teamleader": next(
                        (q for q in quality_serialized if q.get("source_system") == "teamleader"),
                        None,
                    ),
                    "exact": next(
                        (q for q in quality_serialized if q.get("source_system") == "exact"), None
                    ),
                },
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as exc:
        logger.error("get_identity_link_quality_failed", error=str(exc))
        return json.dumps(
            {"status": "error", "error": f"Query failed: {str(exc)}"}, ensure_ascii=False
        )

    finally:
        await service.close()
