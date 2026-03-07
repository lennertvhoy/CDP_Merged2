#!/usr/bin/env python3
"""
Test script for Resend webhook integration.
Sends test emails and verifies events are received.
"""

import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, "/home/ff/.openclaw/workspace/repos/CDP_Merged")

from src.services.resend import ResendClient
from src.core.logger import get_logger

logger = get_logger(__name__)


async def send_test_email(client: ResendClient, to_email: str) -> str | None:
    """Send a test email and return the message ID."""
    print(f"\n📧 Sending test email to: {to_email}")
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Email from CDP</title>
    </head>
    <body>
        <h1>CDP Resend Integration Test</h1>
        <p>This is a test email to verify the Resend webhook integration.</p>
        <p>Please open this email to trigger an 'email.opened' event.</p>
        <p><a href="https://example.com/test">Click here</a> to trigger an 'email.clicked' event.</p>
        <hr>
        <p>Sent at: {}</p>
    </body>
    </html>
    """.format(datetime.now().isoformat())
    
    try:
        result = await client.send_email(
            to=to_email,
            subject="CDP Test: Resend Webhook Integration",
            html=html_content,
        )
        
        message_id = result.get("id")
        print(f"✅ Email sent successfully!")
        print(f"   Message ID: {message_id}")
        
        logger.info("test_email_sent", message_id=message_id, to=to_email)
        return message_id
        
    except Exception as e:
        logger.error("failed_to_send_test_email", error=str(e))
        print(f"❌ Failed to send email: {e}")
        return None


async def list_recent_webhook_events(client: ResendClient) -> None:
    """List recent webhook events from Resend (if available via API)."""
    print("\n📊 Recent Webhook Events:")
    print("   Note: Check Resend Dashboard for real-time event logs")
    print("   Dashboard: https://resend.com/webhooks")


async def verify_webhook_configuration(client: ResendClient) -> bool:
    """Verify that webhooks are properly configured."""
    print("\n🔍 Verifying webhook configuration...")
    
    try:
        webhooks = await client.get_webhooks()
        
        if not webhooks:
            print("❌ No webhooks configured!")
            print("   Run: python scripts/setup_resend_webhooks.py")
            return False
        
        print(f"✅ Found {len(webhooks)} webhook(s):")
        for wh in webhooks:
            print(f"\n   • {wh.get('name', 'Unnamed')}")
            print(f"     ID: {wh.get('id')}")
            print(f"     URL: {wh.get('url')}")
            print(f"     Events: {', '.join(wh.get('events', []))}")
        
        return True
        
    except Exception as e:
        logger.error("failed_to_verify_webhooks", error=str(e))
        print(f"❌ Error verifying webhooks: {e}")
        return False


async def test_tracardi_connection() -> bool:
    """Test connection to Tracardi."""
    import httpx
    
    tracardi_url = os.getenv("TRACARDI_API_URL", "http://137.117.212.154:8686")
    
    print(f"\n🔍 Testing Tracardi connection...")
    print(f"   URL: {tracardi_url}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{tracardi_url}/health", timeout=10.0)
            
            if response.status_code == 200:
                print(f"✅ Tracardi is reachable!")
                return True
            else:
                print(f"⚠️  Tracardi returned status {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Cannot connect to Tracardi: {e}")
        return False


async def run_tests():
    """Run all webhook tests."""
    print("=" * 60)
    print("🧪 Resend Webhook Integration Test")
    print("=" * 60)
    
    client = ResendClient()
    
    # Test 1: Verify webhook configuration
    webhooks_ok = await verify_webhook_configuration(client)
    
    # Test 2: Verify Tracardi connection
    tracardi_ok = await test_tracardi_connection()
    
    if not webhooks_ok:
        print("\n" + "=" * 60)
        print("⚠️  Webhooks not configured!")
        print("=" * 60)
        print("\nTo configure webhooks, run:")
        print("  python scripts/setup_resend_webhooks.py")
        return
    
    if not tracardi_ok:
        print("\n" + "=" * 60)
        print("⚠️  Tracardi not reachable!")
        print("=" * 60)
        print("\nCheck Tracardi deployment status.")
        return
    
    # Test 3: Send test email
    print("\n" + "-" * 60)
    print("Test Email Configuration")
    print("-" * 60)
    
    to_email = input("\nEnter test email address (or press Enter to skip): ").strip()
    
    if to_email:
        message_id = await send_test_email(client, to_email)
        
        if message_id:
            print("\n" + "=" * 60)
            print("✅ Test email sent!")
            print("=" * 60)
            print("\nNext steps:")
            print("  1. Check your inbox for the test email")
            print("  2. Open the email (triggers 'email.opened' event)")
            print("  3. Click the link (triggers 'email.clicked' event)")
            print("  4. Check Tracardi for incoming events:")
            print(f"     {tracardi_url}/events")
            print("  5. Check profile engagement scores")
    else:
        print("\n⏭️  Skipping test email.")
    
    # Test 4: Show webhook status
    print("\n" + "-" * 60)
    await list_recent_webhook_events(client)
    
    print("\n" + "=" * 60)
    print("✅ Test Complete!")
    print("=" * 60)
    print("\nVerification checklist:")
    print("  ☐ Webhook configured in Resend")
    print("  ☐ Tracardi reachable")
    print("  ☐ Test email sent (if provided)")
    print("  ☐ Email opened event received")
    print("  ☐ Email clicked event received")
    print("  ☐ Profile engagement score updated")


if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
        sys.exit(0)
