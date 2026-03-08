#!/usr/bin/env python3
"""Test script to see actual Teamleader company format."""

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
    
    # Get one company to see the format
    response = client.list_records("companies.list", page_size=1, page_number=1)
    
    print("="*80)
    print("RAW RESPONSE STRUCTURE")
    print("="*80)
    import json
    print(json.dumps(response, indent=2))
    
    if response.get("data"):
        company = response["data"][0]
        print("\n" + "="*80)
        print("COMPANY FIELDS")
        print("="*80)
        for key in sorted(company.keys()):
            value = company[key]
            print(f"{key}: {type(value).__name__} = {repr(value)[:100]}")

if __name__ == "__main__":
    asyncio.run(main())
