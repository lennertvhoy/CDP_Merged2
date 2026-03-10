"""Email Marketing Tools.

This module provides tools for email marketing via Flexmail and Resend.
"""

from __future__ import annotations

import json

import httpx
from langchain_core.tools import tool

from src.core.logger import get_logger
from src.services.canonical_segments import CanonicalSegmentService
from src.services.flexmail import FlexmailClient
from src.services.resend import ResendClient
from src.services.tracardi import TracardiClient

logger = get_logger(__name__)


async def _load_segment_contacts(
    segment_id: str,
    *,
    limit: int = 1000,
) -> tuple[list[dict], int, str, dict]:
    """Load contact-capable segment rows from PostgreSQL first, then Tracardi.

    Returns:
        Tuple of (profiles, total_count, backend, diagnostics)
    """
    diagnostics = {
        "segment_id": segment_id,
        "postgresql_checked": False,
        "postgresql_count": 0,
        "tracardi_checked": False,
        "tracardi_count": 0,
        "profiles_with_email": 0,
        "errors": [],
    }

    # Try PostgreSQL first
    try:
        canonical_service = CanonicalSegmentService()
        canonical = await canonical_service.get_segment_members(segment_id, limit=limit)
        diagnostics["postgresql_checked"] = True
        if canonical is not None:
            pg_count = int(canonical["total_count"])
            diagnostics["postgresql_count"] = pg_count
            if pg_count > 0:
                return canonical["rows"], pg_count, "postgresql", diagnostics
            # Empty in PostgreSQL - check Tracardi
    except Exception as exc:
        diagnostics["postgresql_checked"] = True
        diagnostics["errors"].append(f"PostgreSQL: {exc}")
        logger.warning("canonical_segment_contact_lookup_failed", segment=segment_id, error=str(exc))

    # Fall back to Tracardi
    try:
        tracardi = TracardiClient()
        query = f'segments="{segment_id}"'
        search_res = await tracardi.search_profiles(query, limit=limit)
        diagnostics["tracardi_checked"] = True

        if not search_res:
            diagnostics["errors"].append("Tracardi: No response or segment not found")
            raise RuntimeError(
                f"Segment '{segment_id}' not found in PostgreSQL or Tracardi. "
                f"PostgreSQL count: {diagnostics['postgresql_count']}, "
                f"Tracardi: no response"
            )

        profiles = search_res.get("result", []) if search_res else []
        tracardi_count = len(profiles)
        diagnostics["tracardi_count"] = tracardi_count

        # Count profiles with emails
        for p in profiles:
            if _extract_segment_email(p):
                diagnostics["profiles_with_email"] += 1

        if tracardi_count == 0:
            raise RuntimeError(
                f"Segment '{segment_id}' exists but is empty in both sources. "
                f"PostgreSQL: {diagnostics['postgresql_count']}, "
                f"Tracardi: 0 profiles"
            )

        return profiles, tracardi_count, "tracardi", diagnostics

    except RuntimeError:
        raise
    except Exception as exc:
        diagnostics["tracardi_checked"] = True
        diagnostics["errors"].append(f"Tracardi: {exc}")
        raise RuntimeError(
            f"Failed to retrieve segment '{segment_id}' from any source. "
            f"Errors: {'; '.join(diagnostics['errors'])}"
        )


def _extract_segment_email(profile: dict) -> str | None:
    traits = profile.get("traits") or profile.get("data", {}).get("properties", {})
    email = (
        profile.get("main_email")
        or traits.get("email")
        or traits.get("contact_email")
    )
    if not email and "@" in profile.get("id", ""):
        email = profile["id"]
    return email


def _extract_segment_name(profile: dict) -> str:
    traits = profile.get("traits") or profile.get("data", {}).get("properties", {})
    return profile.get("company_name") or traits.get("name") or traits.get("kbo_name") or ""


@tool
async def push_to_flexmail(segment_id: str) -> str:
    """Push a Tracardi segment to Flexmail for email marketing.

    Args:
        segment_id: The segment name/ID to push.

    Returns:
        Success message with count of contacts pushed.
    """
    flexmail = FlexmailClient()
    logger.info("flexmail_push_start", segment=segment_id)
    try:
        profiles_to_push, total_count, backend, _diagnostics = await _load_segment_contacts(segment_id)
    except RuntimeError:
        return f"Failed to retrieve segment '{segment_id}' for Flexmail push."

    # Find 'tracardi_segment' custom field
    custom_fields = await flexmail.get_custom_fields()
    segment_field_id: str | None = next(
        (
            f.get("id")
            for f in custom_fields
            if f.get("label") == "tracardi_segment" or f.get("variable") == "tracardi_segment"
        ),
        None,
    )
    if not segment_field_id:
        logger.warning("flexmail_segment_field_not_found")

    # Get 'Tracardi' interest or first available
    interests = await flexmail.get_interests()
    tracardi_interest = next(
        (i for i in interests if i.get("name", "").lower() == "tracardi"),
        interests[0] if interests else None,
    )
    interest_id = tracardi_interest["id"] if tracardi_interest else None

    pushed_count = 0
    for p in profiles_to_push:
        email = _extract_segment_email(p)
        if not email:
            continue

        name = _extract_segment_name(p) or "Unknown"
        cf_payload = {segment_field_id: segment_id} if segment_field_id else {}
        contact = await flexmail.create_contact(email, name, custom_fields=cf_payload or None)

        if contact and "id" in contact:
            if cf_payload:
                await flexmail.update_contact(str(contact["id"]), {"custom_fields": cf_payload})
            if interest_id:
                await flexmail.add_contact_to_interest(str(contact["id"]), str(interest_id))
            pushed_count += 1

    interest_name = tracardi_interest["name"] if tracardi_interest else "None"
    logger.info(
        "flexmail_push_complete",
        segment=segment_id,
        pushed=pushed_count,
        backend=backend,
    )
    suffix = ""
    if total_count > len(profiles_to_push):
        suffix = f" Loaded {len(profiles_to_push)} of {total_count} total members in this run."
    return (
        f"Pushed {pushed_count} profiles to Flexmail. Target Interest: {interest_name}."
        f"{suffix}"
    )


@tool
async def send_email_via_resend(
    to: str, subject: str, html_content: str, from_email: str | None = None
) -> str:
    """Send a single email via Resend.

    Use for: One-off emails, test sends, notifications, transactional emails.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_content: HTML content of the email.
        from_email: Optional sender email (defaults to configured from_email).

    Returns:
        Success message with message ID or error message.
    """
    client = ResendClient()
    try:
        result = await client.send_email(
            to=to,
            subject=subject,
            html=html_content,
            from_email=from_email,
        )
        message_id = result.get("id", "unknown")
        logger.info("resend_email_tool_success", to=to, message_id=message_id)
        return f"Email sent successfully via Resend. Message ID: {message_id}"
    except httpx.HTTPStatusError as exc:
        logger.error("resend_email_tool_http_error", to=to, status_code=exc.response.status_code)
        return f"Failed to send email via Resend: HTTP {exc.response.status_code}"
    except httpx.RequestError as exc:
        logger.error("resend_email_tool_request_error", to=to, error=str(exc))
        return f"Failed to send email via Resend: Request error - {exc}"


@tool
async def send_bulk_emails_via_resend(
    recipients: list[str], subject: str, html_content: str
) -> str:
    """Send bulk emails to a list of recipients via Resend.

    Use for: Campaigns without creating an audience first, bulk notifications.
    Note: For campaigns to existing audiences, use send_campaign_via_resend instead.

    Args:
        recipients: List of recipient email addresses.
        subject: Email subject line.
        html_content: HTML content of the email.

    Returns:
        Success message with count or error message.
    """
    if not recipients:
        return "No recipients provided."

    client = ResendClient()
    try:
        result = await client.send_bulk_emails(
            recipients=recipients,
            subject=subject,
            html=html_content,
        )
        sent_count = len(result.get("data", []))
        logger.info(
            "resend_bulk_email_tool_success",
            recipient_count=len(recipients),
            sent_count=sent_count,
        )
        return f"Bulk email sent to {sent_count} recipients via Resend."
    except httpx.HTTPStatusError as exc:
        logger.error(
            "resend_bulk_email_tool_http_error",
            recipient_count=len(recipients),
            status_code=exc.response.status_code,
        )
        return f"Failed to send bulk emails via Resend: HTTP {exc.response.status_code}"
    except httpx.RequestError as exc:
        logger.error(
            "resend_bulk_email_tool_request_error",
            recipient_count=len(recipients),
            error=str(exc),
        )
        return f"Failed to send bulk emails via Resend: Request error - {exc}"


@tool
async def push_segment_to_resend(segment_id: str, audience_name: str | None = None) -> str:
    """Push a Tracardi segment to Resend as an audience.

    Use for: Email marketing campaigns, newsletters, audience management.
    This creates a new Resend audience and adds all segment contacts to it.

    Args:
        segment_id: The Tracardi segment name/ID to push.
        audience_name: Optional name for the Resend audience (defaults to segment_id).

    Returns:
        Success message with audience ID and contact count, or error message.
    """
    resend = ResendClient()
    logger.info("resend_push_start", segment=segment_id)
    try:
        profiles_to_push, total_count, backend, diagnostics = await _load_segment_contacts(segment_id, limit=1000)
    except RuntimeError as exc:
        return json.dumps({
            "status": "error",
            "error": str(exc),
            "segment_id": segment_id,
            "suggestions": [
                "Verify the segment name is correct",
                "Check if the segment has any members with: get_segment_stats",
                "Try recreating the segment if it was deleted",
                "Check if PostgreSQL and Tracardi are both accessible"
            ]
        }, ensure_ascii=False)

    if total_count == 0:
        return json.dumps({
            "status": "error",
            "error": f"Segment '{segment_id}' contains no profiles to push.",
            "diagnostics": diagnostics,
            "suggestions": [
                "The segment search criteria may be too restrictive",
                "Check if companies have email addresses (required for Resend)",
                "Verify segment members were successfully projected to Tracardi"
            ]
        }, ensure_ascii=False)

    # Create audience name
    audience_name = audience_name or segment_id

    try:
        # Create the audience in Resend
        audience = await resend.create_audience(name=audience_name)
        audience_id = audience.get("id")

        if not audience_id:
            return "Failed to create Resend audience."

        # Add contacts to the audience
        added_count = 0
        for p in profiles_to_push:
            email = _extract_segment_email(p)
            if not email:
                continue

            name = _extract_segment_name(p)
            parts = name.split(" ", 1) if name else ["", ""]
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

            try:
                await resend.add_contact_to_audience(
                    email=email,
                    audience_id=audience_id,
                    first_name=first_name or None,
                    last_name=last_name or None,
                )
                added_count += 1
            except httpx.HTTPStatusError as contact_exc:
                logger.warning(
                    "resend_add_contact_skipped_http",
                    email=email,
                    status_code=contact_exc.response.status_code,
                )
            except httpx.RequestError as contact_exc:
                logger.warning(
                    "resend_add_contact_skipped_request",
                    email=email,
                    error=str(contact_exc),
                )

        logger.info(
            "resend_push_complete",
            segment=segment_id,
            audience_id=audience_id,
            total=total_count,
            added=added_count,
            backend=backend,
        )

        # Calculate skipped count
        skipped_count = len(profiles_to_push) - added_count
        no_email_count = len(profiles_to_push) - diagnostics.get("profiles_with_email", 0)

        result = {
            "status": "ok",
            "segment_id": segment_id,
            "audience_name": audience_name,
            "audience_id": audience_id,
            "backend": backend,
            "counts": {
                "segment_total": total_count,
                "loaded": len(profiles_to_push),
                "added_to_resend": added_count,
                "skipped": skipped_count,
                "without_email": no_email_count,
            },
            "diagnostics": diagnostics,
        }

        if total_count > len(profiles_to_push):
            result["note"] = f"Loaded {len(profiles_to_push)} of {total_count} total members in this tool call."

        if skipped_count > 0:
            result["suggestions"] = [
                f"{skipped_count} profiles were skipped - likely due to missing/invalid emails",
                "Verify segment members have valid email addresses",
                "Check Tracardi profile data completeness"
            ]

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("resend_push_error", segment=segment_id, error=str(exc))
        return json.dumps({
            "status": "error",
            "error": f"Failed to push segment to Resend: {exc}",
            "segment_id": segment_id,
            "suggestions": [
                "Check Resend API key is valid",
                "Verify network connectivity to Resend API",
                "Check if audience name is unique in Resend"
            ]
        }, ensure_ascii=False)


@tool
async def send_campaign_via_resend(
    audience_id: str, subject: str, html_content: str, from_email: str | None = None
) -> str:
    """Send an email campaign to a Resend audience.

    Use for: Marketing campaigns to existing audiences, newsletters.

    Args:
        audience_id: The Resend audience ID to send to.
        subject: Email subject line.
        html_content: HTML content of the email.
        from_email: Optional sender email (defaults to configured from_email).

    Returns:
        Success message with campaign ID or error message.
    """
    client = ResendClient()
    try:
        result = await client.send_audience_email(
            audience_id=audience_id,
            subject=subject,
            html=html_content,
            from_email=from_email,
        )
        message_id = result.get("id", "unknown")
        logger.info(
            "resend_campaign_tool_success",
            audience_id=audience_id,
            message_id=message_id,
        )
        return f"Campaign sent successfully to Resend audience. Message ID: {message_id}"
    except httpx.HTTPStatusError as exc:
        logger.error(
            "resend_campaign_tool_http_error",
            audience_id=audience_id,
            status_code=exc.response.status_code,
        )
        return f"Failed to send campaign via Resend: HTTP {exc.response.status_code}"
    except httpx.RequestError as exc:
        logger.error("resend_campaign_tool_request_error", audience_id=audience_id, error=str(exc))
        return f"Failed to send campaign via Resend: Request error - {exc}"


__all__ = [
    "push_to_flexmail",
    "send_email_via_resend",
    "send_bulk_emails_via_resend",
    "push_segment_to_resend",
    "send_campaign_via_resend",
]
