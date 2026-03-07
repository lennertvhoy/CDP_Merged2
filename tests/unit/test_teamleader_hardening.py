"""Tests for Teamleader client hardening: pagination, rate limiting, retries."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.services.teamleader import (
    RateLimiter,
    TeamleaderClient,
    TeamleaderCredentials,
)


class TestRateLimiter:
    """Test the token bucket rate limiter."""

    def test_rate_limiter_allows_calls_under_limit(self) -> None:
        """Rate limiter should allow calls when under the limit."""
        limiter = RateLimiter(max_calls=5, window_seconds=60)

        # Should not block for first 5 calls
        start = time.time()
        for _ in range(5):
            limiter.acquire()
        elapsed = time.time() - start

        assert elapsed < 1.0  # Should be nearly instant
        assert len(limiter.calls) == 5

    def test_rate_limiter_tracks_calls_in_window(self) -> None:
        """Rate limiter should track calls within the window."""
        limiter = RateLimiter(max_calls=10, window_seconds=60)

        limiter.acquire()
        limiter.acquire()
        limiter.acquire()

        assert len(limiter.calls) == 3

    def test_rate_limiter_cleans_old_calls(self) -> None:
        """Rate limiter should clean calls outside the window."""
        limiter = RateLimiter(max_calls=5, window_seconds=1)

        # Add old call
        limiter.calls.append(time.time() - 2)  # 2 seconds ago
        limiter.calls.append(time.time())

        limiter._clean_old_calls()

        assert len(limiter.calls) == 1


class TestTeamleaderClientRetry:
    """Test retry logic and error handling."""

    @pytest.fixture
    def credentials(self) -> TeamleaderCredentials:
        return TeamleaderCredentials(
            client_id="test_client_id",
            client_secret="test_client_secret",
            refresh_token="test_refresh_token",
        )

    @pytest.fixture
    def client(self, credentials: TeamleaderCredentials) -> TeamleaderClient:
        return TeamleaderClient(
            credentials,
            max_retries=3,
            backoff_base=0.1,  # Fast backoff for tests
        )

    def test_successful_request_no_retry(self, client: TeamleaderClient) -> None:
        """Successful request should not retry."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch("httpx.post", return_value=mock_response):
            with patch.object(client, "access_token", "test_token"):
                response = client._request_with_retry("POST", "https://api.test/endpoint")

        assert response.status_code == 200

    def test_retry_on_500_error(self, client: TeamleaderClient) -> None:
        """Should retry on 500 errors with exponential backoff."""
        mock_error_response = MagicMock()
        mock_error_response.status_code = 500
        mock_error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_error_response
        )

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.raise_for_status.return_value = None

        with patch("httpx.post", side_effect=[mock_error_response, mock_success_response]):
            with patch.object(client, "access_token", "test_token"):
                response = client._request_with_retry("POST", "https://api.test/endpoint")

        assert response.status_code == 200

    def test_no_retry_on_400_error(self, client: TeamleaderClient) -> None:
        """Should not retry on 4xx client errors."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )

        with patch("httpx.post", return_value=mock_response):
            with patch.object(client, "access_token", "test_token"):
                with pytest.raises(httpx.HTTPStatusError):
                    client._request_with_retry("POST", "https://api.test/endpoint")

    def test_retry_on_rate_limit_429(self, client: TeamleaderClient) -> None:
        """Should retry on 429 rate limit with Retry-After header."""
        mock_rate_limit = MagicMock()
        mock_rate_limit.status_code = 429
        mock_rate_limit.headers = {"Retry-After": "1"}

        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.raise_for_status.return_value = None

        with patch("httpx.post", side_effect=[mock_rate_limit, mock_success]):
            with patch.object(client, "access_token", "test_token"):
                with patch("time.sleep") as mock_sleep:
                    response = client._request_with_retry("POST", "https://api.test/endpoint")

        assert response.status_code == 200
        mock_sleep.assert_called_once_with(1)

    def test_token_refresh_on_401(self, client: TeamleaderClient) -> None:
        """Should refresh token on 401 and retry."""
        mock_unauthorized = MagicMock()
        mock_unauthorized.status_code = 401
        mock_unauthorized.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_unauthorized
        )

        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.raise_for_status.return_value = None

        with patch("httpx.post", side_effect=[mock_unauthorized, mock_success]):
            with patch.object(client, "access_token", "test_token"):
                with patch.object(client, "refresh_access_token") as mock_refresh:
                    response = client._request_with_retry("POST", "https://api.test/endpoint")

        assert response.status_code == 200
        mock_refresh.assert_called_once()


class TestTeamleaderPagination:
    """Test automatic pagination."""

    @pytest.fixture
    def credentials(self) -> TeamleaderCredentials:
        return TeamleaderCredentials(
            client_id="test_client_id",
            client_secret="test_client_secret",
            refresh_token="test_refresh_token",
        )

    @pytest.fixture
    def client(self, credentials: TeamleaderCredentials) -> TeamleaderClient:
        return TeamleaderClient(credentials, max_retries=1)

    def test_list_all_records_pagination(self, client: TeamleaderClient) -> None:
        """Should iterate through all pages."""
        page1 = {
            "data": [{"id": "1"}, {"id": "2"}],
            "meta": {"page": {"total": 2}},
        }
        page2 = {
            "data": [{"id": "3"}, {"id": "4"}],
            "meta": {"page": {"total": 2}},
        }

        responses = [page1, page2]

        def mock_list_records(*args: object, **kwargs: object) -> dict:
            return responses.pop(0)

        with patch.object(client, "list_records", side_effect=mock_list_records):
            with patch.object(client, "access_token", "test_token"):
                records = list(client.list_all_records("companies.list", page_size=2))

        assert len(records) == 4
        assert [r["id"] for r in records] == ["1", "2", "3", "4"]

    def test_list_all_records_respects_max_pages(self, client: TeamleaderClient) -> None:
        """Should respect max_pages limit."""
        page1 = {
            "data": [{"id": "1"}],
            "meta": {"page": {"total": 10}},
        }

        with patch.object(client, "list_records", return_value=page1):
            with patch.object(client, "access_token", "test_token"):
                records = list(client.list_all_records("companies.list", max_pages=1))

        assert len(records) == 1

    def test_list_all_records_stops_on_empty(self, client: TeamleaderClient) -> None:
        """Should stop when no more records."""
        page1 = {
            "data": [{"id": "1"}],
            "meta": {"page": {"total": 2}},
        }
        page2 = {"data": [], "meta": {"page": {"total": 2}}}

        responses = [page1, page2]

        def mock_list_records(*args: object, **kwargs: object) -> dict:
            return responses.pop(0)

        with patch.object(client, "list_records", side_effect=mock_list_records):
            with patch.object(client, "access_token", "test_token"):
                records = list(client.list_all_records("companies.list"))

        assert len(records) == 1


class TestRateLimitStatus:
    """Test rate limit monitoring."""

    @pytest.fixture
    def client(self) -> TeamleaderClient:
        credentials = TeamleaderCredentials(
            client_id="test",
            client_secret="test",
            refresh_token="test",
        )
        return TeamleaderClient(credentials)

    def test_get_rate_limit_status(self, client: TeamleaderClient) -> None:
        """Should return current rate limit status."""
        # Simulate some calls
        client.rate_limiter.acquire()
        client.rate_limiter.acquire()

        status = client.get_rate_limit_status()

        assert status["calls_in_window"] == 2
        assert status["max_calls"] == 100
        assert status["remaining_calls"] == 98
