"""
Google Places enrichment.

Discovers missing contact details using Google Places API.
Phase 2 Enrichment.
Cost: ~€5 per 1000 requests (after $200 free tier)
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.core.logger import get_logger
from src.enrichment.base import BaseEnricher
from src.services.google_places import GooglePlacesClient

logger = get_logger(__name__)


class GooglePlacesEnricher(BaseEnricher):
    """
    Enrich profiles with Google Places data.

    Fetches:
    - Phone number
    - Website
    - Working Hours
    - Photos (urls)
    """

    def __init__(
        self,
        cache_dir: str | None = "./data/cache",
        cache_file: str = "google_places_cache.json",
        timeout: float = 10.0,
        max_concurrent: int = 10,
    ):
        super().__init__(cache_dir=cache_dir, cache_file=cache_file)
        self.client = GooglePlacesClient(timeout=timeout)
        self.estimated_cost_usd = 0.0  # Tracks cost approximation

    def _get_company_name(self, profile: dict) -> str | None:
        """Extract company name."""
        traits = profile.get("traits", {})

        name = traits.get("name", "").strip()
        if name:
            return name

        kbo = traits.get("kbo", {})
        if kbo:
            denominations = kbo.get("denominations", [])
            for denom in denominations:
                if isinstance(denom, dict):
                    name = denom.get("name", "").strip()
                    if name:
                        return name
        return None

    def _get_address_string(self, profile: dict) -> str | None:
        """Extract a structured address string to improve search accuracy."""
        traits = profile.get("traits", {})

        # Try full address first
        if traits.get("address"):
            addr = traits["address"]
            if isinstance(addr, str):
                return addr
            if isinstance(addr, dict):
                parts = filter(
                    None,
                    [
                        addr.get("street"),
                        addr.get("houseNumber"),
                        addr.get("postalCode"),
                        addr.get("city"),
                        addr.get("country", "Belgium"),
                    ],
                )
                return " ".join(parts)

        # Try KBO address
        kbo = traits.get("kbo", {})
        if kbo:
            addresses = kbo.get("addresses", [])
            for addr in addresses:
                if isinstance(addr, dict):
                    parts = filter(
                        None,
                        [
                            addr.get("streetNL") or addr.get("streetFR"),
                            addr.get("houseNumber"),
                            addr.get("zipcode"),
                            addr.get("municipalityNL") or addr.get("municipalityFR"),
                            "Belgium",
                        ],
                    )
                    return " ".join(parts)

        # Fallback to loose fields
        if traits.get("city"):
            return f"{traits.get('city')}, Belgium"

        return None

    def can_enrich(self, profile: dict) -> bool:
        """Check if profile can be enriched by Google Places."""
        # Need at least a company name
        # And ideally misses some key contact info we expect to find
        traits = profile.get("traits", {})

        has_name = bool(self._get_company_name(profile))

        needs_phone = not (traits.get("phone") or traits.get("contact_phone"))
        needs_website = not (traits.get("website_url") or traits.get("website"))

        return has_name and (needs_phone or needs_website)

    async def enrich_profile(self, profile: dict) -> dict:
        """Enrich profile with Google Places details."""
        self.stats.total += 1

        if not self.client.api_key:
            self.stats.skipped += 1
            return profile

        company_name = self._get_company_name(profile)
        if not company_name:
            self.stats.skipped += 1
            return profile

        address = self._get_address_string(profile)

        # Check cache
        cache_key = f"{company_name}_{address}" if address else company_name

        details = None
        cached = await self.cache.get(cache_key, default="MISS")
        if cached != "MISS":
            details = cached
        else:
            try:
                # Update cost approximation (Find Place ~0.017 + Details ~0.017)
                self.estimated_cost_usd += 0.034
                details = await self.client.enrich_company(company_name, address)
                # Cache regardless to avoid repeated failing calls
                await self.cache.set(cache_key, details)
            except Exception as e:
                logger.error(f"Google Places enrichment error for {company_name}: {e}")
                self.stats.failed += 1
                return profile

        if details:
            if "traits" not in profile:
                profile["traits"] = {}

            traits = profile["traits"]
            traits.setdefault("google_places", {})
            google_data = traits["google_places"]

            google_data["enriched_at"] = datetime.now(UTC).isoformat()

            # Apply phone if missing
            if "formatted_phone_number" in details:
                phone = details["formatted_phone_number"]
                if not (
                    traits.get("phone") or traits.get("contact_phone") or traits.get("telephone")
                ):
                    traits["phone"] = phone
                    traits["phone_source"] = "google_places"
                    traits["phone_discovered"] = True
                google_data["phone"] = phone

            # Apply website if missing
            if "website" in details:
                website = details["website"]
                if not (traits.get("website_url") or traits.get("website")):
                    traits["website_url"] = website
                    traits["website_verified"] = True
                    traits["website_discovery_method"] = "google_places"
                google_data["website"] = website

            # Hours
            if "current_opening_hours" in details:
                hours = details["current_opening_hours"].get("weekday_text", [])
                google_data["opening_hours"] = hours

            # Note: We aren't fully downloading or linking photos right now to save DB space,
            # but we can track if they exist.
            if "photos" in details and details["photos"]:
                google_data["photo_count"] = len(details["photos"])

            self.stats.success += 1
            logger.debug(f"Successfully enriched {company_name} from Google Places.")
        else:
            self.stats.failed += 1

        return profile
