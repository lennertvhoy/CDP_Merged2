"""Export Tools.

This module provides tools for exporting segment data to CSV and emailing exports.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from langchain_core.tools import tool

from src.core.logger import get_logger
from src.services.resend import ResendClient
from src.services.tracardi import TracardiClient

logger = get_logger(__name__)


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

    client = TracardiClient()

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

    # Fetch all profiles in segment
    query = f'segments="{segment_id}"'
    result = await client.search_profiles(query, limit=max_records)

    if not result:
        return json.dumps(
            {"status": "error", "error": "Failed to retrieve segment data."},
            ensure_ascii=False,
        )

    profiles = result.get("result", []) or []
    total_count = int(result.get("total", 0) or 0)

    if not profiles:
        return json.dumps(
            {
                "status": "ok",
                "segment_id": segment_id,
                "exported_count": 0,
                "message": "Segment contains no profiles to export.",
            },
            ensure_ascii=False,
        )

    # Create CSV file
    export_dir = Path(tempfile.gettempdir()) / "cdp_exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"{segment_id}_{timestamp}.csv"
    filepath = export_dir / filename

    # Map field names to profile paths
    field_mapping = {
        "name": lambda p: (
            p.get("traits", {}).get("name") or p.get("traits", {}).get("kbo_name") or ""
        ),
        "email": lambda p: (
            p.get("traits", {}).get("email") or p.get("traits", {}).get("contact_email") or ""
        ),
        "phone": lambda p: (
            p.get("traits", {}).get("phone") or p.get("traits", {}).get("contact_phone") or ""
        ),
        "city": lambda p: (
            p.get("traits", {}).get("city") or p.get("traits", {}).get("kbo_city") or ""
        ),
        "zip_code": lambda p: (
            p.get("traits", {}).get("zip_code") or p.get("traits", {}).get("kbo_zip_code") or ""
        ),
        "status": lambda p: p.get("traits", {}).get("status") or "",
        "nace_code": lambda p: p.get("traits", {}).get("nace_code") or "",
        "juridical_form": lambda p: (
            p.get("traits", {}).get("juridical_form")
            or p.get("traits", {}).get("kbo_juridical_form")
            or ""
        ),
        "website": lambda p: (
            p.get("traits", {}).get("website") or p.get("traits", {}).get("url") or ""
        ),
        "revenue": lambda p: p.get("traits", {}).get("revenue_eur") or "",
        "employees": lambda p: p.get("traits", {}).get("employees") or "",
        "company_size": lambda p: p.get("traits", {}).get("company_size") or "",
        "founding_year": lambda p: p.get("traits", {}).get("founding_year") or "",
    }

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
