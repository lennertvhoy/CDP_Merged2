"""
Tracardi CDP Client for CDP_Merged.
From CDPT - working implementation with full profile management.
Hardened with structured logging, custom exceptions, and retry logic.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.config import settings
from src.core.constants import MAX_RETRIES, RETRY_MAX_WAIT, RETRY_MIN_WAIT, TRACARDI_TIMEOUT
from src.core.exceptions import TracardiError
from src.core.logger import get_logger

logger = get_logger(__name__)
TRACARDI_MATCH_ALL_QUERY = "metadata.time.create EXISTS"


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


class TracardiClient:
    """Client for interacting with Tracardi CDP API."""

    def __init__(self) -> None:
        self.base_url = str(settings.TRACARDI_API_URL).rstrip("/")
        self.username = settings.TRACARDI_USERNAME
        self.password = settings.TRACARDI_PASSWORD
        self.token: str | None = None
        self.headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "*/*",
        }

    async def _ensure_token(self) -> None:
        """Authenticate and cache the access token."""
        if self.token:
            return

        url = f"{self.base_url}/user/token"
        payload = {
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
            "scope": "",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, data=payload, timeout=TRACARDI_TIMEOUT)
                response.raise_for_status()
                data = response.json()
                self.token = data.get("access_token")
                self.headers["Authorization"] = f"Bearer {self.token}"
                logger.info("tracardi_authenticated", url=self.base_url)
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "tracardi_auth_failed",
                    status_code=exc.response.status_code,
                    detail=exc.response.text[:200],
                )
                raise TracardiError(
                    f"Authentication failed: {exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error("tracardi_auth_connection_error", error=str(exc))
                raise TracardiError(f"Connection error during auth: {exc}") from exc

    async def _get_client(self) -> httpx.AsyncClient:
        """Return an authenticated async HTTP client."""
        await self._ensure_token()
        return httpx.AsyncClient(headers=self.headers, timeout=TRACARDI_TIMEOUT)

    async def get_or_create_profile(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve or create a profile for the given session ID.

        Args:
            session_id: Unique session identifier.

        Returns:
            Profile dict from Tracardi or None on failure.
        """
        payload = {
            "events": [{"type": "session_start", "properties": {"session_id": session_id}}],
            "source": {"id": settings.TRACARDI_SOURCE_ID},
            "session": {"id": session_id},
        }
        url = f"{self.base_url}/track"
        async with await self._get_client() as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("profile")
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "tracardi_get_or_create_profile_http_error",
                    status_code=exc.response.status_code,
                )
                return None
            except httpx.RequestError as exc:
                logger.warning("tracardi_get_or_create_profile_request_error", error=str(exc))
                return None

    async def get_profile_by_email(self, email: str) -> dict[str, Any] | None:
        """Fetch a profile by email address.

        Args:
            email: Email address to search for.

        Returns:
            Profile dict or None if not found.
        """
        url = f"{self.base_url}/profile/by-email/{email}"
        async with await self._get_client() as client:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 404:
                    return None
                response.raise_for_status()
            except httpx.RequestError as exc:
                logger.warning(
                    "tracardi_request_error", method="get_profile_by_email", error=str(exc)
                )
            return None

    @_retry
    async def track_event(
        self,
        event_type: str,
        properties: dict[str, Any],
        profile_id: str | None = None,
        session_id: str | None = None,
        profile_traits: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Send a single event to Tracardi.

        Args:
            event_type: Event type string.
            properties: Event properties.
            profile_id: Optional profile to associate.
            session_id: Optional session ID.
            profile_traits: Optional profile traits to update.

        Returns:
            Response JSON or None on failure.
        """
        event = {"type": event_type, "properties": properties}
        payload: dict[str, Any] = {
            "events": [event],
            "source": {"id": settings.TRACARDI_SOURCE_ID},
        }
        profile_data: dict[str, Any] = {}
        if profile_id:
            profile_data["id"] = profile_id
        if profile_traits:
            profile_data["traits"] = profile_traits
        if profile_data:
            payload["profile"] = profile_data
        if session_id:
            payload["session"] = {"id": session_id}

        url = f"{self.base_url}/track"
        async with await self._get_client() as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "tracardi_track_event_failed",
                    event_type=event_type,
                    status_code=exc.response.status_code,
                    detail=exc.response.text[:200],
                )
                return None

    async def track_events_batch(self, events: list[dict[str, Any]]) -> list:
        """Send a batch of events to Tracardi.

        Args:
            events: List of event dicts with type, properties, optional profile_id etc.

        Returns:
            List of results (may include exceptions from asyncio.gather).
        """
        async with await self._get_client() as client:
            tasks = []
            for event_data in events:
                payload: dict[str, Any] = {
                    "events": [
                        {
                            "type": event_data["type"],
                            "properties": event_data["properties"],
                        }
                    ],
                    "source": {"id": settings.TRACARDI_SOURCE_ID},
                }
                profile_obj: dict[str, Any] = {}
                if "profile_id" in event_data:
                    profile_obj["id"] = event_data["profile_id"]
                if "profile_traits" in event_data:
                    profile_obj["traits"] = event_data["profile_traits"]
                if profile_obj:
                    payload["profile"] = profile_obj
                if "session_id" in event_data:
                    payload["session"] = {"id": event_data["session_id"]}
                tasks.append(client.post(f"{self.base_url}/track", json=payload))

            results: list = []
            chunk_size = 50
            for i in range(0, len(tasks), chunk_size):
                chunk = tasks[i : i + chunk_size]
                chunk_results = await asyncio.gather(*chunk, return_exceptions=True)
                results.extend(chunk_results)
            return results

    @_retry
    async def import_profiles(self, profiles: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Import profiles directly via the bulk import endpoint.

        Args:
            profiles: List of profile dicts to import.

        Returns:
            Response JSON or None on failure.
        """
        url = f"{self.base_url}/profiles/import"
        # Bulk imports can legitimately take longer than interactive API calls,
        # especially while Elasticsearch is recovering or indexing catches up.
        import_timeout = httpx.Timeout(connect=10.0, read=300.0, write=60.0, pool=60.0)
        async with await self._get_client() as client:
            try:
                response = await client.post(url, json=profiles, timeout=import_timeout)
                response.raise_for_status()
                logger.info("tracardi_profiles_imported", count=len(profiles))
                return response.json()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "tracardi_import_profiles_failed",
                    status_code=exc.response.status_code,
                    detail=exc.response.text[:200],
                )
                raise TracardiError(
                    f"Import failed: {exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc

    @_retry
    async def search_profiles(
        self, query: str, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """Search for profiles using TQL (Tracardi Query Language).

        Args:
            query: TQL query string or ``"*"`` to match all.
            limit: Maximum number of results to return.
            offset: Number of results to skip (for pagination).

        Returns:
            Dict with ``total`` and ``result`` keys.
        """
        url = f"{self.base_url}/profile/select"
        # Tracardi 1.0.x returns HTTP 500 for the older `id` wildcard query.
        # `metadata.time.create EXISTS` is stable for both imported and tracked profiles.
        normalized_query = query.strip()
        where = TRACARDI_MATCH_ALL_QUERY if normalized_query in {"", "*"} else query
        payload: dict[str, Any] = {
            "where": where,
            "limit": limit,
            "offset": offset,
            "full_profile": True,
        }

        async with await self._get_client() as client:
            try:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 404:
                    logger.error("tracardi_search_endpoint_not_found")
                    raise TracardiError(
                        "Profile search endpoint not found: 404",
                        status_code=404,
                    )
                logger.error(
                    "tracardi_search_profiles_failed",
                    status_code=response.status_code,
                    detail=response.text[:200],
                )
                raise TracardiError(
                    f"Profile search failed: {response.status_code}",
                    status_code=response.status_code,
                )
            except httpx.RequestError as exc:
                logger.error("tracardi_search_connection_error", error=str(exc))
                raise TracardiError(f"Profile search connection error: {exc}") from exc

    async def add_profile_to_segment(self, profile_id: str, segment_name: str) -> bool:
        """Add a profile to a named segment.

        Args:
            profile_id: Profile UUID.
            segment_name: Segment name in Tracardi.

        Returns:
            True on success, False otherwise.
        """
        url = f"{self.base_url}/profile/{profile_id}/segment/{segment_name}"
        async with await self._get_client() as client:
            try:
                response = await client.post(url)
                if response.status_code == 200:
                    return True
                logger.warning(
                    "tracardi_add_to_segment_failed",
                    profile_id=profile_id,
                    segment=segment_name,
                    status_code=response.status_code,
                )
                return False
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "tracardi_add_to_segment_http_error",
                    profile_id=profile_id,
                    segment=segment_name,
                    status_code=exc.response.status_code,
                )
                return False
            except httpx.RequestError as exc:
                logger.error(
                    "tracardi_add_to_segment_request_error",
                    profile_id=profile_id,
                    segment=segment_name,
                    error=str(exc),
                )
                return False

    async def create_segment(
        self,
        name: str,
        description: str = "",
        condition: str = "",
    ) -> dict[str, Any]:
        """Create a segment by finding matching profiles and tagging them.

        Args:
            name: Segment name.
            description: Human-readable description.
            condition: TQL condition to match profiles.

        Returns:
            Dict with segment metadata and ``profiles_added`` count.
        """
        logger.info("tracardi_creating_segment", name=name, condition=condition)
        search_result = await self.search_profiles(condition)
        profiles = search_result.get("result", [])

        count = 0
        for p in profiles:
            pid = p.get("id")
            if pid and await self.add_profile_to_segment(pid, name):
                count += 1

        logger.info("tracardi_segment_created", name=name, profiles_added=count)
        return {
            "id": name,
            "name": name,
            "description": description,
            "condition": condition,
            "profiles_added": count,
        }

    async def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile by ID.

        Args:
            profile_id: UUID of the profile to delete.

        Returns:
            True on success, False otherwise.
        """
        url = f"{self.base_url}/profile/{profile_id}"
        async with await self._get_client() as client:
            try:
                response = await client.delete(url)
                if response.status_code == 200:
                    return True
                logger.warning(
                    "tracardi_delete_profile_failed",
                    profile_id=profile_id,
                    status_code=response.status_code,
                )
                return False
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "tracardi_delete_profile_http_error",
                    profile_id=profile_id,
                    status_code=exc.response.status_code,
                )
                return False
            except httpx.RequestError as exc:
                logger.error(
                    "tracardi_delete_profile_request_error", profile_id=profile_id, error=str(exc)
                )
                return False
