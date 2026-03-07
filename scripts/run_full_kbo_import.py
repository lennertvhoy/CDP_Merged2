#!/usr/bin/env python3
"""
Master Orchestration Script for Full KBO Import

This script orchestrates the complete import pipeline:
1. Schema preparation (add missing columns if needed)
2. Full KBO data import to PostgreSQL
3. Batch enrichment (CBE, geocoding, website, AI descriptions)
4. Sync to Tracardi
5. Verification and reporting

Usage:
    # Full pipeline
    python scripts/run_full_kbo_import.py
    
    # Test mode (1000 records)
    python scripts/run_full_kbo_import.py --test
    
    # Import only (skip enrichment)
    python scripts/run_full_kbo_import.py --import-only
    
    # Resume from checkpoint
    python scripts/run_full_kbo_import.py --resume

Estimated Duration:
    - Import: 2-3 hours for 1.94M enterprises
    - Enrichment: 8-12 hours (geocoding rate-limited to 1 req/sec)
    - Total: 10-15 hours for complete pipeline
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import get_logger
from scripts.kbo_runtime import resolve_kbo_zip_path

logger = get_logger(__name__)

# ==========================================
# Configuration
# ==========================================

# ==========================================
# Schema Preparation
# ==========================================

async def prepare_schema():
    """Prepare database schema - add missing columns if needed."""
    logger.info("Preparing database schema...")
    
    try:
        import asyncpg
    except ImportError:
        logger.error("asyncpg not installed. Run: pip install asyncpg")
        raise
    
    # Get connection URL
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
    
    conn = await asyncpg.connect(conn_url)
    
    try:
        # Check if enrichment_data column exists
        column_check = await conn.fetchval(
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'companies' AND column_name = 'enrichment_data'
            """
        )
        
        if column_check == 0:
            logger.info("Adding enrichment_data column to companies table...")
            await conn.execute(
                "ALTER TABLE companies ADD COLUMN enrichment_data JSONB"
            )
            logger.info("Column added successfully")
        else:
            logger.info("Schema already prepared")
        
        # Verify counts
        count = await conn.fetchval("SELECT COUNT(*) FROM companies")
        logger.info(f"Current companies in database: {count:,}")
        
    finally:
        await conn.close()


# ==========================================
# Pipeline Stages
# ==========================================

def run_import_script(max_records: int | None = None, resume: bool = False, skip_tracardi: bool = False) -> int:
    """Run the import script."""
    logger.info("=" * 60)
    logger.info("STAGE 1: Importing KBO data to PostgreSQL")
    logger.info("=" * 60)
    
    cmd = [sys.executable, "scripts/import_kbo_full_enriched.py"]
    
    if max_records:
        cmd.extend(["--max-records", str(max_records)])
    if resume:
        cmd.append("--resume")
    if skip_tracardi:
        cmd.append("--skip-tracardi")
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    return result.returncode


def run_enrichment_script(limit: int | None = None, enrichers: str = "cbe,geocoding,website") -> int:
    """Run the enrichment script."""
    logger.info("=" * 60)
    logger.info("STAGE 2: Enriching companies")
    logger.info("=" * 60)
    
    cmd = [sys.executable, "scripts/enrich_companies_batch.py"]
    
    if limit:
        cmd.extend(["--limit", str(limit)])
    cmd.extend(["--enrichers", enrichers])
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    return result.returncode


def run_tracardi_sync() -> int:
    """Sync PostgreSQL data to Tracardi."""
    logger.info("=" * 60)
    logger.info("STAGE 3: Syncing to Tracardi")
    logger.info("=" * 60)
    
    # For now, we sync during import. In future, could add dedicated sync script
    logger.info("Tracardi sync is handled during import stage")
    return 0


async def verify_results():
    """Verify import results."""
    logger.info("=" * 60)
    logger.info("STAGE 4: Verification")
    logger.info("=" * 60)
    
    try:
        import asyncpg
        import httpx
    except ImportError:
        logger.error("Required packages not installed")
        return
    
    # Get connection URL
    conn_url = os.environ.get("DATABASE_URL")
    if not conn_url:
        env_path = Path(__file__).parent.parent / ".env.database"
        if env_path.exists():
            import configparser
            config = configparser.ConfigParser()
            config.read(env_path)
            conn_url = config.get("connection_string", "url", fallback=None)
    
    if not conn_url:
        logger.warning("No database connection, skipping verification")
        return
    
    conn = await asyncpg.connect(conn_url)
    
    try:
        # PostgreSQL stats
        total = await conn.fetchval("SELECT COUNT(*) FROM companies")
        enriched = await conn.fetchval("SELECT COUNT(*) FROM companies WHERE sync_status = 'enriched'")
        with_nace = await conn.fetchval("SELECT COUNT(*) FROM companies WHERE industry_nace_code IS NOT NULL")
        with_address = await conn.fetchval("SELECT COUNT(*) FROM companies WHERE street_address IS NOT NULL")
        with_email = await conn.fetchval("SELECT COUNT(*) FROM companies WHERE main_email IS NOT NULL")
        with_website = await conn.fetchval("SELECT COUNT(*) FROM companies WHERE website_url IS NOT NULL")
        with_geo = await conn.fetchval("SELECT COUNT(*) FROM companies WHERE geo_latitude IS NOT NULL")
        with_ai_desc = await conn.fetchval("SELECT COUNT(*) FROM companies WHERE ai_description IS NOT NULL")
        
        logger.info("PostgreSQL Statistics:")
        logger.info(f"  Total companies: {total:,}")
        logger.info(f"  Enriched: {enriched:,}")
        logger.info(f"  With NACE code: {with_nace:,}")
        logger.info(f"  With address: {with_address:,}")
        logger.info(f"  With email: {with_email:,}")
        logger.info(f"  With website: {with_website:,}")
        logger.info(f"  With geocoding: {with_geo:,}")
        logger.info(f"  With AI description: {with_ai_desc:,}")
        
        # Tracardi stats
        tracardi_url = os.getenv("TRACARDI_API_URL", "http://localhost:8686")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{tracardi_url}/profiles/count")
                if response.status_code == 200:
                    tracardi_count = response.json().get("count", 0)
                    logger.info(f"Tracardi profiles: {tracardi_count:,}")
        except Exception as e:
            logger.warning(f"Could not get Tracardi count: {e}")
        
    finally:
        await conn.close()


# ==========================================
# Database Setup
# ==========================================

def ensure_postgres_running() -> bool:
    """Ensure PostgreSQL is running via Docker."""
    import subprocess
    import time
    
    # Check if PostgreSQL is already running
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=cdp-postgres", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True
        )
        if "cdp-postgres" in result.stdout:
            logger.info("PostgreSQL container already running")
            return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Check if Docker is available
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("Docker not available. Assuming PostgreSQL is running elsewhere.")
        return True
    
    # Start PostgreSQL
    logger.info("Starting PostgreSQL container...")
    compose_file = Path(__file__).parent.parent / "docker-compose.postgres.yml"
    
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "up", "-d"],
            check=True,
            cwd=Path(__file__).parent.parent
        )
        
        # Wait for PostgreSQL to be ready
        logger.info("Waiting for PostgreSQL to be ready...")
        for i in range(30):
            time.sleep(2)
            try:
                result = subprocess.run(
                    ["docker", "exec", "cdp-postgres", "pg_isready", "-U", "cdpadmin", "-d", "cdp"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    logger.info("PostgreSQL is ready")
                    return True
            except Exception:
                pass
        
        logger.error("PostgreSQL failed to start within timeout")
        return False
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start PostgreSQL: {e}")
        return False


# ==========================================
# Main Orchestration
# ==========================================

async def run_pipeline(
    test_mode: bool = False,
    import_only: bool = False,
    resume: bool = False,
    skip_enrichers: list[str] | None = None,
) -> int:
    """Run the complete import pipeline."""
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info("KBO FULL IMPORT PIPELINE")
    logger.info("=" * 60)
    logger.info(f"Start time: {start_time.isoformat()}")
    logger.info(f"Mode: {'TEST' if test_mode else 'FULL'}")
    kbo_zip_path = resolve_kbo_zip_path()
    logger.info(f"KBO zip: {kbo_zip_path}")
    logger.info("=" * 60)
    
    # Check KBO zip exists
    if not kbo_zip_path.exists():
        logger.error(f"KBO zip not found: {kbo_zip_path}")
        return 1
    
    # Ensure PostgreSQL is running
    if not ensure_postgres_running():
        logger.error("Could not ensure PostgreSQL is running")
        return 1
    
    # Give PostgreSQL a moment to fully initialize
    import asyncio
    await asyncio.sleep(3)
    
    try:
        # Stage 0: Prepare schema
        await prepare_schema()
        
        # Stage 1: Import
        max_records = 1000 if test_mode else None
        import_result = run_import_script(
            max_records=max_records,
            resume=resume,
            skip_tracardi=False,  # Always sync to Tracardi during import
        )
        
        if import_result != 0:
            logger.error("Import stage failed")
            return import_result
        
        # Stage 2: Enrichment (skip if import_only)
        if not import_only:
            # Determine which enrichers to run
            all_enrichers = ["cbe", "geocoding", "website", "description"]
            if skip_enrichers:
                enrichers_to_run = [e for e in all_enrichers if e not in skip_enrichers]
            else:
                enrichers_to_run = all_enrichers
            
            enrichers_str = ",".join(enrichers_to_run)
            limit = 1000 if test_mode else None
            
            enrichment_result = run_enrichment_script(
                limit=limit,
                enrichers=enrichers_str,
            )
            
            if enrichment_result != 0:
                logger.warning("Enrichment stage had errors, continuing...")
        
        # Stage 3: Sync to Tracardi (handled during import)
        # Stage 4: Verification
        await verify_results()
        
        # Final summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)
        logger.info(f"End time: {end_time.isoformat()}")
        logger.info(f"Total duration: {duration/3600:.1f} hours")
        logger.info("=" * 60)
        
        return 0
    
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


# ==========================================
# CLI
# ==========================================

def main():
    parser = argparse.ArgumentParser(
        description="Full KBO import pipeline with enrichment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Full production import
    python scripts/run_full_kbo_import.py
    
    # Test mode (1000 records)
    python scripts/run_full_kbo_import.py --test
    
    # Import only, skip enrichment
    python scripts/run_full_kbo_import.py --import-only
    
    # Skip specific enrichers (useful for re-running)
    python scripts/run_full_kbo_import.py --skip-enrichers geocoding,description
    
    # Resume from checkpoint
    python scripts/run_full_kbo_import.py --resume
        """
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: process only 1000 records",
    )
    parser.add_argument(
        "--import-only",
        action="store_true",
        help="Skip enrichment stage",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint",
    )
    parser.add_argument(
        "--skip-enrichers",
        type=str,
        default="",
        help="Comma-separated list of enrichers to skip (cbe,geocoding,website,description)",
    )
    
    args = parser.parse_args()
    
    skip_enrichers = [e.strip() for e in args.skip_enrichers.split(",") if e.strip()]
    
    try:
        result = asyncio.run(run_pipeline(
            test_mode=args.test,
            import_only=args.import_only,
            resume=args.resume,
            skip_enrichers=skip_enrichers if skip_enrichers else None,
        ))
        sys.exit(result)
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
