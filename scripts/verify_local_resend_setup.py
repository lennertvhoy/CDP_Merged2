#!/usr/bin/env python3
"""
Verify Local Resend Webhook Setup for CDP_Merged.

This script verifies that the local Tracardi instance is properly configured
to receive Resend webhook events. Since ngrok is not configured, actual
webhook receipt from Resend servers is not possible, but all local
configuration can be verified.

Usage:
    python scripts/verify_local_resend_setup.py

Requirements for full end-to-end testing:
    1. ngrok auth token configured: ./ngrok config add-authtoken <token>
    2. Run: ./ngrok http 8686
    3. Set RESEND_WEBHOOK_URL to the ngrok HTTPS URL
    4. Run: python scripts/setup_resend_webhooks_auto.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

import httpx
from dotenv import load_dotenv

# Load environment
load_dotenv(REPO_ROOT / ".env.local")
load_dotenv(REPO_ROOT / ".env")

TRACARDI_API_URL = os.getenv("TRACARDI_API_URL", "http://localhost:8686")
TRACARDI_USERNAME = os.getenv("TRACARDI_USERNAME", "admin@admin.com")
TRACARDI_PASSWORD = os.getenv("TRACARDI_PASSWORD", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")


class ResendSetupVerifier:
    """Verifies local setup for Resend webhook integration."""

    def __init__(self):
        self.api_url = TRACARDI_API_URL.rstrip("/")
        self.token: str | None = None
        self.headers: dict[str, str] = {"Content-Type": "application/json"}
        self.results: dict[str, bool] = {}

    def print_header(self, title: str) -> None:
        """Print formatted header."""
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)

    def print_section(self, title: str) -> None:
        """Print section divider."""
        print(f"\n📋 {title}")
        print("-" * 40)

    async def authenticate(self) -> bool:
        """Authenticate with Tracardi."""
        url = f"{self.api_url}/user/token"
        payload = {
            "username": TRACARDI_USERNAME,
            "password": TRACARDI_PASSWORD,
            "grant_type": "password",
            "scope": "",
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, data=payload, timeout=30.0)
                if response.status_code == 422:
                    response = await client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                self.token = data.get("access_token")
                self.headers["Authorization"] = f"Bearer {self.token}"
                return True
            except Exception as exc:
                print(f"  ❌ Authentication failed: {exc}")
                return False

    async def verify_event_source(self) -> bool:
        """Verify Resend webhook event source exists."""
        url = f"{self.api_url}/event-sources"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, timeout=30.0)
                if response.status_code == 200:
                    data = response.json()
                    grouped = data.get("grouped", {})
                    sources = grouped.get("Event sources", [])
                    
                    for source in sources:
                        if source.get("id") == "resend-webhook":
                            print(f"  ✅ Resend webhook event source found")
                            print(f"     Name: {source.get('name')}")
                            print(f"     Type: {source.get('type')}")
                            print(f"     Enabled: {source.get('enabled', False)}")
                            return True
                    
                    print("  ❌ Resend webhook event source not found")
                    return False
                return False
            except Exception as exc:
                print(f"  ❌ Error: {exc}")
                return False

    async def verify_workflows(self) -> bool:
        """Verify email processing workflows exist."""
        url = f"{self.api_url}/flows/entity"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, timeout=30.0)
                if response.status_code == 200:
                    data = response.json()
                    flows = data.get("result", [])
                    
                    required_workflows = [
                        "Email Bounce Processor",
                        "Email Complaint Processor", 
                        "Email Delivery Processor",
                        "Email Engagement Processor",
                        "High Engagement Segment"
                    ]
                    
                    found_workflows = [f.get("name") for f in flows]
                    all_found = all(wf in found_workflows for wf in required_workflows)
                    
                    if all_found:
                        print(f"  ✅ All {len(required_workflows)} email workflows found")
                        for wf in required_workflows:
                            print(f"     ✓ {wf}")
                    else:
                        print("  ⚠️  Some workflows missing:")
                        for wf in required_workflows:
                            status = "✓" if wf in found_workflows else "✗"
                            print(f"     {status} {wf}")
                    
                    return all_found
                return False
            except Exception as exc:
                print(f"  ❌ Error: {exc}")
                return False

    async def test_tracker_endpoint(self) -> bool:
        """Test the Tracardi tracker endpoint."""
        url = f"{self.api_url}/track"
        
        # Create a test event (profile ID is required)
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
                response = await client.post(
                    url, 
                    json=test_payload, 
                    timeout=10.0
                )
                if response.status_code == 200:
                    print(f"  ✅ Tracker endpoint accepts events")
                    return True
                else:
                    print(f"  ⚠️  Tracker returned {response.status_code}")
                    return False
            except Exception as exc:
                print(f"  ❌ Error: {exc}")
                return False

    def check_ngrok(self) -> bool:
        """Check if ngrok is configured."""
        ngrok_config = Path.home() / ".config/ngrok/ngrok.yml"
        if ngrok_config.exists():
            print(f"  ✅ ngrok is configured")
            return True
        else:
            print(f"  ⚠️  ngrok not configured (required for external webhooks)")
            print(f"     Run: ./ngrok config add-authtoken <your_token>")
            return False

    def check_resend_api_key(self) -> bool:
        """Check if Resend API key is configured."""
        if RESEND_API_KEY and RESEND_API_KEY.startswith("re_"):
            print(f"  ✅ Resend API key configured")
            return True
        else:
            print(f"  ❌ Resend API key not found or invalid")
            return False

    async def simulate_webhook_event(self) -> bool:
        """Simulate a Resend webhook event by sending directly to Tracardi."""
        self.print_section("Simulating Resend Webhook Event")
        
        url = f"{self.api_url}/track"
        
        # Simulate email.opened event
        test_payload = {
            "source": {"id": "resend-webhook"},
            "profile": {
                "traits": {"email": "simulation@example.com"},
                "id": "sim-profile-123"
            },
            "events": [{
                "type": "email.opened",
                "properties": {
                    "email_id": "sim-123",
                    "subject": "Simulation Test",
                    "to": "simulation@example.com",
                    "from": "test@example.com",
                    "user_agent": "CDP Simulation Script"
                }
            }]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, 
                    json=test_payload, 
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    profile_id = data.get("profile", {}).get("id")
                    print(f"  ✅ Event accepted by Tracardi")
                    print(f"     Profile ID: {profile_id}")
                    return True
                else:
                    print(f"  ❌ Tracker returned {response.status_code}")
                    print(f"     Response: {response.text[:200]}")
                    return False
            except Exception as exc:
                print(f"  ❌ Error: {exc}")
                return False

    async def run_verification(self) -> None:
        """Run all verification steps."""
        self.print_header("🚀 Local Resend Webhook Setup Verification")
        
        print(f"\nTracardi API: {TRACARDI_API_URL}")
        print(f"Username: {TRACARDI_USERNAME}")
        
        # Step 1: Authentication
        self.print_section("Step 1: Tracardi Authentication")
        self.results["auth"] = await self.authenticate()
        if not self.results["auth"]:
            print("\n❌ Cannot continue without authentication")
            return
        print("  ✅ Authenticated successfully")
        
        # Step 2: Event Source
        self.print_section("Step 2: Resend Event Source")
        self.results["event_source"] = await self.verify_event_source()
        
        # Step 3: Workflows
        self.print_section("Step 3: Email Processing Workflows")
        self.results["workflows"] = await self.verify_workflows()
        
        # Step 4: Tracker Endpoint
        self.print_section("Step 4: Tracker Endpoint")
        self.results["tracker"] = await self.test_tracker_endpoint()
        
        # Step 5: ngrok Configuration
        self.print_section("Step 5: ngrok Configuration (for external webhooks)")
        self.results["ngrok"] = self.check_ngrok()
        
        # Step 6: Resend API Key
        self.print_section("Step 6: Resend API Key")
        self.results["resend_api"] = self.check_resend_api_key()
        
        # Step 7: Simulate Event
        self.results["simulation"] = await self.simulate_webhook_event()
        
        # Summary
        self.print_summary()

    def print_summary(self) -> None:
        """Print verification summary."""
        self.print_header("📊 Verification Summary")
        
        all_local = all([
            self.results.get("auth", False),
            self.results.get("event_source", False),
            self.results.get("workflows", False),
            self.results.get("tracker", False),
        ])
        
        external_ready = all([
            self.results.get("ngrok", False),
            self.results.get("resend_api", False),
        ])
        
        print("\n✅ Local Configuration:")
        print(f"   Tracardi Authentication: {'✅' if self.results.get('auth') else '❌'}")
        print(f"   Resend Event Source: {'✅' if self.results.get('event_source') else '❌'}")
        print(f"   Email Workflows: {'✅' if self.results.get('workflows') else '❌'}")
        print(f"   Tracker Endpoint: {'✅' if self.results.get('tracker') else '❌'}")
        print(f"   Event Simulation: {'✅' if self.results.get('simulation') else '❌'}")
        
        print("\n🌐 External Webhook Capability:")
        print(f"   ngrok Configured: {'✅' if self.results.get('ngrok') else '⚠️'}")
        print(f"   Resend API Key: {'✅' if self.results.get('resend_api') else '❌'}")
        
        print("\n" + "=" * 60)
        if all_local:
            print("✅ LOCAL SETUP COMPLETE")
            print("=" * 60)
            print("\nLocal Tracardi is ready to receive Resend events!")
            print("\nTo enable external webhooks from Resend servers:")
            print("  1. Configure ngrok: ./ngrok config add-authtoken <token>")
            print("  2. Start tunnel: ./ngrok http 8686")
            print("  3. Copy the HTTPS URL (e.g., https://abc123.ngrok.io)")
            print("  4. Set: export RESEND_WEBHOOK_URL=https://abc123.ngrok.io/track")
            print("  5. Run: python scripts/setup_resend_webhooks_auto.py")
            print("\nTo simulate events locally (no ngrok needed):")
            print("  - Use: python scripts/test_resend_webhooks.py")
        else:
            print("⚠️  LOCAL SETUP INCOMPLETE")
            print("=" * 60)
            print("\nSome local configuration is missing.")
            print("Check the errors above and fix the issues.")


async def main():
    verifier = ResendSetupVerifier()
    await verifier.run_verification()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)
