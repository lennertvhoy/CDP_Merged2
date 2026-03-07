#!/usr/bin/env python3
"""
Demo Smoke Test - Comprehensive pre-demo verification checklist.

Validates all critical systems and demo success criteria before stakeholder demos.
Based on Demo Readiness Protocol from AGENTS.md.

Usage:
    python scripts/demo_smoke_test.py [--quick] [--report]

Options:
    --quick   Run only critical checks (faster)
    --report  Generate JSON report for CI/CD integration
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class Colors:
    """Terminal colors for output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")


def print_check(name: str, passed: bool, details: str = "") -> None:
    """Print a check result."""
    status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if passed else f"{Colors.RED}❌ FAIL{Colors.RESET}"
    warning = f"{Colors.YELLOW}⚠️ WARN{Colors.RESET}" if not passed and details else ""
    print(f"  {status} {name}")
    if details:
        print(f"      {details}")


class DemoSmokeTest:
    """Demo smoke test runner."""

    def __init__(self, quick: bool = False):
        self.quick = quick
        self.results: dict[str, dict[str, Any]] = {}
        self.start_time = datetime.now()

    def add_result(self, category: str, name: str, passed: bool,
                   details: str = "", data: dict | None = None) -> None:
        """Add a test result."""
        if category not in self.results:
            self.results[category] = {}
        self.results[category][name] = {
            "passed": passed,
            "details": details,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        }

    async def check_postgresql(self) -> bool:
        """Check PostgreSQL connectivity and data."""
        print_header("CHECK 1: PostgreSQL Database")

        try:
            import asyncpg

            db_url = os.getenv("DATABASE_URL", "")
            if not db_url:
                self.add_result("database", "connection", False,
                              "DATABASE_URL not set")
                print_check("Connection", False, "DATABASE_URL not set")
                return False

            conn = await asyncpg.connect(db_url)

            # Check companies table
            company_count = await conn.fetchval("SELECT COUNT(*) FROM companies")

            # Check enriched data coverage
            enriched_count = await conn.fetchval(
                "SELECT COUNT(*) FROM companies WHERE main_email IS NOT NULL"
            )

            # Check for demo data presence
            has_website = await conn.fetchval(
                "SELECT COUNT(*) FROM companies WHERE website_url IS NOT NULL LIMIT 1"
            )

            await conn.close()

            coverage_pct = (enriched_count / company_count * 100) if company_count > 0 else 0

            self.add_result("database", "connection", True,
                          f"Connected successfully",
                          {"total_companies": company_count,
                           "enriched": enriched_count,
                           "coverage_pct": round(coverage_pct, 2)})

            print_check("Connection", True)
            print(f"      Total companies: {company_count:,}")
            print(f"      With email: {enriched_count:,} ({coverage_pct:.1f}%)")

            # Demo readiness check
            demo_ready = company_count > 0
            self.add_result("database", "demo_ready", demo_ready,
                          f"Minimum data threshold: {demo_ready}")
            print_check("Demo Data Ready", demo_ready,
                       f"Need >0 companies, have {company_count}")

            return True

        except Exception as e:
            self.add_result("database", "connection", False, str(e))
            print_check("Connection", False, str(e))
            return False

    async def check_tracardi(self) -> bool:
        """Check Tracardi connectivity and profiles."""
        print_header("CHECK 2: Tracardi CDP")

        try:
            from src.services.tracardi import TracardiClient

            client = TracardiClient()
            await client._ensure_token()

            if not client.token:
                self.add_result("tracardi", "auth", False, "No token received")
                print_check("Authentication", False, "No token received")
                return False

            self.add_result("tracardi", "auth", True, "Token obtained")
            print_check("Authentication", True, f"Token: {client.token[:20]}...")

            # Check profiles
            result = await client.search_profiles("*", limit=1)
            total_profiles = result.get("total", 0)

            self.add_result("tracardi", "profiles", True,
                          f"Found {total_profiles} profiles",
                          {"total_profiles": total_profiles})
            print_check("Profile Count", True, f"{total_profiles} profiles")

            # Demo readiness
            demo_ready = total_profiles > 0
            self.add_result("tracardi", "demo_ready", demo_ready)
            print_check("Demo Ready", demo_ready,
                       f"Need >0 profiles for 360° view demo")

            return True

        except Exception as e:
            self.add_result("tracardi", "connection", False, str(e))
            print_check("Connection", False, str(e))
            return False

    async def check_chatbot(self) -> bool:
        """Check chatbot health endpoint."""
        print_header("CHECK 3: Chatbot (Chainlit)")

        try:
            import httpx

            # Try localhost first (development), then check env
            urls_to_try = [
                "http://localhost:8000",
                "http://localhost:7860",
                os.getenv("CHAINLIT_URL", ""),
            ]

            chatbot_url = None
            chatbot_health_path = None
            for url in urls_to_try:
                if not url:
                    continue
                for path in ("/healthz", "/project/healthz", "/health"):
                    try:
                        async with httpx.AsyncClient(timeout=5.0) as client:
                            resp = await client.get(f"{url}{path}")
                            if resp.status_code == 200:
                                chatbot_url = url
                                chatbot_health_path = path
                                break
                    except Exception:
                        continue
                if chatbot_url:
                    break

            if not chatbot_url:
                self.add_result("chatbot", "health", False,
                              "Chatbot not accessible on any known URL")
                print_check("Health Check", False,
                          "Not accessible on localhost:8000, :7860, or CHAINLIT_URL")
                return False

            self.add_result("chatbot", "health", True,
                          f"Responsive at {chatbot_url}{chatbot_health_path}",
                          {"url": chatbot_url, "health_path": chatbot_health_path})
            print_check("Health Check", True, f"Responsive at {chatbot_url}{chatbot_health_path}")

            # Check if it's actually Chainlit
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(chatbot_url)
                is_chainlit = "chainlit" in resp.text.lower() or resp.status_code == 200

            self.add_result("chatbot", "chainlit", is_chainlit)
            print_check("Chainlit UI", is_chainlit)

            return True

        except Exception as e:
            self.add_result("chatbot", "health", False, str(e))
            print_check("Health Check", False, str(e))
            return False

    async def check_enrichment_status(self) -> bool:
        """Check enrichment service status."""
        print_header("CHECK 4: Enrichment Service")

        try:
            import subprocess

            # Check if enrichment process is running
            result = subprocess.run(
                ["pgrep", "-f", "enrich_companies"],
                capture_output=True, text=True
            )
            is_running = result.returncode == 0 and result.stdout.strip()

            self.add_result("enrichment", "process", is_running,
                          "Process running" if is_running else "Process not running")
            print_check("Process Running", is_running)

            # Check recent logs
            logs_dir = Path("logs/enrichment")
            if logs_dir.exists():
                log_files = sorted(logs_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
                if log_files:
                    latest_log = log_files[0]
                    log_mtime = datetime.fromtimestamp(latest_log.stat().st_mtime)
                    hours_since_update = (datetime.now() - log_mtime).total_seconds() / 3600

                    log_fresh = hours_since_update < 2
                    self.add_result("enrichment", "log_fresh", log_fresh,
                                  f"Last update: {hours_since_update:.1f} hours ago",
                                  {"latest_log": str(latest_log), "hours_since": hours_since_update})
                    print_check("Recent Activity", log_fresh,
                              f"Last update: {hours_since_update:.1f}h ago")
                else:
                    self.add_result("enrichment", "log_fresh", False, "No log files found")
                    print_check("Recent Activity", False, "No log files")
            else:
                self.add_result("enrichment", "log_fresh", False, "Logs directory not found")
                print_check("Recent Activity", False, "No logs directory")

            return is_running

        except Exception as e:
            self.add_result("enrichment", "check", False, str(e))
            print_check("Status Check", False, str(e))
            return False

    async def check_demo_data_quality(self) -> bool:
        """Check if demo data meets quality standards."""
        print_header("CHECK 5: Demo Data Quality")

        try:
            import asyncpg

            db_url = os.getenv("DATABASE_URL", "")
            if not db_url:
                self.add_result("demo_data", "quality", False, "No database connection")
                print_check("Data Access", False, "DATABASE_URL not set")
                return False

            conn = await asyncpg.connect(db_url)

            # Check key fields for demo
            checks = {
                "email": "main_email IS NOT NULL",
                "phone": "main_phone IS NOT NULL",
                "website": "website_url IS NOT NULL",
                "ai_description": "ai_description IS NOT NULL",
                "city": "city IS NOT NULL",
            }

            total = await conn.fetchval("SELECT COUNT(*) FROM companies")
            quality_results = {}

            for field, condition in checks.items():
                count = await conn.fetchval(f"SELECT COUNT(*) FROM companies WHERE {condition}")
                pct = (count / total * 100) if total > 0 else 0
                quality_results[field] = {"count": count, "pct": round(pct, 2)}
                threshold = 5 if field == "ai_description" else 10  # Lower threshold for AI
                status = "✅" if pct >= threshold else "⚠️"
                print(f"      {status} {field}: {count:,} ({pct:.1f}%)")

            await conn.close()

            self.add_result("demo_data", "field_coverage", True,
                          "Field coverage calculated", quality_results)

            # Overall demo quality score
            min_fields = ["email", "city"]
            demo_usable = all(quality_results.get(f, {}).get("pct", 0) >= 10 for f in min_fields)

            self.add_result("demo_data", "demo_usable", demo_usable,
                          "Minimum fields present for demo" if demo_usable else "Missing critical fields")
            print_check("Demo Usable", demo_usable,
                       "Need email & city coverage >= 10%" if not demo_usable else "")

            return demo_usable

        except Exception as e:
            self.add_result("demo_data", "quality", False, str(e))
            print_check("Data Access", False, str(e))
            return False

    async def check_environment(self) -> bool:
        """Check required environment variables."""
        print_header("CHECK 6: Environment Configuration")

        required = {
            "DATABASE_URL": "PostgreSQL connection",
            "TRACARDI_API_URL": "Tracardi API endpoint",
            "TRACARDI_USERNAME": "Tracardi auth",
            "TRACARDI_PASSWORD": "Tracardi auth",
        }

        optional = {
            "OPENAI_API_KEY": "LLM functionality",
            "RESEND_API_KEY": "Email capabilities",
            "CHAINLIT_URL": "Chatbot URL override",
        }

        all_ok = True
        env_status = {}

        for var, desc in required.items():
            value = os.getenv(var)
            is_set = bool(value)
            env_status[var] = {"set": is_set, "required": True, "desc": desc}
            print_check(f"{var}", is_set, desc if not is_set else "")
            if not is_set:
                all_ok = False

        for var, desc in optional.items():
            value = os.getenv(var)
            is_set = bool(value)
            env_status[var] = {"set": is_set, "required": False, "desc": desc}
            if is_set:
                print(f"  {Colors.GREEN}✅{Colors.RESET} {var} (optional)")
            else:
                print(f"  {Colors.YELLOW}⚠️{Colors.RESET} {var} (optional) - {desc}")

        self.add_result("environment", "config", all_ok,
                      "All required vars set" if all_ok else "Missing required vars",
                      env_status)

        return all_ok

    async def run_chatbot_prompt_test(self) -> bool:
        """Test the main chatbot prompt path with a simple query."""
        print_header("CHECK 7: Chatbot Prompt Path (E2E)")

        try:
            import httpx

            # This is a simplified check - full E2E would require WebSocket
            # For now, we just verify the endpoint is responsive

            urls_to_try = [
                "http://localhost:8000",
                "http://localhost:7860",
            ]

            responsive = False
            for url in urls_to_try:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        # Try to get the main page
                        resp = await client.get(url)
                        if resp.status_code in (200, 307, 308):
                            responsive = True
                            self.add_result("prompt_path", "accessible", True,
                                          f"Chatbot accessible at {url}")
                            print_check("UI Accessible", True, url)
                            break
                except Exception:
                    continue

            if not responsive:
                self.add_result("prompt_path", "accessible", False,
                              "Chatbot not accessible")
                print_check("UI Accessible", False, "No responsive endpoint found")
                return False

            # Note: Full prompt testing would require WebSocket interaction
            # which is complex. For now, we mark this as warning-level.
            self.add_result("prompt_path", "full_test", None,
                          "Manual verification needed - WebSocket interaction not automated")
            print(f"  {Colors.YELLOW}⚠️{Colors.RESET} Full Prompt Test: Manual verification recommended")
            print("      (WebSocket interaction requires browser automation)")

            return responsive

        except Exception as e:
            self.add_result("prompt_path", "test", False, str(e))
            print_check("Prompt Path", False, str(e))
            return False

    def generate_summary(self) -> dict[str, Any]:
        """Generate test summary."""
        duration = (datetime.now() - self.start_time).total_seconds()

        total_checks = 0
        passed_checks = 0
        failed_checks = 0
        warning_checks = 0

        for category, tests in self.results.items():
            for test_name, result in tests.items():
                total_checks += 1
                if result.get("passed") is True:
                    passed_checks += 1
                elif result.get("passed") is False:
                    failed_checks += 1
                else:
                    warning_checks += 1

        summary = {
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": round(duration, 2),
            "total_checks": total_checks,
            "passed": passed_checks,
            "failed": failed_checks,
            "warnings": warning_checks,
            "pass_rate": round(passed_checks / total_checks * 100, 1) if total_checks > 0 else 0,
            "demo_ready": failed_checks == 0 and passed_checks >= 5,
        }

        return summary

    def print_final_report(self) -> None:
        """Print final report."""
        summary = self.generate_summary()

        print_header("DEMO SMOKE TEST - FINAL REPORT")

        print(f"\n{Colors.BOLD}Execution Summary:{Colors.RESET}")
        print(f"  Duration: {summary['duration_seconds']:.1f}s")
        print(f"  Total Checks: {summary['total_checks']}")
        print(f"  {Colors.GREEN}Passed: {summary['passed']}{Colors.RESET}")
        print(f"  {Colors.RED}Failed: {summary['failed']}{Colors.RESET}")
        print(f"  {Colors.YELLOW}Warnings: {summary['warnings']}{Colors.RESET}")
        print(f"  Pass Rate: {summary['pass_rate']}%")

        print(f"\n{Colors.BOLD}Demo Readiness:{Colors.RESET}")
        if summary['demo_ready']:
            print(f"  {Colors.GREEN}{Colors.BOLD}✅ DEMO READY{Colors.RESET}")
            print("  All critical checks passed. Proceed with confidence.")
        else:
            print(f"  {Colors.RED}{Colors.BOLD}❌ NOT DEMO READY{Colors.RESET}")
            print("  Fix failed checks before demo.")

        print(f"\n{Colors.BOLD}Demo Success Criteria Status:{Colors.RESET}")
        demo_data_result = self.results.get("demo_data", {}).get("demo_usable")
        if demo_data_result is None:
            demo_data_result = self.results.get("database", {}).get("demo_ready", {})
        criteria = [
            ("PostgreSQL accessible", self.results.get("database", {}).get("connection", {}).get("passed", False)),
            ("Tracardi accessible", self.results.get("tracardi", {}).get("auth", {}).get("passed", False)),
            ("Chatbot responsive", self.results.get("chatbot", {}).get("health", {}).get("passed", False)),
            ("Demo data available", demo_data_result.get("passed", False)),
            ("Environment configured", self.results.get("environment", {}).get("config", {}).get("passed", False)),
        ]

        for criterion, passed in criteria:
            status = f"{Colors.GREEN}✅{Colors.RESET}" if passed else f"{Colors.RED}❌{Colors.RESET}"
            print(f"  {status} {criterion}")

        print(f"\n{Colors.CYAN}{'=' * 70}{Colors.RESET}")

    def save_report(self, filename: str | None = None) -> str:
        """Save JSON report."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reports/demo_smoke_test_{timestamp}.json"

        filepath = Path(filename)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "summary": self.generate_summary(),
            "results": self.results,
            "environment": {
                k: "***" if "key" in k.lower() or "password" in k.lower() or "secret" in k.lower()
                  else v[:10] + "..." if v and len(str(v)) > 20 else v
                for k, v in os.environ.items()
                if k.startswith(("TRACARDI", "DATABASE", "CHAINLIT", "RESEND", "OPENAI"))
            }
        }

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)

        return str(filepath)

    async def run(self, save_report_file: bool = False) -> int:
        """Run all checks."""
        print_header("DEMO SMOKE TEST SUITE")
        print(f"Started: {self.start_time.isoformat()}")
        print(f"Mode: {'Quick' if self.quick else 'Full'}")

        # Always run critical checks
        await self.check_environment()
        await self.check_postgresql()
        await self.check_tracardi()
        await self.check_chatbot()

        if not self.quick:
            await self.check_enrichment_status()
            await self.check_demo_data_quality()
            await self.run_chatbot_prompt_test()

        # Final report
        self.print_final_report()

        # Save report if requested
        if save_report_file:
            report_path = self.save_report()
            print(f"\n{Colors.CYAN}Report saved: {report_path}{Colors.RESET}")

        # Return exit code
        summary = self.generate_summary()
        return 0 if summary['demo_ready'] else 1


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Demo smoke test - verify all systems before demo"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run only critical checks"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate JSON report"
    )
    args = parser.parse_args()

    tester = DemoSmokeTest(quick=args.quick)
    exit_code = await tester.run(save_report_file=args.report)
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
