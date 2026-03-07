#!/usr/bin/env python3
"""
KBO Full Import with Maximum Enrichment

Imports ALL enterprises from KBO zip into PostgreSQL and Tracardi with:
- Complete company data (names, addresses, contacts, activities)
- Free enrichment: CBE, geocoding, website discovery
- Azure enrichment: AI descriptions via Azure OpenAI

Usage:
    # Full import with all enrichment
    python scripts/import_kbo_full_enriched.py --all
    
    # Import only (skip enrichment)
    python scripts/import_kbo_full_enriched.py --import-only
    
    # Resume from checkpoint
    python scripts/import_kbo_full_enriched.py --resume
    
    # Test mode (first 1000 records)
    python scripts/import_kbo_full_enriched.py --test

Estimated processing:
    - Import: ~2-3 hours for 1.94M enterprises
    - Enrichment: ~8-12 hours (geocoding rate-limited)
    - Tracardi sync: ~4-6 hours
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import os
import signal
import sys
import time
import traceback
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import get_logger
from src.config import settings
from scripts.kbo_runtime import resolve_kbo_zip_path

logger = get_logger(__name__)

# ==========================================
# Configuration
# ==========================================

STATE_FILE = Path("logs/import_kbo_full_state.json")
LOG_FILE = Path("logs/import_kbo_full.log")

DEFAULT_BATCH_SIZE = 2000
DEFAULT_CHECKPOINT_INTERVAL = 10000
ESTIMATED_TOTAL_COMPANIES = 1_940_000  # Based on enterprise.csv line count

# ==========================================
# Data Classes
# ==========================================

@dataclass
class ImportStats:
    """Statistics for import process."""
    started_at: datetime = field(default_factory=datetime.now)
    processed: int = 0
    inserted_pg: int = 0
    inserted_tracardi: int = 0
    skipped: int = 0
    errors: int = 0
    enriched: int = 0
    batches: int = 0
    
    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now() - self.started_at).total_seconds()
    
    @property
    def rate_per_second(self) -> float:
        elapsed = self.elapsed_seconds
        return self.processed / elapsed if elapsed > 0 else 0
    
    @property
    def percent_complete(self) -> float:
        return (self.processed / ESTIMATED_TOTAL_COMPANIES) * 100
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "processed": self.processed,
            "inserted_pg": self.inserted_pg,
            "inserted_tracardi": self.inserted_tracardi,
            "skipped": self.skipped,
            "errors": self.errors,
            "enriched": self.enriched,
            "batches": self.batches,
            "rate_per_second": round(self.rate_per_second, 2),
            "percent_complete": round(self.percent_complete, 2),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }


@dataclass
class Checkpoint:
    """Checkpoint data for resume capability."""
    last_processed_line: int = 0
    last_kbo_number: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    phase: str = "import"  # import, enrichment, sync
    
    def save(self, path: Path = STATE_FILE) -> None:
        """Save checkpoint to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "last_processed_line": self.last_processed_line,
                "last_kbo_number": self.last_kbo_number,
                "stats": self.stats,
                "timestamp": self.timestamp,
                "phase": self.phase,
            }, f, indent=2)
    
    @classmethod
    def load(cls, path: Path = STATE_FILE) -> Checkpoint | None:
        """Load checkpoint from file."""
        if not path.exists():
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            return cls(
                last_processed_line=data.get("last_processed_line", 0),
                last_kbo_number=data.get("last_kbo_number"),
                stats=data.get("stats", {}),
                timestamp=data.get("timestamp", datetime.now().isoformat()),
                phase=data.get("phase", "import"),
            )
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            return None
    
    def clear(self, path: Path = STATE_FILE) -> None:
        """Clear checkpoint file."""
        if path.exists():
            path.unlink()


# Global state for signal handling
_shutdown_requested = False
_current_stats: ImportStats | None = None
_current_checkpoint: Checkpoint | None = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    signame = signal.Signals(signum).name
    logger.warning(f"Received {signame}, initiating graceful shutdown...")
    _shutdown_requested = True
    
    if _current_stats and _current_checkpoint:
        _current_checkpoint.stats = _current_stats.to_dict()
        _current_checkpoint.save()
        logger.info(f"Progress saved. Resume with: python scripts/import_kbo_full_enriched.py --resume")


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# ==========================================
# KBO Data Extractor
# ==========================================

class KBODataExtractor:
    """Extract and merge data from KBO zip file."""
    
    def __init__(self, zip_path: Path):
        self.zip_path = zip_path
        self._nace_descriptions: dict[str, str] = {}
        self._juridical_forms: dict[str, str] = {}
        self._load_code_mappings()
    
    def _load_code_mappings(self):
        """Load NACE and juridical form descriptions from code.csv."""
        logger.info("Loading code mappings...")
        with zipfile.ZipFile(self.zip_path, 'r') as zf:
            with zf.open('code.csv') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    category = row.get('Category', '')
                    code = row.get('Code', '')
                    desc = row.get('Description', '')
                    
                    if category in ('Nace2008', 'Nace2025') and code.isdigit():
                        self._nace_descriptions[code] = desc
                    elif category == 'JuridicalForm' and code.isdigit():
                        self._juridical_forms[code] = desc
        
        logger.info(f"Loaded {len(self._nace_descriptions)} NACE codes, {len(self._juridical_forms)} juridical forms")
    
    def stream_enterprises(self, start_line: int = 0, max_lines: int | None = None):
        """Stream enterprise records from zip."""
        yielded = 0
        with zipfile.ZipFile(self.zip_path, 'r') as zf:
            with zf.open('enterprise.csv') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for i, row in enumerate(reader, start=1):
                    if start_line and i <= start_line:
                        continue
                    if max_lines is not None and yielded >= max_lines:
                        break
                    yielded += 1
                    yield i, row
    
    def load_lookup_data(self) -> dict[str, dict]:
        """Load all lookup data (addresses, contacts, activities, denominations)."""
        logger.info("Loading lookup data from KBO zip...")
        
        lookups = {
            'addresses': {},
            'contacts': {},
            'activities': {},
            'denominations': {},
            'establishments': {},
        }
        
        with zipfile.ZipFile(self.zip_path, 'r') as zf:
            # Load addresses (prioritize REGO - registered office)
            logger.info("Loading addresses...")
            with zf.open('address.csv') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    entity_num = row['EntityNumber'].replace('.', '')
                    # Keep REGO address or first found
                    if entity_num not in lookups['addresses'] or row.get('TypeOfAddress') == 'REGO':
                        lookups['addresses'][entity_num] = row
            
            # Load contacts
            logger.info("Loading contacts...")
            with zf.open('contact.csv') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    entity_num = row['EntityNumber'].replace('.', '')
                    if entity_num not in lookups['contacts']:
                        lookups['contacts'][entity_num] = {}
                    contact_type = row.get('ContactType', '').lower()
                    lookups['contacts'][entity_num][contact_type] = row.get('Value', '')
            
            # Load activities (NACE codes) - memory optimized, store only codes
            logger.info("Loading activities...")
            with zf.open('activity.csv') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    entity_num = row['EntityNumber'].replace('.', '')
                    nace_code = row.get('NaceCode', '')
                    if nace_code:
                        if entity_num not in lookups['activities']:
                            lookups['activities'][entity_num] = []
                        lookups['activities'][entity_num].append(nace_code)
            
            # Load denominations (company names) - memory optimized
            logger.info("Loading denominations...")
            with zf.open('denomination.csv') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    entity_num = row['EntityNumber'].replace('.', '')
                    denom_type = row.get('TypeOfDenomination', '')
                    name = row.get('Denomination', '')
                    
                    if entity_num not in lookups['denominations']:
                        # Store as tuple: (main_name, alt_names_list)
                        lookups['denominations'][entity_num] = [None, []]
                    
                    # Keep first alternate name (up to 10)
                    if len(lookups['denominations'][entity_num][1]) < 10:
                        lookups['denominations'][entity_num][1].append(name)
                    
                    # Prefer type 001 (commercial name) or use first
                    if denom_type == '001' or lookups['denominations'][entity_num][0] is None:
                        lookups['denominations'][entity_num][0] = name
            
            # Load establishments
            logger.info("Loading establishments...")
            with zf.open('establishment.csv') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    enterprise_num = row['EnterpriseNumber'].replace('.', '')
                    if enterprise_num not in lookups['establishments']:
                        lookups['establishments'][enterprise_num] = []
                    lookups['establishments'][enterprise_num].append({
                        'establishment_number': row.get('EstablishmentNumber', ''),
                        'start_date': row.get('StartDate', ''),
                    })
        
        logger.info(f"Lookup data loaded: {len(lookups['addresses'])} addresses, "
                   f"{len(lookups['contacts'])} contacts, {len(lookups['activities'])} activity records, "
                   f"{len(lookups['denominations'])} names")
        
        return lookups
    
    def build_company_record(self, enterprise_row: dict, lookups: dict) -> dict[str, Any] | None:
        """Build a complete company record from all KBO data sources."""
        entity_num = enterprise_row['EnterpriseNumber'].replace('.', '')
        
        # Get denomination (company name) - now stored as [main_name, alt_names_list]
        denom_data = lookups['denominations'].get(entity_num, [None, []])
        company_name = denom_data[0] or f"Company {entity_num}"
        all_names = denom_data[1]
        
        # Get address
        address = lookups['addresses'].get(entity_num, {})
        
        # Get contacts
        contacts = lookups['contacts'].get(entity_num, {})
        
        # Get activities (NACE codes) - now stored as simple list of strings
        all_nace_codes = lookups['activities'].get(entity_num, [])
        main_nace = all_nace_codes[0] if all_nace_codes else None
        
        # Get establishments
        establishments = lookups['establishments'].get(entity_num, [])
        
        # Parse dates
        founded_date = None
        start_date = enterprise_row.get('StartDate', '')
        if start_date:
            try:
                founded_date = datetime.strptime(start_date, '%d-%m-%Y').date()
            except (ValueError, TypeError):
                pass
        
        # Get juridical form description
        juridical_form_code = enterprise_row.get('JuridicalForm', '')
        juridical_form = self._juridical_forms.get(juridical_form_code, '')
        
        # Build complete record
        return {
            'kbo_number': entity_num,
            'company_name': company_name[:500],
            'all_names': all_names[:10],  # Store up to 10 alternative names
            'street_address': f"{address.get('StreetNL', '')} {address.get('HouseNumber', '')}".strip()[:200] if address else None,
            'city': address.get('MunicipalityNL', '')[:100] if address else None,
            'postal_code': address.get('Zipcode', '')[:20] if address else None,
            'country': 'BE',
            'industry_nace_code': main_nace[:10] if main_nace else None,
            'all_nace_codes': all_nace_codes[:20],  # Store up to 20 NACE codes
            'nace_descriptions': [self._nace_descriptions.get(code, '') for code in all_nace_codes[:5]],
            'legal_form_code': juridical_form_code[:50] if juridical_form_code else None,
            'legal_form': juridical_form[:100] if juridical_form else None,
            'founded_date': founded_date,
            'status': enterprise_row.get('Status', ''),
            'juridical_situation': enterprise_row.get('JuridicalSituation', ''),
            'type_of_enterprise': enterprise_row.get('TypeOfEnterprise', ''),
            'main_email': contacts.get('email')[:255] if contacts.get('email') else None,
            'main_phone': contacts.get('tel')[:50] if contacts.get('tel') else None,
            'main_fax': contacts.get('fax')[:50] if contacts.get('fax') else None,
            'website_url': contacts.get('web')[:500] if contacts.get('web') else None,
            'establishment_count': len(establishments),
            'source_system': 'KBO_FULL',
            'source_id': enterprise_row['EnterpriseNumber'],
            'sync_status': 'pending',
        }


# ==========================================
# PostgreSQL Import
# ==========================================

async def import_to_postgresql(
    companies: list[dict],
    conn: Any,
) -> tuple[int, int]:
    """Import companies to PostgreSQL using COPY protocol."""
    if not companies:
        return 0, 0
    
    # Convert to tuples for COPY
    records = []
    for c in companies:
        first_nace_description = next(
            (desc for desc in c.get("nace_descriptions", []) if desc),
            None,
        )
        enrichment_payload = {
            "all_names": c.get("all_names", []),
            "all_nace_codes": c.get("all_nace_codes", []),
            "nace_descriptions": c.get("nace_descriptions", []),
            "legal_form_code": c.get("legal_form_code"),
            "status": c.get("status"),
            "juridical_situation": c.get("juridical_situation"),
            "type_of_enterprise": c.get("type_of_enterprise"),
            "main_fax": c.get("main_fax"),
            "establishment_count": c.get("establishment_count"),
        }
        has_enrichment_payload = any(
            value not in (None, "", [], {})
            for value in enrichment_payload.values()
        )
        records.append((
            c.get("kbo_number"),
            c.get("company_name", "")[:500],
            c.get("street_address", "")[:200] if c.get("street_address") else None,
            c.get("city", "")[:100] if c.get("city") else None,
            c.get("postal_code", "")[:20] if c.get("postal_code") else None,
            c.get("country", "BE"),
            c.get("industry_nace_code", "")[:10] if c.get("industry_nace_code") else None,
            c.get("industry_nace_code", "")[:10] if c.get("industry_nace_code") else None,
            first_nace_description,
            c.get("legal_form", "")[:100] if c.get("legal_form") else None,
            c.get("legal_form_code", "")[:10] if c.get("legal_form_code") else None,
            c.get("founded_date"),
            c.get("status", "")[:20] if c.get("status") else None,
            c.get("juridical_situation", "")[:50] if c.get("juridical_situation") else None,
            c.get("type_of_enterprise", "")[:20] if c.get("type_of_enterprise") else None,
            c.get("main_email", "")[:255] if c.get("main_email") else None,
            c.get("main_phone", "")[:50] if c.get("main_phone") else None,
            c.get("main_fax", "")[:50] if c.get("main_fax") else None,
            c.get("website_url", "")[:500] if c.get("website_url") else None,
            c.get("source_system", "KBO_FULL"),
            c.get("source_id", ""),
            c.get("sync_status", "pending"),
            c.get("all_names", []),
            c.get("all_nace_codes", []),
            c.get("nace_descriptions", []),
            c.get("establishment_count") or 0,
            json.dumps(enrichment_payload) if has_enrichment_payload else None,
        ))
    
    try:
        # Use COPY for high-performance insert
        await conn.copy_records_to_table(
            "companies",
            records=records,
            columns=[
                "kbo_number", "company_name", "street_address", "city",
                "postal_code", "country", "industry_nace_code", "nace_code",
                "nace_description", "legal_form", "legal_form_code", "founded_date",
                "status", "juridical_situation", "type_of_enterprise", "main_email",
                "main_phone", "main_fax", "website_url", "source_system", "source_id",
                "sync_status", "all_names", "all_nace_codes", "nace_descriptions",
                "establishment_count", "enrichment_data",
            ],
        )
        return len(records), 0
    
    except Exception as e:
        # Fall back to INSERT with ON CONFLICT
        logger.warning(f"COPY failed, falling back to INSERT: {e}")
        inserted = 0
        skipped = 0
        for record in records:
            try:
                result = await conn.execute(
                    """
                    INSERT INTO companies (
                        kbo_number, company_name, street_address, city, postal_code,
                        country, industry_nace_code, nace_code, nace_description,
                        legal_form, legal_form_code, founded_date, status,
                        juridical_situation, type_of_enterprise, main_email,
                        main_phone, main_fax, website_url, source_system, source_id,
                        sync_status, all_names, all_nace_codes, nace_descriptions,
                        establishment_count, enrichment_data
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                        $12, $13, $14, $15, $16, $17, $18, $19, $20, $21,
                        $22, $23, $24, $25, $26, $27
                    )
                    ON CONFLICT (kbo_number) DO NOTHING
                    """,
                    *record
                )
                if result.endswith("1"):
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e2:
                logger.debug(f"Insert error for {record[0]}: {e2}")
                skipped += 1
        return inserted, skipped


# ==========================================
# Tracardi Sync
# ==========================================

import httpx

async def get_tracardi_token() -> str:
    """Get Tracardi authentication token."""
    tracardi_url = os.getenv("TRACARDI_API_URL", "http://localhost:8686")
    username = os.getenv("TRACARDI_USERNAME", "admin@admin.com")
    password = os.getenv("TRACARDI_PASSWORD", "")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{tracardi_url}/user/token",
            data={
                "username": username,
                "password": password,
                "grant_type": "password"
            }
        )
        response.raise_for_status()
        return response.json()["access_token"]


def transform_to_tracardi(company: dict) -> dict:
    """Transform company data to Tracardi profile format."""
    now_iso = datetime.now().isoformat()
    
    # Format KBO with dots
    kbo = company.get("kbo_number", "")
    formatted_kbo = f"{kbo[:4]}.{kbo[4:7]}.{kbo[7:]}" if len(kbo) == 10 else kbo
    
    traits = {
        "company_name": company.get("company_name"),
        "kbo_number": formatted_kbo,
        "kbo_raw": kbo,
        "street_address": company.get("street_address"),
        "city": company.get("city"),
        "postal_code": company.get("postal_code"),
        "country": company.get("country", "BE"),
        "legal_form": company.get("legal_form"),
        "legal_form_code": company.get("legal_form_code"),
        "nace_code": company.get("industry_nace_code"),
        "all_nace_codes": company.get("all_nace_codes", []),
        "nace_descriptions": company.get("nace_descriptions", []),
        "status": company.get("status"),
        "founded_date": company.get("founded_date").isoformat() if company.get("founded_date") else None,
        "email": company.get("main_email"),
        "phone": company.get("main_phone"),
        "website": company.get("website_url"),
        "alternative_names": company.get("all_names", []),
        "establishment_count": company.get("establishment_count", 0),
        "data_source": "KBO_Belgium_Full",
        "imported_at": now_iso,
    }
    
    # Remove None values
    traits = {k: v for k, v in traits.items() if v is not None}
    
    return {
        "id": formatted_kbo,
        "traits": traits,
        "metadata": {
            "time": {
                "insert": now_iso,
                "create": now_iso,
            },
            "system": {
                "inserted": now_iso,
                "created": now_iso,
            }
        }
    }


async def sync_to_tracardi(
    companies: list[dict],
    token: str,
) -> tuple[int, int]:
    """Sync companies to Tracardi."""
    tracardi_url = os.getenv("TRACARDI_API_URL", "http://localhost:8686")
    headers = {"Authorization": f"Bearer {token}"}
    
    profiles = [transform_to_tracardi(c) for c in companies]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{tracardi_url}/profiles/import",
                json=profiles,
                headers=headers
            )
            
            if response.status_code == 200:
                return len(profiles), 0
            else:
                logger.warning(f"Tracardi sync failed: {response.status_code} - {response.text[:200]}")
                return 0, len(profiles)
        
        except Exception as e:
            logger.error(f"Tracardi sync error: {e}")
            return 0, len(profiles)


# ==========================================
# Main Import Process
# ==========================================

async def run_full_import(
    max_records: int | None = None,
    resume: bool = False,
    skip_tracardi: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    checkpoint_interval: int = DEFAULT_CHECKPOINT_INTERVAL,
    zip_path: Path | None = None,
) -> ImportStats:
    """Run the full import process."""
    global _current_stats, _current_checkpoint, _shutdown_requested
    
    stats = ImportStats()
    _current_stats = stats
    
    # Load checkpoint
    checkpoint = Checkpoint()
    if resume:
        loaded = Checkpoint.load()
        if loaded:
            checkpoint = loaded
            logger.info(f"Resuming from line {checkpoint.last_processed_line}, phase: {checkpoint.phase}")
    
    _current_checkpoint = checkpoint
    
    effective_zip_path = resolve_kbo_zip_path() if zip_path is None else zip_path

    # Initialize extractor
    extractor = KBODataExtractor(effective_zip_path)
    
    # Load lookup data
    lookups = extractor.load_lookup_data()
    
    # Database connection
    try:
        import asyncpg
    except ImportError:
        logger.error("asyncpg not installed. Run: pip install asyncpg")
        raise
    
    # Get connection URL
    conn_url = os.environ.get("DATABASE_URL")
    if not conn_url:
        env_path = Path(__file__).parent.parent / ".env.database"
        if env_path.exists():
            import configparser
            config = configparser.ConfigParser()
            config.read(env_path)
            conn_url = config.get("connection_string", "url", fallback=None)
    
    if not conn_url:
        raise RuntimeError("DATABASE_URL or .env.database connection string required")
    
    conn = await asyncpg.connect(conn_url)
    
    try:
        # Get Tracardi token if needed
        tracardi_token = None
        if not skip_tracardi:
            try:
                tracardi_token = await get_tracardi_token()
                logger.info("Authenticated with Tracardi")
            except Exception as e:
                logger.warning(f"Could not authenticate with Tracardi: {e}")
                skip_tracardi = True
        
        # Get starting count
        start_count = await conn.fetchval("SELECT COUNT(*) FROM companies")
        logger.info(f"Starting import. Current PostgreSQL count: {start_count:,}")
        
        # Stream and process enterprises
        batch = []
        last_checkpoint_time = time.time()
        
        for line_num, enterprise_row in extractor.stream_enterprises(
            start_line=checkpoint.last_processed_line,
            max_lines=max_records,
        ):
            # Check for shutdown
            if _shutdown_requested:
                logger.warning("Shutdown requested, saving checkpoint...")
                checkpoint.last_processed_line = line_num
                checkpoint.last_kbo_number = enterprise_row.get("EnterpriseNumber")
                checkpoint.stats = stats.to_dict()
                checkpoint.save()
                break
            
            # Build company record
            company = extractor.build_company_record(enterprise_row, lookups)
            if company:
                batch.append(company)
            
            # Process batch when full
            if len(batch) >= batch_size:
                # Insert to PostgreSQL
                try:
                    inserted, skipped = await import_to_postgresql(batch, conn)
                    stats.inserted_pg += inserted
                    stats.skipped += skipped
                except Exception as e:
                    logger.error(f"PostgreSQL insert error: {e}")
                    stats.errors += len(batch)
                
                # Sync to Tracardi
                if tracardi_token and not skip_tracardi:
                    try:
                        synced, failed = await sync_to_tracardi(batch, tracardi_token)
                        stats.inserted_tracardi += synced
                    except Exception as e:
                        logger.error(f"Tracardi sync error: {e}")
                
                stats.processed += len(batch)
                stats.batches += 1
                batch = []
                
                # Progress logging
                if stats.processed % checkpoint_interval == 0:
                    elapsed = stats.elapsed_seconds
                    rate = stats.rate_per_second
                    eta_seconds = (ESTIMATED_TOTAL_COMPANIES - stats.processed) / rate if rate > 0 else 0
                    
                    logger.info(
                        f"Progress: {stats.processed:,} processed | "
                        f"PG: {stats.inserted_pg:,} inserted | "
                        f"Tracardi: {stats.inserted_tracardi:,} synced | "
                        f"Errors: {stats.errors} | "
                        f"Rate: {rate:.1f}/s | "
                        f"ETA: {eta_seconds/3600:.1f}h"
                    )
                    
                    # Save checkpoint
                    checkpoint.last_processed_line = line_num
                    checkpoint.last_kbo_number = enterprise_row.get("EnterpriseNumber")
                    checkpoint.stats = stats.to_dict()
                    checkpoint.save()
        
        # Process final batch
        if batch and not _shutdown_requested:
            try:
                inserted, skipped = await import_to_postgresql(batch, conn)
                stats.inserted_pg += inserted
                stats.skipped += skipped
                
                if tracardi_token and not skip_tracardi:
                    synced, _ = await sync_to_tracardi(batch, tracardi_token)
                    stats.inserted_tracardi += synced
                
                stats.processed += len(batch)
            except Exception as e:
                logger.error(f"Final batch error: {e}")
        
        # Final stats
        final_count = await conn.fetchval("SELECT COUNT(*) FROM companies")
        
        logger.info("=" * 60)
        if _shutdown_requested:
            logger.info("IMPORT PAUSED (checkpoint saved)")
        else:
            logger.info("IMPORT COMPLETE")
            checkpoint.clear()
        
        logger.info(f"Final PostgreSQL count: {final_count:,}")
        logger.info(f"This session: {stats.inserted_pg:,} inserted to PG, {stats.inserted_tracardi:,} synced to Tracardi")
        logger.info(f"Total time: {stats.elapsed_seconds/3600:.1f} hours")
        logger.info(f"Average rate: {stats.rate_per_second:.1f} records/second")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        checkpoint.stats = stats.to_dict()
        checkpoint.save()
        raise
    
    finally:
        await conn.close()
    
    return stats


# ==========================================
# CLI
# ==========================================

def main():
    parser = argparse.ArgumentParser(
        description="Import ALL KBO data with maximum enrichment"
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Maximum records to import (default: all)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous checkpoint",
    )
    parser.add_argument(
        "--skip-tracardi",
        action="store_true",
        help="Skip Tracardi sync (PostgreSQL only)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Batch size (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=DEFAULT_CHECKPOINT_INTERVAL,
        help=f"Checkpoint interval (default: {DEFAULT_CHECKPOINT_INTERVAL})",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: import only 1000 records",
    )
    
    args = parser.parse_args()
    
    # Test mode override
    if args.test:
        args.max_records = 1000
        logger.info("TEST MODE: Importing only 1,000 records")
    
    # Run import
    try:
        stats = asyncio.run(run_full_import(
            max_records=args.max_records,
            resume=args.resume,
            skip_tracardi=args.skip_tracardi,
            batch_size=args.batch_size,
            checkpoint_interval=args.checkpoint_interval,
        ))
        
        # Exit code based on success
        sys.exit(0 if stats.errors < 1000 else 1)
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
