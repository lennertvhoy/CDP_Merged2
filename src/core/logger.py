"""
Structured logging for CDP_Merged using structlog.

Provides JSON-formatted contextual logging with trace IDs.
Use get_logger(__name__) in every module instead of print().
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog for the application.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure stdlib logging as structlog's backend
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Quiet chatty third-party libraries
    for noisy in ("urllib3", "asyncio", "httpx", "httpcore", "hpack"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to the given name.

    Args:
        name: Module name, typically ``__name__``.

    Returns:
        A bound structlog logger.
    """
    return structlog.get_logger(name)


def bind_trace_id(trace_id: str) -> None:
    """Bind a trace ID to all log records in the current context.

    Args:
        trace_id: Unique request/session identifier.
    """
    structlog.contextvars.bind_contextvars(trace_id=trace_id)


def clear_trace_id() -> None:
    """Clear context vars (call at end of request)."""
    structlog.contextvars.clear_contextvars()
