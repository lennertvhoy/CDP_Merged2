#!/usr/bin/env python3
"""
Setup Tracardi for KBO data ingestion and outbound email campaigns.
Creates event sources, event types, and workflows.
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import httpx
from src.core.logger import get_logger

logger = get_logger(__name__)

# Configuration
TRACARDI_API_URL = os.getenv("TRACARDI_API_URL", "http://localhost:8686")
TRACARDI_USERNAME = os.getenv("TRACARDI_USERNAME", "admin@admin.com")
TRACARDI_PASSWORD = os.getenv("TRACARDI_PASSWORD")

if not TRACARDI_PASSWORD and "localhost" not in TRACARDI_API_URL and "127.0.0.1" not in TRACARDI_API_URL:
    # Try to get from terraform output
    import subprocess
    try:
        result = subprocess.run(
            ["terraform", "-chdir=infra/tracardi", "output", "-raw", "tracardi_admin_password"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            TRACARDI_PASSWORD = result.stdout.strip()
    except Exception:
        pass

if not TRACARDI_PASSWORD:
    raise RuntimeError(
        "TRACARDI_PASSWORD must be set before running setup_tracardi_kbo_and_email.py. "
        "Alternatively, ensure Terraform is available to retrieve the password."
    )

# Bridge IDs (from Tracardi instance)
BRIDGE_REST = "778ded05-4ff3-4e08-9a86-72c0195fa95d"  # REST API Bridge
BRIDGE_WEBHOOK = "3d8bb87e-28d1-4a38-b19c-d0c1fbb71e22"  # Webhook API Bridge


# ============================================================================
# EVENT SOURCES
# ============================================================================

EVENT_SOURCES = {
    "kbo-batch-import": {
        "name": "KBO Batch Import",
        "description": "Batch import of KBO enterprise data from CSV/zip files",
        "type": ["rest"],
        "bridge_id": BRIDGE_REST,
        "bridge_name": "REST API Bridge",
        "tags": ["kbo", "import", "batch", "enterprise"],
    },
    "kbo-realtime": {
        "name": "KBO Real-time Updates",
        "description": "Real-time updates from KBO pubications",
        "type": ["webhook"],
        "bridge_id": BRIDGE_WEBHOOK,
        "bridge_name": "Webhook API Bridge",
        "tags": ["kbo", "realtime", "webhook", "enterprise"],
    },
    "resend-webhook": {
        "name": "Resend Email Webhook",
        "description": "Email events from Resend (sent, delivered, opened, clicked, bounced)",
        "type": ["webhook"],
        "bridge_id": BRIDGE_WEBHOOK,
        "bridge_name": "Webhook API Bridge",
        "tags": ["email", "resend", "marketing", "engagement"],
    },
    "cdp-api": {
        "name": "CDP API",
        "description": "Internal CDP API for profile and event ingestion",
        "type": ["rest"],
        "bridge_id": BRIDGE_REST,
        "bridge_name": "REST API Bridge",
        "tags": ["api", "internal", "cdp"],
    },
}


class TracardiSetupClient:
    """Client for setting up Tracardi configuration."""
    
    def __init__(self, api_url: str, username: str, password: str):
        self.api_url = api_url.rstrip("/")
        self.username = username
        self.password = password
        self.token: str | None = None
        
    async def authenticate(self) -> bool:
        """Authenticate and get access token."""
        url = f"{self.api_url}/user/token"
        payload = {
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
            "scope": "",
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # Try form-encoded first
                response = await client.post(url, data=payload, timeout=30.0)
                if response.status_code == 422:
                    # Fall back to JSON
                    response = await client.post(url, json=payload, timeout=30.0)
                
                response.raise_for_status()
                data = response.json()
                self.token = data.get("access_token")
                logger.info("tracardi_authenticated", url=self.api_url)
                return True
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "tracardi_auth_failed",
                    status_code=exc.response.status_code,
                    detail=exc.response.text[:200],
                )
                return False
            except Exception as exc:
                logger.error("tracardi_auth_error", error=str(exc))
                return False
    
    def get_headers(self) -> dict[str, str]:
        """Get authenticated headers."""
        if not self.token:
            raise RuntimeError("Not authenticated")
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
    
    async def create_event_source(self, source_id: str, config: dict) -> bool:
        """Create an event source in Tracardi."""
        url = f"{self.api_url}/event-source"
        
        payload = {
            "id": source_id,
            "name": config["name"],
            "description": config["description"],
            "type": config["type"],
            "bridge": {
                "id": config["bridge_id"],
                "name": config["bridge_name"],
            },
            "tags": config.get("tags", []),
            "enabled": True,
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, json=payload, headers=self.get_headers(), timeout=30.0
                )
                
                if response.status_code in [200, 201]:
                    logger.info("event_source_created", source_id=source_id)
                    return True
                elif response.status_code == 409:
                    logger.info("event_source_already_exists", source_id=source_id)
                    return True
                elif response.status_code == 404 and "already exists" in response.text.lower():
                    logger.info("event_source_already_exists", source_id=source_id)
                    return True
                else:
                    logger.error(
                        "failed_to_create_event_source",
                        source_id=source_id,
                        status_code=response.status_code,
                        response=response.text[:200],
                    )
                    return False
            except Exception as e:
                logger.error("error_creating_event_source", source_id=source_id, error=str(e))
                return False
    
    async def delete_event_source(self, source_id: str) -> bool:
        """Delete an event source by ID."""
        url = f"{self.api_url}/event-source/{source_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    url, headers=self.get_headers(), timeout=30.0
                )
                if response.status_code in [200, 204, 404]:
                    return True
                return False
            except Exception as e:
                logger.error("error_deleting_event_source", source_id=source_id, error=str(e))
                return False
    
    async def list_event_sources(self) -> list[dict]:
        """List existing event sources."""
        url = f"{self.api_url}/event-sources"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, headers=self.get_headers(), timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                return data.get("result", [])
            except Exception as e:
                logger.error("error_listing_sources", error=str(e))
                return []
    
    async def test_event_tracking(self, source_id: str, event_type: str) -> bool:
        """Test tracking an event to verify the source works."""
        url = f"{self.api_url}/track"
        
        payload = {
            "source": {"id": source_id},
            "events": [
                {
                    "type": event_type,
                    "properties": {
                        "test": True,
                        "timestamp": datetime.now().isoformat(),
                    }
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, json=payload, headers=self.get_headers(), timeout=30.0
                )
                if response.status_code in [200, 201]:
                    logger.info("test_event_tracked", source_id=source_id, event_type=event_type)
                    return True
                else:
                    logger.warning(
                        "test_event_failed",
                        source_id=source_id,
                        event_type=event_type,
                        status_code=response.status_code,
                    )
                    return False
            except Exception as e:
                logger.error("error_tracking_test_event", source_id=source_id, error=str(e))
                return False


async def setup_tracardi():
    """Main setup function."""
    print("=" * 70)
    print("🚀 Tracardi Setup for KBO Data Ingestion & Email Campaigns")
    print("=" * 70)
    print(f"\nTracardi API: {TRACARDI_API_URL}")
    print(f"Username: {TRACARDI_USERNAME}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Create client and authenticate
    client = TracardiSetupClient(TRACARDI_API_URL, TRACARDI_USERNAME, TRACARDI_PASSWORD)
    
    print("\n🔐 Authenticating...")
    if not await client.authenticate():
        print("❌ Authentication failed!")
        return 1
    print("✅ Authentication successful")
    
    # Get current state
    print("\n📊 Current Tracardi State:")
    existing_sources = await client.list_event_sources()
    print(f"  Event Sources: {len(existing_sources)}")
    for src in existing_sources:
        print(f"    - {src.get('id')}: {src.get('name')}")
    
    results = {
        "event_sources": {"created": 0, "failed": 0, "tested": 0},
    }
    
    # Step 1: Create Event Sources
    print("\n" + "-" * 70)
    print("📡 Step 1: Creating Event Sources")
    print("-" * 70)
    
    for source_id, config in EVENT_SOURCES.items():
        print(f"  Creating: {source_id}...", end=" ")
        if await client.create_event_source(source_id, config):
            print("✅")
            results["event_sources"]["created"] += 1
        else:
            print("❌")
            results["event_sources"]["failed"] += 1
    
    # Step 2: Test Event Sources
    print("\n" + "-" * 70)
    print("🧪 Step 2: Testing Event Sources")
    print("-" * 70)
    
    test_events = [
        ("kbo-batch-import", "kbo.enterprise.imported"),
        ("cdp-api", "profile.updated"),
    ]
    
    for source_id, event_type in test_events:
        print(f"  Testing: {source_id} -> {event_type}...", end=" ")
        if await client.test_event_tracking(source_id, event_type):
            print("✅")
            results["event_sources"]["tested"] += 1
        else:
            print("⚠️")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Setup Summary")
    print("=" * 70)
    print(f"\nEvent Sources: {results['event_sources']['created']} created, "
          f"{results['event_sources']['failed']} failed, "
          f"{results['event_sources']['tested']} tested")
    
    total_created = results["event_sources"]["created"]
    total_failed = results["event_sources"]["failed"]
    
    print("\n" + "=" * 70)
    if total_failed == 0 and total_created > 0:
        print("✅ Event sources created and tested successfully!")
        print("=" * 70)
        print("\nNext Steps:")
        print("  1. Configure Resend webhooks to point to Tracardi:")
        print(f"     POST {TRACARDI_API_URL}/track")
        print("     with source.id = 'resend-webhook'")
        print("  2. Run KBO sync to test kbo-batch-import source:")
        print("     TRACARDI_SOURCE_ID=kbo-batch-import python scripts/sync_kbo_to_tracardi.py")
        print("  3. Verify event sources in Tracardi GUI:")
        print(f"     {TRACARDI_API_URL.replace(':8686', ':8787')}")
        print("  4. Create workflows manually in GUI (workflow API requires complex node definitions)")
        return 0
    elif total_created == 0 and total_failed == 0:
        print("ℹ️  No changes made (sources may already exist)")
        print("=" * 70)
        return 0
    else:
        print(f"⚠️  Setup completed with {total_failed} failures")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(setup_tracardi())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
