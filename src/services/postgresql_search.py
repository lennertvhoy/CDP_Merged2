"""PostgreSQL Search Service for CDP_Merged - Primary query plane for chatbot.

This module provides comprehensive search, aggregation, and analytics capabilities
using PostgreSQL as the authoritative data source. It replaces the Tracardi-first
query path with a PostgreSQL-backed deterministic query plane.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from src.core.logger import get_logger
from src.services.postgresql_client_optimized import (
    get_postgresql_client,
)

logger = get_logger(__name__)

COUNT_QUERY_TIMEOUT_SECONDS = 8.0
SEARCH_QUERY_TIMEOUT_SECONDS = 8.0

CITY_VARIANTS: dict[str, list[str]] = {
    "gent": ["Gent", "Ghent", "Gand"],
    "ghent": ["Gent", "Ghent", "Gand"],
    "gand": ["Gent", "Ghent", "Gand"],
    "antwerp": ["Antwerp", "Antwerpen", "Anvers"],
    "antwerpen": ["Antwerp", "Antwerpen", "Anvers"],
    "anvers": ["Antwerp", "Antwerpen", "Anvers"],
    "brussels": ["Brussels", "Brussel", "Bruxelles"],
    "brussel": ["Brussels", "Brussel", "Bruxelles"],
    "bruxelles": ["Brussels", "Brussel", "Bruxelles"],
    "sint-niklaas": ["Sint-Niklaas", "Sint Niklaas", "Saint-Nicolas", "Saint Nicolas"],
    "sint niklaas": ["Sint-Niklaas", "Sint Niklaas", "Saint-Nicolas", "Saint Nicolas"],
    "saint-nicolas": ["Sint-Niklaas", "Sint Niklaas", "Saint-Nicolas", "Saint Nicolas"],
    "saint nicolas": ["Sint-Niklaas", "Sint Niklaas", "Saint-Nicolas", "Saint Nicolas"],
}

STATUS_ALL_MARKERS = {"*", "all", "any"}


@dataclass
class CompanySearchFilters:
    """Search filters for company queries.

    Matches the interface expected by the AI chatbot tools.
    """

    keywords: str | None = None
    enterprise_number: str | None = None
    nace_codes: list[str] | None = None
    juridical_codes: list[str] | None = None
    city: str | None = None
    zip_code: str | None = None
    status: str | None = None
    min_start_date: str | None = None
    has_phone: bool | None = None
    has_email: bool | None = None
    email_domain: str | None = None
    limit: int = 100
    offset: int = 0


class PostgreSQLSearchService:
    """Primary search service using PostgreSQL as the authoritative source.

    This service provides:
    - Full-text search with multiple filter criteria
    - Aggregations and analytics
    - Count queries for segmentation
    - Consistent, deterministic results from PostgreSQL
    """

    def __init__(self) -> None:
        """Initialize the search service."""
        self._client = get_postgresql_client()

    @staticmethod
    def _normalize_email_domain(email_domain: str | None) -> str | None:
        if not email_domain:
            return None

        normalized = email_domain.strip().lower()
        if normalized.startswith("@"):
            normalized = normalized[1:]
        if "@" in normalized:
            normalized = normalized.split("@", 1)[1]
        return normalized or None

    async def ensure_connected(self) -> None:
        """Ensure database connection is established."""
        try:
            await self._client.ensure_connected()
        except Exception as e:
            # Provide detailed error context for debugging
            error_type = type(e).__name__
            error_msg = str(e) or repr(e) or "Connection failed"
            logger.error(
                "postgresql_search_connection_failed",
                error=error_msg,
                error_type=error_type,
                error_repr=repr(e),
            )
            raise RuntimeError(f"PostgreSQL connection failed ({error_type}): {error_msg}") from e

    async def readiness_probe(self) -> dict[str, Any]:
        """Run a lightweight probe for the PostgreSQL-backed query plane."""
        await self.ensure_connected()

        pool = self._client.pool
        assert pool is not None

        async with pool.acquire() as conn:
            db_ping = await conn.fetchval("SELECT 1")
            companies_table = await conn.fetchval("SELECT to_regclass('public.companies')::text")

        if db_ping != 1:
            raise RuntimeError("PostgreSQL ping failed")

        if companies_table != "companies":
            raise RuntimeError("companies table is unavailable")

        return {
            "status": "ok",
            "backend": "postgresql",
            "db_ping": db_ping,
            "companies_table": companies_table,
        }

    @staticmethod
    def _city_candidates(city: str) -> list[str]:
        """Return deduplicated city variants for index-friendly equality filtering."""
        raw = city.strip()
        if not raw:
            return []

        variants = CITY_VARIANTS.get(raw.lower(), [])
        ordered = [raw, raw.title(), *variants]
        seen: set[str] = set()
        candidates: list[str] = []
        for value in ordered:
            candidate = value.strip()
            if not candidate:
                continue
            lowered = candidate.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            candidates.append(candidate)
        return candidates

    @staticmethod
    async def _estimate_total_companies(conn) -> int:
        """Fast estimate fallback for unfiltered counts when exact count times out."""
        estimate = await conn.fetchval(
            """
            SELECT GREATEST(
                COALESCE((SELECT reltuples::bigint FROM pg_class WHERE oid = 'companies'::regclass), 0),
                COALESCE((SELECT n_live_tup::bigint FROM pg_stat_user_tables WHERE relname = 'companies'), 0)
            )
            """
        )
        return int(estimate or 0)

    @staticmethod
    async def _companies_table_has_rows(conn) -> bool:
        """Cheap existence probe used to distinguish empty datasets from filtered zero results."""
        return bool(await conn.fetchval("SELECT EXISTS (SELECT 1 FROM companies LIMIT 1)"))

    @staticmethod
    def _normalize_status_filter(status: str | None) -> str | None:
        """Normalize status filter values and skip explicit "all" markers."""
        if status is None:
            return None

        normalized = status.strip()
        if not normalized:
            return None

        if normalized.lower() in STATUS_ALL_MARKERS:
            return None

        return normalized.upper()

    def _build_where_clause(self, filters: CompanySearchFilters) -> tuple[str, list[Any]]:
        """Build parameterized WHERE clause from filters.

        Args:
            filters: Search filters

        Returns:
            Tuple of (where_clause, params)
        """
        conditions: list[str] = []
        params: list[Any] = []
        param_idx = 0

        def next_param() -> str:
            nonlocal param_idx
            param_idx += 1
            return f"${param_idx}"

        # Keyword search on company name
        if filters.keywords:
            conditions.append(f"company_name ILIKE {next_param()}")
            params.append(f"%{filters.keywords}%")

        # Enterprise number (KBO) - normalize by removing dots and spaces
        if filters.enterprise_number:
            clean = filters.enterprise_number.replace(".", "").replace(" ", "")
            conditions.append(f"kbo_number = {next_param()}")
            params.append(clean)

        # NACE codes (industry classification)
        # Check both primary column and all_nace_codes array for completeness
        if filters.nace_codes:
            placeholders = ", ".join([next_param() for _ in filters.nace_codes])
            nace_placeholders_arr = ", ".join([next_param() for _ in filters.nace_codes])
            conditions.append(
                f"(industry_nace_code IN ({placeholders}) OR all_nace_codes && ARRAY[{nace_placeholders_arr}]::varchar[])"
            )
            params.extend(filters.nace_codes)  # For IN clause
            params.extend(filters.nace_codes)  # For && array overlap

        # Juridical codes (legal form)
        if filters.juridical_codes:
            placeholders = ", ".join([next_param() for _ in filters.juridical_codes])
            conditions.append(f"legal_form IN ({placeholders})")
            params.extend(filters.juridical_codes)

        # City filter
        if filters.city:
            candidates = self._city_candidates(filters.city)
            if candidates:
                placeholders = ", ".join(next_param() for _ in candidates)
                conditions.append(f"city IN ({placeholders})")
                params.extend(candidates)

        # Postal code filter
        if filters.zip_code:
            conditions.append(f"postal_code = {next_param()}")
            params.append(filters.zip_code)

        # Business status filter (for example AC = active company)
        normalized_status = self._normalize_status_filter(filters.status)
        if normalized_status:
            conditions.append(f"status = {next_param()}")
            params.append(normalized_status)

        # Founding date filter used by chatbot/start-date prompts
        if filters.min_start_date:
            conditions.append(f"founded_date >= {next_param()}::date")
            params.append(date.fromisoformat(filters.min_start_date))

        # Has phone filter
        if filters.has_phone:
            conditions.append("main_phone IS NOT NULL AND main_phone != ''")

        # Has email filter
        if filters.has_email:
            conditions.append("main_email IS NOT NULL AND main_email != ''")

        normalized_email_domain = self._normalize_email_domain(filters.email_domain)
        if normalized_email_domain:
            conditions.append(f"LOWER(SPLIT_PART(main_email, '@', 2)) = LOWER({next_param()})")
            params.append(normalized_email_domain)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params

    async def search_companies(
        self,
        filters: CompanySearchFilters,
    ) -> dict[str, Any]:
        """Search companies with comprehensive filters.

        This is the primary search method that replaces Tracardi search_profiles.

        Args:
            filters: Search filters

        Returns:
            Dict with total count, results, and metadata
        """
        try:
            await self.ensure_connected()
        except Exception as conn_exc:
            logger.error(
                "search_companies_connection_failed",
                error=str(conn_exc),
                error_type=type(conn_exc).__name__,
            )
            raise RuntimeError(f"Failed to connect for search: {conn_exc}") from conn_exc

        where_clause, params = self._build_where_clause(filters)

        # Build count query
        count_sql = f"""
            SELECT COUNT(*)
            FROM companies
            WHERE {where_clause}
        """

        # Build search query with all fields
        search_sql = f"""
            SELECT
                id,
                kbo_number,
                vat_number,
                company_name,
                legal_form,
                status,
                street_address,
                city,
                postal_code,
                country,
                geo_latitude,
                geo_longitude,
                industry_nace_code,
                nace_description,
                company_size,
                employee_count,
                revenue_range,
                founding_year,
                website_url,
                main_phone,
                main_email,
                ai_description,
                source,
                created_at,
                updated_at,
                last_sync_at,
                sync_status
            FROM companies
            WHERE {where_clause}
            ORDER BY company_name
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """

        pool = self._client.pool
        assert pool is not None

        async with pool.acquire() as conn:
            count_is_estimated = False
            count_source = "exact_count"
            companies_table_empty = False
            if where_clause == "1=1":
                # Unfiltered counts are too expensive for live prompts; use table stats fast-path.
                total = await self._estimate_total_companies(conn)
                count_is_estimated = True
                count_source = "estimated_reltuples"
                logger.info(
                    "count_query_fast_estimate_unfiltered",
                    estimated_total=total,
                )
            else:
                try:
                    count_row = await conn.fetchrow(
                        count_sql,
                        *params,
                        timeout=COUNT_QUERY_TIMEOUT_SECONDS,
                    )
                    total = int(count_row[0]) if count_row else 0
                except TimeoutError as timeout_exc:
                    raise RuntimeError(
                        "Count query timed out. Please narrow filters and retry."
                    ) from timeout_exc

            if total == 0:
                companies_table_empty = not await self._companies_table_has_rows(conn)

            # Get results
            search_params = params + [filters.limit, filters.offset]
            rows = await conn.fetch(
                search_sql,
                *search_params,
                timeout=SEARCH_QUERY_TIMEOUT_SECONDS,
            )
            results = [dict(row) for row in rows]

            return {
                "total": total,
                "result": results,
                "limit": filters.limit,
                "offset": filters.offset,
                "backend": "postgresql",
                "count_is_estimated": count_is_estimated,
                "count_source": count_source,
                "companies_table_empty": companies_table_empty,
            }

    async def count_companies(
        self,
        filters: CompanySearchFilters,
    ) -> int:
        """Get count of companies matching filters.

        Args:
            filters: Search filters

        Returns:
            Total count
        """
        await self.ensure_connected()

        where_clause, params = self._build_where_clause(filters)

        count_sql = f"""
            SELECT COUNT(*)
            FROM companies
            WHERE {where_clause}
        """

        pool = self._client.pool
        assert pool is not None

        async with pool.acquire() as conn:
            row = await conn.fetchrow(count_sql, *params, timeout=COUNT_QUERY_TIMEOUT_SECONDS)
            return row[0] if row else 0

    async def aggregate_by_field(
        self,
        group_by: str,
        filters: CompanySearchFilters | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Aggregate companies by a field with optional filters.

        Args:
            group_by: Field to group by (city, legal_form, industry_nace_code, etc.)
            filters: Optional search filters
            limit: Maximum number of groups

        Returns:
            Dict with aggregation results
        """
        await self.ensure_connected()

        # Map frontend field names to database columns
        field_map = {
            "city": "city",
            "juridical_form": "legal_form",
            "legal_form": "legal_form",
            "nace_code": "industry_nace_code",
            "industry": "industry_nace_code",  # Alias for natural language queries
            "nace_description": "nace_description",
            "status": "status",
            "zip_code": "postal_code",
        }

        db_field = field_map.get(group_by, group_by)

        where_clause = "1=1"
        params: list[Any] = []

        if filters:
            where_clause, params = self._build_where_clause(filters)

        # Build aggregation query
        agg_sql = f"""
            SELECT
                COALESCE({db_field}, 'Unknown') as group_value,
                COUNT(*) as count,
                COUNT(CASE WHEN main_email IS NOT NULL AND main_email != '' THEN 1 END) as with_email,
                COUNT(CASE WHEN main_phone IS NOT NULL AND main_phone != '' THEN 1 END) as with_phone
            FROM companies
            WHERE {where_clause}
            GROUP BY {db_field}
            ORDER BY count DESC
            LIMIT ${len(params) + 1}
        """

        # Get total matching count
        count_sql = f"""
            SELECT COUNT(*)
            FROM companies
            WHERE {where_clause}
        """

        pool = self._client.pool
        assert pool is not None

        async with pool.acquire() as conn:
            # Get total
            total_row = await conn.fetchrow(count_sql, *params)
            total = total_row[0] if total_row else 0

            # Get aggregation
            agg_params = params + [limit]
            rows = await conn.fetch(agg_sql, *agg_params)

            groups = []
            for row in rows:
                count = row["count"]
                groups.append(
                    {
                        "group_value": row["group_value"],
                        "count": count,
                        "email_coverage_percent": round((row["with_email"] / count) * 100, 1)
                        if count > 0
                        else 0,
                        "phone_coverage_percent": round((row["with_phone"] / count) * 100, 1)
                        if count > 0
                        else 0,
                        "percent_of_total": round((count / total) * 100, 1) if total > 0 else 0,
                    }
                )

            return {
                "status": "ok",
                "group_by": group_by,
                "total_matching_profiles": total,
                "groups": groups,
                "backend": "postgresql",
            }

    async def get_company_by_kbo(self, kbo_number: str) -> dict[str, Any] | None:
        """Get a single company by KBO number.

        Args:
            kbo_number: KBO/enterprise number

        Returns:
            Company dict or None
        """
        await self.ensure_connected()
        return await self._client.get_profile_by_kbo(kbo_number)

    async def get_company_by_id(self, company_id: str) -> dict[str, Any] | None:
        """Get a single company by ID.

        Args:
            company_id: Company UUID

        Returns:
            Company dict or None
        """
        await self.ensure_connected()

        query = """
            SELECT
                id, kbo_number, vat_number, company_name, legal_form,
                status,
                street_address, city, postal_code, country,
                geo_latitude, geo_longitude,
                industry_nace_code, nace_description,
                company_size, employee_count, revenue_range, founding_year,
                website_url, main_phone, main_email,
                ai_description,
                source, created_at, updated_at,
                last_sync_at, sync_status
            FROM companies
            WHERE id = $1
        """

        pool = self._client.pool
        assert pool is not None

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, company_id)
            return dict(row) if row else None

    async def get_coverage_stats(self) -> dict[str, Any]:
        """Get data coverage statistics for the companies table.

        Returns:
            Dict with coverage statistics
        """
        await self.ensure_connected()

        stats_sql = """
            SELECT
                COUNT(*) as total_companies,
                COUNT(CASE WHEN main_email IS NOT NULL AND main_email != '' THEN 1 END) as with_email,
                COUNT(CASE WHEN main_phone IS NOT NULL AND main_phone != '' THEN 1 END) as with_phone,
                COUNT(CASE WHEN website_url IS NOT NULL AND website_url != '' THEN 1 END) as with_website,
                COUNT(CASE WHEN geo_latitude IS NOT NULL THEN 1 END) as with_geocoding,
                COUNT(CASE WHEN industry_nace_code IS NOT NULL THEN 1 END) as with_nace,
                COUNT(CASE WHEN ai_description IS NOT NULL THEN 1 END) as with_ai_description,
                COUNT(CASE WHEN legal_form IS NOT NULL THEN 1 END) as with_legal_form
            FROM companies
        """

        pool = self._client.pool
        assert pool is not None

        async with pool.acquire() as conn:
            row = await conn.fetchrow(stats_sql)
            if not row:
                return {"status": "error", "message": "Failed to get stats"}

            total = row["total_companies"]
            return {
                "status": "ok",
                "total_companies": total,
                "coverage": {
                    "email": {
                        "count": row["with_email"],
                        "percent": round((row["with_email"] / total) * 100, 2) if total > 0 else 0,
                    },
                    "phone": {
                        "count": row["with_phone"],
                        "percent": round((row["with_phone"] / total) * 100, 2) if total > 0 else 0,
                    },
                    "website": {
                        "count": row["with_website"],
                        "percent": round((row["with_website"] / total) * 100, 2)
                        if total > 0
                        else 0,
                    },
                    "geocoding": {
                        "count": row["with_geocoding"],
                        "percent": round((row["with_geocoding"] / total) * 100, 2)
                        if total > 0
                        else 0,
                    },
                    "nace_code": {
                        "count": row["with_nace"],
                        "percent": round((row["with_nace"] / total) * 100, 2) if total > 0 else 0,
                    },
                    "ai_description": {
                        "count": row["with_ai_description"],
                        "percent": round((row["with_ai_description"] / total) * 100, 2)
                        if total > 0
                        else 0,
                    },
                    "legal_form": {
                        "count": row["with_legal_form"],
                        "percent": round((row["with_legal_form"] / total) * 100, 2)
                        if total > 0
                        else 0,
                    },
                },
                "backend": "postgresql",
            }


# Singleton instance
_search_service: PostgreSQLSearchService | None = None


def get_search_service() -> PostgreSQLSearchService:
    """Get or create singleton search service instance."""
    global _search_service
    if _search_service is None:
        _search_service = PostgreSQLSearchService()
    return _search_service


async def close_search_service() -> None:
    """Close the search service and its connections."""
    global _search_service
    if _search_service:
        await _search_service._client.disconnect()
        _search_service = None
