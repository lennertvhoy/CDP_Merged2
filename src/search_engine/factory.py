"""
Query Factory for CDP_Merged.
Generates queries in TQL, SQL, and Elasticsearch DSL formats.
"""

from __future__ import annotations

from src.search_engine.builders.es_builder import ESBuilder
from src.search_engine.builders.sql_builder import SQLBuilder
from src.search_engine.builders.tql_builder import TQLBuilder
from src.search_engine.schema import ProfileSearchParams


class QueryType:
    """Query type constants."""

    TQL = "tql"
    SQL = "sql"
    ELASTIC = "elastic"


class QueryFactory:
    """Factory for generating queries in different formats using the strategy pattern."""

    _builders = {
        QueryType.TQL: TQLBuilder(),
        QueryType.SQL: SQLBuilder(),
        QueryType.ELASTIC: ESBuilder(),
    }

    @classmethod
    def generate(cls, params: ProfileSearchParams, query_type: str) -> str:
        """Generate a query of the specified type.

        Args:
            params: Structured search parameters.
            query_type: One of ``tql``, ``sql``, or ``elastic``.

        Returns:
            Query string in the requested DSL.

        Raises:
            ValueError: If ``query_type`` is not registered.
        """
        builder = cls._builders.get(query_type)
        if not builder:
            raise ValueError(
                f"Unknown query type: '{query_type}'. Supported: {list(cls._builders)}"
            )
        return builder.build(params)

    @classmethod
    def generate_all(cls, params: ProfileSearchParams) -> dict[str, str]:
        """Generate queries in all registered formats.

        Args:
            params: Structured search parameters.

        Returns:
            Dict mapping query type name to query string.
        """
        return {qt: builder.build(params) for qt, builder in cls._builders.items()}
