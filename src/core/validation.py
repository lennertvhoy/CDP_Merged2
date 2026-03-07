"""
Query Validation (Critic) for CDP_Merged.
Ported from CDP's ai_service/critic.py
Provides security validation for queries.
"""

import re

# Destructive SQL keywords that should never appear in SELECT queries
DESTRUCTIVE_KEYWORDS = {
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "REPLACE",
    "GRANT",
    "REVOKE",
    "EXECUTE",
    "EXEC",
}

# Allowed schemas/tables (whitelist)
ALLOWED_SCHEMAS = {"gold", "cdp", "public"}
ALLOWED_TABLES = {
    "gold.view_enterprise_analytics",
    "gold.dim_geography",
    "gold.dim_activity",
    "gold.dim_legal_form",
    "gold.fact_enterprises",
    "cdp.kbo_enterprises",
    "cdp.kbo_establishments",
    "cdp.kbo_activities",
    "cdp.profiles",
    "profiles",
}


def validate_query(query: str) -> dict:
    """
    Validate a query for security issues.

    Args:
        query: The query string to validate

    Returns:
        dict with:
            - valid: bool
            - error: str (if invalid)
            - warning: str (if warning)
            - flags: list of security flags
    """
    if not query:
        return {"valid": False, "error": "No query provided", "flags": ["empty_query"]}

    normalized_query = query.upper()
    security_flags = []

    # 1. Check for destructive commands
    for keyword in DESTRUCTIVE_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalized_query):
            security_flags.append("destructive_sql")
            return {
                "valid": False,
                "error": f"Security violation: Destructive command '{keyword}' detected",
                "flags": security_flags,
            }

    # 2. Check for unauthorized table access
    table_pattern = (
        r"(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*|[a-zA-Z_][a-zA-Z0-9_]*)"
    )
    tables_found = re.findall(table_pattern, query, re.IGNORECASE)

    for table in tables_found:
        table_lower = table.lower()
        schema = table_lower.split(".")[0] if "." in table_lower else None

        if table_lower not in ALLOWED_TABLES and schema not in ALLOWED_SCHEMAS:
            security_flags.append("unauthorized_table")
            return {
                "valid": False,
                "error": f"Security violation: Unauthorized table '{table}' accessed",
                "flags": security_flags,
            }

    # 3. Check for SQL injection patterns
    injection_patterns = [
        r"'\s*OR\s+'1'\s*=\s*'1",  # ' OR '1'='1'
        r";\s*DROP",  # ; DROP TABLE
        r"--",  # SQL comments
        r"/\*.*\*/",  # Block comments
    ]

    for pattern in injection_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            security_flags.append("sql_injection")
            return {
                "valid": False,
                "warning": "Potential SQL injection pattern detected",
                "flags": security_flags,
            }

    return {"valid": True, "flags": security_flags}


def validate_tql_query(query: str) -> dict:
    """
    Validate a TQL (Tracardi Query Language) query.
    TQL has simpler syntax than SQL but still needs validation.
    """
    if not query:
        return {"valid": False, "error": "No query provided", "flags": ["empty_query"]}

    # TQL-specific checks
    # 1. Check for obvious injection attempts
    dangerous_patterns = [
        r"\{\$",  # MongoDB operators
        r"\$where",
        r"__proto__",
        r"constructor",
    ]

    flags = []
    for pattern in dangerous_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            flags.append("suspicious_pattern")

    if flags:
        return {"valid": False, "error": "Query contains suspicious patterns", "flags": flags}

    return {"valid": True, "flags": flags}


def validate_grounded_response_citations(payload: dict, *, enforce_required: bool = False) -> dict:
    """Validate citation presence for grounded responses.

    Enforcement is intended to be feature-flagged by caller.
    """
    backend = str(payload.get("retrieval_backend") or "")
    citations = payload.get("citations") or []
    flags: list[str] = []

    if backend == "azure_ai_search" and enforce_required and len(citations) == 0:
        flags.append("missing_citations")
        return {
            "valid": False,
            "error": "Citation-required mode is enabled but no citations were produced.",
            "flags": flags,
        }

    return {"valid": True, "flags": flags}
