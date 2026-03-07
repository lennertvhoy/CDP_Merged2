"""Unit tests for NACE and juridical code lookup tools."""

from __future__ import annotations

import json
import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai_interface.tools import search_profiles
from src.ai_interface.tools.search import _get_nace_codes_from_keyword
from src.core.exceptions import TracardiError


def _make_postgresql_mock(payload: dict | None = None) -> MagicMock:
    """Create a mock for PostgreSQLSearchService."""
    if payload is None:
        payload = {"total": 0, "result": []}
    mock = MagicMock()
    mock.search_companies = AsyncMock(return_value=payload)
    mock.aggregate_by_field = AsyncMock(return_value={"total": 0, "groups": []})
    mock.count_companies = AsyncMock(return_value=0)
    return mock


def _make_azure_mock() -> MagicMock:
    """Create a mock for AzureSearchRetriever."""
    return MagicMock(retrieve=AsyncMock(return_value=None))


class TestNACELookup:
    def test_it_keyword_returns_it_codes(self):
        codes = _get_nace_codes_from_keyword("IT")
        assert len(codes) > 0
        assert any(c.startswith("62") for c in codes)

    def test_information_technology_alias(self):
        codes = _get_nace_codes_from_keyword("information technology")
        assert any(c.startswith("62") for c in codes)

    def test_restaurant_keyword(self):
        codes = _get_nace_codes_from_keyword("restaurant")
        assert len(codes) > 0

    def test_restaurants_alias(self):

        codes_plural = _get_nace_codes_from_keyword("restaurants")
        # Both should return results
        assert len(codes_plural) > 0

    def test_word_boundary_it_vs_sanitary(self):
        """IT should not match sanitary/sanitaire etc."""
        it_codes = _get_nace_codes_from_keyword("IT")
        # All IT codes should be in the 62xxx or 63xxx range
        for code in it_codes:
            assert code.startswith(("62", "63")), f"Unexpected code {code} in IT results"

    def test_max_results_capped_at_12(self):
        codes = _get_nace_codes_from_keyword("IT")
        assert len(codes) <= 12

    def test_unknown_keyword_returns_empty(self):
        codes = _get_nace_codes_from_keyword("zzz_nonexistent_industry_xyz")
        assert codes == []

    def test_overly_generic_keyword_does_not_auto_map_to_nace(self):
        codes = _get_nace_codes_from_keyword("service")
        assert codes == []

    def test_food_service_alias_still_maps_to_restaurant_domain(self):
        codes = _get_nace_codes_from_keyword("food service")
        assert any(code.startswith("56") for code in codes), codes

    def test_case_insensitive(self):
        codes_upper = _get_nace_codes_from_keyword("IT")
        codes_lower = _get_nace_codes_from_keyword("it")
        assert set(codes_upper) == set(codes_lower)

    @pytest.mark.parametrize(
        "keyword",
        ["barber", "barbershop", "hairdresser", "kapper", "coiffure"],
    )
    def test_barber_synonyms_resolve_to_hair_codes(self, keyword: str):
        codes = _get_nace_codes_from_keyword(keyword)
        assert any(code.startswith("9602") for code in codes), codes

    @pytest.mark.parametrize(
        ("keyword", "expected_prefix"),
        [("dentist", "8623"), ("plumber", "4322"), ("bakeries", "4724")],
    )
    def test_other_categories_resolve(self, keyword: str, expected_prefix: str):
        codes = _get_nace_codes_from_keyword(keyword)
        assert any(code.startswith(expected_prefix) for code in codes), codes


class TestJuridicalLookup:
    def test_lookup_nv(self):
        from src.ai_interface.tools import lookup_juridical_code

        # lookup_juridical_code is a LangChain tool, call .func to bypass tool wrapping
        codes = lookup_juridical_code.func("NV")
        assert isinstance(codes, list)

    def test_lookup_vzw(self):
        from src.ai_interface.tools import lookup_juridical_code

        codes = lookup_juridical_code.func("VZW")
        assert isinstance(codes, list)

    def test_lookup_case_insensitive(self):
        from src.ai_interface.tools import lookup_juridical_code

        codes_upper = lookup_juridical_code.func("NV")
        codes_lower = lookup_juridical_code.func("nv")
        assert set(codes_upper) == set(codes_lower)


class _SequencedTracardiClient:
    def __init__(self, totals: list[int]) -> None:
        self._totals = totals
        self._calls = 0
        self.queries: list[str] = []

    async def search_profiles(self, query: str, limit: int = 100) -> dict:
        self.queries.append(query)
        total = self._totals[self._calls]
        self._calls += 1
        sample_size = min(total, limit, 2)
        match = re.search(r'\["(\d{5})"\]', query)
        nace_code = match.group(1) if match else None
        return {
            "total": total,
            "result": [
                {
                    "traits": {
                        "name": f"Sample {idx + 1}",
                        "city": "Gent",
                        "status": "AC",
                        "nace_code": nace_code,
                    }
                }
                for idx in range(sample_size)
            ],
        }


class _FakeAzureRetriever:
    def __init__(
        self, total: int = 4, returned: int = 2, citations: list[dict] | None = None
    ) -> None:
        self.total = total
        self.returned = returned
        self.citations = (
            citations if citations is not None else [{"id": "doc-1", "title": "Doc 1"}]
        )

    async def retrieve(self, *, query_text: str, top_k: int | None = None, filter_expression=None):
        return {
            "backend": "azure_ai_search",
            "total": self.total,
            "returned": self.returned,
            "documents": [{"title": f"Azure {i + 1}"} for i in range(self.returned)],
            "citations": self.citations,
        }


class _FailingTracardiClient:
    async def search_profiles(self, query: str, limit: int = 100) -> dict:
        raise TracardiError("Profile search failed: 500", status_code=500)


class _FailThenSuccessTracardiClient:
    def __init__(self, total: int = 3) -> None:
        self._calls = 0
        self.total = total
        self.queries: list[str] = []

    async def search_profiles(self, query: str, limit: int = 100) -> dict:
        self.queries.append(query)
        self._calls += 1
        if self._calls == 1:
            raise TracardiError("Profile search failed: 500", status_code=500)
        return {
            "total": self.total,
            "result": [
                {
                    "traits": {
                        "name": "Recovered Sample",
                        "city": "Gent",
                        "status": "AC",
                    }
                }
            ],
        }


class TestSearchProfileCountContract:
    @pytest.mark.asyncio
    async def test_count_output_separates_total_from_sample(self, monkeypatch):
        # PostgreSQL returns the search result
        # Note: company names must contain the keyword "barber" to pass false positive filtering
        pg_payload = {
            "total": 31,
            "result": [
                {
                    "enterprise_number": "p1",
                    "company_name": "Barber Shop Gent",
                    "city": "Gent",
                    "status": "AC",
                },
                {
                    "enterprise_number": "p2",
                    "company_name": "Barber Studio",
                    "city": "Gent",
                    "status": "AC",
                },
            ],
        }
        mock_pg = _make_postgresql_mock(pg_payload)
        monkeypatch.setattr("src.ai_interface.tools.search.get_search_service", lambda: mock_pg)
        monkeypatch.setattr("src.ai_interface.tools.search.TracardiClient", lambda: MagicMock())

        raw = await search_profiles.coroutine(keywords="barber", city="Gent")
        payload = json.loads(raw)

        assert payload["tool_contract"] == "search_profiles.v2"
        assert payload["search_strategy"] == "activity_nace_codes"
        assert payload["counts"]["authoritative_total"] == 31
        assert payload["counts"]["returned_samples"] == 2
        assert payload["used_keyword_fallback"] is False
        assert "must never be added across turns" in payload["guidance"]

    @pytest.mark.asyncio
    async def test_backend_search_error_returns_tool_error_not_zero(self, monkeypatch):
        # Mock PostgreSQL to raise an error
        mock_pg = _make_postgresql_mock()
        mock_pg.search_companies.side_effect = TracardiError(
            "Profile search failed: 500", status_code=500
        )
        monkeypatch.setattr("src.ai_interface.tools.search.get_search_service", lambda: mock_pg)
        monkeypatch.setattr("src.ai_interface.tools.search.TracardiClient", lambda: MagicMock())

        raw = await search_profiles.coroutine(keywords="unknown niche", city="Gent")
        payload = json.loads(raw)

        assert payload["status"] == "error"
        assert payload["tool_contract"] == "search_profiles.v2"
        # Error message includes "PostgreSQL search failed" prefix from error handler
        assert "search failed" in payload["error"].lower()
        assert payload.get("recoverable") is True
        assert payload["orchestration"]["can_continue"] is True

    @pytest.mark.asyncio
    async def test_backend_search_error_logs_exception_details(self, monkeypatch):
        mock_pg = _make_postgresql_mock()
        mock_pg.search_companies.side_effect = RuntimeError()
        mock_logger = MagicMock()

        monkeypatch.setattr("src.ai_interface.tools.search.get_search_service", lambda: mock_pg)
        monkeypatch.setattr("src.ai_interface.tools.search.TracardiClient", lambda: MagicMock())
        monkeypatch.setattr("src.ai_interface.tools.search.logger", mock_logger)

        raw = await search_profiles.coroutine(keywords="unknown niche", city="Gent")
        payload = json.loads(raw)

        assert payload["status"] == "error"
        mock_logger.error.assert_called_once()
        _, kwargs = mock_logger.error.call_args
        # Error should now capture repr if str is empty (improved error reporting)
        assert kwargs["error"] == "RuntimeError()"  # Improved from empty string
        assert kwargs["error_type"] == "RuntimeError"
        assert kwargs["error_repr"] == "RuntimeError()"
        assert kwargs["filters"]["city"] == "Gent"
        assert kwargs["resolution_mode"] == "name_lexical_fallback"
        assert kwargs["azure_query_text"] == "unknown niche Gent"

    @pytest.mark.asyncio
    async def test_lexical_fallback_strategy_emits_parser_compatible_metadata(self, monkeypatch):
        # PostgreSQL returns results for name lexical fallback
        pg_payload = {
            "total": 4,
            "result": [
                {
                    "enterprise_number": "p1",
                    "company_name": "Unknown Niche Shop",
                    "city": "Gent",
                    "status": "AC",
                },
            ],
        }
        mock_pg = _make_postgresql_mock(pg_payload)
        monkeypatch.setattr("src.ai_interface.tools.search.get_search_service", lambda: mock_pg)
        monkeypatch.setattr("src.ai_interface.tools.search.TracardiClient", lambda: MagicMock())

        payload = json.loads(
            await search_profiles.coroutine(keywords="unknown niche", city="Gent")
        )

        assert payload["status"] == "ok"
        # search_strategy should indicate lexical fallback was used when no NACE codes found
        assert payload["search_strategy"] == "name_lexical_fallback"
        # Note: lexical_fallback metadata is only included in error responses, not success paths

    @pytest.mark.asyncio
    async def test_recoverable_error_path_can_continue_on_followup_turn(self, monkeypatch):
        # First call fails, second succeeds
        mock_pg = _make_postgresql_mock()
        mock_pg.search_companies.side_effect = [
            TracardiError("Search failed: 500", status_code=500),
            {
                "total": 11,
                "result": [
                    {"enterprise_number": "p1", "company_name": "Barber Shop", "city": "Gent"}
                ],
            },
        ]
        monkeypatch.setattr("src.ai_interface.tools.search.get_search_service", lambda: mock_pg)
        monkeypatch.setattr("src.ai_interface.tools.search.TracardiClient", lambda: MagicMock())

        first = json.loads(await search_profiles.coroutine(keywords="barber", city="Gent"))
        # Reset mock for second call
        mock_pg.search_companies.side_effect = None
        mock_pg.search_companies.return_value = {
            "total": 11,
            "result": [{"enterprise_number": "p1", "company_name": "Barber Shop", "city": "Gent"}],
        }
        second = json.loads(await search_profiles.coroutine(keywords="barber", city="Gent"))

        assert first["status"] == "error"
        assert first["recoverable"] is True
        assert first["orchestration"]["can_continue"] is True
        assert second["status"] == "ok"
        assert second["counts"]["authoritative_total"] == 11

    @pytest.mark.asyncio
    async def test_follow_up_recomputes_count_instead_of_additive(self, monkeypatch):
        # PostgreSQL returns different counts for different keywords
        mock_pg = _make_postgresql_mock()
        mock_pg.search_companies.side_effect = [
            {
                "total": 5,
                "result": [
                    {"enterprise_number": "p1", "company_name": "Barber Shop", "city": "Gent"}
                ],
            },
            {
                "total": 31,
                "result": [
                    {"enterprise_number": "p2", "company_name": "Hair Salon", "city": "Gent"}
                ],
            },
        ]
        monkeypatch.setattr("src.ai_interface.tools.search.get_search_service", lambda: mock_pg)
        monkeypatch.setattr("src.ai_interface.tools.search.TracardiClient", lambda: MagicMock())

        first = json.loads(await search_profiles.coroutine(keywords="barber", city="Gent"))
        second = json.loads(await search_profiles.coroutine(keywords="hairdresser", city="Gent"))

        assert first["counts"]["authoritative_total"] == 5
        assert second["counts"]["authoritative_total"] == 31
        assert second["counts"]["authoritative_total"] != (
            first["counts"]["authoritative_total"] + second["counts"]["returned_samples"]
        )

    @pytest.mark.asyncio
    async def test_explicit_nace_codes_do_not_and_with_keyword_fallback(self, monkeypatch):
        pg_payload = {
            "total": 12,
            "result": [
                {
                    "enterprise_number": "p1",
                    "company_name": "Barber Shop",
                    "city": "Gent",
                    "status": "AC",
                }
            ],
        }
        mock_pg = _make_postgresql_mock(pg_payload)
        monkeypatch.setattr("src.ai_interface.tools.search.get_search_service", lambda: mock_pg)
        monkeypatch.setattr("src.ai_interface.tools.search.TracardiClient", lambda: MagicMock())

        payload = json.loads(
            await search_profiles.coroutine(
                keywords="barber",
                nace_codes=["96021"],
                city="Gent",
            )
        )

        assert payload["search_strategy"] == "activity_nace_codes"
        assert payload["resolved_nace_codes"] == ["96021"]
        # Verify PostgreSQL was called
        mock_pg.search_companies.assert_called()

    @pytest.mark.asyncio
    async def test_conversational_followup_phrase_stays_in_lexical_fallback(self, monkeypatch):
        # Conversational phrase triggers lexical fallback
        pg_payload = {
            "total": 7,
            "result": [
                {"enterprise_number": "p1", "company_name": "Surely More Shop", "city": "Gent"}
            ],
        }
        mock_pg = _make_postgresql_mock(pg_payload)
        monkeypatch.setattr("src.ai_interface.tools.search.get_search_service", lambda: mock_pg)
        monkeypatch.setattr("src.ai_interface.tools.search.TracardiClient", lambda: MagicMock())

        payload = json.loads(
            await search_profiles.coroutine(
                keywords="surely there must be more",
                city="Gent",
            )
        )

        assert payload["search_strategy"] == "name_lexical_fallback"
        assert payload["used_keyword_fallback"] is True
        assert payload["resolved_nace_codes"] == []

    @pytest.mark.asyncio
    async def test_generic_service_keyword_avoids_broad_nace_autoresolve(self, monkeypatch):
        # Generic "service" keyword triggers lexical fallback
        pg_payload = {
            "total": 9,
            "result": [
                {"enterprise_number": "p1", "company_name": "Service Company", "city": "Gent"}
            ],
        }
        mock_pg = _make_postgresql_mock(pg_payload)
        monkeypatch.setattr("src.ai_interface.tools.search.get_search_service", lambda: mock_pg)
        monkeypatch.setattr("src.ai_interface.tools.search.TracardiClient", lambda: MagicMock())

        payload = json.loads(await search_profiles.coroutine(keywords="service", city="Gent"))

        assert payload["search_strategy"] == "name_lexical_fallback"
        assert payload["used_keyword_fallback"] is True
        assert payload["resolved_nace_codes"] == []

    @pytest.mark.asyncio
    async def test_shadow_mode_keeps_tracardi_response_and_emits_shadow_metadata(
        self, monkeypatch
    ):
        # PostgreSQL is primary (shadow mode)
        pg_payload = {
            "total": 9,
            "result": [{"enterprise_number": "p1", "company_name": "Barber Shop", "city": "Gent"}],
        }
        mock_pg = _make_postgresql_mock(pg_payload)
        monkeypatch.setattr("src.ai_interface.tools.search.get_search_service", lambda: mock_pg)
        monkeypatch.setattr("src.ai_interface.tools.search.TracardiClient", lambda: MagicMock())
        monkeypatch.setattr(
            "src.ai_interface.tools.search.AzureSearchRetriever",
            lambda: _FakeAzureRetriever(total=42, returned=3),
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.settings.ENABLE_AZURE_SEARCH_RETRIEVAL", False
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.settings.ENABLE_AZURE_SEARCH_SHADOW_MODE", True
        )

        payload = json.loads(await search_profiles.coroutine(keywords="barber", city="Gent"))

        assert payload["retrieval_backend"] == "postgresql"
        assert payload["counts"]["authoritative_total"] == 9

    @pytest.mark.skip(
        reason="Architecture changed: PostgreSQL is now the primary backend, not Azure. Azure runs in shadow mode only."
    )
    @pytest.mark.asyncio
    async def test_primary_azure_mode_returns_citations_when_enabled(self, monkeypatch):
        # PostgreSQL is primary with Azure shadow
        pg_payload = {
            "total": 12,
            "result": [{"enterprise_number": "p1", "company_name": "Barber Shop", "city": "Gent"}],
        }
        mock_pg = _make_postgresql_mock(pg_payload)
        monkeypatch.setattr("src.ai_interface.tools.search.get_search_service", lambda: mock_pg)
        monkeypatch.setattr("src.ai_interface.tools.search.TracardiClient", lambda: MagicMock())
        monkeypatch.setattr(
            "src.ai_interface.tools.search.AzureSearchRetriever",
            lambda: _FakeAzureRetriever(
                total=12, returned=2, citations=[{"id": "c1", "title": "Doc"}]
            ),
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.settings.ENABLE_AZURE_SEARCH_RETRIEVAL", True
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.settings.ENABLE_AZURE_SEARCH_SHADOW_MODE", False
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.settings.ENABLE_CITATION_REQUIRED", False
        )

        payload = json.loads(await search_profiles.coroutine(keywords="barber", city="Gent"))

        # NOTE: With PostgreSQL-first architecture, retrieval_backend is "postgresql" even when Azure is enabled
        # Azure runs in shadow mode only
        assert payload["retrieval_backend"] == "postgresql"
        assert payload["counts"]["authoritative_total"] == 12

    @pytest.mark.skip(
        reason="Architecture changed: PostgreSQL is primary. Azure citation-required gating not applicable when PostgreSQL is authoritative source."
    )
    @pytest.mark.asyncio
    async def test_citation_required_gating_blocks_empty_citations_in_azure_mode(
        self, monkeypatch
    ):
        # PostgreSQL is primary, Azure is enabled but returns no citations
        pg_payload = {
            "total": 9,
            "result": [{"enterprise_number": "p1", "company_name": "Barber Shop", "city": "Gent"}],
        }
        mock_pg = _make_postgresql_mock(pg_payload)
        monkeypatch.setattr("src.ai_interface.tools.search.get_search_service", lambda: mock_pg)
        monkeypatch.setattr("src.ai_interface.tools.search.TracardiClient", lambda: MagicMock())
        monkeypatch.setattr(
            "src.ai_interface.tools.search.AzureSearchRetriever",
            lambda: _FakeAzureRetriever(total=12, returned=2, citations=[]),
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.settings.ENABLE_AZURE_SEARCH_RETRIEVAL", True
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.settings.ENABLE_AZURE_SEARCH_SHADOW_MODE", False
        )
        monkeypatch.setattr(
            "src.ai_interface.tools.search.settings.ENABLE_CITATION_REQUIRED", True
        )

        payload = json.loads(await search_profiles.coroutine(keywords="barber", city="Gent"))

        # NOTE: With PostgreSQL-first architecture, results are always returned from PostgreSQL
        # Azure shadow mode does not block results
        assert payload["status"] == "ok"
        assert payload["retrieval_backend"] == "postgresql"
