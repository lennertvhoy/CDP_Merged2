"""
Base service class with shared retry logic and logging for CDP_Merged.
"""

from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.core.constants import MAX_RETRIES, RETRY_MAX_WAIT, RETRY_MIN_WAIT
from src.core.logger import get_logger

logger = get_logger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Return True if the exception warrants a retry.

    Retries on network errors and 5xx HTTP status errors.
    Does NOT retry on 4xx errors (client mistakes).
    """
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def with_retry(func=None):
    """Decorator that applies exponential-backoff retry logic.

    Retry up to MAX_RETRIES times on transient errors (network failures,
    5xx responses). 4xx responses are not retried.
    """
    decorator = retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        reraise=True,
    )
    if func is not None:
        return decorator(func)
    return decorator


class BaseService:
    """Abstract base for external service clients.

    Provides structured logging and a shared retry decorator.
    Subclasses should call super().__init__() and use self.logger.
    """

    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        self.logger = get_logger(f"src.services.{service_name}")

    def log_error(
        self,
        method: str,
        error: Exception,
        status_code: int | None = None,
    ) -> None:
        """Log a service call failure with structured context."""
        self.logger.error(
            "service_call_failed",
            service=self.service_name,
            method=method,
            error=str(error),
            status_code=status_code,
        )

    def log_success(self, method: str, **extra) -> None:
        """Log a successful service call."""
        self.logger.info(
            "service_call_success",
            service=self.service_name,
            method=method,
            **extra,
        )
