"""
Projection Service - PostgreSQL to Tracardi Projection

Implements the projection contract defined in docs/PROJECTION_CONTRACT.md.
Responsible for projecting profiles, traits, and segments from PostgreSQL
to Tracardi in a PII-light, auditable manner.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from src.core.logger import get_logger
from src.services.postgresql_client import PostgreSQLClient
from src.services.tracardi import TracardiClient

logger = get_logger(__name__)


class ProjectionStatus(Enum):
    """Status of a projection operation."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # No changes to project


@dataclass
class ProjectionResult:
    """Result of a projection operation."""

    uid: str
    status: ProjectionStatus
    tracardi_profile_id: str | None = None
    error_message: str | None = None
    projected_fields: list[str] | None = None
    projection_hash: str | None = None


@dataclass
class BatchProjectionResult:
    """Result of a batch projection operation."""

    total: int
    success: int
    failed: int
    skipped: int
    results: list[ProjectionResult]


@dataclass
class SegmentProjectionResult:
    """Result of projecting a segment."""

    segment_key: str
    total_members: int
    projected: int
    failed: int
    results: list[ProjectionResult]


@dataclass
class ProjectionState:
    """Current projection state for a UID."""

    uid: str
    target_system: str
    last_projected_at: datetime | None
    projection_hash: str | None
    projection_status: str
    last_error: str | None


class ProjectionService:
    """
    Service for projecting data from PostgreSQL to Tracardi.

    Implements the projection contract:
    - Projects PII-light business traits
    - Maintains projection state for idempotency
    - Handles lazy profile creation
    - Records audit trail
    """

    def __init__(
        self,
        postgresql_client: PostgreSQLClient | None = None,
        tracardi_client: TracardiClient | None = None,
    ):
        self.postgresql = postgresql_client or PostgreSQLClient()
        self.tracardi = tracardi_client or TracardiClient()
        self.target_system = "tracardi"

    async def initialize(self) -> None:
        """Initialize connections."""
        await self.postgresql.connect()
        # Tracardi client initializes on first use via _ensure_token

    async def close(self) -> None:
        """Close connections."""
        await self.postgresql.disconnect()

    def _compute_hash(self, data: dict) -> str:
        """Compute hash of projection payload for idempotency."""
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:32]

    def _build_profile_payload(
        self,
        org: dict[str, Any],
        traits: list[dict[str, Any]] | None = None,
        segments: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Build PII-light projection payload from organization data.

        Excludes actual email/phone values, includes only has_* flags.
        """
        payload: dict[str, Any] = {
            "id": str(org.get("id")) if org.get("id") else None,
            "ids": [org.get("kbo_number")] if org.get("kbo_number") else [],
            "traits": {
                "business": {
                    "legal_name": org.get("company_name"),
                    "legal_form": org.get("legal_form"),
                    "nace_code": org.get("industry_nace_code"),
                    "nace_description": org.get("nace_description"),
                    "city": org.get("city"),
                    "postal_code": org.get("postal_code"),
                    "country": org.get("country", "BE"),
                    "founded_date": founded_date.isoformat()
                    if (founded_date := org.get("founded_date"))
                    else None,
                    "has_email": bool(org.get("main_email")),
                    "has_phone": bool(org.get("main_phone")),
                    "has_website": bool(org.get("website_url")),
                },
                "enrichment": {
                    "sync_status": org.get("sync_status"),
                    "last_sync_at": org.get("last_sync_at"),
                    "employee_count": org.get("employee_count"),
                    "company_size": org.get("company_size"),
                    "revenue_range": org.get("revenue_range"),
                },
            },
        }

        # Add geo location if available
        if org.get("geo_latitude") and org.get("geo_longitude"):
            payload["traits"]["location"] = {
                "latitude": org.get("geo_latitude"),
                "longitude": org.get("geo_longitude"),
                "city": org.get("city"),
            }

        # Add AI traits
        if traits:
            payload["traits"]["ai"] = {
                t.get("trait_name", "unknown"): t.get("trait_value_text")
                or t.get("trait_value_number")
                or t.get("trait_value_boolean")
                for t in traits
            }

        # Add segment memberships
        if segments:
            payload["traits"]["segments"] = segments

        return payload

    async def _get_traits(self, uid: str) -> list[dict[str, Any]]:
        """Fetch traits for a UID from PostgreSQL."""
        await self.postgresql.ensure_connected()
        pool = self.postgresql.pool
        if not pool:
            return []

        query = """
            SELECT trait_name, trait_value_text, trait_value_number,
                   trait_value_boolean, confidence, source_system, effective_at
            FROM profile_traits
            WHERE uid = $1
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
              AND effective_at <= CURRENT_TIMESTAMP
            ORDER BY effective_at DESC
        """

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, uid)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.warning("failed_to_fetch_traits", uid=uid, error=str(e))
            return []

    async def _get_segment_memberships(self, uid: str) -> list[str]:
        """Fetch segment memberships for a UID."""
        await self.postgresql.ensure_connected()
        pool = self.postgresql.pool
        if not pool:
            return []

        query = """
            SELECT sd.segment_key
            FROM segment_memberships sm
            JOIN segment_definitions sd ON sm.segment_id = sd.segment_id
            WHERE sm.uid = $1 AND sd.is_active = TRUE
        """

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, uid)
                return [row["segment_key"] for row in rows]
        except Exception as e:
            logger.warning("failed_to_fetch_segments", uid=uid, error=str(e))
            return []

    async def _get_projection_state(self, uid: str) -> ProjectionState | None:
        """Get last projection state for a UID."""
        await self.postgresql.ensure_connected()
        pool = self.postgresql.pool
        if not pool:
            return None

        query = """
            SELECT uid, target_system, projected_at, projection_hash,
                   projection_status, last_error
            FROM activation_projection_state
            WHERE uid = $1 AND target_system = $2
            ORDER BY projected_at DESC
            LIMIT 1
        """

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, uid, self.target_system)
                if row:
                    return ProjectionState(
                        uid=row["uid"],
                        target_system=row["target_system"],
                        last_projected_at=row["projected_at"],
                        projection_hash=row["projection_hash"],
                        projection_status=row["projection_status"],
                        last_error=row["last_error"],
                    )
        except Exception as e:
            logger.warning("failed_to_fetch_projection_state", uid=uid, error=str(e))
        return None

    async def _record_projection_state(
        self,
        uid: str,
        projection_hash: str,
        status: ProjectionStatus,
        error_message: str | None = None,
    ) -> None:
        """Record projection state in PostgreSQL."""
        await self.postgresql.ensure_connected()
        pool = self.postgresql.pool
        if not pool:
            return

        query = """
            INSERT INTO activation_projection_state (
                uid, target_system, projected_entity_type, projected_entity_key,
                projection_hash, projection_status, last_error, projected_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (target_system, projected_entity_type, projected_entity_key)
            DO UPDATE SET
                projection_hash = EXCLUDED.projection_hash,
                projection_status = EXCLUDED.projection_status,
                last_error = EXCLUDED.last_error,
                projected_at = EXCLUDED.projected_at,
                updated_at = CURRENT_TIMESTAMP
        """

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    uid,
                    self.target_system,
                    "profile",
                    uid,
                    projection_hash,
                    status.value,
                    error_message,
                    datetime.now(UTC).replace(tzinfo=None),
                )
        except Exception as e:
            logger.error("failed_to_record_projection_state", uid=uid, error=str(e))

    async def project_profile(
        self,
        uid: str,
        force: bool = False,
    ) -> ProjectionResult:
        """
        Project a single profile to Tracardi.

        Args:
            uid: The UID to project
            force: If True, project even if no changes detected

        Returns:
            ProjectionResult with status and metadata
        """
        logger.info("projecting_profile", uid=uid, force=force)

        try:
            # 1. Fetch organization from PostgreSQL
            org = await self.postgresql.get_profile_by_id(uid)
            if not org:
                # Try by KBO if ID lookup fails
                org = await self.postgresql.get_profile_by_kbo(uid)

            if not org:
                logger.warning("profile_not_found_in_postgresql", uid=uid)
                return ProjectionResult(
                    uid=uid,
                    status=ProjectionStatus.FAILED,
                    error_message="Profile not found in PostgreSQL",
                )

            # 2. Fetch traits and segments
            traits = await self._get_traits(uid)
            segments = await self._get_segment_memberships(uid)

            # 3. Build projection payload
            payload = self._build_profile_payload(org, traits, segments)
            projection_hash = self._compute_hash(payload)

            # 4. Check if projection needed (idempotency)
            if not force:
                state = await self._get_projection_state(uid)
                if state and state.projection_hash == projection_hash:
                    logger.info("projection_skipped_no_changes", uid=uid)
                    return ProjectionResult(
                        uid=uid,
                        status=ProjectionStatus.SKIPPED,
                        projection_hash=projection_hash,
                    )

            # 5. Project to Tracardi
            result = await self.tracardi.import_profiles([payload])

            if result:
                # 6. Record success
                await self._record_projection_state(
                    uid=uid,
                    projection_hash=projection_hash,
                    status=ProjectionStatus.SUCCESS,
                )

                # 7. Update source_identity_links with Tracardi profile ID
                await self._update_tracardi_link(uid, result.get("id"))

                logger.info("projection_success", uid=uid)
                return ProjectionResult(
                    uid=uid,
                    status=ProjectionStatus.SUCCESS,
                    tracardi_profile_id=result.get("id"),
                    projection_hash=projection_hash,
                    projected_fields=list(payload.get("traits", {}).keys()),
                )
            else:
                # Tracardi returned None (failure)
                error_msg = "Tracardi import returned None"
                await self._record_projection_state(
                    uid=uid,
                    projection_hash=projection_hash,
                    status=ProjectionStatus.FAILED,
                    error_message=error_msg,
                )
                logger.error("projection_failed", uid=uid, error=error_msg)
                return ProjectionResult(
                    uid=uid,
                    status=ProjectionStatus.FAILED,
                    error_message=error_msg,
                )

        except Exception as e:
            logger.error("projection_exception", uid=uid, error=str(e))
            await self._record_projection_state(
                uid=uid,
                projection_hash="",
                status=ProjectionStatus.FAILED,
                error_message=str(e),
            )
            return ProjectionResult(
                uid=uid,
                status=ProjectionStatus.FAILED,
                error_message=str(e),
            )

    async def _update_tracardi_link(self, uid: str, tracardi_profile_id: str | None) -> None:
        """Update source_identity_links with Tracardi profile ID."""
        if not tracardi_profile_id:
            return

        await self.postgresql.ensure_connected()
        pool = self.postgresql.pool
        if not pool:
            return

        query = """
            INSERT INTO source_identity_links (
                uid, subject_type, source_system, source_entity_type,
                source_record_id, tracardi_profile_id, is_primary
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (source_system, source_entity_type, source_record_id)
            DO UPDATE SET
                tracardi_profile_id = EXCLUDED.tracardi_profile_id,
                updated_at = CURRENT_TIMESTAMP
        """

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    uid,
                    "organization",
                    "tracardi_projection",
                    "profile",
                    uid,
                    tracardi_profile_id,
                    True,
                )
        except Exception as e:
            logger.warning("failed_to_update_tracardi_link", uid=uid, error=str(e))

    async def project_batch(
        self,
        uids: list[str],
        batch_size: int = 50,
    ) -> BatchProjectionResult:
        """
        Project multiple profiles to Tracardi.

        Args:
            uids: List of UIDs to project
            batch_size: Number of profiles per batch

        Returns:
            BatchProjectionResult with aggregated results
        """
        logger.info("projecting_batch", total=len(uids), batch_size=batch_size)

        results: list[ProjectionResult] = []

        for i in range(0, len(uids), batch_size):
            batch = uids[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(uids) + batch_size - 1) // batch_size

            logger.info(
                "processing_batch",
                batch_num=batch_num,
                total_batches=total_batches,
                batch_size=len(batch),
            )

            for uid in batch:
                result = await self.project_profile(uid)
                results.append(result)

        # Aggregate results
        success = sum(1 for r in results if r.status == ProjectionStatus.SUCCESS)
        failed = sum(1 for r in results if r.status == ProjectionStatus.FAILED)
        skipped = sum(1 for r in results if r.status == ProjectionStatus.SKIPPED)

        logger.info(
            "batch_projection_complete",
            total=len(uids),
            success=success,
            failed=failed,
            skipped=skipped,
        )

        return BatchProjectionResult(
            total=len(uids),
            success=success,
            failed=failed,
            skipped=skipped,
            results=results,
        )

    async def project_segment(
        self,
        segment_key: str,
    ) -> SegmentProjectionResult:
        """
        Project all members of a segment to Tracardi.

        Args:
            segment_key: The segment key to project

        Returns:
            SegmentProjectionResult with projection results
        """
        logger.info("projecting_segment", segment_key=segment_key)

        await self.postgresql.ensure_connected()
        pool = self.postgresql.pool
        if not pool:
            return SegmentProjectionResult(
                segment_key=segment_key,
                total_members=0,
                projected=0,
                failed=0,
                results=[],
            )

        # Get segment members
        query = """
            SELECT sm.uid
            FROM segment_memberships sm
            JOIN segment_definitions sd ON sm.segment_id = sd.segment_id
            WHERE sd.segment_key = $1
              AND sd.is_active = TRUE
              AND (sm.projected_to_tracardi = FALSE OR sm.projected_at < CURRENT_TIMESTAMP - INTERVAL '1 hour')
        """

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, segment_key)
                uids = [row["uid"] for row in rows]

                if not uids:
                    logger.info("no_segment_members_to_project", segment_key=segment_key)
                    return SegmentProjectionResult(
                        segment_key=segment_key,
                        total_members=0,
                        projected=0,
                        failed=0,
                        results=[],
                    )

                # Project all members
                batch_result = await self.project_batch(uids)

                # Update projected status
                update_query = """
                    UPDATE segment_memberships
                    SET projected_to_tracardi = TRUE, projected_at = CURRENT_TIMESTAMP
                    WHERE uid = ANY($1)
                      AND segment_id = (SELECT segment_id FROM segment_definitions WHERE segment_key = $2)
                """
                await conn.execute(update_query, uids, segment_key)

                return SegmentProjectionResult(
                    segment_key=segment_key,
                    total_members=len(uids),
                    projected=batch_result.success,
                    failed=batch_result.failed,
                    results=batch_result.results,
                )

        except Exception as e:
            logger.error("segment_projection_failed", segment_key=segment_key, error=str(e))
            return SegmentProjectionResult(
                segment_key=segment_key,
                total_members=0,
                projected=0,
                failed=0,
                results=[],
            )

    async def get_projection_state(self, uid: str) -> ProjectionState | None:
        """Get current projection state for a UID."""
        return await self._get_projection_state(uid)

    async def project_by_sync_status(
        self,
        sync_status: str = "enriched",
        limit: int | None = None,
    ) -> BatchProjectionResult:
        """
        Project all profiles with a given sync status.

        Args:
            sync_status: Sync status to filter by (e.g., 'enriched')
            limit: Maximum number of profiles to project

        Returns:
            BatchProjectionResult
        """
        logger.info(
            "projecting_by_sync_status",
            sync_status=sync_status,
            limit=limit,
        )

        # Fetch profiles with given sync status
        await self.postgresql.ensure_connected()
        pool = self.postgresql.pool
        if not pool:
            return BatchProjectionResult(
                total=0,
                success=0,
                failed=0,
                skipped=0,
                results=[],
            )

        query = """
            SELECT id::text as id FROM companies
            WHERE sync_status = $1
            ORDER BY updated_at DESC
            LIMIT $2
        """

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, sync_status, limit or 10000)
                uids = [row["id"] for row in rows]

                logger.info(
                    "found_profiles_for_projection",
                    sync_status=sync_status,
                    count=len(uids),
                )

                if not uids:
                    return BatchProjectionResult(
                        total=0,
                        success=0,
                        failed=0,
                        skipped=0,
                        results=[],
                    )

                return await self.project_batch(uids)

        except Exception as e:
            logger.error("project_by_sync_status_failed", sync_status=sync_status, error=str(e))
            return BatchProjectionResult(
                total=0,
                success=0,
                failed=0,
                skipped=0,
                results=[],
            )

    async def get_projection_metrics(self) -> dict[str, Any]:
        """Get projection metrics for monitoring."""
        await self.postgresql.ensure_connected()
        pool = self.postgresql.pool
        if not pool:
            return {}

        metrics: dict[str, Any] = {}

        # Overall projection stats
        query_stats = """
            SELECT
                projection_status,
                COUNT(*) as count
            FROM activation_projection_state
            WHERE target_system = 'tracardi'
            GROUP BY projection_status
        """

        # Lag metrics - how long since last projection
        query_lag = """
            SELECT
                AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - projected_at))) as avg_lag_seconds,
                MAX(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - projected_at))) as max_lag_seconds
            FROM activation_projection_state
            WHERE target_system = 'tracardi'
              AND projection_status = 'success'
        """

        # Profiles pending projection (enriched but not projected recently)
        query_pending = """
            SELECT COUNT(*) as count
            FROM companies c
            LEFT JOIN activation_projection_state ps
                ON c.id::text = ps.uid AND ps.target_system = 'tracardi'
            WHERE c.sync_status = 'enriched'
              AND (ps.projected_at IS NULL OR ps.projected_at < c.updated_at)
        """

        try:
            async with pool.acquire() as conn:
                # Stats
                rows = await conn.fetch(query_stats)
                metrics["projection_counts"] = {
                    row["projection_status"]: row["count"] for row in rows
                }

                # Lag
                row = await conn.fetchrow(query_lag)
                if row:
                    metrics["avg_lag_seconds"] = row["avg_lag_seconds"]
                    metrics["max_lag_seconds"] = row["max_lag_seconds"]

                # Pending
                row = await conn.fetchrow(query_pending)
                metrics["pending_projection"] = row["count"] if row else 0

        except Exception as e:
            logger.error("failed_to_get_projection_metrics", error=str(e))

        return metrics
