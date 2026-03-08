"""Production-ready Teamleader Focus client with pagination, rate limiting, and retries."""

from __future__ import annotations

import os
import time
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

TEAMLEADER_ENV_PATH = Path(__file__).resolve().parents[2] / ".env.teamleader"
TEAMLEADER_TOKEN_URL = "https://app.teamleader.eu/oauth2/access_token"
TEAMLEADER_API_BASE_URL = "https://api.focus.teamleader.eu"

# Rate limit configuration
DEFAULT_RATE_LIMIT_CALLS = 100  # requests per window
DEFAULT_RATE_LIMIT_WINDOW = 60  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 2.0  # seconds


def load_teamleader_env_file(path: Path = TEAMLEADER_ENV_PATH) -> bool:
    """Load simple KEY=VALUE pairs from the local Teamleader env file."""
    if not path.exists():
        return False

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'")
        os.environ.setdefault(key.strip(), value)

    return True


def _require_env(name: str, env: Mapping[str, str]) -> str:
    value = env.get(name)
    if value:
        return value
    raise ValueError(f"Missing required Teamleader environment variable: {name}")


def _write_refresh_token(path: Path, refresh_token: str) -> None:
    if not path.exists():
        return

    lines = path.read_text().splitlines()
    updated_lines: list[str] = []
    replaced = False

    for line in lines:
        if line.startswith("TEAMLEADER_REFRESH_TOKEN="):
            updated_lines.append(f"TEAMLEADER_REFRESH_TOKEN={refresh_token}")
            replaced = True
        else:
            updated_lines.append(line)

    if not replaced:
        updated_lines.append(f"TEAMLEADER_REFRESH_TOKEN={refresh_token}")

    path.write_text("\n".join(updated_lines) + "\n")


@dataclass(frozen=True)
class TeamleaderCredentials:
    """Credentials required for Teamleader refresh-token auth."""

    client_id: str
    client_secret: str
    refresh_token: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> TeamleaderCredentials:
        resolved_env = os.environ if env is None else env
        return cls(
            client_id=_require_env("TEAMLEADER_CLIENT_ID", resolved_env),
            client_secret=_require_env("TEAMLEADER_CLIENT_SECRET", resolved_env),
            refresh_token=_require_env("TEAMLEADER_REFRESH_TOKEN", resolved_env),
        )


class RateLimiter:
    """Simple token bucket rate limiter for API calls."""

    def __init__(
        self,
        max_calls: int = DEFAULT_RATE_LIMIT_CALLS,
        window_seconds: int = DEFAULT_RATE_LIMIT_WINDOW,
    ) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls: list[float] = []

    def _clean_old_calls(self) -> None:
        """Remove calls outside the current window."""
        now = time.time()
        cutoff = now - self.window_seconds
        self.calls = [call_time for call_time in self.calls if call_time > cutoff]

    def acquire(self) -> None:
        """Wait if necessary to stay within rate limits."""
        self._clean_old_calls()

        if len(self.calls) >= self.max_calls:
            # Need to wait until the oldest call expires
            now = time.time()
            sleep_time = self.calls[0] + self.window_seconds - now
            if sleep_time > 0:
                time.sleep(sleep_time)
            self._clean_old_calls()

        self.calls.append(time.time())


class TeamleaderClient:
    """Production-ready Teamleader client with pagination, rate limiting, and retries."""

    def __init__(
        self,
        credentials: TeamleaderCredentials,
        *,
        env_path: Path = TEAMLEADER_ENV_PATH,
        timeout: float = 30.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        rate_limit_calls: int = DEFAULT_RATE_LIMIT_CALLS,
        rate_limit_window: int = DEFAULT_RATE_LIMIT_WINDOW,
    ) -> None:
        self.credentials = credentials
        self.env_path = env_path
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.rate_limiter = RateLimiter(rate_limit_calls, rate_limit_window)
        self.access_token: str | None = None

    @classmethod
    def is_configured(cls, env: Mapping[str, str] | None = None) -> bool:
        try:
            TeamleaderCredentials.from_env(env)
        except ValueError:
            return False
        return True

    @classmethod
    def from_env(
        cls,
        *,
        env_path: Path = TEAMLEADER_ENV_PATH,
        timeout: float = 30.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> TeamleaderClient:
        load_teamleader_env_file(env_path)
        credentials = TeamleaderCredentials.from_env()
        return cls(credentials, env_path=env_path, timeout=timeout, max_retries=max_retries)

    def refresh_access_token(self) -> str:
        """Exchange the stored refresh token for a fresh access token."""
        response = httpx.post(
            TEAMLEADER_TOKEN_URL,
            data={
                "client_id": self.credentials.client_id,
                "client_secret": self.credentials.client_secret,
                "refresh_token": self.credentials.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        if not access_token or not refresh_token:
            raise RuntimeError("Teamleader token response did not include both token fields")

        self.access_token = access_token
        self.credentials = TeamleaderCredentials(
            client_id=self.credentials.client_id,
            client_secret=self.credentials.client_secret,
            refresh_token=refresh_token,
        )
        _write_refresh_token(self.env_path, refresh_token)
        return access_token

    def _headers(self) -> dict[str, str]:
        if not self.access_token:
            self.refresh_access_token()

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        is_token_refresh: bool = False,
    ) -> httpx.Response:
        """Make HTTP request with rate limiting, retries, and exponential backoff."""
        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            # Apply rate limiting (skip for token refresh to avoid deadlock)
            if not is_token_refresh:
                self.rate_limiter.acquire()

            try:
                if method.upper() == "POST":
                    response = httpx.post(
                        url,
                        headers=self._headers(),
                        json=json,
                        timeout=self.timeout,
                    )
                else:
                    response = httpx.get(
                        url,
                        headers=self._headers(),
                        timeout=self.timeout,
                    )

                # Handle rate limit (429) with automatic retry
                if response.status_code == 429:
                    retry_after = int(
                        response.headers.get("Retry-After", self.backoff_base * (attempt + 1))
                    )
                    time.sleep(retry_after)
                    continue

                # Handle unauthorized (401) by refreshing token once
                if response.status_code == 401 and not is_token_refresh:
                    self.refresh_access_token()
                    # Retry immediately with new token
                    if method.upper() == "POST":
                        response = httpx.post(
                            url,
                            headers=self._headers(),
                            json=json,
                            timeout=self.timeout,
                        )
                    else:
                        response = httpx.get(
                            url,
                            headers=self._headers(),
                            timeout=self.timeout,
                        )

                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as exc:
                last_exception = exc
                # Don't retry on 4xx errors (except 429 handled above)
                if 400 <= exc.response.status_code < 500 and exc.response.status_code != 429:
                    raise
                # Exponential backoff for 5xx errors
                sleep_time = self.backoff_base * (2**attempt)
                time.sleep(sleep_time)

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exception = exc
                # Exponential backoff for transient errors
                sleep_time = self.backoff_base * (2**attempt)
                time.sleep(sleep_time)

        # All retries exhausted
        if last_exception:
            raise last_exception
        raise RuntimeError(f"Request failed after {self.max_retries} retries")

    def list_records(
        self,
        endpoint: str,
        *,
        page_size: int = 10,
        page_number: int = 1,
        extra_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a Teamleader list endpoint and return the parsed JSON payload."""
        payload: dict[str, Any] = {"page": {"size": page_size, "number": page_number}}
        if extra_payload:
            payload.update(extra_payload)

        response = self._request_with_retry(
            "POST",
            f"{TEAMLEADER_API_BASE_URL}/{endpoint}",
            json=payload,
        )
        return response.json()

    def list_all_records(
        self,
        endpoint: str,
        *,
        page_size: int = 100,
        extra_payload: dict[str, Any] | None = None,
        max_pages: int | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Iterate through all pages of a Teamleader list endpoint.

        Args:
            endpoint: API endpoint (e.g., "companies.list")
            page_size: Number of records per page (max 100)
            extra_payload: Additional payload parameters
            max_pages: Maximum pages to fetch (None for all)

        Yields:
            Individual records from all pages
        """
        page_number = 1
        pages_fetched = 0

        while True:
            if max_pages is not None and pages_fetched >= max_pages:
                break

            response = self.list_records(
                endpoint,
                page_size=page_size,
                page_number=page_number,
                extra_payload=extra_payload,
            )

            records = response.get("data") or []
            yield from records

            pages_fetched += 1

            # Check if there are more pages
            pagination = response.get("meta", {}).get("page", {})
            total_pages = pagination.get("total", page_number)

            if page_number >= total_pages or not records:
                break

            page_number += 1

    def first_record(self, endpoint: str) -> dict[str, Any] | None:
        """Return the first record from a list endpoint, if present."""
        payload = self.list_records(endpoint, page_size=1, page_number=1)
        records = payload.get("data") or []
        return records[0] if records else None

    def get_rate_limit_status(self) -> dict[str, int]:
        """Get current rate limiter status for monitoring."""
        self.rate_limiter._clean_old_calls()
        return {
            "calls_in_window": len(self.rate_limiter.calls),
            "max_calls": self.rate_limiter.max_calls,
            "window_seconds": self.rate_limiter.window_seconds,
            "remaining_calls": self.rate_limiter.max_calls - len(self.rate_limiter.calls),
        }

    def create_record(
        self,
        endpoint: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new record via Teamleader API.
        
        Args:
            endpoint: API endpoint (e.g., "companies.add", "contacts.add", "deals.add")
            data: Record data to create
            
        Returns:
            Created record with ID
        """
        response = self._request_with_retry(
            "POST",
            f"{TEAMLEADER_API_BASE_URL}/{endpoint}",
            json=data,
        )
        return response.json()

    def add_company(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new company in Teamleader.
        
        Args:
            data: Company data with name, address, etc.
            
        Returns:
            Created company record
        """
        return self.create_record("companies.add", data)

    def add_contact(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new contact in Teamleader.
        
        Args:
            data: Contact data with first_name, last_name, email, etc.
            
        Returns:
            Created contact record
        """
        return self.create_record("contacts.add", data)

    def add_deal(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new deal in Teamleader.
        
        Args:
            data: Deal data with title, estimated_value, company_id, etc.
            
        Returns:
            Created deal record
        """
        return self.create_record("deals.add", data)

    async def initialize(self) -> None:
        """Initialize the client by refreshing access token.
        
        This is a convenience method for async initialization.
        """
        self.refresh_access_token()
