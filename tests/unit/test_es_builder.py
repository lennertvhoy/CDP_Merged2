"""Unit tests for Elasticsearch DSL builder."""

from __future__ import annotations

import json

import pytest

from src.search_engine.builders.es_builder import ESBuilder
from src.search_engine.schema import ProfileSearchParams


@pytest.fixture
def builder() -> ESBuilder:
    return ESBuilder()


def parse(query_str: str) -> dict:
    return json.loads(query_str)


class TestESBuilder:
    def test_empty_params_returns_empty(self, builder):
        params = ProfileSearchParams(status=None)
        result = builder.build(params)
        assert result == ""

    def test_city_filter(self, builder):
        params = ProfileSearchParams(city="Gent", status=None)
        result = parse(builder.build(params))
        must = result["query"]["bool"]["filter"]
        cities = [c for c in must if "term" in c and "traits.city.keyword" in c["term"]]
        assert len(cities) == 1
        assert cities[0]["term"]["traits.city.keyword"] == "Gent"

    def test_status_filter(self, builder):
        params = ProfileSearchParams(status="AC")
        result = parse(builder.build(params))
        must = result["query"]["bool"]["filter"]
        statuses = [c for c in must if "term" in c and "traits.status.keyword" in c["term"]]
        assert any(s["term"]["traits.status.keyword"] == "AC" for s in statuses)

    def test_nace_codes_filter(self, builder):
        params = ProfileSearchParams(nace_codes=["62010", "62020"], status=None)
        result = parse(builder.build(params))
        must = result["query"]["bool"]["filter"]
        # NACE codes now use a bool should clause for both singular and plural field names
        bool_clauses = [c for c in must if "bool" in c and "should" in c["bool"]]
        assert len(bool_clauses) == 1
        should_clauses = bool_clauses[0]["bool"]["should"]
        # Check that both singular and plural field names are present
        nace_fields = [c["terms"].keys() for c in should_clauses if "terms" in c]
        nace_fields_flat = [k for keys in nace_fields for k in keys]
        assert any("traits.nace_code" in f for f in nace_fields_flat)
        assert any("traits.nace_codes" in f for f in nace_fields_flat)

    def test_has_email_filter(self, builder):
        params = ProfileSearchParams(has_email=True, status=None)
        result = parse(builder.build(params))
        must = result["query"]["bool"]["filter"]
        exists_clauses = [c for c in must if "exists" in c]
        assert any(c["exists"]["field"] == "traits.email" for c in exists_clauses)

    def test_min_start_date_filter(self, builder):
        params = ProfileSearchParams(min_start_date="2020-01-01", status=None)
        result = parse(builder.build(params))
        must = result["query"]["bool"]["filter"]
        range_clauses = [c for c in must if "range" in c]
        assert len(range_clauses) == 1

    def test_combined_filters(self, builder):
        params = ProfileSearchParams(city="Gent", status="AC", has_email=True)
        result = parse(builder.build(params))
        must = result["query"]["bool"]["filter"]
        assert len(must) >= 3  # city, status, has_email
        assert "_source" in result
        assert "traits.city" in result["_source"]
