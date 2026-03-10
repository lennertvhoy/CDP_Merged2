"""Export Tools.

This module provides tools for exporting segment data to CSV and emailing exports.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from langchain_core.tools import tool

from src.core.logger import get_logger
from src.services.canonical_segments import CanonicalSegmentService
from src.services.postgresql_search import PostgreSQLSearchService
from src.services.resend import ResendClient
from src.services.tracardi import TracardiClient

logger = get_logger(__name__)


def _segment_field_mapping() -> dict[str, Callable[[dict[str, Any]], Any]]:
    return {
        "name": lambda p: (
            p.get("company_name")
            or p.get("traits", {}).get("name")
            or p.get("traits", {}).get("kbo_name")
            or ""
        ),
        "email": lambda p: (
            p.get("main_email")
            or p.get("traits", {}).get("email")
            or p.get("traits", {}).get("contact_email")
            or ""
        ),
        "phone": lambda p: (
            p.get("main_phone")
            or p.get("traits", {}).get("phone")
            or p.get("traits", {}).get("contact_phone")
            or ""
        ),
        "city": lambda p: (
            p.get("city")
            or p.get("traits", {}).get("city")
            or p.get("traits", {}).get("kbo_city")
            or ""
        ),
        "zip_code": lambda p: (
            p.get("postal_code")
            or p.get("traits", {}).get("zip_code")
            or p.get("traits", {}).get("kbo_zip_code")
            or ""
        ),
        "status": lambda p: p.get("status") or p.get("traits", {}).get("status") or "",
        "nace_code": lambda p: (
            p.get("industry_nace_code") or p.get("traits", {}).get("nace_code") or ""
        ),
        "juridical_form": lambda p: (
            p.get("legal_form")
            or p.get("traits", {}).get("juridical_form")
            or p.get("traits", {}).get("kbo_juridical_form")
            or ""
        ),
        "website": lambda p: (
            p.get("website_url")
            or p.get("traits", {}).get("website")
            or p.get("traits", {}).get("url")
            or ""
        ),
        "revenue": lambda p: (
            p.get("revenue_range") or p.get("traits", {}).get("revenue_eur") or ""
        ),
        "employees": lambda p: (
            p.get("employee_count") or p.get("traits", {}).get("employees") or ""
        ),
        "company_size": lambda p: (
            p.get("company_size") or p.get("traits", {}).get("company_size") or ""
        ),
        "founding_year": lambda p: (
            p.get("founding_year") or p.get("traits", {}).get("founding_year") or ""
        ),
    }


async def _load_segment_rows(
    segment_id: str,
    *,
    limit: int,
) -> tuple[list[dict], int, str, dict]:
    """Load segment rows from PostgreSQL first, then fall back to Tracardi.

    Returns:
        Tuple of (rows, total_count, backend, diagnostics)
    """
    diagnostics: dict[str, Any] = {
        "segment_id": segment_id,
        "postgresql_checked": False,
        "postgresql_count": 0,
        "segment_key": None,
        "definition_json": {},
        "tracardi_checked": False,
        "tracardi_count": 0,
        "errors": [],
    }

    # Try PostgreSQL first (canonical source)
    try:
        canonical_service = CanonicalSegmentService()
        canonical = await canonical_service.get_segment_members(segment_id, limit=limit)
        diagnostics["postgresql_checked"] = True
        if canonical is not None:
            pg_count = int(canonical["total_count"])
            diagnostics["postgresql_count"] = pg_count
            diagnostics["segment_key"] = canonical.get("segment_key")
            diagnostics["definition_json"] = canonical.get("definition_json") or {}
            if pg_count > 0:
                return canonical["rows"], pg_count, "postgresql", diagnostics
            # PostgreSQL has segment but it's empty - continue to check Tracardi
    except Exception as exc:
        diagnostics["postgresql_checked"] = True
        diagnostics["errors"].append(f"PostgreSQL lookup failed: {exc}")
        logger.warning(
            "canonical_segment_export_lookup_failed", segment=segment_id, error=str(exc)
        )

    # Fall back to Tracardi
    try:
        client = TracardiClient()
        query = f'segments="{segment_id}"'
        result = await client.search_profiles(query, limit=limit)
        diagnostics["tracardi_checked"] = True

        if result is None:
            diagnostics["errors"].append("Tracardi returned None - segment may not exist")
            raise RuntimeError(
                f"Segment '{segment_id}' not found in PostgreSQL or Tracardi. "
                f"Diagnostics: {diagnostics}"
            )

        tracardi_count = int(result.get("total", 0) or 0)
        diagnostics["tracardi_count"] = tracardi_count

        if tracardi_count == 0:
            # Both sources empty - provide helpful explanation
            pg_status = (
                f"PostgreSQL: {diagnostics['postgresql_count']} members"
                if diagnostics["postgresql_checked"]
                else "PostgreSQL: not checked"
            )
            raise RuntimeError(
                f"Segment '{segment_id}' exists but contains no members. "
                f"{pg_status}, Tracardi: 0 profiles. "
                f"The segment may need to be rebuilt or the search criteria may be too restrictive."
            )

        return result.get("result", []) or [], tracardi_count, "tracardi", diagnostics

    except RuntimeError:
        raise
    except Exception as exc:
        diagnostics["tracardi_checked"] = True
        diagnostics["errors"].append(f"Tracardi lookup failed: {exc}")
        raise RuntimeError(
            f"Failed to retrieve segment '{segment_id}' from any source. "
            f"Errors: {diagnostics['errors']}"
        ) from exc


def _row_matches_canonical_filters(
    row: dict[str, Any],
    filters: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Validate that an exported canonical row still satisfies the stored segment filters."""
    mismatches: list[str] = []

    keywords = (filters.get("keywords") or "").strip().lower()
    if keywords:
        company_name = str(row.get("company_name") or "").lower()
        if keywords not in company_name:
            mismatches.append("keywords")

    enterprise_number = (filters.get("enterprise_number") or "").strip()
    if enterprise_number:
        if str(row.get("kbo_number") or "") != enterprise_number:
            mismatches.append("enterprise_number")

    nace_codes = [str(code) for code in filters.get("nace_codes") or [] if code]
    if nace_codes:
        row_codes = {
            str(code)
            for code in [
                row.get("industry_nace_code"),
                *(row.get("all_nace_codes") or []),
            ]
            if code
        }
        if not row_codes.intersection(nace_codes):
            mismatches.append("nace_codes")

    city = (filters.get("city") or "").strip()
    if city:
        row_city = str(row.get("city") or "")
        if row_city not in PostgreSQLSearchService._city_candidates(city):
            mismatches.append("city")

    zip_code = (filters.get("zip_code") or "").strip()
    if zip_code and str(row.get("postal_code") or "") != zip_code:
        mismatches.append("zip_code")

    status = PostgreSQLSearchService._normalize_status_filter(filters.get("status"))
    if status and str(row.get("status") or "").upper() != status:
        mismatches.append("status")

    has_phone = filters.get("has_phone")
    if has_phone is True and not str(row.get("main_phone") or "").strip():
        mismatches.append("has_phone")

    has_email = filters.get("has_email")
    if has_email is True and not str(row.get("main_email") or "").strip():
        mismatches.append("has_email")

    email_domain = PostgreSQLSearchService._normalize_email_domain(filters.get("email_domain"))
    if email_domain:
        row_email = str(row.get("main_email") or "").strip().lower()
        if not row_email.endswith(f"@{email_domain}"):
            mismatches.append("email_domain")

    return not mismatches, mismatches


def _validate_canonical_segment_rows(
    rows: list[dict[str, Any]],
    definition_json: dict[str, Any] | None,
) -> dict[str, Any]:
    """Check exported canonical rows against stored segment metadata filters."""
    filters = (definition_json or {}).get("filters") or {}
    if not filters:
        return {"validated": False, "checked_rows": 0, "invalid_rows": 0, "filters": {}}

    invalid_rows: list[dict[str, Any]] = []
    for row in rows:
        matches, mismatches = _row_matches_canonical_filters(row, filters)
        if not matches:
            invalid_rows.append(
                {
                    "company_name": row.get("company_name"),
                    "kbo_number": row.get("kbo_number"),
                    "failed_filters": mismatches,
                }
            )

    return {
        "validated": True,
        "checked_rows": len(rows),
        "invalid_rows": len(invalid_rows),
        "filters": filters,
        "sample_invalid_rows": invalid_rows[:5],
    }


@tool
async def export_segment_to_csv(
    segment_id: str,
    include_fields: list[str] | None = None,
    max_records: int = 10000,
) -> str:
    """Export a segment to CSV for download.

    Use for: Data exports, reporting, external analysis, backup.

    Args:
        segment_id: The segment name/ID to export.
        include_fields: List of fields to include. Defaults to common fields.
            Available: name, email, phone, city, zip_code, status,
                      nace_code, juridical_form, revenue, employees, website
        max_records: Maximum records to export (default 10000).

    Returns:
        JSON string with download URL and export statistics.
    """
    import tempfile

    # Default fields if not specified
    if not include_fields:
        include_fields = [
            "name",
            "email",
            "phone",
            "city",
            "zip_code",
            "status",
            "nace_code",
            "juridical_form",
            "website",
        ]

    logger.info("csv_export_start", segment=segment_id, fields=include_fields)

    try:
        profiles, total_count, backend, diagnostics = await _load_segment_rows(
            segment_id, limit=max_records
        )
    except RuntimeError as exc:
        error_msg = str(exc)
        logger.error("csv_export_failed", segment=segment_id, error=error_msg)
        return json.dumps(
            {
                "status": "error",
                "error": error_msg,
                "segment_id": segment_id,
                "suggestions": [
                    "Verify the segment name is correct",
                    "Check if the segment has any members with: get_segment_stats",
                    "Try recreating the segment if it was deleted",
                    "Check if PostgreSQL and Tracardi are both accessible",
                ],
            },
            ensure_ascii=False,
        )

    if not profiles:
        return json.dumps(
            {
                "status": "ok",
                "segment_id": segment_id,
                "exported_count": 0,
                "message": "Segment exists but contains no profiles to export.",
                "backend": backend,
                "diagnostics": diagnostics,
                "suggestions": [
                    "The segment search criteria may be too restrictive",
                    "Try broadening your search filters",
                    "Check if companies in the segment have the requested fields",
                ],
            },
            ensure_ascii=False,
        )

    validation_summary: dict[str, Any] | None = None
    if backend == "postgresql":
        validation_summary = _validate_canonical_segment_rows(
            profiles,
            diagnostics.get("definition_json"),
        )
        if validation_summary.get("validated") and validation_summary.get("invalid_rows", 0) > 0:
            error_msg = (
                f"Export aborted: canonical segment '{segment_id}' has "
                f"{validation_summary['invalid_rows']} row(s) that do not satisfy the stored filters."
            )
            logger.error(
                "csv_export_validation_failed",
                segment=segment_id,
                invalid_rows=validation_summary["invalid_rows"],
            )
            return json.dumps(
                {
                    "status": "error",
                    "error": error_msg,
                    "segment_id": segment_id,
                    "backend": backend,
                    "validation": validation_summary,
                    "suggestions": [
                        "Rebuild the canonical segment from the current search filters",
                        "Inspect the stored segment definition and member rows for drift",
                        "Do not use this export as demo evidence until the mismatch is resolved",
                    ],
                },
                ensure_ascii=False,
            )

    # Create CSV file
    export_dir = Path(tempfile.gettempdir()) / "cdp_exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"{segment_id}_{timestamp}.csv"
    filepath = export_dir / filename

    field_mapping = _segment_field_mapping()

    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=include_fields)
            writer.writeheader()

            for profile in profiles:
                row = {}
                for field in include_fields:
                    extractor = field_mapping.get(field, lambda p: "")
                    value = extractor(profile)
                    row[field] = value if value is not None else ""
                writer.writerow(row)

        # Generate download URL
        # In production, this would be a signed URL to blob storage
        download_url = f"/api/exports/download/{filename}"

        logger.info(
            "csv_export_complete",
            segment=segment_id,
            filename=filename,
            count=len(profiles),
            backend=backend,
        )

        return json.dumps(
            {
                "status": "ok",
                "segment_id": segment_id,
                "exported_count": len(profiles),
                "total_in_segment": total_count,
                "filename": filename,
                "download_url": download_url,
                "fields_included": include_fields,
                "expires_in_hours": 24,
                "backend": backend,
                "validation": validation_summary,
            },
            ensure_ascii=False,
        )

    except (OSError, csv.Error) as exc:
        logger.error("csv_export_failed", segment=segment_id, error=str(exc))
        return json.dumps(
            {"status": "error", "error": f"Export failed: {exc}"},
            ensure_ascii=False,
        )


@tool
async def email_segment_export(
    segment_id: str,
    email_address: str,
    include_fields: list[str] | None = None,
    message: str | None = None,
) -> str:
    """Email a CSV export of a segment to a user.

    Use for: Sharing segment data, scheduled reports, team collaboration.

    Args:
        segment_id: The segment name/ID to export.
        email_address: Recipient email address.
        include_fields: List of fields to include (see export_segment_to_csv).
        message: Optional custom message to include in the email.

    Returns:
        Success message with export details or error message.
    """
    # First generate the CSV export
    export_result = await export_segment_to_csv.ainvoke(  # type: ignore[attr-defined]
        {
            "segment_id": segment_id,
            "include_fields": include_fields,
        }
    )
    export_data = json.loads(export_result)

    if export_data.get("status") != "ok":
        return f"Failed to export segment: {export_data.get('error', 'Unknown error')}"

    exported_count = export_data.get("exported_count", 0)
    filename = export_data.get("filename", "export.csv")

    # Send email with Resend
    client = ResendClient()

    subject = f"CDP Export: {segment_id} ({exported_count} records)"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>Your Segment Export is Ready</h2>

        <p>Hello,</p>

        <p>Your export for segment <strong>"{segment_id}"</strong> has been generated.</p>

        <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Export Details:</h3>
            <ul>
                <li><strong>Records exported:</strong> {exported_count}</li>
                <li><strong>Filename:</strong> {filename}</li>
                <li><strong>Fields included:</strong> {", ".join(export_data.get("fields_included", []))}</li>
            </ul>
        </div>

        {f"<p><strong>Message:</strong> {message}</p>" if message else ""}

        <p>You can download your export using the link below:</p>

        <p>
            <a href="{export_data.get("download_url", "#")}"
               style="background: #007bff; color: white; padding: 10px 20px;
                      text-decoration: none; border-radius: 5px; display: inline-block;">
                Download CSV Export
            </a>
        </p>

        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            This link expires in 24 hours. The export includes {exported_count} records
            from segment "{segment_id}".
        </p>
    </body>
    </html>
    """

    try:
        result = await client.send_email(
            to=email_address,
            subject=subject,
            html=html_content,
        )

        message_id = result.get("id", "unknown")

        logger.info(
            "segment_export_email_sent",
            segment=segment_id,
            to=email_address,
            count=exported_count,
            message_id=message_id,
        )

        return (
            f"Export of {exported_count} records from segment '{segment_id}' "
            f"has been emailed to {email_address}. Message ID: {message_id}"
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "segment_export_email_http_error",
            segment=segment_id,
            to=email_address,
            status_code=exc.response.status_code,
        )
        return f"Export generated but email failed: HTTP {exc.response.status_code}"
    except httpx.RequestError as exc:
        logger.error(
            "segment_export_email_request_error",
            segment=segment_id,
            to=email_address,
            error=str(exc),
        )
        return f"Export generated but email failed: {exc}"


__all__ = [
    "export_segment_to_csv",
    "email_segment_export",
]
