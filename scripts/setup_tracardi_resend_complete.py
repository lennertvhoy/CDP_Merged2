#!/usr/bin/env python3
"""
Complete Tracardi Setup for Resend Email Integration.
Creates event sources, event types, and workflows for processing email events.

Usage:
    python scripts/setup_tracardi_resend_complete.py

Environment Variables:
    TRACARDI_API_URL - Tracardi API endpoint (default: http://137.117.212.154:8686)
    TRACARDI_USERNAME - Tracardi username (default: admin@admin.com)
    TRACARDI_PASSWORD - Tracardi password (required)
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import requests
from src.core.logger import get_logger

logger = get_logger(__name__)

# Configuration
TRACARDI_API_URL = os.getenv("TRACARDI_API_URL", "http://137.117.212.154:8686")
TRACARDI_GUI_URL = TRACARDI_API_URL.replace(":8686", ":8787")
TRACARDI_USERNAME = os.getenv("TRACARDI_USERNAME", "admin@admin.com")
TRACARDI_PASSWORD = os.getenv("TRACARDI_PASSWORD")

if not TRACARDI_PASSWORD:
    import subprocess
    try:
        result = subprocess.run(
            ["terraform", "-chdir=infra/tracardi", "output", "-raw", "tracardi_admin_password"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            TRACARDI_PASSWORD = result.stdout.strip()
    except Exception:
        pass

if not TRACARDI_PASSWORD:
    raise RuntimeError("TRACARDI_PASSWORD must be set")

# Bridge IDs (REST and Webhook)
BRIDGE_REST = "778ded05-4ff3-4e08-9a86-72c0195fa95d"
BRIDGE_WEBHOOK = "3d8bb87e-28d1-4a38-b19c-d0c1fbb71e22"

# ============================================================================
# RESEND EMAIL EVENT TYPES
# ============================================================================

RESEND_EVENT_TYPES = {
    "email.sent": {
        "name": "Email Sent",
        "description": "Email was sent from Resend",
        "properties": {
            "email_id": {"type": "string"},
            "to": {"type": "string"},
            "from": {"type": "string"},
            "subject": {"type": "string"},
            "timestamp": {"type": "datetime"},
        },
    },
    "email.delivered": {
        "name": "Email Delivered",
        "description": "Email was successfully delivered to recipient inbox",
        "properties": {
            "email_id": {"type": "string"},
            "to": {"type": "string"},
            "timestamp": {"type": "datetime"},
        },
    },
    "email.delivery_delayed": {
        "name": "Email Delivery Delayed",
        "description": "Email delivery is temporarily delayed",
        "properties": {
            "email_id": {"type": "string"},
            "to": {"type": "string"},
            "reason": {"type": "string"},
            "timestamp": {"type": "datetime"},
        },
    },
    "email.opened": {
        "name": "Email Opened",
        "description": "Recipient opened the email",
        "properties": {
            "email_id": {"type": "string"},
            "to": {"type": "string"},
            "timestamp": {"type": "datetime"},
            "user_agent": {"type": "string"},
            "ip_address": {"type": "string"},
        },
    },
    "email.clicked": {
        "name": "Email Clicked",
        "description": "Recipient clicked a link in the email",
        "properties": {
            "email_id": {"type": "string"},
            "to": {"type": "string"},
            "link": {"type": "string"},
            "timestamp": {"type": "datetime"},
            "user_agent": {"type": "string"},
            "ip_address": {"type": "string"},
        },
    },
    "email.bounced": {
        "name": "Email Bounced",
        "description": "Email bounced (hard or soft bounce)",
        "properties": {
            "email_id": {"type": "string"},
            "to": {"type": "string"},
            "bounce_type": {"type": "string"},  # hard_bounce, soft_bounce
            "bounce_reason": {"type": "string"},
            "timestamp": {"type": "datetime"},
        },
    },
    "email.complained": {
        "name": "Email Complained",
        "description": "Recipient marked email as spam",
        "properties": {
            "email_id": {"type": "string"},
            "to": {"type": "string"},
            "timestamp": {"type": "datetime"},
        },
    },
}

# ============================================================================
# EVENT SOURCES
# ============================================================================

EVENT_SOURCES = {
    "resend-webhook": {
        "name": "Resend Email Webhook",
        "description": "Email events from Resend (sent, delivered, opened, clicked, bounced, complained)",
        "type": ["webhook"],
        "bridge_id": BRIDGE_WEBHOOK,
        "bridge_name": "Webhook API Bridge",
        "tags": ["email", "resend", "marketing", "engagement", "webhook"],
    },
}

# ============================================================================
# WORKFLOW DEFINITIONS
# ============================================================================

def create_email_engagement_workflow() -> dict:
    """Create workflow for processing email engagement events (opened, clicked)."""
    flow_id = str(uuid.uuid4())
    return {
        "id": flow_id,
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
                    "config": {
                        "event": {
                            "type": ["email.opened", "email.clicked"]
                        }
                    }
                },
                {
                    "id": "increment_engagement_score",
                    "type": "increment",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "field": "traits.engagement_score",
                        "value": 1
                    }
                },
                {
                    "id": "add_engaged_tag",
                    "type": "add_tag",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "tags": ["email_engaged"]
                    }
                },
                {
                    "id": "update_last_engagement",
                    "type": "trait",
                    "position": {"x": 700, "y": 100},
                    "config": {
                        "traits": {
                            "last_email_engagement": "{{event.metadata.time.insert}}",
                            "last_email_event": "{{event.type}}"
                        }
                    }
                },
                {
                    "id": "record_email_metadata",
                    "type": "trait",
                    "position": {"x": 900, "y": 100},
                    "config": {
                        "traits": {
                            "last_email_id": "{{event.properties.email_id}}",
                            "last_email_subject": "{{event.properties.subject}}"
                        }
                    }
                }
            ],
            "edges": [
                {"source": "start", "target": "increment_engagement_score"},
                {"source": "increment_engagement_score", "target": "add_engaged_tag"},
                {"source": "add_engaged_tag", "target": "update_last_engagement"},
                {"source": "update_last_engagement", "target": "record_email_metadata"}
            ]
        }
    }


def create_email_bounce_workflow() -> dict:
    """Create workflow for processing email bounce events."""
    flow_id = str(uuid.uuid4())
    return {
        "id": flow_id,
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
                    "config": {
                        "event": {
                            "type": "email.bounced"
                        }
                    }
                },
                {
                    "id": "mark_invalid_email",
                    "type": "trait",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "traits": {
                            "email_valid": False,
                            "email_bounced_at": "{{event.metadata.time.insert}}"
                        }
                    }
                },
                {
                    "id": "add_bounced_tag",
                    "type": "add_tag",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "tags": ["email_bounced"]
                    }
                },
                {
                    "id": "record_bounce_details",
                    "type": "trait",
                    "position": {"x": 700, "y": 100},
                    "config": {
                        "traits": {
                            "email_bounce_type": "{{event.properties.bounce_type}}",
                            "email_bounce_reason": "{{event.properties.bounce_reason}}"
                        }
                    }
                }
            ],
            "edges": [
                {"source": "start", "target": "mark_invalid_email"},
                {"source": "mark_invalid_email", "target": "add_bounced_tag"},
                {"source": "add_bounced_tag", "target": "record_bounce_details"}
            ]
        }
    }


def create_email_delivery_workflow() -> dict:
    """Create workflow for processing email delivery events."""
    flow_id = str(uuid.uuid4())
    return {
        "id": flow_id,
        "name": "Email Delivery Processor",
        "description": "Process email sent and delivered events",
        "enabled": True,
        "type": "collection",
        "projects": ["default"],
        "flow": {
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "event": {
                            "type": ["email.sent", "email.delivered"]
                        }
                    }
                },
                {
                    "id": "record_email_sent",
                    "type": "trait",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "traits": {
                            "last_email_sent_at": "{{event.metadata.time.insert}}",
                            "email_valid": True
                        }
                    }
                },
                {
                    "id": "increment_emails_sent",
                    "type": "increment",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "field": "traits.total_emails_sent",
                        "value": 1
                    }
                }
            ],
            "edges": [
                {"source": "start", "target": "record_email_sent"},
                {"source": "record_email_sent", "target": "increment_emails_sent"}
            ]
        }
    }


def create_high_engagement_segment_workflow() -> dict:
    """Create workflow for assigning high engagement segments."""
    flow_id = str(uuid.uuid4())
    return {
        "id": flow_id,
        "name": "High Engagement Segment Assignment",
        "description": "Assign highly engaged profiles to VIP segment based on engagement score",
        "enabled": True,
        "type": "collection",
        "projects": ["default"],
        "flow": {
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "event": {
                            "type": ["email.opened", "email.clicked"]
                        }
                    }
                },
                {
                    "id": "check_engagement_score",
                    "type": "if",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "condition": "{{profile.traits.engagement_score >= 5}}"
                    }
                },
                {
                    "id": "add_vip_tag",
                    "type": "add_tag",
                    "position": {"x": 500, "y": 50},
                    "config": {
                        "tags": ["vip", "high_engagement"]
                    }
                },
                {
                    "id": "set_engagement_tier",
                    "type": "trait",
                    "position": {"x": 700, "y": 50},
                    "config": {
                        "traits": {
                            "engagement_tier": "high"
                        }
                    }
                }
            ],
            "edges": [
                {"source": "start", "target": "check_engagement_score"},
                {"source": "check_engagement_score", "target": "add_vip_tag", "label": "true"},
                {"source": "add_vip_tag", "target": "set_engagement_tier"}
            ]
        }
    }


def create_email_complaint_workflow() -> dict:
    """Create workflow for processing spam complaints."""
    flow_id = str(uuid.uuid4())
    return {
        "id": flow_id,
        "name": "Email Complaint Processor",
        "description": "Process spam complaints and suppress profiles",
        "enabled": True,
        "type": "collection",
        "projects": ["default"],
        "flow": {
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "event": {
                            "type": "email.complained"
                        }
                    }
                },
                {
                    "id": "mark_suppressed",
                    "type": "trait",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "traits": {
                            "email_suppressed": True,
                            "email_suppression_reason": "spam_complaint",
                            "email_suppressed_at": "{{event.metadata.time.insert}}"
                        }
                    }
                },
                {
                    "id": "add_complaint_tag",
                    "type": "add_tag",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "tags": ["email_complaint", "do_not_email"]
                    }
                }
            ],
            "edges": [
                {"source": "start", "target": "mark_suppressed"},
                {"source": "mark_suppressed", "target": "add_complaint_tag"}
            ]
        }
    }


# ============================================================================
# TRACARDI API CLIENT
# ============================================================================

class TracardiClient:
    """Client for Tracardi API operations."""
    
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
                response = await client.post(url, data=payload, timeout=30.0)
                if response.status_code == 422:
                    response = await client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                self.token = data.get("access_token")
                return True
            except Exception as exc:
                logger.error("tracardi_auth_error", error=str(exc))
                return False
    
    def get_headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("Not authenticated")
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
    
    async def create_event_source(self, source_id: str, config: dict) -> bool:
        """Create an event source."""
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
                response = await client.post(url, json=payload, headers=self.get_headers(), timeout=30.0)
                if response.status_code in [200, 201]:
                    return True
                elif response.status_code == 409:
                    return True  # Already exists
                else:
                    logger.error("create_source_failed", status=response.status_code, text=response.text[:200])
                    return False
            except Exception as e:
                logger.error("create_source_error", error=str(e))
                return False
    
    async def create_event_type(self, event_type: str, config: dict) -> bool:
        """Create an event type."""
        url = f"{self.api_url}/event-type"
        payload = {
            "id": event_type,
            "name": config["name"],
            "description": config["description"],
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self.get_headers(), timeout=30.0)
                if response.status_code in [200, 201]:
                    return True
                elif response.status_code == 409:
                    return True  # Already exists
                else:
                    logger.error("create_event_type_failed", status=response.status_code, text=response.text[:200])
                    return False
            except Exception as e:
                logger.error("create_event_type_error", error=str(e))
                return False
    
    async def create_workflow(self, workflow: dict) -> tuple[bool, str]:
        """Create a workflow."""
        url = f"{self.api_url}/flow"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, json=workflow, headers=self.get_headers(), timeout=30.0
                )
                if response.status_code in [200, 201]:
                    return True, "Created"
                elif response.status_code == 409:
                    return True, "Already exists"
                else:
                    return False, f"Error {response.status_code}: {response.text[:200]}"
            except Exception as e:
                return False, str(e)
    
    async def list_event_sources(self) -> list[dict]:
        """List existing event sources."""
        url = f"{self.api_url}/event-sources"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.get_headers(), timeout=30.0)
                response.raise_for_status()
                data = response.json()
                return data.get("result", [])
            except Exception as e:
                logger.error("list_sources_error", error=str(e))
                return []
    
    async def list_workflows(self) -> list[dict]:
        """List existing workflows."""
        url = f"{self.api_url}/flows"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.get_headers(), timeout=30.0)
                response.raise_for_status()
                data = response.json()
                return data.get("result", [])
            except Exception as e:
                logger.error("list_workflows_error", error=str(e))
                return []
    
    async def test_event_tracking(self, source_id: str, event_type: str, email: str = "test@example.com") -> bool:
        """Test tracking an event."""
        url = f"{self.api_url}/track"
        
        payload = {
            "source": {"id": source_id},
            "profile": {"traits": {"email": email}},
            "events": [{
                "type": event_type,
                "properties": {
                    "email_id": f"test-{uuid.uuid4().hex[:8]}",
                    "to": email,
                    "subject": "Test Email",
                    "timestamp": datetime.now().isoformat(),
                }
            }]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=30.0)
                return response.status_code in [200, 201]
            except Exception as e:
                logger.error("test_tracking_error", error=str(e))
                return False


# ============================================================================
# MAIN SETUP
# ============================================================================

async def main():
    print("=" * 70)
    print("🚀 Tracardi Setup for Resend Email Integration")
    print("=" * 70)
    print(f"\nTracardi API: {TRACARDI_API_URL}")
    print(f"Tracardi GUI: {TRACARDI_GUI_URL}")
    print(f"Username: {TRACARDI_USERNAME}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    client = TracardiClient(TRACARDI_API_URL, TRACARDI_USERNAME, TRACARDI_PASSWORD)
    
    # Authenticate
    print("\n🔐 Authenticating...")
    if not await client.authenticate():
        print("❌ Authentication failed!")
        return 1
    print("✅ Authentication successful")
    
    # Get current state
    print("\n📊 Current State:")
    existing_sources = await client.list_event_sources()
    existing_workflows = await client.list_workflows()
    print(f"  Event Sources: {len(existing_sources)}")
    print(f"  Workflows: {len(existing_workflows)}")
    
    results = {
        "sources": {"created": 0, "failed": 0},
        "event_types": {"created": 0, "failed": 0},
        "workflows": {"created": 0, "failed": 0, "existing": 0},
        "tests": {"passed": 0, "failed": 0},
    }
    
    # Step 1: Create Event Sources
    print("\n" + "-" * 70)
    print("📡 Step 1: Creating Event Sources")
    print("-" * 70)
    
    for source_id, config in EVENT_SOURCES.items():
        print(f"  Creating {source_id}...", end=" ")
        if await client.create_event_source(source_id, config):
            print("✅")
            results["sources"]["created"] += 1
        else:
            print("❌")
            results["sources"]["failed"] += 1
    
    # Step 2: Create Event Types
    print("\n" + "-" * 70)
    print("📋 Step 2: Creating Event Types")
    print("-" * 70)
    
    for event_type, config in RESEND_EVENT_TYPES.items():
        print(f"  Creating {event_type}...", end=" ")
        if await client.create_event_type(event_type, config):
            print("✅")
            results["event_types"]["created"] += 1
        else:
            print("❌")
            results["event_types"]["failed"] += 1
    
    # Step 3: Create Workflows
    print("\n" + "-" * 70)
    print("⚙️  Step 3: Creating Workflows")
    print("-" * 70)
    
    workflows = [
        create_email_engagement_workflow(),
        create_email_bounce_workflow(),
        create_email_delivery_workflow(),
        create_high_engagement_segment_workflow(),
        create_email_complaint_workflow(),
    ]
    
    for workflow in workflows:
        name = workflow["name"]
        print(f"  Creating {name}...", end=" ")
        success, message = await client.create_workflow(workflow)
        if success:
            if message == "Already exists":
                print("⚠️  Already exists")
                results["workflows"]["existing"] += 1
            else:
                print("✅")
                results["workflows"]["created"] += 1
        else:
            print(f"❌ {message}")
            results["workflows"]["failed"] += 1
    
    # Step 4: Test Event Tracking
    print("\n" + "-" * 70)
    print("🧪 Step 4: Testing Event Tracking")
    print("-" * 70)
    
    test_events = [
        ("resend-webhook", "email.opened"),
        ("resend-webhook", "email.clicked"),
    ]
    
    for source_id, event_type in test_events:
        print(f"  Testing {event_type}...", end=" ")
        if await client.test_event_tracking(source_id, event_type):
            print("✅")
            results["tests"]["passed"] += 1
        else:
            print("⚠️")
            results["tests"]["failed"] += 1
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Setup Summary")
    print("=" * 70)
    print(f"\nEvent Sources: {results['sources']['created']} created, {results['sources']['failed']} failed")
    print(f"Event Types: {results['event_types']['created']} created, {results['event_types']['failed']} failed")
    print(f"Workflows: {results['workflows']['created']} created, {results['workflows']['existing']} existing, {results['workflows']['failed']} failed")
    print(f"Tests: {results['tests']['passed']} passed, {results['tests']['failed']} failed")
    
    # Output created workflows info
    if results["workflows"]["created"] > 0 or results["workflows"]["existing"] > 0:
        print("\n📋 Created Workflows:")
        print("  1. Email Engagement Processor - Updates scores on open/click")
        print("  2. Email Bounce Processor - Marks invalid emails on bounce")
        print("  3. Email Delivery Processor - Tracks sent/delivered emails")
        print("  4. High Engagement Segment Assignment - VIP tagging for engaged users")
        print("  5. Email Complaint Processor - Handles spam complaints")
    
    print("\n" + "=" * 70)
    if results["workflows"]["failed"] == 0 and results["sources"]["failed"] == 0:
        print("✅ Tracardi setup complete!")
        print("=" * 70)
        print("\nNext Steps:")
        print(f"  1. Configure Resend webhook to send events to:")
        print(f"     {TRACARDI_API_URL}/track")
        print(f"  2. Use source ID: resend-webhook")
        print(f"  3. View workflows in Tracardi GUI: {TRACARDI_GUI_URL}/flows")
        print(f"  4. Send a test email via Resend to verify event processing")
        return 0
    else:
        print("⚠️  Setup completed with some failures")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
