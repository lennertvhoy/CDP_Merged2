"""Unit tests for query validation (critic layer)."""

from __future__ import annotations

from src.core.validation import (
    validate_grounded_response_citations,
    validate_query,
    validate_tql_query,
)


class TestValidateQuery:
    """Tests for SQL query validation."""

    def test_safe_select_query(self):
        result = validate_query("SELECT * FROM profiles WHERE city = 'Gent'")
        assert result["valid"] is True
        assert not result["flags"]

    def test_empty_query_invalid(self):
        result = validate_query("")
        assert result["valid"] is False
        assert "empty_query" in result["flags"]

    def test_none_query_invalid(self):
        result = validate_query(None)  # type: ignore[arg-type]
        assert result["valid"] is False

    def test_drop_table_blocked(self):
        result = validate_query("DROP TABLE profiles")
        assert result["valid"] is False
        assert "destructive_sql" in result["flags"]

    def test_delete_blocked(self):
        result = validate_query("DELETE FROM profiles WHERE id = '1'")
        assert result["valid"] is False

    def test_update_blocked(self):
        result = validate_query("UPDATE profiles SET name = 'x'")
        assert result["valid"] is False

    def test_insert_blocked(self):
        result = validate_query("INSERT INTO profiles VALUES ('x')")
        assert result["valid"] is False

    def test_truncate_blocked(self):
        result = validate_query("TRUNCATE TABLE profiles")
        assert result["valid"] is False

    def test_sql_injection_or_pattern(self):
        result = validate_query("SELECT * FROM profiles WHERE id = '1' OR '1'='1'")
        assert result["valid"] is False
        assert "sql_injection" in result["flags"]

    def test_sql_comment_blocked(self):
        result = validate_query("SELECT * FROM profiles -- drop table")
        assert result["valid"] is False

    def test_semicolon_drop_blocked(self):
        result = validate_query("SELECT 1; DROP TABLE profiles")
        assert result["valid"] is False

    def test_case_insensitive_destructive(self):
        result = validate_query("drop table profiles")
        assert result["valid"] is False

    def test_select_with_join_allowed_schema(self):
        """Queries on allowed schemas should pass."""
        result = validate_query("SELECT * FROM cdp.profiles WHERE city = 'Gent'")
        assert result["valid"] is True


class TestValidateTQLQuery:
    """Tests for TQL query validation."""

    def test_valid_tql(self):
        result = validate_tql_query('traits.city="Gent"')
        assert result["valid"] is True

    def test_empty_tql_invalid(self):
        result = validate_tql_query("")
        assert result["valid"] is False

    def test_mongo_operator_blocked(self):
        result = validate_tql_query("{$where: 'malicious()'}")
        assert result["valid"] is False

    def test_proto_pollution_blocked(self):
        result = validate_tql_query("__proto__.admin = true")
        assert result["valid"] is False

    def test_constructor_blocked(self):
        result = validate_tql_query("constructor.prototype.isAdmin = true")
        assert result["valid"] is False

    def test_complex_valid_tql(self):
        result = validate_tql_query('traits.city="Gent" AND traits.status="AC"')
        assert result["valid"] is True


class TestValidateGroundedResponseCitations:
    def test_allows_missing_citations_when_not_enforced(self):
        result = validate_grounded_response_citations(
            {"retrieval_backend": "azure_ai_search", "citations": []},
            enforce_required=False,
        )
        assert result["valid"] is True

    def test_blocks_missing_citations_when_enforced_for_azure(self):
        result = validate_grounded_response_citations(
            {"retrieval_backend": "azure_ai_search", "citations": []},
            enforce_required=True,
        )
        assert result["valid"] is False
        assert "missing_citations" in result["flags"]

    def test_ignores_non_azure_backend_when_enforced(self):
        result = validate_grounded_response_citations(
            {"retrieval_backend": "tracardi_tql", "citations": []},
            enforce_required=True,
        )
        assert result["valid"] is True
