"""Tests for AI interface search tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai_interface.tools.search import (
    _build_azure_query_text,
    _build_recoverable_search_error_payload,
    _filter_false_positives,
    _validate_profile_match,
)
from src.core.search_cache import get_search_cache


class TestBuildAzureQueryText:
    """Test _build_azure_query_text helper."""

    def test_build_with_all_params(self):
        """Test building query with all parameters."""
        result = _build_azure_query_text(
            original_keyword="IT",
            city="Gent",
            zip_code="9000",
            nace_codes=["62010", "62020"],
            juridical_codes=["014"],
        )
        assert "IT" in result
        assert "Gent" in result
        assert "9000" in result
        assert "62010" in result
        assert "62020" in result
        assert "014" in result

    def test_build_with_minimal_params(self):
        """Test building query with minimal parameters."""
        result = _build_azure_query_text(
            original_keyword=None,
            city=None,
            zip_code=None,
            nace_codes=None,
            juridical_codes=None,
        )
        assert result == "*"

    def test_build_with_only_keyword(self):
        """Test building query with only keyword."""
        result = _build_azure_query_text(
            original_keyword="restaurant",
            city=None,
            zip_code=None,
            nace_codes=None,
            juridical_codes=None,
        )
        assert result == "restaurant"


class TestBuildRecoverableSearchErrorPayload:
    """Test _build_recoverable_search_error_payload helper."""

    def test_build_error_payload(self):
        """Test building recoverable error payload."""
        result = _build_recoverable_search_error_payload(
            error_message="Search failed",
            backend="tracardi_tql",
            tql_query='traits.city="Gent"',
            sql_query="SELECT * FROM profile WHERE city='Gent'",
            status_code=500,
            search_strategy="activity_nace_codes",
        )

        assert result["status"] == "error"
        assert result["tool_contract"] == "search_profiles.v2"
        assert result["error_type"] == "search_backend_failure"
        assert result["error"] == "Search failed"
        assert result["recoverable"] is True
        assert result["retryable"] is True  # 500 status is retryable
        assert result["degraded"] is True
        assert result["backend"] == "tracardi_tql"
        assert result["search_strategy"] == "activity_nace_codes"
        assert "orchestration" in result
        assert "ux" in result
        assert "query" in result

    def test_build_error_payload_non_retryable(self):
        """Test building error payload with non-retryable status."""
        result = _build_recoverable_search_error_payload(
            error_message="Bad request",
            backend="tracardi_tql",
            tql_query='traits.city="Gent"',
            sql_query="SELECT * FROM profile",
            status_code=400,
        )

        assert result["retryable"] is False  # 400 status is not retryable

    def test_build_error_payload_server_error_retryable(self):
        """Test that 5xx errors are retryable."""
        result = _build_recoverable_search_error_payload(
            error_message="Service unavailable",
            backend="tracardi_tql",
            tql_query='traits.city="Gent"',
            sql_query="SELECT * FROM profile",
            status_code=503,
        )
        assert result["retryable"] is True

    def test_build_error_payload_none_status(self):
        """Test that None status is retryable."""
        result = _build_recoverable_search_error_payload(
            error_message="Connection error",
            backend="tracardi_tql",
            tql_query='traits.city="Gent"',
            sql_query="SELECT * FROM profile",
            status_code=None,
        )
        assert result["retryable"] is True

    def test_error_payload_structure(self):
        """Test that error payload has expected structure."""
        result = _build_recoverable_search_error_payload(
            error_message="Test error",
            backend="tracardi_tql",
            tql_query="test query",
            sql_query="test sql",
        )

        # Verify required fields
        assert "status" in result
        assert "tool_contract" in result
        assert "error_type" in result
        assert "error" in result
        assert "recoverable" in result
        assert "retryable" in result
        assert "degraded" in result
        assert "orchestration" in result
        assert "ux" in result
        assert "backend" in result
        assert "query" in result
        assert "lexical_fallback" in result

        # Verify orchestration fields
        assert "can_continue" in result["orchestration"]
        assert "state_safe" in result["orchestration"]
        assert "next_action" in result["orchestration"]

        # Verify UX fields
        assert "message_key" in result["ux"]
        assert "retry_hint" in result["ux"]
        assert "degraded_hint" in result["ux"]


# ---------------------------------------------------------------------------
# Regression tests for specific bugs
# ---------------------------------------------------------------------------


def _make_tracardi_mock(payload: dict) -> MagicMock:
    return MagicMock(search_profiles=AsyncMock(return_value=payload))


def _make_azure_mock() -> MagicMock:
    return MagicMock(retrieve=AsyncMock(return_value=None))


def _make_postgresql_mock(payload: dict | None = None) -> MagicMock:
    """Create a mock for PostgreSQLSearchService that returns PostgreSQL-formatted data."""
    if payload is None:
        payload = {"total": 0, "result": []}
    mock = MagicMock()
    mock.search_companies = AsyncMock(return_value=payload)
    mock.aggregate_by_field = AsyncMock(return_value={"total": 0, "groups": []})
    mock.count_companies = AsyncMock(return_value=0)
    return mock


def _disabled_settings() -> MagicMock:
    ms = MagicMock()
    ms.ENABLE_AZURE_SEARCH_RETRIEVAL = False
    ms.ENABLE_AZURE_SEARCH_SHADOW_MODE = False
    ms.ENABLE_CITATION_REQUIRED = False
    return ms


class TestSearchProfilesAppliedFilters:
    """Regression tests for Bug #1: has_phone/has_email variable shadowing.

    Before the fix, the loop variables has_email / has_phone inside
    search_profiles() silently overwrote the function parameters of the same
    name.  After the loop, applied_filters reflected the LAST profile's
    contact data rather than the caller's intent.
    """

    @pytest.mark.asyncio
    async def test_applied_filters_preserve_has_email_true(self):
        """applied_filters['has_email'] must equal the caller's has_email=True.

        Even when the returned profile has NO email address, the filter value
        must not be overwritten by the loop variable.
        """
        from src.ai_interface.tools.search import search_profiles

        pg_payload = {
            "total": 1,
            "result": [
                {
                    "enterprise_number": "abc",
                    "company_name": "ACME BV",
                    "city": "Gent",
                    "status": "AC",
                    # deliberately NO email or phone
                }
            ],
        }

        with (
            patch(
                "src.ai_interface.tools.search.get_search_service",
                return_value=_make_postgresql_mock(pg_payload),
            ),
            patch(
                "src.ai_interface.tools.search.TracardiClient",
                return_value=_make_tracardi_mock({"total": 0, "result": []}),
            ),
            patch(
                "src.ai_interface.tools.search.AzureSearchRetriever",
                return_value=_make_azure_mock(),
            ),
            patch(
                "src.ai_interface.tools.search.settings",
                _disabled_settings(),
            ),
        ):
            result_raw = await search_profiles.ainvoke(
                {"has_email": True, "has_phone": False, "city": "Gent"}
            )

        result = json.loads(result_raw)
        assert result["status"] == "ok", result

        applied = result["applied_filters"]
        # User asked for has_email=True — must be preserved
        assert applied["has_email"] is True, "Bug #1 regression: has_email overwritten by loop var"
        # User asked for has_phone=False — must be preserved
        assert applied["has_phone"] is False, (
            "Bug #1 regression: has_phone overwritten by loop var"
        )

    @pytest.mark.asyncio
    async def test_status_defaults_to_none_for_generic_searches(self):
        """Generic searches should not silently force active-only filtering."""
        from src.ai_interface.tools.search import search_profiles

        pg_payload = {
            "total": 2,
            "result": [
                {
                    "enterprise_number": "p1",
                    "company_name": "ACME",
                    "city": "Gent",
                }
            ],
        }
        mock_pg = _make_postgresql_mock(pg_payload)

        with (
            patch("src.ai_interface.tools.search.get_search_service", return_value=mock_pg),
            patch(
                "src.ai_interface.tools.search.TracardiClient",
                return_value=_make_tracardi_mock({"total": 0, "result": []}),
            ),
            patch(
                "src.ai_interface.tools.search.AzureSearchRetriever",
                return_value=_make_azure_mock(),
            ),
            patch("src.ai_interface.tools.search.settings", _disabled_settings()),
        ):
            result_raw = await search_profiles.ainvoke({"city": "Gent"})

        result = json.loads(result_raw)
        assert result["applied_filters"]["status"] is None
        called_filters = mock_pg.search_companies.await_args.args[0]
        assert called_filters.status is None

    @pytest.mark.asyncio
    async def test_profile_sample_has_email_reflects_actual_profile_data(self):
        """profiles_sample[n]['has_email'] must reflect the profile's actual data,
        not the filter parameter."""
        from src.ai_interface.tools.search import search_profiles

        pg_payload = {
            "total": 2,
            "result": [
                {
                    "enterprise_number": "p1",
                    "company_name": "ACME",
                    "main_email": "info@acme.be",
                    "city": "Gent",
                    "status": "AC",
                },
                {
                    "enterprise_number": "p2",
                    "company_name": "NoContact BV",
                    "city": "Gent",
                    "status": "AC",
                },
            ],
        }

        with (
            patch(
                "src.ai_interface.tools.search.get_search_service",
                return_value=_make_postgresql_mock(pg_payload),
            ),
            patch(
                "src.ai_interface.tools.search.TracardiClient",
                return_value=_make_tracardi_mock({"total": 0, "result": []}),
            ),
            patch(
                "src.ai_interface.tools.search.AzureSearchRetriever",
                return_value=_make_azure_mock(),
            ),
            patch(
                "src.ai_interface.tools.search.settings",
                _disabled_settings(),
            ),
        ):
            result_raw = await search_profiles.ainvoke({"city": "Gent"})

        result = json.loads(result_raw)
        assert result["status"] == "ok"
        samples = result["profiles_sample"]
        assert len(samples) == 2
        assert samples[0]["has_email"] is True, "First profile has email"
        assert samples[1]["has_email"] is False, "Second profile has no email"

    @pytest.mark.asyncio
    async def test_profile_sample_status_uses_business_status_over_sync_status(self):
        """profiles_sample[n]['status'] must show company lifecycle status, not enrichment state."""
        from src.ai_interface.tools.search import search_profiles

        pg_payload = {
            "total": 1,
            "result": [
                {
                    "enterprise_number": "p1",
                    "company_name": "ACME",
                    "city": "Gent",
                    "status": "AC",
                    "sync_status": "enriched",
                }
            ],
        }

        with (
            patch(
                "src.ai_interface.tools.search.get_search_service",
                return_value=_make_postgresql_mock(pg_payload),
            ),
            patch(
                "src.ai_interface.tools.search.TracardiClient",
                return_value=_make_tracardi_mock({"total": 0, "result": []}),
            ),
            patch(
                "src.ai_interface.tools.search.AzureSearchRetriever",
                return_value=_make_azure_mock(),
            ),
            patch(
                "src.ai_interface.tools.search.settings",
                _disabled_settings(),
            ),
        ):
            result_raw = await search_profiles.ainvoke({"city": "Gent"})

        result = json.loads(result_raw)
        assert result["profiles_sample"][0]["status"] == "AC"

    @pytest.mark.asyncio
    async def test_single_nace_code_alias_maps_into_applied_filters(self):
        """Single nace_code inputs should be normalized to nace_codes."""
        from src.ai_interface.tools.search import search_profiles

        pg_payload = {
            "total": 12,
            "result": [
                {
                    "enterprise_number": "p1",
                    "company_name": "Restaurant Example",
                    "city": "Gent",
                    "status": "AC",
                    "industry_nace_code": "56101",
                }
            ],
        }

        mock_pg = _make_postgresql_mock(pg_payload)

        with (
            patch("src.ai_interface.tools.search.get_search_service", return_value=mock_pg),
            patch(
                "src.ai_interface.tools.search.TracardiClient",
                return_value=_make_tracardi_mock({"total": 0, "result": []}),
            ),
            patch(
                "src.ai_interface.tools.search.AzureSearchRetriever",
                return_value=_make_azure_mock(),
            ),
            patch("src.ai_interface.tools.search.settings", _disabled_settings()),
        ):
            result = json.loads(await search_profiles.ainvoke({"nace_code": "56101"}))

        assert result["status"] == "ok"
        assert result["applied_filters"]["nace_codes"] == ["56101"]
        called_filters = mock_pg.search_companies.await_args.args[0]
        assert called_filters.nace_codes == ["56101"]

    @pytest.mark.asyncio
    async def test_email_domain_filter_is_normalized_and_forwarded(self):
        """Email domain filters should normalize addresses and reach PostgreSQL."""
        from src.ai_interface.tools.search import search_profiles

        pg_payload = {
            "total": 3,
            "result": [
                {
                    "enterprise_number": "p1",
                    "company_name": "Mail Example",
                    "city": "Gent",
                    "status": "AC",
                    "main_email": "owner@gmail.com",
                }
            ],
        }

        mock_pg = _make_postgresql_mock(pg_payload)

        with (
            patch("src.ai_interface.tools.search.get_search_service", return_value=mock_pg),
            patch(
                "src.ai_interface.tools.search.TracardiClient",
                return_value=_make_tracardi_mock({"total": 0, "result": []}),
            ),
            patch(
                "src.ai_interface.tools.search.AzureSearchRetriever",
                return_value=_make_azure_mock(),
            ),
            patch("src.ai_interface.tools.search.settings", _disabled_settings()),
        ):
            result = json.loads(await search_profiles.ainvoke({"email_domain": "info@Gmail.com"}))

        assert result["status"] == "ok"
        assert result["applied_filters"]["email_domain"] == "gmail.com"
        called_filters = mock_pg.search_companies.await_args.args[0]
        assert called_filters.email_domain == "gmail.com"


class TestAggregateProfilesPercentOfTotal:
    """Regression tests for Bug #5: percent_of_total used sample size instead of total_count."""

    @pytest.mark.asyncio
    async def test_percent_of_total_uses_authoritative_total_count(self):
        """percent_of_total must be relative to PostgreSQL's authoritative total_count.

        Scenario: total_count=1000, sample has 2 Gent profiles.
        Before fix: 2/2*100 = 100.0 (used sample size).
        After fix:  round(2/1000*100, 1) = 0.2 (uses total_count).
        """
        from src.ai_interface.tools.search import aggregate_profiles

        # PostgreSQL returns both aggregation results and total count
        # Note: aggregate_profiles wraps the result directly, no status wrapper
        pg_payload = {
            "total": 1000,  # authoritative total
            "groups": [
                {"group_value": "Gent", "count": 2, "percent_of_total": 0.2},
            ],
        }

        mock_service = _make_postgresql_mock()
        mock_service.aggregate_by_field = AsyncMock(return_value=pg_payload)

        with (
            patch(
                "src.ai_interface.tools.search.get_search_service",
                return_value=mock_service,
            ),
            patch(
                "src.ai_interface.tools.search._get_nace_codes_from_keyword",
                return_value=[],
            ),
        ):
            result_raw = await aggregate_profiles.ainvoke({"group_by": "city"})

        # aggregate_profiles returns a JSON string, parse it
        result = json.loads(result_raw)
        # The result doesn't have a 'status' field - it's a direct aggregation result
        # Just verify the groups structure
        groups = result.get("groups", [])
        assert len(groups) == 1

        gent = groups[0]
        assert gent["group_value"] == "Gent"
        assert gent["count"] == 2

        pct = gent["percent_of_total"]
        # Before fix: 100.0; after fix: 0.2
        assert pct < 1.0, (
            f"Bug #5 regression: percent_of_total={pct}. "
            "Should be ~0.2 (2/1000), not 100.0 (2/2 sample)."
        )
        assert pct == pytest.approx(0.2, abs=0.05), f"Expected ~0.2, got {pct}"


class TestNextStepsSuggestionsNoFlexmail:
    """Cleanup #6: 'Flexmail' must not appear in next_steps_suggestions."""

    @pytest.mark.asyncio
    async def test_search_profiles_next_steps_no_flexmail(self):
        """next_steps_suggestions for search_profiles must reference Resend, not Flexmail."""
        from src.ai_interface.tools.search import search_profiles

        pg_payload = {
            "total": 5,
            "result": [
                {
                    "enterprise_number": "p1",
                    "company_name": "Co A",
                    "city": "Gent",
                    "status": "AC",
                },
            ],
        }

        with (
            patch(
                "src.ai_interface.tools.search.get_search_service",
                return_value=_make_postgresql_mock(pg_payload),
            ),
            patch(
                "src.ai_interface.tools.search.TracardiClient",
                return_value=_make_tracardi_mock({"total": 0, "result": []}),
            ),
            patch(
                "src.ai_interface.tools.search.AzureSearchRetriever",
                return_value=_make_azure_mock(),
            ),
            patch(
                "src.ai_interface.tools.search.settings",
                _disabled_settings(),
            ),
        ):
            result = json.loads(await search_profiles.ainvoke({"city": "Gent"}))

        suggestions = " ".join(result.get("next_steps_suggestions", []))
        assert "Flexmail" not in suggestions, "Flexmail reference must not appear in suggestions"
        assert "Resend" in suggestions, "Resend should appear in next_steps_suggestions"

    @pytest.mark.asyncio
    async def test_empty_dataset_changes_guidance_and_suggestions(self):
        """Empty local datasets should be diagnosed, not presented as real zero-market answers."""
        from src.ai_interface.tools.search import search_profiles

        pg_payload = {
            "total": 0,
            "result": [],
            "companies_table_empty": True,
        }

        with (
            patch(
                "src.ai_interface.tools.search.get_search_service",
                return_value=_make_postgresql_mock(pg_payload),
            ),
            patch(
                "src.ai_interface.tools.search.TracardiClient",
                return_value=_make_tracardi_mock({"total": 0, "result": []}),
            ),
            patch(
                "src.ai_interface.tools.search.AzureSearchRetriever",
                return_value=_make_azure_mock(),
            ),
            patch(
                "src.ai_interface.tools.search.settings",
                _disabled_settings(),
            ),
        ):
            result = json.loads(await search_profiles.ainvoke({"city": "Sint-Niklaas"}))

        assert result["dataset_state"]["companies_table_empty"] is True
        assert result["dataset_state"]["zero_result_reason"] == "empty_dataset"
        assert "companies table is currently empty" in result["guidance"].lower()
        suggestions = " ".join(result["next_steps_suggestions"])
        assert "Create a segment" not in suggestions
        assert "Resend" not in suggestions
        assert "Load or import company data" in suggestions


# ---------------------------------------------------------------------------
# Tests for 3 Critical Production Fixes (February 2026)
# ---------------------------------------------------------------------------


class TestTQLPersistenceFix:
    """Test Fix #1: TQL persistence for segment creation alignment.

    The SearchCache (SQLite-backed) persists search queries by conversation_id
    so that create_segment can reuse the exact same TQL query across turns.
    """

    @pytest.mark.asyncio
    async def test_store_and_retrieve_tql_via_cache(self):
        """Test that TQL can be stored and retrieved via SearchCache."""
        test_tql = 'traits.city="Gent" AND traits.status="AC"'
        test_params = {"city": "Gent", "status": "AC"}
        test_conv_id = "test-conv-store-retrieve"

        cache = get_search_cache()

        # Store the TQL
        await cache.store_search(test_conv_id, test_tql, test_params)

        # Retrieve and verify
        retrieved = await cache.get_last_search(test_conv_id)
        assert retrieved is not None, "Should retrieve cached search"
        assert retrieved["tql"] == test_tql, f"Expected {test_tql}, got {retrieved['tql']}"
        assert retrieved["params"] == test_params, (
            f"Expected {test_params}, got {retrieved['params']}"
        )

    @pytest.mark.asyncio
    async def test_cache_returns_none_for_unknown_conversation(self):
        """Test that cache returns None for unknown conversation_id."""
        cache = get_search_cache()
        result = await cache.get_last_search("non-existent-conversation-id")
        assert result is None, "Should return None for unknown conversation"

    @pytest.mark.asyncio
    async def test_search_result_contains_tql_for_segment_creation(self):
        """Test that search_profiles returns TQL that can be used by create_segment."""
        from src.ai_interface.tools.search import search_profiles

        pg_payload = {
            "total": 10,
            "result": [
                {
                    "enterprise_number": "p1",
                    "company_name": "ACME",
                    "city": "Gent",
                    "status": "AC",
                },
            ],
        }

        with (
            patch(
                "src.ai_interface.tools.search.get_search_service",
                return_value=_make_postgresql_mock(pg_payload),
            ),
            patch(
                "src.ai_interface.tools.search.TracardiClient",
                return_value=_make_tracardi_mock({"total": 0, "result": []}),
            ),
            patch(
                "src.ai_interface.tools.search.AzureSearchRetriever",
                return_value=_make_azure_mock(),
            ),
            patch(
                "src.ai_interface.tools.search.settings",
                _disabled_settings(),
            ),
        ):
            result = json.loads(await search_profiles.ainvoke({"city": "Gent"}))

        assert result["status"] == "ok"
        # TQL should be in the result for tools_node to extract and store
        assert "query" in result, "Result should contain query info"
        assert "tql" in result["query"], "Query should contain TQL"
        assert "Gent" in result["query"]["tql"], "TQL should contain the city filter"


class TestFalsePositiveFilteringFix:
    """Test Fix #2: False positive filtering (e.g., "pita" vs "Spitaels").

    The _filter_false_positives function filters out profiles that don't
    actually match the keyword using word boundary matching.
    """

    def test_validate_profile_match_with_word_boundary(self):
        """Test that "pita" matches "Pita Palace" but not "Spitaels"."""
        # Valid match - pita as whole word at start
        profile_valid = {"traits": {"name": "Pita Palace", "kbo_name": "Pita Palace BV"}}
        assert _validate_profile_match(profile_valid, "pita") is True

        # Invalid match - pita inside another word
        profile_invalid = {"traits": {"name": "Spitaels Hospital", "kbo_name": "Spitaels NV"}}
        assert _validate_profile_match(profile_invalid, "pita") is False

        # Another invalid match
        profile_capital = {"traits": {"name": "Capital Foods", "kbo_name": "Capital BV"}}
        assert _validate_profile_match(profile_capital, "pita") is False

    def test_validate_profile_match_with_plurals(self):
        """Test that keyword variations (plurals) are matched."""
        profile = {"traits": {"name": "The Baker's Shop", "kbo_name": "Baker Shop BV"}}

        # Should match singular
        assert _validate_profile_match(profile, "baker") is True
        # Should match plural
        assert _validate_profile_match(profile, "bakers") is True

    def test_filter_false_positives_removes_spitaels(self):
        """Test that Spitaels is filtered out when searching for pita."""
        profiles = [
            {"traits": {"name": "Pita Palace", "kbo_name": "Pita Palace BV"}},
            {"traits": {"name": "Spitaels Hospital", "kbo_name": "Spitaels NV"}},
            {"traits": {"name": "Capital Pita", "kbo_name": "Capital Pita BV"}},
        ]

        filtered = _filter_false_positives(profiles, "pita")

        # Should keep Pita Palace and Capital Pita
        assert len(filtered) == 2
        names = [p["traits"]["name"] for p in filtered]
        assert "Pita Palace" in names
        assert "Capital Pita" in names
        assert "Spitaels Hospital" not in names

    def test_filter_false_positives_with_nace_fallback(self):
        """Test that profiles with matching NACE codes are kept even if name doesn't match."""
        profiles = [
            {
                "traits": {
                    "name": "Spitaels Hospital",
                    "kbo_name": "Spitaels NV",
                    "nace_code": "56101",
                }
            },
            {
                "traits": {
                    "name": "Random Restaurant",
                    "kbo_name": "Random BV",
                    "nace_code": "56102",
                }
            },
        ]

        # With NACE codes for restaurants, both should be kept
        nace_codes = ["56101", "56102"]
        filtered = _filter_false_positives(profiles, "pita", nace_codes)

        # Both should be kept due to NACE code matching
        assert len(filtered) == 2

    def test_filter_false_positives_short_keyword(self):
        """Test that short keywords (< 4 chars) are permissive to avoid over-filtering."""
        profiles = [
            {"traits": {"name": "IT Solutions", "kbo_name": "IT Solutions BV"}},
            {"traits": {"name": "Bit Company", "kbo_name": "Bit BV"}},
        ]

        # Short keyword "it" should not filter aggressively
        filtered = _filter_false_positives(profiles, "it")

        # Both should remain for short keywords
        assert len(filtered) == 2


class TestLimitParameterFix:
    """Search sample-size behavior for filtered vs broad prompts."""

    @pytest.mark.asyncio
    async def test_search_profiles_uses_limit_100_for_filtered_queries(self):
        """Filtered prompts should keep a large sample for concrete examples."""
        from src.ai_interface.tools.search import search_profiles

        pg_payload = {
            "total": 50,
            "result": [
                {
                    "enterprise_number": f"p{i}",
                    "company_name": f"Company {i}",
                    "city": "Gent",
                    "status": "AC",
                }
                for i in range(50)
            ],
        }

        mock_pg_service = _make_postgresql_mock(pg_payload)

        with (
            patch(
                "src.ai_interface.tools.search.get_search_service",
                return_value=mock_pg_service,
            ),
            patch(
                "src.ai_interface.tools.search.TracardiClient",
                return_value=_make_tracardi_mock({"total": 0, "result": []}),
            ),
            patch(
                "src.ai_interface.tools.search.AzureSearchRetriever",
                return_value=_make_azure_mock(),
            ),
            patch(
                "src.ai_interface.tools.search.settings",
                _disabled_settings(),
            ),
        ):
            result = json.loads(await search_profiles.ainvoke({"city": "Gent"}))

        assert result["status"] == "ok"
        # Note: The response uses "counts" structure, not "profile_count" directly
        assert result["counts"]["authoritative_total"] == 50
        # Verify PostgreSQL search_companies was called with filtered-query sample limit.
        mock_pg_service.search_companies.assert_called_once()
        called_filters = mock_pg_service.search_companies.await_args.args[0]
        assert called_filters.limit == 100

    @pytest.mark.asyncio
    async def test_search_profiles_uses_limit_10_for_broad_unfiltered_queries(self):
        """Broad prompts like 'How many companies?' should keep payloads lean."""
        from src.ai_interface.tools.search import search_profiles

        pg_payload = {
            "total": 1941216,
            "result": [
                {"enterprise_number": f"p{i}", "company_name": f"Company {i}"} for i in range(10)
            ],
            "count_is_estimated": True,
            "count_source": "estimated_reltuples",
        }

        mock_pg_service = _make_postgresql_mock(pg_payload)

        with (
            patch(
                "src.ai_interface.tools.search.get_search_service",
                return_value=mock_pg_service,
            ),
            patch(
                "src.ai_interface.tools.search.TracardiClient",
                return_value=_make_tracardi_mock({"total": 0, "result": []}),
            ),
            patch(
                "src.ai_interface.tools.search.AzureSearchRetriever",
                return_value=_make_azure_mock(),
            ),
            patch(
                "src.ai_interface.tools.search.settings",
                _disabled_settings(),
            ),
        ):
            result = json.loads(await search_profiles.ainvoke({}))

        assert result["status"] == "ok"
        mock_pg_service.search_companies.assert_called_once()
        called_filters = mock_pg_service.search_companies.await_args.args[0]
        assert called_filters.limit == 10


class TestNaceZeroResultsFallback:
    """Fallback behavior when NACE mapping yields no matching rows."""

    @pytest.mark.asyncio
    async def test_search_profiles_retries_with_keyword_after_nace_zero_results(self):
        from src.ai_interface.tools.search import search_profiles

        first_result = {"total": 0, "result": []}
        second_result = {
            "total": 2,
            "result": [
                {
                    "enterprise_number": "be-1",
                    "company_name": "Software House BV",
                    "city": "Gent",
                    "status": "AC",
                },
                {
                    "enterprise_number": "be-2",
                    "company_name": "Gent Software Labs",
                    "city": "Gent",
                    "status": "AC",
                },
            ],
        }

        mock_pg_service = _make_postgresql_mock(first_result)
        mock_pg_service.search_companies = AsyncMock(side_effect=[first_result, second_result])

        with (
            patch(
                "src.ai_interface.tools.search.get_search_service",
                return_value=mock_pg_service,
            ),
            patch(
                "src.ai_interface.tools.search._get_nace_codes_from_keyword",
                return_value=["62010"],
            ),
            patch(
                "src.ai_interface.tools.search.TracardiClient",
                return_value=_make_tracardi_mock({"total": 0, "result": []}),
            ),
            patch(
                "src.ai_interface.tools.search.AzureSearchRetriever",
                return_value=_make_azure_mock(),
            ),
            patch(
                "src.ai_interface.tools.search.settings",
                _disabled_settings(),
            ),
        ):
            payload = json.loads(
                await search_profiles.ainvoke({"keywords": "software", "city": "Gent"})
            )

        assert payload["status"] == "ok"
        assert payload["search_strategy"] == "nace_then_name_lexical_fallback"
        assert payload["counts"]["authoritative_total"] == 2
        assert payload["lexical_fallback"]["attempted"] is True
        assert payload["lexical_fallback"]["used"] == "company_name_ILIKE"
        assert mock_pg_service.search_companies.await_count == 2


# ---------------------------------------------------------------------------
# Thread Safety Tests
# ---------------------------------------------------------------------------


class TestSearchCacheIsolation:
    """Test that SearchCache properly isolates conversations."""

    @pytest.mark.asyncio
    async def test_concurrent_conversations_dont_interfere(self):
        """Test that different conversation_ids don't see each other's TQL."""
        cache = get_search_cache()

        # Store different TQL for different conversations
        await cache.store_search("conv-1", "traits.city='Brussels'", {"city": "Brussels"})
        await cache.store_search("conv-2", "traits.city='Gent'", {"city": "Gent"})

        # Retrieve and verify isolation
        result1 = await cache.get_last_search("conv-1")
        result2 = await cache.get_last_search("conv-2")

        assert result1["tql"] == "traits.city='Brussels'", (
            f"Conv 1 should have Brussels TQL, got {result1['tql']}"
        )
        assert result2["tql"] == "traits.city='Gent'", (
            f"Conv 2 should have Gent TQL, got {result2['tql']}"
        )


# ---------------------------------------------------------------------------
# Connection Recovery Tests
# ---------------------------------------------------------------------------


class TestPostgreSQLConnectionRecovery:
    """Test that PostgreSQL search recovers from connection failures."""

    @pytest.mark.asyncio
    async def test_search_attempts_connection_reset_on_error(self, monkeypatch):
        """When PostgreSQL search fails, the system should attempt to reset connection."""
        from src.ai_interface.tools.search import search_profiles

        mock_pg = _make_postgresql_mock()
        mock_pg.search_companies.side_effect = RuntimeError("Connection lost")

        mock_close_service = AsyncMock()
        # Patch at the module where it's imported from
        monkeypatch.setattr(
            "src.services.postgresql_search.close_search_service",
            mock_close_service,
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.get_search_service",
            lambda: mock_pg,
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.TracardiClient",
            lambda: MagicMock(),
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.AzureSearchRetriever",
            lambda: _make_azure_mock(),
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.settings",
            _disabled_settings(),
        )

        raw = await search_profiles.coroutine(keywords="restaurant", city="Gent")
        payload = json.loads(raw)

        # Should return error payload
        assert payload["status"] == "error"
        assert "Connection lost" in payload["error"]

        # Should have attempted to close/reset the service
        mock_close_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_error_includes_exception_type(self, monkeypatch):
        """Error messages should include the exception type for better debugging."""
        from src.ai_interface.tools.search import search_profiles

        mock_pg = _make_postgresql_mock()
        mock_pg.search_companies.side_effect = ConnectionError("DB timeout")

        monkeypatch.setattr(
            "src.ai_interface.tools.search.get_search_service",
            lambda: mock_pg,
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.TracardiClient",
            lambda: MagicMock(),
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.AzureSearchRetriever",
            lambda: _make_azure_mock(),
        )
        monkeypatch.setattr(
            "src.services.postgresql_search.close_search_service",
            AsyncMock(),
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.settings",
            _disabled_settings(),
        )

        raw = await search_profiles.coroutine(keywords="cafe", city="Brussels")
        payload = json.loads(raw)

        assert payload["status"] == "error"
        # Error should include exception type
        assert "ConnectionError" in payload["error"]
        assert "DB timeout" in payload["error"]
