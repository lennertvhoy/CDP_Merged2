"""
Phase 2: Intelligence Layer — Unit Tests

Covers:
1. DescriptionEnricher: choices[0] indexing bug fix
2. DescriptionEnricher: L1 cache hit skips HTTP
3. DescriptionEnricher: profiles lacking NACE codes are skipped
4. WebsiteDiscoveryEnricher: email domain tried before name-pattern candidates
5. WebsiteDiscoveryEnricher: None written to cache on total miss
6. WebsiteDiscoveryEnricher: rate limiter invoked during enrich_batch
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.enrichment.descriptions import DescriptionEnricher, _nace_label
from src.enrichment.website_discovery import WebsiteDiscoveryEnricher

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _profile_with_nace(nace_codes: list[str], name: str = "Test Co") -> dict:
    return {"id": "p-1", "traits": {"name": name, "nace_codes": nace_codes}}


def _profile_with_email_name(email: str, name: str) -> dict:
    return {"id": "p-2", "traits": {"name": name, "email": email}}


def _openai_response(text: str) -> MagicMock:
    """Build a minimal mock httpx.Response wrapping an OpenAI-style payload."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 80, "completion_tokens": 40},
    }
    return mock_resp


# ──────────────────────────────────────────────────────────────────────────────
# DescriptionEnricher tests
# ──────────────────────────────────────────────────────────────────────────────


class TestDescriptionEnricher:
    """Tests for DescriptionEnricher (descriptions.py)."""

    @pytest.fixture
    def enricher(self, tmp_path: Path) -> DescriptionEnricher:
        """Return a DescriptionEnricher with a real SQLite cache in a temp dir."""
        e = DescriptionEnricher(
            cache_dir=str(tmp_path),
            cache_file="test_desc_cache.json",
            endpoint="https://fake.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4o-mini",
        )
        return e

    # ── Test 1: choices[0] bug is fixed ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_choices_indexing_bug_fixed(self, enricher: DescriptionEnricher):
        """
        Before the fix, data["choices"]["message"] raised TypeError because
        choices is a list. This test confirms the generated description is
        returned instead of None (which would happen if an exception were swallowed).
        """
        profile = _profile_with_nace(["62010"])

        mock_resp = _openai_response("Test Co offers software consulting services.")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await enricher.enrich_profile(profile)

        assert result["traits"].get("business_description") == (
            "Test Co offers software consulting services."
        ), "Description should be populated; a TypeError would have silently dropped it."

    # ── Test 2: L1 cache hit skips HTTP call ─────────────────────────────────

    @pytest.mark.asyncio
    async def test_cache_hit_skips_http(self, enricher: DescriptionEnricher):
        """When the NACE key is already in L1 cache, no HTTP call should occur."""
        nace_codes = ["46190"]
        cache_key = enricher._get_cache_key(nace_codes)
        await enricher.cache.set(cache_key, "Cached description from previous run.")

        profile = _profile_with_nace(nace_codes)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            result = await enricher.enrich_profile(profile)
            mock_post.assert_not_called()

        assert result["traits"]["business_description"] == "Cached description from previous run."
        # After Bug #2 fix, enrich_profile delegates caching fully to generate_description().
        # The source tag is "azure_openai" whether the value came from cache or a live call.
        assert result["traits"]["business_description_source"] == "azure_openai"

    # ── Test 3: profile with no NACE codes is skipped ────────────────────────

    @pytest.mark.asyncio
    async def test_no_nace_codes_skipped(self, enricher: DescriptionEnricher):
        """can_enrich() returns False for profiles without NACE codes."""
        profile = {"id": "p-bare", "traits": {"name": "No NACE Corp"}}

        assert enricher.can_enrich(profile) is False

        result = await enricher.enrich_profile(profile)
        assert "business_description" not in result.get("traits", {})
        assert enricher.stats.skipped == 1

    # ── Unit test: NACE label helper ─────────────────────────────────────────

    def test_nace_label_known_prefix(self):
        assert _nace_label("62010") == "62010 (software & IT services)"

    def test_nace_label_unknown_prefix(self):
        assert _nace_label("99999") == "99999"


# ──────────────────────────────────────────────────────────────────────────────
# WebsiteDiscoveryEnricher tests
# ──────────────────────────────────────────────────────────────────────────────


class TestWebsiteDiscoveryEnricher:
    """Tests for WebsiteDiscoveryEnricher (website_discovery.py)."""

    @pytest.fixture
    def enricher(self, tmp_path: Path) -> WebsiteDiscoveryEnricher:
        return WebsiteDiscoveryEnricher(
            cache_dir=str(tmp_path),
            cache_file="test_website_cache.json",
            timeout=5.0,
        )

    # ── Test 4: email domain is probed before name-pattern candidates ─────────

    @pytest.mark.asyncio
    async def test_email_domain_priority(self, enricher: WebsiteDiscoveryEnricher):
        """
        discover_website() should try the email-derived domain first.
        We mock _check_website to succeed only for the email-based URL so that,
        if the email-first branch is skipped, the test returns None.
        """

        async def _fake_check(url: str):
            if "acme.be" in url:
                return {"url": url, "status_code": 200, "method": "HEAD"}
            return None

        enricher._check_website = _fake_check  # type: ignore[method-assign]

        result = await enricher.discover_website("ACME BVBA", email="info@acme.be")

        assert result is not None
        assert "acme.be" in result["url"]

    # ── Test 5: None written to cache on full miss ────────────────────────────

    @pytest.mark.asyncio
    async def test_miss_written_to_cache(self, enricher: WebsiteDiscoveryEnricher):
        """
        When no URL validates, None should be stored in cache so repeated calls
        for the same company don't trigger live HTTP requests on every run.
        """

        async def _always_none(url: str):
            return None

        enricher._check_website = _always_none  # type: ignore[method-assign]

        result = await enricher.discover_website("Unknown Corp XYZ123")
        assert result is None

        # The miss should now be persisted in the cache
        cache_key = "Unknown Corp XYZ123_None"
        cached = await enricher.cache.get(cache_key, default="MISS")
        # Cache should hold the explicit None (serialised as JSON null), not "MISS"
        assert cached is None  # json.loads("null") → None, distinct from sentinel "MISS"

    # ── Test 6: rate limiter acquire() is called during enrich_batch ─────────

    @pytest.mark.asyncio
    async def test_rate_limiter_invoked(self, tmp_path: Path):
        """
        After wiring, enricher.rate_limiter should not be None and its
        acquire() method should be called at least once during enrich_batch().
        """
        e = WebsiteDiscoveryEnricher(
            cache_dir=str(tmp_path),
            cache_file="rl_test.json",
        )

        # Replace rate_limiter with a spy
        mock_limiter = AsyncMock()
        e.rate_limiter = mock_limiter

        # Stub enrich_profile so we don't do real HTTP
        async def _stub_enrich(profile: dict) -> dict:
            return profile

        e.enrich_profile = _stub_enrich  # type: ignore[method-assign]

        profiles = [
            _profile_with_email_name("a@acme.be", "Acme NV"),
            _profile_with_email_name("b@beta.be", "Beta BVBA"),
        ]
        await e.enrich_batch(profiles)

        mock_limiter.acquire.assert_called()
        call_count = mock_limiter.acquire.call_count
        assert call_count >= 1, f"Expected rate limiter to be called, got {call_count} calls"
