#!/usr/bin/env python3
"""Direct import of all Teamleader companies to PostgreSQL."""

import asyncio
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.services.teamleader import TeamleaderClient, load_teamleader_env_file
from src.config import settings
import asyncpg


def extract_email_domain(email: str | None) -> str | None:
    """Extract domain from email address."""
    if not email or "@" not in email:
        return None
    return email.split("@")[1].lower()


async def main():
    load_teamleader_env_file()
    
    # Initialize Teamleader client
    client = TeamleaderClient.from_env()
    client.initialize()
    
    # Get all companies from Teamleader
    print("Fetching companies from Teamleader...")
    all_companies = list(client.list_all_records("companies.list", page_size=100))
    print(f"Found {len(all_companies)} companies")
    
    # Get all contacts
    print("Fetching contacts from Teamleader...")
    all_contacts = list(client.list_all_records("contacts.list", page_size=100))
    print(f"Found {len(all_contacts)} contacts")
    
    # Get all deals
    print("Fetching deals from Teamleader...")
    all_deals = list(client.list_all_records("deals.list", page_size=100))
    print(f"Found {len(all_deals)} deals")
    
    # Connect to PostgreSQL
    pool = await asyncpg.create_pool(settings.DATABASE_URL)
    
    async with pool.acquire() as conn:
        # Clear existing data
        print("\nClearing existing CRM data...")
        await conn.execute("TRUNCATE crm_companies, crm_contacts, crm_deals, crm_activities CASCADE")
        
        # Insert companies
        print(f"\nInserting {len(all_companies)} companies...")
        inserted = 0
        for company in all_companies:
            source_id = str(company.get("id", ""))
            vat_number = company.get("vat_number") or company.get("national_identification_number")
            
            # Extract address
            address = company.get("primary_address", {}) or company.get("address", {}) or {}
            
            # Extract email
            primary_email = None
            emails = company.get("emails", [])
            if emails and isinstance(emails[0], dict):
                primary_email = emails[0].get("email")
            elif emails:
                primary_email = str(emails[0])
            
            # Extract phone
            primary_phone = None
            phones = company.get("telephones", [])
            if phones and isinstance(phones[0], dict):
                primary_phone = phones[0].get("number")
            elif phones:
                primary_phone = str(phones[0])
            
            try:
                await conn.execute(
                    """
                    INSERT INTO crm_companies (
                        source_system, source_record_id, vat_number,
                        company_name, legal_name, business_type, status,
                        street_address, city, postal_code, country,
                        main_email, email_domain, main_phone, website_url,
                        crm_status, raw_data
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    """,
                    "teamleader",
                    source_id,
                    vat_number,
                    company.get("name", ""),
                    company.get("name"),
                    company.get("business_type"),
                    company.get("status"),
                    address.get("line_1"),
                    address.get("city"),
                    address.get("postal_code"),
                    address.get("country") or "BE",
                    primary_email,
                    extract_email_domain(primary_email),
                    primary_phone,
                    company.get("website"),
                    company.get("status", "active"),
                    json.dumps(company)
                )
                inserted += 1
            except Exception as e:
                print(f"Error inserting company {company.get('name')}: {e}")
        
        print(f"Inserted {inserted} companies")
        
        # Insert contacts
        print(f"\nInserting {len(all_contacts)} contacts...")
        inserted = 0
        for contact in all_contacts:
            source_id = str(contact.get("id", ""))
            
            # Get email
            primary_email = None
            emails = contact.get("emails", [])
            if emails and isinstance(emails[0], dict):
                primary_email = emails[0].get("email")
            
            # Get phone
            primary_phone = None
            phones = contact.get("telephones", [])
            if phones and isinstance(phones[0], dict):
                primary_phone = phones[0].get("number")
            
            # Get company link
            company_id = None
            company_relation = contact.get("company", {})
            if company_relation and isinstance(company_relation, dict):
                company_source_id = company_relation.get("id")
                if company_source_id:
                    # Find the internal company ID
                    row = await conn.fetchrow(
                        "SELECT id FROM crm_companies WHERE source_record_id = $1",
                        str(company_source_id)
                    )
                    if row:
                        company_id = row["id"]
            
            try:
                await conn.execute(
                    """
                    INSERT INTO crm_contacts (
                        source_system, source_record_id, crm_company_id,
                        first_name, last_name, email, phone,
                        job_title, crm_status, raw_data
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    "teamleader",
                    source_id,
                    company_id,
                    contact.get("first_name", ""),
                    contact.get("last_name", ""),
                    primary_email,
                    primary_phone,
                    contact.get("function"),
                    "active",
                    json.dumps(contact)
                )
                inserted += 1
            except Exception as e:
                print(f"Error inserting contact {contact.get('first_name')} {contact.get('last_name')}: {e}")
        
        print(f"Inserted {inserted} contacts")
        
        # Insert deals
        print(f"\nInserting {len(all_deals)} deals...")
        inserted = 0
        for deal in all_deals:
            source_id = str(deal.get("id", ""))
            
            # Get company link
            company_id = None
            company_relation = deal.get("company", {})
            if company_relation and isinstance(company_relation, dict):
                company_source_id = company_relation.get("id")
                if company_source_id:
                    row = await conn.fetchrow(
                        "SELECT id FROM crm_companies WHERE source_record_id = $1",
                        str(company_source_id)
                    )
                    if row:
                        company_id = row["id"]
            
            # Get contact link
            contact_id = None
            contact_relation = deal.get("contact", {})
            if contact_relation and isinstance(contact_relation, dict):
                contact_source_id = contact_relation.get("id")
                if contact_source_id:
                    row = await conn.fetchrow(
                        "SELECT id FROM crm_contacts WHERE source_record_id = $1",
                        str(contact_source_id)
                    )
                    if row:
                        contact_id = row["id"]
            
            try:
                await conn.execute(
                    """
                    INSERT INTO crm_deals (
                        source_system, source_record_id, crm_company_id, crm_contact_id,
                        deal_title, deal_value, deal_status, deal_phase,
                        raw_data
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    "teamleader",
                    source_id,
                    company_id,
                    contact_id,
                    deal.get("title", ""),
                    deal.get("estimated_value"),
                    deal.get("status", "open"),
                    deal.get("phase", {}).get("name") if isinstance(deal.get("phase"), dict) else deal.get("phase"),
                    json.dumps(deal)
                )
                inserted += 1
            except Exception as e:
                print(f"Error inserting deal {deal.get('title')}: {e}")
        
        print(f"Inserted {inserted} deals")
        
        # Show final counts
        print("\n" + "="*60)
        print("FINAL COUNTS")
        print("="*60)
        companies = await conn.fetchval("SELECT COUNT(*) FROM crm_companies")
        contacts = await conn.fetchval("SELECT COUNT(*) FROM crm_contacts")
        deals = await conn.fetchval("SELECT COUNT(*) FROM crm_deals")
        print(f"Companies: {companies}")
        print(f"Contacts: {contacts}")
        print(f"Deals: {deals}")
    
    await pool.close()
    print("\n✅ Import complete!")

if __name__ == "__main__":
    asyncio.run(main())
