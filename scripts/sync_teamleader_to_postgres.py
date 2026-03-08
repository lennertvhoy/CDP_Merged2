#!/usr/bin/env python3
"""
Teamleader → PostgreSQL Sync Pipeline

Syncs companies, contacts, deals, and activities from Teamleader Focus to PostgreSQL.
Supports incremental sync with cursor tracking and KBO company matching.

Usage:
    # Full sync (all entities)
    poetry run python scripts/sync_teamleader_to_postgres.py --full
    
    # Sync specific entities
    poetry run python scripts/sync_teamleader_to_postgres.py --entities companies,contacts
    
    # Incremental sync (uses last cursor)
    poetry run python scripts/sync_teamleader_to_postgres.py
    
    # With custom database URL
    DATABASE_URL=postgresql://... poetry run python scripts/sync_teamleader_to_postgres.py

Environment:
    Requires .env.teamleader with valid OAuth credentials
    Requires DATABASE_URL pointing to PostgreSQL
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from dateutil import parser as date_parser

import asyncpg

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.core.logger import get_logger
from src.services.teamleader import TeamleaderClient, load_teamleader_env_file
from src.config import settings

logger = get_logger(__name__)

# Configuration - get from environment via settings, no hardcoded fallback
def get_database_url() -> str:
    """Get database URL from settings or environment."""
    url = settings.DATABASE_URL or os.getenv("DATABASE_URL")
    if not url:
        logger.error("DATABASE_URL not configured. Set it in .env or environment.")
        sys.exit(1)
    return url

DEFAULT_DATABASE_URL = get_database_url()
BATCH_SIZE = 100
PAGE_SIZE = 100


def parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime string to naive UTC datetime object."""
    if not value:
        return None
    try:
        dt = date_parser.parse(value)
        # Convert to UTC and remove timezone info for PostgreSQL
        if dt.tzinfo:
            from datetime import timezone
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


@dataclass
class SyncStats:
    """Track sync statistics."""
    entity_type: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    
    @property
    def total(self) -> int:
        return self.created + self.updated + self.skipped


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    stats: list[SyncStats] = field(default_factory=list)
    error_message: str | None = None
    
    def get_stat(self, entity_type: str) -> SyncStats:
        for stat in self.stats:
            if stat.entity_type == entity_type:
                return stat
        stat = SyncStats(entity_type=entity_type)
        self.stats.append(stat)
        return stat


class TeamleaderSync:
    """Sync Teamleader data to PostgreSQL."""
    
    def __init__(
        self,
        database_url: str,
        client: TeamleaderClient | None = None,
    ) -> None:
        self.database_url = database_url
        self.client = client
        self.pool: asyncpg.Pool | None = None
        
    async def initialize(self) -> None:
        """Initialize database pool and ensure client is ready."""
        self.pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
        
        if self.client is None:
            load_teamleader_env_file()
            self.client = TeamleaderClient.from_env()
            
        # Verify client works
        self.client.refresh_access_token()
        logger.info("teamleader_sync_initialized")
        
    async def close(self) -> None:
        """Close database pool."""
        if self.pool:
            await self.pool.close()
            
    async def get_sync_cursor(self, entity_type: str) -> str | None:
        """Get the last sync cursor for an entity type."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT cursor_value, cursor_type 
                FROM sync_state 
                WHERE source_system = 'teamleader' AND entity_type = $1
                """,
                entity_type
            )
            return row["cursor_value"] if row else None
            
    async def update_sync_cursor(
        self,
        entity_type: str,
        cursor_value: str,
        cursor_type: str = "id",
        records_synced: int = 0,
        status: str = "idle",
        error_message: str | None = None,
    ) -> None:
        """Update the sync cursor for an entity type."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sync_state 
                    (source_system, entity_type, cursor_value, cursor_type, 
                     records_synced, last_sync_at, sync_status, error_message)
                VALUES ('teamleader', $1, $2, $3, $4, CURRENT_TIMESTAMP, $5, $6)
                ON CONFLICT (source_system, entity_type) 
                DO UPDATE SET
                    cursor_value = EXCLUDED.cursor_value,
                    cursor_type = EXCLUDED.cursor_type,
                    records_synced = sync_state.records_synced + EXCLUDED.records_synced,
                    last_sync_at = EXCLUDED.last_sync_at,
                    sync_status = EXCLUDED.sync_status,
                    error_message = EXCLUDED.error_message
                """,
                entity_type, cursor_value, cursor_type, records_synced, status, error_message
            )
            
    def normalize_vat(self, vat: str | None) -> str | None:
        """Normalize VAT number for matching."""
        if not vat:
            return None
        # Remove spaces, dots, and standardize BE prefix
        vat = vat.upper().replace(" ", "").replace(".", "").replace("-", "")
        # Ensure BE prefix
        if vat.startswith("BE") and len(vat) == 12:
            return vat
        if len(vat) == 10 and vat.isdigit():
            return f"BE{vat}"
        return vat if vat.startswith("BE") else None
        
    def extract_email_domain(self, email: str | None) -> str | None:
        """Extract domain from email."""
        if not email or "@" not in email:
            return None
        return email.split("@")[-1].lower()
        
    def hash_email(self, email: str | None) -> str | None:
        """Create SHA-256 hash of email for matching."""
        if not email:
            return None
        return hashlib.sha256(email.lower().encode()).hexdigest()
        
    async def find_kbo_match(self, vat_number: str | None, company_name: str | None) -> tuple[str | None, str | None]:
        """Find matching KBO company by VAT or name similarity."""
        if not vat_number and not company_name:
            return None, None
            
        async with self.pool.acquire() as conn:
            # Try VAT match first (most reliable)
            if vat_number:
                normalized_vat = self.normalize_vat(vat_number)
                if normalized_vat:
                    row = await conn.fetchrow(
                        """
                        SELECT kbo_number, id::text as uid 
                        FROM companies 
                        WHERE vat_number = $1 
                        LIMIT 1
                        """,
                        normalized_vat
                    )
                    if row:
                        return row["kbo_number"], row["uid"]
                        
            # Try name match (fuzzy)
            if company_name:
                row = await conn.fetchrow(
                    """
                    SELECT kbo_number, id::text as uid, company_name
                    FROM companies 
                    WHERE company_name % $1
                    ORDER BY similarity(company_name, $1) DESC
                    LIMIT 1
                    """,
                    company_name
                )
                if row:
                    return row["kbo_number"], row["uid"]
                    
        return None, None
        
    async def sync_companies(self, full_sync: bool = False) -> SyncStats:
        """Sync companies from Teamleader to PostgreSQL."""
        stats = SyncStats("companies")
        last_id = None if full_sync else await self.get_sync_cursor("companies")
        
        logger.info("syncing_companies", full_sync=full_sync, cursor=last_id)
        
        page = 1
        total_processed = 0
        
        while True:
            try:
                response = self.client.list_records(
                    "companies.list",
                    page_size=PAGE_SIZE,
                    page_number=page,
                )
                
                records = response.get("data", [])
                if not records:
                    break
                    
                for record in records:
                    source_id = str(record.get("id", ""))
                    
                    # Skip if we've seen this before in incremental mode
                    if last_id and source_id <= last_id:
                        stats.skipped += 1
                        continue
                        
                    # Extract and normalize data
                    vat_number = self.normalize_vat(
                        record.get("vat_number") or record.get("national_identification_number")
                    )
                    company_name = record.get("name", "")
                    
                    # Find KBO match
                    kbo_number, org_uid = await self.find_kbo_match(vat_number, company_name)
                    
                    # Extract address
                    address = record.get("address", {}) or {}
                    primary_email = None
                    emails = record.get("emails", [])
                    if emails:
                        primary_email = emails[0].get("email") if isinstance(emails[0], dict) else str(emails[0])
                        
                    primary_phone = None
                    phones = record.get("telephones", [])
                    if phones:
                        primary_phone = phones[0].get("number") if isinstance(phones[0], dict) else str(phones[0])
                    
                    # Upsert to database
                    async with self.pool.acquire() as conn:
                        result = await conn.execute(
                            """
                            INSERT INTO crm_companies (
                                source_system, source_record_id, kbo_number, vat_number, organization_uid,
                                company_name, legal_name, business_type, status,
                                street_address, city, postal_code, country,
                                main_email, email_domain, main_phone, website_url,
                                crm_status, customer_type,
                                source_created_at, source_updated_at, last_sync_at, raw_data
                            ) VALUES (
                                'teamleader', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, CURRENT_TIMESTAMP, $21
                            )
                            ON CONFLICT (source_system, source_record_id) 
                            DO UPDATE SET
                                kbo_number = COALESCE(EXCLUDED.kbo_number, crm_companies.kbo_number),
                                vat_number = COALESCE(EXCLUDED.vat_number, crm_companies.vat_number),
                                organization_uid = COALESCE(EXCLUDED.organization_uid, crm_companies.organization_uid),
                                company_name = EXCLUDED.company_name,
                                business_type = EXCLUDED.business_type,
                                status = EXCLUDED.status,
                                street_address = EXCLUDED.street_address,
                                city = EXCLUDED.city,
                                postal_code = EXCLUDED.postal_code,
                                main_email = EXCLUDED.main_email,
                                email_domain = EXCLUDED.email_domain,
                                main_phone = EXCLUDED.main_phone,
                                website_url = EXCLUDED.website_url,
                                crm_status = EXCLUDED.crm_status,
                                customer_type = EXCLUDED.customer_type,
                                source_updated_at = EXCLUDED.source_updated_at,
                                last_sync_at = CURRENT_TIMESTAMP,
                                sync_version = crm_companies.sync_version + 1,
                                raw_data = EXCLUDED.raw_data
                            """,
                            source_id,
                            kbo_number,
                            vat_number,
                            org_uid,
                            company_name,
                            record.get("name"),
                            record.get("business_type"),
                            record.get("status"),
                            address.get("line_1"),
                            address.get("city"),
                            address.get("postal_code"),
                            address.get("country") or "BE",
                            primary_email,
                            self.extract_email_domain(primary_email),
                            primary_phone,
                            record.get("website"),
                            record.get("status"),
                            record.get("business_type"),
                            parse_datetime(record.get("created_at")),
                            parse_datetime(record.get("updated_at")),
                            json.dumps(record)
                        )
                        
                        if result and "UPDATE" in result:
                            stats.updated += 1
                        else:
                            stats.created += 1
                            
                    last_id = source_id
                    total_processed += 1
                    
                logger.info("companies_page_processed", page=page, records=len(records))
                page += 1
                
                # Check for more pages
                pagination = response.get("meta", {}).get("page", {})
                if page > pagination.get("total", page):
                    break
                    
                # Rate limit protection
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error("company_sync_error", page=page, error=str(e))
                stats.errors += 1
                await self.update_sync_cursor(
                    "companies", last_id or "", "id", total_processed, "error", str(e)
                )
                raise
                
        # Update cursor
        if last_id:
            await self.update_sync_cursor("companies", last_id, "id", total_processed, "idle")
            
        logger.info("companies_sync_complete", stats=stats)
        return stats
        
    async def sync_contacts(self, full_sync: bool = False) -> SyncStats:
        """Sync contacts from Teamleader to PostgreSQL."""
        stats = SyncStats("contacts")
        last_id = None if full_sync else await self.get_sync_cursor("contacts")
        
        logger.info("syncing_contacts", full_sync=full_sync, cursor=last_id)
        
        page = 1
        total_processed = 0
        
        # Build company ID lookup cache
        async with self.pool.acquire() as conn:
            company_rows = await conn.fetch(
                "SELECT source_record_id, id FROM crm_companies WHERE source_system = 'teamleader'"
            )
            company_id_map = {row["source_record_id"]: row["id"] for row in company_rows}
            
        while True:
            try:
                response = self.client.list_records(
                    "contacts.list",
                    page_size=PAGE_SIZE,
                    page_number=page,
                )
                
                records = response.get("data", [])
                if not records:
                    break
                    
                for record in records:
                    source_id = str(record.get("id", ""))
                    
                    if last_id and source_id <= last_id:
                        stats.skipped += 1
                        continue
                        
                    # Get company link
                    company_id = None
                    company_link = record.get("company", {})
                    if company_link:
                        company_source_id = str(company_link.get("id", ""))
                        company_id = company_id_map.get(company_source_id)
                        
                    # Extract emails
                    primary_email = None
                    emails = record.get("emails", [])
                    if emails and isinstance(emails[0], dict):
                        primary_email = emails[0].get("email")
                        
                    # Extract phones
                    primary_phone = None
                    mobile = None
                    phones = record.get("telephones", [])
                    for phone in phones:
                        if isinstance(phone, dict):
                            if phone.get("type") == "mobile":
                                mobile = phone.get("number")
                            elif not primary_phone:
                                primary_phone = phone.get("number")
                                
                    first_name = record.get("first_name", "")
                    last_name = record.get("last_name", "")
                    full_name = f"{first_name} {last_name}".strip() or record.get("name", "")
                    
                    async with self.pool.acquire() as conn:
                        result = await conn.execute(
                            """
                            INSERT INTO crm_contacts (
                                source_system, source_record_id, crm_company_id, source_company_id,
                                first_name, last_name, full_name,
                                email, email_hash, phone, mobile,
                                job_title, is_decision_maker,
                                source_created_at, source_updated_at, last_sync_at, raw_data
                            ) VALUES (
                                'teamleader', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, CURRENT_TIMESTAMP, $15
                            )
                            ON CONFLICT (source_system, source_record_id) 
                            DO UPDATE SET
                                crm_company_id = COALESCE(EXCLUDED.crm_company_id, crm_contacts.crm_company_id),
                                source_company_id = COALESCE(EXCLUDED.source_company_id, crm_contacts.source_company_id),
                                first_name = EXCLUDED.first_name,
                                last_name = EXCLUDED.last_name,
                                full_name = EXCLUDED.full_name,
                                email = EXCLUDED.email,
                                email_hash = EXCLUDED.email_hash,
                                phone = EXCLUDED.phone,
                                mobile = EXCLUDED.mobile,
                                job_title = EXCLUDED.job_title,
                                is_decision_maker = EXCLUDED.is_decision_maker,
                                source_updated_at = EXCLUDED.source_updated_at,
                                last_sync_at = CURRENT_TIMESTAMP,
                                sync_version = crm_contacts.sync_version + 1,
                                raw_data = EXCLUDED.raw_data
                            """,
                            source_id,
                            company_id,
                            str(company_link.get("id")) if company_link else None,
                            first_name,
                            last_name,
                            full_name,
                            primary_email,
                            self.hash_email(primary_email),
                            primary_phone,
                            mobile,
                            record.get("function"),
                            record.get("decision_maker", False),
                            parse_datetime(record.get("created_at")),
                            parse_datetime(record.get("updated_at")),
                            json.dumps(record)
                        )
                        
                        if result and "UPDATE" in result:
                            stats.updated += 1
                        else:
                            stats.created += 1
                            
                    last_id = source_id
                    total_processed += 1
                    
                logger.info("contacts_page_processed", page=page, records=len(records))
                page += 1
                
                pagination = response.get("meta", {}).get("page", {})
                if page > pagination.get("total", page):
                    break
                    
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error("contact_sync_error", page=page, error=str(e))
                stats.errors += 1
                await self.update_sync_cursor(
                    "contacts", last_id or "", "id", total_processed, "error", str(e)
                )
                raise
                
        if last_id:
            await self.update_sync_cursor("contacts", last_id, "id", total_processed, "idle")
            
        logger.info("contacts_sync_complete", stats=stats)
        return stats
        
    async def sync_deals(self, full_sync: bool = False) -> SyncStats:
        """Sync deals from Teamleader to PostgreSQL."""
        stats = SyncStats("deals")
        last_id = None if full_sync else await self.get_sync_cursor("deals")
        
        logger.info("syncing_deals", full_sync=full_sync, cursor=last_id)
        
        page = 1
        total_processed = 0
        
        # Build company ID lookup cache
        async with self.pool.acquire() as conn:
            company_rows = await conn.fetch(
                "SELECT source_record_id, id FROM crm_companies WHERE source_system = 'teamleader'"
            )
            company_id_map = {row["source_record_id"]: row["id"] for row in company_rows}
            
        while True:
            try:
                response = self.client.list_records(
                    "deals.list",
                    page_size=PAGE_SIZE,
                    page_number=page,
                )
                
                records = response.get("data", [])
                if not records:
                    break
                    
                for record in records:
                    source_id = str(record.get("id", ""))
                    
                    if last_id and source_id <= last_id:
                        stats.skipped += 1
                        continue
                        
                    # Get company link
                    company_id = None
                    company_link = record.get("company", {})
                    if company_link:
                        company_source_id = str(company_link.get("id", ""))
                        company_id = company_id_map.get(company_source_id)
                        
                    # Extract value
                    value_data = record.get("value", {}) or {}
                    deal_value = value_data.get("amount", 0)
                    currency = value_data.get("currency", "EUR")
                    
                    # Extract phase
                    phase_data = record.get("phase", {}) or {}
                    phase_name = phase_data.get("name", "")
                    
                    async with self.pool.acquire() as conn:
                        result = await conn.execute(
                            """
                            INSERT INTO crm_deals (
                                source_system, source_record_id, crm_company_id, source_company_id,
                                deal_title, deal_description,
                                deal_value, deal_currency,
                                deal_status, deal_phase, probability,
                                expected_close_date, actual_close_date,
                                source_created_at, source_updated_at, last_sync_at, raw_data
                            ) VALUES (
                                'teamleader', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, CURRENT_TIMESTAMP, $15
                            )
                            ON CONFLICT (source_system, source_record_id) 
                            DO UPDATE SET
                                crm_company_id = COALESCE(EXCLUDED.crm_company_id, crm_deals.crm_company_id),
                                deal_title = EXCLUDED.deal_title,
                                deal_description = EXCLUDED.deal_description,
                                deal_value = EXCLUDED.deal_value,
                                deal_currency = EXCLUDED.deal_currency,
                                deal_status = EXCLUDED.deal_status,
                                deal_phase = EXCLUDED.deal_phase,
                                probability = EXCLUDED.probability,
                                expected_close_date = EXCLUDED.expected_close_date,
                                actual_close_date = EXCLUDED.actual_close_date,
                                source_updated_at = EXCLUDED.source_updated_at,
                                last_sync_at = CURRENT_TIMESTAMP,
                                sync_version = crm_deals.sync_version + 1,
                                raw_data = EXCLUDED.raw_data
                            """,
                            source_id,
                            company_id,
                            str(company_link.get("id")) if company_link else None,
                            record.get("title", ""),
                            record.get("summary", ""),
                            deal_value,
                            currency,
                            record.get("status", ""),
                            phase_name,
                            record.get("probability", 0),
                            parse_datetime(record.get("estimated_closing_date")),
                            parse_datetime(record.get("closed_at")) if record.get("status") in ["won", "lost"] else None,
                            parse_datetime(record.get("created_at")),
                            parse_datetime(record.get("updated_at")),
                            json.dumps(record)
                        )
                        
                        if result and "UPDATE" in result:
                            stats.updated += 1
                        else:
                            stats.created += 1
                            
                    last_id = source_id
                    total_processed += 1
                    
                logger.info("deals_page_processed", page=page, records=len(records))
                page += 1
                
                pagination = response.get("meta", {}).get("page", {})
                if page > pagination.get("total", page):
                    break
                    
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error("deal_sync_error", page=page, error=str(e))
                stats.errors += 1
                await self.update_sync_cursor(
                    "deals", last_id or "", "id", total_processed, "error", str(e)
                )
                raise
                
        if last_id:
            await self.update_sync_cursor("deals", last_id, "id", total_processed, "idle")
            
        logger.info("deals_sync_complete", stats=stats)
        return stats
        
    async def sync_activities(self, full_sync: bool = False) -> SyncStats:
        """Sync activities/events from Teamleader to PostgreSQL."""
        stats = SyncStats("activities")
        last_id = None if full_sync else await self.get_sync_cursor("activities")
        
        logger.info("syncing_activities", full_sync=full_sync, cursor=last_id)
        
        page = 1
        total_processed = 0
        max_pages = 50  # Limit activities to avoid too much data
        
        # Build lookup caches
        async with self.pool.acquire() as conn:
            company_rows = await conn.fetch(
                "SELECT source_record_id, id FROM crm_companies WHERE source_system = 'teamleader'"
            )
            company_id_map = {row["source_record_id"]: row["id"] for row in company_rows}
            
            contact_rows = await conn.fetch(
                "SELECT source_record_id, id FROM crm_contacts WHERE source_system = 'teamleader'"
            )
            contact_id_map = {row["source_record_id"]: row["id"] for row in contact_rows}
            
        while page <= max_pages:
            try:
                response = self.client.list_records(
                    "events.list",
                    page_size=PAGE_SIZE,
                    page_number=page,
                )
                
                records = response.get("data", [])
                if not records:
                    break
                    
                for record in records:
                    source_id = str(record.get("id", ""))
                    
                    if last_id and source_id <= last_id:
                        stats.skipped += 1
                        continue
                        
                    # Parse links
                    company_id = None
                    contact_ids = []
                    participant_source_ids = []
                    
                    for link in record.get("links", []):
                        if isinstance(link, dict):
                            link_type = link.get("type")
                            link_id = str(link.get("id", ""))
                            participant_source_ids.append(link_id)
                            
                            if link_type == "company":
                                company_id = company_id_map.get(link_id)
                            elif link_type == "contact":
                                contact_id = contact_id_map.get(link_id)
                                if contact_id:
                                    contact_ids.append(contact_id)
                                    
                    activity_type = record.get("type", "event")
                    activity_type_map = {
                        "call": "call",
                        "meeting": "meeting", 
                        "task": "task",
                        "deadline": "deadline",
                    }
                    mapped_type = activity_type_map.get(activity_type, activity_type)
                    
                    async with self.pool.acquire() as conn:
                        result = await conn.execute(
                            """
                            INSERT INTO crm_activities (
                                source_system, source_record_id,
                                crm_company_id, crm_contact_id, source_company_id,
                                activity_type, activity_subject, activity_description,
                                participant_source_ids,
                                activity_date, activity_end_date,
                                completed,
                                source_created_at, source_updated_at, last_sync_at, raw_data
                            ) VALUES (
                                'teamleader', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, CURRENT_TIMESTAMP, $14
                            )
                            ON CONFLICT (source_system, source_record_id) 
                            DO UPDATE SET
                                crm_company_id = COALESCE(EXCLUDED.crm_company_id, crm_activities.crm_company_id),
                                activity_type = EXCLUDED.activity_type,
                                activity_subject = EXCLUDED.activity_subject,
                                activity_description = EXCLUDED.activity_description,
                                participant_source_ids = EXCLUDED.participant_source_ids,
                                activity_date = EXCLUDED.activity_date,
                                activity_end_date = EXCLUDED.activity_end_date,
                                completed = EXCLUDED.completed,
                                source_updated_at = EXCLUDED.source_updated_at,
                                last_sync_at = CURRENT_TIMESTAMP,
                                sync_version = crm_activities.sync_version + 1,
                                raw_data = EXCLUDED.raw_data
                            """,
                            source_id,
                            company_id,
                            contact_ids[0] if contact_ids else None,
                            str(company_id) if company_id else None,
                            mapped_type,
                            record.get("title", ""),
                            record.get("description", ""),
                            json.dumps(participant_source_ids),
                            parse_datetime(record.get("starts_at")),
                            parse_datetime(record.get("ends_at")),
                            record.get("completed", False),
                            parse_datetime(record.get("created_at")),
                            parse_datetime(record.get("updated_at")),
                            json.dumps(record)
                        )
                        
                        if result and "UPDATE" in result:
                            stats.updated += 1
                        else:
                            stats.created += 1
                            
                    last_id = source_id
                    total_processed += 1
                    
                logger.info("activities_page_processed", page=page, records=len(records))
                page += 1
                
                pagination = response.get("meta", {}).get("page", {})
                if page > pagination.get("total", page):
                    break
                    
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error("activity_sync_error", page=page, error=str(e))
                stats.errors += 1
                await self.update_sync_cursor(
                    "activities", last_id or "", "id", total_processed, "error", str(e)
                )
                raise
                
        if last_id:
            await self.update_sync_cursor("activities", last_id, "id", total_processed, "idle")
            
        logger.info("activities_sync_complete", stats=stats)
        return stats
        
    async def run_sync(self, entities: list[str], full_sync: bool = False) -> SyncResult:
        """Run the complete sync process."""
        result = SyncResult(success=True)
        
        try:
            await self.initialize()
            
            if "companies" in entities:
                stats = await self.sync_companies(full_sync=full_sync)
                result.stats.append(stats)
                
            if "contacts" in entities:
                stats = await self.sync_contacts(full_sync=full_sync)
                result.stats.append(stats)
                
            if "deals" in entities:
                stats = await self.sync_deals(full_sync=full_sync)
                result.stats.append(stats)
                
            if "activities" in entities:
                stats = await self.sync_activities(full_sync=full_sync)
                result.stats.append(stats)
                
        except Exception as e:
            logger.error("sync_failed", error=str(e))
            result.success = False
            result.error_message = str(e)
        finally:
            await self.close()
            
        return result


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Sync Teamleader data to PostgreSQL"
    )
    parser.add_argument(
        "--entities",
        type=str,
        default="companies,contacts,deals,activities",
        help="Comma-separated list of entities to sync (default: all)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Perform full sync (ignore cursor)"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=DEFAULT_DATABASE_URL,
        help="PostgreSQL connection URL"
    )
    return parser.parse_args()


async def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    entities = [e.strip() for e in args.entities.split(",")]
    valid_entities = {"companies", "contacts", "deals", "activities"}
    entities = [e for e in entities if e in valid_entities]
    
    if not entities:
        print("❌ No valid entities specified")
        return 1
        
    print("=" * 70)
    print("🚀 Teamleader → PostgreSQL Sync")
    print("=" * 70)
    print(f"Entities: {', '.join(entities)}")
    print(f"Mode: {'FULL' if args.full else 'INCREMENTAL'}")
    print(f"Database: {args.database_url.split('@')[-1]}")
    print("=" * 70)
    print()
    
    sync = TeamleaderSync(database_url=args.database_url)
    result = await sync.run_sync(entities, full_sync=args.full)
    
    print()
    print("=" * 70)
    if result.success:
        print("✅ Sync completed successfully")
        print("=" * 70)
        print()
        for stat in result.stats:
            print(f"📊 {stat.entity_type.upper()}:")
            print(f"   Created: {stat.created}")
            print(f"   Updated: {stat.updated}")
            print(f"   Skipped: {stat.skipped}")
            print(f"   Total: {stat.total}")
            if stat.errors:
                print(f"   Errors: {stat.errors}")
            print()
        return 0
    else:
        print(f"❌ Sync failed: {result.error_message}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
