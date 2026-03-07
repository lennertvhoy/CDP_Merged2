#!/usr/bin/env python3
"""
Resend to Tracardi Webhook Bridge.

Translates Resend webhook format to Tracardi /track format and forwards events.
Run this to receive Resend webhooks and forward them to Tracardi.

Usage:
    # Run the bridge server
    python scripts/resend_to_tracardi_bridge.py
    
    # Or with custom port
    python scripts/resend_to_tracardi_bridge.py 8080
    
    # Test with a simulated Resend event
    curl -X POST http://localhost:5000/webhook/resend \
      -H "Content-Type: application/json" \
      -d '{"type": "email.opened", "email_id": "test-123", "to": "test@example.com"}'

Environment:
    TRACARDI_API_URL - Tracardi API URL (default: http://localhost:8686)
    TRACARDI_USERNAME - Tracardi username
    TRACARDI_PASSWORD - Tracardi password
    RESEND_WEBHOOK_SECRET - Resend webhook signing secret for verification
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

# Add repo root to path for imports
REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

# Load environment
load_dotenv(REPO_ROOT / ".env.local")
load_dotenv(REPO_ROOT / ".env", override=False)

# Configuration
TRACARDI_API_URL = os.getenv("TRACARDI_API_URL", "http://localhost:8686").rstrip("/")
TRACARDI_USERNAME = os.getenv("TRACARDI_USERNAME", "lennertvhoy@gmail.com")
TRACARDI_PASSWORD = os.getenv("TRACARDI_PASSWORD", "")
RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET", "")

# Event type mapping from Resend to Tracardi
EVENT_TYPE_MAP = {
    "email.sent": "email.sent",
    "email.delivered": "email.delivered",
    "email.opened": "email.opened",
    "email.clicked": "email.clicked",
    "email.bounced": "email.bounced",
    "email.complained": "email.complained",
    "email.delivery_delayed": "email.delivery_delayed",
}


async def get_tracardi_token() -> str:
    """Get authentication token from Tracardi."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TRACARDI_API_URL}/user/token",
            data={
                "username": TRACARDI_USERNAME,
                "password": TRACARDI_PASSWORD,
                "grant_type": "password",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["access_token"]


async def forward_to_tracardi(event_data: dict, token: str) -> bool:
    """Forward event to Tracardi /track endpoint."""
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post(
            f"{TRACARDI_API_URL}/track",
            json=event_data,
            headers=headers,
            timeout=10.0,
        )
        return response.status_code == 200


def verify_resend_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    """
    Verify Resend webhook signature using Svix format.
    
    Resend uses Svix format: v1,<timestamp>,<signature>
    The signature is computed as: HMACSHA256(secret, timestamp.payload)
    """
    if not secret or not signature:
        return False
    
    try:
        # Parse Svix header format: v1,<timestamp>,<signature>
        parts = signature.split(",")
        if len(parts) != 3 or parts[0] != "v1":
            return False
        
        timestamp_str = parts[1]
        sig = parts[2]
        
        # Verify timestamp is within 5-minute window
        try:
            timestamp = int(timestamp_str)
            now = int(datetime.now(UTC).timestamp())
            if abs(now - timestamp) > 300:  # 5 minutes
                return False
        except ValueError:
            return False
        
        # Compute expected signature: HMACSHA256(secret, timestamp.payload)
        signed_payload = f"{timestamp_str}.".encode() + payload
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(sig, expected_sig)
        
    except Exception:
        return False


def translate_resend_to_tracardi(resend_payload: dict) -> dict:
    """Translate Resend webhook payload to Tracardi /track format."""
    # Extract Resend event data (Resend uses {"type": "...", "data": {...}} format)
    event_type = resend_payload.get("type", "unknown")
    event_data = resend_payload.get("data", resend_payload)  # Fallback to root if no data key
    
    email_id = event_data.get("email_id", "")
    to_email = event_data.get("to", "")
    from_email = event_data.get("from", "")
    subject = event_data.get("subject", "")
    
    # Map to Tracardi event type
    tracardi_event_type = EVENT_TYPE_MAP.get(event_type, event_type)
    
    # Generate deterministic profile ID from email
    profile_id = hashlib.md5(to_email.encode()).hexdigest()[:16] if to_email else "unknown"
    
    # Create Tracardi-compatible payload
    tracardi_payload = {
        "source": {"id": "resend-webhook"},
        "session": {"id": f"resend-{email_id[:20]}" if email_id else "unknown"},
        "profile": {
            "id": profile_id,
            "traits": {
                "email": to_email,
                "resend_email_id": email_id,
            }
        },
        "events": [{  # Note: Tracardi expects 'events' array, not 'event'
            "type": tracardi_event_type,
            "properties": {
                "email_id": email_id,
                "to": to_email,
                "from": from_email,
                "subject": subject,
                "timestamp": datetime.now(UTC).isoformat(),
                "source": "resend",
                "resend_event_type": event_type,
            }
        }]
    }
    
    return tracardi_payload


# FastAPI app
app = FastAPI(title="Resend to Tracardi Bridge")


@app.post("/webhook/resend")
async def handle_resend_webhook(
    request: Request,
    x_resend_signature: str | None = Header(None),
):
    """
    Receive webhooks from Resend and forward to Tracardi.
    
    Resend webhook format:
    {
        "type": "email.opened",
        "created_at": "2024-01-01T00:00:00.000Z",
        "data": {
            "email_id": "...",
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "subject": "Email Subject"
        }
    }
    """
    body = await request.body()
    
    # Verify signature if secret is configured
    if RESEND_WEBHOOK_SECRET:
        if not verify_resend_signature(body, x_resend_signature, RESEND_WEBHOOK_SECRET):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
    
    # Parse Resend payload
    try:
        resend_payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {e}"
        )
    
    event_type = resend_payload.get("type", "unknown")
    event_data = resend_payload.get("data", resend_payload)
    to_email = event_data.get("to", "")
    
    print(f"📧 Received: {event_type} -> {to_email}")
    
    # Translate to Tracardi format
    tracardi_payload = translate_resend_to_tracardi(resend_payload)
    
    # Forward to Tracardi
    try:
        token = await get_tracardi_token()
        success = await forward_to_tracardi(tracardi_payload, token)
        
        if success:
            print(f"   ✅ Forwarded to Tracardi successfully")
            return JSONResponse({
                "status": "ok",
                "message": "Event forwarded to Tracardi"
            })
        else:
            print(f"   ❌ Failed to forward to Tracardi")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to forward to Tracardi"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"   ❌ Error forwarding to Tracardi: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error forwarding event: {e}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "resend-to-tracardi-bridge",
        "tracardi_api": TRACARDI_API_URL,
        "signature_verification": bool(RESEND_WEBHOOK_SECRET),
    }


@app.get("/")
async def root():
    """Root endpoint with instructions."""
    return {
        "service": "Resend to Tracardi Bridge",
        "version": "1.0.0",
        "endpoints": {
            "POST /webhook/resend": "Receive Resend webhooks",
            "GET /health": "Health check",
        },
        "configuration": {
            "tracardi_api": TRACARDI_API_URL,
            "signature_verification": bool(RESEND_WEBHOOK_SECRET),
        }
    }


def main():
    """Run the bridge server."""
    import uvicorn
    
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    
    print("=" * 60)
    print("  🚀 Resend to Tracardi Bridge")
    print("=" * 60)
    print(f"\n   Listening on: http://localhost:{port}")
    print(f"   Webhook URL:  http://localhost:{port}/webhook/resend")
    print(f"   Health check: http://localhost:{port}/health")
    print(f"   Tracardi API: {TRACARDI_API_URL}")
    print(f"   Signature verification: {'enabled' if RESEND_WEBHOOK_SECRET else 'disabled'}")
    print("\n   Press Ctrl+C to stop")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
