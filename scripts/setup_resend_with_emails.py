#!/usr/bin/env python3
"""
Set up Resend audience with companies that have email addresses
- Extracts emails from KBO contact.csv
- Matches with Tracardi profiles
- Creates Resend audience with valid contacts
"""
import asyncio
import csv
import io
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

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
    raise RuntimeError("TRACARDI_PASSWORD must be set before running setup_resend_with_emails.py")
KBO_ZIP_PATH = Path("/home/ff/.openclaw/workspace/repos/CDP_Merged/KboOpenData_0285_2026_02_27_Full.zip")


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


def extract_emails_from_kbo(zip_path, max_emails=100):
    """Extract email addresses from KBO contact.csv."""
    print(f"📦 Extracting emails from {zip_path}...")
    
    emails = {}  # kbo -> email
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        with zf.open('contact.csv') as f:
            reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
            for row in reader:
                if row['ContactType'] == 'EMAIL':
                    kbo = row['EntityNumber'].replace('.', '')
                    email = row['Value']
                    if email and '@' in email:
                        emails[kbo] = email
                        if len(emails) >= max_emails:
                            break
    
    print(f"✅ Extracted {len(emails)} email addresses")
    return emails


def extract_company_names_from_kbo(zip_path, kbo_numbers):
    """Extract company names for given KBO numbers."""
    print(f"📦 Extracting company names...")
    
    names = {}
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        with zf.open('denomination.csv') as f:
            reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
            for row in reader:
                kbo = row['EntityNumber'].replace('.', '')
                if kbo in kbo_numbers and kbo not in names:
                    name = row.get('Denomination', '')
                    if name:
                        names[kbo] = name
    
    print(f"✅ Found {len(names)} company names")
    return names


async def check_profile_in_tracardi(token, kbo):
    """Check if a KBO number exists in Tracardi."""
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.get(
            f"{TRACARDI_API_URL}/profile/{kbo}",
            headers=headers
        )
        
        return response.status_code == 200


async def create_resend_audience(resend: ResendClient, name: str):
    """Create a new audience in Resend."""
    try:
        audience = await resend.create_audience(name=name)
        logger.info(f"Created Resend audience: {name} (ID: {audience.get('id')})")
        return audience
    except Exception as e:
        logger.error(f"Failed to create audience: {e}")
        return None


async def add_contact_to_resend_audience(resend: ResendClient, audience_id: str, contact_email: str, first_name: str = "", last_name: str = ""):
    """Add a contact to Resend audience."""
    try:
        # Method signature: add_contact_to_audience(email, audience_id, ...)
        await resend.add_contact_to_audience(
            email=contact_email,
            audience_id=audience_id,
            first_name=first_name,
            last_name=last_name,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to add contact {contact_email}: {e}")
        return False


async def main():
    print("=" * 70)
    print("Resend Audience Setup - With Email Extraction from KBO")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    # Initialize Resend client
    print("🔌 Initializing Resend client...")
    resend = ResendClient()
    print(f"✅ Resend client ready")
    
    # Get existing audiences
    print("\n📋 Checking existing audiences...")
    audiences = await resend.get_audiences()
    print(f"   Found {len(audiences)} audiences")
    
    # Extract emails from KBO
    kbo_emails = extract_emails_from_kbo(KBO_ZIP_PATH, max_emails=100)
    
    if not kbo_emails:
        print("❌ No emails found in KBO data")
        return 1
    
    # Get company names
    kbo_names = extract_company_names_from_kbo(KBO_ZIP_PATH, set(kbo_emails.keys()))
    
    # Authenticate with Tracardi
    print("\n🔐 Authenticating with Tracardi...")
    token = await get_tracardi_token()
    print("✅ Tracardi authenticated")
    
    # Check which KBOs exist in Tracardi
    print("\n🔍 Checking which companies exist in Tracardi...")
    matched_contacts = []
    
    for kbo, email in list(kbo_emails.items())[:50]:  # Check first 50
        exists = await check_profile_in_tracardi(token, kbo)
        if exists:
            name = kbo_names.get(kbo, "")
            matched_contacts.append({
                'kbo': kbo,
                'email': email,
                'company_name': name
            })
            print(f"   ✅ {name[:40]} - {email}")
    
    print(f"\n📊 Found {len(matched_contacts)} companies with emails in Tracardi")
    
    if not matched_contacts:
        print("❌ No matching companies found")
        print("   Creating audience with available emails anyway...")
        # Use first 10 emails even if not in Tracardi
        for kbo, email in list(kbo_emails.items())[:10]:
            name = kbo_names.get(kbo, "")
            matched_contacts.append({
                'kbo': kbo,
                'email': email,
                'company_name': name
            })
    
    # Create Resend audience
    audience_name = "KBO Companies - Test Audience"
    print(f"\n🎯 Creating Resend audience: '{audience_name}'...")
    audience = await create_resend_audience(resend, audience_name)
    
    if not audience:
        print("❌ Failed to create audience")
        return 1
    
    audience_id = audience.get("id")
    print(f"✅ Audience created with ID: {audience_id}")
    
    # Add contacts to audience
    print(f"\n📤 Adding {len(matched_contacts)} contacts to audience...")
    added = 0
    failed = 0
    
    for contact in matched_contacts:
        success = await add_contact_to_resend_audience(
            resend, 
            audience_id, 
            contact['email'],
            first_name=contact['company_name'][:20]  # Use company name as first name
        )
        if success:
            added += 1
        else:
            failed += 1
    
    # Summary
    print("\n" + "=" * 70)
    print("SETUP COMPLETE")
    print("=" * 70)
    print(f"Audience: {audience_name}")
    print(f"Audience ID: {audience_id}")
    print(f"Total emails extracted: {len(kbo_emails)}")
    print(f"Matched with Tracardi: {len(matched_contacts)}")
    print(f"Contacts added to Resend: {added}")
    print(f"Failed: {failed}")
    
    if added > 0:
        print(f"\n✅ SUCCESS: Audience ready for email campaigns!")
        print(f"\nNext steps:")
        print(f"   1. Verify domain in Resend dashboard")
        print(f"   2. Send test campaign to this audience")
        print(f"   3. Configure webhooks for engagement tracking")
        return 0
    else:
        print(f"\n⚠️ WARNING: No contacts were added")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
