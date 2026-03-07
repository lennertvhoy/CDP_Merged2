"""
Query Builder Interfaces for CDP_Merged.
From CDPT - Strategy pattern for query generation.
"""

from abc import ABC, abstractmethod

from src.search_engine.schema import ProfileSearchParams


class QueryBuilder(ABC):
    """Abstract base class for query builders."""

    @abstractmethod
    def build(self, params: ProfileSearchParams) -> str:
        """
        Build a query from ProfileSearchParams.

        Args:
            params: The search parameters

        Returns:
            Query string in the specific DSL
        """
        pass
