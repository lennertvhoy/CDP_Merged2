"""
Application-wide constants for CDP_Merged.
"""

# ─── HTTP timeouts (seconds) ──────────────────────────────────────────────────
DEFAULT_HTTP_TIMEOUT: float = 30.0
TRACARDI_TIMEOUT: float = 60.0
FLEXMAIL_TIMEOUT: float = 10.0
RESEND_TIMEOUT: float = 30.0
LLM_TIMEOUT: float = 120.0

# ─── Retry configuration ──────────────────────────────────────────────────────
MAX_RETRIES: int = 3
RETRY_MIN_WAIT: float = 1.0
RETRY_MAX_WAIT: float = 8.0

# ─── Query limits ─────────────────────────────────────────────────────────────
MAX_QUERY_LENGTH: int = 1_000
MAX_SEARCH_RESULTS: int = 100
DEFAULT_SEARCH_LIMIT: int = 20
MAX_NACE_MATCHES: int = 8

# ─── Rate limiting ────────────────────────────────────────────────────────────
RATE_LIMIT_REQUESTS_PER_MINUTE: int = 20

# ─── Flexmail ─────────────────────────────────────────────────────────────────
FLEXMAIL_SYNC_CHUNK_SIZE: int = 50

# ─── Tracardi ─────────────────────────────────────────────────────────────────
TRACARDI_TRACK_CHUNK_SIZE: int = 50

# ─── Supported LLM providers ──────────────────────────────────────────────────
SUPPORTED_LLM_PROVIDERS = {"openai", "azure_openai", "ollama", "mock"}

# ─── Supported query types ────────────────────────────────────────────────────
SUPPORTED_QUERY_TYPES = {"tql", "sql", "elastic"}

# ─── Additional Timeouts ──────────────────────────────────────────────────────
AZURE_SEARCH_TIMEOUT = 15.0
KBO_REQUEST_TIMEOUT = 30.0
WEBSITE_DISCOVERY_TIMEOUT = 10.0
PHONE_DISCOVERY_TIMEOUT = 10.0
GEOCODING_TIMEOUT = 10.0
CBE_API_TIMEOUT = 15.0

# ─── Limits ───────────────────────────────────────────────────────────────────
MAX_BATCH_SIZE = 100
MAX_EXPORT_SIZE = 1000
KBO_SAMPLE_LIMIT = 100
KBO_ANALYSIS_LIMIT = 500
MAX_PROFILE_QUERY_LIMIT = 1000

# ─── KBO Validation ───────────────────────────────────────────────────────────
KBO_NUMBER_LENGTH = 10
KBO_NUMBER_LENGTH_SHORT = 9

# ─── Company Size Thresholds ──────────────────────────────────────────────────
EMPLOYEE_MICRO_THRESHOLD = 10
EMPLOYEE_SMALL_THRESHOLD = 50
EMPLOYEE_MEDIUM_THRESHOLD = 250

# ─── HTTP Status Codes ────────────────────────────────────────────────────────
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_ACCEPTED = 202
HTTP_NO_CONTENT = 204
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_TIMEOUT = 408
HTTP_CONFLICT = 409
HTTP_SERVER_ERROR = 500
HTTP_BAD_GATEWAY = 502
HTTP_SERVICE_UNAVAILABLE = 503

# ─── Cache Settings ───────────────────────────────────────────────────────────
DEFAULT_CACHE_TTL_HOURS = 24
