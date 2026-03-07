"""Canonical PostgreSQL-first segment storage and retrieval."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from src.core.logger import get_logger
from src.services.postgresql_search import COUNT_QUERY_TIMEOUT_SECONDS, CompanySearchFilters
from src.services.postgresql_search import get_search_service
from src.services.runtime_support_schema import ensure_runtime_support_schema

logger = get_logger(__name__)

MAX_CANONICAL_SEGMENT_MEMBERS = 100_000

COMPANY_SEGMENT_FIELDS = """
    c.id::text AS id,
    c.kbo_number,
    c.vat_number,
    c.company_name,
    c.legal_form,
    c.status,
    c.street_address,
    c.city,
    c.postal_code,
    c.country,
    c.geo_latitude,
    c.geo_longitude,
    c.industry_nace_code,
    c.nace_description,
    c.company_size,
    c.employee_count,
    c.revenue_range,
    c.founding_year,
    c.website_url,
    c.main_phone,
    c.main_email,
    c.ai_description,
    c.source,
    c.created_at,
    c.updated_at,
    c.last_sync_at,
    c.sync_status
"""


def _slugify_segment_key(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    slug = slug.strip("-")[:100]
    return slug or "segment"


def _filters_are_empty(filters: CompanySearchFilters) -> bool:
    return not any(
        [
            filters.keywords,
            filters.enterprise_number,
            filters.nace_codes,
            filters.juridical_codes,
            filters.city,
            filters.zip_code,
            filters.status,
            filters.min_start_date,
            filters.has_phone is True,
            filters.has_email is True,
            filters.email_domain,
        ]
    )


def _serialize_filters(filters: CompanySearchFilters) -> dict[str, Any]:
    payload = {
        "keywords": filters.keywords,
        "enterprise_number": filters.enterprise_number,
        "nace_codes": list(filters.nace_codes or []),
        "juridical_codes": list(filters.juridical_codes or []),
        "city": filters.city,
        "zip_code": filters.zip_code,
        "status": filters.status,
        "min_start_date": filters.min_start_date,
        "has_phone": filters.has_phone,
        "has_email": filters.has_email,
        "email_domain": filters.email_domain,
    }
    return {key: value for key, value in payload.items() if value not in (None, "", [])}


class CanonicalSegmentService:
    """Persist and read authoritative segments from PostgreSQL."""

    def __init__(self, search_service=None) -> None:
        self.search_service = search_service or get_search_service()

    async def _ensure_ready(self) -> None:
        await self.search_service.ensure_connected()
        await ensure_runtime_support_schema(self.search_service._client)

    async def _resolve_segment(self, segment_ref: str) -> dict[str, Any] | None:
        await self._ensure_ready()
        pool = self.search_service._client.pool
        assert pool is not None

        query = """
            SELECT
                segment_id::text AS segment_id,
                segment_key,
                segment_name,
                description,
                definition_type,
                definition_json
            FROM segment_definitions
            WHERE is_active = TRUE
              AND (segment_key = $1 OR segment_name = $1 OR segment_id::text = $1)
            ORDER BY
                CASE
                    WHEN segment_key = $1 THEN 0
                    WHEN segment_name = $1 THEN 1
                    ELSE 2
                END
            LIMIT 1
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, segment_ref)
            return dict(row) if row else None

    async def upsert_segment(
        self,
        *,
        name: str,
        filters: CompanySearchFilters,
        condition: str | None = None,
        description: str | None = None,
        owner: str = "chatbot",
    ) -> dict[str, Any]:
        """Create or refresh a canonical segment from deterministic PostgreSQL filters."""

        if _filters_are_empty(filters):
            raise ValueError("Refine the search before creating a canonical segment.")

        await self._ensure_ready()
        pool = self.search_service._client.pool
        assert pool is not None

        where_clause, params = self.search_service._build_where_clause(filters)
        segment_key = _slugify_segment_key(name)
        filters_payload = _serialize_filters(filters)
        definition_payload = {
            "source": "chatbot_search_tool",
            "tql": condition,
            "filters": filters_payload,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        membership_reason = {
            "source": "chatbot_search_tool",
            "filters": filters_payload,
            "tql": condition,
        }

        count_sql = f"""
            SELECT COUNT(*)
            FROM companies
            WHERE {where_clause}
        """

        upsert_sql = """
            INSERT INTO segment_definitions (
                segment_key,
                segment_name,
                description,
                definition_type,
                definition_json,
                owner,
                is_active,
                updated_at
            ) VALUES ($1, $2, $3, $4, $5::jsonb, $6, TRUE, CURRENT_TIMESTAMP)
            ON CONFLICT (segment_key)
            DO UPDATE SET
                segment_name = EXCLUDED.segment_name,
                description = EXCLUDED.description,
                definition_type = EXCLUDED.definition_type,
                definition_json = EXCLUDED.definition_json,
                owner = EXCLUDED.owner,
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP
            RETURNING segment_id::text AS segment_id, segment_key, segment_name
        """

        async with pool.acquire() as conn:
            count_row = await conn.fetchrow(
                count_sql,
                *params,
                timeout=COUNT_QUERY_TIMEOUT_SECONDS,
            )
            member_count = int(count_row[0] or 0) if count_row else 0

            if member_count > MAX_CANONICAL_SEGMENT_MEMBERS:
                raise ValueError(
                    "Search is too broad for a canonical segment. Narrow the filters and retry."
                )

            async with conn.transaction():
                segment_row = await conn.fetchrow(
                    upsert_sql,
                    segment_key,
                    name,
                    description,
                    "metadata",
                    json.dumps(definition_payload),
                    owner,
                )
                assert segment_row is not None
                segment_id = segment_row["segment_id"]

                await conn.execute("DELETE FROM segment_memberships WHERE segment_id = $1::uuid", segment_id)

                insert_membership_sql = f"""
                    INSERT INTO segment_memberships (
                        segment_id,
                        uid,
                        calculated_at,
                        membership_reason,
                        projected_to_tracardi
                    )
                    SELECT
                        ${len(params) + 1}::uuid,
                        id::text,
                        CURRENT_TIMESTAMP,
                        ${len(params) + 2}::jsonb,
                        FALSE
                    FROM companies
                    WHERE {where_clause}
                """
                await conn.execute(
                    insert_membership_sql,
                    *params,
                    segment_id,
                    json.dumps(membership_reason),
                )

        logger.info(
            "canonical_segment_upserted",
            segment_key=segment_key,
            segment_name=name,
            member_count=member_count,
        )
        return {
            "segment_id": segment_id,
            "segment_key": segment_key,
            "segment_name": name,
            "member_count": member_count,
            "filters": filters_payload,
            "backend": "postgresql",
        }

    async def get_segment_members(
        self,
        segment_ref: str,
        *,
        limit: int = 1000,
        offset: int = 0,
    ) -> dict[str, Any] | None:
        """Return canonical segment members with authoritative company fields."""

        segment = await self._resolve_segment(segment_ref)
        if segment is None:
            return None

        pool = self.search_service._client.pool
        assert pool is not None

        bounded_limit = max(1, min(limit, 10_000))
        count_sql = "SELECT COUNT(*) FROM segment_memberships WHERE segment_id = $1::uuid"
        members_sql = f"""
            SELECT {COMPANY_SEGMENT_FIELDS}
            FROM segment_memberships sm
            JOIN companies c ON c.id::text = sm.uid
            WHERE sm.segment_id = $1::uuid
            ORDER BY c.company_name
            LIMIT $2 OFFSET $3
        """

        async with pool.acquire() as conn:
            count_row = await conn.fetchrow(count_sql, segment["segment_id"])
            total_count = int(count_row[0] or 0) if count_row else 0
            rows = await conn.fetch(members_sql, segment["segment_id"], bounded_limit, offset)

        return {
            "segment_id": segment["segment_id"],
            "segment_key": segment["segment_key"],
            "segment_name": segment["segment_name"],
            "description": segment.get("description"),
            "total_count": total_count,
            "rows": [dict(row) for row in rows],
            "backend": "postgresql",
        }

    async def get_segment_stats(self, segment_ref: str) -> dict[str, Any] | None:
        """Return authoritative statistics for a canonical PostgreSQL segment."""

        segment = await self._resolve_segment(segment_ref)
        if segment is None:
            return None

        pool = self.search_service._client.pool
        assert pool is not None

        base_where = "sm.segment_id = $1::uuid"
        totals_sql = f"""
            SELECT
                COUNT(*) AS total_count,
                COUNT(CASE WHEN c.main_email IS NOT NULL AND c.main_email != '' THEN 1 END) AS email_count,
                COUNT(CASE WHEN c.main_phone IS NOT NULL AND c.main_phone != '' THEN 1 END) AS phone_count
            FROM segment_memberships sm
            JOIN companies c ON c.id::text = sm.uid
            WHERE {base_where}
        """
        city_sql = f"""
            SELECT COALESCE(c.city, 'Unknown') AS label, COUNT(*) AS count
            FROM segment_memberships sm
            JOIN companies c ON c.id::text = sm.uid
            WHERE {base_where}
            GROUP BY COALESCE(c.city, 'Unknown')
            ORDER BY count DESC
            LIMIT 10
        """
        status_sql = f"""
            SELECT COALESCE(c.status, 'Unknown') AS label, COUNT(*) AS count
            FROM segment_memberships sm
            JOIN companies c ON c.id::text = sm.uid
            WHERE {base_where}
            GROUP BY COALESCE(c.status, 'Unknown')
            ORDER BY count DESC
        """
        legal_form_sql = f"""
            SELECT COALESCE(c.legal_form, 'Unknown') AS label, COUNT(*) AS count
            FROM segment_memberships sm
            JOIN companies c ON c.id::text = sm.uid
            WHERE {base_where}
            GROUP BY COALESCE(c.legal_form, 'Unknown')
            ORDER BY count DESC
            LIMIT 5
        """

        async with pool.acquire() as conn:
            totals_row = await conn.fetchrow(totals_sql, segment["segment_id"])
            city_rows = await conn.fetch(city_sql, segment["segment_id"])
            status_rows = await conn.fetch(status_sql, segment["segment_id"])
            legal_form_rows = await conn.fetch(legal_form_sql, segment["segment_id"])

        total_count = int(totals_row["total_count"] or 0) if totals_row else 0
        email_count = int(totals_row["email_count"] or 0) if totals_row else 0
        phone_count = int(totals_row["phone_count"] or 0) if totals_row else 0

        return {
            "status": "ok",
            "segment_id": segment["segment_name"],
            "segment_key": segment["segment_key"],
            "profile_count": total_count,
            "sample_analyzed": total_count,
            "note": "Stats from PostgreSQL canonical segment.",
            "contact_coverage": {
                "email_coverage_percent": round((email_count / total_count) * 100, 1)
                if total_count
                else 0,
                "phone_coverage_percent": round((phone_count / total_count) * 100, 1)
                if total_count
                else 0,
                "profiles_with_email": email_count,
                "profiles_with_phone": phone_count,
            },
            "top_cities": [
                {"city": row["label"], "count": int(row["count"] or 0)} for row in city_rows
            ],
            "status_distribution": {
                row["label"]: int(row["count"] or 0) for row in status_rows
            },
            "juridical_form_distribution": {
                row["label"]: int(row["count"] or 0) for row in legal_form_rows
            },
            "backend": "postgresql",
        }


__all__ = ["CanonicalSegmentService", "MAX_CANONICAL_SEGMENT_MEMBERS"]
