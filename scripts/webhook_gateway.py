#!/usr/bin/env python3
"""
Webhook endpoints for receiving events from external systems
Receives events and sends to Azure Event Hub and Tracardi

Security features:
- HMAC signature verification for all webhooks
- Timestamp-based replay protection (5-minute window)
- Redis-backed distributed rate limiting (fallback to memory)
- IP allowlisting for webhook sources
- Structured security logging with audit trail
- Request ID tracking for debugging
"""

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import secrets
import time
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps

from azure.eventhub import EventData, EventHubProducerClient
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv(".env.database")

app = FastAPI(title="CDP Webhook Gateway")

# Event Hub client
EVENTHUB_CONNECTION = os.getenv("EVENTHUB_CONNECTION_STRING")
EVENTHUB_NAME = os.getenv("EVENTHUB_NAME", "cdp-events")

# Webhook secrets (must be configured via environment variables)
TEAMLEADER_WEBHOOK_SECRET = os.getenv("TEAMLEADER_WEBHOOK_SECRET", "")
BREVO_WEBHOOK_SECRET = os.getenv("BREVO_WEBHOOK_SECRET", "")
RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET", "")

# Rate limiting configuration
RATE_LIMIT_REQUESTS = int(os.getenv("WEBHOOK_RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("WEBHOOK_RATE_LIMIT_WINDOW", "60"))  # seconds

# Replay protection configuration
REPLAY_PROTECTION_WINDOW = int(os.getenv("REPLAY_PROTECTION_WINDOW", "300"))  # 5 minutes
REPLAY_NONCE_TTL = REPLAY_PROTECTION_WINDOW + 60  # Slightly longer than window

# IP allowlist configuration (comma-separated list of CIDR ranges)
WEBHOOK_IP_ALLOWLIST = os.getenv("WEBHOOK_IP_ALLOWLIST", "")

# Redis configuration (optional, falls back to memory if not configured)
REDIS_URL = os.getenv("REDIS_URL", "")

producer = None

# Simple in-memory rate limiter (fallback when Redis is not available)
_rate_limit_store: dict[str, list[float]] = {}
_replay_nonce_store: set[str] = set()

# Try to import Redis for distributed rate limiting
_redis_client = None
if REDIS_URL:
    try:
        import redis

        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info("redis_rate_limiter_initialized")
    except Exception as e:
        logger.warning(f"redis_connection_failed: {e}, using_memory_fallback")


def get_request_id() -> str:
    """Generate a unique request ID for tracing."""
    return secrets.token_hex(8)


def verify_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    """
    Verify HMAC signature of webhook payload.

    Args:
        payload: Raw request body
        signature: Signature header value (hex string)
        secret: Webhook secret key

    Returns:
        True if signature is valid, False otherwise
    """
    if not secret or not signature:
        return False

    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_resend_svix_signature(
    payload: bytes, signature_header: str | None, secret: str, request_id: str
) -> tuple[bool, str]:
    """
    Verify Resend webhook signature using Svix format.

    Resend uses Svix format: v1,<timestamp>,<signature>
    The signature is computed as: HMACSHA256(secret, timestamp + "." + payload)

    Args:
        payload: Raw request body
        signature_header: Svix signature header (e.g., "v1,1234567890,abc123...")
        secret: Webhook signing secret
        request_id: Request ID for logging

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not secret or not signature_header:
        return False, "missing_secret_or_signature"

    try:
        # Parse svix header format: v1,<timestamp>,<signature>
        parts = signature_header.split(",")
        if len(parts) != 3 or parts[0] != "v1":
            return False, "invalid_svix_format"

        timestamp_str = parts[1]
        signature = parts[2]

        # Verify timestamp is within replay window
        try:
            timestamp = int(timestamp_str)
            now = int(time.time())
            if abs(now - timestamp) > REPLAY_PROTECTION_WINDOW:
                logger.warning(
                    f"resend_timestamp_outside_window: {request_id}, "
                    f"timestamp_diff={abs(now - timestamp)}"
                )
                return False, "timestamp_outside_replay_window"
        except ValueError:
            return False, "invalid_timestamp"

        # Compute expected signature: HMACSHA256(secret, timestamp + "." + payload)
        signed_payload = f"{timestamp_str}.".encode() + payload
        expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected, signature):
            return False, "signature_mismatch"

        return True, ""

    except Exception as e:
        logger.error(f"resend_signature_verification_error: {request_id}, error={e}")
        return False, "verification_error"


def verify_timestamp(timestamp_str: str | None, request_id: str) -> tuple[bool, str]:
    """
    Verify webhook timestamp is within acceptable window to prevent replay attacks.

    Args:
        timestamp_str: ISO format timestamp or Unix timestamp string
        request_id: Request ID for logging

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not timestamp_str:
        return True, ""  # No timestamp provided, skip replay protection

    try:
        # Try parsing as Unix timestamp first
        try:
            timestamp = int(timestamp_str)
            webhook_time = datetime.fromtimestamp(timestamp, tz=UTC)
        except ValueError:
            # Try ISO format
            webhook_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        now = datetime.now(UTC)
        age_seconds = abs((now - webhook_time).total_seconds())

        if age_seconds > REPLAY_PROTECTION_WINDOW:
            logger.warning(
                f"replay_protection_triggered: {request_id}, "
                f"age_seconds={age_seconds}, max_age={REPLAY_PROTECTION_WINDOW}"
            )
            return False, f"request_too_old: {age_seconds}s > {REPLAY_PROTECTION_WINDOW}s"

        return True, ""

    except Exception as e:
        logger.warning(f"timestamp_parsing_error: {request_id}, error={e}")
        return False, "invalid_timestamp_format"


def check_nonce_reuse(nonce: str, request_id: str) -> bool:
    """
    Check if a nonce has been used before (replay detection).

    Returns True if nonce is new (ok), False if already seen (replay).
    """
    if not nonce:
        return True  # No nonce provided, skip check

    if _redis_client:
        # Use Redis for distributed nonce tracking
        key = f"webhook_nonce:{nonce}"
        try:
            # SET NX (only if not exists) with TTL
            result = _redis_client.set(key, "1", nx=True, ex=REPLAY_NONCE_TTL)
            if result is None:
                logger.warning(f"nonce_reuse_detected: {request_id}, nonce={nonce[:16]}...")
                return False
            return True
        except Exception as e:
            logger.error(f"redis_nonce_check_failed: {request_id}, error={e}")
            # Fall through to memory fallback

    # Memory fallback
    if nonce in _replay_nonce_store:
        logger.warning(f"nonce_reuse_detected: {request_id}, nonce={nonce[:16]}...")
        return False

    _replay_nonce_store.add(nonce)

    # Cleanup old nonces periodically (simple size-based cleanup)
    if len(_replay_nonce_store) > 10000:
        # Clear half the store when it gets too large
        _replay_nonce_store.clear()

    return True


def is_ip_allowed(client_ip: str) -> bool:
    """
    Check if client IP is in the allowlist.
    Returns True if allowlist is empty (allow all) or IP is in allowlist.
    """
    if not WEBHOOK_IP_ALLOWLIST:
        return True  # No allowlist configured, allow all

    try:
        client_addr = ipaddress.ip_address(client_ip)
        for cidr in WEBHOOK_IP_ALLOWLIST.split(","):
            cidr = cidr.strip()
            if not cidr:
                continue
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                if client_addr in network:
                    return True
            except ValueError:
                # Try as single IP
                try:
                    if client_addr == ipaddress.ip_address(cidr):
                        return True
                except ValueError:
                    continue
        return False
    except ValueError:
        logger.warning(f"invalid_client_ip_format: {client_ip}")
        return False


def is_rate_limited(client_id: str, request_id: str) -> bool:
    """
    Check if client is rate limited.
    Uses Redis if available, falls back to in-memory store.

    Args:
        client_id: Unique client identifier (e.g., IP address)
        request_id: Request ID for logging

    Returns:
        True if client should be rate limited, False otherwise
    """
    now = time.time()

    if _redis_client:
        try:
            # Use Redis sorted set for sliding window rate limiting
            key = f"rate_limit:{client_id}"
            pipeline = _redis_client.pipeline()

            # Remove entries outside the window
            pipeline.zremrangebyscore(key, 0, now - RATE_LIMIT_WINDOW)

            # Count remaining entries
            pipeline.zcard(key)

            # Add current request
            pipeline.zadd(key, {str(now): now})

            # Set expiry on the key
            pipeline.expire(key, RATE_LIMIT_WINDOW + 1)

            results = pipeline.execute()
            request_count = results[1]

            if request_count >= RATE_LIMIT_REQUESTS:
                logger.warning(
                    f"rate_limit_exceeded: {request_id}, client={client_id}, "
                    f"count={request_count}, limit={RATE_LIMIT_REQUESTS}"
                )
                return True

            return False

        except Exception as e:
            logger.error(
                f"redis_rate_limit_error: {request_id}, error={e}, falling_back_to_memory"
            )
            # Fall through to memory fallback

    # Memory fallback
    requests = _rate_limit_store.get(client_id, [])

    # Remove requests outside the window
    requests = [t for t in requests if now - t < RATE_LIMIT_WINDOW]

    # Check if limit exceeded
    if len(requests) >= RATE_LIMIT_REQUESTS:
        _rate_limit_store[client_id] = requests
        logger.warning(
            f"rate_limit_exceeded: {request_id}, client={client_id}, "
            f"count={len(requests)}, limit={RATE_LIMIT_REQUESTS}"
        )
        return True

    # Add current request
    requests.append(now)
    _rate_limit_store[client_id] = requests

    return False


def rate_limited_endpoint(func: Callable) -> Callable:
    """
    Decorator to apply rate limiting to an endpoint.
    Uses client IP as identifier.
    """

    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        request_id = getattr(request.state, "request_id", "unknown")

        # Get client IP
        client_ip = request.headers.get("x-forwarded-for", "")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        if is_rate_limited(client_ip, request_id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
            )

        return await func(request, *args, **kwargs)

    return wrapper


def require_ip_allowlist(func: Callable) -> Callable:
    """Decorator to enforce IP allowlist for webhook endpoints."""

    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        request_id = getattr(request.state, "request_id", "unknown")

        # Get client IP
        client_ip = request.headers.get("x-forwarded-for", "")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        if not is_ip_allowed(client_ip):
            logger.warning(f"ip_not_allowed: {request_id}, ip={client_ip}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied.",
            )

        return await func(request, *args, **kwargs)

    return wrapper


def get_producer():
    global producer
    if producer is None:
        producer = EventHubProducerClient.from_connection_string(
            EVENTHUB_CONNECTION, eventhub_name=EVENTHUB_NAME
        )
    return producer


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID for tracing through all requests."""
    request_id = get_request_id()
    request.state.request_id = request_id

    # Log request start
    logger.info(
        f"request_started: {request_id}, method={request.method}, "
        f"path={request.url.path}, client={request.client.host if request.client else 'unknown'}"
    )

    response = await call_next(request)

    # Log request completion
    logger.info(f"request_completed: {request_id}, status={response.status_code}")

    return response


@app.post("/webhook/teamleader")
@require_ip_allowlist
async def teamleader_webhook(
    request: Request,
    x_teamleader_signature: str | None = Header(None),
    x_teamleader_timestamp: str | None = Header(None),
):
    """Receive webhooks from Teamleader CRM with replay protection."""
    request_id = getattr(request.state, "request_id", "unknown")
    body = await request.body()

    # Verify timestamp (replay protection)
    if x_teamleader_timestamp:
        is_valid, error = verify_timestamp(x_teamleader_timestamp, request_id)
        if not is_valid:
            logger.warning(f"teamleader_replay_protection_failed: {request_id}, error={error}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Request expired")

    # Verify signature
    if TEAMLEADER_WEBHOOK_SECRET:
        if not verify_signature(body, x_teamleader_signature, TEAMLEADER_WEBHOOK_SECRET):
            logger.warning(
                f"teamleader_signature_verification_failed: {request_id}, "
                f"has_sig={bool(x_teamleader_signature)}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature"
            )
    else:
        logger.warning(f"teamleader_webhook_secret_not_configured: {request_id}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"teamleader_invalid_json: {request_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload"
        ) from None

    # Transform to standard format
    event = {
        "source": "teamleader",
        "event_type": data.get("event_type", "unknown"),
        "uid": data.get("company_id") or data.get("contact_id"),
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": data,
        "request_id": request_id,
    }

    # Send to Event Hub
    send_to_eventhub(event)

    logger.info(
        f"teamleader_webhook_received: {request_id}, "
        f"event_type={event['event_type']}, uid={event['uid']}"
    )

    return JSONResponse({"status": "received", "request_id": request_id})


@app.post("/webhook/brevo")
@require_ip_allowlist
async def brevo_webhook(
    request: Request,
    x_brevo_signature: str | None = Header(None),
    x_brevo_timestamp: str | None = Header(None),
):
    """Receive webhooks from Brevo (email events) with replay protection."""
    request_id = getattr(request.state, "request_id", "unknown")
    body = await request.body()

    # Verify timestamp (replay protection)
    if x_brevo_timestamp:
        is_valid, error = verify_timestamp(x_brevo_timestamp, request_id)
        if not is_valid:
            logger.warning(f"brevo_replay_protection_failed: {request_id}, error={error}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Request expired")

    # Verify signature
    if BREVO_WEBHOOK_SECRET:
        if not verify_signature(body, x_brevo_signature, BREVO_WEBHOOK_SECRET):
            logger.warning(
                f"brevo_signature_verification_failed: {request_id}, "
                f"has_sig={bool(x_brevo_signature)}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature"
            )
    else:
        logger.warning(f"brevo_webhook_secret_not_configured: {request_id}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"brevo_invalid_json: {request_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload"
        ) from None

    # Transform to standard format
    event = {
        "source": "brevo",
        "event_type": data.get("event"),  # delivered, opened, clicked, etc.
        "uid": data.get("email"),  # Will need mapping to UID
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": data,
        "request_id": request_id,
    }

    send_to_eventhub(event)

    logger.info(
        f"brevo_webhook_received: {request_id}, type={event['event_type']}, email={event['uid']}"
    )

    return JSONResponse({"status": "received", "request_id": request_id})


@app.post("/webhook/resend")
@require_ip_allowlist
async def resend_webhook(
    request: Request,
    x_resend_signature: str | None = Header(None),  # Svix format: v1,timestamp,signature
):
    """
    Receive webhooks from Resend (email events) with Svix signature verification.

    Resend webhook payload structure:
    {
        "type": "email.opened",
        "created_at": "2024-01-01T00:00:00.000Z",
        "data": {
            "created_at": "2024-01-01T00:00:00.000Z",
            "email_id": "...",
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "subject": "Email Subject",
            ...
        }
    }
    """
    request_id = getattr(request.state, "request_id", "unknown")
    body = await request.body()

    # Verify Svix signature (includes timestamp validation)
    if RESEND_WEBHOOK_SECRET:
        is_valid, error = verify_resend_svix_signature(
            body, x_resend_signature, RESEND_WEBHOOK_SECRET, request_id
        )
        if not is_valid:
            logger.warning(f"resend_signature_verification_failed: {request_id}, error={error}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid signature: {error}"
            )
    else:
        logger.warning(f"resend_webhook_secret_not_configured: {request_id}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"resend_invalid_json: {request_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload"
        ) from None

    try:
        # Extract event type and email from Resend payload
        event_type = data.get("type", "unknown")
        event_data = data.get("data", {})

        # Map to profile using email address
        email = event_data.get("to", "")

        # Transform to standard CDP event format
        event = {
            "source": "resend",
            "event_type": event_type,  # email.opened, email.clicked, etc.
            "uid": email,  # Email address as identifier
            "timestamp": data.get("created_at", datetime.now(UTC).isoformat()),
            "payload": {
                "email_id": event_data.get("email_id"),
                "from": event_data.get("from"),
                "to": event_data.get("to"),
                "subject": event_data.get("subject"),
                "click": event_data.get("click"),  # For click events
                "user_agent": event_data.get("user_agent"),
            },
            "request_id": request_id,
        }

        # Also forward to Tracardi if configured
        await forward_to_tracardi(event)

        # Send to Event Hub
        send_to_eventhub(event)

        logger.info(
            f"resend_webhook_received: {request_id}, event_type={event_type}, email={email}"
        )

        return JSONResponse({"status": "received", "request_id": request_id})

    except Exception as e:
        logger.error(f"resend_webhook_error: {request_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process webhook"
        ) from None


@app.post("/webhook/website")
@rate_limited_endpoint
async def website_webhook(request: Request):
    """Receive events from website tracking with rate limiting."""
    request_id = getattr(request.state, "request_id", "unknown")

    try:
        data = await request.json()
    except json.JSONDecodeError as e:
        logger.error(f"website_invalid_json: {request_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload"
        ) from None

    event = {
        "source": "website",
        "event_type": data.get("event_type", "page_view"),
        "uid": data.get("uid") or data.get("anonymous_id"),
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": data,
        "request_id": request_id,
    }

    send_to_eventhub(event)

    logger.info(
        f"website_webhook_received: {request_id}, "
        f"event_type={event['event_type']}, uid={event['uid']}"
    )

    return JSONResponse({"status": "received", "request_id": request_id})


def send_to_eventhub(event: dict):
    """Send event to Azure Event Hub"""
    try:
        producer = get_producer()
        event_data_batch = producer.create_batch()
        event_data_batch.add(EventData(json.dumps(event)))
        producer.send_batch(event_data_batch)
    except Exception as e:
        request_id = event.get("request_id", "unknown")
        logger.error(f"eventhub_send_failed: {request_id}, error={e}")
        raise HTTPException(status_code=500, detail="Failed to process event") from None


async def forward_to_tracardi(event: dict):
    """Forward event to Tracardi for processing.

    This allows Tracardi workflows to process the event and update profiles.
    """
    import httpx

    tracardi_url = os.getenv("TRACARDI_TRACKER_URL", "http://137.117.212.154:8686/tracker")
    request_id = event.get("request_id", "unknown")

    try:
        async with httpx.AsyncClient() as client:
            # Transform CDP event to Tracardi tracker format
            tracardi_event = {
                "source": {"id": event["source"]},
                "profile": {"traits": {"email": event["uid"]}},
                "events": [{"type": event["event_type"], "properties": event["payload"]}],
            }

            response = await client.post(tracardi_url, json=tracardi_event, timeout=10.0)

            if response.status_code == 200:
                logger.info(
                    f"event_forwarded_to_tracardi: {request_id}, "
                    f"event_type={event['event_type']}, email={event['uid']}"
                )
            else:
                logger.warning(
                    f"tracardi_forward_failed: {request_id}, "
                    f"status={response.status_code}, response={response.text[:200]}"
                )

    except Exception as e:
        # Log but don't fail - Event Hub is primary destination
        logger.warning(f"failed_to_forward_to_tracardi: {request_id}, error={e}")


@app.get("/health")
async def health_check():
    """Health check endpoint with security status."""
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "security": {
            "teamleader_signature_verification": bool(TEAMLEADER_WEBHOOK_SECRET),
            "brevo_signature_verification": bool(BREVO_WEBHOOK_SECRET),
            "resend_signature_verification": bool(RESEND_WEBHOOK_SECRET),
            "replay_protection": {
                "enabled": True,
                "window_seconds": REPLAY_PROTECTION_WINDOW,
            },
            "rate_limiting": {
                "enabled": True,
                "requests_per_window": RATE_LIMIT_REQUESTS,
                "window_seconds": RATE_LIMIT_WINDOW,
                "backend": "redis" if _redis_client else "memory",
            },
            "ip_allowlist": {
                "enabled": bool(WEBHOOK_IP_ALLOWLIST),
                "rules_count": len([r for r in WEBHOOK_IP_ALLOWLIST.split(",") if r.strip()])
                if WEBHOOK_IP_ALLOWLIST
                else 0,
            },
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
