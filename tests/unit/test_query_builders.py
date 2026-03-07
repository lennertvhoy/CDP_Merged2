"""
Tests for CDP_Merged query builders.
"""

import pytest

from src.ai_interface.tools.search import _get_nace_codes_from_keyword
from src.search_engine.builders.sql_builder import SQLBuilder
from src.search_engine.builders.tql_builder import TQLBuilder
from src.search_engine.schema import ProfileSearchParams


class TestTQLBuilder:
    """Tests for TQL query builder."""

    def test_basic_city_query(self):
        """Test building a query with city filter."""
        builder = TQLBuilder()
        params = ProfileSearchParams(city="Gent", status="AC")
        query = builder.build(params)

        assert 'traits.city="Gent"' in query
        assert 'traits.status="AC"' in query

    def test_polyglot_city_variants(self):
        """Test that city variants are generated."""
        builder = TQLBuilder()
        params = ProfileSearchParams(city="Ghent")  # English spelling
        query = builder.build(params)

        # Should include both Gent and Ghent variants
        assert 'traits.city="Gent"' in query
        assert 'traits.city="Ghent"' in query

    def test_nace_codes_query(self):
        """Test building query with NACE codes."""
        builder = TQLBuilder()
        params = ProfileSearchParams(nace_codes=["62010", "62020"])
        query = builder.build(params)

        assert 'traits.nace_codes IN ["62010", "62020"]' in query

    def test_kbo_normalization(self):
        """Test KBO number normalization."""
        builder = TQLBuilder()
        params = ProfileSearchParams(enterprise_number="0207.446.759")
        query = builder.build(params)

        # Should include both dotted and clean versions
        assert "0207.446.759" in query or "0207446759" in query

    def test_has_email_filter(self):
        """Test email existence filter."""
        builder = TQLBuilder()
        params = ProfileSearchParams(has_email=True)
        query = builder.build(params)

        assert "traits.email EXISTS" in query


class TestSQLBuilder:
    """Tests for SQL query builder."""

    def test_basic_sql_query(self):
        """Test building a basic SQL query."""
        builder = SQLBuilder()
        params = ProfileSearchParams(city="Gent", status="AC")
        query = builder.build(params)

        assert "SELECT *" in query
        assert "FROM profiles" in query
        assert "city ILIKE 'Gent'" in query
        assert "status = 'AC'" in query


class TestNACELookup:
    """Tests for NACE code lookup."""

    def test_it_keyword(self):
        """Test IT keyword lookup."""
        codes = _get_nace_codes_from_keyword("IT")
        # Should include computer programming codes
        assert any(code.startswith("62") for code in codes)

    def test_restaurant_keyword(self):
        """Test restaurant keyword lookup."""
        codes = _get_nace_codes_from_keyword("restaurant")
        # Should include restaurant codes
        assert len(codes) > 0

    def test_word_boundary_matching(self):
        """Test that word boundaries are respected."""
        # "IT" should not match "sanITary"
        codes_sanitary = _get_nace_codes_from_keyword("sanitary")
        codes_it = _get_nace_codes_from_keyword("IT")

        # These should be different
        assert codes_sanitary != codes_it


class TestValidation:
    """Tests for query validation."""

    def test_safe_query(self):
        """Test that safe queries pass validation."""
        from src.core.validation import validate_query

        result = validate_query("SELECT * FROM profiles WHERE city = 'Gent'")
        assert result["valid"] is True

    def test_destructive_query_blocked(self):
        """Test that destructive queries are blocked."""
        from src.core.validation import validate_query

        result = validate_query("DROP TABLE profiles")
        assert result["valid"] is False
        assert "destructive" in result["error"].lower()

    def test_sql_injection_blocked(self):
        """Test SQL injection patterns are detected."""
        from src.core.validation import validate_query

        result = validate_query("SELECT * FROM profiles WHERE id = '1' OR '1'='1'")
        assert result["valid"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
