#!/usr/bin/env python3
"""
Automated Resend Webhook Setup for CDP_Merged.
Creates webhooks without user interaction - useful for CI/CD and deployment.

Usage:
    python scripts/setup_resend_webhooks_auto.py [--engagement|--full|--delete-all]

Options:
    --engagement    Create engagement tracking webhook only (default)
    --full          Create full tracking webhook with all events
    --delete-all    Delete all existing webhooks first
    --list          Just list existing webhooks
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.resend import ResendClient
from src.core.logger import get_logger

logger = get_logger(__name__)

# Configuration from environment
TRACARDI_IP = os.getenv("TRACARDI_IP", "137.117.212.154")
TRACARDI_TRACKER_URL = os.getenv("TRACARDI_TRACKER_URL", f"http://{TRACARDI_IP}:8686/tracker")
WEBHOOK_ENDPOINT = os.getenv("RESEND_WEBHOOK_URL", TRACARDI_TRACKER_URL)

EMAIL_EVENTS = [
    "email.sent", "email.delivered", "email.delivery_delayed",
    "email.bounced", "email.complained", "email.opened", "email.clicked",
]

ENGAGEMENT_EVENTS = ["email.opened", "email.clicked", "email.bounced", "email.complained"]


async def list_webhooks(client: ResendClient) -> list[dict]:
    """List all webhooks."""
    webhooks = await client.get_webhooks()
    print(f"Found {len(webhooks)} webhook(s):")
    for wh in webhooks:
        print(f"  - {wh.get('name')} ({wh.get('id')})")
        print(f"    URL: {wh.get('url')}")
        print(f"    Events: {len(wh.get('events', []))}")
    return webhooks


async def delete_all_webhooks(client: ResendClient) -> int:
    """Delete all existing webhooks."""
    webhooks = await client.get_webhooks()
    deleted = 0
    for wh in webhooks:
        try:
            await client.delete_webhook(wh["id"])
            print(f"✅ Deleted: {wh.get('name')} ({wh['id'][:8]}...)")
            deleted += 1
        except Exception as e:
            print(f"❌ Failed to delete {wh['id']}: {e}")
    return deleted


async def create_webhook(
    client: ResendClient,
    events: list[str],
    name: str
) -> dict | None:
    """Create a webhook."""
    try:
        result = await client.create_webhook(
            endpoint_url=WEBHOOK_ENDPOINT,
            events=events,
            name=name,
        )
        print(f"✅ Created webhook: {name}")
        print(f"   ID: {result.get('id')}")
        print(f"   Secret: {result.get('token', 'N/A')[:30]}...")
        print(f"\n⚠️  IMPORTANT: Save the webhook secret to your .env file:")
        print(f"   RESEND_WEBHOOK_SECRET={result.get('token')}")
        return result
    except Exception as e:
        print(f"❌ Failed to create webhook: {e}")
        return None


async def main():
    parser = argparse.ArgumentParser(description="Setup Resend webhooks")
    parser.add_argument(
        "--engagement", action="store_true",
        help="Create engagement tracking webhook (opened, clicked, bounced)"
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Create full tracking webhook (all events)"
    )
    parser.add_argument(
        "--delete-all", action="store_true",
        help="Delete all existing webhooks"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Just list existing webhooks"
    )
    args = parser.parse_args()
    
    client = ResendClient()
    
    # Default to engagement if no args
    if not any([args.engagement, args.full, args.delete_all, args.list]):
        args.engagement = True
    
    if args.list:
        await list_webhooks(client)
        return
    
    if args.delete_all:
        count = await delete_all_webhooks(client)
        print(f"\nDeleted {count} webhook(s)")
        return
    
    # Create webhook
    if args.full:
        events = EMAIL_EVENTS
        name = "CDP Full Email Tracking"
    else:
        events = ENGAGEMENT_EVENTS
        name = "CDP Email Engagement Tracking"
    
    print(f"Creating webhook: {name}")
    print(f"Endpoint: {WEBHOOK_ENDPOINT}")
    print(f"Events: {', '.join(events)}\n")
    
    result = await create_webhook(client, events, name)
    
    if result:
        print("\n✅ Webhook setup complete!")
        print("\nNext steps:")
        print("1. Add RESEND_WEBHOOK_SECRET to your .env file")
        print("2. Ensure your webhook endpoint is accessible:", WEBHOOK_ENDPOINT)
        print("3. Send a test email to verify events are received")
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
