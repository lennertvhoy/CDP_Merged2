"""
TQL (Tracardi Query Language) Builder for CDP_Merged.
From CDPT - Working implementation with word-boundary NACE matching.
"""

import re

from src.search_engine.interfaces import QueryBuilder
from src.search_engine.schema import ProfileSearchParams


class TQLBuilder(QueryBuilder):
    """
    Tracardi Query Language (TQL) Builder.
    Preserves existing logic for polyglot city support, ID normalization.
    """

    def _normalize_kbo(self, kbo: str) -> list[str]:
        """Returns both raw and formatted versions."""
        clean = kbo.replace(".", "").replace(" ", "").strip()
        if len(clean) == 10 and clean.isdigit():
            dotted = f"{clean[:4]}.{clean[4:7]}.{clean[7:]}"
            return sorted({clean, dotted}, reverse=True)
        return [kbo]

    def _get_city_variants(self, city: str) -> list[str]:
        """Polyglot support: returns list of variants."""
        city_map = {
            "gent": ["Gent", "Gand", "Ghent"],
            "ghent": ["Gent", "Gand", "Ghent"],
            "gand": ["Gent", "Gand", "Ghent"],
            "antwerp": ["Antwerp", "Antwerpen", "Anvers"],
            "antwerpen": ["Antwerp", "Antwerpen", "Anvers"],
            "anvers": ["Antwerp", "Antwerpen", "Anvers"],
            "brussels": ["Brussels", "Brussel", "Bruxelles"],
            "brussel": ["Brussels", "Brussel", "Bruxelles"],
            "bruxelles": ["Brussels", "Brussel", "Bruxelles"],
            "liege": ["Liege", "Luik"],
            "luik": ["Liege", "Luik"],
            "namur": ["Namur", "Namen"],
            "namen": ["Namur", "Namen"],
            "sint-niklaas": ["Sint-Niklaas", "Saint-Nicolas"],
            "saint-nicolas": ["Sint-Niklaas", "Saint-Nicolas"],
        }
        key = city.lower()
        return city_map.get(key, [city])

    def _escape_tql_value(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"').strip()

    def _extract_keyword_tokens(self, keyword: str) -> list[str]:
        raw_tokens = re.findall(r"[A-Za-z0-9]+", keyword.lower())
        tokens: list[str] = []
        for token in raw_tokens:
            if len(token) < 3:
                continue
            if token not in tokens:
                tokens.append(token)
        return tokens[:4]

    def _build_lexical_name_search(self, keyword: str, lexical_operator: str = "CONSIST") -> str:
        escaped_keyword = self._escape_tql_value(keyword)
        if not escaped_keyword:
            return ""

        fields = ["traits.name", "traits.kbo_name"]
        operator = lexical_operator.strip().upper() or "CONSIST"
        # TQL uses == with wildcards for partial matching, not CONSIST
        if operator == "CONSIST":
            # Use == with wildcards for substring matching
            lexical_conditions = [f'{field} == "*{escaped_keyword}*"' for field in fields]
        else:
            lexical_conditions = [f'{field} == "{escaped_keyword}"' for field in fields]

        for token in self._extract_keyword_tokens(keyword):
            escaped_token = self._escape_tql_value(token)
            if escaped_token.lower() == escaped_keyword.lower():
                continue
            for field in fields:
                if operator == "CONSIST":
                    lexical_conditions.append(f'{field} == "*{escaped_token}*"')
                else:
                    lexical_conditions.append(f'{field} == "{escaped_token}"')

        unique_conditions: list[str] = []
        for condition in lexical_conditions:
            if condition not in unique_conditions:
                unique_conditions.append(condition)
        return f"({' OR '.join(unique_conditions)})"

    def build(self, params: ProfileSearchParams, *, lexical_operator: str = "CONSIST") -> str:
        """Build TQL query from ProfileSearchParams."""
        conditions = []

        # 1. Exact Matches - TQL uses = (single equals) for equality
        if params.city:
            variants = self._get_city_variants(params.city)
            city_conditions = [f'traits.city="{c}"' for c in variants]
            city_conditions.extend([f'traits.kbo_city="{c}"' for c in variants])
            conditions.append(f"({' OR '.join(city_conditions)})")

        if params.zip_code:
            conditions.append(f'traits.zip="{params.zip_code}"')

        if params.status:
            conditions.append(f'traits.status="{params.status}"')

        # 2. ID Logic (Format Fix) - TQL uses = (single equals)
        if params.enterprise_number:
            id_targets = self._normalize_kbo(params.enterprise_number)
            id_fields = ["id", "traits.enterprise_number", "traits.kbo_number"]

            id_conditions = []
            for val in id_targets:
                for field in id_fields:
                    id_conditions.append(f'{field}="{val}"')

            conditions.append(f"({' OR '.join(id_conditions)})")

        # 3. Array fields - TQL uses IN [...] for membership checks
        # Support both singular and plural field names for compatibility
        if params.nace_codes:
            codes_list = ", ".join([f'"{code}"' for code in params.nace_codes])
            # Use OR with both field names to handle data structure variations
            nace_condition_singular = f"traits.nace_code IN [{codes_list}]"
            nace_condition_plural = f"traits.nace_codes IN [{codes_list}]"
            conditions.append(f"({nace_condition_singular} OR {nace_condition_plural})")

        if params.juridical_codes:
            codes_list = ", ".join([f'"{code}"' for code in params.juridical_codes])
            conditions.append(f"traits.juridical_form IN [{codes_list}]")

        # 4. Date Math - TQL uses >= for range comparison
        if params.min_start_date:
            conditions.append(f'traits.start_date>="{params.min_start_date}"')

        # 5. Existence Checks - use EXISTS (correctly handled by Tracardi TQL)
        if params.has_phone:
            conditions.append("traits.phone EXISTS")
        if params.has_email:
            conditions.append("traits.email EXISTS")

        # 6. Name/Keyword Search (Smart Detection)
        if params.keywords:
            kw = params.keywords

            # Check for valid KBO/Enterprise number format
            clean_id = kw.replace(".", "").replace(" ", "").strip()
            is_valid_kbo = len(clean_id) == 10 and clean_id.isdigit()

            if is_valid_kbo:
                id_targets = self._normalize_kbo(kw)
                id_fields = ["id", "traits.enterprise_number", "traits.kbo_number"]
                id_conditions = []
                for val in id_targets:
                    for field in id_fields:
                        id_conditions.append(f'{field}="{val}"')

                conditions.append(f"({' OR '.join(id_conditions)})")
            else:
                lexical_condition = self._build_lexical_name_search(
                    kw, lexical_operator=lexical_operator
                )
                if lexical_condition:
                    conditions.append(lexical_condition)

        # 7. GHOST PROFILE FILTER
        searching_by_id = params.enterprise_number or (
            params.keywords
            and params.keywords.replace(".", "").replace(" ", "").isdigit()
            and len(params.keywords.replace(".", "").replace(" ", "")) == 10
        )

        if not searching_by_id:
            conditions.append("traits.name EXISTS")

        if not conditions:
            return "traits.name EXISTS"

        return " AND ".join(conditions)
