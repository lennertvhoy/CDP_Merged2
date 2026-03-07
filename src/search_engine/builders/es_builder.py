"""
ElasticSearch DSL query builder for CDP_Merged.

This builder generates native Elasticsearch query DSL from ProfileSearchParams.
It is registered in QueryFactory as the 'elastic' query type.
"""

from __future__ import annotations

from typing import Any

from src.search_engine.interfaces import QueryBuilder
from src.search_engine.schema import ProfileSearchParams


class ESBuilder(QueryBuilder):
    """Builds Elasticsearch DSL queries from ProfileSearchParams."""

    def build(self, params: ProfileSearchParams) -> str:
        """Build an Elasticsearch DSL query dict serialised as a JSON string.

        Args:
            params: Structured search parameters.

        Returns:
            JSON string representing the ES query, or empty string if no params.
        """
        import json

        must_clauses: list[dict[str, Any]] = []

        if params.city:
            must_clauses.append({"term": {"traits.city.keyword": params.city}})

        if params.status:
            must_clauses.append({"term": {"traits.status.keyword": params.status}})

        if params.nace_codes:
            # Support both singular and plural field names for compatibility
            must_clauses.append(
                {
                    "bool": {
                        "should": [
                            {"terms": {"traits.nace_code.keyword": params.nace_codes}},
                            {"terms": {"traits.nace_codes.keyword": params.nace_codes}},
                        ]
                    }
                }
            )

        if params.juridical_codes:
            must_clauses.append(
                {"terms": {"traits.juridical_code.keyword": params.juridical_codes}}
            )

        if params.zip_code:
            must_clauses.append({"term": {"traits.zip_code.keyword": params.zip_code}})

        if params.enterprise_number:
            normalized = params.enterprise_number.replace(".", "").replace(" ", "")
            must_clauses.append(
                {
                    "bool": {
                        "should": [
                            {
                                "term": {
                                    "traits.enterprise_number.keyword": params.enterprise_number
                                }
                            },
                            {"term": {"traits.enterprise_number.keyword": normalized}},
                        ]
                    }
                }
            )

        if params.has_email:
            must_clauses.append({"exists": {"field": "traits.email"}})

        if params.has_phone:
            must_clauses.append({"exists": {"field": "traits.phone"}})

        if params.min_start_date:
            must_clauses.append({"range": {"traits.start_date": {"gte": params.min_start_date}}})

        if not must_clauses:
            return ""

        query = {
            "query": {"bool": {"filter": must_clauses}},
            "_source": [
                "id",
                "traits.name",
                "traits.kbo_name",
                "traits.city",
                "traits.kbo_city",
                "traits.status",
                "traits.email",
                "traits.contact_email",
                "traits.phone",
                "traits.contact_phone",
                "traits.telephone",
                "traits.enterprise_number",
                "traits.kbo_number",
                "traits.nace_code",
                "traits.nace_codes",
                "traits.juridical_form",
            ],
        }
        return json.dumps(query, ensure_ascii=False)
