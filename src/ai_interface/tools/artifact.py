"""Local artifact tools for analysis reports and spreadsheet-compatible exports."""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from src.ai_interface.tools.nace_resolver import _get_nace_codes_from_keyword
from src.core.logger import get_logger
from src.services.postgresql_search import CompanySearchFilters, get_search_service

logger = get_logger(__name__)

ARTIFACT_ROOT = Path("output") / "agent_artifacts"


def _get_base_url() -> str:
    """Get the base URL for download links.

    For local deployment, uses CHAINLIT_URL or falls back to localhost:8000.
    For Azure deployment, this can be extended to use the deployed URL.
    """
    # Check for explicitly configured base URL
    base_url = os.getenv("CHAINLIT_URL", "").rstrip("/")
    if base_url:
        return base_url

    # Default to localhost for local development
    port = os.getenv("CHAINLIT_PORT", "8000")
    return f"http://localhost:{port}"


SEARCH_RESULT_FIELDS = [
    "kbo_number",
    "company_name",
    "city",
    "postal_code",
    "status",
    "industry_nace_code",
    "legal_form",
    "main_email",
    "main_phone",
    "website_url",
]
AGGREGATION_FIELDS = [
    "group_value",
    "count",
    "email_coverage_percent",
    "phone_coverage_percent",
    "percent_of_total",
]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-") or "artifact"


def _normalize_email_domain(email_domain: str | None) -> str | None:
    if not email_domain:
        return None

    normalized = email_domain.strip().lower()
    if normalized.startswith("@"):
        normalized = normalized[1:]
    if "@" in normalized:
        normalized = normalized.split("@", 1)[1]
    return normalized or None


def _build_filters(
    *,
    keywords: str | None,
    nace_codes: list[str] | None,
    nace_code: str | None,
    juridical_codes: list[str] | None,
    city: str | None,
    zip_code: str | None,
    status: str | None,
    min_start_date: str | None,
    has_phone: bool | None,
    has_email: bool | None,
    email_domain: str | None,
    max_rows: int,
) -> tuple[CompanySearchFilters, list[str]]:
    resolved_nace_codes = list(nace_codes or [])
    if nace_code:
        single_code = nace_code.strip()
        if single_code and single_code not in resolved_nace_codes:
            resolved_nace_codes.insert(0, single_code)

    search_keyword = keywords
    if keywords and not resolved_nace_codes:
        mapped_codes = _get_nace_codes_from_keyword(keywords)
        if mapped_codes:
            resolved_nace_codes = mapped_codes
            search_keyword = None

    filters = CompanySearchFilters(
        keywords=search_keyword,
        enterprise_number=None,
        nace_codes=resolved_nace_codes or None,
        juridical_codes=juridical_codes,
        city=city,
        zip_code=zip_code,
        status=status,
        min_start_date=min_start_date,
        has_phone=has_phone,
        has_email=has_email,
        email_domain=_normalize_email_domain(email_domain),
        limit=max(1, min(max_rows, 1000)),
        offset=0,
    )
    return filters, resolved_nace_codes


def _artifact_path(title: str, output_format: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    return ARTIFACT_ROOT / f"{_slugify(title)}_{timestamp}.{output_format}"


def _build_download_url(filename: str) -> str:
    """Build the download URL for an artifact file.

    Args:
        filename: The artifact filename (not full path)

    Returns:
        Full URL to download the artifact via the /download/artifacts endpoint
    """
    base_url = _get_base_url()
    return f"{base_url}/download/artifacts/{filename}"


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _markdown_table(rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
    if not rows:
        return "_No rows available._"

    def escape(value: Any) -> str:
        return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")

    header = "| " + " | ".join(fieldnames) + " |"
    divider = "| " + " | ".join(["---"] * len(fieldnames)) + " |"
    body = [
        "| " + " | ".join(escape(row.get(field, "")) for field in fieldnames) + " |"
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def _coverage_rows(coverage: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field_name, metrics in coverage.items():
        rows.append(
            {
                "field": field_name,
                "count": metrics.get("count", 0),
                "percent": metrics.get("percent", 0),
            }
        )
    return rows


@tool
async def create_data_artifact(
    title: str,
    artifact_type: str,
    output_format: str = "markdown",
    use_last_search: bool = False,
    keywords: str | None = None,
    city: str | None = None,
    zip_code: str | None = None,
    status: str | None = None,
    nace_codes: list[str] | None = None,
    nace_code: str | None = None,
    juridical_codes: list[str] | None = None,
    min_start_date: str | None = None,
    has_phone: bool | None = None,
    has_email: bool | None = None,
    email_domain: str | None = None,
    group_by: str | None = None,
    max_rows: int = 200,
) -> str:
    """Create a local document or spreadsheet-compatible artifact from query-plane data.

    Use this for local reports and exports:
    - `artifact_type="search_results"` with `output_format="csv"` for spreadsheets
    - `artifact_type="aggregation"` with `group_by="city"` for analysis summaries
    - `artifact_type="coverage_report"` for overall local data-quality diagnostics

    Args:
        title: Human-readable title used in the filename and report heading.
        artifact_type: One of `search_results`, `aggregation`, or `coverage_report`.
        output_format: One of `markdown`, `csv`, or `json`.
        use_last_search: When true, tools_node may inject the previous search filters.
        keywords: Optional activity keyword. Auto-resolved to NACE codes when possible.
        city: Optional city filter.
        zip_code: Optional postal-code filter.
        status: Optional company status filter.
        nace_codes: Optional list of NACE codes.
        nace_code: Optional single NACE code alias.
        juridical_codes: Optional list of juridical form codes.
        min_start_date: Optional founded-date lower bound.
        has_phone: Optional phone-coverage filter.
        has_email: Optional email-coverage filter.
        email_domain: Optional email-domain filter.
        group_by: Required when `artifact_type="aggregation"`.
        max_rows: Maximum result rows or groups to include.

    Returns:
        JSON string with artifact metadata and the local file path.
    """
    valid_artifact_types = {"search_results", "aggregation", "coverage_report"}
    valid_output_formats = {"markdown", "csv", "json"}

    if artifact_type not in valid_artifact_types:
        return json.dumps(
            {
                "status": "error",
                "error": (
                    f"Invalid artifact_type '{artifact_type}'. "
                    f"Valid options: {', '.join(sorted(valid_artifact_types))}"
                ),
            },
            ensure_ascii=False,
        )

    if output_format not in valid_output_formats:
        return json.dumps(
            {
                "status": "error",
                "error": (
                    f"Invalid output_format '{output_format}'. "
                    f"Valid options: {', '.join(sorted(valid_output_formats))}"
                ),
            },
            ensure_ascii=False,
        )

    if artifact_type == "aggregation" and not group_by:
        return json.dumps(
            {
                "status": "error",
                "error": "group_by is required when artifact_type='aggregation'.",
            },
            ensure_ascii=False,
        )

    if artifact_type != "coverage_report":
        has_explicit_filters = any(
            [
                keywords,
                city,
                zip_code,
                status,
                nace_codes,
                nace_code,
                juridical_codes,
                min_start_date,
                bool(has_phone),
                bool(has_email),
                email_domain,
            ]
        )
        if not has_explicit_filters and not use_last_search:
            return json.dumps(
                {
                    "status": "error",
                    "error": (
                        "Provide filters or set use_last_search=true after a search before "
                        "creating an artifact."
                    ),
                },
                ensure_ascii=False,
            )

    search_service = get_search_service()
    path = _artifact_path(title=title, output_format=output_format)

    try:
        metadata: dict[str, Any] = {
            "title": title,
            "artifact_type": artifact_type,
            "output_format": output_format,
            "artifact_path": str(path.resolve()),
            "artifact_relative_path": str(path),
            "spreadsheet_compatible": output_format == "csv",
            "download_url": _build_download_url(path.name),
            "filename": path.name,
        }

        if artifact_type == "coverage_report":
            coverage_result = await search_service.get_coverage_stats()
            rows = _coverage_rows(coverage_result.get("coverage", {}))
            metadata["total_companies"] = coverage_result.get("total_companies", 0)

            if output_format == "json":
                path.write_text(json.dumps(coverage_result, indent=2, ensure_ascii=False), "utf-8")
            elif output_format == "csv":
                _write_csv(path, rows, ["field", "count", "percent"])
            else:
                markdown = "\n".join(
                    [
                        f"# {title}",
                        "",
                        f"- Total companies: {coverage_result.get('total_companies', 0)}",
                        f"- Backend: {coverage_result.get('backend', 'postgresql')}",
                        "",
                        _markdown_table(rows, ["field", "count", "percent"]),
                    ]
                )
                path.write_text(markdown, encoding="utf-8")

            metadata["row_count"] = len(rows)
            return json.dumps({"status": "ok", **metadata}, ensure_ascii=False)

        filters, resolved_nace_codes = _build_filters(
            keywords=keywords,
            nace_codes=nace_codes,
            nace_code=nace_code,
            juridical_codes=juridical_codes,
            city=city,
            zip_code=zip_code,
            status=status,
            min_start_date=min_start_date,
            has_phone=has_phone,
            has_email=has_email,
            email_domain=email_domain,
            max_rows=max_rows,
        )
        metadata["applied_filters"] = {
            "keywords": filters.keywords,
            "city": filters.city,
            "zip_code": filters.zip_code,
            "status": filters.status,
            "nace_codes": resolved_nace_codes,
            "juridical_codes": filters.juridical_codes or [],
            "min_start_date": filters.min_start_date,
            "has_phone": bool(filters.has_phone),
            "has_email": bool(filters.has_email),
            "email_domain": filters.email_domain,
            "use_last_search": use_last_search,
        }

        if artifact_type == "search_results":
            result = await search_service.search_companies(filters)
            rows = result.get("result", []) or []
            metadata["authoritative_total"] = int(result.get("total", 0) or 0)
            metadata["row_count"] = len(rows)

            if output_format == "json":
                path.write_text(json.dumps(result, indent=2, ensure_ascii=False), "utf-8")
            elif output_format == "csv":
                _write_csv(path, rows, SEARCH_RESULT_FIELDS)
            else:
                preview_rows = rows[:20]
                markdown = "\n".join(
                    [
                        f"# {title}",
                        "",
                        f"- Authoritative total: {metadata['authoritative_total']}",
                        f"- Rows exported: {len(rows)}",
                        "",
                        _markdown_table(preview_rows, SEARCH_RESULT_FIELDS),
                    ]
                )
                path.write_text(markdown, encoding="utf-8")

            return json.dumps({"status": "ok", **metadata}, ensure_ascii=False)

        aggregation_result = await search_service.aggregate_by_field(
            group_by=group_by or "city",
            filters=filters,
            limit=max(1, min(max_rows, 200)),
        )
        groups = aggregation_result.get("groups", []) or []
        metadata["group_by"] = aggregation_result.get("group_by", group_by)
        metadata["total_matching_profiles"] = aggregation_result.get("total_matching_profiles", 0)
        metadata["row_count"] = len(groups)

        if output_format == "json":
            path.write_text(json.dumps(aggregation_result, indent=2, ensure_ascii=False), "utf-8")
        elif output_format == "csv":
            _write_csv(path, groups, AGGREGATION_FIELDS)
        else:
            preview_groups = groups[:20]
            markdown = "\n".join(
                [
                    f"# {title}",
                    "",
                    f"- Group by: {metadata['group_by']}",
                    f"- Total matching profiles: {metadata['total_matching_profiles']}",
                    "",
                    _markdown_table(preview_groups, AGGREGATION_FIELDS),
                ]
            )
            path.write_text(markdown, encoding="utf-8")

        return json.dumps({"status": "ok", **metadata}, ensure_ascii=False)

    except Exception as exc:
        logger.error(
            "create_data_artifact_failed",
            artifact_type=artifact_type,
            output_format=output_format,
            error=str(exc),
        )
        return json.dumps(
            {
                "status": "error",
                "error": f"Failed to create artifact: {exc}",
            },
            ensure_ascii=False,
        )


__all__ = ["create_data_artifact", "ARTIFACT_ROOT"]
