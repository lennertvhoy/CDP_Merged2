"""Deterministic assertions for multi-turn integration stories."""

from __future__ import annotations

import json
import re
from typing import Any

from tests.integration.helpers.conversation_driver import TurnResult


def assert_turn_indexing(results: list[TurnResult]) -> None:
    assert results, "Expected at least one turn result."
    for expected_index, result in enumerate(results, start=1):
        assert result.turn_index == expected_index, (
            f"Turn indexing mismatch: expected {expected_index}, got {result.turn_index}"
        )


def assert_session_identity(results: list[TurnResult]) -> None:
    assert results, "Expected at least one turn result."
    thread_ids = {result.thread_id for result in results}
    profile_ids = {result.profile_id for result in results}
    assert len(thread_ids) == 1, f"Expected one thread_id, got {thread_ids}"
    assert len(profile_ids) == 1, f"Expected one profile_id, got {profile_ids}"


def assert_protocol_invariants(result: TurnResult, *, expect_tools: bool = False) -> None:
    assert result.user_text.strip(), "User text should never be empty."
    assert "agent" in result.node_trace, f"Missing agent node trace: {result.node_trace}"
    assert result.final_answer is not None and str(result.final_answer).strip(), (
        "Final answer should be non-empty."
    )
    if expect_tools:
        assert result.tool_calls, "Expected tool calls but none were captured."
        assert "tools" in result.node_trace, (
            "Expected tools node trace when tool calls are expected."
        )


def assert_expected_tools(result: TurnResult, expected_tools: list[str]) -> None:
    actual = {call.get("name") for call in result.tool_calls}
    missing = [name for name in expected_tools if name not in actual]
    assert not missing, f"Missing expected tools {missing}; got {sorted(actual)}"


def assert_error_recovery_happened(result: TurnResult) -> None:
    error_tools: set[str] = set()
    successful_tools: set[str] = set()

    for chunk in result.raw_chunks:
        if chunk.get("node") != "tools":
            continue
        for tool_message in chunk.get("tool_messages", []):
            name = tool_message.get("name")
            status = tool_message.get("status")
            if not name:
                continue
            if status == "error":
                error_tools.add(name)
            else:
                successful_tools.add(name)

    assert error_tools, "Expected at least one tool error for recovery scenario."
    assert error_tools & successful_tools, (
        "Expected at least one errored tool to be retried successfully."
    )


def extract_tool_json_payloads(
    result: TurnResult,
    *,
    tool_name: str | None = None,
    include_error_status: bool = False,
) -> list[dict[str, Any]]:
    """Extract JSON object payloads emitted by tool messages for one turn."""
    payloads: list[dict[str, Any]] = []

    for chunk in result.raw_chunks:
        if chunk.get("node") != "tools":
            continue

        for tool_message in chunk.get("tool_messages", []):
            name = tool_message.get("name")
            status = tool_message.get("status")
            if tool_name and name != tool_name:
                continue
            if status == "error" and not include_error_status:
                continue

            content = tool_message.get("content")
            if not isinstance(content, str):
                continue
            try:
                decoded = json.loads(content)
            except json.JSONDecodeError:
                continue

            if isinstance(decoded, dict):
                payloads.append(decoded)

    return payloads


def compute_citation_coverage(results: list[TurnResult]) -> dict[str, float | int]:
    """Compute citation-coverage metrics over Azure-grounded tool payloads."""
    azure_payloads = 0
    payloads_with_citations = 0
    total_citations = 0

    for result in results:
        for payload in extract_tool_json_payloads(result, tool_name="search_profiles"):
            if payload.get("retrieval_backend") != "azure_ai_search":
                continue
            azure_payloads += 1
            citations = payload.get("citations") or []
            if citations:
                payloads_with_citations += 1
            total_citations += len(citations)

    coverage_ratio = (
        float(payloads_with_citations) / float(azure_payloads) if azure_payloads else 1.0
    )
    return {
        "azure_payloads": azure_payloads,
        "payloads_with_citations": payloads_with_citations,
        "total_citations": total_citations,
        "coverage_ratio": coverage_ratio,
    }


def assert_citation_coverage(results: list[TurnResult], *, min_ratio: float = 1.0) -> None:
    metrics = compute_citation_coverage(results)
    assert metrics["coverage_ratio"] >= min_ratio, (
        f"Citation coverage below threshold. metrics={metrics}, min_ratio={min_ratio}"
    )


def assert_retrieval_backend_metadata_present(
    result: TurnResult,
    *,
    expected_backend: str | None = None,
) -> None:
    payloads = extract_tool_json_payloads(result, tool_name="search_profiles")
    assert payloads, "Expected at least one search_profiles JSON payload in tool messages."

    for payload in payloads:
        assert "retrieval_backend" in payload, f"Missing retrieval_backend in payload: {payload}"
        counts = payload.get("counts")
        assert isinstance(counts, dict), f"Missing counts metadata in payload: {payload}"
        assert "authoritative_total" in counts, (
            f"Missing authoritative_total in payload: {payload}"
        )

    if expected_backend is not None:
        backends = {str(payload.get("retrieval_backend")) for payload in payloads}
        assert expected_backend in backends, (
            f"Expected backend '{expected_backend}' not found; got {sorted(backends)}"
        )


def assert_shadow_metadata_consistent(result: TurnResult) -> None:
    payloads = extract_tool_json_payloads(result, tool_name="search_profiles")
    assert payloads, "Expected search_profiles payloads for shadow assertions."

    shadow_payload = next(
        (payload for payload in payloads if isinstance(payload.get("shadow_retrieval"), dict)),
        None,
    )
    assert shadow_payload is not None, "Expected shadow_retrieval metadata but none found."

    shadow = shadow_payload["shadow_retrieval"]
    assert shadow.get("enabled") is True, f"Expected shadow mode enabled. payload={shadow_payload}"
    assert shadow.get("backend") == "azure_ai_search", (
        f"Expected azure_ai_search shadow backend. payload={shadow_payload}"
    )

    primary_counts = shadow_payload.get("counts") or {}
    shadow_counts = shadow.get("counts") or {}
    assert isinstance(primary_counts, dict) and isinstance(shadow_counts, dict), (
        f"Missing primary/shadow count metadata. payload={shadow_payload}"
    )
    assert isinstance(primary_counts.get("authoritative_total"), int)
    assert isinstance(primary_counts.get("returned_samples"), int)
    assert isinstance(shadow_counts.get("authoritative_total"), int)
    assert isinstance(shadow_counts.get("returned_samples"), int)


def assert_low_confidence_fallback_behavior(result: TurnResult) -> None:
    payloads = extract_tool_json_payloads(result, tool_name="search_profiles")
    assert payloads, "Expected search_profiles payloads for fallback assertions."

    fallback_payload = next(
        (
            payload
            for payload in payloads
            if payload.get("used_keyword_fallback") is True
            and payload.get("search_strategy") == "name_lexical_fallback"
        ),
        None,
    )
    assert fallback_payload is not None, (
        "Expected a lexical fallback payload under low-confidence/insufficient context path."
    )
    assert fallback_payload.get("resolved_nace_codes") == [], (
        f"Expected no resolved_nace_codes in fallback mode: {fallback_payload}"
    )


def assert_answer_contains_citation_markers(result: TurnResult) -> None:
    answer = str(result.final_answer or "")
    has_bracket_marker = bool(re.search(r"\[\d+\]", answer))
    has_source_marker = "source:" in answer.lower()
    assert has_bracket_marker or has_source_marker, (
        f"Expected citation markers in answer text, got: {answer!r}"
    )
