#!/usr/bin/env python3
"""
Populate Hyperrealistic Demo Data for CDP Illustrated Guide

Creates 50+ realistic Belgian companies across:
- Teamleader (CRM) - with contacts, deals, activities
- Exact Online (Financial) - with invoices, GL accounts
- KBO linkage via VAT numbers

This provides credible data for:
- 360° Golden Record demonstrations
- Cross-sell/up-sell scenarios
- Segment activation demos
- ROI tracking examples

Usage:
    uv run python scripts/populate_hyperrealistic_demo_data.py --dry-run  # Preview
    uv run python scripts/populate_hyperrealistic_demo_data.py           # Execute
    uv run python scripts/populate_hyperrealistic_demo_data.py --reset   # Clear first
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import asyncpg

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.core.logger import get_logger
from src.services.teamleader import TeamleaderClient, load_teamleader_env_file

logger = get_logger(__name__)

# Hyperrealistic Belgian company data
HYPERREALISTIC_COMPANIES = [
    # IT Services & Software
    {"name": "TechVision Solutions BV", "vat": "BE0475123456", "city": "Brussels", "sector": "IT Services", "employees": 45, "revenue": 2500000},
    {"name": "ByteLogic Computing NV", "vat": "BE0456234567", "city": "Antwerp", "sector": "Software Development", "employees": 28, "revenue": 1800000},
    {"name": "CloudSystems Belgium BV", "vat": "BE0467345678", "city": "Gent", "sector": "Cloud Services", "employees": 62, "revenue": 4200000},
    {"name": "DataFlow Analytics NV", "vat": "BE0478456789", "city": "Leuven", "sector": "Data Analytics", "employees": 35, "revenue": 2100000},
    {"name": "SecureIT Partners BV", "vat": "BE0489567890", "city": "Brussels", "sector": "Cybersecurity", "employees": 52, "revenue": 3800000},
    
    # Legal & Accounting
    {"name": "Advocatenkantoor De Vries & Partners BV", "vat": "BE0401234567", "city": "Brussels", "sector": "Legal Services", "employees": 18, "revenue": 3200000},
    {"name": "Fiduciaire Janssens NV", "vat": "BE0412345678", "city": "Antwerp", "sector": "Accounting", "employees": 25, "revenue": 1900000},
    {"name": "LexConsult Brussels BV", "vat": "BE0423456789", "city": "Brussels", "sector": "Legal Services", "employees": 42, "revenue": 5500000},
    {"name": "Accountancy Plus Gent NV", "vat": "BE0434567890", "city": "Gent", "sector": "Accounting", "employees": 15, "revenue": 1200000},
    {"name": "Notariaat Peeters & Zn BV", "vat": "BE0445678901", "city": "Leuven", "sector": "Notary", "employees": 8, "revenue": 950000},
    
    # Construction & Engineering
    {"name": "Bouwbedrijf Van den Berg NV", "vat": "BE0501234567", "city": "Antwerp", "sector": "Construction", "employees": 85, "revenue": 8500000},
    {"name": "Ingenieursbureau Delta BV", "vat": "BE0512345678", "city": "Brussels", "sector": "Engineering", "employees": 38, "revenue": 4800000},
    {"name": "Constructie Maes NV", "vat": "BE0523456789", "city": "Gent", "sector": "Construction", "employees": 65, "revenue": 7200000},
    {"name": "Architectuur Studio Plus BV", "vat": "BE0534567890", "city": "Brussels", "sector": "Architecture", "employees": 22, "revenue": 2800000},
    {"name": "Technische Installaties Peters NV", "vat": "BE0545678901", "city": "Leuven", "sector": "Technical Services", "employees": 48, "revenue": 5600000},
    
    # Healthcare & Pharma
    {"name": "MediCare Plus BV", "vat": "BE0601234567", "city": "Brussels", "sector": "Healthcare", "employees": 120, "revenue": 12500000},
    {"name": "PharmaBel NV", "vat": "BE0612345678", "city": "Antwerp", "sector": "Pharmaceuticals", "employees": 95, "revenue": 15000000},
    {"name": "Zorggroep Vlaanderen BV", "vat": "BE0623456789", "city": "Gent", "sector": "Elderly Care", "employees": 250, "revenue": 22000000},
    {"name": "MediTech Solutions NV", "vat": "BE0634567890", "city": "Leuven", "sector": "Medical Devices", "employees": 55, "revenue": 6800000},
    {"name": "Apotheekketoots Centraal BV", "vat": "BE0645678901", "city": "Brussels", "sector": "Pharmacy", "employees": 35, "revenue": 4200000},
    
    # Retail & E-commerce
    {"name": "Fashion Forward Belgium NV", "vat": "BE0701234567", "city": "Antwerp", "sector": "Fashion Retail", "employees": 75, "revenue": 9800000},
    {"name": "ElectroWorld Plus BV", "vat": "BE0712345678", "city": "Brussels", "sector": "Electronics Retail", "employees": 45, "revenue": 5200000},
    {"name": "BioMarkt Gent BV", "vat": "BE0723456789", "city": "Gent", "sector": "Organic Food", "employees": 28, "revenue": 3100000},
    {"name": "Online Retail Solutions NV", "vat": "BE0734567890", "city": "Leuven", "sector": "E-commerce", "employees": 42, "revenue": 7800000},
    {"name": "Home & Living Stores BV", "vat": "BE0745678901", "city": "Brussels", "sector": "Home Goods", "employees": 58, "revenue": 6400000},
    
    # Manufacturing
    {"name": "MetalWorks Belgium NV", "vat": "BE0801234567", "city": "Antwerp", "sector": "Metal Manufacturing", "employees": 145, "revenue": 18000000},
    {"name": "Plastics Industries BV", "vat": "BE0812345678", "city": "Gent", "sector": "Plastics", "employees": 88, "revenue": 12000000},
    {"name": "Food Processing Bel NV", "vat": "BE0823456789", "city": "Leuven", "sector": "Food Production", "employees": 165, "revenue": 25000000},
    {"name": "Textile Creations BV", "vat": "BE0834567890", "city": "Brussels", "sector": "Textiles", "employees": 72, "revenue": 8900000},
    {"name": "Chemical Solutions NV", "vat": "BE0845678901", "city": "Antwerp", "sector": "Chemicals", "employees": 55, "revenue": 11000000},
    
    # Logistics & Transport
    {"name": "Fast Logistics Belgium BV", "vat": "BE0901234567", "city": "Antwerp", "sector": "Logistics", "employees": 210, "revenue": 28000000},
    {"name": "TransPort NV", "vat": "BE0912345678", "city": "Gent", "sector": "Transport", "employees": 125, "revenue": 16500000},
    {"name": "EuroShipping Plus BV", "vat": "BE0923456789", "city": "Brussels", "sector": "Shipping", "employees": 85, "revenue": 13500000},
    {"name": "LogiChain Solutions NV", "vat": "BE0934567890", "city": "Leuven", "sector": "Supply Chain", "employees": 48, "revenue": 7200000},
    {"name": "Green Transport BV", "vat": "BE0945678901", "city": "Brussels", "sector": "Sustainable Transport", "employees": 38, "revenue": 5400000},
    
    # Education & Training
    {"name": "EduLearn Belgium NV", "vat": "BE1001234567", "city": "Brussels", "sector": "Education", "employees": 65, "revenue": 6200000},
    {"name": "Training Plus BV", "vat": "BE1012345678", "city": "Antwerp", "sector": "Corporate Training", "employees": 32, "revenue": 3800000},
    {"name": "TechAcademy Gent NV", "vat": "BE1023456789", "city": "Gent", "sector": "IT Training", "employees": 28, "revenue": 3200000},
    {"name": "Language Lab BV", "vat": "BE1034567890", "city": "Leuven", "sector": "Language Training", "employees": 22, "revenue": 2400000},
    {"name": "Business School Plus NV", "vat": "BE1045678901", "city": "Brussels", "sector": "Business Education", "employees": 45, "revenue": 7500000},
    
    # Hospitality & Tourism
    {"name": "Hotel Group Belgium NV", "vat": "BE1101234567", "city": "Brussels", "sector": "Hotels", "employees": 185, "revenue": 22000000},
    {"name": "Restaurant Concepts BV", "vat": "BE1112345678", "city": "Antwerp", "sector": "Restaurants", "employees": 95, "revenue": 9800000},
    {"name": "Event Masters NV", "vat": "BE1123456789", "city": "Gent", "sector": "Event Management", "employees": 42, "revenue": 5600000},
    {"name": "Travel Experts BV", "vat": "BE1134567890", "city": "Brussels", "sector": "Travel Agency", "employees": 28, "revenue": 4200000},
    {"name": "Catering Delights NV", "vat": "BE1145678901", "city": "Leuven", "sector": "Catering", "employees": 55, "revenue": 4800000},
    
    # Real Estate
    {"name": "ImmoTrust Belgium NV", "vat": "BE1201234567", "city": "Brussels", "sector": "Real Estate", "employees": 38, "revenue": 8500000},
    {"name": "Property Partners BV", "vat": "BE1212345678", "city": "Antwerp", "sector": "Property Management", "employees": 25, "revenue": 5200000},
    {"name": "Commercial Real Estate NV", "vat": "BE1223456789", "city": "Gent", "sector": "Commercial Property", "employees": 32, "revenue": 7800000},
    {"name": "Housing Solutions BV", "vat": "BE1234567890", "city": "Leuven", "sector": "Residential Real Estate", "employees": 18, "revenue": 3600000},
    {"name": "InvestImmo NV", "vat": "BE1245678901", "city": "Brussels", "sector": "Real Estate Investment", "employees": 22, "revenue": 12000000},
]

# Decision makers per company
DECISION_MAKERS = [
    ("David", "Mertens", "CTO", "david.mertens@{}"),
    ("Sarah", "Peeters", "CEO", "sarah.peeters@{}"),
    ("Marc", "Janssens", "IT Director", "marc.janssens@{}"),
    ("Emma", "Maes", "CFO", "emma.maes@{}"),
    ("Lucas", "Jacobs", "Head of Operations", "lucas.jacobs@{}"),
    ("Sofie", "Vermeulen", "Marketing Director", "sofie.vermeulen@{}"),
    ("Thomas", "Willems", "Sales Director", "thomas.willems@{}"),
    ("Laura", "Claes", "Procurement Manager", "laura.claes@{}"),
    ("Peter", "Goossens", "HR Director", "peter.goossens@{}"),
    ("Ann", "De Smet", "Finance Manager", "ann.desmet@{}"),
]

# Deal types and values
DEAL_TYPES = [
    ("MS365 Migration Project", 15000, 45000),
    ("Managed Services Contract", 5000, 15000),
    ("Cloud Infrastructure Setup", 25000, 75000),
    ("Cybersecurity Assessment", 8000, 20000),
    ("Network Modernization", 20000, 60000),
    ("Data Analytics Platform", 30000, 90000),
    ("Software Development", 40000, 120000),
    ("IT Consulting Retainer", 3000, 10000),
    ("Backup & Recovery Solution", 10000, 30000),
    ("VoIP Phone System", 8000, 25000),
]

# Activity types
ACTIVITY_TYPES = ["call", "meeting", "task"]
ACTIVITY_SUBJECTS = [
    "Contract renewal discussion",
    "Quarterly business review",
    "Project kickoff meeting",
    "Technical requirements review",
    "Follow-up on proposal",
    "Demo presentation",
    "Support ticket escalation",
    "Strategic planning session",
    "Training session planning",
    "Budget approval discussion",
]


@dataclass
class CompanyData:
    """Complete company data for all systems."""
    name: str
    vat: str
    city: str
    sector: str
    employees: int
    revenue: int
    contacts: list[dict] = field(default_factory=list)
    deals: list[dict] = field(default_factory=list)
    activities: list[dict] = field(default_factory=list)
    invoices: list[dict] = field(default_factory=list)


def generate_company_data(company_def: dict) -> CompanyData:
    """Generate complete realistic data for a company."""
    company = CompanyData(
        name=company_def["name"],
        vat=company_def["vat"],
        city=company_def["city"],
        sector=company_def["sector"],
        employees=company_def["employees"],
        revenue=company_def["revenue"],
    )
    
    # Generate domain from company name
    domain_base = company.name.lower().replace(" ", "").replace("&", "and").replace(".", "").replace("-", "")
    if "bv" in domain_base:
        domain_base = domain_base.replace("bv", "").rstrip(".")
    if "nv" in domain_base:
        domain_base = domain_base.replace("nv", "").rstrip(".")
    domain = f"{domain_base}.be"
    
    # Generate 1-3 contacts
    num_contacts = random.randint(1, 3)
    used_makers = set()
    for i in range(num_contacts):
        # Pick unique decision maker
        available = [dm for dm in DECISION_MAKERS if dm[2] not in used_makers]
        if not available:
            break
        dm = random.choice(available)
        used_makers.add(dm[2])
        
        first, last, title, email_template = dm
        email = email_template.format(domain)
        
        company.contacts.append({
            "first_name": first,
            "last_name": last,
            "full_name": f"{first} {last}",
            "email": email,
            "phone": f"+32 {random.choice(['2', '3', '9'])} {random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}",
            "job_title": title,
            "is_decision_maker": True,
        })
    
    # Generate 0-3 deals
    num_deals = random.randint(0, 3)
    for i in range(num_deals):
        deal_type = random.choice(DEAL_TYPES)
        base_value = random.randint(deal_type[1], deal_type[2])
        
        # Random close date in past or future
        days_offset = random.randint(-180, 180)
        close_date = datetime.now() + timedelta(days=days_offset)
        
        # Determine status based on close date
        if days_offset < -30:
            status = random.choice(["won", "lost"])
            probability = 100 if status == "won" else 0
        elif days_offset < 0:
            status = "won"
            probability = 100
        else:
            status = "open"
            probability = random.randint(30, 80)
        
        company.deals.append({
            "title": deal_type[0],
            "value": base_value,
            "status": status,
            "probability": probability,
            "expected_close_date": close_date.strftime("%Y-%m-%d") if status == "open" else None,
            "actual_close_date": close_date.strftime("%Y-%m-%d") if status != "open" else None,
        })
    
    # Generate 2-8 activities
    num_activities = random.randint(2, 8)
    for i in range(num_activities):
        days_ago = random.randint(1, 90)
        activity_date = datetime.now() - timedelta(days=days_ago)
        
        company.activities.append({
            "type": random.choice(ACTIVITY_TYPES),
            "subject": random.choice(ACTIVITY_SUBJECTS),
            "description": f"Detailed discussion about {company.sector.lower()} requirements and next steps.",
            "date": activity_date.strftime("%Y-%m-%d"),
            "completed": random.choice([True, True, True, False]),  # 75% completed
        })
    
    # Generate 3-12 invoices
    num_invoices = random.randint(3, 12)
    for i in range(num_invoices):
        # Invoice over past 2 years
        days_ago = random.randint(1, 730)
        invoice_date = datetime.now() - timedelta(days=days_ago)
        
        # Amount based on company revenue
        base_amount = company.revenue / 12  # Monthly-ish
        variance = random.uniform(0.3, 2.0)
        amount = round(base_amount * variance, 2)
        
        # Paid if older than 60 days
        is_paid = days_ago > 60 or random.choice([True, True, False])
        
        company.invoices.append({
            "invoice_number": f"INV-{invoice_date.year}-{random.randint(1000, 9999)}",
            "amount": amount,
            "date": invoice_date.strftime("%Y-%m-%d"),
            "due_date": (invoice_date + timedelta(days=30)).strftime("%Y-%m-%d"),
            "status": "paid" if is_paid else "outstanding",
        })
    
    return company


class DemoDataPopulator:
    """Populate demo data across all systems."""
    
    def __init__(self, database_url: str, dry_run: bool = False):
        self.database_url = database_url
        self.dry_run = dry_run
        self.pool: asyncpg.Pool | None = None
        self.teamleader_client: TeamleaderClient | None = None
        self.stats = {
            "companies_created": 0,
            "contacts_created": 0,
            "deals_created": 0,
            "activities_created": 0,
            "invoices_created": 0,
            "kbo_links_established": 0,
        }
    
    async def initialize(self) -> None:
        """Initialize database and API connections."""
        self.pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
        
        # Initialize Teamleader client
        load_teamleader_env_file()
        self.teamleader_client = TeamleaderClient.from_env()
        self.teamleader_client.refresh_access_token()
        
        logger.info("demo_populator_initialized", dry_run=self.dry_run)
    
    async def close(self) -> None:
        """Close connections."""
        if self.pool:
            await self.pool.close()
    
    async def check_existing_companies(self) -> int:
        """Count existing demo companies."""
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM crm_companies WHERE source_system = 'teamleader'"
            )
            return count
    
    async def create_teamleader_company(self, company: CompanyData) -> str | None:
        """Create a company in Teamleader via API."""
        if self.dry_run:
            logger.info("dry_run_create_company", name=company.name, vat=company.vat)
            return f"dry-run-{company.vat}"
        
        try:
            # Build company data for Teamleader API
            company_data = {
                "name": company.name,
                "business_type": "NV" if "NV" in company.name else "BV",
                "vat_number": company.vat.replace("BE", ""),
                "national_identification_number": company.vat.replace("BE", ""),
                "emails": [{"type": "primary", "email": f"info@{company.name.lower().replace(' ', '').replace('&', 'and')}.be"}],
                "telephones": [{"type": "phone", "number": f"+32 {random.choice(['2', '3', '9'])} {random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}"}],
                "website": f"https://www.{company.name.lower().replace(' ', '').replace('&', 'and')}.be",
                "address": {
                    "line_1": f"{random.randint(1, 200)} {random.choice(['Main Street', 'Business Park', 'Industrial Zone'])}",
                    "postal_code": self._get_postal_code(company.city),
                    "city": company.city,
                    "country": "BE",
                },
            }
            
            response = self.teamleader_client.add_company(company_data)
            company_id = response.get("data", {}).get("id")
            
            if company_id:
                self.stats["companies_created"] += 1
                logger.info("teamleader_company_created", name=company.name, id=company_id)
                
                # Create contacts
                for contact in company.contacts:
                    await self.create_teamleader_contact(company_id, contact)
                
                # Create deals
                for deal in company.deals:
                    await self.create_teamleader_deal(company_id, deal)
                
                return company_id
            
        except Exception as e:
            logger.error("teamleader_company_error", name=company.name, error=str(e))
        
        return None
    
    async def create_teamleader_contact(self, company_id: str, contact: dict) -> None:
        """Create a contact in Teamleader."""
        if self.dry_run:
            return
        
        try:
            contact_data = {
                "first_name": contact["first_name"],
                "last_name": contact["last_name"],
                "emails": [{"type": "primary", "email": contact["email"]}],
                "telephones": [{"type": "phone", "number": contact["phone"]}],
                "function": contact["job_title"],
                "decision_maker": contact["is_decision_maker"],
                "company": {"type": "company", "id": company_id},
            }
            
            self.teamleader_client.add_contact(contact_data)
            self.stats["contacts_created"] += 1
            
        except Exception as e:
            logger.error("teamleader_contact_error", error=str(e))
    
    async def create_teamleader_deal(self, company_id: str, deal: dict) -> None:
        """Create a deal in Teamleader."""
        if self.dry_run:
            return
        
        try:
            deal_data = {
                "title": deal["title"],
                "summary": f"Deal value: €{deal['value']:,}",
                "value": {"amount": deal["value"], "currency": "EUR"},
                "probability": deal["probability"],
                "estimated_closing_date": deal.get("expected_close_date"),
                "company": {"type": "company", "id": company_id},
            }
            
            self.teamleader_client.add_deal(deal_data)
            self.stats["deals_created"] += 1
            
        except Exception as e:
            logger.error("teamleader_deal_error", error=str(e))
    
    async def create_exact_customer(self, company: CompanyData) -> None:
        """Create customer in Exact Online (via database for demo)."""
        if self.dry_run:
            logger.info("dry_run_create_exact_customer", name=company.name)
            return
        
        try:
            async with self.pool.acquire() as conn:
                # Generate customer code
                customer_code = f"C{random.randint(10000, 99999)}"
                
                await conn.execute(
                    """
                    INSERT INTO exact_customers (
                        source_system, source_record_id, kbo_number, vat_number,
                        customer_code, customer_name, 
                        address_line1, city, postal_code, country,
                        email, phone,
                        revenue_ytd, outstanding_amount,
                        source_created_at, last_sync_at, raw_data
                    ) VALUES (
                        'exact_demo', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, 
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, $14
                    )
                    ON CONFLICT (source_system, source_record_id) 
                    DO UPDATE SET
                        revenue_ytd = EXCLUDED.revenue_ytd,
                        outstanding_amount = EXCLUDED.outstanding_amount,
                        last_sync_at = CURRENT_TIMESTAMP
                    """,
                    company.vat,
                    company.vat.replace("BE", ""),
                    company.vat,
                    customer_code,
                    company.name,
                    f"{random.randint(1, 200)} Business Street",
                    company.city,
                    self._get_postal_code(company.city),
                    "BE",
                    f"billing@{company.name.lower().replace(' ', '').replace('&', 'and')}.be",
                    f"+32 {random.choice(['2', '3'])} {random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}",
                    Decimal(str(company.revenue)),
                    Decimal(str(random.uniform(0, company.revenue * 0.15))),
                    json.dumps({"demo": True, "sector": company.sector, "employees": company.employees}),
                )
                
                # Create invoices
                for invoice in company.invoices:
                    await conn.execute(
                        """
                        INSERT INTO exact_invoices (
                            source_system, source_record_id, customer_code,
                            invoice_number, invoice_date, due_date,
                            amount_excl_vat, amount_incl_vat, vat_amount,
                            currency, status, payment_status,
                            source_created_at, last_sync_at, raw_data
                        ) VALUES (
                            'exact_demo', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, $12
                        )
                        ON CONFLICT (source_system, source_record_id) 
                        DO UPDATE SET
                            payment_status = EXCLUDED.payment_status,
                            last_sync_at = CURRENT_TIMESTAMP
                        """,
                        f"{company.vat}-{invoice['invoice_number']}",
                        customer_code,
                        invoice["invoice_number"],
                        datetime.strptime(invoice["date"], "%Y-%m-%d"),
                        datetime.strptime(invoice["due_date"], "%Y-%m-%d"),
                        Decimal(str(invoice["amount"] / 1.21)),  # Excl VAT
                        Decimal(str(invoice["amount"])),
                        Decimal(str(invoice["amount"] * 0.21 / 1.21)),
                        "EUR",
                        "posted",
                        invoice["status"],
                        json.dumps(invoice),
                    )
                
                self.stats["invoices_created"] += len(company.invoices)
                logger.info("exact_customer_created", name=company.name, code=customer_code)
                
        except Exception as e:
            logger.error("exact_customer_error", name=company.name, error=str(e))
    
    async def establish_kbo_link(self, company: CompanyData) -> None:
        """Create or update KBO link for the company."""
        if self.dry_run:
            return
        
        try:
            async with self.pool.acquire() as conn:
                # Check if KBO company exists
                kbo_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM companies WHERE vat_number = $1)",
                    company.vat
                )
                
                if not kbo_exists:
                    # Create minimal KBO record for demo
                    kbo_number = company.vat.replace("BE", "")
                    await conn.execute(
                        """
                        INSERT INTO companies (
                            kbo_number, company_name, vat_number,
                            status, juridical_situation,
                            street_address, city, postal_code, country,
                            industry_nace_code, legal_form_code,
                            employee_count, 
                            source_system, source_record_id, raw_data
                        ) VALUES (
                            $1, $2, $3, 'AC', '000', $4, $5, $6, 'BE',
                            $7, $8, $9, 'demo_populator', $10, $11
                        )
                        ON CONFLICT (kbo_number) 
                        DO UPDATE SET
                            vat_number = EXCLUDED.vat_number,
                            employee_count = EXCLUDED.employee_count
                        """,
                        kbo_number,
                        company.name,
                        company.vat,
                        f"{random.randint(1, 200)} Demo Street",
                        company.city,
                        self._get_postal_code(company.city),
                        self._get_nace_code(company.sector),
                        "001" if "BV" in company.name else "002",
                        company.employees,
                        kbo_number,
                        json.dumps({"demo": True, "sector": company.sector}),
                    )
                    logger.info("kbo_record_created", name=company.name, kbo=kbo_number)
                
                # Create identity link
                await conn.execute(
                    """
                    INSERT INTO source_identity_links (
                        source_system, source_record_id,
                        kbo_number, vat_number,
                        link_confidence, link_method,
                        verified, created_at
                    ) VALUES (
                        'teamleader', $1, $2, $3, 1.0, 'vat_match', true, CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (source_system, source_record_id) 
                    DO UPDATE SET
                        kbo_number = EXCLUDED.kbo_number,
                        link_confidence = EXCLUDED.link_confidence
                    """,
                    company.vat,
                    company.vat.replace("BE", ""),
                    company.vat,
                )
                
                # Also link Exact
                await conn.execute(
                    """
                    INSERT INTO source_identity_links (
                        source_system, source_record_id,
                        kbo_number, vat_number,
                        link_confidence, link_method,
                        verified, created_at
                    ) VALUES (
                        'exact', $1, $2, $3, 1.0, 'vat_match', true, CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (source_system, source_record_id) 
                    DO UPDATE SET
                        kbo_number = EXCLUDED.kbo_number,
                        link_confidence = EXCLUDED.link_confidence
                    """,
                    company.vat,
                    company.vat.replace("BE", ""),
                    company.vat,
                )
                
                self.stats["kbo_links_established"] += 1
                
        except Exception as e:
            logger.error("kbo_link_error", name=company.name, error=str(e))
    
    def _get_postal_code(self, city: str) -> str:
        """Get realistic postal code for Belgian city."""
        codes = {
            "Brussels": random.choice(["1000", "1020", "1030", "1040", "1050", "1060", "1070", "1080", "1090", "1120", "1130", "1140", "1150", "1160", "1170", "1180", "1190", "1200", "1210"]),
            "Antwerp": random.choice(["2000", "2018", "2020", "2030", "2040", "2050", "2060", "2100", "2140", "2170", "2180", "2600", "2610", "2660"]),
            "Gent": random.choice(["9000", "9030", "9031", "9032", "9040", "9041", "9042", "9050", "9051", "9052"]),
            "Leuven": random.choice(["3000", "3001", "3010", "3012", "3018"]),
        }
        return codes.get(city, "1000")
    
    def _get_nace_code(self, sector: str) -> str:
        """Get NACE code for sector."""
        codes = {
            "IT Services": "62010",
            "Software Development": "62020",
            "Cloud Services": "62030",
            "Data Analytics": "63110",
            "Cybersecurity": "62010",
            "Legal Services": "69101",
            "Accounting": "69201",
            "Notary": "69102",
            "Construction": "41201",
            "Engineering": "71121",
            "Architecture": "71111",
            "Technical Services": "43210",
            "Healthcare": "86101",
            "Pharmaceuticals": "21200",
            "Elderly Care": "87301",
            "Medical Devices": "32500",
            "Pharmacy": "47731",
            "Fashion Retail": "47710",
            "Electronics Retail": "47410",
            "Organic Food": "47210",
            "E-commerce": "47910",
            "Home Goods": "47591",
            "Metal Manufacturing": "24100",
            "Plastics": "22210",
            "Food Production": "10110",
            "Textiles": "13100",
            "Chemicals": "20110",
            "Logistics": "52290",
            "Transport": "49410",
            "Shipping": "50100",
            "Supply Chain": "52210",
            "Sustainable Transport": "49410",
            "Education": "85201",
            "Corporate Training": "85590",
            "IT Training": "85599",
            "Language Training": "85599",
            "Business Education": "85599",
            "Hotels": "55101",
            "Restaurants": "56101",
            "Event Management": "82301",
            "Travel Agency": "79110",
            "Catering": "56210",
            "Real Estate": "68100",
            "Property Management": "68310",
            "Commercial Property": "68100",
            "Residential Real Estate": "68100",
            "Real Estate Investment": "68100",
        }
        return codes.get(sector, "62010")
    
    async def populate(self, count: int = 50) -> dict:
        """Populate demo data across all systems."""
        print("=" * 70)
        print("🚀 Populating Hyperrealistic Demo Data")
        print("=" * 70)
        print(f"Mode: {'DRY RUN (preview only)' if self.dry_run else 'LIVE'}")
        print(f"Target: {count} companies")
        print("=" * 70)
        print()
        
        # Generate all company data
        companies = [generate_company_data(c) for c in HYPERREALISTIC_COMPANIES[:count]]
        
        for i, company in enumerate(companies, 1):
            print(f"[{i}/{len(companies)}] Processing: {company.name}")
            print(f"       VAT: {company.vat} | City: {company.city} | Sector: {company.sector}")
            print(f"       Contacts: {len(company.contacts)} | Deals: {len(company.deals)} | Invoices: {len(company.invoices)}")
            
            # Create in Teamleader
            company_id = await self.create_teamleader_company(company)
            
            if company_id or self.dry_run:
                # Create in Exact
                await self.create_exact_customer(company)
                
                # Establish KBO link
                await self.establish_kbo_link(company)
            
            print()
        
        # Refresh materialized views
        if not self.dry_run:
            print("Refreshing materialized views...")
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY unified_company_360")
                    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY unified_pipeline_revenue")
                    print("✅ Views refreshed")
            except Exception as e:
                logger.warning("view_refresh_warning", error=str(e))
        
        return self.stats


def get_database_url() -> str:
    """Get database URL from environment."""
    url = os.getenv("DATABASE_URL")
    if not url:
        # Try to construct from .env.local
        env_file = Path(__file__).resolve().parents[1] / ".env.local"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("DATABASE_URL="):
                        url = line.strip().split("=", 1)[1].strip('"')
                        break
    return url


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Populate hyperrealistic demo data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating data")
    parser.add_argument("--count", type=int, default=50, help="Number of companies to create")
    parser.add_argument("--reset", action="store_true", help="Clear existing demo data first")
    parser.add_argument("--database-url", type=str, default=get_database_url(), help="PostgreSQL URL")
    args = parser.parse_args()
    
    if not args.database_url:
        print("❌ DATABASE_URL not configured")
        return 1
    
    populator = DemoDataPopulator(args.database_url, dry_run=args.dry_run)
    
    try:
        await populator.initialize()
        
        if args.reset and not args.dry_run:
            print("⚠️  Reset requested - clearing existing demo data...")
            # TODO: Implement reset logic
            print("   (Reset not yet implemented - proceeding with upserts)")
            print()
        
        # Check existing
        existing = await populator.check_existing_companies()
        if existing > 0:
            print(f"ℹ️  Found {existing} existing Teamleader companies")
            print()
        
        # Populate
        stats = await populator.populate(count=args.count)
        
        # Summary
        print("=" * 70)
        print("📊 POPULATION SUMMARY")
        print("=" * 70)
        for key, value in stats.items():
            print(f"  {key}: {value}")
        print("=" * 70)
        
        if args.dry_run:
            print("\n⚠️  This was a DRY RUN. No data was actually created.")
            print("   Run without --dry-run to create the data.")
        else:
            print("\n✅ Demo data population complete!")
            print("\nNext steps:")
            print("  1. Sync Teamleader: uv run python scripts/sync_teamleader_to_postgres.py --full")
            print("  2. Test 360° view: Query 'Show me TechVision Solutions'")
            print("  3. Create segment: 'Software companies in Brussels'")
            print("  4. Activate to Resend: Push segment and capture screenshot")
        
        return 0
        
    except Exception as e:
        logger.error("population_failed", error=str(e))
        print(f"\n❌ Error: {e}")
        return 1
    finally:
        await populator.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
