"""
Prometheus metrics for CDP_Merged.

Import and use the counters/histograms in app.py and graph nodes
to track request performance and error rates.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram, start_http_server

# ─── Request metrics ──────────────────────────────────────────────────────────

QUERY_REQUESTS_TOTAL = Counter(
    "cdp_query_requests_total",
    "Total number of NLQ requests received",
    ["status"],  # labels: success, error
)

QUERY_DURATION_SECONDS = Histogram(
    "cdp_query_duration_seconds",
    "Time spent processing a query end-to-end",
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

# ─── LLM metrics ─────────────────────────────────────────────────────────────

LLM_REQUESTS_TOTAL = Counter(
    "cdp_llm_requests_total",
    "Total LLM API calls",
    ["provider", "status"],
)

# ─── Tracardi metrics ─────────────────────────────────────────────────────────

TRACARDI_REQUESTS_TOTAL = Counter(
    "cdp_tracardi_requests_total",
    "Total Tracardi API calls",
    ["method", "status"],
)

SEGMENT_CREATIONS_TOTAL = Counter(
    "cdp_segment_creations_total",
    "Total segments created",
    ["status"],
)

# ─── Flexmail metrics ─────────────────────────────────────────────────────────

FLEXMAIL_PUSH_TOTAL = Counter(
    "cdp_flexmail_push_total",
    "Total Flexmail push operations",
    ["status"],
)

FLEXMAIL_CONTACTS_PUSHED = Counter(
    "cdp_flexmail_contacts_pushed_total",
    "Total individual contacts pushed to Flexmail",
)

# ─── Error metrics ────────────────────────────────────────────────────────────

ERRORS_TOTAL = Counter(
    "cdp_errors_total",
    "Total application errors",
    ["error_type"],
)


def start_metrics_server(port: int = 9090) -> None:
    """Start the Prometheus metrics HTTP server on the given port.

    Args:
        port: Port to expose metrics on (default 9090).
    """
    start_http_server(port)
