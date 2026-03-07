"""
Resend Integration Client for CDP_Merged.
Developer-friendly email API for transactional and bulk emails.
Hardened with structured logging, custom exceptions, and retry logic.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.config import settings
from src.core.constants import MAX_RETRIES, RESEND_TIMEOUT, RETRY_MAX_WAIT, RETRY_MIN_WAIT
from src.core.exceptions import ResendError
from src.core.logger import get_logger

logger = get_logger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Determine if an exception is retryable."""
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        # Retry on 429 (rate limit) and 5xx server errors
        return exc.response.status_code in (429, 503, 502, 501, 500)
    return False


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
    reraise=True,
)


class ResendClient:
    """Client for interacting with the Resend email API."""

    BASE_URL = "https://api.resend.com"

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize Resend client.

        Args:
            api_key: Resend API key. If not provided, uses settings.RESEND_API_KEY.
        """
        self.api_key = api_key or settings.RESEND_API_KEY
        self.from_email = settings.RESEND_FROM_EMAIL or "onboarding@resend.dev"
        self.headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "CDP-Agent/1.0",
        }

    def _get_client(self) -> httpx.AsyncClient:
        """Return a configured async HTTP client."""
        return httpx.AsyncClient(headers=self.headers, timeout=RESEND_TIMEOUT)

    @_retry
    async def send_email(
        self,
        to: str,
        subject: str,
        html: str,
        from_email: str | None = None,
    ) -> dict[str, Any]:
        """Send a single email via Resend.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            html: HTML content of the email.
            from_email: Sender email address (defaults to configured from_email).

        Returns:
            Response dict with 'id' field on success.

        Raises:
            ResendError: If the API call fails.
        """
        url = f"{self.BASE_URL}/emails"
        payload = {
            "from": from_email or self.from_email,
            "to": to,
            "subject": subject,
            "html": html,
        }

        async with self._get_client() as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "resend_email_sent",
                    to=to,
                    subject=subject[:50],
                    message_id=data.get("id"),
                )
                return data
            except httpx.HTTPStatusError as exc:
                error_detail = ""
                try:
                    error_detail = exc.response.json().get("message", "")
                except (json.JSONDecodeError, KeyError):
                    error_detail = exc.response.text[:200]

                logger.error(
                    "resend_send_email_failed",
                    to=to,
                    status_code=exc.response.status_code,
                    error=error_detail,
                )
                raise ResendError(
                    f"Failed to send email: {error_detail or exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error("resend_send_email_error", to=to, error=str(exc))
                raise ResendError(f"Request error sending email: {exc}") from exc

    @_retry
    async def send_bulk_emails(
        self,
        recipients: list[str],
        subject: str,
        html: str,
        from_email: str | None = None,
    ) -> dict[str, Any]:
        """Send bulk emails to multiple recipients via Resend batch API.

        Args:
            recipients: List of recipient email addresses.
            subject: Email subject line.
            html: HTML content of the email.
            from_email: Sender email address (defaults to configured from_email).

        Returns:
            Response dict with batch results.

        Raises:
            ResendError: If the API call fails.
        """
        url = f"{self.BASE_URL}/emails/batch"
        sender = from_email or self.from_email

        # Build batch payload
        emails = [
            {"from": sender, "to": recipient, "subject": subject, "html": html}
            for recipient in recipients
        ]
        payload = {"emails": emails}

        async with self._get_client() as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "resend_bulk_emails_sent",
                    recipient_count=len(recipients),
                    subject=subject[:50],
                )
                return data
            except httpx.HTTPStatusError as exc:
                error_detail = ""
                try:
                    error_detail = exc.response.json().get("message", "")
                except (json.JSONDecodeError, KeyError):
                    error_detail = exc.response.text[:200]

                logger.error(
                    "resend_send_bulk_failed",
                    recipient_count=len(recipients),
                    status_code=exc.response.status_code,
                    error=error_detail,
                )
                raise ResendError(
                    f"Failed to send bulk emails: {error_detail or exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error("resend_send_bulk_error", error=str(exc))
                raise ResendError(f"Request error sending bulk emails: {exc}") from exc

    @_retry
    async def get_domains(self) -> list[dict[str, Any]]:
        """List all verified domains in Resend.

        Returns:
            List of domain dicts with 'id', 'name', 'status', etc.

        Raises:
            ResendError: If the API call fails.
        """
        url = f"{self.BASE_URL}/domains"

        async with self._get_client() as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                domains = data.get("data", [])
                logger.info("resend_domains_listed", count=len(domains))
                return domains
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "resend_get_domains_failed",
                    status_code=exc.response.status_code,
                )
                raise ResendError(
                    f"Failed to list domains: {exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error("resend_get_domains_error", error=str(exc))
                raise ResendError(f"Request error listing domains: {exc}") from exc

    @_retry
    async def get_audiences(self) -> list[dict[str, Any]]:
        """List all audiences in Resend.

        Returns:
            List of audience dicts with 'id', 'name', etc.

        Raises:
            ResendError: If the API call fails.
        """
        url = f"{self.BASE_URL}/audiences"

        async with self._get_client() as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                audiences = data.get("data", [])
                logger.info("resend_audiences_listed", count=len(audiences))
                return audiences
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "resend_get_audiences_failed",
                    status_code=exc.response.status_code,
                )
                raise ResendError(
                    f"Failed to list audiences: {exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error("resend_get_audiences_error", error=str(exc))
                raise ResendError(f"Request error listing audiences: {exc}") from exc

    @_retry
    async def create_audience(self, name: str) -> dict[str, Any]:
        """Create a new audience in Resend.

        Args:
            name: Name for the new audience.

        Returns:
            Response dict with 'id' field on success.

        Raises:
            ResendError: If the API call fails.
        """
        url = f"{self.BASE_URL}/audiences"
        payload = {"name": name}

        async with self._get_client() as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "resend_audience_created",
                    name=name,
                    audience_id=data.get("id"),
                )
                return data
            except httpx.HTTPStatusError as exc:
                error_detail = ""
                try:
                    error_detail = exc.response.json().get("message", "")
                except (json.JSONDecodeError, KeyError):
                    error_detail = exc.response.text[:200]

                logger.error(
                    "resend_create_audience_failed",
                    name=name,
                    status_code=exc.response.status_code,
                    error=error_detail,
                )
                raise ResendError(
                    f"Failed to create audience: {error_detail or exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error("resend_create_audience_error", name=name, error=str(exc))
                raise ResendError(f"Request error creating audience: {exc}") from exc

    @_retry
    async def add_contact_to_audience(
        self,
        email: str,
        audience_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> dict[str, Any]:
        """Add a contact to an audience.

        Args:
            email: Contact email address.
            audience_id: Resend audience ID.
            first_name: Optional first name.
            last_name: Optional last name.

        Returns:
            Response dict with contact data on success.

        Raises:
            ResendError: If the API call fails.
        """
        url = f"{self.BASE_URL}/audiences/{audience_id}/contacts"
        payload: dict[str, Any] = {"email": email}
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name

        async with self._get_client() as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "resend_contact_added_to_audience",
                    email=email,
                    audience_id=audience_id,
                )
                return data
            except httpx.HTTPStatusError as exc:
                error_detail = ""
                try:
                    error_detail = exc.response.json().get("message", "")
                except (json.JSONDecodeError, KeyError):
                    error_detail = exc.response.text[:200]

                logger.error(
                    "resend_add_contact_failed",
                    email=email,
                    audience_id=audience_id,
                    status_code=exc.response.status_code,
                    error=error_detail,
                )
                raise ResendError(
                    f"Failed to add contact: {error_detail or exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error(
                    "resend_add_contact_error",
                    email=email,
                    audience_id=audience_id,
                    error=str(exc),
                )
                raise ResendError(f"Request error adding contact: {exc}") from exc

    @_retry
    async def send_audience_email(
        self,
        audience_id: str,
        subject: str,
        html: str,
        from_email: str | None = None,
    ) -> dict[str, Any]:
        """Send an email campaign to an audience.

        Args:
            audience_id: Resend audience ID.
            subject: Email subject line.
            html: HTML content of the email.
            from_email: Sender email address (defaults to configured from_email).

        Returns:
            Response dict with campaign data on success.

        Raises:
            ResendError: If the API call fails.
        """
        url = f"{self.BASE_URL}/emails"
        payload = {
            "from": from_email or self.from_email,
            "to": [],  # Required but empty for audience sends
            "subject": subject,
            "html": html,
            "audience_id": audience_id,
        }

        async with self._get_client() as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "resend_audience_email_sent",
                    audience_id=audience_id,
                    subject=subject[:50],
                    message_id=data.get("id"),
                )
                return data
            except httpx.HTTPStatusError as exc:
                error_detail = ""
                try:
                    error_detail = exc.response.json().get("message", "")
                except (json.JSONDecodeError, KeyError):
                    error_detail = exc.response.text[:200]

                logger.error(
                    "resend_send_audience_email_failed",
                    audience_id=audience_id,
                    status_code=exc.response.status_code,
                    error=error_detail,
                )
                raise ResendError(
                    f"Failed to send audience email: {error_detail or exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error(
                    "resend_send_audience_email_error",
                    audience_id=audience_id,
                    error=str(exc),
                )
                raise ResendError(f"Request error sending audience email: {exc}") from exc

    # ============ Webhook Methods ============

    @_retry
    async def get_webhooks(self) -> list[dict[str, Any]]:
        """List all webhooks configured in Resend.

        Returns:
            List of webhook dicts with 'id', 'url', 'events', etc.

        Raises:
            ResendError: If the API call fails.
        """
        url = f"{self.BASE_URL}/webhooks"

        async with self._get_client() as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                webhooks = data.get("data", [])
                logger.info("resend_webhooks_listed", count=len(webhooks))
                return webhooks
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "resend_get_webhooks_failed",
                    status_code=exc.response.status_code,
                )
                raise ResendError(
                    f"Failed to list webhooks: {exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error("resend_get_webhooks_error", error=str(exc))
                raise ResendError(f"Request error listing webhooks: {exc}") from exc

    @_retry
    async def create_webhook(
        self,
        endpoint_url: str,
        events: list[str],
        name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new webhook in Resend.

        Args:
            endpoint_url: URL to send webhook events to.
            events: List of event types to subscribe to.
                Available events: email.sent, email.delivered, email.opened,
                email.clicked, email.bounced, email.complained, email.delivery_delayed
            name: Optional name for the webhook.

        Returns:
            Response dict with 'id' field on success.

        Raises:
            ResendError: If the API call fails.
        """
        url = f"{self.BASE_URL}/webhooks"
        payload: dict[str, Any] = {
            "endpoint": endpoint_url,
            "events": events,
        }
        if name:
            payload["name"] = name

        async with self._get_client() as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "resend_webhook_created",
                    name=name,
                    webhook_id=data.get("id"),
                    endpoint=endpoint_url,
                    events=events,
                )
                return data
            except httpx.HTTPStatusError as exc:
                error_detail = ""
                try:
                    error_detail = exc.response.json().get("message", "")
                except (json.JSONDecodeError, KeyError):
                    error_detail = exc.response.text[:200]

                logger.error(
                    "resend_create_webhook_failed",
                    name=name,
                    endpoint=endpoint_url,
                    status_code=exc.response.status_code,
                    error=error_detail,
                )
                raise ResendError(
                    f"Failed to create webhook: {error_detail or exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error(
                    "resend_create_webhook_error",
                    name=name,
                    endpoint=endpoint_url,
                    error=str(exc),
                )
                raise ResendError(f"Request error creating webhook: {exc}") from exc

    @_retry
    async def update_webhook(
        self,
        webhook_id: str,
        endpoint_url: str | None = None,
        events: list[str] | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing webhook in Resend.

        Args:
            webhook_id: ID of the webhook to update.
            endpoint_url: New URL to send webhook events to.
            events: New list of event types to subscribe to.
            name: New name for the webhook.

        Returns:
            Response dict with webhook data on success.

        Raises:
            ResendError: If the API call fails.
        """
        url = f"{self.BASE_URL}/webhooks/{webhook_id}"
        payload: dict[str, Any] = {}
        if endpoint_url:
            payload["url"] = endpoint_url
        if events:
            payload["events"] = events
        if name:
            payload["name"] = name

        async with self._get_client() as client:
            try:
                response = await client.patch(url, json=payload)
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "resend_webhook_updated",
                    webhook_id=webhook_id,
                    name=name,
                )
                return data
            except httpx.HTTPStatusError as exc:
                error_detail = ""
                try:
                    error_detail = exc.response.json().get("message", "")
                except (json.JSONDecodeError, KeyError):
                    error_detail = exc.response.text[:200]

                logger.error(
                    "resend_update_webhook_failed",
                    webhook_id=webhook_id,
                    status_code=exc.response.status_code,
                    error=error_detail,
                )
                raise ResendError(
                    f"Failed to update webhook: {error_detail or exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error(
                    "resend_update_webhook_error",
                    webhook_id=webhook_id,
                    error=str(exc),
                )
                raise ResendError(f"Request error updating webhook: {exc}") from exc

    @_retry
    async def delete_webhook(self, webhook_id: str) -> dict[str, Any]:
        """Delete a webhook from Resend.

        Args:
            webhook_id: ID of the webhook to delete.

        Returns:
            Response dict on success.

        Raises:
            ResendError: If the API call fails.
        """
        url = f"{self.BASE_URL}/webhooks/{webhook_id}"

        async with self._get_client() as client:
            try:
                response = await client.delete(url)
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "resend_webhook_deleted",
                    webhook_id=webhook_id,
                )
                return data
            except httpx.HTTPStatusError as exc:
                error_detail = ""
                try:
                    error_detail = exc.response.json().get("message", "")
                except (json.JSONDecodeError, KeyError):
                    error_detail = exc.response.text[:200]

                logger.error(
                    "resend_delete_webhook_failed",
                    webhook_id=webhook_id,
                    status_code=exc.response.status_code,
                    error=error_detail,
                )
                raise ResendError(
                    f"Failed to delete webhook: {error_detail or exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error(
                    "resend_delete_webhook_error",
                    webhook_id=webhook_id,
                    error=str(exc),
                )
                raise ResendError(f"Request error deleting webhook: {exc}") from exc
