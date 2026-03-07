#!/usr/bin/env python3
"""
Setup Resend Event Webhooks for CDP_Merged.
Configures webhooks to receive email engagement events from Resend.

Usage:
    python scripts/setup_resend_webhooks.py

Environment Variables:
    RESEND_API_KEY - Your Resend API key
    RESEND_WEBHOOK_URL - URL endpoint for receiving webhooks (default: Tracardi tracker)
    TRACARDI_TRACKER_URL - Tracardi tracker URL for event forwarding
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.resend import ResendClient
from src.core.logger import get_logger

logger = get_logger(__name__)

# Configuration
TRACARDI_IP = os.getenv("TRACARDI_IP", "137.117.212.154")
TRACARDI_TRACKER_URL = os.getenv("TRACARDI_TRACKER_URL", f"http://{TRACARDI_IP}:8686/tracker")
WEBHOOK_ENDPOINT = os.getenv("RESEND_WEBHOOK_URL", TRACARDI_TRACKER_URL)

# All webhook events to subscribe to
EMAIL_EVENTS = [
    "email.sent",
    "email.delivered", 
    "email.delivery_delayed",
    "email.bounced",
    "email.complained",
    "email.opened",
    "email.clicked",
]

# Key events for engagement tracking
ENGAGEMENT_EVENTS = [
    "email.opened",
    "email.clicked", 
    "email.bounced",
    "email.complained",
]


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_section(title: str) -> None:
    """Print a section divider."""
    print(f"\n📋 {title}")
    print("-" * 40)


async def list_existing_webhooks(client: ResendClient) -> list[dict]:
    """List all existing webhooks in Resend."""
    print_section("Checking Existing Webhooks")
    
    try:
        webhooks = await client.get_webhooks()
        
        if not webhooks:
            print("  📭 No webhooks configured yet.")
        else:
            print(f"  Found {len(webhooks)} webhook(s):\n")
            for i, wh in enumerate(webhooks, 1):
                print(f"  {i}. {wh.get('name', 'Unnamed')}")
                print(f"     ID: {wh.get('id')}")
                print(f"     URL: {wh.get('url')}")
                events = wh.get('events', [])
                print(f"     Events: {', '.join(events[:3])}", end="")
                if len(events) > 3:
                    print(f" (+{len(events) - 3} more)")
                else:
                    print()
                print()
        
        return webhooks
        
    except Exception as e:
        logger.error("failed_to_list_webhooks", error=str(e))
        print(f"  ❌ Error listing webhooks: {e}")
        return []


async def create_webhook(
    client: ResendClient,
    endpoint_url: str,
    events: list[str],
    name: str,
) -> dict | None:
    """Create a webhook in Resend."""
    print(f"\n🔧 Creating webhook: {name}")
    print(f"   Endpoint: {endpoint_url}")
    print(f"   Events: {', '.join(events)}")
    
    try:
        result = await client.create_webhook(
            endpoint_url=endpoint_url,
            events=events,
            name=name,
        )
        
        webhook_id = result.get("id")
        token = result.get("token", "N/A")
        
        print(f"\n✅ Webhook created successfully!")
        print(f"   ID: {webhook_id}")
        print(f"   Secret Token: {token[:20]}..." if len(token) > 20 else f"   Secret Token: {token}")
        
        logger.info("webhook_created", webhook_id=webhook_id, name=name)
        
        # Print configuration instructions
        print(f"\n📝 Configuration Instructions:")
        print(f"   Add this to your .env file:")
        print(f"   RESEND_WEBHOOK_SECRET={token}")
        print(f"   RESEND_WEBHOOK_URL={endpoint_url}")
        
        return result
        
    except Exception as e:
        logger.error("failed_to_create_webhook", error=str(e))
        print(f"\n❌ Failed to create webhook: {e}")
        return None


async def delete_webhook(client: ResendClient, webhook_id: str) -> bool:
    """Delete an existing webhook."""
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


async def setup_engagement_webhook(client: ResendClient) -> dict | None:
    """Setup webhook for engagement tracking (opened, clicked, bounced)."""
    return await create_webhook(
        client=client,
        endpoint_url=WEBHOOK_ENDPOINT,
        events=ENGAGEMENT_EVENTS,
        name="CDP Email Engagement Tracking",
    )


async def setup_full_tracking_webhook(client: ResendClient) -> dict | None:
    """Setup webhook for full email tracking (all events)."""
    return await create_webhook(
        client=client,
        endpoint_url=WEBHOOK_ENDPOINT,
        events=EMAIL_EVENTS,
        name="CDP Full Email Tracking",
    )


async def test_webhook(client: ResendClient) -> None:
    """Test the webhook configuration by sending a test email."""
    print_section("Testing Webhook Configuration")
    
    test_email = input("Enter email address for test (or press Enter to skip): ").strip()
    
    if not test_email:
        print("  ⏭️  Skipping test.")
        return
    
    print(f"\n📧 Sending test email to: {test_email}")
    
    try:
        result = await client.send_email(
            to=test_email,
            subject="🧪 Resend Webhook Test",
            html="""
            <html>
                <body>
                    <h1>🧪 Test Email</h1>
                    <p>This is a test email to verify webhook configuration.</p>
                    <p><a href="https://resend.com">Click here to test click tracking</a></p>
                    <p>Open and click this email to see events in your CDP!</p>
                </body>
            </html>
            """,
        )
        
        print(f"✅ Test email sent!")
        print(f"   Email ID: {result.get('id')}")
        print(f"\n📋 Next steps:")
        print(f"   1. Check your inbox ({test_email})")
        print(f"   2. Open the email (should trigger 'email.opened' event)")
        print(f"   3. Click the link (should trigger 'email.clicked' event)")
        print(f"   4. Check Tracardi dashboard for incoming events")
        
    except Exception as e:
        print(f"❌ Failed to send test email: {e}")


async def main():
    """Main setup function for Resend webhooks."""
    print_header("🚀 Resend Webhook Configuration")
    
    # Check configuration
    print("\n📊 Current Configuration:")
    print(f"   Webhook Endpoint: {WEBHOOK_ENDPOINT}")
    print(f"   Tracardi Tracker: {TRACARDI_TRACKER_URL}")
    
    client = ResendClient()
    
    # Step 1: List existing webhooks
    existing = await list_existing_webhooks(client)
    
    # Step 2: Show options
    print("\n" + "=" * 60)
    print("Options:")
    print("  1. Create engagement tracking webhook (opened, clicked, bounced)")
    print("  2. Create full email tracking webhook (all events)")
    print("  3. Delete existing webhook")
    print("  4. Test webhook with test email")
    print("  5. Exit without changes")
    print("=" * 60)
    
    choice = input("\nEnter choice (1-5): ").strip()
    
    if choice == "1":
        result = await setup_engagement_webhook(client)
        if result:
            await test_webhook(client)
            
    elif choice == "2":
        result = await setup_full_tracking_webhook(client)
        if result:
            await test_webhook(client)
            
    elif choice == "3":
        if not existing:
            print("\n❌ No webhooks to delete.")
            return
            
        print("\nSelect webhook to delete:")
        for i, wh in enumerate(existing, 1):
            print(f"  {i}. {wh.get('name', 'Unnamed')} ({wh.get('id')[:8]}...)")
        
        idx = input("\nEnter number: ").strip()
        try:
            webhook_id = existing[int(idx) - 1]["id"]
            await delete_webhook(client, webhook_id)
        except (ValueError, IndexError):
            print("\n❌ Invalid selection.")
            
    elif choice == "4":
        await test_webhook(client)
            
    elif choice == "5":
        print("\n👋 Exiting without changes.")
        
    else:
        print("\n❌ Invalid choice. Exiting.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.error("setup_failed", error=str(e))
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
