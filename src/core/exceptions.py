"""
Custom exception hierarchy for CDP_Merged.

All application-specific exceptions inherit from CDPError,
allowing callers to catch either broad or specific error types.
"""

from __future__ import annotations


class CDPError(Exception):
    """Base exception for all CDP_Merged errors."""

    def __init__(self, message: str, context: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict = context or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"


# ─── Configuration ────────────────────────────────────────────────────────────


class ConfigurationError(CDPError):
    """Raised when required configuration is missing or invalid."""


# ─── Validation ───────────────────────────────────────────────────────────────


class ValidationError(CDPError):
    """Raised when a user query fails security or format validation."""

    def __init__(self, message: str, flags: list[str] | None = None, **kwargs) -> None:
        super().__init__(message, **kwargs)
        self.flags: list[str] = flags or []


# ─── External Services ────────────────────────────────────────────────────────


class TracardiError(CDPError):
    """Raised when a Tracardi API call fails."""

    def __init__(self, message: str, status_code: int | None = None, **kwargs) -> None:
        super().__init__(message, **kwargs)
        self.status_code = status_code


class FlexmailError(CDPError):
    """Raised when a Flexmail API call fails."""

    def __init__(self, message: str, status_code: int | None = None, **kwargs) -> None:
        super().__init__(message, **kwargs)
        self.status_code = status_code


class ResendError(CDPError):
    """Raised when a Resend API call fails."""

    def __init__(self, message: str, status_code: int | None = None, **kwargs) -> None:
        super().__init__(message, **kwargs)
        self.status_code = status_code


# ─── LLM ─────────────────────────────────────────────────────────────────────


class LLMError(CDPError):
    """Raised when an LLM provider call fails."""

    def __init__(self, message: str, provider: str | None = None, **kwargs) -> None:
        super().__init__(message, **kwargs)
        self.provider = provider


# ─── Timeouts ─────────────────────────────────────────────────────────────────


class QueryTimeoutError(CDPError):
    """Raised when a query or LLM call exceeds the configured timeout."""
