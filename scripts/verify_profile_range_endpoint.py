#!/usr/bin/env python3
"""
Verify that Tracardi profile range endpoint works correctly.

The /profile/select/range endpoint requires a specific payload format with
minDate and maxDate objects containing absolute datetime components.
"""

import json
import os
import sys
import urllib.request
import urllib.error
import ssl
from datetime import datetime


def get_token(base_url: str, username: str, password: str) -> str:
    """Authenticate with Tracardi and return access token."""
    data = urllib.parse.urlencode({
        "username": username,
        "password": password,
        "grant_type": "password"
    }).encode()
    
    req = urllib.request.Request(
        f"{base_url}/user/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        return result["access_token"]


def api_call(base_url: str, token: str, path: str, payload=None, method="GET"):
    """Make an authenticated API call to Tracardi."""
    url = f"{base_url}{path}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    if payload and method == "GET":
        method = "POST"
    
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return {"status": resp.status, "body": json.loads(resp.read().decode())}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode()}


def build_datetime_payload(dt: datetime):
    """Build Tracardi DatetimePayload structure."""
    return {
        "year": dt.year,
        "month": dt.month,
        "date": dt.day,
        "hour": dt.hour if dt.hour <= 12 else dt.hour - 12,
        "minute": dt.minute,
        "second": dt.second,
        "meridiem": "AM" if dt.hour < 12 else "PM",
        "timeZone": 0
    }


def verify_range_endpoint(base_url: str, username: str, password: str) -> bool:
    """Verify the profile range endpoint works correctly."""
    print(f"Connecting to Tracardi at {base_url}...")
    
    try:
        token = get_token(base_url, username, password)
        print("✓ Authentication successful")
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        return False
    
    # Test basic select endpoint
    print("\nTesting /profile/select...")
    result = api_call(base_url, token, "/profile/select", {"where": "*", "limit": 1})
    if result["status"] != 200:
        print(f"✗ /profile/select failed: {result['body']}")
        return False
    
    select_total = result["body"].get("total", 0)
    print(f"✓ /profile/select returned {select_total} profiles")
    
    # Test range endpoint with proper payload format
    print("\nTesting /profile/select/range/page/0...")
    
    # Use a wide date range to capture all profiles
    start_dt = datetime(2020, 1, 1, 0, 0, 0)
    end_dt = datetime(2030, 12, 31, 23, 59, 59)
    
    range_payload = {
        "where": "",
        "limit": 25,
        "start": 0,
        "minDate": {
            "absolute": build_datetime_payload(start_dt)
        },
        "maxDate": {
            "absolute": build_datetime_payload(end_dt)
        }
    }
    
    result = api_call(base_url, token, "/profile/select/range/page/0", range_payload)
    if result["status"] != 200:
        print(f"✗ /profile/select/range/page/0 failed: {result['body']}")
        return False
    
    range_total = result["body"].get("total", 0)
    result_count = len(result["body"].get("result", []))
    print(f"✓ /profile/select/range/page/0 returned {range_total} profiles (showing {result_count})")
    
    # Verify totals match
    if select_total == range_total:
        print(f"\n✓ SUCCESS: Both endpoints return {select_total} profiles")
        return True
    else:
        print(f"\n✗ MISMATCH: /profile/select returned {select_total}, "
              f"but /profile/select/range returned {range_total}")
        return False


def main():
    """Main entry point."""
    base_url = os.environ.get("TRACARDI_URL", "http://137.117.212.154:8686")
    username = os.environ.get("TRACARDI_USERNAME", "admin@admin.com")
    password = os.environ.get("TRACARDI_PASSWORD")
    
    if not password:
        print("Error: TRACARDI_PASSWORD environment variable is required")
        print("\nUsage:")
        print("  export TRACARDI_PASSWORD='your-password'")
        print("  python scripts/verify_profile_range_endpoint.py")
        sys.exit(1)
    
    success = verify_range_endpoint(base_url, username, password)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
