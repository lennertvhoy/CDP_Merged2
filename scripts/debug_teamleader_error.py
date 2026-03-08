#!/usr/bin/env python3
"""Debug script to see actual error from Teamleader API."""

import sys
import random
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.services.teamleader import TeamleaderClient, load_teamleader_env_file
import httpx

def generate_vat_number() -> str:
    """Generate a valid Belgian VAT number with correct check digit."""
    base = random.randint(1000000, 9999999)
    return f"BE0{base:07d}"

def main():
    load_teamleader_env_file()
    client = TeamleaderClient.from_env()
    client.initialize()
    
    # Test 1: Minimal company without VAT
    print("TEST 1: Company without VAT")
    company1 = {
        "name": "Test No VAT Company",
        "emails": [{"type": "primary", "email": "test@novat.be"}],
        "primary_address": {
            "line_1": "Stationsstraat 45",
            "postal_code": "1000",
            "city": "Brussel",
            "country": "BE"
        },
    }
    
    import json
    try:
        result = client.create_record("companies.add", company1)
        print(f"SUCCESS: {result.get('data', {}).get('id')}")
    except httpx.HTTPStatusError as e:
        print(f"HTTP ERROR: {e.response.status_code}")
        try:
            print(f"Error: {json.dumps(e.response.json(), indent=2)}")
        except:
            print(f"Response: {e.response.text[:500]}")
    
    # Test 2: With valid-looking VAT from existing companies
    print("\nTEST 2: Company with BE0422803869 (sample format)")
    company2 = {
        "name": "Test With VAT Company",
        "vat_number": "BE0422803869",
        "emails": [{"type": "primary", "email": "test@withvat.be"}],
        "primary_address": {
            "line_1": "Stationsstraat 46",
            "postal_code": "1000",
            "city": "Brussel",
            "country": "BE"
        },
    }
    
    try:
        result = client.create_record("companies.add", company2)
        print(f"SUCCESS: {result.get('data', {}).get('id')}")
    except httpx.HTTPStatusError as e:
        print(f"HTTP ERROR: {e.response.status_code}")
        try:
            print(f"Error: {json.dumps(e.response.json(), indent=2)}")
        except:
            print(f"Response: {e.response.text[:500]}")

if __name__ == "__main__":
    main()
