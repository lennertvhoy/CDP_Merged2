#!/usr/bin/env python3
"""
CLI for running data enrichment on profiles using PostgreSQL backend.

Usage:
    python -m scripts.enrich_profiles --help
    python -m scripts.enrich_profiles --dry-run --limit 100
    python -m scripts.enrich_profiles --phase contact_validation --limit 1000
    python -m scripts.enrich_profiles --full --limit 10000
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import configure_logging, get_logger

logger = get_logger(__name__)


def setup_args() -> argparse.Namespace:
    """Set up CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Enrich profiles with external data sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Dry run with 100 profiles
    python -m scripts.enrich_profiles --dry-run --limit 100

    # Run contact validation only
    python -m scripts.enrich_profiles --phase phase1_contact_validation --limit 1000

    # Run website discovery only
    python -m scripts.enrich_profiles --phase phase3_website_discovery --limit 500

    # Full pipeline with 10K profiles
    python -m scripts.enrich_profiles --full --limit 10000

    # Custom query (matches name/KBO/city)
    python -m scripts.enrich_profiles --query "Brussels" --limit 500
        """
    )

    # Operation mode
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test mode - don't update database (default)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Live mode - actually update profiles",
    )

    # Scope
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum profiles to process (default: 100)",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="*",
        help="Search query (default: * for all). Matches name/KBO/city",
    )

    # Phases
    parser.add_argument(
        "--phase",
        type=str,
        choices=[
            "phase1_contact_validation",
            "phase2_cbe_integration",
            "phase3_cbe_financials",
            "phase4_phone_discovery",
            "phase5_website_discovery",
            "phase6_google_places",
            "phase7_b2b_provider",
            "phase8_descriptions",
            "phase9_geocoding",
            "phase10_deduplication",
        ],
        help="Run specific phase only",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pipeline (all phases)",
    )

    # Utilities
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show current enrichment stats and exit",
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Check database connectivity and exit",
    )

    # Configuration
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for processing (default: 100)",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=150.0,
        help="Budget limit in EUR (default: 150)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--connection-url",
        type=str,
        default=None,
        help="PostgreSQL connection URL (optional, defaults to .env.database)",
    )

    # Output
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for results (JSON)",
    )

    args = parser.parse_args()

    # Default to dry-run unless --live specified
    if not args.live:
        args.dry_run = True
    else:
        args.dry_run = False

    return args


async def run_postgresql_pipeline(args: argparse.Namespace) -> dict:
    """Run enrichment using PostgreSQL backend."""
    from src.enrichment.postgresql_pipeline import (
        PostgreSQLEnrichmentPipeline,
        run_enrichment_postgresql,
    )

    # Handle health check
    if args.health_check:
        pipeline = PostgreSQLEnrichmentPipeline(connection_url=args.connection_url)
        health = await pipeline.db.health_check() if pipeline.db else {"status": "not connected"}
        print("\n" + "=" * 60)
        print("POSTGRESQL HEALTH CHECK")
        print("=" * 60)
        print(json.dumps(health, indent=2))
        return health

    # Initialize pipeline
    pipeline = PostgreSQLEnrichmentPipeline(
        batch_size=args.batch_size,
        budget_eur=args.budget,
        connection_url=args.connection_url,
    )

    if args.stats:
        stats = pipeline.get_stats()
        print("\n" + "=" * 60)
        print("ENRICHMENT STATISTICS (PostgreSQL)")
        print("=" * 60)
        print(json.dumps(stats, indent=2))
        return stats

    # Determine phases to run
    phases = None
    if args.phase:
        # Map phase name to enricher name
        phase_to_enricher = {
            "phase1_contact_validation": "contact_validation",
            "phase2_cbe_integration": "cbe_integration",
            "phase3_cbe_financials": "cbe_financials",
            "phase4_phone_discovery": "phone_discovery",
            "phase5_website_discovery": "website_discovery",
            "phase6_google_places": "google_places",
            "phase7_b2b_provider": "b2b_provider",
            "phase8_descriptions": "descriptions",
            "phase9_geocoding": "geocoding",
            "phase10_deduplication": "deduplication",
        }
        phases = [phase_to_enricher.get(args.phase, args.phase)]
        logger.info(f"Running single phase: {args.phase}")
    elif args.full:
        logger.info("Running full pipeline (all phases)")
    else:
        # Default: just contact validation for safety
        phases = ["contact_validation"]
        logger.info("Running contact validation only (use --full for all phases)")

    # Run enrichment
    logger.info("\nStarting PostgreSQL enrichment...")
    start_time = datetime.now(UTC)

    try:
        # Convert * query to None for PostgreSQL
        query = args.query if args.query != "*" else None

        results = await run_enrichment_postgresql(
            query=query,
            limit=args.limit,
            phases=phases,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            connection_url=args.connection_url,
        )

        end_time = datetime.now(UTC)
        duration = (end_time - start_time).total_seconds()

        # Add timing info
        results["duration_seconds"] = duration
        results["started_at"] = start_time.isoformat()
        results["completed_at"] = end_time.isoformat()
        results["backend"] = "postgresql"

        return results

    except Exception as e:
        logger.error(f"PostgreSQL enrichment failed: {e}")
        raise


async def main():
    """Main entry point."""
    args = setup_args()

    # Configure logging
    configure_logging(args.log_level)

    logger.info("=" * 60)
    logger.info("Profile Enrichment")
    logger.info("=" * 60)
    logger.info(f"Mode: {'LIVE' if not args.dry_run else 'DRY RUN'}")
    logger.info(f"Limit: {args.limit}")
    logger.info(f"Query: {args.query}")

    try:
        results = await run_postgresql_pipeline(args)

        # Skip output formatting for utility commands that already printed
        if args.stats or args.health_check:
            return

        # Output results
        print("\n" + "=" * 60)
        print("ENRICHMENT RESULTS")
        print("=" * 60)
        print(json.dumps(results, indent=2, default=str))

        # Save to file if specified
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Results saved to: {output_path}")

        run_completed = bool(results.get("completed", results.get("pipeline_completed", True)))
        run_status = str(results.get("status", "completed"))
        run_exit_reason = str(results.get("exit_reason", "not_provided"))
        if (not run_completed) or run_status not in {"completed", "success"}:
            logger.error(
                "PostgreSQL enrichment ended without full completion: "
                f"status={run_status}, completed={run_completed}, "
                f"exit_reason={run_exit_reason}"
            )
            raise RuntimeError(
                "PostgreSQL enrichment incomplete: "
                f"status={run_status}, completed={run_completed}, "
                f"exit_reason={run_exit_reason}"
            )

        if "duration_seconds" in results:
            logger.info(f"\nCompleted in {results['duration_seconds']:.1f} seconds")

    except Exception as e:
        logger.error(f"Enrichment failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
