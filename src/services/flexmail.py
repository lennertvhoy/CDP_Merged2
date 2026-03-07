"""
Flexmail Integration Client for CDP_Merged.
From CDPT - working implementation for email marketing automation.
Hardened with structured logging, custom exceptions, and retry logic.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.config import settings
from src.core.constants import FLEXMAIL_TIMEOUT, MAX_RETRIES, RETRY_MAX_WAIT, RETRY_MIN_WAIT
from src.core.exceptions import FlexmailError
from src.core.logger import get_logger

logger = get_logger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
    reraise=True,
)


class FlexmailClient:
    """Client for interacting with the Flexmail email marketing API."""

    def __init__(self) -> None:
        self.base_url = str(settings.FLEXMAIL_API_URL).rstrip("/")
        self.api_token = settings.FLEXMAIL_API_TOKEN
        self.account_id = settings.FLEXMAIL_ACCOUNT_ID
        self.source_id = settings.FLEXMAIL_SOURCE_ID
        self.auth = (str(self.account_id), self.api_token or "")
        self.headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/hal+json",
            "User-Agent": "CDP-Agent/1.0",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Return a configured async HTTP client with auth."""
        return httpx.AsyncClient(auth=self.auth, headers=self.headers, timeout=FLEXMAIL_TIMEOUT)

    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        signature: str,
        secret: str | None = None,
    ) -> bool:
        """Verify the HMAC-SHA256 signature of a Flexmail webhook.

        Args:
            payload: Raw request body bytes.
            signature: Signature value from the request header.
            secret: Webhook secret; falls back to ``settings.FLEXMAIL_WEBHOOK_SECRET``.

        Returns:
            True if the signature is valid, False otherwise.
        """
        resolved_secret = secret or settings.FLEXMAIL_WEBHOOK_SECRET
        if not resolved_secret:
            logger.warning("flexmail_webhook_no_secret")
            return False

        expected = hmac.new(
            key=resolved_secret.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    @_retry
    async def get_custom_fields(self) -> list[dict[str, Any]]:
        """List all custom fields defined in Flexmail.

        Returns:
            List of custom field dicts.
        """
        url = f"{self.base_url}/custom-fields"
        async with await self._get_client() as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                return data.get("_embedded", {}).get("item", [])
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "flexmail_get_custom_fields_failed",
                    status_code=exc.response.status_code,
                )
                raise FlexmailError(
                    f"Failed to list custom fields: {exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc

    @_retry
    async def create_contact(
        self,
        email: str,
        name: str,
        language: str = "nl",
        custom_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a contact in Flexmail.

        Args:
            email: Contact email address.
            name: Full name (split into first/last).
            language: ISO language code (default ``nl``).
            custom_fields: Optional dict of custom field values.

        Returns:
            Created or existing contact dict; empty dict on failure.
        """
        url = f"{self.base_url}/contacts"
        parts = name.split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

        payload: dict[str, Any] = {
            "email": email,
            "first_name": first_name,
            "name": last_name,
            "language": language,
            "source": int(self.source_id),
        }
        if custom_fields:
            payload["custom_fields"] = custom_fields

        async with await self._get_client() as client:
            try:
                response = await client.post(url, json=payload)
                if response.status_code == 201:
                    logger.info("flexmail_contact_created", email=email)
                    return response.json()
                if response.status_code == 409:
                    logger.info("flexmail_contact_exists", email=email)
                    return await self.get_contact_by_email(email)
                logger.warning(
                    "flexmail_create_contact_unexpected",
                    email=email,
                    status_code=response.status_code,
                )
                return {}
            except httpx.RequestError as exc:
                logger.error("flexmail_create_contact_error", email=email, error=str(exc))
                return {}

    async def update_contact(self, contact_id: str, fields: dict[str, Any]) -> bool:
        """Update an existing contact's fields.

        Args:
            contact_id: Flexmail contact ID.
            fields: Dict of fields to update (first_name, name, language, custom_fields).

        Returns:
            True on success, False otherwise.
        """
        current = await self.get_contact_by_id(contact_id)
        if not current:
            return False

        payload = current.copy()
        for key in ("first_name", "name", "language"):
            if key in fields:
                payload[key] = fields[key]
        if "custom_fields" in fields:
            payload.setdefault("custom_fields", {})
            payload["custom_fields"].update(fields["custom_fields"])

        clean_payload: dict[str, Any] = {
            "email": payload.get("email"),
            "first_name": payload.get("first_name"),
            "name": payload.get("name"),
            "language": payload.get("language"),
            "source": int(self.source_id),
        }
        if "custom_fields" in payload:
            clean_payload["custom_fields"] = payload["custom_fields"]

        url = f"{self.base_url}/contacts/{contact_id}"
        async with await self._get_client() as client:
            try:
                response = await client.put(url, json=clean_payload)
                if response.status_code in (200, 204):
                    logger.info("flexmail_contact_updated", contact_id=contact_id)
                    return True
                logger.warning(
                    "flexmail_update_contact_failed",
                    contact_id=contact_id,
                    status_code=response.status_code,
                )
                return False
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "flexmail_update_contact_http_error",
                    contact_id=contact_id,
                    status_code=exc.response.status_code,
                    error=str(exc),
                )
                return False
            except httpx.RequestError as exc:
                logger.error(
                    "flexmail_update_contact_request_error", contact_id=contact_id, error=str(exc)
                )
                return False

    async def get_contact_by_id(self, contact_id: str) -> dict[str, Any]:
        """Fetch a contact by their Flexmail ID.

        Args:
            contact_id: Flexmail contact ID.

        Returns:
            Contact dict or empty dict if not found.
        """
        url = f"{self.base_url}/contacts/{contact_id}"
        async with await self._get_client() as client:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
                return {}
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "flexmail_get_contact_by_id_http_error",
                    contact_id=contact_id,
                    status_code=exc.response.status_code,
                )
                return {}
            except httpx.RequestError as exc:
                logger.error(
                    "flexmail_get_contact_by_id_request_error",
                    contact_id=contact_id,
                    error=str(exc),
                )
                return {}

    async def get_contact_by_email(self, email: str) -> dict[str, Any]:
        """Fetch a contact by email address.

        Args:
            email: Email address to look up.

        Returns:
            Contact dict or empty dict if not found.
        """
        url = f"{self.base_url}/contacts"
        async with await self._get_client() as client:
            try:
                response = await client.get(url, params={"email": email})
                if response.status_code == 200:
                    items = response.json().get("_embedded", {}).get("item", [])
                    return items[0] if items else {}
                logger.warning(
                    "flexmail_get_contact_by_email_failed",
                    email=email,
                    status_code=response.status_code,
                )
                return {}
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "flexmail_get_contact_by_email_http_error",
                    email=email,
                    status_code=exc.response.status_code,
                )
                return {}
            except httpx.RequestError as exc:
                logger.error(
                    "flexmail_get_contact_by_email_request_error", email=email, error=str(exc)
                )
                return {}

    @_retry
    async def get_interests(self) -> list[dict[str, Any]]:
        """List all available interests (mailing lists) in Flexmail.

        Returns:
            List of interest dicts.
        """
        url = f"{self.base_url}/interests"
        async with await self._get_client() as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.json().get("_embedded", {}).get("item", [])
            except httpx.HTTPStatusError as exc:
                logger.error("flexmail_get_interests_failed", status_code=exc.response.status_code)
                raise FlexmailError(
                    f"Failed to list interests: {exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc

    async def add_contact_to_interest(self, contact_id: str, interest_id: str) -> bool:
        """Subscribe a contact to an interest (mailing list).

        Args:
            contact_id: Flexmail contact ID.
            interest_id: Interest ID to subscribe to.

        Returns:
            True on success, False otherwise.
        """
        url = f"{self.base_url}/contacts/{contact_id}/interest-subscriptions"
        async with await self._get_client() as client:
            try:
                response = await client.post(url, json={"interest_id": interest_id})
                if response.status_code == 201:
                    logger.info(
                        "flexmail_contact_added_to_interest",
                        contact_id=contact_id,
                        interest_id=interest_id,
                    )
                    return True
                logger.warning(
                    "flexmail_add_to_interest_failed",
                    contact_id=contact_id,
                    interest_id=interest_id,
                    status_code=response.status_code,
                )
                return False
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "flexmail_add_to_interest_http_error",
                    contact_id=contact_id,
                    interest_id=interest_id,
                    status_code=exc.response.status_code,
                )
                return False
            except httpx.RequestError as exc:
                logger.error(
                    "flexmail_add_to_interest_request_error",
                    contact_id=contact_id,
                    interest_id=interest_id,
                    error=str(exc),
                )
                return False
