#!/usr/bin/env python3
"""Test script for Projection Service - Session 10 Deployment"""

import asyncio
import configparser
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.services.projection import ProjectionService, ProjectionStatus
from src.services.postgresql_client import PostgreSQLClient

# Load connection URL from .env.database
env_path = Path(__file__).parent.parent / ".env.database"
config = configparser.ConfigParser()
config.read(env_path)
CONNECTION_URL = config.get("connection_string", "url")


async def test_single_projection():
    """Test projecting a single profile to Tracardi."""
    print("=" * 60)
    print("PROJECTION SERVICE TEST - Session 10")
    print("=" * 60)

    # Initialize service
    print("\n[1/6] Initializing ProjectionService...")
    pg_client = PostgreSQLClient(connection_url=CONNECTION_URL)
    service = ProjectionService(postgresql_client=pg_client)
    await service.initialize()
    print("✓ Service initialized")

    # Get a test company from PostgreSQL
    print("\n[2/6] Fetching test company from PostgreSQL...")
    await service.postgresql.ensure_connected()
    pool = service.postgresql.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, company_name, kbo_number, sync_status FROM companies WHERE sync_status = 'enriched' LIMIT 1"
        )
        if not row:
            print("✗ No enriched companies found - cannot test projection")
            return False

        test_uid = str(row["id"])
        test_name = row["company_name"]
        test_kbo = row["kbo_number"]
        print(f"✓ Found test company:")
        print(f"  - UID: {test_uid}")
        print(f"  - Name: {test_name}")
        print(f"  - KBO: {test_kbo}")

    # Check current projection state
    print("\n[3/6] Checking current projection state...")
    state = await service.get_projection_state(test_uid)
    if state:
        print(f"  - Last projected: {state.last_projected_at}")
        print(f"  - Status: {state.projection_status}")
        print(
            f"  - Hash: {state.projection_hash[:16]}..."
            if state.projection_hash
            else "  - Hash: None"
        )
    else:
        print("  - No previous projection state found (first time)")

    # Project the profile
    print(f"\n[4/6] Projecting profile to Tracardi (force=True)...")
    result = await service.project_profile(test_uid, force=True)

    print(f"  - Status: {result.status.value}")
    print(f"  - Tracardi Profile ID: {result.tracardi_profile_id}")
    print(
        f"  - Projection Hash: {result.projection_hash[:16]}..."
        if result.projection_hash
        else "  - Projection Hash: None"
    )

    if result.error_message:
        print(f"  - Error: {result.error_message}")

    if result.status == ProjectionStatus.SUCCESS:
        print("✓ Projection successful")
    elif result.status == ProjectionStatus.SKIPPED:
        print("⚠ Projection skipped (no changes)")
    else:
        print("✗ Projection failed")

    # Verify projection state was recorded
    print("\n[5/6] Verifying projection state in PostgreSQL...")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT projection_status, projection_hash, projected_at 
               FROM activation_projection_state 
               WHERE uid = $1 AND target_system = 'tracardi'""",
            test_uid,
        )
        if row:
            print(f"✓ Projection state recorded:")
            print(f"  - Status: {row['projection_status']}")
            print(
                f"  - Hash: {row['projection_hash'][:16]}..."
                if row["projection_hash"]
                else "  - Hash: None"
            )
            print(f"  - Projected at: {row['projected_at']}")
        else:
            print("✗ Projection state NOT found in database")

    # Verify source_identity_links
    print("\n[6/6] Verifying source_identity_links...")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT tracardi_profile_id FROM source_identity_links WHERE uid = $1", test_uid
        )
        if row and row["tracardi_profile_id"]:
            print(f"✓ Tracardi link recorded: {row['tracardi_profile_id']}")
        else:
            print("⚠ No Tracardi link found (may be expected if projection skipped/failed)")

    # Cleanup
    await service.close()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

    return result.status == ProjectionStatus.SUCCESS


async def test_metrics():
    """Test projection metrics."""
    print("\n" + "=" * 60)
    print("PROJECTION METRICS TEST")
    print("=" * 60)

    pg_client = PostgreSQLClient(connection_url=CONNECTION_URL)
    service = ProjectionService(postgresql_client=pg_client)
    await service.initialize()

    print("\nFetching projection metrics...")
    metrics = await service.get_projection_metrics()

    print("\nMetrics:")
    for key, value in metrics.items():
        print(f"  - {key}: {value}")

    await service.close()

    print("\n✓ Metrics retrieved successfully")
    return True


async def main():
    """Run all projection tests."""
    try:
        success = await test_single_projection()
        await test_metrics()

        if success:
            print("\n✅ ALL TESTS PASSED")
            return 0
        else:
            print("\n⚠ TEST COMPLETED WITH WARNINGS/ERRORS")
            return 1

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
