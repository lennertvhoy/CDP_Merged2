#!/usr/bin/env python3
"""
Setup Tracardi workflows via API.
Creates workflows for KBO import processing and email event handling.
"""

import asyncio
import os
import sys
import uuid
from typing import Any

sys.path.insert(0, "/home/ff/.openclaw/workspace/repos/CDP_Merged")

import httpx
from src.core.logger import get_logger

logger = get_logger(__name__)

# Configuration
TRACARDI_API_URL = os.getenv("TRACARDI_API_URL", "http://137.117.212.154:8686")
TRACARDI_USERNAME = os.getenv("TRACARDI_USERNAME", "admin@admin.com")
TRACARDI_PASSWORD = os.getenv("TRACARDI_PASSWORD")

if not TRACARDI_PASSWORD:
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
    raise RuntimeError("TRACARDI_PASSWORD must be set")


class TracardiWorkflowClient:
    """Client for creating Tracardi workflows."""
    
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
                logger.info("tracardi_authenticated")
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
    
    async def list_workflows(self) -> list[dict]:
        """List existing workflows/flows."""
        url = f"{self.api_url}/flows"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.get_headers(), timeout=30.0)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result", [])
                return []
            except Exception as e:
                logger.error("error_listing_workflows", error=str(e))
                return []
    
    async def create_workflow(self, workflow_def: dict) -> tuple[bool, str]:
        """Create a workflow/flow in Tracardi.
        
        Returns: (success, message)
        """
        url = f"{self.api_url}/flow"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, json=workflow_def, headers=self.get_headers(), timeout=30.0
                )
                
                if response.status_code in [200, 201]:
                    return True, "Created successfully"
                elif response.status_code == 409:
                    return True, "Already exists"
                else:
                    error_text = response.text[:300]
                    logger.error(
                        "failed_to_create_workflow",
                        status_code=response.status_code,
                        response=error_text,
                    )
                    return False, f"Error {response.status_code}: {error_text}"
                    
            except Exception as e:
                logger.error("error_creating_workflow", error=str(e))
                return False, str(e)


def create_kbo_import_workflow() -> dict:
    """Create workflow definition for KBO import processing."""
    flow_id = str(uuid.uuid4())
    
    return {
        "id": flow_id,
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
                    "config": {
                        "event": {
                            "type": "kbo.enterprise.imported"
                        }
                    }
                },
                {
                    "id": "set_kbo_number",
                    "type": "trait",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "traits": {
                            "kbo_number": "{{event.properties.kbo_number}}"
                        }
                    }
                },
                {
                    "id": "set_company_name",
                    "type": "trait",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "traits": {
                            "company_name": "{{event.properties.enterprise_name}}"
                        }
                    }
                },
                {
                    "id": "set_nace_codes",
                    "type": "trait",
                    "position": {"x": 700, "y": 100},
                    "config": {
                        "traits": {
                            "nace_codes": "{{event.properties.nace_codes}}"
                        }
                    }
                },
                {
                    "id": "set_location",
                    "type": "trait",
                    "position": {"x": 900, "y": 100},
                    "config": {
                        "traits": {
                            "city": "{{event.properties.city}}"
                        }
                    }
                },
                {
                    "id": "add_kbo_tag",
                    "type": "add_tag",
                    "position": {"x": 1100, "y": 100},
                    "config": {
                        "tags": ["kbo_enterprise"]
                    }
                }
            ],
            "edges": [
                {"source": "start", "target": "set_kbo_number"},
                {"source": "set_kbo_number", "target": "set_company_name"},
                {"source": "set_company_name", "target": "set_nace_codes"},
                {"source": "set_nace_codes", "target": "set_location"},
                {"source": "set_location", "target": "add_kbo_tag"}
            ]
        }
    }


def create_email_engagement_workflow() -> dict:
    """Create workflow definition for email engagement processing."""
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
                    "id": "increment_score",
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
                    "id": "set_last_engagement",
                    "type": "trait",
                    "position": {"x": 700, "y": 100},
                    "config": {
                        "traits": {
                            "last_email_engagement": "{{event.metadata.time.insert}}"
                        }
                    }
                }
            ],
            "edges": [
                {"source": "start", "target": "increment_score"},
                {"source": "increment_score", "target": "add_engaged_tag"},
                {"source": "add_engaged_tag", "target": "set_last_engagement"}
            ]
        }
    }


def create_email_bounce_workflow() -> dict:
    """Create workflow definition for email bounce processing."""
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
                    "id": "mark_invalid",
                    "type": "trait",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "traits": {
                            "email_valid": False
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
                    "id": "record_bounce_reason",
                    "type": "trait",
                    "position": {"x": 700, "y": 100},
                    "config": {
                        "traits": {
                            "email_bounce_reason": "{{event.properties.bounce_type}}"
                        }
                    }
                }
            ],
            "edges": [
                {"source": "start", "target": "mark_invalid"},
                {"source": "mark_invalid", "target": "add_bounced_tag"},
                {"source": "add_bounced_tag", "target": "record_bounce_reason"}
            ]
        }
    }


def create_high_engagement_segment_workflow() -> dict:
    """Create workflow for high engagement segment assignment."""
    flow_id = str(uuid.uuid4())
    
    return {
        "id": flow_id,
        "name": "High Engagement Segment Assignment",
        "description": "Assign highly engaged profiles to VIP segment",
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
                    "id": "check_engagement",
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
                    "id": "set_tier",
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
                {"source": "start", "target": "check_engagement"},
                {"source": "check_engagement", "target": "add_vip_tag", "label": "Yes"},
                {"source": "add_vip_tag", "target": "set_tier"}
            ]
        }
    }


async def setup_workflows():
    """Main setup function."""
    print("=" * 70)
    print("🚀 Tracardi Workflow Setup")
    print("=" * 70)
    print(f"\nTracardi API: {TRACARDI_API_URL}")
    
    # Create client and authenticate
    client = TracardiWorkflowClient(TRACARDI_API_URL, TRACARDI_USERNAME, TRACARDI_PASSWORD)
    
    print("\n🔐 Authenticating...")
    if not await client.authenticate():
        print("❌ Authentication failed!")
        return 1
    print("✅ Authentication successful")
    
    # Check existing workflows
    print("\n📊 Checking existing workflows...")
    existing = await client.list_workflows()
    print(f"  Found {len(existing)} existing workflows")
    
    # Define workflows to create
    workflows = [
        create_kbo_import_workflow(),
        create_email_engagement_workflow(),
        create_email_bounce_workflow(),
        create_high_engagement_segment_workflow(),
    ]
    
    results = {"created": 0, "failed": 0, "existing": 0}
    
    print("\n" + "-" * 70)
    print("📋 Creating Workflows")
    print("-" * 70)
    
    for workflow in workflows:
        name = workflow["name"]
        print(f"\n  Creating: {name}...")
        success, message = await client.create_workflow(workflow)
        
        if success:
            if "Already exists" in message:
                print(f"    ⚠️  Already exists")
                results["existing"] += 1
            else:
                print(f"    ✅ Created")
                results["created"] += 1
        else:
            print(f"    ❌ Failed: {message}")
            results["failed"] += 1
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Setup Summary")
    print("=" * 70)
    print(f"  Created:   {results['created']}")
    print(f"  Existing:  {results['existing']}")
    print(f"  Failed:    {results['failed']}")
    
    if results["failed"] == 0:
        print("\n✅ All workflows configured successfully!")
        print("\nNext Steps:")
        print("  1. Verify workflows in Tracardi GUI:")
        print(f"     http://137.117.212.154:8787/flows")
        print("  2. Configure Resend webhooks to point to Tracardi")
        print("  3. Test event flows")
        return 0
    else:
        print(f"\n⚠️  Setup completed with {results['failed']} failures")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(setup_workflows())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
