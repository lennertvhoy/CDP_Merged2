#!/usr/bin/env python3
"""Create demo companies in Teamleader that match Exact-linked KBOs."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.services.teamleader import TeamleaderClient, load_teamleader_env_file

# Companies to create (matching Exact-linked KBOs for true 360° views)
COMPANIES = [
    {"name": "Ordinateur Express", "vat": "BE0418633489", "city": "Brussels", "sector": "IT Services"},
    {"name": "B.B.S. Entreprise", "vat": "BE0438437723", "city": "Antwerp", "sector": "Business Services"},
    {"name": "DEF Services", "vat": "BE0508638405", "city": "Gent", "sector": "Consulting"},
    {"name": "Vespa Club Mechelen", "vat": "BE0649863970", "city": "Mechelen", "sector": "Non-profit"},
    {"name": "Manilla Games", "vat": "BE0722816284", "city": "Brussels", "sector": "Gaming"},
]

load_teamleader_env_file()
client = TeamleaderClient.from_env()
client.refresh_access_token()

print("Creating 360° demo companies in Teamleader...")
print("=" * 60)

created = 0
for company in COMPANIES:
    try:
        data = {
            "name": company["name"],
            "vat_number": company["vat"].replace("BE", ""),
            "national_identification_number": company["vat"].replace("BE", ""),
            "business_type": "BV" if "Services" in company["name"] or "Express" in company["name"] else "VZW",
            "address": {
                "line_1": f"Demo Address 123",
                "city": company["city"],
                "postal_code": "1000",
                "country": "BE",
            },
            "emails": [{"type": "primary", "email": f"info@{company['name'].lower().replace(' ', '').replace('.', '')}.be"}],
            "telephones": [{"type": "phone", "number": f"+32 2 {10000000 + hash(company['name']) % 90000000}"[:12]}],
            "website": f"https://www.{company['name'].lower().replace(' ', '').replace('.', '')}.be",
        }
        result = client.add_company(data)
        company_id = result.get("data", {}).get("id", "N/A")
        print(f"✅ Created: {company['name'][:30]:<30} ID: {company_id[:20]}")
        created += 1
    except Exception as e:
        error_str = str(e).lower()
        if "already exists" in error_str or "duplicate" in error_str or "already" in error_str:
            print(f"ℹ️  Exists:  {company['name'][:30]:<30}")
        else:
            print(f"❌ Error:   {company['name'][:30]:<30} - {str(e)[:50]}")

print("=" * 60)
print(f"Created/Verified: {created}/{len(COMPANIES)} companies")
print("\nNext: Run sync and then test 360° view")
