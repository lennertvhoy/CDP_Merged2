#!/usr/bin/env python3
"""
Exact Online → PostgreSQL Sync Pipeline

Syncs accounts (GL), customers, invoices, invoice lines, and transactions from Exact Online to PostgreSQL.
Supports incremental sync with cursor tracking and KBO/VAT company matching.

Usage:
    # Full sync (all entities)
    poetry run python scripts/sync_exact_to_postgres.py --full
    
    # Sync specific entities
    poetry run python scripts/sync_exact_to_postgres.py --entities accounts,customers,invoices
    
    # Incremental sync (uses last cursor)
    poetry run python scripts/sync_exact_to_postgres.py
    
    # With custom database URL
    DATABASE_URL=postgresql://... poetry run python scripts/sync_exact_to_postgres.py

Environment:
    Requires .env.exact with valid OAuth credentials
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
from src.services.exact import ExactClient, load_exact_env_file, ExactCredentials

logger = get_logger(__name__)

# Configuration
DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://cdpadmin:cdpadmin123@localhost:5432/cdp?sslmode=disable"
)
BATCH_SIZE = 100
PAGE_SIZE = 100


def parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime string to naive UTC datetime object."""
    if not value:
        return None
    try:
        dt = date_parser.parse(value)
        if dt.tzinfo:
            from datetime import timezone
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def parse_exact_date(value: str | None) -> datetime | None:
    """Parse Exact Online date format (\"/Date(timestamp)/\") to datetime."""
    if not value:
        return None
    try:
        match = re.match(r"/Date\((\d+)\)/", value)
        if match:
            timestamp_ms = int(match.group(1))
            return datetime.utcfromtimestamp(timestamp_ms / 1000)
        return parse_datetime(value)
    except Exception:
        return None


def extract_guid(value: str | None) -> str | None:
    """Extract GUID from Exact's format."""
    if not value:
        return None
    match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(value))
    return match.group(1).lower() if match else None


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


class ExactOnlineSync:
    """Sync Exact Online data to PostgreSQL."""
    
    def __init__(
        self,
        database_url: str,
        client: ExactClient | None = None,
    ) -> None:
        self.database_url = database_url
        self.client = client
        self.pool: asyncpg.Pool | None = None
        
    async def initialize(self) -> None:
        """Initialize database pool and ensure client is ready."""
        self.pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
        
        if self.client is None:
            load_exact_env_file()
            self.client = ExactClient.from_env()
            
        logger.info("exact_sync_initialized", division=self.client.division_id)
        
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
                WHERE source_system = 'exact' AND entity_type = $1
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
                VALUES ('exact', $1, $2, $3, $4, CURRENT_TIMESTAMP, $5, $6)
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
        vat = vat.upper().replace(" ", "").replace(".", "").replace("-", "")
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

    async def sync_accounts(self, full_sync: bool = False) -> SyncStats:
        """Sync GL accounts from Exact to PostgreSQL."""
        stats = SyncStats("accounts")
        last_modified = None if full_sync else await self.get_sync_cursor("accounts")
        
        logger.info("syncing_accounts", full_sync=full_sync, cursor=last_modified)
        
        filter_query = None
        if last_modified and not full_sync:
            filter_query = f"Modified gt datetime'{last_modified}'"
        
        total_processed = 0
        last_modified_date = last_modified or ""
        
        try:
            for record in self.client.get_all_records(
                "financial/GLAccounts",
                select="ID,Code,Name,Type,Description,Active,TaxCode,Classification",
                filter_query=filter_query,
                orderby="Code",
                top=PAGE_SIZE,
            ):
                source_id = extract_guid(record.get("ID"))
                if not source_id:
                    stats.skipped += 1
                    continue
                
                account_code = record.get("Code", "")
                modified = record.get("Modified", "")
                
                async with self.pool.acquire() as conn:
                    result = await conn.execute(
                        """
                        INSERT INTO exact_accounts (
                            source_system, source_record_id, account_code, account_name,
                            account_type, account_classification, is_active, is_tax_relevant,
                            tax_code, reporting_code, reporting_description,
                            source_created_at, source_updated_at, last_sync_at, raw_data
                        ) VALUES (
                            'exact', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, CURRENT_TIMESTAMP, $13
                        )
                        ON CONFLICT (source_system, source_record_id) 
                        DO UPDATE SET
                            account_code = EXCLUDED.account_code,
                            account_name = EXCLUDED.account_name,
                            account_type = EXCLUDED.account_type,
                            account_classification = EXCLUDED.account_classification,
                            is_active = EXCLUDED.is_active,
                            tax_code = EXCLUDED.tax_code,
                            source_updated_at = EXCLUDED.source_updated_at,
                            last_sync_at = CURRENT_TIMESTAMP,
                            sync_version = exact_accounts.sync_version + 1,
                            raw_data = EXCLUDED.raw_data
                        """,
                        source_id,
                        account_code,
                        record.get("Name", ""),
                        record.get("Type", ""),
                        record.get("Classification", ""),
                        record.get("Active", True),
                        record.get("TaxCode") is not None,
                        record.get("TaxCode", ""),
                        record.get("ReportingCode", ""),
                        record.get("Description", ""),
                        parse_exact_date(record.get("Created")),
                        parse_exact_date(modified),
                        json.dumps(record)
                    )
                    
                    if result and "UPDATE" in result:
                        stats.updated += 1
                    else:
                        stats.created += 1
                
                if modified and modified > last_modified_date:
                    last_modified_date = modified
                    
                total_processed += 1
                
                if total_processed % 100 == 0:
                    logger.info("accounts_progress", processed=total_processed)
                    
        except Exception as e:
            logger.error("account_sync_error", error=str(e))
            stats.errors += 1
            await self.update_sync_cursor(
                "accounts", last_modified_date, "timestamp", total_processed, "error", str(e)
            )
            raise
            
        if last_modified_date:
            await self.update_sync_cursor("accounts", last_modified_date, "timestamp", total_processed, "idle")
            
        logger.info("accounts_sync_complete", stats=stats)
        return stats

    async def sync_customers(self, full_sync: bool = False) -> SyncStats:
        """Sync customers from Exact to PostgreSQL."""
        stats = SyncStats("customers")
        last_modified = None if full_sync else await self.get_sync_cursor("customers")
        
        logger.info("syncing_customers", full_sync=full_sync, cursor=last_modified)
        
        filter_query = "Type eq 'C'"
        if last_modified and not full_sync:
            filter_query = f"{filter_query} and Modified gt datetime'{last_modified}'"
        
        total_processed = 0
        last_modified_date = last_modified or ""
        
        try:
            for record in self.client.get_all_records(
                "crm/Accounts",
                select="ID,Name,AddressLine1,AddressLine2,AddressLine3,Postcode,City,Country,Email,Phone,Website,VATNumber,ChamberOfCommerce,Code,CreditLine,DiscountPercentage,PaymentTermsDays,IsSalesBlocked,Status,AccountManager,Classification1,Classification2,Modified,Created",
                filter_query=filter_query,
                orderby="Name",
                top=PAGE_SIZE,
            ):
                source_id = extract_guid(record.get("ID"))
                if not source_id:
                    stats.skipped += 1
                    continue
                
                company_name = record.get("Name", "")
                vat_number = self.normalize_vat(record.get("VATNumber"))
                kbo_number = record.get("ChamberOfCommerce")
                modified = record.get("Modified", "")
                
                matched_kbo, org_uid = await self.find_kbo_match(vat_number, company_name)
                
                if not matched_kbo and kbo_number:
                    matched_kbo = kbo_number
                
                email = record.get("Email", "")
                
                async with self.pool.acquire() as conn:
                    result = await conn.execute(
                        """
                        INSERT INTO exact_customers (
                            source_system, source_record_id, kbo_number, vat_number, organization_uid,
                            company_name, legal_name, 
                            street_address, city, postal_code, country,
                            main_email, email_domain, main_phone, website_url,
                            credit_line, discount_percentage, payment_terms_days,
                            vat_number_exact, status, is_blocked,
                            customer_type, account_manager,
                            source_created_at, source_updated_at, last_sync_at, raw_data
                        ) VALUES (
                            'exact', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, CURRENT_TIMESTAMP, $25
                        )
                        ON CONFLICT (source_system, source_record_id) 
                        DO UPDATE SET
                            kbo_number = COALESCE(EXCLUDED.kbo_number, exact_customers.kbo_number),
                            vat_number = COALESCE(EXCLUDED.vat_number, exact_customers.vat_number),
                            organization_uid = COALESCE(EXCLUDED.organization_uid, exact_customers.organization_uid),
                            company_name = EXCLUDED.company_name,
                            street_address = EXCLUDED.street_address,
                            city = EXCLUDED.city,
                            postal_code = EXCLUDED.postal_code,
                            main_email = EXCLUDED.main_email,
                            email_domain = EXCLUDED.email_domain,
                            main_phone = EXCLUDED.main_phone,
                            website_url = EXCLUDED.website_url,
                            credit_line = EXCLUDED.credit_line,
                            status = EXCLUDED.status,
                            is_blocked = EXCLUDED.is_blocked,
                            account_manager = EXCLUDED.account_manager,
                            source_updated_at = EXCLUDED.source_updated_at,
                            last_sync_at = CURRENT_TIMESTAMP,
                            sync_version = exact_customers.sync_version + 1,
                            raw_data = EXCLUDED.raw_data
                        """,
                        source_id,
                        matched_kbo,
                        vat_number,
                        org_uid,
                        company_name,
                        company_name,
                        " ".join(filter(None, [
                            record.get("AddressLine1", ""),
                            record.get("AddressLine2", ""),
                            record.get("AddressLine3", "")
                        ])),
                        record.get("City", ""),
                        record.get("Postcode", ""),
                        record.get("Country", "BE"),
                        email,
                        self.extract_email_domain(email),
                        record.get("Phone", ""),
                        record.get("Website", ""),
                        record.get("CreditLine"),
                        record.get("DiscountPercentage"),
                        record.get("PaymentTermsDays"),
                        record.get("VATNumber", ""),
                        record.get("Status", "C"),
                        record.get("IsSalesBlocked", False),
                        record.get("Classification1", ""),
                        record.get("AccountManager", {}).get("FullName") if isinstance(record.get("AccountManager"), dict) else "",
                        parse_exact_date(record.get("Created")),
                        parse_exact_date(modified),
                        json.dumps(record)
                    )
                    
                    if result and "UPDATE" in result:
                        stats.updated += 1
                    else:
                        stats.created += 1
                
                if modified and modified > last_modified_date:
                    last_modified_date = modified
                    
                total_processed += 1
                
                if total_processed % 100 == 0:
                    logger.info("customers_progress", processed=total_processed)
                    
        except Exception as e:
            logger.error("customer_sync_error", error=str(e))
            stats.errors += 1
            await self.update_sync_cursor(
                "customers", last_modified_date, "timestamp", total_processed, "error", str(e)
            )
            raise
            
        if last_modified_date:
            await self.update_sync_cursor("customers", last_modified_date, "timestamp", total_processed, "idle")
            
        logger.info("customers_sync_complete", stats=stats)
        return stats

    async def sync_invoices(self, full_sync: bool = False) -> SyncStats:
        """Sync sales invoices from Exact to PostgreSQL."""
        stats = SyncStats("invoices")
        last_modified = None if full_sync else await self.get_sync_cursor("invoices")
        
        logger.info("syncing_invoices", full_sync=full_sync, cursor=last_modified)
        
        filter_query = None
        if last_modified and not full_sync:
            filter_query = f"Modified gt datetime'{last_modified}'"
        
        total_processed = 0
        last_modified_date = last_modified or ""
        
        async with self.pool.acquire() as conn:
            customer_rows = await conn.fetch(
                "SELECT source_record_id, id FROM exact_customers WHERE source_system = 'exact'"
            )
            customer_id_map = {row["source_record_id"]: row["id"] for row in customer_rows}
        
        try:
            for record in self.client.get_all_records(
                "salesinvoice/SalesInvoices",
                select="ID,InvoiceNumber,Type,Description,AmountDC,VATAmountDC,AmountFC,VATAmountFC,Currency,ExchangeRate,InvoiceDate,DueDate,DeliveryDate,PaymentDate,Status,PaymentStatus,AmountPaid,AmountOpen,DaysOverdue,PaymentConditionDescription,OrderedBy,Customer,JournalCode,DocumentNumber,Modified,Created",
                filter_query=filter_query,
                orderby="InvoiceDate desc",
                top=PAGE_SIZE,
            ):
                source_id = extract_guid(record.get("ID"))
                if not source_id:
                    stats.skipped += 1
                    continue
                
                invoice_number = record.get("InvoiceNumber", "")
                modified = record.get("Modified", "")
                
                customer_data = record.get("Customer", {})
                exact_customer_id = extract_guid(customer_data.get("ID")) if isinstance(customer_data, dict) else None
                crm_company_id = customer_id_map.get(exact_customer_id) if exact_customer_id else None
                
                amount_excl = record.get("AmountDC", 0)
                vat_amount = record.get("VATAmountDC", 0)
                amount_incl = amount_excl + vat_amount
                
                async with self.pool.acquire() as conn:
                    result = await conn.execute(
                        """
                        INSERT INTO exact_sales_invoices (
                            source_system, source_record_id, invoice_number,
                            exact_customer_id, crm_company_id,
                            invoice_type, invoice_description,
                            total_amount_excl, total_vat_amount, total_amount_incl,
                            currency, exchange_rate,
                            invoice_date, due_date, delivery_date, payment_date,
                            invoice_status, payment_status,
                            amount_paid, amount_open, days_overdue,
                            payment_condition, document_number, journal_code,
                            source_created_at, source_updated_at, last_sync_at, raw_data
                        ) VALUES (
                            'exact', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, CURRENT_TIMESTAMP, $26
                        )
                        ON CONFLICT (source_system, source_record_id) 
                        DO UPDATE SET
                            exact_customer_id = COALESCE(EXCLUDED.exact_customer_id, exact_sales_invoices.exact_customer_id),
                            crm_company_id = COALESCE(EXCLUDED.crm_company_id, exact_sales_invoices.crm_company_id),
                            invoice_status = EXCLUDED.invoice_status,
                            payment_status = EXCLUDED.payment_status,
                            amount_paid = EXCLUDED.amount_paid,
                            amount_open = EXCLUDED.amount_open,
                            days_overdue = EXCLUDED.days_overdue,
                            payment_date = EXCLUDED.payment_date,
                            source_updated_at = EXCLUDED.source_updated_at,
                            last_sync_at = CURRENT_TIMESTAMP,
                            sync_version = exact_sales_invoices.sync_version + 1,
                            raw_data = EXCLUDED.raw_data
                        """,
                        source_id,
                        invoice_number,
                        exact_customer_id,
                        crm_company_id,
                        record.get("Type", ""),
                        record.get("Description", ""),
                        amount_excl,
                        vat_amount,
                        amount_incl,
                        record.get("Currency", "EUR"),
                        record.get("ExchangeRate", 1.0),
                        parse_exact_date(record.get("InvoiceDate")),
                        parse_exact_date(record.get("DueDate")),
                        parse_exact_date(record.get("DeliveryDate")),
                        parse_exact_date(record.get("PaymentDate")),
                        record.get("Status", ""),
                        record.get("PaymentStatus", ""),
                        record.get("AmountPaid", 0),
                        record.get("AmountOpen", 0),
                        record.get("DaysOverdue", 0),
                        record.get("PaymentConditionDescription", ""),
                        record.get("DocumentNumber", ""),
                        record.get("JournalCode", ""),
                        parse_exact_date(record.get("Created")),
                        parse_exact_date(modified),
                        json.dumps(record)
                    )
                    
                    if result and "UPDATE" in result:
                        stats.updated += 1
                    else:
                        stats.created += 1
                
                if modified and modified > last_modified_date:
                    last_modified_date = modified
                    
                total_processed += 1
                
                if total_processed % 100 == 0:
                    logger.info("invoices_progress", processed=total_processed)
                    
        except Exception as e:
            logger.error("invoice_sync_error", error=str(e))
            stats.errors += 1
            await self.update_sync_cursor(
                "invoices", last_modified_date, "timestamp", total_processed, "error", str(e)
            )
            raise
            
        if last_modified_date:
            await self.update_sync_cursor("invoices", last_modified_date, "timestamp", total_processed, "idle")
            
        logger.info("invoices_sync_complete", stats=stats)
        return stats

    async def sync_transactions(self, full_sync: bool = False) -> SyncStats:
        """Sync general ledger transactions from Exact to PostgreSQL."""
        stats = SyncStats("transactions")
        last_entry = None if full_sync else await self.get_sync_cursor("transactions")
        
        logger.info("syncing_transactions", full_sync=full_sync, cursor=last_entry)
        
        filter_query = None
        if last_entry and not full_sync:
            filter_query = f"EntryNumber gt {last_entry}"
        
        total_processed = 0
        last_entry_number = int(last_entry) if last_entry and last_entry.isdigit() else 0
        
        async with self.pool.acquire() as conn:
            customer_rows = await conn.fetch(
                "SELECT source_record_id, id FROM exact_customers WHERE source_system = 'exact'"
            )
            customer_id_map = {row["source_record_id"]: row["id"] for row in customer_rows}
        
        try:
            for record in self.client.get_all_records(
                "financialtransaction/Transactions",
                select="ID,EntryNumber,Date,FinancialYear,FinancialPeriod,GLAccount,Account,Description,Document,AmountDC,AmountFC,Currency,JournalCode,JournalDescription,Reference,InvoiceNumber,CostCenter,CostUnit,Project,Modified,Created",
                filter_query=filter_query,
                orderby="EntryNumber",
                top=PAGE_SIZE,
            ):
                source_id = extract_guid(record.get("ID"))
                if not source_id:
                    stats.skipped += 1
                    continue
                
                entry_number = record.get("EntryNumber", 0)
                
                gl_account_data = record.get("GLAccount", {})
                exact_gl_account_id = extract_guid(gl_account_data.get("ID")) if isinstance(gl_account_data, dict) else None
                
                account_data = record.get("Account", {})
                exact_customer_id = extract_guid(account_data.get("ID")) if isinstance(account_data, dict) else None
                crm_company_id = customer_id_map.get(exact_customer_id) if exact_customer_id else None
                
                async with self.pool.acquire() as conn:
                    result = await conn.execute(
                        """
                        INSERT INTO exact_transactions (
                            source_system, source_record_id, entry_number,
                            transaction_date, financial_year, financial_period,
                            exact_gl_account_id, exact_gl_account_code,
                            exact_customer_id, crm_company_id,
                            transaction_type, transaction_description, document_number,
                            amount, amount_dc, currency,
                            reference_number, invoice_number,
                            journal_code, journal_description,
                            cost_center, cost_unit, project_code,
                            source_created_at, source_updated_at, last_sync_at, raw_data
                        ) VALUES (
                            'exact', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, CURRENT_TIMESTAMP, $25
                        )
                        ON CONFLICT (source_system, source_record_id) 
                        DO UPDATE SET
                            exact_gl_account_id = COALESCE(EXCLUDED.exact_gl_account_id, exact_transactions.exact_gl_account_id),
                            exact_customer_id = COALESCE(EXCLUDED.exact_customer_id, exact_transactions.exact_customer_id),
                            crm_company_id = COALESCE(EXCLUDED.crm_company_id, exact_transactions.crm_company_id),
                            amount = EXCLUDED.amount,
                            amount_dc = EXCLUDED.amount_dc,
                            source_updated_at = EXCLUDED.source_updated_at,
                            last_sync_at = CURRENT_TIMESTAMP,
                            sync_version = exact_transactions.sync_version + 1,
                            raw_data = EXCLUDED.raw_data
                        """,
                        source_id,
                        entry_number,
                        parse_exact_date(record.get("Date")),
                        record.get("FinancialYear"),
                        record.get("FinancialPeriod"),
                        exact_gl_account_id,
                        gl_account_data.get("Code") if isinstance(gl_account_data, dict) else None,
                        exact_customer_id,
                        crm_company_id,
                        record.get("Type", ""),
                        record.get("Description", ""),
                        record.get("Document", ""),
                        record.get("AmountDC", 0),
                        record.get("AmountFC", 0),
                        record.get("Currency", "EUR"),
                        record.get("Reference", ""),
                        record.get("InvoiceNumber", ""),
                        record.get("JournalCode", ""),
                        record.get("JournalDescription", ""),
                        record.get("CostCenter", ""),
                        record.get("CostUnit", ""),
                        record.get("Project", ""),
                        parse_exact_date(record.get("Created")),
                        parse_exact_date(record.get("Modified")),
                        json.dumps(record)
                    )
                    
                    if result and "UPDATE" in result:
                        stats.updated += 1
                    else:
                        stats.created += 1
                
                if entry_number and entry_number > last_entry_number:
                    last_entry_number = entry_number
                    
                total_processed += 1
                
                if total_processed % 100 == 0:
                    logger.info("transactions_progress", processed=total_processed)
                    
        except Exception as e:
            logger.error("transaction_sync_error", error=str(e))
            stats.errors += 1
            await self.update_sync_cursor(
                "transactions", str(last_entry_number), "entry_number", total_processed, "error", str(e)
            )
            raise
            
        if last_entry_number > 0:
            await self.update_sync_cursor("transactions", str(last_entry_number), "entry_number", total_processed, "idle")
            
        logger.info("transactions_sync_complete", stats=stats)
        return stats
        
    async def run_sync(self, entities: list[str], full_sync: bool = False) -> SyncResult:
        """Run the complete sync process."""
        result = SyncResult(success=True)
        
        try:
            await self.initialize()
            
            if "accounts" in entities:
                stats = await self.sync_accounts(full_sync=full_sync)
                result.stats.append(stats)
                
            if "customers" in entities:
                stats = await self.sync_customers(full_sync=full_sync)
                result.stats.append(stats)
                
            if "invoices" in entities:
                stats = await self.sync_invoices(full_sync=full_sync)
                result.stats.append(stats)
                
            if "transactions" in entities:
                stats = await self.sync_transactions(full_sync=full_sync)
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
        description="Sync Exact Online data to PostgreSQL"
    )
    parser.add_argument(
        "--entities",
        type=str,
        default="accounts,customers,invoices,transactions",
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
    valid_entities = {"accounts", "customers", "invoices", "transactions"}
    entities = [e for e in entities if e in valid_entities]
    
    if not entities:
        print("No valid entities specified")
        return 1
        
    if not ExactClient.is_configured():
        load_exact_env_file()
        if not ExactClient.is_configured():
            print("=" * 70)
            print("Exact Online Not Configured")
            print("=" * 70)
            print()
            print("Please configure your Exact Online credentials in .env.exact:")
            print()
            print("  EXACT_CLIENT_ID=your_client_id")
            print("  EXACT_CLIENT_SECRET=your_client_secret")
            print("  EXACT_REFRESH_TOKEN=your_refresh_token")
            print("  EXACT_REDIRECT_URI=https://cdp.it1.be/callback/exact")
            print("  EXACT_BASE_URL=https://start.exactonline.be")
            print()
            return 1
        
    print("=" * 70)
    print("Exact Online Sync")
    print("=" * 70)
    print(f"Entities: {', '.join(entities)}")
    print(f"Mode: {'FULL' if args.full else 'INCREMENTAL'}")
    print(f"Database: {args.database_url.split('@')[-1]}")
    print("=" * 70)
    print()
    
    sync = ExactOnlineSync(database_url=args.database_url)
    result = await sync.run_sync(entities, full_sync=args.full)
    
    print()
    print("=" * 70)
    if result.success:
        print("Sync completed successfully")
        print("=" * 70)
        print()
        for stat in result.stats:
            print(f"{stat.entity_type.upper()}:")
            print(f"   Created: {stat.created}")
            print(f"   Updated: {stat.updated}")
            print(f"   Skipped: {stat.skipped}")
            print(f"   Total: {stat.total}")
            if stat.errors:
                print(f"   Errors: {stat.errors}")
            print()
        return 0
    else:
        print(f"Sync failed: {result.error_message}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
