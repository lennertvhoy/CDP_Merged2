#!/usr/bin/env python3
"""Verify Teamleader sync status."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.services.teamleader import TeamleaderClient, load_teamleader_env_file
from src.config import settings
import asyncpg

async def main():
    load_teamleader_env_file()
    
    # Count in Teamleader
    client = TeamleaderClient.from_env()
    client.initialize()
    
    print("="*60)
    print("TEAMLEADER COUNTS")
    print("="*60)
    
    companies_response = client.list_records("companies.list", page_size=1, page_number=1)
    companies_meta = companies_response.get("meta", {})
    companies_total = companies_meta.get("page", {}).get("total", "unknown")
    print(f"Companies: {companies_total} total pages" if companies_total != "unknown" else f"Companies: ~{len(companies_response.get('data', []))} on first page")
    
    # Actually count all companies
    all_companies = list(client.list_all_records("companies.list", page_size=100))
    print(f"Companies (actual count): {len(all_companies)}")
    
    all_contacts = list(client.list_all_records("contacts.list", page_size=100))
    print(f"Contacts (actual count): {len(all_contacts)}")
    
    all_deals = list(client.list_all_records("deals.list", page_size=100))
    print(f"Deals (actual count): {len(all_deals)}")
    
    # Show sample company names
    print("\nSample companies in Teamleader:")
    for company in all_companies[:10]:
        print(f"  - {company.get('name')} ({company.get('id')})")
    
    # Count in PostgreSQL
    print("\n" + "="*60)
    print("POSTGRESQL COUNTS")
    print("="*60)
    
    pool = await asyncpg.create_pool(settings.DATABASE_URL)
    async with pool.acquire() as conn:
        pg_companies = await conn.fetchval("SELECT COUNT(*) FROM crm_companies")
        pg_contacts = await conn.fetchval("SELECT COUNT(*) FROM crm_contacts")
        pg_deals = await conn.fetchval("SELECT COUNT(*) FROM crm_deals")
        
        print(f"Companies: {pg_companies}")
        print(f"Contacts: {pg_contacts}")
        print(f"Deals: {pg_deals}")
        
        print("\nCompanies in PostgreSQL:")
        rows = await conn.fetch("SELECT company_name, source_record_id FROM crm_companies ORDER BY company_name")
        for row in rows:
            print(f"  - {row['company_name']} ({row['source_record_id'][:8]}...)")
    
    await pool.close()
    
    print("\n" + "="*60)
    print("COMPARISON")
    print("="*60)
    print(f"Companies: {len(all_companies)} in Teamleader, {pg_companies} in PostgreSQL")
    print(f"Contacts: {len(all_contacts)} in Teamleader, {pg_contacts} in PostgreSQL")
    print(f"Deals: {len(all_deals)} in Teamleader, {pg_deals} in PostgreSQL")

if __name__ == "__main__":
    asyncio.run(main())
