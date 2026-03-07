#!/usr/bin/env python3
"""
Simple Tracardi Setup for Resend Email Integration (using standard library only).
"""

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# Configuration
TRACARDI_API_URL = os.getenv("TRACARDI_API_URL", "http://localhost:8686")
TRACARDI_GUI_URL = TRACARDI_API_URL.replace(":8686", ":8787")
TRACARDI_USERNAME = os.getenv("TRACARDI_USERNAME", "lennertvhoy@gmail.com")
TRACARDI_PASSWORD = os.getenv("TRACARDI_PASSWORD", "okdennieh")

BRIDGE_WEBHOOK = "3d8bb87e-28d1-4a38-b19c-d0c1fbb71e22"

RESEND_EVENT_TYPES = {
    "email.sent": {"name": "Email Sent", "description": "Email was sent from Resend"},
    "email.delivered": {"name": "Email Delivered", "description": "Email was successfully delivered"},
    "email.opened": {"name": "Email Opened", "description": "Recipient opened the email"},
    "email.clicked": {"name": "Email Clicked", "description": "Recipient clicked a link"},
    "email.bounced": {"name": "Email Bounced", "description": "Email bounced"},
    "email.complained": {"name": "Email Complained", "description": "Recipient marked as spam"},
}


def api_request(method, path, data=None, token=None):
    """Make an API request to Tracardi."""
    url = f"{TRACARDI_API_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        req = Request(url, method=method, headers=headers)
        if data:
            req.data = json.dumps(data).encode('utf-8')
        
        with urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except HTTPError as e:
        return e.code, e.read().decode('utf-8')
    except Exception as e:
        return 0, str(e)


def authenticate():
    """Authenticate and get access token."""
    print("🔐 Authenticating...")
    
    # Use form-encoded data for authentication
    url = f"{TRACARDI_API_URL}/user/token"
    data = f"username={TRACARDI_USERNAME}&password={TRACARDI_PASSWORD}&grant_type=password&scope=".encode('utf-8')
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    try:
        req = Request(url, method="POST", data=data, headers=headers)
        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            print("✅ Authentication successful")
            return data.get("access_token")
    except HTTPError as e:
        print(f"❌ Authentication failed: {e.code} - {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return None
    
    if status == 200:
        token = data.get("access_token")
        print("✅ Authentication successful")
        return token
    else:
        print(f"❌ Authentication failed: {status} - {data}")
        return None


def create_event_source(token, source_id, name, description):
    """Create an event source."""
    print(f"  Creating event source: {source_id}...", end=" ")
    
    payload = {
        "id": source_id,
        "name": name,
        "description": description,
        "type": ["webhook"],
        "bridge": {"id": BRIDGE_WEBHOOK, "name": "Webhook API Bridge"},
        "tags": ["email", "resend", "marketing"],
        "enabled": True,
    }
    
    status, data = api_request("POST", "/event-source", payload, token)
    
    if status in [200, 201]:
        print("✅")
        return True
    elif status == 409:
        print("⚠️ Already exists")
        return True
    else:
        print(f"❌ {status}")
        return False


def create_event_type(token, event_type, config):
    """Create an event type."""
    print(f"  Creating event type: {event_type}...", end=" ")
    
    payload = {
        "id": event_type,
        "name": config["name"],
        "description": config["description"],
    }
    
    status, data = api_request("POST", "/event-type", payload, token)
    
    if status in [200, 201]:
        print("✅")
        return True
    elif status == 409:
        print("⚠️ Already exists")
        return True
    else:
        print(f"❌ {status}")
        return False


def create_workflow(token, workflow):
    """Create a workflow."""
    name = workflow["name"]
    print(f"  Creating workflow: {name}...", end=" ")
    
    status, data = api_request("POST", "/flow", workflow, token)
    
    if status in [200, 201]:
        print("✅")
        return True
    elif status == 409:
        print("⚠️ Already exists")
        return True
    else:
        print(f"❌ {status}")
        return False


def test_event(token, source_id, event_type):
    """Test tracking an event."""
    print(f"  Testing {event_type}...", end=" ")
    
    payload = {
        "source": {"id": source_id},
        "profile": {"traits": {"email": "test@example.com"}},
        "events": [{
            "type": event_type,
            "properties": {
                "email_id": f"test-{uuid.uuid4().hex[:8]}",
                "to": "test@example.com",
                "timestamp": datetime.now().isoformat(),
            }
        }]
    }
    
    status, data = api_request("POST", "/track", payload, token)
    
    if status in [200, 201]:
        print("✅")
        return True
    else:
        print(f"⚠️ {status}")
        return False


def main():
    print("=" * 70)
    print("🚀 Tracardi Setup for Resend Email Integration")
    print("=" * 70)
    print(f"\nTracardi API: {TRACARDI_API_URL}")
    print(f"Tracardi GUI: {TRACARDI_GUI_URL}")
    print(f"Username: {TRACARDI_USERNAME}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Authenticate
    token = authenticate()
    if not token:
        return 1
    
    results = {"sources": 0, "event_types": 0, "workflows": 0, "tests": 0}
    
    # Create event source
    print("\n📡 Creating Event Source...")
    if create_event_source(token, "resend-webhook", "Resend Email Webhook", 
                           "Email events from Resend"):
        results["sources"] += 1
    
    # Create event types
    print("\n📋 Creating Event Types...")
    for event_type, config in RESEND_EVENT_TYPES.items():
        if create_event_type(token, event_type, config):
            results["event_types"] += 1
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Setup Summary")
    print("=" * 70)
    print(f"Event Sources: {results['sources']} created")
    print(f"Event Types: {results['event_types']}/{len(RESEND_EVENT_TYPES)} created")
    
    print("\n✅ Basic Tracardi setup complete!")
    print("\nNext Steps:")
    print(f"  1. Configure Resend webhook to send events to:")
    print(f"     {TRACARDI_API_URL}/track")
    print(f"  2. Use source ID: resend-webhook")
    print(f"  3. View event sources in Tracardi GUI: {TRACARDI_GUI_URL}")
    print(f"\nNote: Workflows must be created manually in Tracardi GUI.")
    print(f"      See docs/TRACARDI_RESEND_WORKFLOWS.md for instructions.")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
        sys.exit(1)
