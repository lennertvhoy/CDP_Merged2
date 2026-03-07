#!/usr/bin/env python3
"""Integration verification for PostgreSQL Search Service.

This script verifies the PostgreSQL-first query plane implementation
by connecting to the live database and running real queries.
"""

import asyncio
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.postgresql_search import CompanySearchFilters, get_search_service
from src.ai_interface.tools.search import search_profiles, aggregate_profiles, get_data_coverage_stats


async def verify_postgresql_search():
    """Verify PostgreSQL search service functionality."""
    print("=" * 60)
    print("PostgreSQL Search Service - Integration Verification")
    print("=" * 60)
    
    # Load database URL from .env.database
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env.database")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("url = "):
                    url = line.strip().split(" = ", 1)[1]
                    os.environ["DATABASE_URL"] = url
                    break
    
    if not os.environ.get("DATABASE_URL"):
        print("❌ DATABASE_URL not found")
        return False
    
    print("\n1. Testing PostgreSQLSearchService connection...")
    try:
        search_service = get_search_service()
        await search_service.ensure_connected()
        print("   ✅ Database connection successful")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return False
    
    print("\n2. Testing get_coverage_stats...")
    try:
        stats = await search_service.get_coverage_stats()
        print(f"   ✅ Coverage stats retrieved")
        print(f"      Total companies: {stats.get('total_companies', 'N/A'):,}")
        coverage = stats.get('coverage', {})
        for field, data in coverage.items():
            print(f"      - {field}: {data.get('count', 0):,} ({data.get('percent', 0)}%)")
    except Exception as e:
        print(f"   ❌ Coverage stats failed: {e}")
    
    print("\n3. Testing count_companies (no filters)...")
    try:
        filters = CompanySearchFilters(limit=10)
        count = await search_service.count_companies(filters)
        print(f"   ✅ Total count: {count:,} companies")
    except Exception as e:
        print(f"   ❌ Count failed: {e}")
    
    print("\n4. Testing search_companies (restaurants in Antwerp)...")
    try:
        # Restaurant NACE codes
        filters = CompanySearchFilters(
            nace_codes=["56101", "56102", "56301"],
            city="Antwerpen",
            limit=5
        )
        result = await search_service.search_companies(filters)
        total = result.get('total', 0)
        results = result.get('result', [])
        print(f"   ✅ Found {total:,} restaurants in Antwerpen")
        print(f"   Sample results:")
        for r in results[:3]:
            print(f"      - {r.get('company_name', 'N/A')} ({r.get('city', 'N/A')})")
    except Exception as e:
        print(f"   ❌ Search failed: {e}")
    
    print("\n5. Testing aggregate_by_field (by city)...")
    try:
        filters = CompanySearchFilters(
            nace_codes=["62010"],  # IT companies
            limit=100
        )
        agg = await search_service.aggregate_by_field(
            group_by="city",
            filters=filters,
            limit=5
        )
        groups = agg.get('groups', [])
        print(f"   ✅ Aggregation successful ({len(groups)} groups)")
        print(f"   Top cities for IT companies:")
        for g in groups[:3]:
            print(f"      - {g.get('group_value', 'N/A')}: {g.get('count', 0):,}")
    except Exception as e:
        print(f"   ❌ Aggregation failed: {e}")
    
    print("\n6. Testing get_data_coverage_stats tool...")
    try:
        result = await get_data_coverage_stats.ainvoke({})
        data = json.loads(result)
        if data.get('status') == 'ok':
            print(f"   ✅ Tool returned successfully")
            total = data.get('total_companies', 0)
            print(f"      Total: {total:,} companies")
        else:
            print(f"   ❌ Tool returned error: {data.get('error')}")
    except Exception as e:
        print(f"   ❌ Tool failed: {e}")
    
    print("\n7. Testing search_profiles tool...")
    try:
        result = await search_profiles.ainvoke({
            "keywords": "restaurant",
            "city": "Gent",
            "limit": 3
        })
        data = json.loads(result)
        if data.get('status') == 'ok':
            total = data.get('counts', {}).get('authoritative_total', 0)
            print(f"   ✅ Tool returned successfully")
            print(f"      Found {total:,} restaurants in Gent")
            print(f"      Backend: {data.get('retrieval_backend', 'unknown')}")
        else:
            print(f"   ❌ Tool returned error: {data.get('error')}")
    except Exception as e:
        print(f"   ❌ Tool failed: {e}")
    
    print("\n8. Testing aggregate_profiles tool...")
    try:
        result = await aggregate_profiles.ainvoke({
            "group_by": "city",
            "keywords": "IT",
            "limit_results": 3
        })
        data = json.loads(result)
        if data.get('status') == 'ok':
            groups = data.get('groups', [])
            print(f"   ✅ Tool returned successfully")
            print(f"      Top 3 cities: {', '.join([g.get('group_value', 'N/A') for g in groups])}")
        else:
            print(f"   ❌ Tool returned error: {data.get('error')}")
    except Exception as e:
        print(f"   ❌ Tool failed: {e}")
    
    print("\n" + "=" * 60)
    print("Verification Complete")
    print("=" * 60)
    
    # Close connection
    from src.services.postgresql_client_optimized import get_postgresql_client
    client = get_postgresql_client()
    await client.disconnect()
    print("\n✅ Database connection closed")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(verify_postgresql_search())
    sys.exit(0 if success else 1)
