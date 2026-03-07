#!/usr/bin/env python3
"""
KBO Import with SQLite-backed lookups (Memory-efficient)

This version uses SQLite for lookup tables instead of in-memory dicts,
reducing RAM usage from ~10GB to ~500MB.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import os
import signal
import sqlite3
import sys
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import get_logger

logger = get_logger(__name__)

KBO_ZIP_PATH = Path("/home/ff/.openclaw/workspace/repos/CDP_Merged/KboOpenData_0285_2026_02_27_Full.zip")
STATE_FILE = Path("logs/import_kbo_full_state.json")
BATCH_SIZE = 2000
CHECKPOINT_INTERVAL = 10000
ESTIMATED_TOTAL = 1_940_000

@dataclass
class ImportStats:
    started_at: datetime = field(default_factory=datetime.now)
    processed: int = 0
    inserted: int = 0
    errors: int = 0
    
    @property
    def rate_per_second(self) -> float:
        elapsed = (datetime.now() - self.started_at).total_seconds()
        return self.processed / elapsed if elapsed > 0 else 0

class KBOImport:
    def __init__(self, zip_path: Path, db_path: Path = Path("kbo_lookups.db")):
        self.zip_path = zip_path
        self.db_path = db_path
        self.stats = ImportStats()
        self._stop_requested = False
        self._nace_desc: dict[str, str] = {}
        self._juridical_forms: dict[str, str] = {}
        
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.warning("Received SIGTERM/SIGINT, will stop after current batch...")
        self._stop_requested = True
    
    def _init_sqlite(self):
        """Initialize SQLite database for lookups."""
        if self.db_path.exists():
            self.db_path.unlink()
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        
        # Create lookup tables
        conn.execute("""
            CREATE TABLE addresses (
                entity_num TEXT PRIMARY KEY,
                street TEXT,
                house_num TEXT,
                zipcode TEXT,
                municipality TEXT,
                type_of_address TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE contacts (
                entity_num TEXT PRIMARY KEY,
                email TEXT,
                tel TEXT,
                fax TEXT,
                web TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE activities (
                entity_num TEXT,
                nace_code TEXT,
                classification TEXT,
                PRIMARY KEY (entity_num, nace_code)
            )
        """)
        
        conn.execute("""
            CREATE TABLE denominations (
                entity_num TEXT,
                name TEXT,
                type TEXT,
                PRIMARY KEY (entity_num, name)
            )
        """)
        
        conn.execute("CREATE INDEX idx_act_entity ON activities(entity_num)")
        conn.execute("CREATE INDEX idx_den_entity ON denominations(entity_num)")
        
        conn.commit()
        return conn
    
    def load_lookups(self):
        """Load all lookup data into SQLite (memory-efficient)."""
        conn = self._init_sqlite()
        
        with zipfile.ZipFile(self.zip_path, 'r') as zf:
            # Load NACE/juridical form codes (small, keep in memory)
            logger.info("Loading code mappings...")
            with zf.open('code.csv') as f:
                for row in csv.DictReader(io.TextIOWrapper(f, 'utf-8')):
                    cat = row.get('Category', '')
                    code = row.get('Code', '')
                    desc = row.get('Description', '')
                    if cat in ('Nace2008', 'Nace2025') and code.isdigit():
                        self._nace_desc[code] = desc
                    elif cat == 'JuridicalForm' and code.isdigit():
                        self._juridical_forms[code] = desc
            logger.info(f"Loaded {len(self._nace_desc)} NACE codes, {len(self._juridical_forms)} juridical forms")
            
            # Load addresses to SQLite
            logger.info("Loading addresses to SQLite...")
            with zf.open('address.csv') as f:
                batch = []
                for row in csv.DictReader(io.TextIOWrapper(f, 'utf-8')):
                    entity_num = row['EntityNumber'].replace('.', '')
                    # Keep only REGO or first occurrence
                    cur = conn.execute("SELECT 1 FROM addresses WHERE entity_num=?", (entity_num,))
                    if cur.fetchone() is None or row.get('TypeOfAddress') == 'REGO':
                        if row.get('TypeOfAddress') == 'REGO':
                            conn.execute("DELETE FROM addresses WHERE entity_num=?", (entity_num,))
                        batch.append((
                            entity_num,
                            row.get('StreetNL', ''),
                            row.get('HouseNumber', ''),
                            row.get('Zipcode', ''),
                            row.get('MunicipalityNL', ''),
                            row.get('TypeOfAddress', '')
                        ))
                        if len(batch) >= 10000:
                            conn.executemany(
                                "INSERT OR REPLACE INTO addresses VALUES (?,?,?,?,?,?)",
                                batch
                            )
                            batch = []
                if batch:
                    conn.executemany(
                        "INSERT OR REPLACE INTO addresses VALUES (?,?,?,?,?,?)",
                        batch
                    )
            conn.commit()
            
            # Load contacts
            logger.info("Loading contacts to SQLite...")
            with zf.open('contact.csv') as f:
                contacts_dict: dict[str, dict] = {}
                for row in csv.DictReader(io.TextIOWrapper(f, 'utf-8')):
                    entity_num = row['EntityNumber'].replace('.', '')
                    if entity_num not in contacts_dict:
                        contacts_dict[entity_num] = {}
                    contact_type = row.get('ContactType', '').lower()
                    contacts_dict[entity_num][contact_type] = row.get('Value', '')
                
                batch = [
                    (e, c.get('email', ''), c.get('tel', ''), c.get('fax', ''), c.get('web', ''))
                    for e, c in contacts_dict.items()
                ]
                conn.executemany(
                    "INSERT OR REPLACE INTO contacts VALUES (?,?,?,?,?)",
                    batch
                )
                conn.commit()
                contacts_dict.clear()
            
            # Load activities
            logger.info("Loading activities to SQLite...")
            with zf.open('activity.csv') as f:
                batch = []
                for row in csv.DictReader(io.TextIOWrapper(f, 'utf-8')):
                    entity_num = row['EntityNumber'].replace('.', '')
                    nace = row.get('NaceCode', '')
                    if nace:
                        batch.append((entity_num, nace, row.get('Classification', '')))
                        if len(batch) >= 10000:
                            conn.executemany(
                                "INSERT OR IGNORE INTO activities VALUES (?,?,?)",
                                batch
                            )
                            batch = []
                if batch:
                    conn.executemany(
                        "INSERT OR IGNORE INTO activities VALUES (?,?,?)",
                        batch
                    )
                conn.commit()
            
            # Load denominations
            logger.info("Loading denominations to SQLite...")
            with zf.open('denomination.csv') as f:
                batch = []
                for row in csv.DictReader(io.TextIOWrapper(f, 'utf-8')):
                    entity_num = row['EntityNumber'].replace('.', '')
                    name = row.get('Denomination', '')
                    dtype = row.get('TypeOfDenomination', '')
                    if name:
                        batch.append((entity_num, name, dtype))
                        if len(batch) >= 10000:
                            conn.executemany(
                                "INSERT OR IGNORE INTO denominations VALUES (?,?,?)",
                                batch
                            )
                            batch = []
                if batch:
                    conn.executemany(
                        "INSERT OR IGNORE INTO denominations VALUES (?,?,?)",
                        batch
                    )
                conn.commit()
        
        # Verify counts
        addr_count = conn.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
        act_count = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        den_count = conn.execute("SELECT COUNT(*) FROM denominations").fetchone()[0]
        logger.info(f"SQLite lookups ready: {addr_count} addresses, {act_count} activities, {den_count} names")
        
        conn.close()
    
    def get_company_data(self, entity_num: str, enterprise_row: dict) -> dict | None:
        """Get complete company data from SQLite lookups."""
        conn = sqlite3.connect(self.db_path)
        
        # Get address
        cur = conn.execute(
            "SELECT street, house_num, zipcode, municipality FROM addresses WHERE entity_num=?",
            (entity_num,)
        )
        addr = cur.fetchone()
        street = f"{addr[0]} {addr[1]}".strip() if addr else None
        city = addr[3] if addr else None
        zipcode = addr[2] if addr else None
        
        # Get contacts
        cur = conn.execute(
            "SELECT email, tel, fax, web FROM contacts WHERE entity_num=?",
            (entity_num,)
        )
        cont = cur.fetchone()
        email = cont[0] if cont else None
        phone = cont[1] if cont else None
        fax = cont[2] if cont else None
        web = cont[3] if cont else None
        
        # Get activities
        cur = conn.execute(
            "SELECT nace_code FROM activities WHERE entity_num=? ORDER BY classification",
            (entity_num,)
        )
        nace_codes = [r[0] for r in cur.fetchall()]
        main_nace = nace_codes[0] if nace_codes else None
        
        # Get denomination
        cur = conn.execute(
            "SELECT name FROM denominations WHERE entity_num=? AND type='001' LIMIT 1",
            (entity_num,)
        )
        den = cur.fetchone()
        company_name = den[0] if den else enterprise_row.get('EnterpriseNumber', '')
        
        # Parse dates
        founded_date = None
        start_date = enterprise_row.get('StartDate', '')
        if start_date:
            try:
                founded_date = datetime.strptime(start_date, '%d-%m-%Y').date().isoformat()
            except (ValueError, TypeError):
                pass
        
        # Get juridical form
        jf_code = enterprise_row.get('JuridicalForm', '')
        legal_form = self._juridical_forms.get(jf_code, '')
        
        conn.close()
        
        return {
            'kbo_number': entity_num,
            'company_name': company_name[:500],
            'street_address': street[:200] if street else None,
            'city': city[:100] if city else None,
            'postal_code': zipcode[:20] if zipcode else None,
            'country': 'BE',
            'industry_nace_code': main_nace[:10] if main_nace else None,
            'legal_form': legal_form[:100] if legal_form else None,
            'founded_date': founded_date,
            'main_email': email[:255] if email else None,
            'main_phone': phone[:50] if phone else None,
            'main_fax': fax[:50] if fax else None,
            'website_url': web[:500] if web else None,
            'source_system': 'KBO_FULL',
            'source_id': enterprise_row['EnterpriseNumber'],
            'sync_status': 'pending',
            'enrichment_data': json.dumps({'all_nace_codes': nace_codes[:20]})
        }
    
    async def import_to_postgresql(self, records: list[dict]):
        """Import records to PostgreSQL."""
        import asyncpg
        
        conn_str = os.getenv('DATABASE_URL')
        if not conn_str:
            raise ValueError("DATABASE_URL not set")
        
        conn = await asyncpg.connect(conn_str)
        inserted = 0
        
        for record in records:
            try:
                await conn.execute("""
                    INSERT INTO companies (
                        kbo_number, company_name, street_address, city, postal_code,
                        country, industry_nace_code, legal_form, founded_date,
                        main_email, main_phone, main_fax, website_url, 
                        source_system, source_id, sync_status, enrichment_data
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    ON CONFLICT (kbo_number) DO NOTHING
                """, *record.values())
                inserted += 1
            except Exception as e:
                logger.debug(f"Insert error for {record.get('kbo_number')}: {e}")
        
        await conn.close()
        return inserted
    
    async def run(self, max_records: int | None = None, resume: bool = False):
        """Main import loop."""
        import asyncpg
        
        # Load lookups to SQLite
        self.load_lookups()
        
        # Get starting point
        start_line = 0
        if resume and STATE_FILE.exists():
            with open(STATE_FILE) as f:
                state = json.load(f)
                start_line = state.get('last_line', 0)
                logger.info(f"Resuming from line {start_line}")
        
        # Connect to PostgreSQL to check count
        conn_str = os.getenv('DATABASE_URL')
        conn = await asyncpg.connect(conn_str)
        count = await conn.fetchval("SELECT COUNT(*) FROM companies")
        logger.info(f"Starting import. Current PostgreSQL count: {count}")
        await conn.close()
        
        # Process enterprises
        batch = []
        with zipfile.ZipFile(self.zip_path, 'r') as zf:
            with zf.open('enterprise.csv') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for i, row in enumerate(reader, start=1):
                    if i < start_line:
                        continue
                    if max_records and self.stats.processed >= max_records:
                        break
                    if self._stop_requested:
                        break
                    
                    entity_num = row['EntityNumber'].replace('.', '')
                    company_data = self.get_company_data(entity_num, row)
                    
                    if company_data:
                        batch.append(company_data)
                    
                    if len(batch) >= BATCH_SIZE:
                        inserted = await self.import_to_postgresql(batch)
                        self.stats.inserted += inserted
                        self.stats.processed += len(batch)
                        batch = []
                        
                        if self.stats.processed % CHECKPOINT_INTERVAL == 0:
                            with open(STATE_FILE, 'w') as f:
                                json.dump({'last_line': i}, f)
                            logger.info(
                                f"Progress: {self.stats.processed:,} processed, "
                                f"{self.stats.inserted:,} inserted, "
                                f"{self.stats.rate_per_second:.1f}/sec"
                            )
        
        # Final batch
        if batch:
            inserted = await self.import_to_postgresql(batch)
            self.stats.inserted += inserted
            self.stats.processed += len(batch)
        
        # Cleanup
        if self.db_path.exists():
            self.db_path.unlink()
        
        logger.info(
            f"Import complete: {self.stats.processed:,} processed, "
            f"{self.stats.inserted:,} inserted in "
            f"{(datetime.now() - self.stats.started_at).total_seconds()/60:.1f} minutes"
        )

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-records', type=int, help='Maximum records to import')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parser.add_argument('--test', action='store_true', help='Test mode (1000 records)')
    args = parser.parse_args()
    
    max_records = 1000 if args.test else args.max_records
    
    importer = KBOImport(KBO_ZIP_PATH)
    await importer.run(max_records=max_records, resume=args.resume)

if __name__ == '__main__':
    asyncio.run(main())
