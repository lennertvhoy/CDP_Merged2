"""Unified 360° View Query Service

Provides high-level query interface for cross-source customer insights,
combining KBO, Teamleader CRM, and Exact Online financial data.

Example usage:
    service = Unified360Service(database_url)
    
    # Query: "What is the total pipeline value for software companies in Brussels?"
    result = await service.get_industry_pipeline_summary(
        nace_prefix='62',
        city='Brussels'
    )
    
    # Query: "Show me IT companies in Gent with open deals over €10k"
    result = await service.find_companies_with_pipeline(
        nace_codes=['62010', '62020', '62030'],
        city='Gent',
        min_pipeline_value=10000
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import asyncpg


@dataclass
class Company360Profile:
    """Complete 360° profile for a company."""
    # Identity
    company_uid: str
    kbo_number: str | None
    vat_number: str | None
    
    # KBO Data
    kbo_company_name: str | None
    legal_form: str | None
    nace_code: str | None
    nace_description: str | None
    kbo_status: str | None
    kbo_city: str | None
    website_url: str | None
    employee_count: int | None
    
    # Teamleader Data
    tl_company_id: str | None
    tl_company_name: str | None
    tl_status: str | None
    tl_customer_type: str | None
    tl_email: str | None
    tl_phone: str | None
    
    # Exact Data
    exact_customer_id: str | None
    exact_company_name: str | None
    exact_status: str | None
    exact_credit_line: Decimal | None
    exact_payment_terms: int | None
    exact_account_manager: str | None
    
    # Identity Link Status
    identity_link_status: str  # 'linked_both', 'linked_teamleader', 'linked_exact', 'kbo_only'
    last_updated_at: datetime
    
    # Related data (populated on demand)
    pipeline: PipelineSummary | None = None
    financials: FinancialSummary | None = None
    activities: list[ActivityRecord] = field(default_factory=list)
    deals: list[DealRecord] = field(default_factory=list)


@dataclass
class PipelineSummary:
    """CRM pipeline summary."""
    open_deals_count: int = 0
    open_deals_value: Decimal = Decimal('0')
    won_deals_ytd: int = 0
    won_value_ytd: Decimal = Decimal('0')
    lost_deals_ytd: int = 0
    lost_value_ytd: Decimal = Decimal('0')


@dataclass
class FinancialSummary:
    """Exact Online financial summary."""
    revenue_ytd: Decimal = Decimal('0')
    revenue_total: Decimal = Decimal('0')
    outstanding_amount: Decimal = Decimal('0')
    overdue_amount: Decimal = Decimal('0')
    total_invoices: int = 0
    paid_invoices: int = 0
    open_invoices: int = 0
    overdue_invoices: int = 0
    avg_days_overdue: float | None = None
    last_invoice_date: date | None = None


@dataclass
class ActivityRecord:
    """Activity record from any source."""
    source_system: str
    activity_type: str
    activity_description: str
    activity_date: datetime
    activity_data: dict[str, Any]


@dataclass
class DealRecord:
    """CRM deal record."""
    deal_title: str
    deal_value: Decimal
    deal_currency: str
    deal_status: str
    deal_phase: str | None
    probability: int
    expected_close_date: date | None
    actual_close_date: date | None


@dataclass
class IndustrySummary:
    """Industry-level summary."""
    industry_category: str
    nace_code: str | None
    nace_description: str | None
    city: str | None
    company_count: int
    total_pipeline_value: Decimal
    total_won_value_ytd: Decimal
    total_revenue_ytd: Decimal
    total_outstanding: Decimal
    total_overdue: Decimal


@dataclass
class GeographicSummary:
    """Geographic distribution summary."""
    city: str
    total_companies: int
    companies_with_crm: int
    companies_with_financials: int
    total_pipeline: Decimal
    total_revenue_ytd: Decimal
    total_outstanding: Decimal
    market_penetration_pct: float
    province: str = ""  # Kept for backward compatibility, may be empty


class Unified360Service:
    """Service for unified 360° customer view queries."""

    def __init__(self, pool: asyncpg.Pool | None = None, database_url: str | None = None):
        self._pool = pool
        self._database_url = database_url
        self._owned_pool = pool is None

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool."""
        if self._pool is None:
            if not self._database_url:
                raise ValueError("Either pool or database_url must be provided")
            self._pool = await asyncpg.create_pool(
                self._database_url, 
                min_size=1, 
                max_size=3
            )
        return self._pool

    async def close(self) -> None:
        """Close the connection pool if owned."""
        if self._owned_pool and self._pool:
            await self._pool.close()
            self._pool = None

    async def get_company_360_profile(
        self, 
        kbo_number: str | None = None,
        company_uid: str | None = None
    ) -> Company360Profile | None:
        """Get complete 360° profile for a company.
        
        Args:
            kbo_number: KBO number to look up
            company_uid: Or use company UID instead
            
        Returns:
            Company360Profile or None if not found
        """
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            if kbo_number:
                row = await conn.fetchrow(
                    "SELECT * FROM unified_company_360 WHERE kbo_number = $1",
                    kbo_number
                )
            elif company_uid:
                row = await conn.fetchrow(
                    "SELECT * FROM unified_company_360 WHERE company_uid = $1",
                    company_uid
                )
            else:
                raise ValueError("Either kbo_number or company_uid must be provided")

            if not row:
                return None

            profile = Company360Profile(
                company_uid=row['company_uid'],
                kbo_number=row['kbo_number'],
                vat_number=row['vat_number'],
                kbo_company_name=row['kbo_company_name'],
                legal_form=row['legal_form'],
                nace_code=row['nace_code'],
                nace_description=row['nace_description'],
                kbo_status=row['kbo_status'],
                kbo_city=row['kbo_city'],
                website_url=row['website_url'],
                employee_count=row['employee_count'],
                tl_company_id=row['tl_company_id'],
                tl_company_name=row['tl_company_name'],
                tl_status=row['tl_status'],
                tl_customer_type=row['tl_customer_type'],
                tl_email=row['tl_email'],
                tl_phone=row['tl_phone'],
                exact_customer_id=row['exact_customer_id'],
                exact_company_name=row['exact_company_name'],
                exact_status=row['exact_status'],
                exact_credit_line=row['exact_credit_line'],
                exact_payment_terms=row['exact_payment_terms'],
                exact_account_manager=row['exact_account_manager'],
                identity_link_status=row['identity_link_status'],
                last_updated_at=row['last_updated_at']
            )

            # Load pipeline data
            pipeline_row = await conn.fetchrow(
                """
                SELECT * FROM unified_pipeline_revenue 
                WHERE kbo_number = $1
                """,
                row['kbo_number']
            )
            
            if pipeline_row:
                profile.pipeline = PipelineSummary(
                    open_deals_count=pipeline_row['tl_open_deals'] or 0,
                    open_deals_value=pipeline_row['tl_pipeline_value'] or Decimal('0'),
                    won_deals_ytd=pipeline_row['tl_won_deals_ytd'] or 0,
                    won_value_ytd=pipeline_row['tl_won_value_ytd'] or Decimal('0')
                )
                profile.financials = FinancialSummary(
                    revenue_ytd=pipeline_row['exact_revenue_ytd'] or Decimal('0'),
                    revenue_total=pipeline_row['exact_revenue_total'] or Decimal('0'),
                    outstanding_amount=pipeline_row['exact_outstanding'] or Decimal('0'),
                    overdue_amount=pipeline_row['exact_overdue'] or Decimal('0')
                )

            return profile

    async def find_companies_with_pipeline(
        self,
        nace_codes: list[str] | None = None,
        nace_prefix: str | None = None,
        city: str | None = None,
        min_pipeline_value: Decimal | None = None,
        min_revenue_ytd: Decimal | None = None,
        has_financial_data: bool | None = None,
        has_crm_data: bool | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """Find companies matching criteria with pipeline/revenue data.
        
        Example: "IT companies in Gent with open deals over €10k"
        
        Args:
            nace_codes: Specific NACE codes to filter
            nace_prefix: NACE code prefix (e.g., '62' for software)
            city: City name (case-insensitive partial match)
            min_pipeline_value: Minimum pipeline value
            min_revenue_ytd: Minimum YTD revenue
            has_financial_data: Filter for companies with Exact data
            has_crm_data: Filter for companies with Teamleader data
            limit: Maximum results
            
        Returns:
            List of matching companies with summary data
        """
        pool = await self._get_pool()
        
        conditions = ["kbo_number IS NOT NULL"]
        params = []
        param_idx = 1

        if nace_codes:
            placeholders = ','.join(f'${i}' for i in range(param_idx, param_idx + len(nace_codes)))
            conditions.append(f"nace_code IN ({placeholders})")
            params.extend(nace_codes)
            param_idx += len(nace_codes)

        if nace_prefix:
            conditions.append(f"nace_code LIKE ${param_idx}")
            params.append(f"{nace_prefix}%")
            param_idx += 1

        if city:
            conditions.append(f"kbo_city ILIKE ${param_idx}")
            params.append(f"%{city}%")
            param_idx += 1

        if min_pipeline_value:
            conditions.append(f"tl_pipeline_value >= ${param_idx}")
            params.append(min_pipeline_value)
            param_idx += 1

        if min_revenue_ytd:
            conditions.append(f"exact_revenue_ytd >= ${param_idx}")
            params.append(min_revenue_ytd)
            param_idx += 1

        if has_financial_data is not None:
            conditions.append(f"has_financial_data = ${param_idx}")
            params.append(has_financial_data)
            param_idx += 1

        if has_crm_data is not None:
            conditions.append(f"has_crm_data = ${param_idx}")
            params.append(has_crm_data)
            param_idx += 1

        where_clause = " AND ".join(conditions)
        params.append(limit)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT 
                    kbo_number,
                    kbo_company_name,
                    nace_code,
                    nace_description,
                    kbo_city,
                    tl_open_deals,
                    tl_pipeline_value,
                    tl_won_value_ytd,
                    exact_revenue_ytd,
                    exact_outstanding,
                    exact_overdue,
                    has_crm_data,
                    has_financial_data,
                    total_exposure
                FROM unified_pipeline_revenue
                WHERE {where_clause}
                ORDER BY total_exposure DESC NULLS LAST
                LIMIT ${param_idx}
                """,
                *params
            )

        return [dict(row) for row in rows]

    async def get_industry_pipeline_summary(
        self,
        nace_prefix: str | None = None,
        city: str | None = None,
        limit: int = 50
    ) -> list[IndustrySummary]:
        """Get industry-level pipeline and revenue summary.
        
        Example: "What is the total pipeline value for software companies in Brussels?"
        
        Args:
            nace_prefix: Filter by NACE code prefix (e.g., '62' for software/IT)
            city: Filter by city
            limit: Maximum results
            
        Returns:
            List of industry summaries
        """
        pool = await self._get_pool()
        
        conditions = ["1=1"]
        params = []
        param_idx = 1

        if nace_prefix:
            conditions.append(f"nace_code LIKE ${param_idx}")
            params.append(f"{nace_prefix}%")
            param_idx += 1

        if city:
            conditions.append(f"kbo_city ILIKE ${param_idx}")
            params.append(f"%{city}%")
            param_idx += 1

        where_clause = " AND ".join(conditions)
        params.append(limit)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT 
                    industry_category,
                    nace_code,
                    nace_description,
                    kbo_city,
                    company_count,
                    total_pipeline_value,
                    total_won_value_ytd,
                    total_revenue_ytd,
                    total_outstanding,
                    total_overdue
                FROM industry_pipeline_summary
                WHERE {where_clause}
                ORDER BY total_pipeline_value DESC NULLS LAST
                LIMIT ${param_idx}
                """,
                *params
            )

        return [
            IndustrySummary(
                industry_category=row['industry_category'],
                nace_code=row['nace_code'],
                nace_description=row['nace_description'],
                city=row['kbo_city'],
                company_count=row['company_count'],
                total_pipeline_value=row['total_pipeline_value'] or Decimal('0'),
                total_won_value_ytd=row['total_won_value_ytd'] or Decimal('0'),
                total_revenue_ytd=row['total_revenue_ytd'] or Decimal('0'),
                total_outstanding=row['total_outstanding'] or Decimal('0'),
                total_overdue=row['total_overdue'] or Decimal('0')
            )
            for row in rows
        ]

    async def get_geographic_distribution(
        self,
        min_companies: int = 1,
        limit: int = 100
    ) -> list[GeographicSummary]:
        """Get geographic distribution of companies with data coverage.
        
        Args:
            min_companies: Minimum number of companies to include
            limit: Maximum results
            
        Returns:
            List of geographic summaries
        """
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    city,
                    total_companies,
                    companies_with_crm,
                    companies_with_financials,
                    total_pipeline,
                    total_revenue_ytd,
                    total_outstanding,
                    market_penetration_pct
                FROM geographic_revenue_distribution
                WHERE total_companies >= $1
                ORDER BY total_revenue_ytd DESC NULLS LAST
                LIMIT $2
                """,
                min_companies,
                limit
            )

        return [
            GeographicSummary(
                city=row['city'],
                province="",
                total_companies=row['total_companies'],
                companies_with_crm=row['companies_with_crm'],
                companies_with_financials=row['companies_with_financials'],
                total_pipeline=row['total_pipeline'] or Decimal('0'),
                total_revenue_ytd=row['total_revenue_ytd'] or Decimal('0'),
                total_outstanding=row['total_outstanding'] or Decimal('0'),
                market_penetration_pct=row['market_penetration_pct'] or 0.0
            )
            for row in rows
        ]

    async def get_company_activity_timeline(
        self,
        kbo_number: str,
        limit: int = 50,
        activity_types: list[str] | None = None
    ) -> list[ActivityRecord]:
        """Get chronological activity timeline for a company.
        
        Args:
            kbo_number: KBO number
            limit: Maximum activities to return
            activity_types: Filter by activity types
            
        Returns:
            List of activity records
        """
        pool = await self._get_pool()
        
        conditions = ["kbo_number = $1"]
        params = [kbo_number]
        param_idx = 2

        if activity_types:
            placeholders = ','.join(f'${i}' for i in range(param_idx, param_idx + len(activity_types)))
            conditions.append(f"activity_type IN ({placeholders})")
            params.extend(activity_types)
            param_idx += len(activity_types)

        where_clause = " AND ".join(conditions)
        params.append(limit)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT 
                    source_system,
                    activity_type,
                    activity_description,
                    activity_date,
                    activity_data
                FROM company_activity_timeline
                WHERE {where_clause}
                ORDER BY activity_date DESC
                LIMIT ${param_idx}
                """,
                *params
            )

        return [
            ActivityRecord(
                source_system=row['source_system'],
                activity_type=row['activity_type'],
                activity_description=row['activity_description'],
                activity_date=row['activity_date'],
                activity_data=row['activity_data']
            )
            for row in rows
        ]

    async def get_high_value_accounts(
        self,
        min_exposure: Decimal | None = None,
        account_priority: str | None = None,
        limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get high-value accounts with risk/opportunity indicators.
        
        Args:
            min_exposure: Minimum total exposure (pipeline + outstanding)
            account_priority: Filter by priority ('high_risk', 'high_opportunity', etc.)
            limit: Maximum results
            
        Returns:
            List of high-value account records
        """
        pool = await self._get_pool()
        
        conditions = ["1=1"]
        params = []
        param_idx = 1

        if min_exposure:
            conditions.append(f"total_exposure >= ${param_idx}")
            params.append(min_exposure)
            param_idx += 1

        if account_priority:
            conditions.append(f"account_priority = ${param_idx}")
            params.append(account_priority)
            param_idx += 1

        where_clause = " AND ".join(conditions)
        params.append(limit)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT 
                    kbo_number,
                    kbo_company_name,
                    nace_code,
                    kbo_city,
                    tl_open_deals,
                    tl_pipeline_value,
                    exact_revenue_ytd,
                    exact_outstanding,
                    exact_overdue,
                    total_exposure,
                    account_priority,
                    data_completeness_score,
                    exact_account_manager
                FROM high_value_accounts
                WHERE {where_clause}
                ORDER BY total_exposure DESC
                LIMIT ${param_idx}
                """,
                *params
            )

        return [dict(row) for row in rows]

    async def get_identity_link_quality(self) -> list[dict[str, Any]]:
        """Get identity link quality metrics for all sources.
        
        Returns:
            List of quality metrics per source system
        """
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM identity_link_quality")

        return [dict(row) for row in rows]

    async def search_companies_unified(
        self,
        query: str,
        search_fields: list[str] | None = None,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """Search across all company data sources.
        
        Args:
            query: Search query string
            search_fields: Fields to search (default: company names)
            limit: Maximum results
            
        Returns:
            List of matching companies with source info
        """
        pool = await self._get_pool()
        
        # Default search on KBO company names
        search_pattern = f"%{query}%"
        
        async with pool.acquire() as conn:
            # Search unified view
            rows = await conn.fetch(
                """
                SELECT 
                    company_uid,
                    kbo_number,
                    kbo_company_name,
                    tl_company_name,
                    exact_company_name,
                    nace_code,
                    kbo_city,
                    identity_link_status,
                    last_updated_at
                FROM unified_company_360
                WHERE 
                    kbo_company_name ILIKE $1
                    OR tl_company_name ILIKE $1
                    OR exact_company_name ILIKE $1
                    OR kbo_number ILIKE $1
                ORDER BY 
                    CASE 
                        WHEN kbo_company_name ILIKE $2 THEN 1
                        WHEN tl_company_name ILIKE $2 THEN 2
                        WHEN exact_company_name ILIKE $2 THEN 3
                        ELSE 4
                    END,
                    kbo_company_name
                LIMIT $3
                """,
                search_pattern,
                query,  # Exact match priority
                limit
            )

        return [dict(row) for row in rows]
