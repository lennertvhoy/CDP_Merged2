#!/usr/bin/env python3
"""
Configure Tracardi to receive and process Resend email events.
Sets up event sources, event types, and workflows.
"""

import asyncio
import os
import sys
from typing import Any

sys.path.insert(0, "/home/ff/.openclaw/workspace/repos/CDP_Merged")

import httpx
from src.core.logger import get_logger

logger = get_logger(__name__)

# Configuration
TRACARDI_API_URL = os.getenv("TRACARDI_API_URL", "http://137.117.212.154:8686")
TRACARDI_TOKEN = os.getenv("TRACARDI_TOKEN")

if not TRACARDI_TOKEN:
    raise RuntimeError("TRACARDI_TOKEN must be set before running setup_tracardi_resend_workflow.py")

# Resend event types mapping
RESEND_EVENT_TYPES = {
    "email.sent": {
        "name": "Email Sent",
        "description": "Email was sent from Resend",
        "properties": {
            "email_id": "string",
            "to": "string",
            "from": "string",
            "subject": "string",
            "timestamp": "datetime",
        },
    },
    "email.delivered": {
        "name": "Email Delivered",
        "description": "Email was successfully delivered to recipient",
        "properties": {
            "email_id": "string",
            "to": "string",
            "timestamp": "datetime",
        },
    },
    "email.opened": {
        "name": "Email Opened",
        "description": "Recipient opened the email",
        "properties": {
            "email_id": "string",
            "to": "string",
            "timestamp": "datetime",
            "user_agent": "string",
        },
    },
    "email.clicked": {
        "name": "Email Clicked",
        "description": "Recipient clicked a link in the email",
        "properties": {
            "email_id": "string",
            "to": "string",
            "link": "string",
            "timestamp": "datetime",
        },
    },
    "email.bounced": {
        "name": "Email Bounced",
        "description": "Email bounced (hard or soft)",
        "properties": {
            "email_id": "string",
            "to": "string",
            "bounce_type": "string",
            "timestamp": "datetime",
        },
    },
}

HEADERS = {
    "Authorization": f"Bearer {TRACARDI_TOKEN}",
    "Content-Type": "application/json",
}


async def create_event_type(client: httpx.AsyncClient, event_type: str, config: dict) -> bool:
    """Create an event type in Tracardi."""
    url = f"{TRACARDI_API_URL}/event-type"
    
    payload = {
        "id": event_type,
        "name": config["name"],
        "description": config["description"],
        "properties": config["properties"],
    }
    
    try:
        response = await client.post(url, json=payload, headers=HEADERS)
        
        if response.status_code in [200, 201]:
            logger.info("event_type_created", event_type=event_type)
            print(f"  ✅ Created event type: {event_type}")
            return True
        elif response.status_code == 409:
            logger.info("event_type_already_exists", event_type=event_type)
            print(f"  ⚠️  Event type already exists: {event_type}")
            return True
        else:
            logger.error(
                "failed_to_create_event_type",
                event_type=event_type,
                status_code=response.status_code,
                response=response.text,
            )
            print(f"  ❌ Failed to create event type {event_type}: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error("error_creating_event_type", event_type=event_type, error=str(e))
        print(f"  ❌ Error creating event type {event_type}: {e}")
        return False


async def create_event_source(client: httpx.AsyncClient) -> bool:
    """Create Resend as an event source in Tracardi."""
    url = f"{TRACARDI_API_URL}/source"
    
    payload = {
        "id": "resend",
        "name": "Resend Email Service",
        "description": "Email events from Resend API",
        "type": "webhook",
        "tags": ["email", "marketing"],
    }
    
    try:
        response = await client.post(url, json=payload, headers=HEADERS)
        
        if response.status_code in [200, 201]:
            logger.info("event_source_created", source="resend")
            print(f"  ✅ Created event source: resend")
            return True
        elif response.status_code == 409:
            logger.info("event_source_already_exists", source="resend")
            print(f"  ⚠️  Event source already exists: resend")
            return True
        else:
            logger.error(
                "failed_to_create_event_source",
                status_code=response.status_code,
                response=response.text,
            )
            print(f"  ❌ Failed to create event source: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error("error_creating_event_source", error=str(e))
        print(f"  ❌ Error creating event source: {e}")
        return False


async def create_engagement_workflow(client: httpx.AsyncClient) -> bool:
    """Create a workflow for processing email engagement events."""
    url = f"{TRACARDI_API_URL}/flow"
    
    # Workflow definition for processing email engagement
    workflow = {
        "id": "email-engagement-processor",
        "name": "Email Engagement Processor",
        "description": "Process email open/click events and update engagement scores",
        "enabled": True,
        "trigger": {
            "type": "event",
            "events": ["email.opened", "email.clicked"],
        },
        "actions": [
            {
                "id": "update_engagement_score",
                "name": "Update Engagement Score",
                "type": "increment",
                "config": {
                    "field": "traits.engagement_score",
                    "value": 1,
                },
            },
            {
                "id": "add_engaged_tag",
                "name": "Add Engaged Tag",
                "type": "add_tag",
                "config": {
                    "tags": ["email_engaged"],
                },
            },
            {
                "id": "update_last_engagement",
                "name": "Update Last Engagement",
                "type": "set_field",
                "config": {
                    "field": "traits.last_email_engagement",
                    "value": "{{event.timestamp}}",
                },
            },
        ],
    }
    
    try:
        response = await client.post(url, json=workflow, headers=HEADERS)
        
        if response.status_code in [200, 201]:
            logger.info("engagement_workflow_created")
            print(f"  ✅ Created engagement workflow")
            return True
        elif response.status_code == 409:
            logger.info("engagement_workflow_already_exists")
            print(f"  ⚠️  Engagement workflow already exists")
            return True
        else:
            logger.error(
                "failed_to_create_workflow",
                status_code=response.status_code,
                response=response.text,
            )
            print(f"  ❌ Failed to create workflow: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error("error_creating_workflow", error=str(e))
        print(f"  ❌ Error creating workflow: {e}")
        return False


async def create_bounce_workflow(client: httpx.AsyncClient) -> bool:
    """Create a workflow for processing bounce events."""
    url = f"{TRACARDI_API_URL}/flow"
    
    workflow = {
        "id": "email-bounce-processor",
        "name": "Email Bounce Processor",
        "description": "Process email bounce events and mark invalid emails",
        "enabled": True,
        "trigger": {
            "type": "event",
            "events": ["email.bounced"],
        },
        "actions": [
            {
                "id": "mark_invalid_email",
                "name": "Mark Invalid Email",
                "type": "set_field",
                "config": {
                    "field": "traits.email_valid",
                    "value": False,
                },
            },
            {
                "id": "add_bounced_tag",
                "name": "Add Bounced Tag",
                "type": "add_tag",
                "config": {
                    "tags": ["email_bounced"],
                },
            },
        ],
    }
    
    try:
        response = await client.post(url, json=workflow, headers=HEADERS)
        
        if response.status_code in [200, 201]:
            logger.info("bounce_workflow_created")
            print(f"  ✅ Created bounce workflow")
            return True
        elif response.status_code == 409:
            logger.info("bounce_workflow_already_exists")
            print(f"  ⚠️  Bounce workflow already exists")
            return True
        else:
            logger.error(
                "failed_to_create_bounce_workflow",
                status_code=response.status_code,
                response=response.text,
            )
            print(f"  ❌ Failed to create bounce workflow: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error("error_creating_bounce_workflow", error=str(e))
        print(f"  ❌ Error creating bounce workflow: {e}")
        return False


async def setup_tracardi():
    """Main setup function for Tracardi configuration."""
    print("=" * 60)
    print("🚀 Tracardi Configuration for Resend Events")
    print("=" * 60)
    print(f"\nTracardi API: {TRACARDI_API_URL}")
    
    async with httpx.AsyncClient() as client:
        # Step 1: Create event source
        print("\n📊 Step 1: Creating event source...")
        await create_event_source(client)
        
        # Step 2: Create event types
        print("\n📊 Step 2: Creating event types...")
        for event_type, config in RESEND_EVENT_TYPES.items():
            await create_event_type(client, event_type, config)
        
        # Step 3: Create workflows
        print("\n📊 Step 3: Creating workflows...")
        await create_engagement_workflow(client)
        await create_bounce_workflow(client)
    
    print("\n" + "=" * 60)
    print("✅ Tracardi Configuration Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Configure Resend webhook to send events to Tracardi")
    print("  2. Send a test email via Resend")
    print("  3. Check Tracardi for incoming events")
    print("  4. Verify profile engagement scores are updated")


if __name__ == "__main__":
    try:
        asyncio.run(setup_tracardi())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
        sys.exit(0)
