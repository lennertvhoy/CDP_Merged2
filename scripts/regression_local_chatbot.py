#!/usr/bin/env python3
"""
Local-only chatbot regression test suite.

Tests core search and aggregation functionality against local PostgreSQL.
Designed to run fast (< 30 seconds) and validate local-only mode.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai_interface.tools import create_data_artifact
from src.ai_interface.tools.search import aggregate_profiles, search_profiles
from src.config import settings


@dataclass
class TestResult:
    name: str
    passed: bool
    duration_ms: float = 0.0
    found_count: int | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ChatbotRegressionTest:
    """Fast local-only regression tests for chatbot queries."""

    def __init__(self) -> None:
        self.results: list[TestResult] = []
        self.start_time: float = 0.0
        
        # Use database URL from settings (env vars or .env files)
        if settings.DATABASE_URL:
            os.environ["DATABASE_URL"] = settings.DATABASE_URL

    async def run_all(self) -> bool:
        """Run all regression tests."""
        print("=" * 70)
        print("Local Chatbot Regression Test Suite")
        print("=" * 70)
        db_url = os.environ.get('DATABASE_URL', 'not set')
        # Mask password in output for security
        if '://' in db_url and '@' in db_url:
            parts = db_url.split('@')
            creds = parts[0].split('://')[1] if '://' in parts[0] else parts[0]
            if ':' in creds:
                masked = parts[0].replace(creds, creds.split(':')[0] + ':***')
                db_url = masked + '@' + '@'.join(parts[1:])
        print(f"Database: {db_url}")
        print()

        tests = [
            self.test_gent_restaurants,
            self.test_brussels_companies,
            self.test_antwerpen_aggregation,
            self.test_nace_code_search,
            self.test_email_domain_search,
            self.test_city_count,
            self.test_artifact_export,
        ]

        for test in tests:
            await self._run_test(test)

        return self._print_summary()

    async def _run_test(self, test_func) -> None:
        """Run a single test and record result."""
        import time
        
        name = test_func.__name__.replace("test_", "").replace("_", " ").title()
        start = time.perf_counter()
        
        try:
            await test_func()
            duration = (time.perf_counter() - start) * 1000
            # Test function should append its own result with details
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self.results.append(TestResult(
                name=name,
                passed=False,
                duration_ms=duration,
                error=str(e)
            ))

    async def test_gent_restaurants(self) -> None:
        """Test: Restaurants in Gent."""
        print("1. Restaurants in Gent")
        print("-" * 40)
        
        result = await search_profiles.ainvoke({
            "keywords": "restaurant",
            "city": "Gent",
        })
        data = json.loads(result)

        total = data.get("counts", {}).get("authoritative_total", 0)
        backend = data.get("retrieval_backend", "unknown")
        companies = data.get("profiles_sample", [])

        passed = data.get("status") == "ok" and backend == "postgresql" and total > 0
        
        status = "✅" if passed else "❌"
        print(f"   {status} Backend: {backend}")
        print(f"   {status} Found: {total} restaurants")
        if companies:
            print(f"   Sample: {companies[0].get('name', 'N/A')}")
        
        self.results.append(TestResult(
            name="Restaurants in Gent",
            passed=passed,
            found_count=total,
            details={"backend": backend, "sample": companies[0] if companies else None}
        ))
        print()

    async def test_brussels_companies(self) -> None:
        """Test: Companies in Brussels (no status filter)."""
        print("2. Companies in Brussels")
        print("-" * 40)
        
        result = await search_profiles.ainvoke({
            "city": "Brussel",
        })
        data = json.loads(result)
        
        total = data.get("counts", {}).get("authoritative_total", 0)
        backend = data.get("retrieval_backend", "unknown")
        
        passed = data.get("status") == "ok" and total > 0
        
        status = "✅" if passed else "❌"
        print(f"   {status} Backend: {backend}")
        print(f"   {status} Found: {total} companies")
        print(f"   ℹ️  Includes all statuses (not just 'active')")
        
        self.results.append(TestResult(
            name="Companies in Brussels",
            passed=passed,
            found_count=total,
            details={"backend": backend}
        ))
        print()

    async def test_antwerpen_aggregation(self) -> None:
        """Test: Top industries in Antwerpen."""
        print("3. Top Industries in Antwerpen")
        print("-" * 40)
        
        result = await aggregate_profiles.ainvoke({
            "city": "Antwerpen",
            "group_by": "nace_code",
            "limit_results": 5
        })
        data = json.loads(result)

        total = data.get("total_matching_profiles", 0)
        groups = data.get("groups", [])

        passed = data.get("status") == "ok" and total > 0 and len(groups) > 0

        status = "✅" if passed else "❌"
        print(f"   {status} Total: {total} companies")
        print(f"   {status} Top industries:")
        for g in groups[:3]:
            print(f"      - {g.get('group_value', 'N/A')}: {g.get('count', 0)}")
        
        self.results.append(TestResult(
            name="Top Industries in Antwerpen",
            passed=passed,
            found_count=total,
            details={"groups": len(groups)}
        ))
        print()

    async def test_nace_code_search(self) -> None:
        """Test: NACE code search."""
        print("4. NACE Code Search (56101 - Restaurants)")
        print("-" * 40)
        
        result = await search_profiles.ainvoke({
            "nace_code": "56101",
        })
        data = json.loads(result)

        total = data.get("counts", {}).get("authoritative_total", 0)
        backend = data.get("retrieval_backend", "unknown")
        applied_nace_codes = data.get("applied_filters", {}).get("nace_codes", [])

        passed = (
            data.get("status") == "ok"
            and total > 0
            and backend == "postgresql"
            and applied_nace_codes == ["56101"]
        )
        
        status = "✅" if passed else "❌"
        print(f"   {status} Backend: {backend}")
        print(f"   {status} Found: {total} companies with NACE 56101")
        
        self.results.append(TestResult(
            name="NACE Code Search",
            passed=passed,
            found_count=total,
            details={"backend": backend, "nace_codes": applied_nace_codes}
        ))
        print()

    async def test_email_domain_search(self) -> None:
        """Test: Email domain search."""
        print("5. Email Domain Search")
        print("-" * 40)
        
        result = await search_profiles.ainvoke({
            "email_domain": "gmail.com",
        })
        data = json.loads(result)

        total = data.get("counts", {}).get("authoritative_total", 0)
        backend = data.get("retrieval_backend", "unknown")
        applied_email_domain = data.get("applied_filters", {}).get("email_domain")

        passed = (
            data.get("status") == "ok"
            and total > 0
            and backend == "postgresql"
            and applied_email_domain == "gmail.com"
        )
        
        status = "✅" if passed else "❌"
        print(f"   {status} Backend: {backend}")
        print(f"   {status} Found: {total} companies with gmail.com")
        
        self.results.append(TestResult(
            name="Email Domain Search",
            passed=passed,
            found_count=total,
            details={"backend": backend, "email_domain": applied_email_domain}
        ))
        print()

    async def test_city_count(self) -> None:
        """Test: Aggregation by city."""
        print("6. Company Count by City")
        print("-" * 40)
        
        result = await aggregate_profiles.ainvoke({
            "group_by": "city",
            "limit_results": 10
        })
        data = json.loads(result)

        total = data.get("total_matching_profiles", 0)
        groups = data.get("groups", [])

        passed = data.get("status") == "ok" and total > 0 and len(groups) > 0
        
        status = "✅" if passed else "❌"
        print(f"   {status} Total companies: {total}")
        print(f"   {status} Top cities:")
        for g in groups[:5]:
            city = g.get("group_value", "N/A") or "Unknown"
            print(f"      - {city}: {g.get('count', 0)}")
        
        self.results.append(TestResult(
            name="Company Count by City",
            passed=passed,
            found_count=total,
            details={"cities": len(groups)}
        ))
        print()

    async def test_artifact_export(self) -> None:
        """Test: Local markdown artifact generation."""
        print("7. Local Artifact Export")
        print("-" * 40)

        result = await create_data_artifact.ainvoke(
            {
                "title": "regression-gent-restaurants",
                "artifact_type": "search_results",
                "output_format": "markdown",
                "keywords": "restaurant",
                "city": "Gent",
                "max_rows": 10,
            }
        )
        data = json.loads(result)

        artifact_path = data.get("artifact_path")
        passed = (
            data.get("status") == "ok"
            and data.get("output_format") == "markdown"
            and artifact_path
            and Path(artifact_path).exists()
        )

        status = "✅" if passed else "❌"
        print(f"   {status} Artifact: {artifact_path or 'missing'}")

        self.results.append(
            TestResult(
                name="Local Artifact Export",
                passed=passed,
                details={"artifact_path": artifact_path},
            )
        )
        print()

    def _print_summary(self) -> bool:
        """Print test summary and return overall pass/fail."""
        print("=" * 70)
        print("Summary")
        print("=" * 70)
        
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        
        print(f"Passed: {passed}/{total}")
        print()
        
        for r in self.results:
            icon = "✅" if r.passed else "❌"
            count_info = f" (found: {r.found_count:,})" if r.found_count is not None else ""
            error_info = f" [ERROR: {r.error}]" if r.error else ""
            print(f"  {icon} {r.name}{count_info}{error_info}")
        
        print()
        print("=" * 70)
        
        if passed == total:
            print("✅ All tests passed - local chatbot regression OK")
            return True
        else:
            print(f"❌ {total - passed} test(s) failed")
            return False


async def main() -> int:
    """Main entry point."""
    tester = ChatbotRegressionTest()
    success = await tester.run_all()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
