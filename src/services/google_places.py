"""
Google Places API Client.

Interfaces with the Google Places API to fetch contact data:
- Phone numbers
- Websites
- Opening Hours
- Photos
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.core.circuit_breaker import CircuitBreaker
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
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)


class GooglePlacesClient:
    """
    Client for interacting with Google Places API.
    """

    FIND_PLACE_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

    def __init__(self, api_key: str | None = None, timeout: float = 10.0):
        self.api_key = api_key or os.environ.get("GOOGLE_PLACES_API_KEY")
        self.timeout = timeout
        self.circuit_breaker = CircuitBreaker(
            name="GooglePlacesAPI", failure_threshold=5, recovery_timeout=60.0
        )

        # In a real setup, missing API key might be ok if we gracefully fallback/skip
        if not self.api_key:
            logger.warning("GOOGLE_PLACES_API_KEY is not set. GooglePlacesClient will fail.")

    @_retry
    async def search_company(self, company_name: str, address: str | None = None) -> str | None:
        """
        Search for a company and return its place_id.

        Args:
            company_name: Name of the company
            address: Optional address to improve search accuracy

        Returns:
            Google place_id or None
        """
        if not self.api_key:
            return None

        if not self.circuit_breaker.can_execute():
            logger.warning("GooglePlaces API circuit is open. Skipping search_company.")
            return None

        query = company_name
        if address:
            query = f"{company_name} {address}"

        params = {
            "input": query,
            "inputtype": "textquery",
            "fields": "place_id",
            "key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.FIND_PLACE_URL, params=params)

                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")

                    if status == "OK" and data.get("candidates"):
                        self.circuit_breaker.record_success()
                        # Get first candidate
                        return data["candidates"][0].get("place_id")
                    elif status == "ZERO_RESULTS":
                        logger.debug(f"No Google Place found for: {query}")
                        self.circuit_breaker.record_success()
                    else:
                        logger.warning(f"Google Places API error (Find Place): {status}")
                        if status in ["OVER_QUERY_LIMIT", "REQUEST_DENIED", "UNKNOWN_ERROR"]:
                            self.circuit_breaker.record_failure()

                else:
                    self.circuit_breaker.record_failure()
                    logger.error(f"HTTP Error {response.status_code} on Find Place API")
                    response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Google Places API HTTP Error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error searching Google Places for {query}: {e}")
            self.circuit_breaker.record_failure()

        return None

    @_retry
    async def get_place_details(self, place_id: str) -> dict[str, Any] | None:
        """
        Get details for a specific place_id.

        Args:
            place_id: Google place_id

        Returns:
            Dictionary with place details
        """
        if not self.api_key:
            return None

        if not self.circuit_breaker.can_execute():
            logger.warning("GooglePlaces API circuit is open. Skipping get_place_details.")
            return None

        # Request specific fields to minimize cost and latency
        fields = "name,formatted_phone_number,website,current_opening_hours,photos"

        params = {
            "place_id": place_id,
            "fields": fields,
            "key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.PLACE_DETAILS_URL, params=params)

                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")

                    if status == "OK":
                        self.circuit_breaker.record_success()
                        return data.get("result", {})
                    else:
                        logger.warning(f"Google Places API error (Details): {status}")
                        if status in ["OVER_QUERY_LIMIT", "REQUEST_DENIED", "UNKNOWN_ERROR"]:
                            self.circuit_breaker.record_failure()
                else:
                    self.circuit_breaker.record_failure()
                    logger.error(f"HTTP Error {response.status_code} on Place Details API")
                    response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Google Places API HTTP Error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching Google Place Details for {place_id}: {e}")
            self.circuit_breaker.record_failure()

        return None

    async def enrich_company(
        self, company_name: str, address: str | None = None
    ) -> dict[str, Any] | None:
        """
        Convenience method to search by name/address and immediately get details.

        Args:
            company_name: Name of the company
            address: Optional address to improve search accuracy

        Returns:
            Dictionary with enriched place details or None
        """
        if not self.api_key:
            return None

        place_id = await self.search_company(company_name, address)
        if not place_id:
            return None

        return await self.get_place_details(place_id)
