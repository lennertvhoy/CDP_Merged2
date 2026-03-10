"""
Phase 3: Geocoding & Deduplication Hardening — Unit Tests

Covers:
1. GeocodingEnricher: rate limiting (≥1s delay between requests)
2. GeocodingEnricher: checkpoint/resume (already-geocoded profiles are skipped)
3. GeocodingEnricher: graceful fallback on TimeoutException
4. GeocodingEnricher: graceful fallback on ConnectError
5. DeduplicationEnricher: exact KBO match → flagged as duplicate
6. DeduplicationEnricher: fuzzy name match above threshold → flagged
7. DeduplicationEnricher: fuzzy name below threshold → not flagged
8. DeduplicationEnricher: winner election by most-complete traits
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.enrichment.deduplication import (
    DeduplicationEnricher,
    _address_similarity,
    _name_similarity,
    _normalise_name,
)
from src.enrichment.geocoding import GeocodingEnricher

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _geo_profile(
    profile_id: str,
    street: str = "Examplestraat 1",
    city: str = "Antwerpen",
    zipcode: str = "2000",
) -> dict:
    return {
        "id": profile_id,
        "traits": {
            "street": street,
            "city": city,
            "zipcode": zipcode,
            "country": "Belgium",
        },
    }


def _nominatim_response(lat: float = 51.2, lon: float = 4.4) -> list:
    return [
        {
            "lat": str(lat),
            "lon": str(lon),
            "display_name": "Test, Belgium",
            "osm_type": "way",
            "osm_id": "123",
            "category": "place",
            "type": "house",
            "importance": 0.5,
            "boundingbox": ["51.0", "51.4", "4.0", "4.8"],
        }
    ]


def _company_profile(
    profile_id: str,
    name: str,
    enterprise_number: str = "",
    street: str = "",
    city: str = "",
    extra_traits: dict | None = None,
) -> dict:
    traits: dict = {"name": name}
    if enterprise_number:
        traits["enterprise_number"] = enterprise_number
    if street:
        traits["street"] = street
    if city:
        traits["city"] = city
    if extra_traits:
        traits.update(extra_traits)
    return {"id": profile_id, "traits": traits}


# ──────────────────────────────────────────────────────────────────────────────
# GeocodingEnricher Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestGeocodingEnricher:
    """Tests for the hardened GeocodingEnricher."""

    @pytest.fixture
    def enricher(self, tmp_path: Path) -> GeocodingEnricher:
        return GeocodingEnricher(
            cache_dir=str(tmp_path / "cache"),
            cache_file="geo_test.json",
            checkpoint_dir=str(tmp_path / "progress"),
        )

    # ── Test 1: Rate limiting ─────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_rate_limit_delay_applied(self, enricher: GeocodingEnricher):
        """
        When two geocoding requests are made back-to-back, asyncio.sleep should
        be called to enforce at least the RATE_LIMIT_DELAY between them.
        """
        # Build two profiles targeting distinct addresses → two cache misses
        profiles = [
            _geo_profile("p-a", street="Kerkstraat 1", city="Brussel"),
            _geo_profile("p-b", street="Marktplein 5", city="Gent"),
        ]

        sleep_calls: list[float] = []

        # Mock the httpx response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _nominatim_response()

        async def _mock_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with (
            patch("src.enrichment.geocoding.asyncio.sleep", side_effect=_mock_sleep),
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        ):
            await enricher.enrich_batch(profiles)

        # At least one rate-limiting sleep should have occurred (between the two requests)
        assert len(sleep_calls) >= 1, (
            f"Expected at least one rate-limiting sleep call, got {sleep_calls}"
        )
        # The sleep duration should match the configured delay
        assert any(d <= enricher.RATE_LIMIT_DELAY for d in sleep_calls), (
            f"Expected a sleep ≤ {enricher.RATE_LIMIT_DELAY}s, got {sleep_calls}"
        )

    # ── Test 2: Checkpoint/resume ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_checkpoint_resume(self, enricher: GeocodingEnricher, tmp_path: Path):
        """
        Profiles whose IDs are already in the checkpoint should be skipped
        without making any Nominatim request.
        """
        # Simulate a previous run that geocoded p-1
        enricher._geocoded_ids.add("p-1")

        http_call_count = 0

        async def _counting_get(*args, **kwargs):
            nonlocal http_call_count
            http_call_count += 1
            mock = MagicMock()
            mock.raise_for_status = MagicMock()
            mock.json.return_value = _nominatim_response()
            return mock

        with patch("httpx.AsyncClient.get", side_effect=_counting_get):
            await enricher.enrich_batch(
                [
                    _geo_profile("p-1"),  # should be skipped
                    _geo_profile("p-2"),  # should be geocoded
                ]
            )

        # Only p-2 should trigger a real request
        assert http_call_count == 1, f"Expected 1 HTTP call (for p-2 only), got {http_call_count}"
        assert enricher.stats.skipped >= 1, "p-1 should have been skipped"

    # ── Test 3: Graceful fallback on TimeoutException ─────────────────────────

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self, enricher: GeocodingEnricher):
        """
        When Nominatim times out on all retries, the profile is returned
        unchanged (no exception propagated, stats.failed incremented).
        """
        profile = _geo_profile("p-timeout")
        dict(profile["traits"])

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = await enricher.enrich_profile(profile)

        # Profile returned unchanged (no geo fields injected)
        assert "geo_latitude" not in result.get("traits", {}), (
            "geo_latitude should NOT be present after a timeout failure"
        )
        assert enricher.stats.failed == 1, "stats.failed should be 1 after timeout"

    # ── Test 4: Graceful fallback on ConnectError ─────────────────────────────

    @pytest.mark.asyncio
    async def test_fallback_on_connect_error(self, enricher: GeocodingEnricher):
        """
        When Nominatim is unreachable (ConnectError), the pipeline should NOT
        raise — the profile is returned unchanged.
        """
        profile = _geo_profile("p-connect-err")

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("connection refused"),
        ):
            # Must not raise
            try:
                result = await enricher.enrich_profile(profile)
            except Exception as exc:
                pytest.fail(f"enrich_profile raised unexpectedly: {exc!r}")

        assert "geo_latitude" not in result.get("traits", {})
        assert enricher.stats.failed == 1

    def test_build_address_tolerates_nullable_zipcode_and_country(
        self, enricher: GeocodingEnricher
    ):
        profile = {
            "id": "p-nullable-address",
            "traits": {
                "street": "Examplestraat 1",
                "city": "Antwerpen",
                "zipcode": None,
                "country": None,
            },
        }

        assert enricher._build_address(profile) == "Examplestraat 1, Antwerpen, Belgium"


# ──────────────────────────────────────────────────────────────────────────────
# DeduplicationEnricher Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestDeduplicationEnricher:
    """Tests for DeduplicationEnricher."""

    @pytest.fixture
    def enricher(self, tmp_path: Path) -> DeduplicationEnricher:
        return DeduplicationEnricher(
            threshold=0.85,
            cache_dir=str(tmp_path),
            cache_file="dedup_test.json",
        )

    # ── Test 5: Exact KBO match ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_exact_kbo_match(self, enricher: DeduplicationEnricher):
        """
        Two profiles sharing the same enterprise_number are always duplicates,
        regardless of name similarity.
        """
        profiles = [
            _company_profile("p-1", "ACME NV", enterprise_number="BE0123456789"),
            _company_profile(
                "p-2", "Completely Different Name SA", enterprise_number="BE0123456789"
            ),
        ]

        result = await enricher.enrich_batch(profiles)

        # One of the two should be flagged as duplicate
        flagged = [p for p in result if p["traits"].get("is_duplicate")]
        assert len(flagged) == 1, f"Expected exactly 1 duplicate flagged, got {len(flagged)}"
        winner = [p for p in result if not p["traits"].get("is_duplicate")]
        assert len(winner) == 1
        assert winner[0]["traits"]["duplicate_count"] == 1
        assert flagged[0]["traits"]["duplicate_of"] == winner[0]["id"]

    # ── Test 6: Fuzzy name match above threshold ──────────────────────────────

    @pytest.mark.asyncio
    async def test_fuzzy_name_match_above_threshold(self, enricher: DeduplicationEnricher):
        """
        Near-identical company names (slight typo/abbreviation) should be
        identified as duplicates when above the similarity threshold.
        """
        profiles = [
            _company_profile(
                "p-1", "Antwerp Logistics NV", street="Havenstraat 1", city="Antwerpen"
            ),
            _company_profile(
                "p-2",
                "Antwerp Logistiks NV",  # one-character typo
                street="Havenstraat 1",
                city="Antwerpen",
            ),
        ]

        result = await enricher.enrich_batch(profiles)
        flagged = [p for p in result if p["traits"].get("is_duplicate")]
        assert len(flagged) == 1, (
            f"Expected 1 duplicate flagged for near-identical names, got {len(flagged)}"
        )

    # ── Test 7: Fuzzy name below threshold → not flagged ─────────────────────

    @pytest.mark.asyncio
    async def test_fuzzy_name_below_threshold(self, enricher: DeduplicationEnricher):
        """
        Clearly different company names should NOT be flagged as duplicates.
        """
        profiles = [
            _company_profile("p-1", "Antwerp Steel BVBA", city="Antwerpen"),
            _company_profile("p-2", "Brussels Software NV", city="Brussel"),
        ]

        result = await enricher.enrich_batch(profiles)
        flagged = [p for p in result if p["traits"].get("is_duplicate")]
        assert len(flagged) == 0, (
            f"Expected 0 duplicates for clearly different names, got {len(flagged)}"
        )

    # ── Test 8: Winner is most-complete record ────────────────────────────────

    @pytest.mark.asyncio
    async def test_merge_keeps_most_complete(self, enricher: DeduplicationEnricher):
        """
        When two profiles are duplicates, the one with more populated traits
        should be elected as the canonical (winner) record.
        """
        # p-1: sparse (only name + KBO)
        sparse = _company_profile("p-sparse", "ACME NV", enterprise_number="BE0999999999")
        # p-2: rich (name + KBO + email + phone + website)
        rich = _company_profile(
            "p-rich",
            "ACME NV",
            enterprise_number="BE0999999999",
            extra_traits={
                "email": "info@acme.be",
                "phone": "+32 3 123 45 67",
                "website": "https://acme.be",
                "city": "Antwerpen",
                "street": "Havenstraat 1",
            },
        )

        result = await enricher.enrich_batch([sparse, rich])

        winner = next(p for p in result if not p["traits"].get("is_duplicate"))
        loser = next(p for p in result if p["traits"].get("is_duplicate"))

        assert winner["id"] == "p-rich", (
            f"Expected 'p-rich' (more complete) to be the winner, got {winner['id']!r}"
        )
        assert loser["id"] == "p-sparse"
        assert loser["traits"]["duplicate_of"] == "p-rich"


# ──────────────────────────────────────────────────────────────────────────────
# Helper function unit tests
# ──────────────────────────────────────────────────────────────────────────────


class TestHelperFunctions:
    """Unit tests for normalisation and similarity helpers."""

    def test_normalise_strips_legal_suffix(self):
        assert "acme" in _normalise_name("ACME NV")
        assert "nv" not in _normalise_name("ACME NV")

    def test_normalise_case_insensitive(self):
        assert _normalise_name("Hello World") == _normalise_name("HELLO WORLD")

    def test_name_similarity_identical(self):
        assert _name_similarity("acme", "acme") == pytest.approx(1.0)

    def test_name_similarity_different(self):
        assert _name_similarity("acme", "banana") < 0.5

    def test_address_similarity_exact(self):
        traits = {"street": "Examplestraat 1", "city": "Antwerpen"}
        assert _address_similarity(traits, traits) == pytest.approx(1.0)

    def test_address_similarity_empty(self):
        assert _address_similarity({}, {}) == pytest.approx(0.0)
