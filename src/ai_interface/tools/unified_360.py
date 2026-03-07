"""Unified 360° View Tools for Cross-Source Customer Insights.

These tools enable natural language queries against unified views combining
KBO, Teamleader CRM, and Exact Online financial data.

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
    return settings.DATABASE_URL or settings.POSTGRES_CONNECTION_STRING


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
    """Query unified 360° customer data combining KBO, Teamleader, and Exact Online.

    This tool provides comprehensive cross-source insights for sales, finance, and operations.

    QUERY TYPES:
    - "company_profile": Get complete 360° profile for a specific company (requires kbo_number)
    - "pipeline_summary": Find companies with pipeline/revenue data (optionally filter by city/NACE)
    - "activity_timeline": Get chronological activity for a company (requires kbo_number)
    - "search_by_name": Search companies across all source systems by name

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
        JSON string with query results including company data, pipeline, financials, and activities.

    Examples:
        - query_unified_360(query_type="company_profile", kbo_number="0123.456.789")
        - query_unified_360(query_type="pipeline_summary", city="Brussels", nace_prefix="62")
        - query_unified_360(query_type="search_by_name", company_name="Acme Corp")
    """
    service = Unified360Service(database_url=_get_database_url())

    try:
        if query_type == "company_profile":
            if not kbo_number:
                return json.dumps({
                    "status": "error",
                    "error": "kbo_number is required for company_profile query type"
                }, ensure_ascii=False)

            profile = await service.get_company_360_profile(kbo_number=kbo_number)
            if not profile:
                return json.dumps({
                    "status": "error",
                    "error": f"No company found with KBO number {kbo_number}"
                }, ensure_ascii=False)

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
                } if profile.tl_company_id else None,
                "exact": {
                    "customer_id": profile.exact_customer_id,
                    "company_name": profile.exact_company_name,
                    "status": profile.exact_status,
                    "credit_line": float(profile.exact_credit_line) if profile.exact_credit_line else None,
                    "payment_terms": profile.exact_payment_terms,
                    "account_manager": profile.exact_account_manager,
                } if profile.exact_customer_id else None,
                "pipeline": _serialize_for_json(profile.pipeline.__dict__) if profile.pipeline else None,
                "financials": _serialize_for_json(profile.financials.__dict__) if profile.financials else None,
                "identity_link_status": profile.identity_link_status,
                "data_sources": {
                    "kbo": True,
                    "teamleader": profile.tl_company_id is not None,
                    "exact": profile.exact_customer_id is not None,
                }
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        elif query_type == "pipeline_summary":
            from decimal import Decimal

            companies = await service.find_companies_with_pipeline(
                nace_codes=[nace_code] if nace_code else None,
                nace_prefix=nace_prefix,
                city=city,
                min_pipeline_value=Decimal(str(min_pipeline_value)) if min_pipeline_value else None,
                min_revenue_ytd=Decimal(str(min_revenue_ytd)) if min_revenue_ytd else None,
                limit=limit
            )

            return json.dumps({
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
            }, ensure_ascii=False, indent=2)

        elif query_type == "activity_timeline":
            if not kbo_number:
                return json.dumps({
                    "status": "error",
                    "error": "kbo_number is required for activity_timeline query type"
                }, ensure_ascii=False)

            activities = await service.get_company_activity_timeline(kbo_number=kbo_number, limit=limit)

            return json.dumps({
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
            }, ensure_ascii=False, indent=2)

        elif query_type == "search_by_name":
            if not company_name:
                return json.dumps({
                    "status": "error",
                    "error": "company_name is required for search_by_name query type"
                }, ensure_ascii=False)

            companies = await service.search_companies_unified(query=company_name, limit=limit)

            return json.dumps({
                "status": "ok",
                "query_type": query_type,
                "search_term": company_name,
                "result_count": len(companies),
                "companies": _serialize_for_json(companies),
            }, ensure_ascii=False, indent=2)

        else:
            return json.dumps({
                "status": "error",
                "error": f"Unknown query_type: {query_type}. Valid types: company_profile, pipeline_summary, activity_timeline, search_by_name"
            }, ensure_ascii=False)

    except Exception as exc:
        logger.error("query_unified_360_failed", error=str(exc), query_type=query_type)
        return json.dumps({
            "status": "error",
            "error": f"Query failed: {str(exc)}"
        }, ensure_ascii=False)

    finally:
        await service.close()


@tool
async def get_industry_summary(
    industry_category: str | None = None,
    nace_prefix: str | None = None,
    city: str | None = None,
    limit: int = 20,
) -> str:
    """Get industry-level pipeline and revenue summary across all companies.

    Use this for questions like:
    - "What is the total pipeline value for software companies in Brussels?"
    - "Show me industry breakdown for IT companies"
    - "Which industries have the most revenue in Antwerp?"

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
        - get_industry_summary(industry_category="software", city="Brussels")
        - get_industry_summary(nace_prefix="62")
        - get_industry_summary(industry_category="restaurant", city="Gent")
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
            nace_prefix=prefix,
            city=city,
            limit=limit
        )

        if not summaries:
            return json.dumps({
                "status": "ok",
                "message": f"No industry data found for the specified criteria",
                "filters": {
                    "industry_category": industry_category,
                    "nace_prefix": prefix,
                    "city": city,
                },
                "summaries": [],
            }, ensure_ascii=False)

        return json.dumps({
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
                    "total_pipeline_value": float(s.total_pipeline_value) if s.total_pipeline_value else 0,
                    "total_won_value_ytd": float(s.total_won_value_ytd) if s.total_won_value_ytd else 0,
                    "total_revenue_ytd": float(s.total_revenue_ytd) if s.total_revenue_ytd else 0,
                    "total_outstanding": float(s.total_outstanding) if s.total_outstanding else 0,
                    "total_overdue": float(s.total_overdue) if s.total_overdue else 0,
                }
                for s in summaries
            ],
        }, ensure_ascii=False, indent=2)

    except Exception as exc:
        logger.error("get_industry_summary_failed", error=str(exc))
        return json.dumps({
            "status": "error",
            "error": f"Query failed: {str(exc)}"
        }, ensure_ascii=False)

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

    Use this for questions like:
    - "Which high-value accounts have overdue invoices?"
    - "Show me companies with high pipeline value"
    - "Find high-risk accounts in Brussels"
    - "List companies with total exposure over €50k"

    ACCOUNT PRIORITIES:
    - "high_risk": Accounts with >€10k overdue
    - "medium_risk": Accounts with some overdue
    - "high_opportunity": Accounts with >€50k pipeline
    - "medium_opportunity": Accounts with >€10k pipeline
    - "high_value": Accounts with >€100k revenue YTD
    - "standard": Other accounts with data

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
        - find_high_value_accounts(has_overdue=True)
        - find_high_value_accounts(min_exposure=50000, city="Brussels")
        - find_high_value_accounts(account_priority="high_opportunity")
    """
    from decimal import Decimal

    service = Unified360Service(database_url=_get_database_url())

    try:
        accounts = await service.get_high_value_accounts(
            min_exposure=Decimal(str(min_exposure)) if min_exposure else None,
            account_priority=account_priority,
            limit=limit
        )

        # Filter by city if specified
        if city:
            accounts = [a for a in accounts if a.get('kbo_city', '').lower() == city.lower()]

        # Filter for overdue if specified
        if has_overdue:
            accounts = [a for a in accounts if (a.get('exact_overdue') or 0) > 0]

        if not accounts:
            return json.dumps({
                "status": "ok",
                "message": "No high-value accounts found matching the criteria",
                "filters_applied": {
                    "min_exposure": min_exposure,
                    "account_priority": account_priority,
                    "city": city,
                    "has_overdue": has_overdue,
                },
                "accounts": [],
            }, ensure_ascii=False)

        return json.dumps({
            "status": "ok",
            "filters_applied": {
                "min_exposure": min_exposure,
                "account_priority": account_priority,
                "city": city,
                "has_overdue": has_overdue,
            },
            "result_count": len(accounts),
            "total_pipeline_value": sum(a.get('tl_pipeline_value', 0) or 0 for a in accounts),
            "total_outstanding": sum(a.get('exact_outstanding', 0) or 0 for a in accounts),
            "total_overdue": sum(a.get('exact_overdue', 0) or 0 for a in accounts),
            "accounts": _serialize_for_json(accounts),
        }, ensure_ascii=False, indent=2)

    except Exception as exc:
        logger.error("find_high_value_accounts_failed", error=str(exc))
        return json.dumps({
            "status": "error",
            "error": f"Query failed: {str(exc)}"
        }, ensure_ascii=False)

    finally:
        await service.close()


@tool
async def get_geographic_revenue_distribution(
    min_companies: int = 1,
    limit: int = 50,
) -> str:
    """Get geographic distribution of companies with pipeline and revenue data.

    Use this for questions like:
    - "Which cities have the most revenue?"
    - "Show me geographic distribution of our customers"
    - "What is our market penetration by city?"

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
        - get_geographic_revenue_distribution()
        - get_geographic_revenue_distribution(min_companies=100, limit=20)
    """
    service = Unified360Service(database_url=_get_database_url())

    try:
        distribution = await service.get_geographic_distribution(
            min_companies=min_companies,
            limit=limit
        )

        if not distribution:
            return json.dumps({
                "status": "ok",
                "message": "No geographic distribution data available",
                "distribution": [],
            }, ensure_ascii=False)

        return json.dumps({
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
        }, ensure_ascii=False, indent=2)

    except Exception as exc:
        logger.error("get_geographic_revenue_distribution_failed", error=str(exc))
        return json.dumps({
            "status": "error",
            "error": f"Query failed: {str(exc)}"
        }, ensure_ascii=False)

    finally:
        await service.close()


@tool
async def get_identity_link_quality() -> str:
    """Get identity link quality metrics showing KBO matching coverage.

    Use this to monitor how well Teamleader and Exact records are linked
to KBO/PostgreSQL companies.

    Returns:
        JSON string with quality metrics per source system:
        - source_system: "teamleader" or "exact"
        - total_records: Total records in source
        - with_kbo_number: Records matched by KBO
        - match_rate_pct: Percentage successfully matched
        - oldest_sync/newest_sync: Sync time range

    Examples:
        - get_identity_link_quality()
    """
    service = Unified360Service(database_url=_get_database_url())

    try:
        quality = await service.get_identity_link_quality()
        quality_serialized = _serialize_for_json(quality)

        return json.dumps({
            "status": "ok",
            "source_count": len(quality_serialized),
            "quality_metrics": quality_serialized,
            "summary": {
                "teamleader": next((q for q in quality_serialized if q.get('source_system') == 'teamleader'), None),
                "exact": next((q for q in quality_serialized if q.get('source_system') == 'exact'), None),
            }
        }, ensure_ascii=False, indent=2)

    except Exception as exc:
        logger.error("get_identity_link_quality_failed", error=str(exc))
        return json.dumps({
            "status": "error",
            "error": f"Query failed: {str(exc)}"
        }, ensure_ascii=False)

    finally:
        await service.close()
