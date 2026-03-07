"""CI-safe eval harness tests for retrieval + grounding quality gates."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from tests.integration.helpers.assertions import (
    assert_answer_contains_citation_markers,
    assert_citation_coverage,
    assert_low_confidence_fallback_behavior,
    assert_protocol_invariants,
    assert_retrieval_backend_metadata_present,
    assert_shadow_metadata_consistent,
    extract_tool_json_payloads,
)
from tests.integration.helpers.conversation_driver import ConversationDriver, TurnSpec

pytestmark = pytest.mark.integration


@tool
async def search_profiles(
    user_query: str,
    language: str,
    gate_primary_azure: bool = False,
    gate_shadow_azure: bool = False,
    gate_citation_required: bool = False,
) -> str:
    """Deterministic retrieval fixture that mirrors retrieval/citation gate behavior."""
    query_lower = user_query.lower()

    if "low confidence" in query_lower or "insufficient context" in query_lower:
        payload = {
            "status": "ok",
            "tool_contract": "search_profiles.v2",
            "retrieval_backend": "tracardi_tql",
            "search_strategy": "name_lexical_fallback",
            "used_keyword_fallback": True,
            "resolved_nace_codes": [],
            "counts": {
                "authoritative_total": 3,
                "returned_samples": 2,
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    if gate_primary_azure:
        citations = (
            [] if "no citations" in query_lower else [{"id": f"{language}-doc-1", "title": "KB"}]
        )
        if gate_citation_required and not citations:
            return json.dumps(
                {
                    "status": "error",
                    "tool_contract": "search_profiles.v2",
                    "error": "Citation-required mode is enabled but no citations were produced.",
                    "flags": ["missing_citations"],
                    "release_gates": {
                        "enable_azure_search_retrieval": gate_primary_azure,
                        "enable_azure_search_shadow_mode": gate_shadow_azure,
                        "enable_citation_required": gate_citation_required,
                    },
                },
                ensure_ascii=False,
            )

        payload = {
            "status": "ok",
            "tool_contract": "search_profiles.v2",
            "retrieval_backend": "azure_ai_search",
            "counts": {
                "authoritative_total": 11,
                "returned_samples": 2,
            },
            "citations": citations,
            "release_gates": {
                "enable_azure_search_retrieval": gate_primary_azure,
                "enable_azure_search_shadow_mode": gate_shadow_azure,
                "enable_citation_required": gate_citation_required,
                "lang": language,
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    payload = {
        "status": "ok",
        "tool_contract": "search_profiles.v2",
        "retrieval_backend": "tracardi_tql",
        "counts": {
            "authoritative_total": 9,
            "returned_samples": 2,
        },
        "release_gates": {
            "enable_azure_search_retrieval": gate_primary_azure,
            "enable_azure_search_shadow_mode": gate_shadow_azure,
            "enable_citation_required": gate_citation_required,
            "lang": language,
        },
    }

    if gate_shadow_azure:
        payload["shadow_retrieval"] = {
            "enabled": True,
            "backend": "azure_ai_search",
            "counts": {
                "authoritative_total": 10,
                "returned_samples": 2,
            },
            "citations": [{"id": "shadow-doc-1", "title": "Shadow"}],
        }

    return json.dumps(payload, ensure_ascii=False)


class RetrievalGroundingEvalModel:
    """Deterministic model that emits retrieval tool calls and citation-aware responses."""

    async def ainvoke(self, messages: list[BaseMessage]) -> AIMessage:
        last = messages[-1]

        if isinstance(last, ToolMessage) and last.name == "search_profiles":
            payload = json.loads(str(last.content))
            language = payload.get("release_gates", {}).get("lang", None)

            if payload.get("status") == "error":
                return AIMessage(content="Grounded output unavailable: missing citations.")

            backend = payload.get("retrieval_backend")
            citations = payload.get("citations") or []

            if backend == "azure_ai_search" and citations:
                return AIMessage(content="Grounded response [1]. Source: KB")

            if language == "fr":
                return AIMessage(content="Réponse sans citation pour ce tour.")
            if language == "nl":
                return AIMessage(content="Antwoord zonder bron voor deze beurt.")
            return AIMessage(content="Ungrounded response for this turn.")

        if isinstance(last, HumanMessage):
            text = str(last.content)
            text_lower = text.lower()
            language = "fr" if "bonjour" in text_lower else "nl" if "hallo" in text_lower else "en"

            gate_primary_azure = "azure primary" in text_lower
            gate_shadow_azure = "shadow" in text_lower
            gate_citation_required = "citation required" in text_lower

            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_profiles",
                        "args": {
                            "user_query": text,
                            "language": language,
                            "gate_primary_azure": gate_primary_azure,
                            "gate_shadow_azure": gate_shadow_azure,
                            "gate_citation_required": gate_citation_required,
                        },
                        "id": f"eval-{len(messages)}",
                        "type": "tool_call",
                    }
                ],
            )

        return AIMessage(content="No-op")


def _eval_driver(*, thread_id: str) -> ConversationDriver:
    return ConversationDriver(
        thread_id=thread_id,
        agent_model=RetrievalGroundingEvalModel(),
        bound_tools=[search_profiles],
    )


@dataclass(frozen=True)
class EvalTurnExpectation:
    expected_status: str = "ok"
    expected_backend: str | None = None
    citation_required: bool = False
    expect_fallback: bool = False


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    category: str
    turns: list[TurnSpec]
    expectations: list[EvalTurnExpectation]


def _has_citation_markers(answer: str | None) -> bool:
    text = str(answer or "")
    return "[1]" in text or "source:" in text.lower()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    rank = int(round((percentile / 100.0) * (len(sorted_values) - 1)))
    rank = max(0, min(rank, len(sorted_values) - 1))
    return float(sorted_values[rank])


def evaluate_gate_thresholds(
    *,
    correctness_rate: float,
    groundedness_citation_compliance_rate: float,
    failure_rate: float,
    p95_latency_ms: float,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    gate_results = {
        "correctness_rate": correctness_rate >= thresholds["min_correctness_rate"],
        "groundedness_citation_compliance_rate": (
            groundedness_citation_compliance_rate
            >= thresholds["min_groundedness_citation_compliance_rate"]
        ),
        "failure_rate": failure_rate <= thresholds["max_failure_rate"],
        "latency_p95_ms": p95_latency_ms <= thresholds["max_latency_p95_ms"],
    }
    return {
        "thresholds": thresholds,
        "results": gate_results,
        "passed": all(gate_results.values()),
    }


def validate_eval_summary_artifact_schema(payload: dict[str, Any]) -> None:
    assert payload.get("schema_version") == "eval_summary.v1"
    assert isinstance(payload.get("generated_at"), str)
    totals = payload.get("totals")
    assert isinstance(totals, dict)
    assert isinstance(totals.get("cases"), int)
    assert isinstance(totals.get("prompts"), int)

    metrics = payload.get("metrics")
    assert isinstance(metrics, dict)
    assert isinstance(metrics.get("correctness_rate"), float)
    assert isinstance(metrics.get("groundedness_citation_compliance_rate"), float)
    assert isinstance(metrics.get("failure_rate"), float)
    latency = metrics.get("latency_ms")
    assert isinstance(latency, dict)
    assert isinstance(latency.get("p50"), float)
    assert isinstance(latency.get("p95"), float)
    assert isinstance(latency.get("mean"), float)

    gates = payload.get("gates")
    assert isinstance(gates, dict)
    assert isinstance(gates.get("thresholds"), dict)
    assert isinstance(gates.get("results"), dict)
    assert isinstance(gates.get("passed"), bool)

    categories = payload.get("categories")
    assert isinstance(categories, dict)
    for category_payload in categories.values():
        assert isinstance(category_payload, dict)
        assert isinstance(category_payload.get("prompts"), int)
        assert isinstance(category_payload.get("correct_prompts"), int)
        assert isinstance(category_payload.get("failed_prompts"), int)

    case_results = payload.get("case_results")
    assert isinstance(case_results, list)
    assert case_results, "Expected non-empty case_results list"


def build_eval_cases() -> list[EvalCase]:
    return [
        EvalCase(
            case_id="lookup-en-azure",
            category="lookup",
            turns=[
                TurnSpec(user_text="Azure primary citation required: find IT companies in Gent.")
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="ok",
                    expected_backend="azure_ai_search",
                    citation_required=True,
                )
            ],
        ),
        EvalCase(
            case_id="lookup-fr-azure",
            category="lookup",
            turns=[
                TurnSpec(
                    user_text="Bonjour, Azure primary citation required pour trouver des entreprises IT à Gent."
                )
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="ok",
                    expected_backend="azure_ai_search",
                    citation_required=True,
                )
            ],
        ),
        EvalCase(
            case_id="lookup-nl-azure",
            category="lookup",
            turns=[
                TurnSpec(
                    user_text="Hallo, Azure primary citation required om IT bedrijven in Gent te zoeken."
                )
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="ok",
                    expected_backend="azure_ai_search",
                    citation_required=True,
                )
            ],
        ),
        EvalCase(
            case_id="lookup-shadow-parity",
            category="lookup",
            turns=[
                TurnSpec(user_text="Run lookup in shadow mode for active companies in Brussels.")
            ],
            expectations=[
                EvalTurnExpectation(expected_status="ok", expected_backend="tracardi_tql")
            ],
        ),
        EvalCase(
            case_id="lookup-tracardi-default",
            category="lookup",
            turns=[TurnSpec(user_text="Find active companies in Antwerp without Azure primary.")],
            expectations=[
                EvalTurnExpectation(expected_status="ok", expected_backend="tracardi_tql")
            ],
        ),
        EvalCase(
            case_id="lookup-retail-bruges",
            category="lookup",
            turns=[
                TurnSpec(
                    user_text="Search for retail companies in Bruges with normal retrieval behavior."
                )
            ],
            expectations=[
                EvalTurnExpectation(expected_status="ok", expected_backend="tracardi_tql")
            ],
        ),
        EvalCase(
            case_id="ambiguity-low-confidence-en",
            category="ambiguity",
            turns=[
                TurnSpec(
                    user_text="Low confidence: insufficient context for company type in Leuven, continue retrieval."
                )
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="ok",
                    expected_backend="tracardi_tql",
                    expect_fallback=True,
                )
            ],
        ),
        EvalCase(
            case_id="ambiguity-low-confidence-fr",
            category="ambiguity",
            turns=[
                TurnSpec(
                    user_text=(
                        "Bonjour, low confidence: insufficient context sur le secteur, continue retrieval."
                    )
                )
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="ok",
                    expected_backend="tracardi_tql",
                    expect_fallback=True,
                )
            ],
        ),
        EvalCase(
            case_id="ambiguity-low-confidence-nl",
            category="ambiguity",
            turns=[
                TurnSpec(
                    user_text=(
                        "Hallo, low confidence: insufficient context voor dit verzoek, continue retrieval."
                    )
                )
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="ok",
                    expected_backend="tracardi_tql",
                    expect_fallback=True,
                )
            ],
        ),
        EvalCase(
            case_id="ambiguity-shadow-plus-fallback",
            category="ambiguity",
            turns=[
                TurnSpec(
                    user_text=(
                        "Shadow mode with low confidence: insufficient context, continue retrieval with fallback."
                    )
                )
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="ok",
                    expected_backend="tracardi_tql",
                    expect_fallback=True,
                )
            ],
        ),
        EvalCase(
            case_id="ambiguity-broader-request",
            category="ambiguity",
            turns=[
                TurnSpec(
                    user_text="Request is vague: just show possibly relevant firms near Ghent without azure primary."
                )
            ],
            expectations=[
                EvalTurnExpectation(expected_status="ok", expected_backend="tracardi_tql")
            ],
        ),
        EvalCase(
            case_id="failure-citation-required-missing-en",
            category="failure",
            turns=[
                TurnSpec(
                    user_text=(
                        "Azure primary citation required with no citations for this lookup should fail."
                    )
                )
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="error",
                    expected_backend=None,
                    citation_required=True,
                )
            ],
        ),
        EvalCase(
            case_id="failure-citation-required-missing-fr",
            category="failure",
            turns=[
                TurnSpec(
                    user_text=(
                        "Bonjour, Azure primary citation required et no citations pour ce tour."
                    )
                )
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="error",
                    expected_backend=None,
                    citation_required=True,
                )
            ],
        ),
        EvalCase(
            case_id="failure-citation-required-missing-nl",
            category="failure",
            turns=[
                TurnSpec(
                    user_text=(
                        "Hallo, Azure primary citation required met no citations moet falen."
                    )
                )
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="error",
                    expected_backend=None,
                    citation_required=True,
                )
            ],
        ),
        EvalCase(
            case_id="failure-citation-required-shadow-context",
            category="failure",
            turns=[
                TurnSpec(
                    user_text=(
                        "Shadow mode and Azure primary citation required with no citations must fail hard."
                    )
                )
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="error",
                    expected_backend=None,
                    citation_required=True,
                )
            ],
        ),
        EvalCase(
            case_id="failure-no-citation-flag-omitted",
            category="failure",
            turns=[
                TurnSpec(
                    user_text=(
                        "Azure primary with no citations but without citation required flag should remain ok."
                    )
                )
            ],
            expectations=[
                EvalTurnExpectation(expected_status="ok", expected_backend="azure_ai_search")
            ],
        ),
        EvalCase(
            case_id="continuity-two-turn-citation",
            category="multi_turn_intent_continuity",
            turns=[
                TurnSpec(
                    user_text="Azure primary citation required: find biotech companies in Gent."
                ),
                TurnSpec(
                    user_text="Follow-up: keep same request and include only active companies."
                ),
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="ok",
                    expected_backend="azure_ai_search",
                    citation_required=True,
                ),
                EvalTurnExpectation(expected_status="ok", expected_backend="tracardi_tql"),
            ],
        ),
        EvalCase(
            case_id="continuity-two-turn-shadow",
            category="multi_turn_intent_continuity",
            turns=[
                TurnSpec(
                    user_text="Run shadow parity retrieval for logistics profiles in Brussels."
                ),
                TurnSpec(user_text="Follow-up: same intent, narrow to active only."),
            ],
            expectations=[
                EvalTurnExpectation(expected_status="ok", expected_backend="tracardi_tql"),
                EvalTurnExpectation(expected_status="ok", expected_backend="tracardi_tql"),
            ],
        ),
        EvalCase(
            case_id="continuity-three-turn-mixed-language",
            category="multi_turn_intent_continuity",
            turns=[
                TurnSpec(
                    user_text="Find companies in Antwerp with Azure primary citation required."
                ),
                TurnSpec(user_text="Bonjour, follow-up: garde la même intention pour ce thread."),
                TurnSpec(
                    user_text="Hallo, follow-up: behoud dezelfde intentie en beperk tot actief."
                ),
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="ok",
                    expected_backend="azure_ai_search",
                    citation_required=True,
                ),
                EvalTurnExpectation(expected_status="ok", expected_backend="tracardi_tql"),
                EvalTurnExpectation(expected_status="ok", expected_backend="tracardi_tql"),
            ],
        ),
        EvalCase(
            case_id="continuity-recovery-after-failure",
            category="multi_turn_intent_continuity",
            turns=[
                TurnSpec(
                    user_text=(
                        "Azure primary citation required with no citations should fail this turn for continuity test."
                    )
                ),
                TurnSpec(
                    user_text="Follow-up: retry with Azure primary citation required and include citations."
                ),
            ],
            expectations=[
                EvalTurnExpectation(expected_status="error", citation_required=True),
                EvalTurnExpectation(
                    expected_status="ok",
                    expected_backend="azure_ai_search",
                    citation_required=True,
                ),
            ],
        ),
        EvalCase(
            case_id="continuity-low-confidence-then-concrete",
            category="multi_turn_intent_continuity",
            turns=[
                TurnSpec(
                    user_text="Low confidence: insufficient context for this lookup, continue retrieval."
                ),
                TurnSpec(
                    user_text="Follow-up: Azure primary citation required for concrete IT company lookup."
                ),
            ],
            expectations=[
                EvalTurnExpectation(
                    expected_status="ok",
                    expected_backend="tracardi_tql",
                    expect_fallback=True,
                ),
                EvalTurnExpectation(
                    expected_status="ok",
                    expected_backend="azure_ai_search",
                    citation_required=True,
                ),
            ],
        ),
    ]


def _default_thresholds() -> dict[str, float]:
    return {
        "min_correctness_rate": float(os.getenv("EVAL_MIN_CORRECTNESS_RATE", "0.85")),
        "min_groundedness_citation_compliance_rate": float(
            os.getenv("EVAL_MIN_GROUNDEDNESS_RATE", "0.90")
        ),
        "max_failure_rate": float(os.getenv("EVAL_MAX_FAILURE_RATE", "0.20")),
        "max_latency_p95_ms": float(os.getenv("EVAL_MAX_P95_LATENCY_MS", "2500")),
    }


async def run_eval_suite(
    *,
    artifact_path: str,
    thresholds: dict[str, float] | None = None,
    selected_categories: set[str] | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or _default_thresholds()
    all_cases = build_eval_cases()
    cases = [
        case
        for case in all_cases
        if not selected_categories or case.category in selected_categories
    ]

    correctness_total = 0
    citation_required_total = 0
    citation_required_compliant = 0
    failure_total = 0
    error_response_total = 0
    prompt_total = 0
    latency_values_ms: list[float] = []
    case_results: list[dict[str, Any]] = []
    category_rollup: dict[str, dict[str, int]] = {}

    for case in cases:
        driver = _eval_driver(thread_id=f"eval-suite-{case.case_id}")
        turn_results: list[dict[str, Any]] = []

        for spec, expectation in zip(case.turns, case.expectations, strict=True):
            prompt_total += 1
            start = perf_counter()
            result = await driver.run_turn(spec)
            latency_ms = (perf_counter() - start) * 1000.0
            latency_values_ms.append(latency_ms)

            payloads = extract_tool_json_payloads(
                result,
                tool_name="search_profiles",
                include_error_status=True,
            )
            primary_payload = payloads[0] if payloads else {}
            actual_status = str(primary_payload.get("status", "error"))
            actual_backend = primary_payload.get("retrieval_backend")
            citations = primary_payload.get("citations") or []

            turn_correct = actual_status == expectation.expected_status
            if expectation.expected_backend is not None:
                turn_correct = turn_correct and actual_backend == expectation.expected_backend
            if expectation.expect_fallback:
                turn_correct = turn_correct and bool(primary_payload.get("used_keyword_fallback"))
            if expectation.citation_required and expectation.expected_status == "ok":
                turn_correct = (
                    turn_correct and bool(citations) and _has_citation_markers(result.final_answer)
                )

            correctness_total += int(turn_correct)
            error_response_total += int(actual_status == "error")
            failure_total += int(
                actual_status == "error" and expectation.expected_status != "error"
            )

            if expectation.citation_required:
                citation_required_total += 1
                citation_ok = bool(citations) and _has_citation_markers(result.final_answer)
                citation_required_compliant += int(citation_ok)
            else:
                citation_ok = None

            category_bucket = category_rollup.setdefault(
                case.category,
                {"prompts": 0, "correct_prompts": 0, "failed_prompts": 0},
            )
            category_bucket["prompts"] += 1
            category_bucket["correct_prompts"] += int(turn_correct)
            category_bucket["failed_prompts"] += int(actual_status == "error")

            turn_results.append(
                {
                    "turn_index": result.turn_index,
                    "prompt": spec.user_text,
                    "latency_ms": round(latency_ms, 3),
                    "expected": {
                        "status": expectation.expected_status,
                        "backend": expectation.expected_backend,
                        "citation_required": expectation.citation_required,
                        "expect_fallback": expectation.expect_fallback,
                    },
                    "actual": {
                        "status": actual_status,
                        "backend": actual_backend,
                        "citations": len(citations),
                        "has_citation_markers": _has_citation_markers(result.final_answer),
                        "used_keyword_fallback": bool(
                            primary_payload.get("used_keyword_fallback")
                        ),
                    },
                    "correct": turn_correct,
                    "citation_compliant": citation_ok,
                }
            )

        case_results.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "prompt_count": len(case.turns),
                "turn_results": turn_results,
            }
        )

    correctness_rate = float(correctness_total) / float(prompt_total) if prompt_total else 0.0
    groundedness_rate = (
        float(citation_required_compliant) / float(citation_required_total)
        if citation_required_total
        else 1.0
    )
    failure_rate = float(failure_total) / float(prompt_total) if prompt_total else 0.0
    error_response_rate = (
        float(error_response_total) / float(prompt_total) if prompt_total else 0.0
    )

    latency_summary = {
        "p50": float(round(_percentile(latency_values_ms, 50), 3)),
        "p95": float(round(_percentile(latency_values_ms, 95), 3)),
        "mean": float(round(sum(latency_values_ms) / len(latency_values_ms), 3))
        if latency_values_ms
        else 0.0,
    }

    gates = evaluate_gate_thresholds(
        correctness_rate=correctness_rate,
        groundedness_citation_compliance_rate=groundedness_rate,
        failure_rate=failure_rate,
        p95_latency_ms=latency_summary["p95"],
        thresholds=thresholds,
    )

    artifact = {
        "schema_version": "eval_summary.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "totals": {
            "cases": len(cases),
            "prompts": prompt_total,
            "citation_required_prompts": citation_required_total,
        },
        "metrics": {
            "correctness_rate": float(round(correctness_rate, 4)),
            "groundedness_citation_compliance_rate": float(round(groundedness_rate, 4)),
            "failure_rate": float(round(failure_rate, 4)),
            "error_response_rate": float(round(error_response_rate, 4)),
            "latency_ms": latency_summary,
        },
        "gates": gates,
        "categories": category_rollup,
        "case_results": case_results,
    }
    validate_eval_summary_artifact_schema(artifact)

    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    return artifact


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic retrieval/grounding eval suite"
    )
    parser.add_argument(
        "--artifact",
        default="tests/integration/snapshots/eval_suite/eval_summary.json",
        help="Path to JSON artifact output.",
    )
    parser.add_argument(
        "--category",
        action="append",
        choices=["lookup", "ambiguity", "failure", "multi_turn_intent_continuity"],
        help="Optional category filter. Can be passed multiple times.",
    )
    parser.add_argument("--min-correctness-rate", type=float, default=None)
    parser.add_argument("--min-groundedness-rate", type=float, default=None)
    parser.add_argument("--max-failure-rate", type=float, default=None)
    parser.add_argument("--max-p95-latency-ms", type=float, default=None)
    return parser.parse_args()


def _cli_thresholds(args: argparse.Namespace) -> dict[str, float]:
    thresholds = _default_thresholds()
    if args.min_correctness_rate is not None:
        thresholds["min_correctness_rate"] = args.min_correctness_rate
    if args.min_groundedness_rate is not None:
        thresholds["min_groundedness_citation_compliance_rate"] = args.min_groundedness_rate
    if args.max_failure_rate is not None:
        thresholds["max_failure_rate"] = args.max_failure_rate
    if args.max_p95_latency_ms is not None:
        thresholds["max_latency_p95_ms"] = args.max_p95_latency_ms
    return thresholds


def main() -> int:
    args = _parse_args()
    thresholds = _cli_thresholds(args)
    categories = set(args.category or [])
    artifact = asyncio.run(
        run_eval_suite(
            artifact_path=args.artifact,
            thresholds=thresholds,
            selected_categories=categories or None,
        )
    )
    print(json.dumps({"artifact": args.artifact, "gates": artifact["gates"]}, ensure_ascii=False))
    return 0 if artifact["gates"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


class TestRetrievalGroundingEvalHarness:
    @pytest.mark.asyncio
    async def test_multilingual_citation_coverage_for_azure_primary(self):
        driver = _eval_driver(thread_id="eval-multilingual-citations")
        specs = [
            TurnSpec(user_text="EN: Azure primary citation required for this retrieval turn."),
            TurnSpec(user_text="Bonjour, Azure primary citation required pour ce tour."),
            TurnSpec(user_text="Hallo, Azure primary citation required voor deze beurt."),
        ]

        results = await driver.run_conversation(specs)

        for result in results:
            assert_protocol_invariants(result, expect_tools=True)
            assert_retrieval_backend_metadata_present(result, expected_backend="azure_ai_search")
            assert_answer_contains_citation_markers(result)

        assert_citation_coverage(results, min_ratio=1.0)

    @pytest.mark.asyncio
    async def test_shadow_mode_parity_metadata_present_and_consistent(self):
        driver = _eval_driver(thread_id="eval-shadow-parity")
        result = (
            await driver.run_conversation(
                [TurnSpec(user_text="Run shadow parity check with shadow mode enabled.")]
            )
        )[0]

        assert_protocol_invariants(result, expect_tools=True)
        assert_retrieval_backend_metadata_present(result, expected_backend="tracardi_tql")
        assert_shadow_metadata_consistent(result)

    @pytest.mark.asyncio
    async def test_low_confidence_path_uses_lexical_fallback_metadata(self):
        driver = _eval_driver(thread_id="eval-low-confidence")
        result = (
            await driver.run_conversation(
                [
                    TurnSpec(
                        user_text="Low confidence: insufficient context, please continue retrieval."
                    )
                ]
            )
        )[0]

        assert_protocol_invariants(result, expect_tools=True)
        assert_retrieval_backend_metadata_present(result, expected_backend="tracardi_tql")
        assert_low_confidence_fallback_behavior(result)

    @pytest.mark.asyncio
    async def test_citation_required_gate_blocks_azure_without_citations(self):
        driver = _eval_driver(thread_id="eval-citation-required-gate")
        result = (
            await driver.run_conversation(
                [
                    TurnSpec(
                        user_text=(
                            "Azure primary citation required with no citations should fail this turn."
                        )
                    )
                ]
            )
        )[0]

        assert_protocol_invariants(result, expect_tools=True)
        tool_payloads = extract_tool_json_payloads(result, tool_name="search_profiles")

        assert tool_payloads, "Expected eval harness to emit at least one search_profiles payload."
        assert tool_payloads[0].get("status") == "error"
        assert "missing_citations" in (tool_payloads[0].get("flags") or [])

    @pytest.mark.asyncio
    async def test_eval_suite_generates_machine_readable_summary_artifact(self, tmp_path: Path):
        artifact_path = tmp_path / "eval_summary.json"
        artifact = await run_eval_suite(artifact_path=str(artifact_path))

        assert artifact_path.exists()
        assert artifact["schema_version"] == "eval_summary.v1"
        assert artifact["totals"]["prompts"] >= 20
        assert "lookup" in artifact["categories"]
        assert "ambiguity" in artifact["categories"]
        assert "failure" in artifact["categories"]
        assert "multi_turn_intent_continuity" in artifact["categories"]

    @pytest.mark.asyncio
    async def test_eval_suite_gate_failure_semantics(self, tmp_path: Path):
        artifact_path = tmp_path / "eval_summary_fail.json"
        artifact = await run_eval_suite(
            artifact_path=str(artifact_path),
            thresholds={
                "min_correctness_rate": 1.0,
                "min_groundedness_citation_compliance_rate": 1.0,
                "max_failure_rate": 0.0,
                "max_latency_p95_ms": 0.0,
            },
        )

        assert artifact_path.exists()
        assert artifact["gates"]["passed"] is False
