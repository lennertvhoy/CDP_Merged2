from __future__ import annotations

from tests.integration.test_retrieval_grounding_eval_harness import (
    evaluate_gate_thresholds,
    validate_eval_summary_artifact_schema,
)


def test_evaluate_gate_thresholds_passes_when_all_metrics_within_bounds() -> None:
    payload = evaluate_gate_thresholds(
        correctness_rate=0.92,
        groundedness_citation_compliance_rate=0.95,
        failure_rate=0.05,
        p95_latency_ms=320.0,
        thresholds={
            "min_correctness_rate": 0.85,
            "min_groundedness_citation_compliance_rate": 0.9,
            "max_failure_rate": 0.2,
            "max_latency_p95_ms": 2500.0,
        },
    )

    assert payload["passed"] is True
    assert all(payload["results"].values())


def test_evaluate_gate_thresholds_fails_when_any_metric_breaks_threshold() -> None:
    payload = evaluate_gate_thresholds(
        correctness_rate=0.70,
        groundedness_citation_compliance_rate=0.50,
        failure_rate=0.35,
        p95_latency_ms=3100.0,
        thresholds={
            "min_correctness_rate": 0.85,
            "min_groundedness_citation_compliance_rate": 0.9,
            "max_failure_rate": 0.2,
            "max_latency_p95_ms": 2500.0,
        },
    )

    assert payload["passed"] is False
    assert payload["results"]["correctness_rate"] is False
    assert payload["results"]["groundedness_citation_compliance_rate"] is False
    assert payload["results"]["failure_rate"] is False
    assert payload["results"]["latency_p95_ms"] is False


def test_validate_eval_summary_artifact_schema_accepts_expected_shape() -> None:
    payload = {
        "schema_version": "eval_summary.v1",
        "generated_at": "2026-02-22T00:00:00+00:00",
        "totals": {"cases": 2, "prompts": 4, "citation_required_prompts": 2},
        "metrics": {
            "correctness_rate": 0.95,
            "groundedness_citation_compliance_rate": 0.9,
            "failure_rate": 0.05,
            "latency_ms": {"p50": 11.0, "p95": 19.0, "mean": 13.0},
        },
        "gates": {
            "thresholds": {
                "min_correctness_rate": 0.85,
                "min_groundedness_citation_compliance_rate": 0.9,
                "max_failure_rate": 0.2,
                "max_latency_p95_ms": 2500.0,
            },
            "results": {
                "correctness_rate": True,
                "groundedness_citation_compliance_rate": True,
                "failure_rate": True,
                "latency_p95_ms": True,
            },
            "passed": True,
        },
        "categories": {
            "lookup": {"prompts": 1, "correct_prompts": 1, "failed_prompts": 0},
            "failure": {"prompts": 3, "correct_prompts": 3, "failed_prompts": 1},
        },
        "case_results": [
            {
                "case_id": "lookup-case",
                "category": "lookup",
                "prompt_count": 1,
                "turn_results": [],
            }
        ],
    }

    validate_eval_summary_artifact_schema(payload)
