"""Production-ready Exact Online client with pagination, rate limiting, and retries."""

from __future__ import annotations

import os
import time
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

EXACT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env.exact"
EXACT_TOKEN_URL_TEMPLATE = "{base_url}/api/oauth2/token"
EXACT_API_BASE_URL_TEMPLATE = "{base_url}/api/v1/{division}"

# Rate limit configuration
DEFAULT_RATE_LIMIT_CALLS = 60  # requests per minute (Exact limit)
DEFAULT_RATE_LIMIT_WINDOW = 60  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 2.0  # seconds


def load_exact_env_file(path: Path = EXACT_ENV_PATH) -> bool:
    """Load simple KEY=VALUE pairs from the local Exact env file."""
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
    raise ValueError(f"Missing required Exact environment variable: {name}")


def _write_refresh_token(path: Path, refresh_token: str) -> None:
    if not path.exists():
        return

    lines = path.read_text().splitlines()
    updated_lines: list[str] = []
    replaced = False

    for line in lines:
        if line.startswith("EXACT_REFRESH_TOKEN="):
            updated_lines.append(f"EXACT_REFRESH_TOKEN={refresh_token}")
            replaced = True
        else:
            updated_lines.append(line)

    if not replaced:
        updated_lines.append(f"EXACT_REFRESH_TOKEN={refresh_token}")

    path.write_text("\n".join(updated_lines) + "\n")


def _write_tokens(path: Path, access_token: str, refresh_token: str, expires_at: float) -> None:
    """Update the .env.exact file with new access and refresh tokens."""
    if not path.exists():
        return

    lines = path.read_text().splitlines()
    updated_lines: list[str] = []
    access_replaced = False
    refresh_replaced = False
    expires_replaced = False

    for line in lines:
        if line.startswith("EXACT_ACCESS_TOKEN="):
            updated_lines.append(f"EXACT_ACCESS_TOKEN={access_token}")
            access_replaced = True
        elif line.startswith("EXACT_REFRESH_TOKEN="):
            updated_lines.append(f"EXACT_REFRESH_TOKEN={refresh_token}")
            refresh_replaced = True
        elif line.startswith("EXACT_TOKEN_EXPIRES_AT="):
            updated_lines.append(f"EXACT_TOKEN_EXPIRES_AT={expires_at}")
            expires_replaced = True
        else:
            updated_lines.append(line)

    # Add missing fields
    if not access_replaced:
        updated_lines.append(f"EXACT_ACCESS_TOKEN={access_token}")
    if not refresh_replaced:
        updated_lines.append(f"EXACT_REFRESH_TOKEN={refresh_token}")
    if not expires_replaced:
        updated_lines.append(f"EXACT_TOKEN_EXPIRES_AT={expires_at}")

    path.write_text("\n".join(updated_lines) + "\n")


@dataclass(frozen=True)
class ExactCredentials:
    """Credentials required for Exact Online OAuth2 auth."""

    client_id: str
    client_secret: str
    refresh_token: str
    access_token: str | None = None
    token_expires_at: float = 0
    base_url: str = "https://start.exactonline.be"
    division_id: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ExactCredentials:
        resolved_env = os.environ if env is None else env
        base_url = resolved_env.get("EXACT_BASE_URL", "https://start.exactonline.be")
        division_id = resolved_env.get("EXACT_DIVISION_ID")
        access_token = resolved_env.get("EXACT_ACCESS_TOKEN")
        expires_at_str = resolved_env.get("EXACT_TOKEN_EXPIRES_AT", "0")
        try:
            token_expires_at = float(expires_at_str)
        except (ValueError, TypeError):
            token_expires_at = 0
        return cls(
            client_id=_require_env("EXACT_CLIENT_ID", resolved_env),
            client_secret=_require_env("EXACT_CLIENT_SECRET", resolved_env),
            refresh_token=_require_env("EXACT_REFRESH_TOKEN", resolved_env),
            access_token=access_token,
            token_expires_at=token_expires_at,
            base_url=base_url,
            division_id=division_id,
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
            now = time.time()
            sleep_time = self.calls[0] + self.window_seconds - now
            if sleep_time > 0:
                time.sleep(sleep_time)
            self._clean_old_calls()

        self.calls.append(time.time())


class ExactClient:
    """Production-ready Exact Online client with pagination, rate limiting, and retries."""

    def __init__(
        self,
        credentials: ExactCredentials,
        *,
        env_path: Path = EXACT_ENV_PATH,
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
        # Use stored access token if available
        self.access_token: str | None = credentials.access_token
        self._token_expires_at: float = credentials.token_expires_at
        self._division_id: str | None = credentials.division_id

    @classmethod
    def is_configured(cls, env: Mapping[str, str] | None = None) -> bool:
        try:
            ExactCredentials.from_env(env)
        except ValueError:
            return False
        return True

    @classmethod
    def from_env(
        cls,
        *,
        env_path: Path = EXACT_ENV_PATH,
        timeout: float = 30.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> ExactClient:
        load_exact_env_file(env_path)
        credentials = ExactCredentials.from_env()
        return cls(credentials, env_path=env_path, timeout=timeout, max_retries=max_retries)

    @property
    def division_id(self) -> str:
        """Get the Exact division ID, auto-discovering if needed."""
        if self._division_id is None:
            self._discover_division()
        return self._division_id

    def _discover_division(self) -> None:
        """Auto-discover the division ID from the current user's context."""
        response = self._request_with_retry(
            "GET",
            f"{self.credentials.base_url}/api/v1/current/Me",
            is_token_refresh=False,
        )
        data = response.json()
        
        # Extract division from the first user's current division
        items = data.get("d", {}).get("results", [])
        if items:
            division = items[0].get("CurrentDivision")
            if division:
                self._division_id = str(int(division))  # Remove decimal
                # Update credentials with discovered division
                self.credentials = ExactCredentials(
                    client_id=self.credentials.client_id,
                    client_secret=self.credentials.client_secret,
                    refresh_token=self.credentials.refresh_token,
                    base_url=self.credentials.base_url,
                    division_id=self._division_id,
                )
                return
        
        raise RuntimeError("Could not auto-discover Exact division ID")

    def _get_api_base_url(self) -> str:
        """Get the API base URL with division."""
        return EXACT_API_BASE_URL_TEMPLATE.format(
            base_url=self.credentials.base_url,
            division=self.division_id,
        )

    def refresh_access_token(self) -> str:
        """Exchange the stored refresh token for a fresh access token."""
        import time
        
        token_url = EXACT_TOKEN_URL_TEMPLATE.format(base_url=self.credentials.base_url)
        response = httpx.post(
            token_url,
            data={
                "client_id": self.credentials.client_id,
                "client_secret": self.credentials.client_secret,
                "refresh_token": self.credentials.refresh_token,
                "grant_type": "refresh_token",
                "redirect_uri": self.credentials.base_url,  # Required by Exact
            },
            timeout=self.timeout,
        )
        
        # Handle "token not expired" - wait and retry once
        if response.status_code == 400 and "not expired" in response.text:
            # The existing token is still valid, but we don't have it.
            # Wait 2 seconds for the token to age, then retry
            time.sleep(2)
            response = httpx.post(
                token_url,
                data={
                    "client_id": self.credentials.client_id,
                    "client_secret": self.credentials.client_secret,
                    "refresh_token": self.credentials.refresh_token,
                    "grant_type": "refresh_token",
                    "redirect_uri": self.credentials.base_url,
                },
                timeout=self.timeout,
            )
            
        response.raise_for_status()
        payload = response.json()

        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_in = payload.get("expires_in", 600)
        
        if not access_token or not refresh_token:
            raise RuntimeError("Exact token response did not include both token fields")

        self.access_token = access_token
        self._token_expires_at = time.time() + expires_in - 60  # Refresh 60s before expiry
        
        self.credentials = ExactCredentials(
            client_id=self.credentials.client_id,
            client_secret=self.credentials.client_secret,
            refresh_token=refresh_token,
            access_token=access_token,
            token_expires_at=self._token_expires_at,
            base_url=self.credentials.base_url,
            division_id=self.credentials.division_id,
        )
        _write_tokens(self.env_path, access_token, refresh_token, self._token_expires_at)
        return access_token

    def _headers(self) -> dict[str, str]:
        import time
        
        # Refresh token if expired or not present
        if not self.access_token or time.time() >= self._token_expires_at:
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
                if 400 <= exc.response.status_code < 500 and exc.response.status_code != 429:
                    raise
                sleep_time = self.backoff_base * (2**attempt)
                time.sleep(sleep_time)

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exception = exc
                sleep_time = self.backoff_base * (2**attempt)
                time.sleep(sleep_time)

        if last_exception:
            raise last_exception
        raise RuntimeError(f"Request failed after {self.max_retries} retries")

    def get_records(
        self,
        endpoint: str,
        *,
        select: str | None = None,
        filter_query: str | None = None,
        orderby: str | None = None,
        skip: int = 0,
        top: int = 100,
    ) -> dict[str, Any]:
        """Call an Exact Online GET endpoint and return parsed JSON."""
        base_url = self._get_api_base_url()
        
        # Build OData query parameters
        params: list[str] = []
        if select:
            params.append(f"$select={select}")
        if filter_query:
            params.append(f"$filter={filter_query}")
        if orderby:
            params.append(f"$orderby={orderby}")
        if skip > 0:
            params.append(f"$skip={skip}")
        params.append(f"$top={top}")
        
        query_string = "&".join(params)
        url = f"{base_url}/{endpoint}?{query_string}"

        response = self._request_with_retry("GET", url)
        return response.json()

    def get_all_records(
        self,
        endpoint: str,
        *,
        select: str | None = None,
        filter_query: str | None = None,
        orderby: str | None = None,
        top: int = 100,
        max_records: int | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Iterate through all records from an Exact endpoint with automatic pagination."""
        skip = 0
        records_yielded = 0

        while True:
            response = self.get_records(
                endpoint,
                select=select,
                filter_query=filter_query,
                orderby=orderby,
                skip=skip,
                top=top,
            )

            # Exact returns data in "d" -> "results"
            data = response.get("d", {})
            records = data.get("results", [])
            
            if not records:
                break

            for record in records:
                if max_records is not None and records_yielded >= max_records:
                    return
                yield record
                records_yielded += 1

            # Check if there's a __next link for pagination
            if "__next" not in data:
                break

            skip += top

    def get_account(self, account_id: str) -> dict[str, Any] | None:
        """Get a single account by ID."""
        try:
            response = self.get_records(
                f"crm/Accounts(guid'{account_id}')",
                top=1,
            )
            results = response.get("d", {}).get("results", [])
            return results[0] if results else None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    def get_contact(self, contact_id: str) -> dict[str, Any] | None:
        """Get a single contact by ID."""
        try:
            response = self.get_records(
                f"crm/Contacts(guid'{contact_id}')",
                top=1,
            )
            results = response.get("d", {}).get("results", [])
            return results[0] if results else None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    def get_rate_limit_status(self) -> dict[str, int]:
        """Get current rate limiter status for monitoring."""
        self.rate_limiter._clean_old_calls()
        return {
            "calls_in_window": len(self.rate_limiter.calls),
            "max_calls": self.rate_limiter.max_calls,
            "window_seconds": self.rate_limiter.window_seconds,
            "remaining_calls": self.rate_limiter.max_calls - len(self.rate_limiter.calls),
        }
