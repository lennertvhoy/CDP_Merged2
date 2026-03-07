#!/usr/bin/env python3
"""
Setup Tracardi Activation Layer - Local Development.

Creates workflows, destinations, and segments for the activation layer.
This script is designed for the local Docker Compose stack.

Usage:
    python scripts/setup_tracardi_activation_layer.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any

# Add repo root to path (works from any location)
REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

import httpx
from dotenv import load_dotenv

from src.core.logger import get_logger

logger = get_logger(__name__)

# Load environment variables from .env.local
load_dotenv(REPO_ROOT / ".env.local")

# Configuration
TRACARDI_API_URL = os.getenv("TRACARDI_API_URL", "http://localhost:8686")
TRACARDI_USERNAME = os.getenv("TRACARDI_USERNAME", "admin@admin.com")
TRACARDI_PASSWORD = os.getenv("TRACARDI_PASSWORD", "")
TRACARDI_SOURCE_ID = os.getenv("TRACARDI_SOURCE_ID", "cdp-api")

if not TRACARDI_PASSWORD:
    logger.error("TRACARDI_PASSWORD not set in .env.local")
    sys.exit(1)


class TracardiActivationClient:
    """Client for configuring Tracardi activation layer."""

    def __init__(self, api_url: str, username: str, password: str):
        self.api_url = api_url.rstrip("/")
        self.username = username
        self.password = password
        self.token: str | None = None
        self.headers: dict[str, str] = {"Content-Type": "application/json"}

    async def authenticate(self) -> bool:
        """Authenticate and cache the access token."""
        url = f"{self.api_url}/user/token"
        payload = {
            "username": self.username,
            "password": self.password,
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
                logger.info("tracardi_authenticated", url=self.api_url)
                return True
            except Exception as exc:
                logger.error("tracardi_auth_error", error=str(exc))
                return False

    async def get_workflows(self) -> list[dict]:
        """List existing workflows."""
        url = f"{self.api_url}/flows"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, timeout=30.0)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result", [])
                return []
            except Exception as exc:
                logger.error("error_listing_workflows", error=str(exc))
                return []

    async def create_workflow(self, workflow: dict) -> tuple[bool, str]:
        """Create a workflow in Tracardi."""
        url = f"{self.api_url}/flow"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, json=workflow, headers=self.headers, timeout=30.0
                )
                if response.status_code in [200, 201]:
                    return True, "Created successfully"
                elif response.status_code == 409:
                    return True, "Already exists"
                else:
                    error = response.text[:200]
                    logger.error(
                        "workflow_create_failed",
                        name=workflow.get("name"),
                        status=response.status_code,
                        error=error,
                    )
                    return False, f"Error {response.status_code}: {error}"
            except Exception as exc:
                logger.error(
                    "workflow_create_exception", name=workflow.get("name"), error=str(exc)
                )
                return False, str(exc)

    async def get_destinations(self) -> list[dict]:
        """List existing destinations."""
        url = f"{self.api_url}/destinations"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, timeout=30.0)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result", [])
                return []
            except Exception as exc:
                logger.error("error_listing_destinations", error=str(exc))
                return []

    async def create_destination(self, destination: dict) -> tuple[bool, str]:
        """Create a destination in Tracardi."""
        url = f"{self.api_url}/destination"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, json=destination, headers=self.headers, timeout=30.0
                )
                if response.status_code in [200, 201]:
                    return True, "Created successfully"
                elif response.status_code == 409:
                    return True, "Already exists"
                else:
                    error = response.text[:200]
                    logger.error(
                        "destination_create_failed",
                        name=destination.get("name"),
                        status=response.status_code,
                        error=error,
                    )
                    return False, f"Error {response.status_code}: {error}"
            except Exception as exc:
                logger.error(
                    "destination_create_exception",
                    name=destination.get("name"),
                    error=str(exc),
                )
                return False, str(exc)

    async def get_segments(self) -> list[dict]:
        """List existing segments."""
        url = f"{self.api_url}/segments"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, timeout=30.0)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result", [])
                return []
            except Exception as exc:
                logger.error("error_listing_segments", error=str(exc))
                return []

    async def create_segment(self, segment: dict) -> tuple[bool, str]:
        """Create a segment in Tracardi."""
        url = f"{self.api_url}/segment"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, json=segment, headers=self.headers, timeout=30.0
                )
                if response.status_code in [200, 201]:
                    return True, "Created successfully"
                elif response.status_code == 409:
                    return True, "Already exists"
                else:
                    error = response.text[:200]
                    logger.error(
                        "segment_create_failed",
                        name=segment.get("name"),
                        status=response.status_code,
                        error=error,
                    )
                    return False, f"Error {response.status_code}: {error}"
            except Exception as exc:
                logger.error(
                    "segment_create_exception", name=segment.get("name"), error=str(exc)
                )
                return False, str(exc)


# Workflow Definitions

def create_kbo_import_workflow() -> dict:
    """Create workflow for KBO import processing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "KBO Import Processor",
        "description": "Process KBO enterprise import events and enrich profiles",
        "enabled": True,
        "type": "collection",
        "projects": ["default"],
        "flow": {
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "position": {"x": 100, "y": 100},
                    "config": {"event": {"type": "kbo.enterprise.imported"}},
                },
                {
                    "id": "set_kbo_traits",
                    "type": "trait",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "traits": {
                            "kbo_number": "{{event.properties.kbo_number}}",
                            "company_name": "{{event.properties.enterprise_name}}",
                            "nace_codes": "{{event.properties.nace_codes}}",
                            "city": "{{event.properties.city}}",
                        }
                    },
                },
                {
                    "id": "add_kbo_tag",
                    "type": "add_tag",
                    "position": {"x": 500, "y": 100},
                    "config": {"tags": ["kbo_enterprise"]},
                },
            ],
            "edges": [
                {"source": "start", "target": "set_kbo_traits"},
                {"source": "set_kbo_traits", "target": "add_kbo_tag"},
            ],
        },
    }


def create_email_engagement_workflow() -> dict:
    """Create workflow for email engagement processing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "Email Engagement Processor",
        "description": "Process email open/click events and update engagement scores",
        "enabled": True,
        "type": "collection",
        "projects": ["default"],
        "flow": {
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "position": {"x": 100, "y": 100},
                    "config": {"event": {"type": ["email.opened", "email.clicked"]}},
                },
                {
                    "id": "increment_score",
                    "type": "increment",
                    "position": {"x": 300, "y": 100},
                    "config": {"field": "traits.engagement_score", "value": 1},
                },
                {
                    "id": "add_engaged_tag",
                    "type": "add_tag",
                    "position": {"x": 500, "y": 100},
                    "config": {"tags": ["email_engaged"]},
                },
                {
                    "id": "set_last_engagement",
                    "type": "trait",
                    "position": {"x": 700, "y": 100},
                    "config": {
                        "traits": {"last_email_engagement": "{{event.metadata.time.insert}}"}
                    },
                },
            ],
            "edges": [
                {"source": "start", "target": "increment_score"},
                {"source": "increment_score", "target": "add_engaged_tag"},
                {"source": "add_engaged_tag", "target": "set_last_engagement"},
            ],
        },
    }


def create_email_bounce_workflow() -> dict:
    """Create workflow for email bounce processing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "Email Bounce Processor",
        "description": "Process email bounce events and mark invalid emails",
        "enabled": True,
        "type": "collection",
        "projects": ["default"],
        "flow": {
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "position": {"x": 100, "y": 100},
                    "config": {"event": {"type": "email.bounced"}},
                },
                {
                    "id": "mark_invalid",
                    "type": "trait",
                    "position": {"x": 300, "y": 100},
                    "config": {"traits": {"email_valid": False}},
                },
                {
                    "id": "add_bounced_tag",
                    "type": "add_tag",
                    "position": {"x": 500, "y": 100},
                    "config": {"tags": ["email_bounced"]},
                },
            ],
            "edges": [
                {"source": "start", "target": "mark_invalid"},
                {"source": "mark_invalid", "target": "add_bounced_tag"},
            ],
        },
    }


def create_campaign_activation_workflow() -> dict:
    """Create workflow for campaign activation triggers."""
    return {
        "id": str(uuid.uuid4()),
        "name": "Campaign Activation Trigger",
        "description": "Trigger campaigns based on segment membership or events",
        "enabled": True,
        "type": "collection",
        "projects": ["default"],
        "flow": {
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "position": {"x": 100, "y": 100},
                    "config": {"event": {"type": "segment.assigned"}},
                },
                {
                    "id": "check_segment",
                    "type": "if",
                    "position": {"x": 300, "y": 100},
                    "config": {"condition": "{{event.properties.segment_name}} exists"},
                },
                {
                    "id": "log_activation",
                    "type": "debug",
                    "position": {"x": 500, "y": 50},
                    "config": {"message": "Campaign activated for segment: {{event.properties.segment_name}}"},
                },
            ],
            "edges": [
                {"source": "start", "target": "check_segment"},
                {"source": "check_segment", "target": "log_activation", "label": "Yes"},
            ],
        },
    }


# Destination Definitions

def create_resend_destination_config() -> dict:
    """Create Resend email destination configuration."""
    return {
        "id": "resend-email",
        "name": "Resend Email Service",
        "description": "Send emails via Resend API",
        "type": "webhook",
        "config": {
            "url": "https://api.resend.com/emails",
            "method": "POST",
            "headers": {
                "Authorization": "Bearer {{env.RESEND_API_KEY}}",
                "Content-Type": "application/json",
            },
            "body": {
                "from": "{{config.from_email}}",
                "to": "{{profile.email}}",
                "subject": "{{config.subject}}",
                "html": "{{config.html_body}}",
                "text": "{{config.text_body}}",
            },
        },
        "tags": ["email", "marketing"],
    }


def create_flexmail_destination_config() -> dict:
    """Create Flexmail destination configuration (placeholder)."""
    return {
        "id": "flexmail",
        "name": "Flexmail",
        "description": "Send emails via Flexmail API (configure credentials)",
        "type": "webhook",
        "config": {
            "url": "https://api.flexmail.com/v1/messages",
            "method": "POST",
            "headers": {
                "Authorization": "Bearer {{env.FLEXMAIL_API_KEY}}",
                "Content-Type": "application/json",
            },
        },
        "tags": ["email", "marketing"],
    }


# Segment Definitions

def create_high_engagement_segment() -> dict:
    """Create high engagement segment."""
    return {
        "id": "high-engagement",
        "name": "High Engagement",
        "description": "Profiles with engagement score >= 5",
        "condition": "traits.engagement_score >= 5",
        "enabled": True,
    }


def create_email_engaged_segment() -> dict:
    """Create email engaged segment."""
    return {
        "id": "email-engaged",
        "name": "Email Engaged",
        "description": "Profiles who have opened or clicked emails",
        "condition": "tags contains 'email_engaged'",
        "enabled": True,
    }


def create_kbo_enterprise_segment() -> dict:
    """Create KBO enterprise segment."""
    return {
        "id": "kbo-enterprises",
        "name": "KBO Enterprises",
        "description": "Belgian companies from KBO dataset",
        "condition": "tags contains 'kbo_enterprise'",
        "enabled": True,
    }


async def setup_activation_layer():
    """Main setup function for Tracardi activation layer."""
    print("=" * 70)
    print("🚀 Tracardi Activation Layer Setup")
    print("=" * 70)
    print(f"\nTracardi API: {TRACARDI_API_URL}")
    print(f"Username: {TRACARDI_USERNAME}")

    # Create client and authenticate
    client = TracardiActivationClient(TRACARDI_API_URL, TRACARDI_USERNAME, TRACARDI_PASSWORD)

    print("\n🔐 Authenticating...")
    if not await client.authenticate():
        print("❌ Authentication failed!")
        return 1
    print("✅ Authentication successful")

    # Check current state
    print("\n📊 Checking current state...")
    existing_workflows = await client.get_workflows()
    existing_destinations = await client.get_destinations()
    existing_segments = await client.get_segments()

    print(f"  Existing workflows: {len(existing_workflows)}")
    print(f"  Existing destinations: {len(existing_destinations)}")
    print(f"  Existing segments: {len(existing_segments)}")

    results = {
        "workflows": {"created": 0, "existing": 0, "failed": 0},
        "destinations": {"created": 0, "existing": 0, "failed": 0},
        "segments": {"created": 0, "existing": 0, "failed": 0},
    }

    # Create workflows
    print("\n" + "-" * 70)
    print("📋 Creating Workflows")
    print("-" * 70)

    workflows = [
        create_kbo_import_workflow(),
        create_email_engagement_workflow(),
        create_email_bounce_workflow(),
        create_campaign_activation_workflow(),
    ]

    for workflow in workflows:
        name = workflow["name"]
        print(f"\n  Creating: {name}...")
        success, message = await client.create_workflow(workflow)

        if success:
            if "Already exists" in message:
                print(f"    ⚠️  Already exists")
                results["workflows"]["existing"] += 1
            else:
                print(f"    ✅ Created")
                results["workflows"]["created"] += 1
        else:
            print(f"    ❌ Failed: {message}")
            results["workflows"]["failed"] += 1

    # Create destinations
    print("\n" + "-" * 70)
    print("📧 Creating Destinations")
    print("-" * 70)

    destinations = [
        create_resend_destination_config(),
        create_flexmail_destination_config(),
    ]

    for destination in destinations:
        name = destination["name"]
        print(f"\n  Creating: {name}...")
        success, message = await client.create_destination(destination)

        if success:
            if "Already exists" in message:
                print(f"    ⚠️  Already exists")
                results["destinations"]["existing"] += 1
            else:
                print(f"    ✅ Created")
                results["destinations"]["created"] += 1
        else:
            print(f"    ❌ Failed: {message}")
            results["destinations"]["failed"] += 1

    # Create segments
    print("\n" + "-" * 70)
    print("👥 Creating Segments")
    print("-" * 70)

    segments = [
        create_high_engagement_segment(),
        create_email_engaged_segment(),
        create_kbo_enterprise_segment(),
    ]

    for segment in segments:
        name = segment["name"]
        print(f"\n  Creating: {name}...")
        success, message = await client.create_segment(segment)

        if success:
            if "Already exists" in message:
                print(f"    ⚠️  Already exists")
                results["segments"]["existing"] += 1
            else:
                print(f"    ✅ Created")
                results["segments"]["created"] += 1
        else:
            print(f"    ❌ Failed: {message}")
            results["segments"]["failed"] += 1

    # Summary
    print("\n" + "=" * 70)
    print("📊 Setup Summary")
    print("=" * 70)
    print(f"\nWorkflows:")
    print(f"  Created:   {results['workflows']['created']}")
    print(f"  Existing:  {results['workflows']['existing']}")
    print(f"  Failed:    {results['workflows']['failed']}")
    print(f"\nDestinations:")
    print(f"  Created:   {results['destinations']['created']}")
    print(f"  Existing:  {results['destinations']['existing']}")
    print(f"  Failed:    {results['destinations']['failed']}")
    print(f"\nSegments:")
    print(f"  Created:   {results['segments']['created']}")
    print(f"  Existing:  {results['segments']['existing']}")
    print(f"  Failed:    {results['segments']['failed']}")

    total_failed = (
        results["workflows"]["failed"]
        + results["destinations"]["failed"]
        + results["segments"]["failed"]
    )

    if total_failed == 0:
        print("\n" + "=" * 70)
        print("✅ Activation layer configured successfully!")
        print("=" * 70)
        print("\nNext Steps:")
        print("  1. Open Tracardi GUI to verify:")
        print(f"     http://localhost:8787")
        print("  2. Check workflows in Process Flows section")
        print("  3. Verify destinations are configured")
        print("  4. Test email engagement tracking")
        print("  5. Run: python scripts/smoke_test_tracardi_e2e.py")
        return 0
    else:
        print(f"\n⚠️  Setup completed with {total_failed} failures")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(setup_activation_layer())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
