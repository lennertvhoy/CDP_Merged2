"""
Geocoding enrichment via OpenStreetMap/Nominatim.

Rate limits: 1 request/second (free tier)
Adds latitude/longitude to addresses.

Phase 3 hardening:
- Retry with exponential backoff (3 attempts, 30s timeout)
- Resumable checkpoint support (save every 100 profiles)
- 30-day cache TTL (stored alongside geocode data)
- Graceful fallback: Nominatim failures skip the profile, never block pipeline
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from src.core.logger import get_logger
from src.enrichment.base import BaseEnricher

logger = get_logger(__name__)

# Cache TTL: 30 days (geocodes rarely change)
_CACHE_TTL_DAYS = 30
_CACHE_TTL = timedelta(days=_CACHE_TTL_DAYS)

# Retry configuration
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0  # seconds (doubles each retry)
_REQUEST_TIMEOUT = 30.0  # seconds per request


class GeocodingEnricher(BaseEnricher):
    """
    Geocode addresses using Nominatim (OpenStreetMap).

    Respects rate limit of 1 req/sec with built-in delays.
    Supports:
    - 30-day persistent cache
    - Checkpoint/resume (skips already-geocoded profiles)
    - Retry with exponential backoff
    - Graceful failure (never blocks pipeline)
    """

    API_URL = "https://nominatim.openstreetmap.org/search"
    RATE_LIMIT_DELAY = 1.1  # Slightly over 1s to be safe

    def __init__(
        self,
        cache_dir: str | None = "./data/cache",
        cache_file: str = "geocoding_cache.json",
        checkpoint_dir: str = "./data/progress",
        user_agent: str = "CDP_Merged_Bot/1.0",
        email: str | None = None,
        cache=None,
    ):
        super().__init__(cache_dir=cache_dir, cache_file=cache_file, cache=cache)
        self.user_agent = user_agent
        self.email = email
        self._last_request_time: datetime | None = None
        self._semaphore = asyncio.Semaphore(1)  # Sequential requests to Nominatim

        # Checkpoint support
        self._checkpoint_dir = Path(checkpoint_dir)
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_file = self._checkpoint_dir / "geocoding_checkpoint.json"
        self._geocoded_ids: set[str] = self._load_checkpoint()
        self._profiles_since_checkpoint = 0
        self._checkpoint_interval = 100

    # ──────────────────────────────────────────────────────────────────────────
    # Checkpoint helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _load_checkpoint(self) -> set[str]:
        """Load saved profile IDs that have already been geocoded."""
        if not self._checkpoint_file.exists():
            return set()
        try:
            data = json.loads(self._checkpoint_file.read_text())
            ids = set(data.get("geocoded_ids", []))
            logger.info(
                f"Geocoding checkpoint: resuming from {len(ids)} already-geocoded profiles"
            )
            return ids
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning(f"Could not read geocoding checkpoint: {e}")
            return set()

    def _save_checkpoint(self) -> None:
        """Persist the set of geocoded profile IDs to disk."""
        try:
            self._checkpoint_file.write_text(
                json.dumps(
                    {
                        "geocoded_ids": list(self._geocoded_ids),
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    indent=2,
                )
            )
        except OSError as e:
            logger.warning(f"Could not save geocoding checkpoint: {e}")

    def mark_geocoded(self, profile_id: str) -> None:
        """Mark a profile as geocoded and persist checkpoint every N profiles."""
        self._geocoded_ids.add(profile_id)
        self._profiles_since_checkpoint += 1
        if self._profiles_since_checkpoint >= self._checkpoint_interval:
            self._save_checkpoint()
            self._profiles_since_checkpoint = 0

    def is_already_geocoded(self, profile_id: str) -> bool:
        """Check if a profile was already geocoded in a previous run."""
        return profile_id in self._geocoded_ids

    def reset_checkpoint(self) -> None:
        """Clear the checkpoint (start fresh)."""
        self._geocoded_ids.clear()
        if self._checkpoint_file.exists():
            self._checkpoint_file.unlink()
        logger.info("Geocoding checkpoint cleared")

    # ──────────────────────────────────────────────────────────────────────────
    # Cache helpers (with 30-day TTL)
    # ──────────────────────────────────────────────────────────────────────────

    async def _cache_get(self, key: str) -> dict | None | str:
        """
        Get a cached geocode result, respecting 30-day TTL.

        Returns:
            - dict with geocode data if fresh cache hit
            - None if address was previously tried and returned no results
            - sentinel "MISS" if not in cache or TTL expired
        """
        entry = await self.cache.get(key, default="MISS")
        if entry == "MISS":
            return "MISS"

        # entry is wrapped: {"data": ..., "cached_at": "..."}
        if not isinstance(entry, dict) or "cached_at" not in entry:
            # Legacy entry without TTL metadata — treat as miss to refresh
            return "MISS"

        cached_at_str = entry.get("cached_at")
        if not isinstance(cached_at_str, str):
            return "MISS"
        try:
            cached_at = datetime.fromisoformat(cached_at_str)
            # Naive comparison
            if cached_at.tzinfo is not None:
                cached_at = cached_at.replace(tzinfo=None)
            if datetime.now(UTC) - cached_at > _CACHE_TTL:
                logger.debug(f"Cache entry expired (>30d) for key: {key[:40]}")
                return "MISS"
        except (ValueError, TypeError):
            return "MISS"

        return entry.get("data")  # May be None (cached miss) or a dict

    async def _cache_set(self, key: str, value: dict | None) -> None:
        """Store a geocode result with a timestamp for TTL enforcement."""
        entry = {
            "data": value,
            "cached_at": datetime.now(UTC).isoformat(),
        }
        await self.cache.set(key, entry)

    # ──────────────────────────────────────────────────────────────────────────
    # Nominatim request (rate-limited + retry)
    # ──────────────────────────────────────────────────────────────────────────

    async def _rate_limited_request(self, client: httpx.AsyncClient, params: dict) -> list:
        """
        Make a rate-limited request to Nominatim with retry and exponential backoff.

        Ensures ≥1.1s between requests. Retries up to _MAX_RETRIES times on
        transient errors. Returns raw JSON list from Nominatim, or [] on failure.

        Raises:
            httpx.TimeoutException: re-raised after all retries exhausted
            httpx.HTTPStatusError: re-raised on 4xx/5xx after retries
        """
        async with self._semaphore:
            # Rate limiting
            if self._last_request_time:
                elapsed = (datetime.now(UTC) - self._last_request_time).total_seconds()
                if elapsed < self.RATE_LIMIT_DELAY:
                    delay = self.RATE_LIMIT_DELAY - elapsed
                    logger.debug(f"Rate limiting: sleeping {delay:.2f}s")
                    await asyncio.sleep(delay)

            headers = {"User-Agent": self.user_agent}
            if self.email:
                headers["From"] = self.email

            last_exc: Exception | None = None
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    response = await client.get(
                        self.API_URL,
                        params=params,
                        headers=headers,
                        timeout=_REQUEST_TIMEOUT,
                    )
                    self._last_request_time = datetime.now(UTC)
                    response.raise_for_status()
                    return response.json()

                except httpx.TimeoutException as e:
                    last_exc = e
                    wait = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"Nominatim timeout (attempt {attempt}/{_MAX_RETRIES}), "
                        f"retrying in {wait:.1f}s"
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(wait)

                except httpx.HTTPStatusError as e:
                    last_exc = e
                    # 429 Too Many Requests — back off
                    if e.response.status_code == 429:
                        wait = _RETRY_BASE_DELAY * (2**attempt)
                        logger.warning(f"Nominatim rate-limited (429), backing off {wait:.1f}s")
                        if attempt < _MAX_RETRIES:
                            await asyncio.sleep(wait)
                    else:
                        # Non-transient HTTP error — don't retry
                        logger.warning(
                            f"HTTP error {e.response.status_code} from Nominatim: "
                            f"{e.response.text[:200]}"
                        )
                        raise

                except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
                    last_exc = e
                    wait = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"Nominatim connection error (attempt {attempt}/{_MAX_RETRIES}): "
                        f"{e} — retrying in {wait:.1f}s"
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(wait)

            # All retries exhausted
            raise last_exc  # type: ignore[misc]

    # ──────────────────────────────────────────────────────────────────────────
    # Address building
    # ──────────────────────────────────────────────────────────────────────────

    def _build_address(self, profile: dict) -> str | None:
        """Build address string from profile traits (handles Belgian formats)."""
        traits = profile.get("traits", {})

        street = (traits.get("street") or "").strip()
        zipcode = (traits.get("zipcode") or "").strip()
        city = (traits.get("city") or "").strip()
        country = (traits.get("country") or "Belgium").strip() or "Belgium"

        if not street or not city:
            return None

        # Belgian address formats:
        # "Examplestraat 67, 2000 Antwerpen, Belgium"
        # "Rue Example 45, 1050 Bruxelles, Belgium"
        parts: list[str] = [street]
        if zipcode:
            parts.append(f"{zipcode} {city}")
        else:
            parts.append(city)
        parts.append(country)

        return ", ".join(parts)

    def _get_cache_key(self, address: str) -> str:
        """Generate cache key for address."""
        return address.lower().strip()

    # ──────────────────────────────────────────────────────────────────────────
    # Public geocoding API
    # ──────────────────────────────────────────────────────────────────────────

    async def geocode_address(self, address: str) -> dict | None:
        """
        Geocode a single address string.

        Returns:
            Dict with lat/lon and metadata, or None if not found / on error.
        """
        cache_key = self._get_cache_key(address)

        cached = await self._cache_get(cache_key)
        if cached != "MISS":
            logger.debug(f"Cache hit for address: {address[:50]}")
            return (
                cached if not isinstance(cached, str) else None
            )  # May be None (cached miss) or a geocode dict

        params = {
            "q": address,
            "format": "json",
            "limit": 1,
            "countrycodes": "be",
            "addressdetails": 1,
        }

        async with httpx.AsyncClient() as client:
            try:
                data = await self._rate_limited_request(client, params)

                if not data:
                    logger.debug(f"No geocoding results for: {address[:50]}")
                    await self._cache_set(cache_key, None)
                    return None

                result = data[0]
                geocoded = {
                    "latitude": float(result["lat"]),
                    "longitude": float(result["lon"]),
                    "display_name": result.get("display_name"),
                    "osm_type": result.get("osm_type"),
                    "osm_id": result.get("osm_id"),
                    "category": result.get("category"),
                    "type": result.get("type"),
                    "importance": result.get("importance"),
                    "boundingbox": result.get("boundingbox"),
                }

                await self._cache_set(cache_key, geocoded)
                return geocoded

            except (KeyError, ValueError) as e:
                logger.error(f"Geocoding parse error for '{address[:50]}': {e}")
                return None

            except (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.RemoteProtocolError,
                httpx.RequestError,
            ) as e:
                # Graceful fallback: log and return None, don't raise
                logger.warning(f"Nominatim unreachable for '{address[:50]}': {e!r}")
                return None

    # ──────────────────────────────────────────────────────────────────────────
    # BaseEnricher interface
    # ──────────────────────────────────────────────────────────────────────────

    def can_enrich(self, profile: dict) -> bool:
        """Check if profile has enough address data to geocode."""
        traits = profile.get("traits", {})
        return bool(traits.get("street") and traits.get("city"))

    async def enrich_profile(self, profile: dict) -> dict:
        """
        Enrich a single profile with geocoding data.

        Skips profiles already in the checkpoint set.
        Gracefully handles Nominatim failures.
        """
        self.stats.total += 1

        profile_id = profile.get("id", "")

        # Resume support: skip already-geocoded profiles
        if profile_id and self.is_already_geocoded(profile_id):
            self.stats.skipped += 1
            logger.debug(f"Checkpoint hit, skipping profile {profile_id}")
            return profile

        if not self.can_enrich(profile):
            self.stats.skipped += 1
            return profile

        address = self._build_address(profile)
        if not address:
            self.stats.skipped += 1
            return profile

        try:
            geocoded = await self.geocode_address(address)

            if geocoded:
                if "traits" not in profile:
                    profile["traits"] = {}

                profile["traits"]["geo_latitude"] = geocoded["latitude"]
                profile["traits"]["geo_longitude"] = geocoded["longitude"]
                profile["traits"]["geo_display_name"] = geocoded["display_name"]
                profile["traits"]["geo_type"] = geocoded["type"]
                profile["traits"]["geo_importance"] = geocoded["importance"]
                profile["traits"]["geo_enriched_at"] = datetime.now(UTC).isoformat()
                profile["traits"]["geo_source"] = "nominatim"

                self.stats.success += 1
                logger.debug(
                    f"Geocoded: {address[:50]} → ({geocoded['latitude']}, {geocoded['longitude']})"
                )
            else:
                self.stats.failed += 1

        except Exception as e:
            # Safety net: never let a geocoding error crash the pipeline
            logger.error(f"Unexpected geocoding error for profile {profile_id}: {e}")
            self.stats.failed += 1

        finally:
            # Mark as processed in checkpoint (success or failure)
            if profile_id:
                self.mark_geocoded(profile_id)

        return profile

    def finish(self) -> None:
        """Flush checkpoint on pipeline completion."""
        super().finish()
        self._save_checkpoint()
        logger.info(
            f"GeocodingEnricher finished. "
            f"Checkpoint saved: {len(self._geocoded_ids)} total geocoded IDs."
        )
