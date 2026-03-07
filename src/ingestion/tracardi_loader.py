"""
KBO Data Ingestion for CDP_Merged.
From CDPT - Loads KBO public data into Tracardi.
"""

import asyncio
import csv
import os
import random
from datetime import UTC, datetime
from typing import Any

from src.core.logger import get_logger
from src.services.tracardi import TracardiClient

logger = get_logger(__name__)

# Path to KBO data
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data/kbo"
)


def infer_province(zipcode: str) -> str:
    """Infer province from zipcode."""
    if not zipcode:
        return "Unknown"
    try:
        z = int(zipcode)
        if 9000 <= z <= 9999:
            return "Oost-Vlaanderen"
        if 8000 <= z <= 8999:
            return "West-Vlaanderen"
        if 2000 <= z <= 2999:
            return "Antwerpen"
        if 3500 <= z <= 3999:
            return "Limburg"
        if 1500 <= z <= 1999:
            return "Vlaams-Brabant"
        if 3000 <= z <= 3499:
            return "Vlaams-Brabant"
        if 1000 <= z <= 1299:
            return "Brussels"
        return "Other"
    except ValueError:
        return "Unknown"


async def load_and_aggregate_data() -> list[dict[str, Any]]:
    """
    Load and aggregate KBO data from CSV files.
    Returns list of enterprise dictionaries.
    """
    logger.info("Reading Address CSV first to filter relevant entities")

    enterprises: dict[str, dict[str, Any]] = {}

    # 1. Address.csv - Filter by Zipcode FIRST
    logger.info("Pass 1: Address.csv (Filtering)")
    address_path = os.path.join(DATA_DIR, "address.csv")
    if not os.path.exists(address_path):
        logger.warning(
            "Address file not found, skipping KBO ingestion", extra={"path": address_path}
        )
        return []

    with open(address_path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("TypeOfAddress") == "REGO":
                zipcode = row.get("Zipcode", "")
                try:
                    z = int(zipcode)
                    valid_ranges = [
                        (9000, 9099),  # Gent
                        (2000, 2999),  # Antwerp
                        (1000, 1299),  # Brussels
                        (4000, 4999),  # Liège
                        (9100, 9199),  # Sint-Niklaas
                    ]

                    in_valid_range = any(start <= z <= end for start, end in valid_ranges)

                    if in_valid_range:
                        ent_num = row.get("EntityNumber")
                        if ent_num is None:
                            continue
                        enterprises[ent_num] = {
                            "enterprise_number": ent_num,
                            "status": None,
                            "address": {
                                "street": f"{row.get('StreetNL', '')} {row.get('HouseNumber', '')}".strip(),
                                "zipcode": zipcode,
                                "city": row.get("MunicipalityNL", ""),
                                "country": row.get("CountryNL", ""),
                            },
                            "province": infer_province(zipcode),
                            "nace_codes": [],
                            "emails": [],
                            "phones": [],
                            "name": "[No Name in Source]",
                        }
                except ValueError:
                    pass

    logger.info("Found candidate enterprises in target regions", extra={"count": len(enterprises)})

    # 2. Enterprise.csv - Verify Active Status
    logger.info("Pass 2: Enterprise.csv (Verifying Active Status)")
    enterprise_path = os.path.join(DATA_DIR, "enterprise.csv")
    if os.path.exists(enterprise_path):
        verified_active_ids = set()
        with open(enterprise_path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # enterprise.csv uses EnterpriseNumber; keep fallback for variant exports
                ent_num = row.get("EnterpriseNumber") or row.get("EntityNumber")
                if ent_num in enterprises:
                    if row.get("Status") == "AC":
                        enterprises[ent_num]["status"] = row.get("Status")
                        enterprises[ent_num]["start_date"] = row.get("StartDate")
                        enterprises[ent_num]["juridical_form"] = row.get("JuridicalForm")
                        verified_active_ids.add(ent_num)

        # Keep only enterprises present in enterprise.csv and explicitly marked active.
        enterprises = {
            ent_num: payload
            for ent_num, payload in enterprises.items()
            if ent_num in verified_active_ids
        }

    logger.info("Retained active enterprises", extra={"count": len(enterprises)})

    # 3. Denomination.csv - Get company names
    logger.info("Pass 3: Denomination.csv")
    denomination_path = os.path.join(DATA_DIR, "denomination.csv")
    if os.path.exists(denomination_path):
        with open(denomination_path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ent_num = row.get("EntityNumber")
                if ent_num in enterprises:
                    enterprises[ent_num]["name"] = row.get("Denomination", "[No Name]")

    # 4. Activity.csv - Get NACE codes
    logger.info("Pass 4: Activity.csv")
    activity_path = os.path.join(DATA_DIR, "activity.csv")
    if os.path.exists(activity_path):
        with open(activity_path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ent_num = row.get("EntityNumber")
                if ent_num in enterprises:
                    nace = row.get("NaceCode")
                    if nace:
                        enterprises[ent_num]["nace_codes"].append(nace)

    # 5. Contact.csv - Get emails and phones
    logger.info("Pass 5: Contact.csv")
    contact_path = os.path.join(DATA_DIR, "contact.csv")
    if os.path.exists(contact_path):
        with open(contact_path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ent_num = row.get("EntityNumber")
                if ent_num in enterprises:
                    contact_type = row.get("ContactType")
                    value = row.get("Value")
                    if contact_type == "EMAIL" and value:
                        enterprises[ent_num]["emails"].append(value)
                    elif contact_type == "TEL" and value:
                        enterprises[ent_num]["phones"].append(value)

    return list(enterprises.values())


async def ingest_to_tracardi(data: list[dict[str, Any]]):
    """Ingest enterprise data into Tracardi."""
    client = TracardiClient()
    logger.info("Sending profiles to Tracardi", extra={"count": len(data)})

    batch_size = max(1, int(os.getenv("KBO_INGEST_BATCH_SIZE", "50")))
    events_batch = []
    ingest_time = datetime.now(UTC).replace(microsecond=0).isoformat()

    for i, ent in enumerate(data):
        event_properties = {
            "enterprise_number": ent.get("enterprise_number"),
            "name": ent.get("name"),
            "status": ent.get("status"),
            "start_date": ent.get("start_date"),
            "juridical_form": ent.get("juridical_form"),
            "street": ent.get("address", {}).get("street"),
            "zipcode": ent.get("address", {}).get("zipcode"),
            "city": ent.get("address", {}).get("city"),
            "country": ent.get("address", {}).get("country"),
            "province": ent.get("province"),
            "nace_codes": ent.get("nace_codes", []),
            "emails": ent.get("emails", []),
            "phones": ent.get("phones", []),
            "email": ent.get("emails", [])[0] if ent.get("emails") else None,
            "phone": ent.get("phones", [])[0] if ent.get("phones") else None,
            "employee_count": random.randint(1, 500),  # Mock for POC
        }

        profile_payload: dict[str, Any] = {
            "id": ent.get("enterprise_number"),
            "traits": event_properties,
            "properties": event_properties,
            "segments": [],
            # Tracardi GUI profile list (`/profile/select/range/...`) filters on create/update time.
            # Bulk imports only populate `insert` automatically, so we set create/update explicitly.
            "metadata": {"time": {"create": ingest_time, "update": ingest_time}},
        }

        events_batch.append(profile_payload)

        if len(events_batch) >= batch_size:
            logger.info("Sending batch", extra={"batch_number": i // batch_size + 1})
            await client.import_profiles(events_batch)
            events_batch = []

    if events_batch:
        logger.info("Sending final batch")
        await client.import_profiles(events_batch)

    logger.info("Ingestion complete")


async def main():
    """Main entry point for KBO ingestion."""
    data = await load_and_aggregate_data()
    if data:
        await ingest_to_tracardi(data)
    else:
        logger.warning("No data to ingest")


if __name__ == "__main__":
    asyncio.run(main())
