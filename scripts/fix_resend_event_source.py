#!/usr/bin/env python3
"""
Fix Resend event source type from webhook to REST.

This script updates the existing 'resend-webhook' event source
to use the REST bridge instead of the Webhook bridge, allowing
events to be accepted via the /track endpoint.
"""

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import httpx

from dotenv import load_dotenv

# Load both env files
load_dotenv(REPO_ROOT / ".env.local")
load_dotenv(REPO_ROOT / ".env")

TRACARDI_API_URL = os.getenv("TRACARDI_API_URL", "http://localhost:8686")
TRACARDI_USERNAME = os.getenv("TRACARDI_USERNAME", "admin@admin.com")
TRACARDI_PASSWORD = os.getenv("TRACARDI_PASSWORD", "")

# Bridge IDs
BRIDGE_REST = "778ded05-4ff3-4e08-9a86-72c0195fa95d"


async def authenticate() -> str | None:
    """Authenticate and get token."""
    url = f"{TRACARDI_API_URL}/user/token"
    
    # Form-encoded payload (OAuth2 standard)
    payload = {
        "username": TRACARDI_USERNAME,
        "password": TRACARDI_PASSWORD,
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data.get("access_token")
        except httpx.HTTPStatusError as exc:
            # Try JSON fallback
            try:
                response = await client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                return data.get("access_token")
            except Exception as exc2:
                print(f"❌ Authentication failed: {exc2}")
                return None
        except Exception as exc:
            print(f"❌ Authentication failed: {exc}")
            return None


async def delete_event_source(token: str, source_id: str) -> bool:
    """Delete an event source."""
    url = f"{TRACARDI_API_URL}/event-source/{source_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(url, headers=headers, timeout=30.0)
            if response.status_code in [200, 204, 404]:
                print(f"  ✅ Deleted existing event source: {source_id}")
                return True
            else:
                print(f"  ⚠️  Delete returned {response.status_code}: {response.text[:200]}")
                return False
        except Exception as exc:
            print(f"  ❌ Error deleting: {exc}")
            return False


async def create_event_source(token: str) -> bool:
    """Create the Resend event source with REST type."""
    url = f"{TRACARDI_API_URL}/event-source"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    payload = {
        "id": "resend-webhook",
        "name": "Resend Email Webhook",
        "description": "Email events from Resend (sent, delivered, opened, clicked, bounced)",
        "type": ["rest"],
        "bridge": {
            "id": BRIDGE_REST,
            "name": "REST API Bridge",
        },
        "tags": ["email", "resend", "marketing", "engagement"],
        "enabled": True,
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            if response.status_code in [200, 201]:
                print(f"  ✅ Created Resend event source with REST type")
                return True
            else:
                print(f"  ❌ Create failed: {response.status_code}: {response.text[:200]}")
                return False
        except Exception as exc:
            print(f"  ❌ Error creating: {exc}")
            return False


async def test_event_source(token: str) -> bool:
    """Test that the event source accepts events."""
    url = f"{TRACARDI_API_URL}/track"
    
    test_payload = {
        "source": {"id": "resend-webhook"},
        "profile": {
            "id": "test-profile-123",
            "traits": {"email": "test@example.com"}
        },
        "events": [{
            "type": "email.opened",
            "properties": {
                "email_id": "test-123",
                "subject": "Test Email"
            }
        }]
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=test_payload, timeout=10.0)
            if response.status_code == 200:
                print(f"  ✅ Event source accepts events via /track endpoint")
                data = response.json()
                profile_id = data.get("profile", {}).get("id")
                print(f"     Profile ID: {profile_id}")
                return True
            else:
                print(f"  ❌ Track failed: {response.status_code}: {response.text[:200]}")
                return False
        except Exception as exc:
            print(f"  ❌ Error testing: {exc}")
            return False


async def main():
    print("=" * 60)
    print("🔧 Fixing Resend Event Source")
    print("=" * 60)
    print(f"\nTracardi API: {TRACARDI_API_URL}")
    
    # Step 1: Authenticate
    print("\n🔐 Authenticating...")
    token = await authenticate()
    if not token:
        print("❌ Authentication failed!")
        return 1
    print("✅ Authenticated")
    
    # Step 2: Delete existing event source
    print("\n🗑️  Deleting existing event source...")
    await delete_event_source(token, "resend-webhook")
    
    # Step 3: Create new event source with REST type
    print("\n📡 Creating new event source with REST type...")
    if not await create_event_source(token):
        return 1
    
    # Step 4: Test the event source
    print("\n🧪 Testing event source...")
    if not await test_event_source(token):
        return 1
    
    print("\n" + "=" * 60)
    print("✅ Resend event source fixed successfully!")
    print("=" * 60)
    print("\nThe event source now accepts events via the /track endpoint.")
    print("You can now configure Resend webhooks to send events to Tracardi.")
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
        sys.exit(1)
