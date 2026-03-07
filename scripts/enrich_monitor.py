#!/usr/bin/env python3
"""
Monitor enrichment progress by checking database counts.

Environment variables required:
    DATABASE_URL: PostgreSQL connection string
    Or individual:
        DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT (default: 5432)

Example:
    export DATABASE_URL="postgresql://user:pass@host:5432/db?sslmode=require"
    python scripts/enrich_monitor.py
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime


def get_database_url() -> str:
    """Get database URL from environment."""
    if database_url := os.environ.get("DATABASE_URL"):
        return database_url
    
    # Build from individual env vars
    host = os.environ.get("DB_HOST")
    name = os.environ.get("DB_NAME")
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")
    port = os.environ.get("DB_PORT", "5432")
    
    if not all([host, name, user, password]):
        print(
            "ERROR: Database credentials not configured.", file=sys.stderr
        )
        print(
            "Set either DATABASE_URL or DB_HOST, DB_NAME, DB_USER, DB_PASSWORD",
            file=sys.stderr,
        )
        print(
            "Example: export DATABASE_URL='postgresql://user:pass@host:5432/db?sslmode=require'",
            file=sys.stderr,
        )
        sys.exit(1)
    
    return f"postgresql://{user}:{password}@{host}:{port}/{name}?sslmode=require"


async def get_stats():
    """Get enrichment stats from database."""
    db_url = get_database_url()
    conn = await asyncpg.connect(db_url)
    
    total = await conn.fetchval("SELECT COUNT(*) FROM companies")
    pending = await conn.fetchval("SELECT COUNT(*) FROM companies WHERE sync_status = 'pending'")
    enriched = await conn.fetchval("SELECT COUNT(*) FROM companies WHERE sync_status = 'enriched'")
    
    await conn.close()
    
    return {
        "total": total,
        "pending": pending,
        "enriched": enriched,
        "progress_pct": (enriched / total * 100) if total > 0 else 0,
    }


def main():
    """Print current enrichment stats."""
    stats = asyncio.run(get_stats())
    
    print(f"\n{'='*60}")
    print(f"ENRICHMENT STATUS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print(f"Total companies: {stats['total']:,}")
    print(f"Pending: {stats['pending']:,} ({stats['pending']/stats['total']*100:.2f}%)")
    print(f"Enriched: {stats['enriched']:,} ({stats['enriched']/stats['total']*100:.2f}%)")
    print(f"Progress: {stats['progress_pct']:.2f}%")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
