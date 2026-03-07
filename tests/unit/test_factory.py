"""Unit tests for QueryFactory."""

from __future__ import annotations

import pytest

from src.search_engine.factory import QueryFactory, QueryType
from src.search_engine.schema import ProfileSearchParams


class TestQueryFactory:
    def test_generate_tql(self):
        params = ProfileSearchParams(city="Gent", status="AC")
        query = QueryFactory.generate(params, QueryType.TQL)
        assert isinstance(query, str)

    def test_generate_sql(self):
        params = ProfileSearchParams(city="Gent", status="AC")
        query = QueryFactory.generate(params, QueryType.SQL)
        assert isinstance(query, str)

    def test_generate_elastic(self):
        params = ProfileSearchParams(city="Gent", status="AC")
        query = QueryFactory.generate(params, QueryType.ELASTIC)
        assert isinstance(query, str)

    def test_generate_all_returns_all_types(self):
        params = ProfileSearchParams(city="Gent", status="AC")
        queries = QueryFactory.generate_all(params)
        assert QueryType.TQL in queries
        assert QueryType.SQL in queries
        assert QueryType.ELASTIC in queries

    def test_generate_all_returns_strings(self):
        params = ProfileSearchParams(city="Gent", status="AC")
        queries = QueryFactory.generate_all(params)
        for v in queries.values():
            assert isinstance(v, str)

    def test_unknown_query_type_raises(self):
        params = ProfileSearchParams(city="Gent")
        with pytest.raises(ValueError, match="Unknown query type"):
            QueryFactory.generate(params, "unknown_type")
