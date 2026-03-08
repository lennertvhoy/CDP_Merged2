"""Sync Autotask PSA data to PostgreSQL with identity linking.

This script syncs companies, tickets, and contracts from Autotask to PostgreSQL,
creating identity links for unified 360° customer views.

Usage:
    # Demo mode (default - uses mock data)
    poetry run python scripts/sync_autotask_to_postgres.py

    # Production sync (requires credentials in .env.autotask)
    export AUTOTASK_DEMO_MODE=false
    poetry run python scripts/sync_autotask_to_postgres.py --full

    # Incremental sync
    poetry run python scripts/sync_autotask_to_postgres.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg
from src.services.autotask import AutotaskClient, AutotaskMockData
from src.config import settings

def get_database_url() -> str:
    """Get database URL from settings or environment."""
    url = settings.DATABASE_URL or os.getenv("DATABASE_URL")
    if not url:
        print("Error: DATABASE_URL not configured. Set it in .env or environment.")
        sys.exit(1)
    return url


async def get_db_pool():
    """Create database pool."""
    return await asyncpg.create_pool(get_database_url())


# Database schema migration for Autotask tables
AUTOTASK_TABLES_SQL = """
-- Autotask companies table
CREATE TABLE IF NOT EXISTS autotask_companies (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address1 VARCHAR(255),
    address2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),
    phone VARCHAR(50),
    fax VARCHAR(50),
    web_address VARCHAR(255),
    company_type VARCHAR(50),
    market_segment_id INTEGER,
    account_manager_id INTEGER,
    territory_id INTEGER,
    tax_id VARCHAR(50),
    create_date TIMESTAMP,
    last_modified_date TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Autotask tickets table
CREATE TABLE IF NOT EXISTS autotask_tickets (
    id VARCHAR(50) PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    company_id VARCHAR(50),
    contact_id VARCHAR(50),
    status VARCHAR(50),
    priority VARCHAR(50),
    queue_id INTEGER,
    ticket_type VARCHAR(100),
    issue_type VARCHAR(100),
    sub_issue_type VARCHAR(100),
    assigned_resource_id INTEGER,
    create_date TIMESTAMP,
    last_modified_date TIMESTAMP,
    due_date TIMESTAMP,
    completed_date TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES autotask_companies(id)
);

-- Autotask contracts table
CREATE TABLE IF NOT EXISTS autotask_contracts (
    id VARCHAR(50) PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,
    contract_name VARCHAR(255) NOT NULL,
    contract_type VARCHAR(100),
    status VARCHAR(50),
    contract_value DECIMAL(15, 2),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    billing_code_id INTEGER,
    service_level_agreement_id INTEGER,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES autotask_companies(id)
);

-- Autotask sync cursor tracking
CREATE TABLE IF NOT EXISTS autotask_sync_cursor (
    id INTEGER PRIMARY KEY DEFAULT 1,
    last_sync_at TIMESTAMP,
    companies_count INTEGER DEFAULT 0,
    tickets_count INTEGER DEFAULT 0,
    contracts_count INTEGER DEFAULT 0,
    CONSTRAINT single_row CHECK (id = 1)
);

INSERT INTO autotask_sync_cursor (id, last_sync_at) VALUES (1, NULL)
ON CONFLICT (id) DO NOTHING;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_autotask_tickets_company_id ON autotask_tickets(company_id);
CREATE INDEX IF NOT EXISTS idx_autotask_contracts_company_id ON autotask_contracts(company_id);
CREATE INDEX IF NOT EXISTS idx_autotask_companies_tax_id ON autotask_companies(tax_id);
"""


async def ensure_schema(pool) -> None:
    """Ensure Autotask tables exist in PostgreSQL."""
    async with pool.acquire() as conn:
        await conn.execute(AUTOTASK_TABLES_SQL)
    print("✓ Autotask schema ensured")


async def sync_companies(pool, client: AutotaskClient, full_sync: bool = False) -> int:
    """Sync Autotask companies to PostgreSQL."""
    count = 0
    
    async with pool.acquire() as conn:
        # Clear existing data if full sync
        if full_sync:
            await conn.execute("TRUNCATE autotask_companies CASCADE")
            print("Cleared existing company data (full sync)")
        
        for company in client.get_companies():
            await conn.execute(
                """
                INSERT INTO autotask_companies (
                    id, name, address1, address2, city, state, postal_code, country,
                    phone, fax, web_address, company_type, market_segment_id,
                    account_manager_id, territory_id, tax_id, create_date, last_modified_date
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    address1 = EXCLUDED.address1,
                    address2 = EXCLUDED.address2,
                    city = EXCLUDED.city,
                    state = EXCLUDED.state,
                    postal_code = EXCLUDED.postal_code,
                    country = EXCLUDED.country,
                    phone = EXCLUDED.phone,
                    fax = EXCLUDED.fax,
                    web_address = EXCLUDED.web_address,
                    company_type = EXCLUDED.company_type,
                    market_segment_id = EXCLUDED.market_segment_id,
                    account_manager_id = EXCLUDED.account_manager_id,
                    territory_id = EXCLUDED.territory_id,
                    tax_id = EXCLUDED.tax_id,
                    last_modified_date = EXCLUDED.last_modified_date,
                    synced_at = CURRENT_TIMESTAMP
                """,
                company.id,
                company.name,
                company.address1,
                company.address2,
                company.city,
                company.state,
                company.postal_code,
                company.country,
                company.phone,
                company.fax,
                company.web_address,
                company.company_type,
                company.market_segment_id,
                company.account_manager_id,
                company.territory_id,
                company.tax_id,
                company.create_date,
                company.last_modified_date,
            )
            count += 1
    
    return count


async def sync_tickets(pool, client: AutotaskClient, full_sync: bool = False) -> int:
    """Sync Autotask tickets to PostgreSQL."""
    count = 0
    
    async with pool.acquire() as conn:
        # Clear existing data if full sync
        if full_sync:
            await conn.execute("TRUNCATE autotask_tickets")
            print("Cleared existing ticket data (full sync)")
        
        for ticket in client.get_tickets():
            await conn.execute(
                """
                INSERT INTO autotask_tickets (
                    id, title, description, company_id, contact_id, status,
                    priority, queue_id, ticket_type, issue_type, sub_issue_type,
                    assigned_resource_id, create_date, last_modified_date, due_date, completed_date
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    company_id = EXCLUDED.company_id,
                    contact_id = EXCLUDED.contact_id,
                    status = EXCLUDED.status,
                    priority = EXCLUDED.priority,
                    queue_id = EXCLUDED.queue_id,
                    ticket_type = EXCLUDED.ticket_type,
                    issue_type = EXCLUDED.issue_type,
                    sub_issue_type = EXCLUDED.sub_issue_type,
                    assigned_resource_id = EXCLUDED.assigned_resource_id,
                    last_modified_date = EXCLUDED.last_modified_date,
                    due_date = EXCLUDED.due_date,
                    completed_date = EXCLUDED.completed_date,
                    synced_at = CURRENT_TIMESTAMP
                """,
                ticket.id,
                ticket.title,
                ticket.description,
                ticket.company_id,
                ticket.contact_id,
                ticket.status,
                ticket.priority,
                ticket.queue_id,
                ticket.ticket_type,
                ticket.issue_type,
                ticket.sub_issue_type,
                ticket.assigned_resource_id,
                ticket.create_date,
                ticket.last_modified_date,
                ticket.due_date,
                ticket.completed_date,
            )
            count += 1
    
    return count


async def sync_contracts(pool, client: AutotaskClient, full_sync: bool = False) -> int:
    """Sync Autotask contracts to PostgreSQL."""
    count = 0
    
    async with pool.acquire() as conn:
        # Clear existing data if full sync
        if full_sync:
            await conn.execute("TRUNCATE autotask_contracts")
            print("Cleared existing contract data (full sync)")
        
        for contract in client.get_contracts():
            await conn.execute(
                """
                INSERT INTO autotask_contracts (
                    id, company_id, contract_name, contract_type, status,
                    contract_value, start_date, end_date, billing_code_id,
                    service_level_agreement_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (id) DO UPDATE SET
                    company_id = EXCLUDED.company_id,
                    contract_name = EXCLUDED.contract_name,
                    contract_type = EXCLUDED.contract_type,
                    status = EXCLUDED.status,
                    contract_value = EXCLUDED.contract_value,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    billing_code_id = EXCLUDED.billing_code_id,
                    service_level_agreement_id = EXCLUDED.service_level_agreement_id,
                    synced_at = CURRENT_TIMESTAMP
                """,
                contract.id,
                contract.company_id,
                contract.contract_name,
                contract.contract_type,
                contract.status,
                contract.contract_value,
                contract.start_date,
                contract.end_date,
                contract.billing_code_id,
                contract.service_level_agreement_id,
            )
            count += 1
    
    return count


async def create_identity_links(pool) -> int:
    """Create identity links between Autotask companies and KBO records."""
    count = 0
    
    async with pool.acquire() as conn:
        # Match by Tax ID (VAT/BTW number)
        result = await conn.execute(
            """
            INSERT INTO source_identity_links (
                uid,
                subject_type,
                source_system,
                source_entity_type,
                source_record_id,
                is_primary
            )
            SELECT 
                c.id::varchar as uid,
                'company' as subject_type,
                'autotask' as source_system,
                'company' as source_entity_type,
                ac.id as source_record_id,
                false as is_primary
            FROM companies c
            JOIN autotask_companies ac ON 
                REPLACE(REPLACE(REPLACE(c.vat_number, '.', ''), ' ', ''), 'BE0', '') = 
                REPLACE(REPLACE(REPLACE(ac.tax_id, '.', ''), ' ', ''), 'BE0', '')
            WHERE c.vat_number IS NOT NULL 
              AND ac.tax_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM source_identity_links sil
                  WHERE sil.uid = c.id::varchar
                    AND sil.source_system = 'autotask'
                    AND sil.source_record_id = ac.id
              )
            ON CONFLICT (source_system, source_entity_type, source_record_id) DO NOTHING
            """
        )
        count = int(result.split()[-1]) if result else 0
    
    return count


async def update_sync_cursor(pool, companies: int, tickets: int, contracts: int) -> None:
    """Update the sync cursor with latest counts."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE autotask_sync_cursor SET
                last_sync_at = CURRENT_TIMESTAMP,
                companies_count = $1,
                tickets_count = $2,
                contracts_count = $3
            WHERE id = 1
            """,
            companies, tickets, contracts
        )


async def main():
    parser = argparse.ArgumentParser(description="Sync Autotask data to PostgreSQL")
    parser.add_argument("--full", action="store_true", help="Full sync (clears existing data)")
    parser.add_argument("--production", action="store_true", help="Use production API (requires credentials)")
    args = parser.parse_args()
    
    # Set production mode if requested
    if args.production:
        os.environ["AUTOTASK_DEMO_MODE"] = "false"
        print("Production mode enabled - will attempt real API calls")
    
    print("=" * 60)
    print("Autotask → PostgreSQL Sync")
    print("=" * 60)
    print(f"Mode: {'PRODUCTION' if args.production else 'DEMO (mock data)'}")
    print(f"Sync type: {'FULL' if args.full else 'Incremental'}")
    print()
    
    # Initialize database
    pool = await get_db_pool()
    await ensure_schema(pool)
    
    # Initialize Autotask client
    try:
        client = AutotaskClient()
    except ValueError as e:
        print(f"Error initializing Autotask client: {e}")
        print("\nFor production sync, ensure .env.autotask exists with:")
        print("  AUTOTASK_USERNAME=your_username")
        print("  AUTOTASK_PASSWORD=your_password")
        print("  AUTOTASK_INTEGRATION_CODE=your_code")
        await pool.close()
        return 1
    
    # Sync data
    start_time = datetime.utcnow()
    
    try:
        print("Syncing companies...")
        companies_count = await sync_companies(pool, client, full_sync=args.full)
        print(f"  ✓ Synced {companies_count} companies")
        
        print("Syncing tickets...")
        tickets_count = await sync_tickets(pool, client, full_sync=args.full)
        print(f"  ✓ Synced {tickets_count} tickets")
        
        print("Syncing contracts...")
        contracts_count = await sync_contracts(pool, client, full_sync=args.full)
        print(f"  ✓ Synced {contracts_count} contracts")
        
        print("\nCreating identity links...")
        links_count = await create_identity_links(pool)
        print(f"  ✓ Created {links_count} identity links")
        
        # Update sync cursor
        await update_sync_cursor(pool, companies_count, tickets_count, contracts_count)
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        print()
        print("=" * 60)
        print("Sync Complete!")
        print("=" * 60)
        print(f"Companies:    {companies_count}")
        print(f"Tickets:      {tickets_count}")
        print(f"Contracts:    {contracts_count}")
        print(f"ID Links:     {links_count}")
        print(f"Duration:     {duration:.2f}s")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()
        await pool.close()
        return 1
    
    finally:
        client.close()
        await pool.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
