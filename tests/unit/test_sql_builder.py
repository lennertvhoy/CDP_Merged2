"""Unit tests for SQL query builder - Deterministic Execution Model.

These tests verify the deterministic, parameterized query path that prevents
SQL injection and ensures consistent query execution for the chatbot.
"""

from __future__ import annotations

import pytest

from src.search_engine.builders.sql_builder import SQLBuilder
from src.search_engine.schema import ProfileSearchParams


@pytest.fixture
def builder() -> SQLBuilder:
    return SQLBuilder()


class TestSQLBuilderParameterized:
    """Tests for the deterministic parameterized query builder (production path)."""

    def test_basic_select_parameterized(self, builder):
        """Verify basic parameterized query structure."""
        params = ProfileSearchParams(city="Gent", status="AC")
        sql, query_params = builder.build_parametrized(params)

        assert "SELECT" in sql.upper()
        assert "profiles" in sql.lower()
        # Parameters should be placeholders, not literal values
        assert "$1" in sql or "$2" in sql
        # Actual values should be in the parameter tuple
        assert "Gent" in query_params or any("Gent" in str(p) for p in query_params)

    def test_city_filter_parameterized(self, builder):
        """Verify city filter uses parameterized placeholder."""
        params = ProfileSearchParams(city="Gent")
        sql, query_params = builder.build_parametrized(params)

        # SQL should use placeholder
        assert "$1" in sql
        # Value should be in parameters, not SQL
        assert any("Gent" in str(p) for p in query_params)

    def test_sql_injection_prevention_city(self, builder):
        """Verify SQL injection attempts are neutralized by parameterization."""
        malicious_input = "Gent'; DROP TABLE profiles; --"
        params = ProfileSearchParams(city=malicious_input)
        sql, query_params = builder.build_parametrized(params)

        # SQL should not contain the malicious payload directly
        assert "DROP TABLE" not in sql
        # Malicious input should be safely in the parameter tuple
        assert any("DROP TABLE" in str(p) for p in query_params)

    def test_sql_injection_prevention_keywords(self, builder):
        """Verify SQL injection via keywords field is prevented."""
        malicious_keyword = "test' OR '1'='1"
        params = ProfileSearchParams(keywords=malicious_keyword)
        sql, query_params = builder.build_parametrized(params)

        # SQL should use placeholder for keywords
        assert "$" in sql
        # Malicious pattern should be in parameters, not raw SQL
        assert any("'1'='1" in str(p) for p in query_params)

    def test_nace_codes_parameterized(self, builder):
        """Verify NACE codes use multiple placeholders for IN clause."""
        params = ProfileSearchParams(nace_codes=["62010", "62020", "62030"])
        sql, query_params = builder.build_parametrized(params)

        # Should have placeholders for each code
        assert "$1" in sql
        assert "$2" in sql
        assert "$3" in sql
        # All codes should be in parameters
        assert "62010" in query_params
        assert "62020" in query_params
        assert "62030" in query_params

    def test_combined_filters_parameterized(self, builder):
        """Verify multiple filters use sequential parameter numbering."""
        params = ProfileSearchParams(
            city="Gent", status="AC", nace_codes=["62010"], zip_code="9000"
        )
        sql, query_params = builder.build_parametrized(params)

        # Should have multiple numbered parameters
        assert "$1" in sql
        assert "$2" in sql
        # Check all expected values are in parameters
        param_values = [str(p) for p in query_params]
        assert any("Gent" in v for v in param_values)
        assert "AC" in param_values
        assert "62010" in param_values
        assert "9000" in param_values

    def test_email_domain_parameterized(self, builder):
        """Verify email-domain filters are parameterized safely."""
        params = ProfileSearchParams(email_domain="info@gmail.com")
        sql, query_params = builder.build_parametrized(params)

        assert "SPLIT_PART(email, '@', 2)" in sql
        assert "DROP TABLE" not in sql
        assert "gmail.com" in query_params

    def test_enterprise_number_normalization(self, builder):
        """Verify enterprise number normalization in parameterized query."""
        params = ProfileSearchParams(enterprise_number="0207.446.759")
        sql, query_params = builder.build_parametrized(params)

        # Parameter should have dots removed
        assert "0207446759" in query_params
        assert "0207.446.759" not in query_params

    def test_empty_params_parameterized(self, builder):
        """Verify empty params produce valid parameterized query."""
        params = ProfileSearchParams()
        sql, query_params = builder.build_parametrized(params)

        assert isinstance(sql, str)
        assert isinstance(query_params, tuple)
        assert "SELECT" in sql.upper()

    def test_has_phone_email_flags(self, builder):
        """Verify boolean flags don't generate parameters (static SQL)."""
        # Use status=None to avoid default "AC" parameter
        params = ProfileSearchParams(has_phone=True, has_email=True, status=None)
        sql, query_params = builder.build_parametrized(params)

        # Static conditions should be in SQL
        assert "phone IS NOT NULL" in sql
        assert "email IS NOT NULL" in sql
        # No parameters needed for boolean flags
        assert len(query_params) == 0


class TestSQLBuilderLegacy:
    """Tests for the legacy string-building method (deprecated, non-production)."""

    def test_basic_select(self, builder):
        params = ProfileSearchParams(city="Gent", status="AC")
        query = builder.build(params)
        assert "SELECT" in query.upper()
        assert "profiles" in query.lower()

    def test_city_filter(self, builder):
        params = ProfileSearchParams(city="Gent")
        query = builder.build(params)
        assert "Gent" in query

    def test_status_filter(self, builder):
        params = ProfileSearchParams(status="AC")
        query = builder.build(params)
        assert "AC" in query

    def test_nace_codes(self, builder):
        params = ProfileSearchParams(nace_codes=["62010", "62020"])
        query = builder.build(params)
        assert "62010" in query
        assert "62020" in query

    def test_combined_filters(self, builder):
        params = ProfileSearchParams(city="Gent", status="AC", nace_codes=["62010"])
        query = builder.build(params)
        assert "Gent" in query
        assert "AC" in query
        assert "62010" in query

    def test_empty_params(self, builder):
        params = ProfileSearchParams()
        query = builder.build(params)
        assert isinstance(query, str)
