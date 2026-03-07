"""
SQL Query Builder for CDP_Merged.
From CDPT - For potential PostgreSQL backend support.
"""

from src.search_engine.interfaces import QueryBuilder
from src.search_engine.schema import ProfileSearchParams


class SQLBuilder(QueryBuilder):
    """SQL query builder for PostgreSQL backend."""

    def build(self, params: ProfileSearchParams) -> str:
        """
        Build SQL query from ProfileSearchParams.

        DEPRECATED: This method uses string formatting and is vulnerable to SQL injection.
        Use build_parametrized() instead for user-provided input.
        """
        conditions = []

        if params.city:
            conditions.append(f"city ILIKE '{params.city}'")

        if params.zip_code:
            conditions.append(f"zip_code = '{params.zip_code}'")

        if params.status:
            conditions.append(f"status = '{params.status}'")

        if params.enterprise_number:
            clean = params.enterprise_number.replace(".", "").replace(" ", "")
            conditions.append(f"enterprise_number = '{clean}'")

        if params.nace_codes:
            codes = ", ".join([f"'{c}'" for c in params.nace_codes])
            conditions.append(f"nace_code IN ({codes})")

        if params.juridical_codes:
            codes = ", ".join([f"'{c}'" for c in params.juridical_codes])
            conditions.append(f"juridical_form IN ({codes})")

        if params.min_start_date:
            conditions.append(f"start_date >= '{params.min_start_date}'")

        if params.has_phone:
            conditions.append("phone IS NOT NULL AND phone != ''")

        if params.has_email:
            conditions.append("email IS NOT NULL AND email != ''")

        if params.keywords:
            conditions.append(f"name ILIKE '%{params.keywords}%'")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        return f"""  # nosec
SELECT *
FROM profiles
WHERE {where_clause}
LIMIT 100
""".strip()

    def build_parametrized(self, params: ProfileSearchParams) -> tuple[str, tuple]:
        """
        Build a parameterized SQL query with separate parameters to prevent SQL injection.

        Returns:
            Tuple of (sql_query_with_placeholders, parameter_tuple)
            Usage: cursor.execute(sql, params)
        """
        conditions = []
        query_params = []
        param_idx = 0

        def next_param():
            nonlocal param_idx
            param_idx += 1
            return f"${param_idx}"

        if params.city:
            conditions.append(f"city ILIKE {next_param()}")
            query_params.append(f"%{params.city}%")

        if params.zip_code:
            conditions.append(f"zip_code = {next_param()}")
            query_params.append(params.zip_code)

        if params.status:
            conditions.append(f"status = {next_param()}")
            query_params.append(params.status)

        if params.enterprise_number:
            clean = params.enterprise_number.replace(".", "").replace(" ", "")
            conditions.append(f"enterprise_number = {next_param()}")
            query_params.append(clean)

        if params.nace_codes:
            # For IN clauses, we need to expand placeholders
            placeholders = ", ".join([next_param() for _ in params.nace_codes])
            conditions.append(f"nace_code IN ({placeholders})")
            query_params.extend(params.nace_codes)

        if params.juridical_codes:
            placeholders = ", ".join([next_param() for _ in params.juridical_codes])
            conditions.append(f"juridical_form IN ({placeholders})")
            query_params.extend(params.juridical_codes)

        if params.min_start_date:
            conditions.append(f"start_date >= {next_param()}")
            query_params.append(params.min_start_date)

        if params.has_phone:
            conditions.append("phone IS NOT NULL AND phone != ''")

        if params.has_email:
            conditions.append("email IS NOT NULL AND email != ''")

        if params.keywords:
            conditions.append(f"name ILIKE {next_param()}")
            query_params.append(f"%{params.keywords}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        sql = f"""  # nosec
SELECT *
FROM profiles
WHERE {where_clause}
LIMIT 100
""".strip()

        return sql, tuple(query_params)
