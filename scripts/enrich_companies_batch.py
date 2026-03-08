#!/usr/bin/env python3
"""
Batch Enrichment Pipeline for KBO Companies

Enriches imported companies using:
- FREE: CBE Integration (industry classification, size estimates)
- FREE: OpenStreetMap Geocoding (lat/lon coordinates)
- FREE: Website Discovery (URL pattern matching + scraping)
- AZURE/LOCAL: AI Descriptions via Azure OpenAI OR local Ollama

AI Description Options:
    # Use Azure OpenAI (default, paid)
    python scripts/enrich_companies_batch.py --enrichers description

    # Use local Ollama (FREE, requires Ollama running)
    export DESCRIPTION_ENRICHER=ollama
    export OLLAMA_MODEL=llama3.1:8b  # or llama3.2:3b, mistral, etc.
    python scripts/enrich_companies_batch.py --enrichers description

Usage:
    # Enrich all pending companies
    python scripts/enrich_companies_batch.py

    # Enrich with specific enrichers only
    python scripts/enrich_companies_batch.py --enrichers cbe,geocoding,website

    # Limit number of companies
    python scripts/enrich_companies_batch.py --limit 10000

    # Resume from checkpoint
    python scripts/enrich_companies_batch.py --resume
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import get_logger

logger = get_logger(__name__)

# ==========================================
# Configuration
# ==========================================

STATE_FILE = Path("logs/enrichment_state.json")
DEFAULT_BATCH_SIZE = 500
DEFAULT_CHECKPOINT_INTERVAL = 2000

CBE_HAS_USABLE_NACE_SQL = (
    "("
    "NULLIF(BTRIM(COALESCE(industry_nace_code, '')), '') IS NOT NULL "
    "OR CASE "
    "WHEN jsonb_typeof(enrichment_data->'all_nace_codes') = 'array' "
    "THEN jsonb_array_length(enrichment_data->'all_nace_codes') > 0 "
    "ELSE FALSE "
    "END"
    ")"
)

ENRICHER_WHERE_CLAUSES = {
    "cbe": (
        "("
        "(COALESCE(nace_description, '') = '' "
        "OR company_size IS NULL "
        "OR employee_count IS NULL) "
        f"AND {CBE_HAS_USABLE_NACE_SQL}"
        ")"
    ),
    "geocoding": (
        "((geo_latitude IS NULL OR geo_longitude IS NULL) "
        "AND COALESCE(street_address, '') <> '' "
        "AND COALESCE(city, '') <> '')"
    ),
    "website": "(COALESCE(website_url, '') = '')",
    "description": "(COALESCE(ai_description, '') = '')",
}


@dataclass
class EnrichmentStats:
    """Statistics for enrichment process."""
    started_at: datetime = field(default_factory=datetime.now)
    processed: int = 0
    enriched: int = 0
    skipped: int = 0
    failed: int = 0
    errors: int = 0

    # Per-enricher stats
    cbe_success: int = 0
    geocoding_success: int = 0
    website_success: int = 0
    description_success: int = 0
    last_company_id: str | None = None

    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now() - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "processed": self.processed,
            "enriched": self.enriched,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
            "cbe_success": self.cbe_success,
            "geocoding_success": self.geocoding_success,
            "website_success": self.website_success,
            "description_success": self.description_success,
            "last_company_id": self.last_company_id,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }


# Global state
_shutdown_requested = False
_current_stats: EnrichmentStats | None = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    signame = signal.Signals(signum).name
    logger.warning(f"Received {signame}, initiating graceful shutdown...")
    _shutdown_requested = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# ==========================================
# Enrichment Functions
# ==========================================

async def enrich_cbe(company: dict, enricher: Any | None = None) -> dict:
    """Enrich with CBE data (industry classification, size estimates)."""
    if enricher is None:
        from src.enrichment.cbe_integration import CBEIntegrationEnricher

        enricher = CBEIntegrationEnricher(use_api=False)  # Use local data only (free)

    # Extract NACE codes from enrichment_data JSONB if available
    enrichment_data = company.get("enrichment_data", {}) or {}
    if isinstance(enrichment_data, str):
        import json
        try:
            enrichment_data = json.loads(enrichment_data)
        except json.JSONDecodeError:
            enrichment_data = {}

    # Get NACE codes from enrichment_data JSONB (where KBO import stores them)
    nace_codes = enrichment_data.get("all_nace_codes", [])
    if not nace_codes and company.get("industry_nace_code"):
        # Fallback to the column value
        nace_codes = [company.get("industry_nace_code")]

    # Build profile structure expected by enricher
    founded_date = company.get("founded_date") or company.get("founding_year")
    if founded_date and hasattr(founded_date, 'isoformat'):
        start_date = founded_date.isoformat()
    elif founded_date:
        start_date = str(founded_date)
    else:
        start_date = None

    profile = {
        "kbo_number": company.get("kbo_number"),
        "traits": {
            "nace_codes": nace_codes,
            "start_date": start_date,
        }
    }

    try:
        enriched = await enricher.enrich_profile(profile)
        cbe_data = enriched.get("traits", {}).get("cbe_enrichment", {})

        updates = {}

        # Extract industry sector
        if cbe_data.get("industry_sector"):
            updates["nace_description"] = cbe_data["industry_sector"]

        # Extract size estimate
        size_info = cbe_data.get("size_estimate", {})
        if size_info.get("category"):
            updates["company_size"] = size_info["category"]
        if size_info.get("estimated_employees"):
            updates["employee_count"] = size_info["estimated_employees"]

        return updates

    except Exception as e:
        logger.debug(f"CBE enrichment failed for {company.get('kbo_number')}: {e}")
        return {}


async def enrich_geocoding(company: dict, enricher: Any | None = None) -> dict:
    """Enrich with geocoding data (lat/lon coordinates)."""
    if enricher is None:
        from src.enrichment.geocoding import GeocodingEnricher

        enricher = GeocodingEnricher()

    # Skip if no address
    if not company.get("street_address") or not company.get("city"):
        return {}

    # Build profile structure
    profile = {
        "id": company.get("kbo_number"),
        "traits": {
            "street": company.get("street_address"),
            "zipcode": company.get("postal_code"),
            "city": company.get("city"),
            "country": company.get("country", "BE"),
        }
    }

    try:
        enriched = await enricher.enrich_profile(profile)
        traits = enriched.get("traits", {})

        updates = {}

        if traits.get("geo_latitude") and traits.get("geo_longitude"):
            updates["geo_latitude"] = traits["geo_latitude"]
            updates["geo_longitude"] = traits["geo_longitude"]

        return updates

    except Exception as e:
        logger.debug(f"Geocoding failed for {company.get('kbo_number')}: {e}")
        return {}


async def enrich_website(company: dict, enricher: Any | None = None) -> dict:
    """Enrich with website discovery."""
    if enricher is None:
        from src.enrichment.website_discovery import WebsiteDiscoveryEnricher

        enricher = WebsiteDiscoveryEnricher()

    # Skip if already has website
    if company.get("website_url"):
        return {}

    # Build profile structure
    profile = {
        "traits": {
            "name": company.get("company_name"),
            "email": company.get("main_email"),
        }
    }

    try:
        enriched = await enricher.enrich_profile(profile)
        traits = enriched.get("traits", {})

        updates = {}

        if traits.get("website_url"):
            updates["website_url"] = traits["website_url"]

        # Also capture discovered emails/phones
        if traits.get("emails") and not company.get("main_email"):
            updates["main_email"] = traits["emails"][0]

        if traits.get("phone") and not company.get("main_phone"):
            updates["main_phone"] = traits["phone"]

        return updates

    except Exception as e:
        logger.debug(f"Website discovery failed for {company.get('kbo_number')}: {e}")
        return {}


async def enrich_description(company: dict, enricher: Any | None = None) -> dict:
    """Enrich with AI-generated description via Azure OpenAI or Ollama."""
    if enricher is None:
        # Respect DESCRIPTION_ENRICHER env var for fallback enricher
        description_enricher = os.environ.get("DESCRIPTION_ENRICHER", "azure").lower()

        if description_enricher == "ollama":
            from src.enrichment.descriptions_ollama import OllamaDescriptionEnricher

            ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
            ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
            enricher = OllamaDescriptionEnricher(ollama_url=ollama_url, model=ollama_model)
        else:
            from src.enrichment.descriptions import DescriptionEnricher

            enricher = DescriptionEnricher()

    # Skip if no NACE codes
    nace_codes = company.get("all_nace_codes", [])
    if not nace_codes:
        return {}

    # Build profile structure
    profile = {
        "traits": {
            "name": company.get("company_name"),
            "nace_codes": nace_codes,
        }
    }

    try:
        enriched = await enricher.enrich_profile(profile)
        traits = enriched.get("traits", {})

        updates = {}

        if traits.get("business_description"):
            updates["ai_description"] = traits["business_description"]
            updates["ai_description_generated_at"] = datetime.now()

        return updates

    except Exception as e:
        logger.debug(f"Description generation failed for {company.get('kbo_number')}: {e}")
        return {}


# ==========================================
# Batch Processing
# ==========================================

async def process_company(
    company: dict,
    enrichers: list[str],
    enricher_instances: dict[str, Any] | None = None,
) -> tuple[str, dict]:
    """Process a single company with specified enrichers."""
    company_id = str(company.get("id"))
    updates = {}
    enricher_instances = enricher_instances or {}

    for enricher_name in enrichers:
        try:
            if enricher_name == "cbe":
                cbe_updates = await enrich_cbe(
                    company,
                    enricher=enricher_instances.get("cbe"),
                )
                updates.update(cbe_updates)

            elif enricher_name == "geocoding":
                geo_updates = await enrich_geocoding(
                    company,
                    enricher=enricher_instances.get("geocoding"),
                )
                updates.update(geo_updates)

            elif enricher_name == "website":
                web_updates = await enrich_website(
                    company,
                    enricher=enricher_instances.get("website"),
                )
                updates.update(web_updates)

            elif enricher_name == "description":
                desc_updates = await enrich_description(
                    company,
                    enricher=enricher_instances.get("description"),
                )
                updates.update(desc_updates)

        except Exception as e:
            logger.warning(f"Enricher {enricher_name} failed for {company_id}: {e}")

    return company_id, updates


def build_where_clause(enrichers: list[str]) -> str:
    """Build the canonical companies-table selector for the requested enrichers."""
    clauses = [ENRICHER_WHERE_CLAUSES[name] for name in enrichers if name in ENRICHER_WHERE_CLAUSES]
    if not clauses:
        return "TRUE"
    if len(clauses) == 1:
        return clauses[0]
    return "(" + " OR ".join(clauses) + ")"


def build_company_query(
    enrichers: list[str],
    limit: int | None = None,
    start_after_id: str | None = None,
) -> tuple[str, list[Any]]:
    """Build a stable companies selector for chunked enrichment scans."""
    where_clause = build_where_clause(enrichers)
    query = f"""
        SELECT * FROM companies
        WHERE {where_clause}
    """
    params: list[Any] = []

    if start_after_id is not None:
        params.append(start_after_id)
        query += f"\n        AND id > ${len(params)}"

    query += "\n        ORDER BY id"

    if limit is not None:
        params.append(limit)
        query += f"\n        LIMIT ${len(params)}"

    return query, params


def create_enricher_instances(enrichers: list[str]) -> dict[str, Any]:
    """Create shared enricher instances for this run."""
    instances: dict[str, Any] = {}

    if "cbe" in enrichers:
        from src.enrichment.cbe_integration import CBEIntegrationEnricher

        instances["cbe"] = CBEIntegrationEnricher(use_api=False)
    if "geocoding" in enrichers:
        from src.enrichment.geocoding import GeocodingEnricher

        instances["geocoding"] = GeocodingEnricher()
    if "website" in enrichers:
        from src.enrichment.website_discovery import WebsiteDiscoveryEnricher

        instances["website"] = WebsiteDiscoveryEnricher()
    if "description" in enrichers:
        # Select description enricher based on environment variable
        description_enricher = os.environ.get("DESCRIPTION_ENRICHER", "azure").lower()

        if description_enricher == "ollama":
            from src.enrichment.descriptions_ollama import OllamaDescriptionEnricher

            ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
            ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

            instances["description"] = OllamaDescriptionEnricher(
                ollama_url=ollama_url,
                model=ollama_model,
            )
            logger.info(f"Using Ollama description enricher (model: {ollama_model})")
        else:
            from src.enrichment.descriptions import DescriptionEnricher

            instances["description"] = DescriptionEnricher()
            logger.info("Using Azure OpenAI description enricher")

    return instances


async def run_enrichment(
    limit: int | None = None,
    start_after_id: str | None = None,
    enrichers: list[str] | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    resume: bool = False,
) -> EnrichmentStats:
    """Run the enrichment pipeline."""
    global _current_stats, _shutdown_requested

    stats = EnrichmentStats()
    _current_stats = stats

    if enrichers is None:
        enrichers = ["cbe", "geocoding", "website", "description"]

    logger.info(f"Starting enrichment with: {', '.join(enrichers)}")

    # Database connection
    try:
        import asyncpg
    except ImportError:
        logger.error("asyncpg not installed. Run: pip install asyncpg")
        raise

    conn_url = os.environ.get("DATABASE_URL")
    if not conn_url:
        env_path = Path(__file__).parent.parent / ".env.database"
        if env_path.exists():
            import configparser
            config = configparser.ConfigParser()
            config.read(env_path)
            conn_url = config.get("connection_string", "url", fallback=None)

    if not conn_url:
        raise RuntimeError("DATABASE_URL or .env.database connection string required")

    conn = None
    enricher_instances: dict[str, Any] = {}

    try:
        logger.info("Connecting to enrichment database")
        conn = await asyncpg.connect(conn_url)
        logger.info("Enrichment database connected")

        logger.info(f"Creating enricher instances for: {', '.join(enrichers)}")
        enricher_instances = create_enricher_instances(enrichers)
        logger.info("Enricher instances ready")

        # Get companies needing enrichment
        # Select against canonical field coverage rather than trusting sync_status,
        # which can be stale or phase-agnostic after earlier runs.
        logger.info(
            f"Fetching companies to enrich (limit={limit}, start_after_id={start_after_id or 'START'})"
        )
        query, params = build_company_query(
            enrichers,
            limit=limit,
            start_after_id=start_after_id,
        )
        rows = await conn.fetch(query, *params)

        logger.info(f"Found {len(rows)} companies to enrich")

        # Process in batches
        for i in range(0, len(rows), batch_size):
            if _shutdown_requested:
                logger.warning("Shutdown requested, stopping...")
                break

            batch = rows[i:i + batch_size]

            # Process batch concurrently
            tasks = [
                process_company(dict(row), enrichers, enricher_instances=enricher_instances)
                for row in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Apply updates
            for result, row in zip(results, batch, strict=False):
                stats.last_company_id = str(row["id"])
                if isinstance(result, Exception):
                    stats.errors += 1
                    logger.warning(f"Processing failed for {row['id']}: {result}")
                    continue
                company_id, updates = result

                if updates:
                    try:
                        # Build update query
                        set_clauses = []
                        values = []

                        for key, value in updates.items():
                            set_clauses.append(f"{key} = ${len(values) + 1}")
                            values.append(value)

                        set_clauses.append("sync_status = 'enriched'")
                        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

                        query = f"""
                            UPDATE companies
                            SET {', '.join(set_clauses)}
                            WHERE id = ${len(values) + 1}
                        """
                        values.append(row['id'])

                        await conn.execute(query, *values)
                        stats.enriched += 1

                        # Track per-enricher success
                        if "nace_description" in updates or "company_size" in updates:
                            stats.cbe_success += 1
                        if "geo_latitude" in updates:
                            stats.geocoding_success += 1
                        if "website_url" in updates:
                            stats.website_success += 1
                        if "ai_description" in updates:
                            stats.description_success += 1

                    except Exception as e:
                        logger.error(f"Update failed for {company_id}: {e}")
                        stats.failed += 1
                else:
                    stats.skipped += 1
                    # Mark as processed even if no updates
                    try:
                        await conn.execute(
                            "UPDATE companies SET sync_status = 'enriched', updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                            row['id']
                        )
                    except Exception as e:
                        logger.error(f"Status update failed for {company_id}: {e}")

            stats.processed += len(batch)

            # Progress logging
            if stats.processed % DEFAULT_CHECKPOINT_INTERVAL == 0:
                logger.info(
                    f"Progress: {stats.processed:,} processed | "
                    f"Enriched: {stats.enriched:,} | "
                    f"Skipped: {stats.skipped:,} | "
                    f"Failed: {stats.failed:,} | "
                    f"Rate: {stats.processed / stats.elapsed_seconds:.1f}/s"
                )
                logger.info(
                    f"  CBE: {stats.cbe_success} | "
                    f"Geo: {stats.geocoding_success} | "
                    f"Web: {stats.website_success} | "
                    f"Desc: {stats.description_success}"
                )

        # Final stats
        logger.info("=" * 60)
        logger.info("ENRICHMENT COMPLETE")
        logger.info(f"Total processed: {stats.processed:,}")
        logger.info(f"Enriched: {stats.enriched:,}")
        logger.info(f"Skipped: {stats.skipped:,}")
        logger.info(f"Failed: {stats.failed:,}")
        logger.info(f"Errors: {stats.errors}")
        logger.info("-" * 60)
        logger.info(f"CBE enrichments: {stats.cbe_success}")
        logger.info(f"Geocoding enrichments: {stats.geocoding_success}")
        logger.info(f"Website discoveries: {stats.website_success}")
        logger.info(f"AI descriptions: {stats.description_success}")
        logger.info(f"Last company ID: {stats.last_company_id or 'n/a'}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

    finally:
        if conn is not None:
            await conn.close()
        for enricher in enricher_instances.values():
            finish = getattr(enricher, "finish", None)
            if callable(finish):
                finish()

    return stats


# ==========================================
# CLI
# ==========================================

def main():
    parser = argparse.ArgumentParser(
        description="Batch enrichment pipeline for KBO companies"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum companies to process",
    )
    parser.add_argument(
        "--start-after-id",
        type=str,
        default=None,
        help="Resume the canonical scan strictly after this company UUID",
    )
    parser.add_argument(
        "--enrichers",
        type=str,
        default="cbe,geocoding,website,description",
        help="Comma-separated list of enrichers to run (default: all)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Batch size (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint",
    )

    args = parser.parse_args()

    enrichers = [e.strip() for e in args.enrichers.split(",")]

    try:
        stats = asyncio.run(run_enrichment(
            limit=args.limit,
            start_after_id=args.start_after_id,
            enrichers=enrichers,
            batch_size=args.batch_size,
            resume=args.resume,
        ))

        sys.exit(0 if stats.errors < 100 else 1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
