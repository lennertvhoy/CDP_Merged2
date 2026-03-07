"""Unit tests for TracardiClient (all external calls mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.exceptions import TracardiError


class TestTracardiClientAuth:
    @pytest.mark.asyncio
    async def test_ensures_token_on_first_call(self):
        from src.services.tracardi import TracardiClient

        client = TracardiClient()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "test-token-123"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_http

            await client._ensure_token()

        assert client.token == "test-token-123"

    @pytest.mark.asyncio
    async def test_token_cached_on_second_call(self):
        from src.services.tracardi import TracardiClient

        client = TracardiClient()
        client.token = "already-have-token"  # Pre-set token

        # Should not call httpx at all
        with patch("httpx.AsyncClient") as mock_cls:
            await client._ensure_token()
            mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_auth_failure_raises_tracardi_error(self):
        from src.services.tracardi import TracardiClient

        client = TracardiClient()

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "401", request=MagicMock(), response=mock_response
                )
            )
            mock_client_cls.return_value = mock_http

            with pytest.raises(TracardiError):
                await client._ensure_token()


class TestTracardiClientSearch:
    @pytest.mark.asyncio
    async def test_search_wildcard_uses_metadata_time_query(self):
        from src.services.tracardi import TRACARDI_MATCH_ALL_QUERY, TracardiClient

        client = TracardiClient()
        client.token = "test-token"
        client.headers["Authorization"] = "Bearer test-token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"total": 9, "result": [{"id": "p1"}]}

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_http

            result = await client.search_profiles("*", limit=1)

        assert result["total"] == 9
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["where"] == TRACARDI_MATCH_ALL_QUERY

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        from src.services.tracardi import TracardiClient

        client = TracardiClient()
        client.token = "test-token"
        client.headers["Authorization"] = "Bearer test-token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"total": 2, "result": [{"id": "p1"}, {"id": "p2"}]}

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_http

            result = await client.search_profiles('traits.city="Gent"')

        assert result["total"] == 2
        assert len(result["result"]) == 2

    @pytest.mark.asyncio
    async def test_search_404_raises_tracardi_error(self):
        from src.services.tracardi import TracardiClient

        client = TracardiClient()
        client.token = "test-token"
        client.headers["Authorization"] = "Bearer test-token"

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_http

            with pytest.raises(TracardiError) as exc:
                await client.search_profiles('traits.city="Gent"')

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_search_500_raises_tracardi_error(self):
        from src.services.tracardi import TracardiClient

        client = TracardiClient()
        client.token = "test-token"
        client.headers["Authorization"] = "Bearer test-token"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "parser error"

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_http

            with pytest.raises(TracardiError):
                await client.search_profiles('traits.name CONSIST "bakery"')


class TestTracardiCreateSegment:
    @pytest.mark.asyncio
    async def test_create_segment_returns_count(self):
        from src.services.tracardi import TracardiClient

        client = TracardiClient()
        # Mock search_profiles and add_profile_to_segment
        client.search_profiles = AsyncMock(
            return_value={"total": 2, "result": [{"id": "p1"}, {"id": "p2"}]}
        )
        client.add_profile_to_segment = AsyncMock(return_value=True)

        result = await client.create_segment("test-seg", condition='traits.city="Gent"')

        assert result["profiles_added"] == 2
        assert result["name"] == "test-seg"
