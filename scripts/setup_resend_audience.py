#!/usr/bin/env python3
"""
Set up Resend audience from Tracardi profiles
- Creates audience for IT companies in East Flanders
- Syncs contacts from Tracardi to Resend
"""
import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, '/home/ff/.openclaw/workspace/repos/CDP_Merged')

import httpx
from src.services.resend import ResendClient
from src.core.logger import get_logger

logger = get_logger(__name__)

# Configuration
TRACARDI_API_URL = os.getenv("TRACARDI_API_URL", "http://137.117.212.154:8686")
TRACARDI_USERNAME = os.getenv("TRACARDI_USERNAME", "admin@cdpmerged.local")
TRACARDI_PASSWORD = os.getenv("TRACARDI_PASSWORD")
if not TRACARDI_PASSWORD:
    raise RuntimeError("TRACARDI_PASSWORD must be set before running setup_resend_audience.py")


async def get_tracardi_token():
    """Get authentication token from Tracardi."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TRACARDI_API_URL}/user/token",
            data={
                "username": TRACARDI_USERNAME,
                "password": TRACARDI_PASSWORD,
                "grant_type": "password"
            }
        )
        response.raise_for_status()
        return response.json()["access_token"]


async def get_profiles_from_tracardi(token, limit=100):
    """Get profiles from Tracardi."""
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        # Search for profiles with email
        response = await client.post(
            f"{TRACARDI_API_URL}/profiles/search",
            json={
                "limit": limit,
                "where": "traits.main_email EXISTS"
            },
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("result", [])
        else:
            logger.error(f"Failed to get profiles: {response.status_code}")
            return []


async def get_it_companies_from_tracardi(token, limit=50):
    """Get IT companies from Tracardi (based on NACE codes)."""
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        # Search for profiles with IT NACE codes
        # NACE codes: 62, 63, 58.2, 61
        response = await client.post(
            f"{TRACARDI_API_URL}/profiles/search",
            json={
                "limit": limit,
                "where": "traits.is_it_company = true"
            },
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("result", [])
        else:
            # Try without filter
            response = await client.post(
                f"{TRACARDI_API_URL}/profiles/search",
                json={"limit": limit},
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                profiles = data.get("result", [])
                # Filter IT companies locally
                it_profiles = []
                for p in profiles:
                    nace = p.get("traits", {}).get("nace_code", "")
                    if nace and (nace.startswith("62") or nace.startswith("63") or 
                                nace.startswith("58.2") or nace.startswith("61")):
                        it_profiles.append(p)
                return it_profiles
            return []


async def create_resend_audience(resend: ResendClient, name: str):
    """Create a new audience in Resend."""
    try:
        audience = await resend.create_audience(name=name)
        logger.info(f"Created Resend audience: {name} (ID: {audience.get('id')})")
        return audience
    except Exception as e:
        logger.error(f"Failed to create audience: {e}")
        return None


async def add_profiles_to_resend_audience(resend: ResendClient, audience_id: str, profiles):
    """Add Tracardi profiles to Resend audience."""
    added = 0
    failed = 0
    
    for profile in profiles:
        traits = profile.get("traits", {})
        email = traits.get("main_email")
        
        if not email:
            continue
        
        first_name = ""
        last_name = ""
        company = traits.get("company_name", "")
        
        # Try to parse name from company or other fields
        contact_data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "unsubscribed": False,
        }
        
        try:
            await resend.add_contact_to_audience(audience_id, **contact_data)
            added += 1
            logger.info(f"Added contact: {email}")
        except Exception as e:
            failed += 1
            logger.error(f"Failed to add contact {email}: {e}")
    
    return added, failed


async def main():
    print("=" * 70)
    print("Resend Audience Setup - IT Companies East Flanders")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    # Initialize Resend client
    print("🔌 Initializing Resend client...")
    resend = ResendClient()
    print(f"✅ Resend client ready (API key: {resend.api_key[:8]}...)")
    
    # Get existing audiences
    print("\n📋 Checking existing audiences...")
    audiences = await resend.get_audiences()
    print(f"   Found {len(audiences)} audiences:")
    for a in audiences:
        print(f"     - {a.get('name')} (ID: {a.get('id')})")
    
    # Get Tracardi token
    print("\n🔐 Authenticating with Tracardi...")
    token = await get_tracardi_token()
    print("✅ Tracardi authenticated")
    
    # Get IT profiles from Tracardi
    print("\n🔍 Fetching IT companies from Tracardi...")
    it_profiles = await get_it_companies_from_tracardi(token, limit=100)
    print(f"✅ Found {len(it_profiles)} IT companies")
    
    if not it_profiles:
        print("❌ No IT companies found in Tracardi")
        print("   Try running: poetry run python scripts/sync_kbo_to_tracardi.py")
        return 1
    
    # Show sample profiles
    print("\n📋 Sample profiles:")
    for i, p in enumerate(it_profiles[:5]):
        traits = p.get("traits", {})
        print(f"   {i+1}. {traits.get('company_name')} - {traits.get('city')}")
        print(f"      NACE: {traits.get('nace_code')} - IT: {traits.get('is_it_company')}")
    
    # Create audience
    audience_name = "IT Companies - East Flanders"
    print(f"\n🎯 Creating Resend audience: '{audience_name}'...")
    audience = await create_resend_audience(resend, audience_name)
    
    if not audience:
        print("❌ Failed to create audience")
        return 1
    
    audience_id = audience.get("id")
    print(f"✅ Audience created with ID: {audience_id}")
    
    # Add contacts to audience
    print(f"\n📤 Adding {len(it_profiles)} contacts to audience...")
    added, failed = await add_profiles_to_resend_audience(resend, audience_id, it_profiles)
    
    # Summary
    print("\n" + "=" * 70)
    print("SETUP COMPLETE")
    print("=" * 70)
    print(f"Audience: {audience_name}")
    print(f"Audience ID: {audience_id}")
    print(f"Profiles in Tracardi: {len(it_profiles)}")
    print(f"Contacts added to Resend: {added}")
    print(f"Failed: {failed}")
    
    if added > 0:
        print(f"\n✅ SUCCESS: Audience ready for email campaigns!")
        print(f"\nNext steps:")
        print(f"   1. Verify domain in Resend dashboard")
        print(f"   2. Create email campaign")
        print(f"   3. Configure webhooks for engagement tracking")
        return 0
    else:
        print(f"\n⚠️ WARNING: No contacts were added")
        print(f"   Check if profiles have email addresses")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
