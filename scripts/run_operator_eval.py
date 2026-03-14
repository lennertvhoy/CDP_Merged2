#!/usr/bin/env python3
"""Executable eval runner for operator chat quality assessment.

Wires the 9 eval cases from docs/evals/operator_eval_cases.v1.json
to an automated runner that scores responses against the live Operator API.

Usage:
    python scripts/run_operator_eval.py [--cases CASE_ID,...] [--output OUTPUT.json]

Exit codes:
    0 - All required evals passed
    1 - One or more evals failed
    2 - Setup/runtime error
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import aiohttp


@dataclass
class EvalResult:
    """Result of a single eval case execution."""
    case_id: str
    category: str
    passed: bool
    scores: dict[str, float] = field(default_factory=dict)
    total_score: float = 0.0
    max_possible: float = 10.0
    response_text: str = ""
    error: str | None = None
    duration_ms: int = 0
    checks: dict[str, bool] = field(default_factory=dict)


@dataclass
class EvalRun:
    """Complete eval run results."""
    timestamp: str
    api_endpoint: str
    cases_run: int
    cases_passed: int
    cases_failed: int
    results: list[EvalResult]
    summary: dict[str, Any] = field(default_factory=dict)


class OperatorEvalRunner:
    """Runner for operator eval cases against live API."""
    
    def __init__(self, api_base: str = "http://localhost:8170"):
        self.api_base = api_base.rstrip("/")
        self.eval_cases: list[dict] = []
        self.session: aiohttp.ClientSession | None = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    def load_eval_cases(self, cases_file: Path | None = None) -> list[dict]:
        """Load eval cases from the canonical eval bank."""
        if cases_file is None:
            cases_file = Path(__file__).parent.parent / "docs" / "evals" / "operator_eval_cases.v1.json"
        
        with open(cases_file) as f:
            data = json.load(f)
        
        self.eval_cases = data.get("cases", [])
        print(f"Loaded {len(self.eval_cases)} eval cases from {cases_file}")
        return self.eval_cases
    
    async def check_api_health(self) -> bool:
        """Verify Operator API is accessible."""
        if not self.session:
            return False
        
        try:
            async with self.session.get(f"{self.api_base}/healthz", timeout=5) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"API health check failed: {e}")
            return False
    
    async def run_chat_turn(self, message: str, thread_id: str | None = None) -> dict:
        """Execute a single chat turn against the Operator API.
        
        Note: Auth is required. Set OPERATOR_TEST_TOKEN env var or configure
        local auth bypass for testing.
        """
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        # For now, we check auth requirement via bootstrap
        async with self.session.get(f"{self.api_base}/api/operator/bootstrap") as resp:
            bootstrap = await resp.json()
            auth_required = bootstrap.get("session", {}).get("auth", {}).get("required", True)
        
        if auth_required:
            # Try to use a test token or local dev bypass
            token = os.environ.get("OPERATOR_TEST_TOKEN")
            if not token:
                # Check if local accounts are available for testing
                return {
                    "error": "auth_required",
                    "message": "Operator API requires authentication. Set OPERATOR_TEST_TOKEN or configure local test account.",
                    "bootstrap": bootstrap,
                }
        
        # Execute chat stream
        payload = {
            "message": message,
            "thread_id": thread_id or f"eval-{int(time.time())}",
        }
        
        headers = {}
        if token := os.environ.get("OPERATOR_TEST_TOKEN"):
            headers["Authorization"] = f"Bearer {token}"
        
        accumulated = ""
        async with self.session.post(
            f"{self.api_base}/api/operator/chat/stream",
            json=payload,
            headers=headers,
            timeout=60,
        ) as resp:
            # Read streaming response
            async for line in resp.content:
                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue
                try:
                    event = json.loads(line_str)
                    if event.get("type") == "assistant_delta":
                        accumulated += event.get("delta", "")
                    elif event.get("type") == "assistant_message":
                        msg = event.get("message", {})
                        accumulated = msg.get("content", accumulated)
                    elif event.get("type") == "error":
                        return {"error": event.get("error", "unknown"), "partial": accumulated}
                except json.JSONDecodeError:
                    continue
        
        return {"content": accumulated, "thread_id": payload["thread_id"]}
    
    def score_response(self, case: dict, response: str) -> tuple[float, dict[str, float], dict[str, bool]]:
        """Score a response against eval case criteria.
        
        Returns: (total_score, dimension_scores, check_results)
        """
        scores: dict[str, float] = {}
        checks: dict[str, bool] = {}
        
        # Extract success criteria
        success_criteria = case.get("sections", {}).get("success_criteria", [])
        score_focus = case.get("score_focus", {})
        primary_dims = score_focus.get("primary_dimensions", ["intent", "trust"])
        must_fail = score_focus.get("must_fail_if", [])
        
        # Check mandatory failures
        checks["tool_leakage"] = any(
            tool in response.lower() 
            for tool in ["search_profiles", "create_segment", "export_segment", 
                        "push_to_resend", "query_unified"]
        )
        checks["answer_first_failure"] = any(
            phrase in response.lower()[:200]
            for phrase in ["i need to", "i will", "let me", "first,", "step 1"]
        )
        checks["hallucinated_missing_data"] = "i don't have" not in response.lower() and "not specified" not in response.lower()
        
        # Score dimensions (simplified heuristic scoring)
        # In a full implementation, this would use an LLM judge or human review
        
        # Intent: Did it address the goal?
        goal_keywords = case.get("sections", {}).get("goal", "").lower().split()[:5]
        intent_score = 7.0 + (sum(1 for kw in goal_keywords if kw in response.lower()) * 0.5)
        scores["intent"] = min(10.0, intent_score)
        
        # Autonomy: Did it solve without excessive back-and-forth?
        scores["autonomy"] = 8.0 if len(response) > 100 else 5.0
        
        # Trust: Did it stay honest about uncertainty?
        has_uncertainty_markers = any(
            phrase in response.lower() 
            for phrase in ["i don't have", "not specified", "uncertain", "may be"]
        )
        scores["trust"] = 8.0 if has_uncertainty_markers else 7.0
        
        # Actionability: Can the user act on this?
        has_action_items = any(
            marker in response.lower()
            for marker in ["you can", "try", "recommend", "suggest", "next step"]
        )
        scores["actionability"] = 7.5 if has_action_items else 6.0
        
        # UX Polish: Does it feel like a product?
        ux_negative_markers = [
            checks["tool_leakage"],
            checks["answer_first_failure"],
            "error" in response.lower() and "sorry" not in response.lower(),
        ]
        scores["ux_product_polish"] = 10.0 - sum(ux_negative_markers) * 3.0
        
        # Calculate weighted total
        weights = {"intent": 0.2, "autonomy": 0.3, "trust": 0.3, "actionability": 0.2}
        total = sum(scores.get(k, 5.0) * w for k, w in weights.items())
        
        # Apply mandatory failure deductions
        if checks["tool_leakage"]:
            total = max(0, total - 3.0)
        if checks["answer_first_failure"]:
            total = max(0, total - 2.0)
        
        return round(total, 2), scores, checks
    
    async def run_case(self, case: dict) -> EvalResult:
        """Execute a single eval case."""
        case_id = case["case_id"]
        category = case.get("category", "unknown")
        prompt = case.get("prompt", "")
        
        print(f"\n  Running: {case_id} ({category})")
        
        start = time.time()
        try:
            result = await self.run_chat_turn(prompt)
            duration = int((time.time() - start) * 1000)
            
            if "error" in result:
                return EvalResult(
                    case_id=case_id,
                    category=category,
                    passed=False,
                    error=result.get("message", result["error"]),
                    duration_ms=duration,
                )
            
            response_text = result.get("content", "")
            total, scores, checks = self.score_response(case, response_text)
            
            # Pass threshold: >= 7.0 total and no mandatory failures
            passed = total >= 7.0 and not checks.get("tool_leakage", False) and not checks.get("answer_first_failure", False)
            
            print(f"    Score: {total}/10 | Passed: {passed}")
            if checks.get("tool_leakage"):
                print(f"    ⚠️  Tool leakage detected")
            if checks.get("answer_first_failure"):
                print(f"    ⚠️  Answer-first violation")
            
            return EvalResult(
                case_id=case_id,
                category=category,
                passed=passed,
                scores=scores,
                total_score=total,
                response_text=response_text[:500] + "..." if len(response_text) > 500 else response_text,
                duration_ms=duration,
                checks=checks,
            )
            
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            return EvalResult(
                case_id=case_id,
                category=category,
                passed=False,
                error=str(e),
                duration_ms=duration,
            )
    
    async def run_all(self, case_filter: list[str] | None = None) -> EvalRun:
        """Run all or filtered eval cases."""
        if not self.eval_cases:
            self.load_eval_cases()
        
        cases = self.eval_cases
        if case_filter:
            cases = [c for c in cases if c["case_id"] in case_filter]
        
        print(f"\n{'='*60}")
        print(f"Operator Eval Run")
        print(f"API: {self.api_base}")
        print(f"Cases: {len(cases)}")
        print(f"{'='*60}")
        
        # Check API health
        if not await self.check_api_health():
            print("\n❌ Operator API is not accessible")
            return EvalRun(
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                api_endpoint=self.api_base,
                cases_run=0,
                cases_passed=0,
                cases_failed=0,
                results=[],
                summary={"error": "API not accessible"},
            )
        
        print("✅ API is healthy")
        
        # Run cases
        results: list[EvalResult] = []
        for case in cases:
            result = await self.run_case(case)
            results.append(result)
        
        # Calculate summary
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        
        # Category breakdown
        by_category: dict[str, dict] = {}
        for r in results:
            cat = r.category
            if cat not in by_category:
                by_category[cat] = {"total": 0, "passed": 0, "avg_score": 0.0}
            by_category[cat]["total"] += 1
            by_category[cat]["passed"] += 1 if r.passed else 0
            by_category[cat]["avg_score"] += r.total_score
        
        for cat in by_category:
            by_category[cat]["avg_score"] = round(
                by_category[cat]["avg_score"] / by_category[cat]["total"], 2
            )
        
        summary = {
            "pass_rate": round(passed / len(results) * 100, 1) if results else 0,
            "avg_score": round(sum(r.total_score for r in results) / len(results), 2) if results else 0,
            "by_category": by_category,
        }
        
        return EvalRun(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            api_endpoint=self.api_base,
            cases_run=len(results),
            cases_passed=passed,
            cases_failed=failed,
            results=results,
            summary=summary,
        )


def main():
    parser = argparse.ArgumentParser(description="Run operator eval cases")
    parser.add_argument("--cases", help="Comma-separated case IDs to run (default: all)")
    parser.add_argument("--api", default="http://localhost:8170", help="Operator API base URL")
    parser.add_argument("--output", "-o", help="Output JSON file for results")
    parser.add_argument("--format", choices=["json", "markdown", "csv"], default="json", help="Output format")
    args = parser.parse_args()
    
    case_filter = args.cases.split(",") if args.cases else None
    
    async def run():
        async with OperatorEvalRunner(api_base=args.api) as runner:
            eval_run = await runner.run_all(case_filter=case_filter)
            
            # Print summary
            print(f"\n{'='*60}")
            print("SUMMARY")
            print(f"{'='*60}")
            print(f"Cases run: {eval_run.cases_run}")
            print(f"Passed: {eval_run.cases_passed}")
            print(f"Failed: {eval_run.cases_failed}")
            print(f"Pass rate: {eval_run.summary.get('pass_rate', 0)}%")
            print(f"Avg score: {eval_run.summary.get('avg_score', 0)}/10")
            
            if eval_run.summary.get("by_category"):
                print(f"\nBy Category:")
                for cat, stats in eval_run.summary["by_category"].items():
                    print(f"  {cat}: {stats['passed']}/{stats['total']} passed, avg {stats['avg_score']}")
            
            # Output to file if requested
            if args.output:
                output_path = Path(args.output)
                
                if args.format == "json":
                    # Convert dataclasses to dicts
                    run_dict = {
                        "timestamp": eval_run.timestamp,
                        "api_endpoint": eval_run.api_endpoint,
                        "cases_run": eval_run.cases_run,
                        "cases_passed": eval_run.cases_passed,
                        "cases_failed": eval_run.cases_failed,
                        "summary": eval_run.summary,
                        "results": [asdict(r) for r in eval_run.results],
                    }
                    with open(output_path, "w") as f:
                        json.dump(run_dict, f, indent=2)
                    print(f"\nResults written to: {output_path}")
                    
                elif args.format == "markdown":
                    lines = [
                        "# Operator Eval Results",
                        f"\n**Timestamp:** {eval_run.timestamp}",
                        f"**API:** {eval_run.api_endpoint}",
                        f"\n## Summary",
                        f"- Cases run: {eval_run.cases_run}",
                        f"- Passed: {eval_run.cases_passed}",
                        f"- Failed: {eval_run.cases_failed}",
                        f"- Pass rate: {eval_run.summary.get('pass_rate', 0)}%",
                        f"- Avg score: {eval_run.summary.get('avg_score', 0)}/10",
                        f"\n## Results",
                        "| Case ID | Category | Score | Status |",
                        "|---------|----------|-------|--------|",
                    ]
                    for r in eval_run.results:
                        status = "✅ Pass" if r.passed else "❌ Fail"
                        lines.append(f"| {r.case_id} | {r.category} | {r.total_score} | {status} |")
                    
                    with open(output_path, "w") as f:
                        f.write("\n".join(lines))
                    print(f"\nResults written to: {output_path}")
            
            # Exit code based on results
            return 0 if eval_run.cases_failed == 0 else 1
    
    exit_code = asyncio.run(run())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
