#!/usr/bin/env python3
"""
Synthetic Demo Dataset Generator

Generates a curated dataset of realistic Belgian companies for consistent demos.
This ensures rich demo experiences regardless of live enrichment progress.

Usage:
    python scripts/generate_demo_dataset.py [--count 500] [--output demo]

Environment:
    DEMO_MODE=true - Switch application to use demo schema

The generated data is stored in a separate PostgreSQL schema (`demo`) to avoid
polluting production data.
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
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class CompanyTemplate:
    """Template for generating realistic Belgian companies."""

    name_prefixes: list[str] = field(
        default_factory=lambda: [
            "Belgian",
            "Flemish",
            "Walloon",
            "Brussels",
            "Antwerp",
            "Ghent",
            "Liege",
            "Namur",
            "Leuven",
            "Mechelen",
            "Hasselt",
            "Kortrijk",
            "Oostende",
            "Sint-Niklaas",
            "Genk",
            "Bruges",
            "Louvain",
        ]
    )

    name_cores: list[str] = field(
        default_factory=lambda: [
            "Tech",
            "Solutions",
            "Consulting",
            "Group",
            "Industries",
            "Systems",
            "Digital",
            "Innovations",
            "Services",
            "Partners",
            "Enterprises",
            "Logistics",
            "Engineering",
            "Manufacturing",
            "Trading",
            "Holdings",
        ]
    )

    name_suffixes: list[str] = field(
        default_factory=lambda: ["BV", "NV", "CV", "SCRL", "SA", "SPRL", "VBA", "CommV"]
    )

    cities: list[dict] = field(
        default_factory=lambda: [
            {
                "name": "Brussel",
                "zip_prefix": "10",
                "region": "Brussels",
                "lat": 50.85,
                "lon": 4.35,
            },
            {
                "name": "Antwerpen",
                "zip_prefix": "20",
                "region": "Flanders",
                "lat": 51.22,
                "lon": 4.40,
            },
            {"name": "Gent", "zip_prefix": "90", "region": "Flanders", "lat": 51.05, "lon": 3.73},
            {
                "name": "Brugge",
                "zip_prefix": "80",
                "region": "Flanders",
                "lat": 51.21,
                "lon": 3.22,
            },
            {
                "name": "Leuven",
                "zip_prefix": "30",
                "region": "Flanders",
                "lat": 50.88,
                "lon": 4.70,
            },
            {"name": "Luik", "zip_prefix": "40", "region": "Wallonia", "lat": 50.63, "lon": 5.57},
            {"name": "Namur", "zip_prefix": "50", "region": "Wallonia", "lat": 50.47, "lon": 4.87},
            {
                "name": "Hasselt",
                "zip_prefix": "35",
                "region": "Flanders",
                "lat": 50.93,
                "lon": 5.34,
            },
            {
                "name": "Mechelen",
                "zip_prefix": "28",
                "region": "Flanders",
                "lat": 51.03,
                "lon": 4.48,
            },
            {
                "name": "Kortrijk",
                "zip_prefix": "85",
                "region": "Flanders",
                "lat": 50.83,
                "lon": 3.27,
            },
        ]
    )

    nace_codes: list[dict] = field(
        default_factory=lambda: [
            {
                "code": "6201",
                "description": "Computer programming activities",
                "sector": "Technology",
            },
            {
                "code": "6202",
                "description": "Computer consultancy activities",
                "sector": "Technology",
            },
            {
                "code": "6311",
                "description": "Data processing, hosting and related activities",
                "sector": "Technology",
            },
            {
                "code": "7022",
                "description": "Business and other management consultancy",
                "sector": "Consulting",
            },
            {"code": "7311", "description": "Advertising agencies", "sector": "Marketing"},
            {
                "code": "7320",
                "description": "Market research and public opinion polling",
                "sector": "Marketing",
            },
            {
                "code": "4646",
                "description": "Wholesale of pharmaceutical goods",
                "sector": "Healthcare",
            },
            {
                "code": "8621",
                "description": "General medical practice activities",
                "sector": "Healthcare",
            },
            {
                "code": "6820",
                "description": "Renting and operating of own or leased real estate",
                "sector": "Real Estate",
            },
            {
                "code": "4110",
                "description": "Development of building projects",
                "sector": "Construction",
            },
            {"code": "4321", "description": "Electrical installation", "sector": "Construction"},
            {
                "code": "4711",
                "description": "Retail sale in non-specialised stores",
                "sector": "Retail",
            },
            {"code": "4920", "description": "Freight rail transport", "sector": "Logistics"},
            {"code": "4941", "description": "Road freight transport", "sector": "Logistics"},
            {
                "code": "5510",
                "description": "Hotels and similar accommodation",
                "sector": "Hospitality",
            },
            {
                "code": "5610",
                "description": "Restaurants and mobile food service activities",
                "sector": "Hospitality",
            },
        ]
    )

    legal_forms: list[str] = field(
        default_factory=lambda: [
            "Besloten Vennootschap",
            "Naamloze Vennootschap",
            "Commanditaire Vennootschap",
            "Société Privée à Responsabilité Limitée",
            "Société Anonyme",
            "Coöperatieve Vennootschap",
            "Vennootschap onder firma",
        ]
    )

    streets: list[str] = field(
        default_factory=lambda: [
            "Main Street",
            "Station Road",
            "High Street",
            "Church Street",
            "Park Avenue",
            "Market Square",
            "Industrial Avenue",
            "Business Park",
            "Technology Drive",
            "Innovation Boulevard",
            "Commerce Street",
            "Enterprise Way",
        ]
    )

    email_domains: list[str] = field(
        default_factory=lambda: [
            "gmail.com",
            "outlook.com",
            "hotmail.com",
            "yahoo.com",
            "company.be",
            "enterprise.eu",
            "business.net",
            "corporate.com",
            "consulting.be",
            "solutions.eu",
            "tech.net",
            "services.com",
        ]
    )

    website_suffixes: list[str] = field(
        default_factory=lambda: [".be", ".eu", ".com", ".net", ".org", ".io"]
    )


class DemoDatasetGenerator:
    """Generates realistic demo data for Belgian companies."""

    def __init__(self, seed: int = 42):
        self.template = CompanyTemplate()
        self.seed = seed
        random.seed(seed)
        self.generated_companies: list[dict] = []

    def _generate_kbo_number(self, index: int) -> str:
        """Generate a valid-looking Belgian KBO number."""
        # KBO numbers are 10 digits, starting with 0
        base = 200000000 + (index * 137) % 800000000
        return f"{base:010d}"

    def _generate_company_name(self) -> str:
        """Generate a realistic company name."""
        patterns = [
            lambda: (
                f"{random.choice(self.template.name_prefixes)} {random.choice(self.template.name_cores)} {random.choice(self.template.name_suffixes)}"
            ),
            lambda: (
                f"{random.choice(self.template.name_cores)} {random.choice(self.template.name_prefixes)} {random.choice(self.template.name_suffixes)}"
            ),
            lambda: (
                f"{random.choice(self.template.name_prefixes)}-{random.choice(self.template.name_cores)} {random.choice(self.template.name_suffixes)}"
            ),
            lambda: (
                f"{random.choice(self.template.name_cores)}.be {random.choice(self.template.name_suffixes)}"
            ),
        ]
        return random.choice(patterns)()

    def _generate_address(self, city: dict) -> dict:
        """Generate a realistic address."""
        street = random.choice(self.template.streets)
        number = random.randint(1, 250)
        box = random.choice(["", "", "", f" bus {random.randint(1, 20)}"])
        zip_code = f"{city['zip_prefix']}{random.randint(0, 99):02d}"

        return {
            "street": f"{street} {number}{box}",
            "city": city["name"],
            "zip_code": zip_code,
            "country": "Belgium",
        }

    def _generate_contact_info(self, company_name: str) -> dict:
        """Generate realistic contact information."""
        # Normalize company name for email/website
        normalized = company_name.lower().replace(" ", "").replace("-", "").replace(".", "")
        # Remove suffixes for domain
        for suffix in ["bv", "nv", "cv", "scrl", "sa", "sprl", "vba", "commv"]:
            normalized = normalized.removesuffix(suffix)

        email = f"info@{normalized[:20]}{random.choice(self.template.email_domains)}"
        website = f"https://www.{normalized[:20]}{random.choice(self.template.website_suffixes)}"

        # Generate realistic Belgian phone number
        prefixes = ["02", "03", "04", "09", "010", "011", "012", "013", "014", "015", "016"]
        prefix = random.choice(prefixes)
        number = "".join([str(random.randint(0, 9)) for _ in range(8)])
        phone = f"+32 {prefix[1:] if prefix.startswith('0') else prefix} {number[:2]} {number[2:4]} {number[4:6]} {number[6:]}"

        return {"email": email, "phone": phone, "website": website}

    def _generate_ai_description(self, company_name: str, nace: dict) -> str:
        """Generate a realistic AI company description."""
        templates = [
            f"{company_name} is a leading {nace['sector'].lower()} company specializing in {nace['description'].lower()}. Established in Belgium, they serve clients across the {random.choice(['Benelux', 'European', 'Belgian'])} market with innovative solutions and professional expertise.",
            f"Founded with a vision for excellence, {company_name} delivers {nace['description'].lower()} services to businesses of all sizes. Their {nace['sector'].lower()} expertise has made them a trusted partner in the Belgian market.",
            f"{company_name} operates in the {nace['sector'].lower()} sector, focusing on {nace['description'].lower()}. With years of experience, they provide high-quality services tailored to client needs throughout Belgium.",
            f"As a prominent player in {nace['sector'].lower()}, {company_name} offers comprehensive {nace['description'].lower()} solutions. Their Belgian headquarters supports operations across multiple regions with dedicated professionals.",
        ]
        return random.choice(templates)

    def _generate_founding_date(self) -> datetime:
        """Generate a realistic founding date."""
        years_back = random.randint(1, 50)
        days_variation = random.randint(-180, 180)
        date = datetime.now() - timedelta(days=years_back * 365 + days_variation)
        return date

    def _generate_employee_count(self) -> int:
        """Generate realistic employee count distribution."""
        weights = [
            (1, 5, 0.35),  # 35% micro companies
            (6, 20, 0.30),  # 30% small companies
            (21, 50, 0.20),  # 20% medium-small
            (51, 100, 0.10),  # 10% medium
            (101, 500, 0.04),  # 4% large
            (501, 2000, 0.01),  # 1% enterprise
        ]

        rand = random.random()
        cumulative = 0
        for min_val, max_val, weight in weights:
            cumulative += weight
            if rand <= cumulative:
                return random.randint(min_val, max_val)
        return random.randint(1, 10)

    def _generate_revenue_range(self, employees: int) -> str:
        """Generate realistic revenue range based on employee count."""
        base_revenue = employees * random.randint(80000, 150000)

        if base_revenue < 1_000_000:
            return "< €1M"
        elif base_revenue < 5_000_000:
            return "€1M - €5M"
        elif base_revenue < 10_000_000:
            return "€5M - €10M"
        elif base_revenue < 50_000_000:
            return "€10M - €50M"
        elif base_revenue < 100_000_000:
            return "€50M - €100M"
        else:
            return "> €100M"

    def generate_company(self, index: int) -> dict:
        """Generate a single complete company record."""
        city = random.choice(self.template.cities)
        nace = random.choice(self.template.nace_codes)
        company_name = self._generate_company_name()
        address = self._generate_address(city)
        contact = self._generate_contact_info(company_name)
        employees = self._generate_employee_count()

        # Add slight variation to lat/lon based on street number
        lat_offset = (index % 100 - 50) / 10000
        lon_offset = (index % 97 - 48) / 10000

        return {
            "kbo_number": self._generate_kbo_number(index),
            "company_name": company_name,
            "legal_form": random.choice(self.template.legal_forms),
            "street_address": address["street"],
            "city": address["city"],
            "postal_code": address["zip_code"],
            "country": address["country"],
            "nace_code": nace["code"],
            "nace_description": nace["description"],
            "sector": nace["sector"],
            "region": city["region"],
            "main_email": contact["email"],
            "main_phone": contact["phone"],
            "website_url": contact["website"],
            "ai_description": self._generate_ai_description(company_name, nace),
            "founded_date": self._generate_founding_date().strftime("%Y-%m-%d"),
            "employee_count": employees,
            "revenue_range": self._generate_revenue_range(employees),
            "geo_latitude": round(city["lat"] + lat_offset, 6),
            "geo_longitude": round(city["lon"] + lon_offset, 6),
            "sync_status": "enriched",
            "enriched_at": datetime.now().isoformat(),
            "data_source": "demo_synthetic",
            "demo_provenance": {
                "type": "synthetic",
                "generated_at": datetime.now().isoformat(),
                "generator_version": "1.0",
                "seed": self.seed,
            },
        }

    def generate(self, count: int = 500) -> list[dict]:
        """Generate the full demo dataset."""
        print(f"Generating {count} synthetic Belgian companies...")
        self.generated_companies = []

        for i in range(count):
            company = self.generate_company(i)
            self.generated_companies.append(company)

            if (i + 1) % 100 == 0:
                print(f"  Generated {i + 1}/{count} companies...")

        print(f"✅ Generated {count} companies successfully")
        return self.generated_companies

    def get_statistics(self) -> dict:
        """Calculate statistics about the generated dataset."""
        if not self.generated_companies:
            return {}

        stats = {
            "total_count": len(self.generated_companies),
            "by_region": {},
            "by_sector": {},
            "by_city": {},
            "by_employee_range": {},
            "email_coverage": 100.0,
            "phone_coverage": 100.0,
            "website_coverage": 100.0,
            "ai_description_coverage": 100.0,
            "geocoding_coverage": 100.0,
        }

        for company in self.generated_companies:
            # Region distribution
            region = company["region"]
            stats["by_region"][region] = stats["by_region"].get(region, 0) + 1

            # Sector distribution
            sector = company["sector"]
            stats["by_sector"][sector] = stats["by_sector"].get(sector, 0) + 1

            # City distribution
            city = company["city"]
            stats["by_city"][city] = stats["by_city"].get(city, 0) + 1

            # Employee range
            emp = company["employee_count"]
            if emp <= 5:
                range_key = "1-5"
            elif emp <= 20:
                range_key = "6-20"
            elif emp <= 50:
                range_key = "21-50"
            elif emp <= 100:
                range_key = "51-100"
            elif emp <= 500:
                range_key = "101-500"
            else:
                range_key = "500+"
            stats["by_employee_range"][range_key] = (
                stats["by_employee_range"].get(range_key, 0) + 1
            )

        return stats


class DemoDatabaseManager:
    """Manages the demo dataset in PostgreSQL."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    async def setup_demo_schema(self) -> bool:
        """Create the demo schema and tables."""
        try:
            import asyncpg

            conn = await asyncpg.connect(self.database_url)

            # Create demo schema
            await conn.execute("CREATE SCHEMA IF NOT EXISTS demo")

            # Create demo_companies table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS demo.companies (
                    id SERIAL PRIMARY KEY,
                    kbo_number VARCHAR(20) UNIQUE NOT NULL,
                    company_name VARCHAR(500) NOT NULL,
                    legal_form VARCHAR(100),
                    street_address VARCHAR(500),
                    city VARCHAR(100),
                    postal_code VARCHAR(20),
                    country VARCHAR(100) DEFAULT 'Belgium',
                    nace_code VARCHAR(20),
                    nace_description VARCHAR(500),
                    sector VARCHAR(100),
                    region VARCHAR(100),
                    main_email VARCHAR(500),
                    main_phone VARCHAR(100),
                    website_url VARCHAR(500),
                    ai_description TEXT,
                    founded_date DATE,
                    employee_count INTEGER,
                    revenue_range VARCHAR(100),
                    geo_latitude DECIMAL(10, 6),
                    geo_longitude DECIMAL(10, 6),
                    sync_status VARCHAR(50) DEFAULT 'enriched',
                    enriched_at TIMESTAMP WITH TIME ZONE,
                    data_source VARCHAR(100) DEFAULT 'demo_synthetic',
                    demo_provenance JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)

            # Create indexes for common query patterns
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_demo_companies_city
                ON demo.companies(city)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_demo_companies_nace
                ON demo.companies(nace_code)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_demo_companies_sector
                ON demo.companies(sector)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_demo_companies_region
                ON demo.companies(region)
            """)

            await conn.close()
            print("✅ Demo schema and tables created")
            return True

        except Exception as e:
            print(f"❌ Failed to setup demo schema: {e}")
            return False

    async def load_companies(self, companies: list[dict]) -> bool:
        """Load companies into the demo schema."""
        try:
            import asyncpg

            conn = await asyncpg.connect(self.database_url)

            # Clear existing demo data
            await conn.execute("DELETE FROM demo.companies")

            # Insert companies in batches
            batch_size = 100
            total = len(companies)

            for i in range(0, total, batch_size):
                batch = companies[i : i + batch_size]

                values = []
                for company in batch:
                    values.append(
                        (
                            company["kbo_number"],
                            company["company_name"],
                            company["legal_form"],
                            company["street_address"],
                            company["city"],
                            company["postal_code"],
                            company["country"],
                            company["nace_code"],
                            company["nace_description"],
                            company["sector"],
                            company["region"],
                            company["main_email"],
                            company["main_phone"],
                            company["website_url"],
                            company["ai_description"],
                            company["founded_date"],
                            company["employee_count"],
                            company["revenue_range"],
                            company["geo_latitude"],
                            company["geo_longitude"],
                            company["sync_status"],
                            company["enriched_at"],
                            company["data_source"],
                            json.dumps(company["demo_provenance"]),
                        )
                    )

                await conn.executemany(
                    """
                    INSERT INTO demo.companies (
                        kbo_number, company_name, legal_form, street_address,
                        city, postal_code, country, nace_code, nace_description,
                        sector, region, main_email, main_phone, website_url,
                        ai_description, founded_date, employee_count, revenue_range,
                        geo_latitude, geo_longitude, sync_status, enriched_at,
                        data_source, demo_provenance
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                             $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24)
                """,
                    values,
                )

                print(f"  Loaded {min(i + batch_size, total)}/{total} companies...")

            await conn.close()
            print(f"✅ Loaded {total} companies into demo schema")
            return True

        except Exception as e:
            print(f"❌ Failed to load companies: {e}")
            return False

    async def verify_load(self) -> dict:
        """Verify the demo data was loaded correctly."""
        try:
            import asyncpg

            conn = await asyncpg.connect(self.database_url)

            count = await conn.fetchval("SELECT COUNT(*) FROM demo.companies")

            # Sample a few records
            samples = await conn.fetch("""
                SELECT kbo_number, company_name, city, sector, main_email
                FROM demo.companies
                LIMIT 3
            """)

            await conn.close()

            return {"count": count, "samples": [dict(s) for s in samples]}

        except Exception as e:
            return {"error": str(e)}


async def main():
    parser = argparse.ArgumentParser(description="Generate synthetic demo dataset for Belgian CDP")
    parser.add_argument(
        "--count", type=int, default=500, help="Number of companies to generate (default: 500)"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--output",
        type=str,
        choices=["database", "json", "both"],
        default="both",
        help="Output target (default: both)",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=os.getenv("DATABASE_URL"),
        help="PostgreSQL connection string (or set DATABASE_URL env var)",
    )
    parser.add_argument(
        "--json-file",
        type=str,
        default="data/demo_companies.json",
        help="JSON output file path (default: data/demo_companies.json)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("DEMO DATASET GENERATOR")
    print("=" * 70)
    print("Configuration:")
    print(f"  Count: {args.count} companies")
    print(f"  Seed: {args.seed}")
    print(f"  Output: {args.output}")
    print()

    # Generate companies
    generator = DemoDatasetGenerator(seed=args.seed)
    companies = generator.generate(count=args.count)

    # Display statistics
    stats = generator.get_statistics()
    print("\n📊 Dataset Statistics:")
    print(f"  Total companies: {stats['total_count']}")
    print(f"  Email coverage: {stats['email_coverage']:.1f}%")
    print(f"  Phone coverage: {stats['phone_coverage']:.1f}%")
    print(f"  Website coverage: {stats['website_coverage']:.1f}%")
    print(f"  AI description coverage: {stats['ai_description_coverage']:.1f}%")
    print(f"  Geocoding coverage: {stats['geocoding_coverage']:.1f}%")

    print("\n  By Region:")
    for region, count in sorted(stats["by_region"].items(), key=lambda x: -x[1]):
        print(f"    {region}: {count} ({count / stats['total_count'] * 100:.1f}%)")

    print("\n  By Sector:")
    for sector, count in sorted(stats["by_sector"].items(), key=lambda x: -x[1])[:5]:
        print(f"    {sector}: {count} ({count / stats['total_count'] * 100:.1f}%)")

    # Save to JSON if requested
    if args.output in ("json", "both"):
        json_path = Path(args.json_file)
        json_path.parent.mkdir(parents=True, exist_ok=True)

        output_data = {
            "generated_at": datetime.now().isoformat(),
            "count": len(companies),
            "seed": args.seed,
            "statistics": stats,
            "companies": companies,
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Saved JSON to: {json_path}")

    # Load to database if requested
    if args.output in ("database", "both"):
        if not args.database_url:
            print("\n⚠️  DATABASE_URL not set, skipping database load")
            print("   Set DATABASE_URL or pass --database-url to load to PostgreSQL")
        else:
            print("\n🔄 Loading to database...")
            db_manager = DemoDatabaseManager(args.database_url)

            if await db_manager.setup_demo_schema():
                if await db_manager.load_companies(companies):
                    verification = await db_manager.verify_load()
                    print("\n✅ Database verification:")
                    print(f"   Loaded: {verification.get('count', 0)} companies")
                    if "samples" in verification:
                        print("\n   Sample records:")
                        for sample in verification["samples"]:
                            print(
                                f"     - {sample['company_name']} ({sample['city']}, {sample['sector']})"
                            )

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
    print("\nTo use the demo dataset:")
    print("  1. Set DEMO_MODE=true in your environment")
    print("  2. The application will query from 'demo.companies' instead of 'public.companies'")
    print("  3. All demo data has 100% coverage for consistent presentations")


if __name__ == "__main__":
    asyncio.run(main())
