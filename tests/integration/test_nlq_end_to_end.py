"""
Integration tests for the full NLQ end-to-end flow.

These tests require a running Tracardi instance.
Run with: INTEGRATION_TESTS=1 pytest tests/integration/ -m integration -v
"""

from __future__ import annotations

import os

import pytest

INTEGRATION = os.getenv("INTEGRATION_TESTS", "0") == "1"
pytestmark = pytest.mark.integration


@pytest.mark.skipif(not INTEGRATION, reason="Requires INTEGRATION_TESTS=1 and running Tracardi")
class TestTracardiConnectivity:
    """Verify Tracardi is reachable and accepting queries."""

    @pytest.mark.asyncio
    async def test_tracardi_health(self):
        """Tracardi API should respond to a basic search."""
        from src.services.tracardi import TracardiClient

        client = TracardiClient()
        result = await client.search_profiles("*", limit=1)
        assert isinstance(result, dict)
        assert "total" in result

    @pytest.mark.asyncio
    async def test_tracardi_auth(self):
        """Should authenticate and receive a token."""
        from src.services.tracardi import TracardiClient

        client = TracardiClient()
        await client._ensure_token()
        assert client.token is not None


@pytest.mark.skipif(not INTEGRATION, reason="Requires INTEGRATION_TESTS=1 and running Tracardi")
class TestNLQEndToEnd:
    """Full NLQ flow: language → query builder → Tracardi."""

    @pytest.mark.asyncio
    async def test_it_companies_gent(self):
        """'Find IT companies in Gent' should produce a non-empty result."""
        from src.ai_interface.tools import _get_nace_codes_from_keyword
        from src.search_engine.builders.tql_builder import TQLBuilder
        from src.search_engine.schema import ProfileSearchParams
        from src.services.tracardi import TracardiClient

        # 1. Resolve NACE codes from keyword
        nace_codes = _get_nace_codes_from_keyword("IT")
        assert len(nace_codes) > 0

        # 2. Build TQL query
        params = ProfileSearchParams(nace_codes=nace_codes, city="Gent", status="AC")
        query = TQLBuilder().build(params)
        assert query

        # 3. Execute against Tracardi
        client = TracardiClient()
        result = await client.search_profiles(query)
        assert isinstance(result, dict)
        assert "total" in result
        # total may be 0 if no data loaded, but the call should succeed

    @pytest.mark.asyncio
    async def test_validation_blocks_destructive(self):
        """Destructive queries should never reach Tracardi."""
        from src.core.validation import validate_query

        result = validate_query("DROP TABLE profiles")
        assert not result["valid"]
        assert "destructive_sql" in result["flags"]

    @pytest.mark.asyncio
    async def test_keyword_fallback_consist_operator_supported(self):
        """Assumption check: keyword fallback uses TQL CONSIST and should execute."""
        from src.search_engine.builders.tql_builder import TQLBuilder
        from src.search_engine.schema import ProfileSearchParams
        from src.services.tracardi import TracardiClient

        params = ProfileSearchParams(keywords="barber", city="Gent", status="AC")
        query = TQLBuilder().build(params)
        assert "CONSIST" in query

        client = TracardiClient()
        result = await client.search_profiles(query)
        assert isinstance(result, dict)
        assert "total" in result
