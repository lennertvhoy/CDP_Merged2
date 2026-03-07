#!/usr/bin/env python3
"""
Monitoring dashboard for Projection and Writeback Services.

Usage:
    python scripts/monitor_projection.py
    python scripts/monitor_projection.py --watch  # Auto-refresh every 30s
"""

import argparse
import asyncio
import configparser
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.services.projection import ProjectionService
from src.services.writeback import WritebackService
from src.services.postgresql_client import PostgreSQLClient

# Load connection URL from .env.database
env_path = Path(__file__).parent.parent / ".env.database"
config = configparser.ConfigParser()
config.read(env_path)
CONNECTION_URL = config.get("connection_string", "url")


def format_count(count: int) -> str:
    """Format large numbers with commas."""
    return f"{count:,}"


def format_duration(seconds: float | None) -> str:
    """Format duration in human-readable form."""
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


async def get_projection_metrics() -> dict:
    """Get projection metrics from ProjectionService."""
    pg_client = PostgreSQLClient(connection_url=CONNECTION_URL)
    service = ProjectionService(postgresql_client=pg_client)
    await service.initialize()

    try:
        metrics = await service.get_projection_metrics()
    except Exception as e:
        metrics = {"error": str(e)}

    await service.close()
    return metrics


async def get_writeback_metrics() -> dict:
    """Get writeback metrics from WritebackService."""
    pg_client = PostgreSQLClient(connection_url=CONNECTION_URL)
    service = WritebackService(postgresql_client=pg_client)
    await service.initialize()

    try:
        metrics = await service.get_writeback_metrics()
        metrics = {
            "total_events_processed": metrics.total_events_processed,
            "events_by_type": metrics.events_by_type,
            "traits_created": metrics.traits_created,
            "ai_decisions_created": metrics.ai_decisions_created,
            "avg_processing_time_ms": metrics.avg_processing_time_ms,
            "last_writeback_at": metrics.last_writeback_at,
        }
    except Exception as e:
        metrics = {"error": str(e)}

    await service.close()
    return metrics


async def get_enrichment_status() -> dict:
    """Get current enrichment status from PostgreSQL."""
    pg_client = PostgreSQLClient(connection_url=CONNECTION_URL)
    await pg_client.connect()

    try:
        pool = pg_client.pool
        async with pool.acquire() as conn:
            # Get sync status distribution
            status_rows = await conn.fetch(
                """SELECT sync_status, COUNT(*) as count 
                   FROM companies GROUP BY sync_status"""
            )

            # Get total count
            total_row = await conn.fetchrow("SELECT COUNT(*) FROM companies")

            # Get enriched count with contact data
            contact_row = await conn.fetchrow(
                """SELECT COUNT(*) FROM companies 
                   WHERE sync_status = 'enriched' 
                   AND (main_email IS NOT NULL OR main_phone IS NOT NULL)"""
            )

            status_dist = {row["sync_status"]: row["count"] for row in status_rows}

            return {
                "total": total_row[0],
                "sync_status": status_dist,
                "with_contact_data": contact_row[0],
            }
    except Exception as e:
        return {"error": str(e)}
    finally:
        await pg_client.disconnect()


async def display_dashboard():
    """Display the monitoring dashboard."""
    print("\n" + "=" * 70)
    print(f" CDP PROJECTION & ENRICHMENT MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Projection Metrics
    print("\n📊 PROJECTION METRICS (PostgreSQL → Tracardi)")
    print("-" * 50)
    proj_metrics = await get_projection_metrics()

    if "error" in proj_metrics:
        print(f"  Error: {proj_metrics['error']}")
    else:
        counts = proj_metrics.get("projection_counts", {})
        print(f"  Success:        {format_count(counts.get('success', 0))}")
        print(f"  Failed:         {format_count(counts.get('failed', 0))}")
        print(f"  Pending:        {format_count(proj_metrics.get('pending_projection', 0))}")
        print(f"  Avg Lag:        {format_duration(proj_metrics.get('avg_lag_seconds'))}")
        print(f"  Max Lag:        {format_duration(proj_metrics.get('max_lag_seconds'))}")

    # Writeback Metrics
    print("\n🔄 WRITEBACK METRICS (Tracardi → PostgreSQL)")
    print("-" * 50)
    wb_metrics = await get_writeback_metrics()

    if "error" in wb_metrics:
        print(f"  Error: {wb_metrics['error']}")
    else:
        print(f"  Events Processed:  {format_count(wb_metrics.get('total_events_processed', 0))}")
        print(f"  Traits Created:    {format_count(wb_metrics.get('traits_created', 0))}")
        print(f"  AI Decisions:      {format_count(wb_metrics.get('ai_decisions_created', 0))}")

        events_by_type = wb_metrics.get("events_by_type", {})
        if events_by_type:
            print(f"  Events by Type:")
            for event_type, count in sorted(events_by_type.items(), key=lambda x: -x[1])[:5]:
                print(f"    - {event_type}: {format_count(count)}")

        last_wb = wb_metrics.get("last_writeback_at")
        if last_wb:
            print(f"  Last Writeback:    {last_wb}")

    # Enrichment Status
    print("\n⚡ ENRICHMENT STATUS")
    print("-" * 50)
    enrich_status = await get_enrichment_status()

    if "error" in enrich_status:
        print(f"  Error: {enrich_status['error']}")
    else:
        total = enrich_status.get("total", 0)
        sync_status = enrich_status.get("sync_status", {})

        pending = sync_status.get("pending", 0)
        enriched = sync_status.get("enriched", 0)

        print(f"  Total Companies:    {format_count(total)}")
        print(f"  Pending:            {format_count(pending)} ({pending / total * 100:.1f}%)")
        print(f"  Enriched:           {format_count(enriched)} ({enriched / total * 100:.1f}%)")
        print(f"  With Contact Data:  {format_count(enrich_status.get('with_contact_data', 0))}")

    print("\n" + "=" * 70)
    print(" Legend:")
    print("   Projection = Data flow PostgreSQL → Tracardi")
    print("   Writeback  = Data flow Tracardi → PostgreSQL")
    print("=" * 70)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="CDP Projection & Enrichment Monitor")
    parser.add_argument("--watch", "-w", action="store_true", help="Auto-refresh every 30 seconds")
    parser.add_argument(
        "--interval", "-i", type=int, default=30, help="Refresh interval in seconds (default: 30)"
    )
    args = parser.parse_args()

    if args.watch:
        import time

        try:
            while True:
                await display_dashboard()
                print(f"\n⏱️  Refreshing in {args.interval}s... (Ctrl+C to exit)")
                await asyncio.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n\n👋 Monitor stopped.")
    else:
        await display_dashboard()


if __name__ == "__main__":
    asyncio.run(main())
