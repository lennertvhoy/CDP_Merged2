#!/usr/bin/env python3
"""Test script to debug Teamleader company creation."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.services.teamleader import TeamleaderClient, load_teamleader_env_file

async def main():
    load_teamleader_env_file()
    client = TeamleaderClient.from_env()
    client.initialize()
    
    # Test with minimal data first
    test_cases = [
        {"name": "Test Company Minimal"},
        {"name": "Test Company With Address", "primary_address": {"line_1": "Test Street 1", "city": "Brussel", "postal_code": "1000", "country": "BE"}},
        {"name": "Test Company With Email", "emails": [{"type": "primary", "email": "test@test.be"}]},
        {"name": "Test Company Full", "name": "Test Company Full", "primary_address": {"line_1": "Test Street 1", "city": "Brussel", "postal_code": "1000", "country": "BE"}, "emails": [{"type": "primary", "email": "test@example.be"}], "language": "nl"},
    ]
    
    for i, test_data in enumerate(test_cases):
        print(f"\n{'='*60}")
        print(f"Test {i+1}: {test_data}")
        print('='*60)
        try:
            result = client.create_record("companies.add", test_data)
            print(f"SUCCESS: Created company with ID: {result.get('data', {}).get('id')}")
        except Exception as e:
            print(f"ERROR: {e}")
            # Try to get more details
            if hasattr(e, 'response'):
                try:
                    error_detail = e.response.json()
                    print(f"Error details: {error_detail}")
                except:
                    print(f"Response text: {e.response.text[:500]}")

if __name__ == "__main__":
    asyncio.run(main())
