"""
Batch enrichment pipeline for PostgreSQL-based profiles (v2.0 architecture).

Orchestrates all enrichment sources with:
- Queue-based processing
- Progress tracking
- Cost monitoring
- Resumable batches
- Direct PostgreSQL updates (no Tracardi dependency)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config import settings
from src.core.cache import MultiTierCache, RedisCache, SQLiteCache
from src.core.logger import get_logger
from src.enrichment.b2b_provider import B2BProviderEnricher
from src.enrichment.cbe_integration import CBEIntegrationEnricher
from src.enrichment.contact_validation import ContactValidationEnricher
from src.enrichment.deduplication import DeduplicationEnricher
from src.enrichment.descriptions import DescriptionEnricher
from src.enrichment.geocoding import GeocodingEnricher
from src.enrichment.google_places import GooglePlacesEnricher
from src.enrichment.phone_discovery import PhoneDiscoveryEnricher
from src.enrichment.progress import CostTracker, ProgressTracker
from src.enrichment.website_discovery import WebsiteDiscoveryEnricher
from src.services.cbe_extended import CBEExtendedClient
from src.services.postgresql_client import PostgreSQLClient
from src.services.projection import ProjectionService

logger = get_logger(__name__)


class PostgreSQLEnrichmentPipeline:
    """
    Pipeline for batch-enriching profiles stored in PostgreSQL.

    This is the v2.0 architecture that replaces Tracardi with PostgreSQL
    as the primary data store.

    Supports:
    - Phase-based processing (quick wins first)
    - Resumable batches
    - Progress tracking
    - Cost monitoring
    - Rate limiting
    """

    def __init__(
        self,
        batch_size: int = 100,
        progress_dir: str = "./data/progress",
        cache_dir: str = "./data/cache",
        budget_eur: float = 150.0,
        connection_url: str | None = None,
    ):
        self.batch_size = batch_size
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize trackers
        self.progress = ProgressTracker(progress_dir=progress_dir)
        self.costs = CostTracker(budget_eur=budget_eur)

        # ------------------------------------------------------------------
        # Build shared MultiTierCache instances for the Phase 2 enrichers.
        # When REDIS_URL is set (production), we get SQLite L1 + Redis L2.
        # Without Redis (local dev / CI) the enrichers fall back to SQLite.
        # ------------------------------------------------------------------
        redis_url = getattr(settings, "REDIS_URL", None)

        def _make_cache(db_filename: str, redis_prefix: str, redis_ttl: int = 86400):
            """Return a MultiTierCache when Redis is available, else None (fallback in enricher)."""
            if not redis_url:
                return None
            db_path = self.cache_dir / db_filename
            l1 = SQLiteCache(db_path=db_path, table_name=db_filename.replace(".db", ""))
            l2 = RedisCache(url=redis_url, prefix=redis_prefix, ttl=redis_ttl)
            return MultiTierCache(l1=l1, l2=l2)

        website_cache = _make_cache("website_enricher.db", "cdp:website:", redis_ttl=86400 * 7)
        desc_cache = _make_cache("desc_enricher.db", "cdp:desc:", redis_ttl=86400 * 30)
        phone_cache = _make_cache("phone_enricher.db", "cdp:phone:", redis_ttl=86400 * 14)
        geo_cache = _make_cache("geo_enricher.db", "cdp:geo:", redis_ttl=86400 * 30)

        # Initialize enrichers
        self.enrichers: dict[str, Any] = {
            "contact_validation": ContactValidationEnricher(
                cache_dir=str(self.cache_dir),
                cache_file="contact_validation_cache.json",
            ),
            "website_discovery": WebsiteDiscoveryEnricher(
                cache_dir=str(self.cache_dir),
                cache_file="website_cache.json",
                cache=website_cache,
            ),
            "cbe_integration": CBEIntegrationEnricher(
                cache_dir=str(self.cache_dir),
                cache_file="cbe_cache.json",
            ),
            "cbe_financials": CBEExtendedClient(
                data_dir=str(self.cache_dir / "cbe_extended"),
                use_api=True,
            ),
            "phone_discovery": PhoneDiscoveryEnricher(
                cache_dir=str(self.cache_dir),
                cache_file="phone_discovery_cache.json",
                cache=phone_cache,
            ),
            "geocoding": GeocodingEnricher(
                cache_dir=str(self.cache_dir),
                cache_file="geocoding_cache.json",
                cache=geo_cache,
            ),
            "deduplication": DeduplicationEnricher(
                cache_dir=str(self.cache_dir),
                cache_file="deduplication_cache.json",
            ),
            "descriptions": DescriptionEnricher(
                cache_dir=str(self.cache_dir),
                cache_file="descriptions_cache.json",
                cache=desc_cache,
            ),
            "google_places": GooglePlacesEnricher(
                cache_dir=str(self.cache_dir),
                cache_file="google_places_cache.json",
            ),
            "b2b_provider": B2BProviderEnricher(
                cache_dir=str(self.cache_dir),
                cache_file="b2b_cache.json",
            ),
        }

        # PostgreSQL client
        self.db: PostgreSQLClient | None = None
        self.connection_url = connection_url

    async def _get_db_client(self) -> PostgreSQLClient:
        """Get or create PostgreSQL client."""
        if not self.db:
            self.db = PostgreSQLClient(self.connection_url)
            await self.db.connect()
        return self.db

    def _profile_to_dict(self, profile: dict[str, Any]) -> dict[str, Any]:
        """
        Convert PostgreSQL profile row to dict format compatible with enrichers.

        This normalizes the PostgreSQL schema to match what enrichers expect
        from the old Tracardi format.
        """
        return {
            "id": str(profile.get("id", "")),
            "kbo_number": profile.get("kbo_number"),
            "vat_number": profile.get("vat_number"),
            "name": profile.get("company_name", ""),
            "legal_form": profile.get("legal_form"),
            "address": {
                "street": profile.get("street_address"),
                "city": profile.get("city"),
                "postal_code": profile.get("postal_code"),
                "country": profile.get("country", "BE"),
            },
            "geo": {
                "latitude": profile.get("geo_latitude"),
                "longitude": profile.get("geo_longitude"),
            }
            if profile.get("geo_latitude")
            else None,
            "industry": {
                "nace_code": profile.get("industry_nace_code"),
                "description": profile.get("nace_description"),
            },
            "company_size": profile.get("company_size"),
            "employee_count": profile.get("employee_count"),
            "annual_revenue": profile.get("annual_revenue"),
            "founded_date": profile.get("founded_date"),
            "website": profile.get("website_url"),
            "phone": profile.get("main_phone"),
            "email": profile.get("main_email"),
            "ai_description": profile.get("ai_description"),
            # Raw database fields for updates
            "_db_fields": profile,
        }

    def _extract_updates(self, enriched_profile: dict[str, Any]) -> dict[str, Any]:
        """
        Extract database field updates from enriched profile.

        Maps enrichment results back to PostgreSQL column names.
        """
        updates: dict[str, Any] = {}

        # Website discovery
        if "website" in enriched_profile and enriched_profile["website"]:
            updates["website_url"] = enriched_profile["website"]

        # Phone discovery
        if "phone" in enriched_profile and enriched_profile["phone"]:
            updates["main_phone"] = enriched_profile["phone"]

        # Email
        if "email" in enriched_profile and enriched_profile["email"]:
            updates["main_email"] = enriched_profile["email"]

        # Geocoding
        if "geo" in enriched_profile and enriched_profile["geo"]:
            geo = enriched_profile["geo"]
            if geo.get("latitude"):
                updates["geo_latitude"] = geo["latitude"]
            if geo.get("longitude"):
                updates["geo_longitude"] = geo["longitude"]

        # AI Description
        if "ai_description" in enriched_profile and enriched_profile["ai_description"]:
            updates["ai_description"] = enriched_profile["ai_description"]
            updates["ai_description_generated_at"] = datetime.now(UTC).replace(tzinfo=None)

        # CBE Integration - industry info
        if "industry" in enriched_profile and enriched_profile["industry"]:
            industry = enriched_profile["industry"]
            if industry.get("nace_code"):
                updates["industry_nace_code"] = industry["nace_code"]
            if industry.get("description"):
                updates["nace_description"] = industry["description"]

        # CBE Financials
        if "employee_count" in enriched_profile and enriched_profile["employee_count"]:
            updates["employee_count"] = enriched_profile["employee_count"]
        if "annual_revenue" in enriched_profile and enriched_profile["annual_revenue"]:
            updates["annual_revenue"] = enriched_profile["annual_revenue"]
        if "company_size" in enriched_profile and enriched_profile["company_size"]:
            updates["company_size"] = enriched_profile["company_size"]

        # Contact validation
        if "main_email" in enriched_profile and enriched_profile["main_email"]:
            updates["main_email"] = enriched_profile["main_email"]

        # Sync status tracking - use naive datetime for PostgreSQL compatibility
        updates["last_sync_at"] = datetime.now(UTC).replace(tzinfo=None)
        updates["sync_status"] = "enriched"

        return updates

    async def fetch_profiles(
        self,
        query: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        """
        Fetch profiles from PostgreSQL.

        Args:
            query: Simple search query (matches name, KBO, city)
            limit: Maximum profiles to fetch
            offset: Pagination offset

        Returns:
            List of profiles in enricher-compatible format
        """
        db = await self._get_db_client()

        logger.info("Fetching profiles from PostgreSQL")

        if query and query != "*":
            result = await db.search_profiles(query, limit=limit or 1000, offset=offset)
            profiles = result.get("result", [])
        else:
            profiles = await db.get_profiles(limit=limit or 1000, offset=offset)

        # Convert to enricher-compatible format
        converted = [self._profile_to_dict(p) for p in profiles]

        logger.info(f"Fetched {len(converted)} profiles from PostgreSQL")
        return converted

    async def get_profile_count(self) -> int:
        """Get total number of profiles in database."""
        db = await self._get_db_client()
        return await db.get_profile_count()

    async def update_profiles(self, profiles: list[dict]) -> dict:
        """
        Update enriched profiles in PostgreSQL.

        Args:
            profiles: List of enriched profiles

        Returns:
            Update result
        """
        db = await self._get_db_client()

        # Prepare updates
        updates = []
        for profile in profiles:
            profile_id = profile.get("id")
            if not profile_id:
                continue

            # Extract database field updates
            update_data = self._extract_updates(profile)
            if update_data:
                updates.append((profile_id, update_data))

        if not updates:
            return {"success": True, "updated": 0}

        try:
            result = await db.update_profiles_batch(updates)
            logger.info(f"Updated {result['success']} profiles in PostgreSQL")

            # Auto-project enriched profiles to Tracardi
            await self._auto_project_profiles(updates)

            return {
                "success": True,
                "updated": result["success"],
                "failed": result["failed"],
            }
        except Exception as e:
            logger.error(f"Failed to update profiles: {e}")
            return {"success": False, "error": str(e)}

    async def _auto_project_profiles(
        self,
        updates: list[tuple[str, dict]],
    ) -> None:
        """
        Auto-project enriched profiles to Tracardi.

        This is called after successful enrichment to keep Tracardi
        in sync with PostgreSQL for activation workflows.
        """
        if not updates:
            return

        try:
            projection_service = ProjectionService(postgresql_client=self.db)
            await projection_service.initialize()

            # Extract UIDs from updates
            uids = [str(profile_id) for profile_id, _ in updates]

            # Project in small batches to avoid overwhelming Tracardi
            batch_size = 10
            total_projected = 0

            for i in range(0, len(uids), batch_size):
                batch = uids[i : i + batch_size]
                result = await projection_service.project_batch(batch)
                total_projected += result.success

                if result.failed > 0:
                    logger.warning(
                        "auto_projection_batch_partial",
                        batch_index=i // batch_size,
                        success=result.success,
                        failed=result.failed,
                    )

            logger.info(
                "auto_projection_complete",
                total_enriched=len(uids),
                total_projected=total_projected,
            )

            await projection_service.close()

        except Exception as e:
            # Log but don't fail the enrichment - projection can retry later
            logger.error("auto_projection_failed", error=str(e))

    async def run_phase_streaming(
        self,
        phase_name: str,
        enricher_name: str,
        query: str | None = None,
        job_id: str | None = None,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> dict:
        """
        Run enrichment phase with streaming to avoid memory overflow.

        Processes profiles in batches directly from PostgreSQL without
        loading all profiles into memory at once.

        Supports crash-resume via an offset checkpoint file stored in
        the progress directory.

        Args:
            phase_name: Name of this phase
            enricher_name: Name of enricher to use
            query: Optional search query
            job_id: Optional job ID for tracking
            dry_run: If True, don't update database

        Returns:
            Phase result with completion metadata (`completed`, `status`,
            and `exit_reason`) for clean-exit guardrails.
        """
        import json as _json

        if enricher_name not in self.enrichers:
            raise ValueError(f"Unknown enricher: {enricher_name}")

        enricher = self.enrichers[enricher_name]
        job_id = job_id or f"{phase_name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

        # Checkpoint file for resume support
        checkpoint_file = (
            Path(self.progress.progress_dir)
            / f"streaming_last_offset_{phase_name.replace('/', '_')}.json"
        )

        def _load_checkpoint() -> int:
            if checkpoint_file.exists():
                try:
                    data = _json.loads(checkpoint_file.read_text())
                    saved = data.get("last_offset", 0)
                    if saved > 0:
                        logger.info(
                            f"Streaming resume: phase={phase_name} resuming from offset={saved}"
                        )
                    return int(saved)
                except (ValueError, KeyError, OSError):
                    pass
            return 0

        def _save_checkpoint(current_offset: int) -> None:
            try:
                checkpoint_file.write_text(
                    _json.dumps(
                        {
                            "phase": phase_name,
                            "last_offset": current_offset,
                            "updated_at": datetime.now(UTC).isoformat(),
                        },
                        indent=2,
                    )
                )
            except OSError as exc:
                logger.warning(f"Could not save streaming offset checkpoint: {exc}")

        def _clear_checkpoint() -> None:
            try:
                if checkpoint_file.exists():
                    checkpoint_file.unlink()
            except OSError as exc:
                logger.warning(f"Could not clear streaming offset checkpoint: {exc}")

        def _build_result(
            *,
            completed: bool,
            status: str,
            exit_reason: str,
            processed_this_run: int,
            processed_cumulative: int,
            target_profiles: int,
            enriched: int,
            skipped: int,
        ) -> dict[str, Any]:
            return {
                "phase": phase_name,
                "enricher": enricher_name,
                "job_id": job_id,
                "total_profiles": processed_this_run,
                "processed_this_run": processed_this_run,
                "processed_cumulative": processed_cumulative,
                "target_profiles": target_profiles,
                "enriched": enriched,
                "skipped": skipped,
                "stats": enricher.stats.to_dict(),
                "dry_run": dry_run,
                "completed": completed,
                "status": status,
                "exit_reason": exit_reason,
            }

        logger.info(
            f"Starting streaming phase: {phase_name} with {enricher_name} "
            f"(query={query}, limit={limit}, batch_size={self.batch_size})"
        )

        # Load checkpoint before DB operations (fast fail)
        last_offset = _load_checkpoint()
        offset = last_offset
        logger.info(f"Phase {phase_name}: checkpoint loaded, resuming from offset={offset}")

        db = await self._get_db_client()

        # Get total count, respecting limit if provided
        total_in_db = await db.get_profile_count()
        total_matches = min(total_in_db, limit) if limit is not None else total_in_db
        logger.info(
            f"Phase {phase_name}: {total_matches} profiles to process "
            f"(DB has {total_in_db}, limit={limit})"
        )

        if offset > total_matches:
            logger.warning(
                f"Phase {phase_name}: checkpoint offset {offset} exceeds target "
                f"{total_matches}; treating target as already reached"
            )

        self.progress.start_job(job_id, enricher_name, total_matches)
        enricher.start()

        total_processed = 0
        total_enriched = 0
        total_skipped = 0
        loop_iteration = 0
        completed = False
        status = "running"
        exit_reason = "running"

        try:
            if total_matches == 0:
                completed = True
                status = "completed"
                exit_reason = "no_matches"
                logger.info(
                    f"Phase {phase_name}: exiting before loop reason={exit_reason} "
                    f"processed_this_run={total_processed} processed_cumulative={offset} "
                    f"target={total_matches} limit={limit}"
                )

            while status == "running":
                loop_iteration += 1
                processed_cumulative = offset
                remaining = max(total_matches - processed_cumulative, 0)
                fetch_limit = min(self.batch_size, remaining) if remaining > 0 else 0

                logger.info(
                    f"Phase {phase_name}: loop_start iteration={loop_iteration} "
                    f"offset={offset} processed_this_run={total_processed} "
                    f"processed_cumulative={processed_cumulative} target={total_matches} "
                    f"remaining={remaining} fetch_limit={fetch_limit} limit={limit}"
                )

                if remaining <= 0:
                    completed = True
                    status = "completed"
                    if limit is not None and processed_cumulative >= limit:
                        exit_reason = "limit_reached"
                    else:
                        exit_reason = "target_reached"
                    logger.info(
                        f"Phase {phase_name}: breaking loop reason={exit_reason} "
                        f"iteration={loop_iteration} processed_this_run={total_processed} "
                        f"processed_cumulative={processed_cumulative} "
                        f"target={total_matches} limit={limit}"
                    )
                    break

                # Fetch batch
                rows = await db.get_profiles(
                    limit=fetch_limit,
                    offset=offset,
                    order_by="id",
                )

                if not rows:
                    if offset >= total_matches:
                        completed = True
                        status = "completed"
                        exit_reason = "target_reached"
                        logger.info(
                            f"Phase {phase_name}: breaking loop reason={exit_reason} "
                            f"iteration={loop_iteration} processed_this_run={total_processed} "
                            f"processed_cumulative={offset} target={total_matches} limit={limit}"
                        )
                    else:
                        completed = False
                        status = "incomplete"
                        exit_reason = "no_rows_before_target"
                        logger.warning(
                            f"Phase {phase_name}: breaking loop reason={exit_reason} "
                            f"iteration={loop_iteration} processed_this_run={total_processed} "
                            f"processed_cumulative={offset} target={total_matches} "
                            f"remaining={max(total_matches - offset, 0)} limit={limit}"
                        )
                    break

                # Convert to enricher format
                profiles = [self._profile_to_dict(p) for p in rows]

                enrichable = [p for p in profiles if enricher.can_enrich(p)]
                skipped = len(profiles) - len(enrichable)
                total_skipped += skipped

                if enrichable:
                    enriched_batch = await enricher.enrich_batch(enrichable)
                    total_enriched += len(enriched_batch)

                    if not dry_run:
                        await self.update_profiles(enriched_batch)

                    # Clear references to help GC
                    del enriched_batch

                for _ in profiles:
                    self.progress.increment_progress(job_id, success=True)

                batch_processed = len(profiles)
                total_processed += batch_processed
                offset += batch_processed

                # Clear references to help GC
                del profiles
                del enrichable

                # Force garbage collection every 5 batches to prevent memory buildup
                if loop_iteration % 5 == 0:
                    import gc

                    gc.collect()

                # Save checkpoint every 10 batches
                if loop_iteration % 10 == 0:
                    _save_checkpoint(offset)

                logger.info(
                    f"Phase {phase_name}: loop_end iteration={loop_iteration} "
                    f"batch_processed={batch_processed} processed_this_run={total_processed} "
                    f"processed_cumulative={offset} enriched={total_enriched} "
                    f"skipped={total_skipped} target={total_matches} limit={limit}"
                )

                if limit is not None and offset >= limit:
                    completed = True
                    status = "completed"
                    exit_reason = "limit_reached"
                    logger.info(
                        f"Phase {phase_name}: breaking loop reason={exit_reason} "
                        f"iteration={loop_iteration} processed_this_run={total_processed} "
                        f"processed_cumulative={offset} target={total_matches} limit={limit}"
                    )
                    break

                if offset >= total_matches:
                    completed = True
                    status = "completed"
                    exit_reason = "target_reached"
                    logger.info(
                        f"Phase {phase_name}: breaking loop reason={exit_reason} "
                        f"iteration={loop_iteration} processed_this_run={total_processed} "
                        f"processed_cumulative={offset} target={total_matches} limit={limit}"
                    )
                    break

                # Small delay between batches
                await asyncio.sleep(0.05)

            if status == "running":
                completed = False
                status = "incomplete"
                exit_reason = "loop_ended_without_explicit_reason"
                logger.error(
                    f"Phase {phase_name}: loop ended unexpectedly reason={exit_reason} "
                    f"processed_this_run={total_processed} processed_cumulative={offset} "
                    f"target={total_matches} limit={limit}"
                )

            if completed:
                _save_checkpoint(offset)
                _clear_checkpoint()
                self.progress.complete_job(job_id)
            else:
                _save_checkpoint(offset)
                self.progress.complete_job(
                    job_id,
                    error_message=(
                        "Incomplete phase exit: "
                        f"reason={exit_reason}, processed_this_run={total_processed}, "
                        f"processed_cumulative={offset}, target={total_matches}, limit={limit}"
                    ),
                )

            enricher.finish()

            # Record costs if applicable
            if hasattr(enricher, "estimated_cost_usd") and enricher.estimated_cost_usd > 0:
                self.costs.record_cost(
                    source=enricher_name,
                    operation="api_calls",
                    cost_eur=enricher.estimated_cost_usd * 0.92,
                    details={"tokens_used": getattr(enricher, "tokens_used", 0)},
                )

            result = _build_result(
                completed=completed,
                status=status,
                exit_reason=exit_reason,
                processed_this_run=total_processed,
                processed_cumulative=offset,
                target_profiles=total_matches,
                enriched=total_enriched,
                skipped=total_skipped,
            )
            logger.info(
                f"Phase {phase_name}: returning result status={status} "
                f"completed={completed} exit_reason={exit_reason} "
                f"processed_this_run={total_processed} processed_cumulative={offset} "
                f"target={total_matches} limit={limit}"
            )
            return result

        except Exception as e:
            logger.error(
                f"Phase {phase_name}: exception before return reason=exception "
                f"processed_this_run={total_processed} processed_cumulative={offset} "
                f"target={total_matches} limit={limit} error={e}"
            )
            # Checkpoint is intentionally kept so the next run can resume
            _save_checkpoint(offset)
            self.progress.complete_job(job_id, error_message=str(e))
            enricher.finish()
            raise

    async def run_phase(
        self,
        phase_name: str,
        enricher_name: str,
        profiles: list[dict],
        job_id: str | None = None,
        dry_run: bool = False,
    ) -> dict:
        """
        Run a single enrichment phase.

        Args:
            phase_name: Name of this phase
            enricher_name: Name of enricher to use
            profiles: Profiles to enrich
            job_id: Optional job ID for tracking
            dry_run: If True, don't update database

        Returns:
            Phase result
        """
        if enricher_name not in self.enrichers:
            raise ValueError(f"Unknown enricher: {enricher_name}")

        enricher = self.enrichers[enricher_name]
        job_id = job_id or f"{phase_name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Starting phase: {phase_name} with {enricher_name}")

        # Start progress tracking
        self.progress.start_job(job_id, enricher_name, len(profiles))
        enricher.start()

        # Filter profiles that can be enriched
        enrichable = [p for p in profiles if enricher.can_enrich(p)]
        skipped = len(profiles) - len(enrichable)

        logger.info(f"Enrichable: {len(enrichable)}, Skipped: {skipped}")

        enriched_profiles = []

        try:
            # Process in batches
            for i in range(0, len(enrichable), self.batch_size):
                batch = enrichable[i : i + self.batch_size]
                batch_num = i // self.batch_size + 1
                total_batches = (len(enrichable) + self.batch_size - 1) // self.batch_size

                logger.info(
                    f"Processing batch {batch_num}/{total_batches} ({len(batch)} profiles)"
                )

                # Enrich batch
                enriched_batch = await enricher.enrich_batch(batch)
                enriched_profiles.extend(enriched_batch)

                # Update progress
                for _ in batch:
                    self.progress.increment_progress(job_id, success=True)

                # Update PostgreSQL if not dry run
                if not dry_run:
                    await self.update_profiles(enriched_batch)

                # Small delay between batches to not overload
                await asyncio.sleep(0.1)

            # Mark as complete
            self.progress.complete_job(job_id)
            enricher.finish()

            # Record costs if applicable
            if hasattr(enricher, "estimated_cost_usd") and enricher.estimated_cost_usd > 0:
                self.costs.record_cost(
                    source=enricher_name,
                    operation="api_calls",
                    cost_eur=enricher.estimated_cost_usd * 0.92,
                    details={"tokens_used": getattr(enricher, "tokens_used", 0)},
                )

            return {
                "phase": phase_name,
                "enricher": enricher_name,
                "job_id": job_id,
                "total_profiles": len(profiles),
                "enriched": len(enrichable),
                "skipped": skipped,
                "stats": enricher.stats.to_dict(),
                "dry_run": dry_run,
            }

        except Exception as e:
            logger.error(f"Phase {phase_name} failed: {e}")
            self.progress.complete_job(job_id, error_message=str(e))
            enricher.finish()
            raise

    async def run_full_pipeline(
        self,
        profiles: list[dict] | None = None,
        phases: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict:
        """
        Run full enrichment pipeline.

        Default phases (in order):
        1. contact_validation (fast, no API calls)
        2. cbe_integration (fast, no API calls)
        3. website_discovery (moderate, HTTP requests)
        4. descriptions (expensive, AI API)
        5. geocoding (slow, rate-limited)

        Args:
            profiles: Profiles to enrich (if None, fetches all from DB)
            phases: List of phase names to run (default: all)
            dry_run: If True, don't update database

        Returns:
            Pipeline results
        """
        # Default phase order (optimized for speed/cost)
        default_phases = [
            ("phase1_contact_validation", "contact_validation"),
            ("phase2_cbe_integration", "cbe_integration"),
            ("phase3_cbe_financials", "cbe_financials"),
            ("phase4_phone_discovery", "phone_discovery"),
            ("phase5_website_discovery", "website_discovery"),
            ("phase6_google_places", "google_places"),
            ("phase7_b2b_provider", "b2b_provider"),
            ("phase8_descriptions", "descriptions"),
            ("phase9_geocoding", "geocoding"),
            ("phase10_deduplication", "deduplication"),
        ]

        if phases:
            phase_map = dict(default_phases)
            default_phases = [(p, phase_map[p]) for p in phases if p in phase_map]

        results = []

        # Fetch profiles if not provided
        if profiles is None:
            profiles = await self.fetch_profiles()

        for phase_name, enricher_name in default_phases:
            try:
                result = await self.run_phase(
                    phase_name=phase_name,
                    enricher_name=enricher_name,
                    profiles=profiles,
                    dry_run=dry_run,
                )
                results.append(result)

                # Update profiles for next phase
                profiles = await self.fetch_profiles()

            except Exception as e:
                logger.error(f"Phase {phase_name} failed: {e}")
                results.append(
                    {
                        "phase": phase_name,
                        "error": str(e),
                        "status": "failed",
                    }
                )

        return {
            "pipeline_completed": True,
            "phases_run": len(results),
            "phases": results,
            "cost_summary": self.costs.get_summary(),
        }

    async def run_from_postgresql(
        self,
        query: str | None = None,
        limit: int | None = None,
        phases: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict:
        """
        Run pipeline directly from PostgreSQL data.

        Args:
            query: Optional search query
            limit: Maximum profiles to process (overall limit across all phases)
            phases: Phases to run
            dry_run: If True, don't update database

        Returns:
            Pipeline results with completion metadata (`completed`, `status`,
            and `exit_reason`) to prevent false-green runs.
        """
        # Use streaming mode for large datasets
        logger.info(
            f"Starting streaming enrichment from PostgreSQL "
            f"(query={query}, limit={limit}, dry_run={dry_run})"
        )

        # Phase mapping
        phase_map = {
            "contact_validation": "phase1_contact_validation",
            "cbe_integration": "phase2_cbe_integration",
            "cbe_financials": "phase3_cbe_financials",
            "phone_discovery": "phase4_phone_discovery",
            "website_discovery": "phase5_website_discovery",
            "google_places": "phase6_google_places",
            "b2b_provider": "phase7_b2b_provider",
            "descriptions": "phase8_descriptions",
            "geocoding": "phase9_geocoding",
            "deduplication": "phase10_deduplication",
        }

        phases_to_run = phases or list(phase_map.keys())
        results = []
        total_processed_overall = 0
        pipeline_completed = True
        pipeline_status = "completed"
        pipeline_exit_reason = "all_phases_completed"

        if not phases_to_run:
            pipeline_exit_reason = "no_phases_requested"

        for phase_name in phases_to_run:
            if limit is not None and total_processed_overall >= limit:
                pipeline_exit_reason = "overall_limit_reached"
                logger.info(
                    f"Stopping pipeline due to overall limit "
                    f"reason={pipeline_exit_reason} "
                    f"overall_processed={total_processed_overall} limit={limit}"
                )
                break

            if phase_name not in phase_map:
                logger.warning(f"Unknown phase: {phase_name}, skipping")
                continue

            job_id = phase_map[phase_name]
            logger.info(f"Running streaming phase: {phase_name} (job_id={job_id}, limit={limit})")

            try:
                result = await self.run_phase_streaming(
                    phase_name=job_id,
                    enricher_name=phase_name,
                    query=query,
                    dry_run=dry_run,
                    limit=limit,  # Pass the limit to respect overall processing cap
                )
                results.append(result)

                phase_processed = int(result.get("total_profiles", 0))
                total_processed_overall += phase_processed
                phase_completed = bool(result.get("completed", True))
                phase_status = str(result.get("status", "completed"))
                phase_exit_reason = str(result.get("exit_reason", "unknown"))

                logger.info(
                    f"Phase {phase_name} finished: status={phase_status} "
                    f"completed={phase_completed} exit_reason={phase_exit_reason} "
                    f"processed={phase_processed} overall_processed={total_processed_overall} "
                    f"limit={limit}"
                )

                if (not phase_completed) or phase_status not in {"completed", "success"}:
                    pipeline_completed = False
                    pipeline_status = "failed" if phase_status == "failed" else "incomplete"
                    pipeline_exit_reason = f"phase_{phase_name}_{phase_exit_reason}"
                    logger.error(
                        f"Stopping pipeline due to non-success phase={phase_name} "
                        f"status={phase_status} completed={phase_completed} "
                        f"exit_reason={phase_exit_reason}"
                    )
                    break

                # If we've hit the overall limit, stop processing more phases
                if limit is not None and total_processed_overall >= limit:
                    pipeline_exit_reason = "overall_limit_reached"
                    logger.info(
                        f"Stopping pipeline due to overall limit "
                        f"reason={pipeline_exit_reason} "
                        f"overall_processed={total_processed_overall} limit={limit}"
                    )
                    break

            except Exception as e:
                logger.error(f"Phase {phase_name} failed: {e}")
                results.append(
                    {
                        "phase": phase_name,
                        "error": str(e),
                        "status": "failed",
                        "completed": False,
                        "exit_reason": "exception",
                    }
                )
                pipeline_completed = False
                pipeline_status = "failed"
                pipeline_exit_reason = f"phase_{phase_name}_exception"
                logger.error(
                    f"Stopping pipeline due to exception phase={phase_name} "
                    f"exit_reason={pipeline_exit_reason}"
                )
                break

        if pipeline_completed and pipeline_exit_reason == "all_phases_completed":
            logger.info("Pipeline completed all requested phases successfully")
        elif pipeline_completed:
            logger.info(
                f"Pipeline completed with intentional stop reason={pipeline_exit_reason} "
                f"overall_processed={total_processed_overall} limit={limit}"
            )
        else:
            logger.error(
                f"Pipeline returning non-success status={pipeline_status} "
                f"completed={pipeline_completed} exit_reason={pipeline_exit_reason} "
                f"overall_processed={total_processed_overall} phases_run={len(results)}"
            )

        return {
            "pipeline_completed": pipeline_completed,
            "completed": pipeline_completed,
            "status": pipeline_status,
            "exit_reason": pipeline_exit_reason,
            "phases_run": len(results),
            "phases": results,
            "total_processed_overall": total_processed_overall,
            "cost_summary": self.costs.get_summary(),
        }

    def get_stats(self) -> dict:
        """Get enrichment statistics."""
        return {
            "enrichers": {
                name: enricher.stats.to_dict() for name, enricher in self.enrichers.items()
            },
            "progress": self.progress.get_summary(),
            "costs": self.costs.get_summary(),
        }


async def run_enrichment_postgresql(
    query: str | None = None,
    limit: int | None = None,
    phases: list[str] | None = None,
    dry_run: bool = True,
    batch_size: int = 100,
    connection_url: str | None = None,
) -> dict:
    """
    Convenience function to run PostgreSQL-based enrichment.

    Args:
        query: Optional search query
        limit: Maximum profiles
        phases: Specific phases to run
        dry_run: Test mode (no updates)
        batch_size: Processing batch size
        connection_url: Optional PostgreSQL connection URL

    Returns:
        Results dict
    """
    pipeline = PostgreSQLEnrichmentPipeline(
        batch_size=batch_size,
        connection_url=connection_url,
    )

    return await pipeline.run_from_postgresql(
        query=query,
        limit=limit,
        phases=phases,
        dry_run=dry_run,
    )
