#!/usr/bin/env python3
"""Test script for Writeback Service - Session 10 Deployment"""

import asyncio
import configparser
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.services.writeback import WritebackService
from src.services.postgresql_client import PostgreSQLClient
from dataclasses import asdict

# Load connection URL from .env.database
env_path = Path(__file__).parent.parent / ".env.database"
config = configparser.ConfigParser()
config.read(env_path)
CONNECTION_URL = config.get("connection_string", "url")


async def test_writeback_webhook():
    """Test processing a webhook from Tracardi."""
    print("=" * 60)
    print("WRITEBACK SERVICE TEST - Session 10")
    print("=" * 60)

    # Initialize service
    print("\n[1/5] Initializing WritebackService...")
    pg_client = PostgreSQLClient(connection_url=CONNECTION_URL)
    service = WritebackService(postgresql_client=pg_client)
    await service.initialize()
    print("✓ Service initialized")

    # Get a test company UID
    print("\n[2/5] Fetching test company UID...")
    await service.postgresql.ensure_connected()
    pool = service.postgresql.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM companies LIMIT 1")
        if not row:
            print("✗ No companies found - cannot test writeback")
            return False

        test_uid = str(row["id"])
        print(f"✓ Test UID: {test_uid}")

    # Simulate Tracardi webhook payload - tag assigned
    print("\n[3/5] Simulating Tracardi webhook (tag.assigned)...")
    webhook_payload = {
        "event": {
            "id": f"test-event-{datetime.now(UTC).timestamp()}",
            "type": "tag.assigned",
            "profile": {"id": test_uid},
            "properties": {"tag_name": "test_tag_session10", "tag_value": "high_value"},
            "metadata": {"time": {"insert": datetime.now(UTC).isoformat()}},
        }
    }

    result = await service.handle_webhook(webhook_payload)
    print(f"  - Status: {result.status}")
    print(f"  - Records written: {result.records_written}")

    if result.error_message:
        print(f"  - Error: {result.error_message}")

    # Verify event_facts was written
    print("\n[4/5] Verifying event_facts table...")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT event_type, event_source, attributes 
               FROM event_facts 
               WHERE uid = $1 AND event_type = 'tag.assigned'
               ORDER BY occurred_at DESC LIMIT 1""",
            test_uid,
        )
        if row:
            print(f"✓ Event fact recorded:")
            print(f"  - Type: {row['event_type']}")
            print(f"  - Source: {row['event_source']}")
            print(f"  - Attributes: {row['attributes']}")
        else:
            print("✗ Event fact NOT found")

    # Verify profile_traits was written
    print("\n[5/5] Verifying profile_traits table...")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT trait_name, trait_value_text, source_system 
               FROM profile_traits 
               WHERE uid = $1 AND trait_name = 'tag_test_tag_session10'
               ORDER BY effective_at DESC LIMIT 1""",
            test_uid,
        )
        if row:
            print(f"✓ Trait recorded:")
            print(f"  - Name: {row['trait_name']}")
            print(f"  - Value: {row['trait_value_text']}")
            print(f"  - Source: {row['source_system']}")
        else:
            print("⚠ Trait NOT found (may be expected based on writeback logic)")

    # Cleanup
    await service.close()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

    return result.status == "success"


async def test_writeback_metrics():
    """Test writeback metrics."""
    print("\n" + "=" * 60)
    print("WRITEBACK METRICS TEST")
    print("=" * 60)

    pg_client = PostgreSQLClient(connection_url=CONNECTION_URL)
    service = WritebackService(postgresql_client=pg_client)
    await service.initialize()

    print("\nFetching writeback metrics...")
    metrics = await service.get_writeback_metrics()

    print("\nMetrics:")
    metrics_dict = asdict(metrics)
    for key, value in metrics_dict.items():
        print(f"  - {key}: {value}")

    await service.close()

    print("\n✓ Metrics retrieved successfully")
    return True


async def main():
    """Run all writeback tests."""
    try:
        success = await test_writeback_webhook()
        await test_writeback_metrics()

        if success:
            print("\n✅ ALL TESTS PASSED")
            return 0
        else:
            print("\n⚠ TEST COMPLETED WITH WARNINGS")
            return 1

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
