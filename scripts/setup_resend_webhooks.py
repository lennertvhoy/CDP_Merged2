#!/usr/bin/env python3
"""
Setup Resend Event Webhooks for CDP_Merged.
Configures webhooks to receive email engagement events from Resend.
"""

import asyncio
import os
import sys
from typing import Any

sys.path.insert(0, "/home/ff/.openclaw/workspace/repos/CDP_Merged")

from src.services.resend import ResendClient
from src.core.logger import get_logger

logger = get_logger(__name__)

# Configuration
TRACARDI_IP = os.getenv("TRACARDI_IP", "137.117.212.154")
TRACARDI_TRACKER_URL = f"http://{TRACARDI_IP}:8686/tracker"

# Webhook events to subscribe to
EMAIL_EVENTS = [
    "email.sent",
    "email.delivered",
    "email.opened",
    "email.clicked",
    "email.bounced",
    "email.complained",
    "email.delivery_delayed",
]

# Key events for engagement tracking
ENGAGEMENT_EVENTS = [
    "email.opened",
    "email.clicked",
    "email.bounced",
]


async def list_existing_webhooks(client: ResendClient) -> list[dict[str, Any]]:
    """List all existing webhooks in Resend."""
    logger.info("listing_existing_webhooks")
    webhooks = await client.get_webhooks()
    
    if not webhooks:
        print("\n📭 No webhooks configured yet.")
    else:
        print(f"\n📋 Found {len(webhooks)} webhook(s):")
        for wh in webhooks:
            print(f"  • {wh.get('name', 'Unnamed')} ({wh.get('id')})")
            print(f"    URL: {wh.get('url')}")
            print(f"    Events: {', '.join(wh.get('events', []))}")
    
    return webhooks


async def create_engagement_webhook(
    client: ResendClient,
    endpoint_url: str = TRACARDI_TRACKER_URL,
    name: str = "CDP Engagement Tracker",
) -> dict[str, Any] | None:
    """Create a webhook for email engagement events."""
    logger.info("creating_engagement_webhook", endpoint=endpoint_url, name=name)
    
    print(f"\n🔧 Creating webhook: {name}")
    print(f"   Endpoint: {endpoint_url}")
    print(f"   Events: {', '.join(ENGAGEMENT_EVENTS)}")
    
    try:
        result = await client.create_webhook(
            endpoint_url=endpoint_url,
            events=ENGAGEMENT_EVENTS,
            name=name,
        )
        
        webhook_id = result.get("id")
        print(f"\n✅ Webhook created successfully!")
        print(f"   ID: {webhook_id}")
        print(f"   Token: {result.get('token', 'N/A')}")
        
        logger.info("engagement_webhook_created", webhook_id=webhook_id)
        return result
        
    except Exception as e:
        logger.error("failed_to_create_webhook", error=str(e))
        print(f"\n❌ Failed to create webhook: {e}")
        return None


async def create_full_tracking_webhook(
    client: ResendClient,
    endpoint_url: str = TRACARDI_TRACKER_URL,
    name: str = "CDP Full Email Tracking",
) -> dict[str, Any] | None:
    """Create a webhook for all email events."""
    logger.info("creating_full_tracking_webhook", endpoint=endpoint_url, name=name)
    
    print(f"\n🔧 Creating webhook: {name}")
    print(f"   Endpoint: {endpoint_url}")
    print(f"   Events: {', '.join(EMAIL_EVENTS)}")
    
    try:
        result = await client.create_webhook(
            endpoint_url=endpoint_url,
            events=EMAIL_EVENTS,
            name=name,
        )
        
        webhook_id = result.get("id")
        print(f"\n✅ Webhook created successfully!")
        print(f"   ID: {webhook_id}")
        
        logger.info("full_tracking_webhook_created", webhook_id=webhook_id)
        return result
        
    except Exception as e:
        logger.error("failed_to_create_full_webhook", error=str(e))
        print(f"\n❌ Failed to create webhook: {e}")
        return None


async def delete_existing_webhook(client: ResendClient, webhook_id: str) -> bool:
    """Delete an existing webhook."""
    logger.info("deleting_webhook", webhook_id=webhook_id)
    
    print(f"\n🗑️  Deleting webhook: {webhook_id}")
    
    try:
        await client.delete_webhook(webhook_id)
        print(f"✅ Webhook {webhook_id} deleted successfully!")
        logger.info("webhook_deleted", webhook_id=webhook_id)
        return True
        
    except Exception as e:
        logger.error("failed_to_delete_webhook", webhook_id=webhook_id, error=str(e))
        print(f"❌ Failed to delete webhook: {e}")
        return False


async def setup_webhooks():
    """Main setup function for Resend webhooks."""
    print("=" * 60)
    print("🚀 Resend Webhook Configuration")
    print("=" * 60)
    
    client = ResendClient()
    
    # Step 1: List existing webhooks
    print("\n📊 Step 1: Checking existing webhooks...")
    existing = await list_existing_webhooks(client)
    
    # Step 2: Ask user what to do
    print("\n" + "-" * 60)
    print("Options:")
    print("  1. Create engagement tracking webhook (opened, clicked, bounced)")
    print("  2. Create full email tracking webhook (all events)")
    print("  3. Delete existing webhook")
    print("  4. Exit without changes")
    print("-" * 60)
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        # Create engagement webhook
        result = await create_engagement_webhook(client)
        
        if result:
            print("\n" + "=" * 60)
            print("✅ Configuration Complete!")
            print("=" * 60)
            print("\nNext steps:")
            print("  1. Configure Tracardi to process incoming events")
            print("  2. Create workflow for engagement scoring")
            print("  3. Send test email and verify events are received")
            
    elif choice == "2":
        # Create full tracking webhook
        result = await create_full_tracking_webhook(client)
        
        if result:
            print("\n" + "=" * 60)
            print("✅ Configuration Complete!")
            print("=" * 60)
            print("\nNext steps:")
            print("  1. Configure Tracardi to process incoming events")
            print("  2. Create workflow for engagement scoring")
            print("  3. Send test email and verify events are received")
            
    elif choice == "3":
        # Delete webhook
        if not existing:
            print("\n❌ No webhooks to delete.")
            return
            
        print("\nSelect webhook to delete:")
        for i, wh in enumerate(existing, 1):
            print(f"  {i}. {wh.get('name', 'Unnamed')} ({wh.get('id')[:8]}...)")
        
        idx = input("\nEnter number: ").strip()
        try:
            webhook_id = existing[int(idx) - 1]["id"]
            await delete_existing_webhook(client, webhook_id)
        except (ValueError, IndexError):
            print("\n❌ Invalid selection.")
            
    elif choice == "4":
        print("\n👋 Exiting without changes.")
        
    else:
        print("\n❌ Invalid choice. Exiting.")


if __name__ == "__main__":
    try:
        asyncio.run(setup_webhooks())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
        sys.exit(0)
