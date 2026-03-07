#!/usr/bin/env python3
"""
Import KBO data to PostgreSQL
"""
import asyncio
import csv
import json
import os
from datetime import datetime
import asyncpg
from dotenv import load_dotenv

load_dotenv('.env.database')

KBO_DIR = "kbo_extracted"
BATCH_SIZE = 1000

async def import_kbo_data(limit=None):
    """Import KBO enterprise data to PostgreSQL"""
    
    # Connect to PostgreSQL (use full connection string)
    conn = await asyncpg.connect(
        'postgresql://cdpadmin:<redacted>@cdp-postgres-b1ms.postgres.database.azure.com:5432/postgres?sslmode=require'
    )
    
    print("Connected to PostgreSQL")
    
    # Load address data into memory for faster lookup
    print("Loading addresses...")
    addresses = {}
    with open(f"{KBO_DIR}/address.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_num = row['EntityNumber']
            if entity_num not in addresses:
                addresses[entity_num] = row
    print(f"Loaded {len(addresses)} addresses")
    
    # Load denomination (company names)
    print("Loading company names...")
    names = {}
    with open(f"{KBO_DIR}/denomination.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_num = row['EntityNumber']
            # Prefer type 001 (main name)
            if entity_num not in names or row['TypeOfDenomination'] == '001':
                names[entity_num] = row['Denomination']
    print(f"Loaded {len(names)} company names")
    
    # Load activity (NACE codes)
    print("Loading NACE codes...")
    nace_codes = {}
    with open(f"{KBO_DIR}/activity.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_num = row['EntityNumber']
            # Take first/main activity
            if entity_num not in nace_codes:
                nace_codes[entity_num] = row.get('NaceCode', '')
    print(f"Loaded {len(nace_codes)} NACE codes")
    
    # Process enterprises
    print("Importing enterprises...")
    inserted = 0
    skipped = 0
    batch = []
    
    with open(f"{KBO_DIR}/enterprise.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            
            entity_num = row['EnterpriseNumber'].replace('.', '')
            
            # Skip if already exists
            existing = await conn.fetchval(
                "SELECT 1 FROM companies WHERE kbo_number = $1", entity_num
            )
            if existing:
                skipped += 1
                continue
            
            # Get address
            addr = addresses.get(row['EnterpriseNumber'], {})
            
            # Get name
            name = names.get(row['EnterpriseNumber'], f"Company {entity_num}")
            
            # Get NACE
            nace = nace_codes.get(row['EnterpriseNumber'], '')
            
            # Parse dates
            founded_date = None
            if row.get('StartDate'):
                try:
                    founded_date = datetime.strptime(row['StartDate'], '%d-%m-%Y').date()
                except:
                    pass
            
            batch.append({
                'kbo_number': entity_num,
                'company_name': name[:500],
                'street_address': f"{addr.get('StreetNL', '')} {addr.get('HouseNumber', '')}".strip()[:200] if addr else None,
                'city': addr.get('MunicipalityNL', '')[:100] if addr else None,
                'postal_code': addr.get('Zipcode', '')[:20] if addr else None,
                'country': 'BE',
                'industry_nace_code': nace[:10] if nace else None,
                'legal_form': row.get('JuridicalForm', '')[:50],
                'founded_date': founded_date,
                'source_system': 'KBO',
                'source_id': row['EnterpriseNumber']
            })
            
            if len(batch) >= BATCH_SIZE:
                await insert_batch(conn, batch)
                inserted += len(batch)
                print(f"  Inserted: {inserted}, Skipped: {skipped}")
                batch = []
    
    # Insert remaining
    if batch:
        await insert_batch(conn, batch)
        inserted += len(batch)
    
    await conn.close()
    
    print(f"\nImport complete!")
    print(f"  Total inserted: {inserted}")
    print(f"  Total skipped: {skipped}")
    return inserted

async def insert_batch(conn, batch):
    """Insert batch of companies"""
    await conn.executemany('''
        INSERT INTO companies (
            kbo_number, company_name, street_address, city, postal_code,
            country, industry_nace_code, legal_form, founded_date,
            source_system, created_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW()
        )
        ON CONFLICT (kbo_number) DO NOTHING
    ''', [
        (
            b['kbo_number'], b['company_name'], b['street_address'],
            b['city'], b['postal_code'], b['country'],
            b['industry_nace_code'], b['legal_form'], b['founded_date'],
            b['source_system']
        )
        for b in batch
    ])

if __name__ == "__main__":
    import sys
    
    # Check if test mode (first 10K)
    test_mode = '--test' in sys.argv
    limit = 10000 if test_mode else None
    
    if test_mode:
        print("TEST MODE: Importing first 10,000 companies")
    else:
        print("FULL MODE: Importing all companies (may take 30+ minutes)")
    
    start_time = datetime.now()
    count = asyncio.run(import_kbo_data(limit))
    elapsed = datetime.now() - start_time
    
    print(f"\nTime elapsed: {elapsed}")
    print(f"Rate: {count / elapsed.total_seconds():.1f} companies/second")
