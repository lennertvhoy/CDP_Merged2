#!/usr/bin/env python3
"""
Diagnostic test script for Tracardi CDP connectivity and query functionality.
Run this in the deployed environment to verify the chatbot will work correctly.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def test_tracardi_connection():
    """Test basic Tracardi connectivity."""
    print("=" * 60)
    print("TEST 1: Tracardi Connection & Authentication")
    print("=" * 60)

    try:
        from src.services.tracardi import TracardiClient
        from src.config import settings

        print(f"Tracardi API URL: {settings.TRACARDI_API_URL}")
        print(f"Tracardi Username: {settings.TRACARDI_USERNAME}")
        print(f"Tracardi Source ID: {settings.TRACARDI_SOURCE_ID}")

        client = TracardiClient()

        # Test authentication
        await client._ensure_token()
        if client.token:
            print(f"✅ Authentication SUCCESS - Token received")
            print(f"   Token prefix: {client.token[:20]}...")
        else:
            print("❌ Authentication FAILED - No token received")
            return False

        return True

    except Exception as e:
        print(f"❌ Connection FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_tracardi_data_count():
    """Test how many profiles exist in Tracardi."""
    print("\n" + "=" * 60)
    print("TEST 2: Tracardi Profile Count (All Profiles)")
    print("=" * 60)

    try:
        from src.services.tracardi import TracardiClient

        client = TracardiClient()
        result = await client.search_profiles("*", limit=1)

        total = result.get("total", 0)
        print(f"Total profiles in Tracardi: {total}")

        if total > 0:
            print(f"✅ Data check PASSED - Found {total} profiles")
            return True, total
        else:
            print("❌ Data check FAILED - No profiles found in Tracardi")
            print("   This means the KBO data was not loaded properly.")
            return False, 0

    except Exception as e:
        print(f"❌ Query FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, 0


async def test_nace_keyword_resolution():
    """Test NACE code resolution from keywords."""
    print("\n" + "=" * 60)
    print("TEST 3: NACE Code Resolution")
    print("=" * 60)

    try:
        from src.ai_interface.tools import _get_nace_codes_from_keyword

        test_cases = [
            ("IT", ["62010", "63110"]),
            ("bakery", ["10711", "10712"]),
            ("restaurant", ["56101", "56102"]),
        ]

        all_passed = True
        for keyword, expected_prefixes in test_cases:
            codes = _get_nace_codes_from_keyword(keyword)
            print(f"  '{keyword}' -> {codes[:5]}...")

            if codes:
                # Check if at least one expected prefix is present
                has_expected = any(
                    any(code.startswith(prefix) for code in codes)
                    for prefix in expected_prefixes
                )
                if has_expected:
                    print(f"    ✅ Correctly resolves to expected NACE codes")
                else:
                    print(f"    ⚠️ Resolves but unexpected codes")
            else:
                print(f"    ❌ No codes resolved")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"❌ NACE resolution FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_bakery_search_gent():
    """Test the specific query: bakeries in Gent."""
    print("\n" + "=" * 60)
    print("TEST 4: Search Query - 'bakeries in Gent'")
    print("=" * 60)

    try:
        from src.ai_interface.tools import _get_nace_codes_from_keyword
        from src.search_engine.factory import QueryFactory
        from src.search_engine.schema import ProfileSearchParams
        from src.services.tracardi import TracardiClient

        # Step 1: Resolve NACE codes
        nace_codes = _get_nace_codes_from_keyword("bakery")
        print(f"NACE codes for 'bakery': {nace_codes}")

        # Step 2: Build search params
        params = ProfileSearchParams(
            nace_codes=nace_codes,
            city="Gent",
            status="AC"
        )

        # Step 3: Generate queries
        queries = QueryFactory.generate_all(params)
        tql_query = queries.get("tql")
        print(f"TQL query: {tql_query}")

        # Step 4: Execute search
        client = TracardiClient()
        result = await client.search_profiles(tql_query, limit=5)

        total = result.get("total", 0)
        profiles = result.get("result", [])

        print(f"\nResults:")
        print(f"  Total bakeries in Gent: {total}")
        print(f"  Sample profiles returned: {len(profiles)}")

        if profiles:
            print(f"\n  Sample results:")
            for i, p in enumerate(profiles[:3], 1):
                props = p.get("traits") or p.get("data", {}).get("properties", {})
                name = props.get("name") or props.get("kbo_name") or "[No Name]"
                city = props.get("city") or props.get("kbo_city") or "Unknown"
                print(f"    {i}. {name} ({city})")

        if total > 0:
            print(f"\n✅ Bakery search PASSED - Found {total} bakeries in Gent")
            return True, total
        else:
            print(f"\n⚠️ Bakery search returned 0 results")
            print(f"   This could mean:")
            print(f"   - No bakeries in Gent in the data")
            print(f"   - Data not loaded correctly")
            print(f"   - Query syntax issue")
            return False, 0

    except Exception as e:
        print(f"❌ Bakery search FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, 0


async def test_it_companies_brussels():
    """Test the specific query: IT companies in Brussels."""
    print("\n" + "=" * 60)
    print("TEST 5: Search Query - 'IT companies in Brussels'")
    print("=" * 60)

    try:
        from src.ai_interface.tools import _get_nace_codes_from_keyword
        from src.search_engine.factory import QueryFactory
        from src.search_engine.schema import ProfileSearchParams
        from src.services.tracardi import TracardiClient

        # Step 1: Resolve NACE codes
        nace_codes = _get_nace_codes_from_keyword("IT")
        print(f"NACE codes for 'IT': {nace_codes}")

        # Step 2: Build search params
        params = ProfileSearchParams(
            nace_codes=nace_codes,
            city="Brussels",
            status="AC"
        )

        # Step 3: Generate queries
        queries = QueryFactory.generate_all(params)
        tql_query = queries.get("tql")
        print(f"TQL query: {tql_query}")

        # Step 4: Execute search
        client = TracardiClient()
        result = await client.search_profiles(tql_query, limit=5)

        total = result.get("total", 0)
        profiles = result.get("result", [])

        print(f"\nResults:")
        print(f"  Total IT companies in Brussels: {total}")
        print(f"  Sample profiles returned: {len(profiles)}")

        if profiles:
            print(f"\n  Sample results:")
            for i, p in enumerate(profiles[:3], 1):
                props = p.get("traits") or p.get("data", {}).get("properties", {})
                name = props.get("name") or props.get("kbo_name") or "[No Name]"
                city = props.get("city") or props.get("kbo_city") or "Unknown"
                print(f"    {i}. {name} ({city})")

        if total > 0:
            print(f"\n✅ IT search PASSED - Found {total} IT companies in Brussels")
            return True, total
        else:
            print(f"\n⚠️ IT search returned 0 results")
            return False, 0

    except Exception as e:
        print(f"❌ IT search FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, 0


async def main():
    """Run all diagnostic tests."""
    print("\n" + "=" * 60)
    print("TRACARDI CDP DIAGNOSTIC TEST SUITE")
    print("=" * 60)
    print("\nThis script tests if the chatbot can correctly query")
    print("Tracardi for KBO company data.\n")

    results = {}

    # Test 1: Connection
    results["connection"] = await test_tracardi_connection()

    # Test 2: Data count
    results["data_count"], total_profiles = await test_tracardi_data_count()

    # Test 3: NACE resolution
    results["nace_resolution"] = await test_nace_keyword_resolution()

    # Test 4: Bakery search
    results["bakery_gent"], bakery_count = await test_bakery_search_gent()

    # Test 5: IT search
    results["it_brussels"], it_count = await test_it_companies_brussels()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name:20s}: {status}")

    all_passed = all(results.values())

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nThe chatbot is correctly configured and Tracardi has data.")
        print("The chatbot should return actual results for queries like:")
        print(f"  - 'how many bakeries in gent?' -> {bakery_count}")
        print(f"  - 'IT companies in Brussels' -> {it_count}")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        print("\nThe chatbot may not work correctly. Check the errors above.")
        print("\nCommon issues:")
        print("  1. Tracardi is not running or not accessible")
        print("  2. Tracardi credentials are incorrect")
        print("  3. KBO data was not loaded into Tracardi")
        print("  4. Environment variables are not set correctly")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
