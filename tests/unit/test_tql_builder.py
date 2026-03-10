"""Unit tests for TQL query builder."""

from __future__ import annotations

import pytest

from src.search_engine.builders.tql_builder import TQLBuilder
from src.search_engine.schema import ProfileSearchParams


@pytest.fixture
def builder() -> TQLBuilder:
    return TQLBuilder()


class TestTQLBuilderCity:
    def test_basic_city(self, builder):
        params = ProfileSearchParams(city="Gent", status="AC")
        query = builder.build(params)
        assert 'traits.city="Gent"' in query
        assert 'traits.status="AC"' in query

    def test_polyglot_gent_variants(self, builder):
        params = ProfileSearchParams(city="Ghent")
        query = builder.build(params)
        # Should include both spellings for Gent
        assert "Gent" in query
        assert "Ghent" in query

    def test_empty_params_returns_default(self, builder):
        params = ProfileSearchParams()
        query = builder.build(params)
        # Empty params returns just the name EXISTS filter (no default status)
        assert query == "traits.name EXISTS"


class TestTQLBuilderNACE:
    def test_single_nace_code(self, builder):
        params = ProfileSearchParams(nace_codes=["62010"])
        query = builder.build(params)
        # Should check both singular and plural field names for compatibility
        assert 'traits.nace_code IN ["62010"]' in query
        assert 'traits.nace_codes IN ["62010"]' in query

    def test_multiple_nace_codes_use_in(self, builder):
        params = ProfileSearchParams(nace_codes=["62010", "62020"])
        query = builder.build(params)
        # Should check both singular and plural field names for compatibility
        assert 'traits.nace_code IN ["62010", "62020"]' in query
        assert 'traits.nace_codes IN ["62010", "62020"]' in query
        # Should use OR between the two field name variants
        assert " OR " in query


class TestTQLBuilderKBO:
    def test_enterprise_number_normalisation(self, builder):
        params = ProfileSearchParams(enterprise_number="0207.446.759")
        query = builder.build(params)
        assert "0207.446.759" in query or "0207446759" in query

    def test_enterprise_number_clean(self, builder):
        params = ProfileSearchParams(enterprise_number="0207446759")
        query = builder.build(params)
        assert "0207446759" in query


class TestTQLBuilderFilters:
    def test_has_email_filter(self, builder):
        params = ProfileSearchParams(has_email=True)
        query = builder.build(params)
        assert "email" in query.lower()

    def test_status_active(self, builder):
        params = ProfileSearchParams(status="AC")
        query = builder.build(params)
        assert "AC" in query

    def test_status_none_not_in_query(self, builder):
        params = ProfileSearchParams(status=None)
        query = builder.build(params)
        # status=None should not add status filter
        assert "status" not in query.lower() or query == ""

    def test_keyword_fallback_uses_lexical_consist(self, builder):
        params = ProfileSearchParams(keywords="barber")
        query = builder.build(params)
        assert '== "*barber*"' in query
        assert 'traits.name="barber"' not in query
