"""
Writeback Service - Tracardi to PostgreSQL Writeback

Implements the writeback portion of the projection contract defined in
docs/PROJECTION_CONTRACT.md. Responsible for syncing events, traits,
and workflow outcomes from Tracardi back to PostgreSQL.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from src.core.logger import get_logger
from src.services.postgresql_client import PostgreSQLClient
from src.services.tracardi import TracardiClient

logger = get_logger(__name__)


class WritebackStatus(Enum):
    """Status of a writeback operation."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # Event type not configured for writeback


@dataclass
class WritebackResult:
    """Result of a writeback operation."""

    event_id: str
    status: WritebackStatus
    records_written: int = 0
    error_message: str | None = None


@dataclass
class BatchWritebackResult:
    """Result of a batch writeback operation."""

    total_events: int
    success: int
    failed: int
    skipped: int
    results: list[WritebackResult]


@dataclass
class TraitSyncResult:
    """Result of syncing traits."""

    uid: str
    traits_synced: int
    status: WritebackStatus
    error_message: str | None = None


@dataclass
class WritebackMetrics:
    """Metrics for writeback operations."""

    total_events_processed: int
    events_by_type: dict[str, int]
    traits_created: int
    ai_decisions_created: int
    avg_processing_time_ms: float
    last_writeback_at: datetime | None


class WritebackService:
    """
    Service for writing back data from Tracardi to PostgreSQL.

    Implements the writeback contract:
    - Polls Tracardi events or receives webhooks
    - Normalizes events to canonical format
    - Writes to event_facts table
    - Extracts and persists traits
    - Records AI decision provenance
    """

    # Event types that should be written back to PostgreSQL
    WRITEBACK_EVENT_TYPES = {
        "email.opened",
        "email.clicked",
        "email.bounced",
        "email.delivered",
        "email.sent",
        "webhook.received",
        "workflow.completed",
        "workflow.failed",
        "ai.decision",
        "tag.assigned",
        "score.updated",
        "segment.entered",
        "segment.left",
        "page.view",
        "session.started",
        "session.ended",
        "goal.achieved",
    }

    # Event types that generate AI decisions
    AI_DECISION_EVENTS = {
        "ai.decision",
        "recommendation.generated",
        "classification.completed",
        "prediction.made",
    }

    # Event types that generate traits
    TRAIT_GENERATING_EVENTS = {
        "tag.assigned",
        "score.updated",
        "engagement.scored",
        "segment.entered",
        "segment.left",
    }

    def __init__(
        self,
        postgresql_client: PostgreSQLClient | None = None,
        tracardi_client: TracardiClient | None = None,
    ):
        self.postgresql = postgresql_client or PostgreSQLClient()
        self.tracardi = tracardi_client or TracardiClient()

    async def initialize(self) -> None:
        """Initialize connections."""
        await self.postgresql.connect()

    async def close(self) -> None:
        """Close connections."""
        await self.postgresql.disconnect()

    def _normalize_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """
        Normalize a Tracardi event to canonical event_facts format.

        Returns None if event should be skipped.
        """
        event_type = event.get("type", "")

        # Skip events not in writeback list
        if event_type not in self.WRITEBACK_EVENT_TYPES:
            return None

        # Extract profile ID (UID)
        profile = event.get("profile", {})
        uid = profile.get("id") if isinstance(profile, dict) else None

        if not uid:
            logger.warning("event_missing_uid", event_type=event_type)
            return None

        # Build normalized event
        properties = event.get("properties", {})
        metadata = event.get("metadata", {})
        time_info = metadata.get("time", {}) if isinstance(metadata, dict) else {}

        # Parse occurred_at
        occurred_at = time_info.get("insert")
        if occurred_at:
            if isinstance(occurred_at, str):
                try:
                    occurred_at = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
                except ValueError:
                    occurred_at = datetime.now(UTC)
            elif not isinstance(occurred_at, datetime):
                occurred_at = datetime.now(UTC)
        else:
            occurred_at = datetime.now(UTC)

        normalized = {
            "uid": uid,
            "organization_uid": uid,  # For now, same as uid
            "event_type": event_type,
            "event_channel": properties.get("channel", "unknown"),
            "event_source": "tracardi",
            "source_event_id": event.get("id"),
            "occurred_at": occurred_at.replace(tzinfo=None) if occurred_at.tzinfo else occurred_at,
            "event_value": self._extract_event_value(event_type, properties),
            "attributes": json.dumps(properties, default=str),
        }

        return normalized

    def _extract_event_value(self, event_type: str, properties: dict) -> float | None:
        """Extract a numeric value from event properties if relevant."""
        value_fields = {
            "score.updated": "score_value",
            "engagement.scored": "engagement_score",
            "goal.achieved": "goal_value",
        }

        field = value_fields.get(event_type)
        if field and field in properties:
            try:
                return float(properties[field])
            except (ValueError, TypeError):
                pass
        return None

    async def _write_event_fact(self, normalized_event: dict[str, Any]) -> bool:
        """Write normalized event to event_facts table."""
        await self.postgresql.ensure_connected()
        pool = self.postgresql.pool
        if not pool:
            return False

        query = """
            INSERT INTO event_facts (
                uid, organization_uid, event_type, event_channel, event_source,
                source_event_id, occurred_at, event_value, attributes
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT DO NOTHING
        """

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    normalized_event["uid"],
                    normalized_event["organization_uid"],
                    normalized_event["event_type"],
                    normalized_event["event_channel"],
                    normalized_event["event_source"],
                    normalized_event["source_event_id"],
                    normalized_event["occurred_at"],
                    normalized_event["event_value"],
                    normalized_event["attributes"],
                )
                return True
        except Exception as e:
            logger.error("failed_to_write_event_fact", error=str(e))
            return False

    async def _extract_and_write_trait(self, event: dict[str, Any]) -> bool:
        """Extract trait from event and write to profile_traits table."""
        event_type = event.get("type", "")

        if event_type not in self.TRAIT_GENERATING_EVENTS:
            return False

        profile = event.get("profile", {})
        uid = profile.get("id") if isinstance(profile, dict) else None
        if not uid:
            return False

        properties = event.get("properties", {})

        # Map event types to trait extraction
        trait_extractors = {
            "tag.assigned": lambda p: {
                "trait_name": f"tag_{p.get('tag_name', 'unknown')}",
                "trait_value_boolean": True,
                "confidence": 1.0,
            },
            "score.updated": lambda p: {
                "trait_name": p.get("score_name", "score"),
                "trait_value_number": p.get("score_value"),
                "confidence": 1.0,
            },
            "engagement.scored": lambda p: {
                "trait_name": "engagement_score",
                "trait_value_number": p.get("engagement_score"),
                "confidence": p.get("confidence", 0.8),
            },
            "segment.entered": lambda p: {
                "trait_name": f"segment_{p.get('segment_key', 'unknown')}",
                "trait_value_boolean": True,
                "confidence": 1.0,
            },
            "segment.left": lambda p: {
                "trait_name": f"segment_{p.get('segment_key', 'unknown')}",
                "trait_value_boolean": False,
                "confidence": 1.0,
            },
        }

        extractor = trait_extractors.get(event_type)
        if not extractor:
            return False

        trait_data = extractor(properties)

        # Determine which value field to use
        value = None
        if "trait_value_text" in trait_data:
            value = trait_data["trait_value_text"]
        elif "trait_value_number" in trait_data:
            value = trait_data["trait_value_number"]
        elif "trait_value_boolean" in trait_data:
            value = trait_data["trait_value_boolean"]

        await self.postgresql.ensure_connected()
        pool = self.postgresql.pool
        if not pool:
            return False

        query = """
            INSERT INTO profile_traits (
                uid, trait_name, trait_value_text, trait_value_number, trait_value_boolean,
                confidence, source_system, source_reference, effective_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (uid, trait_name) DO UPDATE SET
                trait_value_text = COALESCE(EXCLUDED.trait_value_text, profile_traits.trait_value_text),
                trait_value_number = COALESCE(EXCLUDED.trait_value_number, profile_traits.trait_value_number),
                trait_value_boolean = COALESCE(EXCLUDED.trait_value_boolean, profile_traits.trait_value_boolean),
                confidence = EXCLUDED.confidence,
                source_reference = EXCLUDED.source_reference,
                updated_at = CURRENT_TIMESTAMP
        """

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    uid,
                    trait_data["trait_name"],
                    trait_data.get("trait_value_text"),
                    trait_data.get("trait_value_number"),
                    trait_data.get("trait_value_boolean"),
                    trait_data["confidence"],
                    "tracardi_projection",
                    event.get("id"),
                    datetime.now(UTC).replace(tzinfo=None),
                )
                logger.info(
                    "trait_written",
                    uid=uid,
                    trait_name=trait_data["trait_name"],
                    value=value,
                )
                return True
        except Exception as e:
            logger.error("failed_to_write_trait", uid=uid, error=str(e))
            return False

    async def _extract_and_write_ai_decision(self, event: dict[str, Any]) -> bool:
        """Extract AI decision from event and write to ai_decisions table."""
        event_type = event.get("type", "")

        if event_type not in self.AI_DECISION_EVENTS:
            return False

        profile = event.get("profile", {})
        uid = profile.get("id") if isinstance(profile, dict) else None
        if not uid:
            return False

        properties = event.get("properties", {})
        metadata = event.get("metadata", {})
        time_info = metadata.get("time", {}) if isinstance(metadata, dict) else {}

        # Parse decided_at
        decided_at = time_info.get("insert")
        if decided_at:
            if isinstance(decided_at, str):
                try:
                    decided_at = datetime.fromisoformat(decided_at.replace("Z", "+00:00"))
                except ValueError:
                    decided_at = datetime.now(UTC)
            elif not isinstance(decided_at, datetime):
                decided_at = datetime.now(UTC)
        else:
            decided_at = datetime.now(UTC)

        decision_data = {
            "uid": uid,
            "decision_type": properties.get("decision_type", "unknown"),
            "decision_name": properties.get(
                "decision_name", properties.get("recommendation_type", "unknown")
            ),
            "decision_value": properties.get("decision_value") or properties.get("recommendation"),
            "confidence": properties.get("confidence", 0.0),
            "source_system": "tracardi_projection",
            "model_name": properties.get("model_name"),
            "model_version": properties.get("model_version"),
            "decided_at": decided_at.replace(tzinfo=None) if decided_at.tzinfo else decided_at,
            "explanation": properties.get("explanation", properties.get("reason", {})),
        }

        await self.postgresql.ensure_connected()
        pool = self.postgresql.pool
        if not pool:
            return False

        query = """
            INSERT INTO ai_decisions (
                uid, decision_type, decision_name, decision_value, confidence,
                source_system, model_name, model_version, decided_at, explanation
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT DO NOTHING
        """

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    decision_data["uid"],
                    decision_data["decision_type"],
                    decision_data["decision_name"],
                    decision_data["decision_value"],
                    decision_data["confidence"],
                    decision_data["source_system"],
                    decision_data["model_name"],
                    decision_data["model_version"],
                    decision_data["decided_at"],
                    decision_data["explanation"],
                )
                logger.info(
                    "ai_decision_written",
                    uid=uid,
                    decision_name=decision_data["decision_name"],
                )
                return True
        except Exception as e:
            logger.error("failed_to_write_ai_decision", uid=uid, error=str(e))
            return False

    async def process_event(self, event: dict[str, Any]) -> WritebackResult:
        """
        Process a single Tracardi event and write back to PostgreSQL.

        Args:
            event: Tracardi event dict

        Returns:
            WritebackResult with status
        """
        event_id = event.get("id", "unknown")
        event_type = event.get("type", "unknown")

        logger.debug("processing_event", event_id=event_id, event_type=event_type)

        try:
            # Normalize event
            normalized = self._normalize_event(event)
            if not normalized:
                return WritebackResult(
                    event_id=event_id,
                    status=WritebackStatus.SKIPPED,
                )

            records_written = 0

            # Write event fact
            if await self._write_event_fact(normalized):
                records_written += 1

            # Extract and write trait
            if await self._extract_and_write_trait(event):
                records_written += 1

            # Extract and write AI decision
            if await self._extract_and_write_ai_decision(event):
                records_written += 1

            logger.info(
                "event_processed",
                event_id=event_id,
                event_type=event_type,
                records_written=records_written,
            )

            return WritebackResult(
                event_id=event_id,
                status=WritebackStatus.SUCCESS,
                records_written=records_written,
            )

        except Exception as e:
            logger.error(
                "event_processing_failed",
                event_id=event_id,
                event_type=event_type,
                error=str(e),
            )
            return WritebackResult(
                event_id=event_id,
                status=WritebackStatus.FAILED,
                error_message=str(e),
            )

    async def process_events(
        self,
        events: list[dict[str, Any]],
    ) -> BatchWritebackResult:
        """
        Process multiple Tracardi events.

        Args:
            events: List of Tracardi event dicts

        Returns:
            BatchWritebackResult with aggregated results
        """
        results: list[WritebackResult] = []

        for event in events:
            result = await self.process_event(event)
            results.append(result)

        success = sum(1 for r in results if r.status == WritebackStatus.SUCCESS)
        failed = sum(1 for r in results if r.status == WritebackStatus.FAILED)
        skipped = sum(1 for r in results if r.status == WritebackStatus.SKIPPED)

        return BatchWritebackResult(
            total_events=len(events),
            success=success,
            failed=failed,
            skipped=skipped,
            results=results,
        )

    async def poll_and_process(
        self,
        since: datetime | None = None,
        event_types: set[str] | None = None,
        limit: int = 1000,
    ) -> BatchWritebackResult:
        """
        Poll Tracardi for events and process them.

        Args:
            since: Fetch events since this time (defaults to last hour)
            event_types: Filter to specific event types
            limit: Maximum events to fetch

        Returns:
            BatchWritebackResult
        """
        if since is None:
            since = datetime.now(UTC) - timedelta(hours=1)

        types_to_fetch = event_types or self.WRITEBACK_EVENT_TYPES

        logger.info(
            "polling_tracardi_events",
            since=since.isoformat(),
            event_types=len(types_to_fetch),
            limit=limit,
        )

        # TODO: Implement event fetching from Tracardi
        # This requires Tracardi to expose an event query API
        # For now, return empty result
        logger.warning("event_polling_not_implemented")

        return BatchWritebackResult(
            total_events=0,
            success=0,
            failed=0,
            skipped=0,
            results=[],
        )

    async def handle_webhook(self, webhook_payload: dict[str, Any]) -> WritebackResult:
        """
        Handle a real-time webhook from Tracardi.

        Args:
            webhook_payload: Webhook payload from Tracardi

        Returns:
            WritebackResult
        """
        logger.info("handling_webhook", payload_keys=list(webhook_payload.keys()))

        # Extract event from webhook payload
        # Tracardi webhooks typically have the event in the payload
        event = webhook_payload.get("event", webhook_payload)

        return await self.process_event(event)

    async def sync_traits(self, uid: str) -> TraitSyncResult:
        """
        Sync traits from Tracardi to PostgreSQL for a specific UID.

        Args:
            uid: UID to sync traits for

        Returns:
            TraitSyncResult
        """
        logger.info("syncing_traits", uid=uid)

        try:
            # Fetch profile from Tracardi
            # Note: This requires a method to fetch profile by ID
            # which may not exist in current Tracardi client

            # TODO: Implement when profile fetch API is available
            logger.warning("trait_sync_not_implemented")

            return TraitSyncResult(
                uid=uid,
                traits_synced=0,
                status=WritebackStatus.SKIPPED,
            )

        except Exception as e:
            logger.error("trait_sync_failed", uid=uid, error=str(e))
            return TraitSyncResult(
                uid=uid,
                traits_synced=0,
                status=WritebackStatus.FAILED,
                error_message=str(e),
            )

    async def get_writeback_metrics(self) -> WritebackMetrics:
        """Get writeback metrics for monitoring."""
        await self.postgresql.ensure_connected()
        pool = self.postgresql.pool
        if not pool:
            return WritebackMetrics(
                total_events_processed=0,
                events_by_type={},
                traits_created=0,
                ai_decisions_created=0,
                avg_processing_time_ms=0.0,
                last_writeback_at=None,
            )

        metrics = WritebackMetrics(
            total_events_processed=0,
            events_by_type={},
            traits_created=0,
            ai_decisions_created=0,
            avg_processing_time_ms=0.0,
            last_writeback_at=None,
        )

        # Total events from Tracardi
        query_events = """
            SELECT
                COUNT(*) as total,
                event_type,
                COUNT(*) FILTER (WHERE event_type = event_type) as count
            FROM event_facts
            WHERE event_source = 'tracardi'
            GROUP BY event_type
        """

        # Traits from Tracardi projection
        query_traits = """
            SELECT COUNT(*) as count
            FROM profile_traits
            WHERE source_system = 'tracardi_projection'
        """

        # AI decisions from Tracardi
        query_ai = """
            SELECT COUNT(*) as count
            FROM ai_decisions
            WHERE source_system = 'tracardi_projection'
        """

        # Last writeback time
        query_last = """
            SELECT MAX(created_at) as last_at
            FROM event_facts
            WHERE event_source = 'tracardi'
        """

        try:
            async with pool.acquire() as conn:
                # Events by type
                rows = await conn.fetch(query_events)
                for row in rows:
                    metrics.events_by_type[row["event_type"]] = row["count"]
                    metrics.total_events_processed += row["count"]

                # Traits
                row = await conn.fetchrow(query_traits)
                metrics.traits_created = row["count"] if row else 0

                # AI decisions
                row = await conn.fetchrow(query_ai)
                metrics.ai_decisions_created = row["count"] if row else 0

                # Last writeback
                row = await conn.fetchrow(query_last)
                if row and row["last_at"]:
                    metrics.last_writeback_at = row["last_at"]

        except Exception as e:
            logger.error("failed_to_get_writeback_metrics", error=str(e))

        return metrics
