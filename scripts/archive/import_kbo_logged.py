#!/usr/bin/env python3
"""
KBO Import with Progress Logging
Logs progress every 1000 companies
"""
import asyncio
import csv
import os
import sys
from datetime import datetime
import asyncpg

KBO_DIR = "kbo_extracted"
BATCH_SIZE = 500

async def import_kbo_with_logging():
    """Import KBO data with regular progress updates"""
    
    conn = await asyncpg.connect(
        'postgresql://cdpadmin:<redacted>@cdp-postgres-b1ms.postgres.database.azure.com:5432/postgres?sslmode=require'
    )
    
    # Get starting count
    start_count = await conn.fetchval('SELECT COUNT(*) FROM companies')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting from {start_count:,} companies")
    
    # Load reference data
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Loading reference data...")
    names = {}
    with open(f"{KBO_DIR}/denomination.csv", 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['EntityNumber'] not in names or row['TypeOfDenomination'] == '001':
                names[row['EntityNumber']] = row['Denomination']
    
    addresses = {}
    with open(f"{KBO_DIR}/address.csv", 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['EntityNumber'] not in addresses:
                addresses[row['EntityNumber']] = row
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Loaded {len(names):,} names, {len(addresses):,} addresses")
    
    # Process enterprises
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting import...")
    batch = []
    processed = 0
    last_log = datetime.now()
    
    with open(f"{KBO_DIR}/enterprise.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            # Skip already imported
            if i < start_count:
                continue
            
            entity_num = row['EnterpriseNumber'].replace('.', '')
            addr = addresses.get(row['EnterpriseNumber'], {})
            name = names.get(row['EnterpriseNumber'], f'Company {entity_num}')
            
            batch.append((
                entity_num, name[:500],
                f"{addr.get('StreetNL', '')} {addr.get('HouseNumber', '')}".strip()[:200] if addr else None,
                addr.get('MunicipalityNL', '')[:100] if addr else None,
                addr.get('Zipcode', '')[:20] if addr else None,
                'BE', row.get('JuridicalForm', '')[:50], 'KBO'
            ))
            
            if len(batch) >= BATCH_SIZE:
                await conn.executemany('''
                    INSERT INTO companies (kbo_number, company_name, street_address, city, postal_code, 
                        country, legal_form, source_system, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    ON CONFLICT (kbo_number) DO NOTHING
                ''', batch)
                processed += len(batch)
                
                # Log every 1000 companies or every minute
                now = datetime.now()
                if processed % 1000 == 0 or (now - last_log).seconds >= 60:
                    total = start_count + processed
                    percent = total / 516000 * 100
                    elapsed = (now - last_log).total_seconds()
                    rate = 1000 / elapsed * 60 if elapsed > 0 else 0
                    remaining = (516000 - total) / (processed / ((now - datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=0)).total_seconds() + 1))
                    
                    print(f"[{now.strftime('%H:%M:%S')}] Progress: {total:,} companies ({percent:.1f}%) - Rate: {rate:.0f}/hour")
                    sys.stdout.flush()
                    last_log = now
                
                batch = []
    
    # Insert remaining
    if batch:
        await conn.executemany('''
            INSERT INTO companies (kbo_number, company_name, street_address, city, postal_code,
                country, legal_form, source_system, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            ON CONFLICT (kbo_number) DO NOTHING
        ''', batch)
        processed += len(batch)
    
    final_count = await conn.fetchval('SELECT COUNT(*) FROM companies')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Import complete! Total: {final_count:,} companies")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(import_kbo_with_logging())
