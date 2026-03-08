"""Unit tests for the query-intent routing guard in critic_node.

These tests verify that the deterministic keyword-based routing rules
correctly reject wrong tool choices before the LLM can execute them,
and that they never block valid tool choices or unrelated queries.

All tests call _validate_tool_call() or _check_routing_rules() directly;
no LLM or network I/O is involved.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.graph.nodes import (
    QUERY_ROUTING_RULES,
    _check_routing_rules,
    _extract_last_user_query,
    _validate_tool_call,
)


# ---------------------------------------------------------------------------
# _extract_last_user_query
# ---------------------------------------------------------------------------


class TestExtractLastUserQuery:
    def test_returns_last_human_message_lowercase(self):
        messages = [
            SystemMessage(content="system prompt"),
            HumanMessage(content="How well are SOURCE SYSTEMS linked to KBO?"),
        ]
        assert _extract_last_user_query(messages) == "how well are source systems linked to kbo?"

    def test_returns_last_of_multiple_human_messages(self):
        messages = [
            HumanMessage(content="First question"),
            AIMessage(content="First answer"),
            HumanMessage(content="Second QUESTION"),
        ]
        assert _extract_last_user_query(messages) == "second question"

    def test_returns_empty_string_when_no_human_message(self):
        messages = [SystemMessage(content="system prompt")]
        assert _extract_last_user_query(messages) == ""

    def test_returns_empty_string_for_empty_list(self):
        assert _extract_last_user_query([]) == ""


# ---------------------------------------------------------------------------
# _check_routing_rules
# ---------------------------------------------------------------------------


class TestCheckRoutingRules:
    # ── Identity link quality ──────────────────────────────────────────────

    def test_kbo_link_query_rejects_coverage_stats(self):
        valid, msg = _check_routing_rules(
            "get_data_coverage_stats",
            "how well are source systems linked to kbo?",
        )
        assert not valid
        assert "get_identity_link_quality" in msg
        assert "get_data_coverage_stats" in msg

    def test_kbo_link_query_rejects_search_profiles(self):
        valid, msg = _check_routing_rules(
            "search_profiles",
            "how well are source systems linked to kbo?",
        )
        assert not valid
        assert "get_identity_link_quality" in msg

    def test_kbo_link_query_allows_correct_tool(self):
        valid, msg = _check_routing_rules(
            "get_identity_link_quality",
            "how well are source systems linked to kbo?",
        )
        assert valid
        assert msg == ""

    def test_match_rate_keyword_triggers_rule(self):
        valid, msg = _check_routing_rules(
            "get_data_coverage_stats",
            "what is the kbo match rate for teamleader?",
        )
        assert not valid
        assert "get_identity_link_quality" in msg

    # ── Geographic revenue distribution ───────────────────────────────────

    def test_revenue_distribution_rejects_aggregate_profiles(self):
        valid, msg = _check_routing_rules(
            "aggregate_profiles",
            "show me revenue distribution by city",
        )
        assert not valid
        assert "get_geographic_revenue_distribution" in msg
        assert "aggregate_profiles" in msg

    def test_revenue_by_city_rejects_search_profiles(self):
        valid, msg = _check_routing_rules(
            "search_profiles",
            "which cities have the most revenue by city?",
        )
        assert not valid
        assert "get_geographic_revenue_distribution" in msg

    def test_revenue_distribution_allows_correct_tool(self):
        valid, msg = _check_routing_rules(
            "get_geographic_revenue_distribution",
            "show me revenue distribution by city",
        )
        assert valid
        assert msg == ""

    # ── Industry pipeline ─────────────────────────────────────────────────

    def test_pipeline_value_query_rejects_search_profiles(self):
        valid, msg = _check_routing_rules(
            "search_profiles",
            "pipeline value for software companies in brussels?",
        )
        assert not valid
        assert "get_industry_summary" in msg
        assert "search_profiles" in msg

    def test_pipeline_value_query_rejects_aggregate_profiles(self):
        valid, msg = _check_routing_rules(
            "aggregate_profiles",
            "what is the total pipeline value for it companies?",
        )
        assert not valid
        assert "get_industry_summary" in msg

    def test_pipeline_value_allows_correct_tool(self):
        valid, msg = _check_routing_rules(
            "get_industry_summary",
            "pipeline value for software companies in brussels?",
        )
        assert valid
        assert msg == ""

    def test_industry_pipeline_keyword_triggers_rule(self):
        valid, msg = _check_routing_rules(
            "search_profiles",
            "show me total pipeline for software and retail segments",
        )
        assert not valid
        assert "get_industry_summary" in msg

    # ── No rule should fire for unrelated queries ─────────────────────────

    def test_generic_search_query_is_not_affected(self):
        valid, msg = _check_routing_rules(
            "search_profiles",
            "find restaurants in gent",
        )
        assert valid
        assert msg == ""

    def test_aggregate_by_city_for_counts_is_not_affected(self):
        """aggregate_profiles for simple count breakdowns must not be blocked."""
        valid, msg = _check_routing_rules(
            "aggregate_profiles",
            "break down companies by city",
        )
        assert valid
        assert msg == ""

    def test_empty_user_query_never_blocks(self):
        valid, msg = _check_routing_rules("search_profiles", "")
        assert valid
        assert msg == ""

    def test_coverage_stats_for_data_quality_is_not_affected(self):
        """get_data_coverage_stats called for actual coverage questions must pass."""
        valid, msg = _check_routing_rules(
            "get_data_coverage_stats",
            "what is the overall data quality and completeness?",
        )
        assert valid
        assert msg == ""

    # ── Non-forbidden tool for a routing-rule query is allowed ────────────

    def test_nace_lookup_before_industry_query_is_allowed(self):
        """A preparatory lookup_nace_code call must not be blocked by the pipeline rule."""
        valid, msg = _check_routing_rules(
            "lookup_nace_code",
            "pipeline value for software companies in brussels?",
        )
        assert valid
        assert msg == ""


# ---------------------------------------------------------------------------
# _validate_tool_call (integration with routing rules)
# ---------------------------------------------------------------------------


class TestValidateToolCallRoutingIntegration:
    """End-to-end integration: routing guard wired into _validate_tool_call()."""

    def _make_tool_call(self, name: str, args: dict | None = None) -> dict:
        return {"name": name, "args": args or {}, "id": "test-id"}

    def test_routing_guard_rejects_via_validate(self):
        tc = self._make_tool_call("get_data_coverage_stats")
        valid, msg = _validate_tool_call(
            tc, user_query="how well are source systems linked to kbo?"
        )
        assert not valid
        assert "get_identity_link_quality" in msg

    def test_routing_guard_allows_correct_tool_via_validate(self):
        tc = self._make_tool_call("get_identity_link_quality")
        valid, msg = _validate_tool_call(
            tc, user_query="how well are source systems linked to kbo?"
        )
        assert valid
        assert msg == ""

    def test_routing_guard_no_user_query_does_not_block(self):
        """Without a user_query the routing guard must be silent."""
        tc = self._make_tool_call("get_data_coverage_stats")
        valid, msg = _validate_tool_call(tc, user_query="")
        assert valid
        assert msg == ""


# ---------------------------------------------------------------------------
# Sanity-check the rule table itself
# ---------------------------------------------------------------------------


class TestQueryRoutingRulesStructure:
    def test_all_required_tools_are_360_tools(self):
        valid_360_tools = {
            "get_identity_link_quality",
            "get_geographic_revenue_distribution",
            "get_industry_summary",
            "find_high_value_accounts",
            "query_unified_360",
        }
        for rule in QUERY_ROUTING_RULES:
            assert rule["required_tool"] in valid_360_tools, (
                f"Rule '{rule['name']}' has required_tool '{rule['required_tool']}' "
                "which is not a known 360° tool"
            )

    def test_required_tool_not_in_forbidden_tools(self):
        for rule in QUERY_ROUTING_RULES:
            assert rule["required_tool"] not in rule["forbidden_tools"], (
                f"Rule '{rule['name']}' has required_tool in its own forbidden_tools set"
            )

    def test_all_rules_have_keywords(self):
        for rule in QUERY_ROUTING_RULES:
            assert rule["keywords"], f"Rule '{rule['name']}' has no keywords"

    def test_all_rules_have_error_hint(self):
        for rule in QUERY_ROUTING_RULES:
            assert rule.get("error_hint"), f"Rule '{rule['name']}' missing error_hint"
