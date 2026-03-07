#!/usr/bin/env python3
"""KBO Data Ingestion into Tracardi"""

import csv
import os
from pathlib import Path

import requests  # type: ignore[import-untyped]

from src.core.logger import get_logger

logger = get_logger(__name__)

TRACARDI_HOST = os.environ.get("TRACARDI_HOST", "http://localhost:8686")
TRACARDI_USER = os.environ.get("TRACARDI_USER")
TRACARDI_PASS = os.environ.get("TRACARDI_PASSWORD")

if not TRACARDI_USER or not TRACARDI_PASS:
    raise ValueError(
        "TRACARDI_USER and TRACARDI_PASSWORD environment variables must be set. "
        "Example: TRACARDI_USER=admin TRACARDI_PASSWORD=secret python -m src.ingestion.kbo_ingest"
    )


def get_access_token() -> str:
    """Get access token from Tracardi"""
    url = f"{TRACARDI_HOST}/user/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = f"username={TRACARDI_USER}&password={TRACARDI_PASS}"
    response = requests.post(url, data=data, headers=headers, timeout=30)  # 30s timeout
    response.raise_for_status()
    return response.json()["access_token"]


def load_kbo_data(data_dir: Path) -> list[dict]:
    """Load and merge KBO CSV files"""
    from typing import Any

    enterprises: dict[str, dict[str, Any]] = {}

    # Load enterprise.csv
    with open(data_dir / "enterprise.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            enterprise_num = row["EnterpriseNumber"]
            enterprises[enterprise_num] = {
                "enterprise_number": enterprise_num,
                "status": row["Status"],
                "juridical_form": row["JuridicalForm"],
                "start_date": row["StartDate"],
                "denominations": [],
                "addresses": [],
                "activities": [],
                "contacts": {},
            }

    # Load denomination.csv
    with open(data_dir / "denomination.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_num = row["EntityNumber"]
            if entity_num in enterprises:
                enterprises[entity_num]["denominations"].append(row["Denomination"])
                # Use first denomination as primary name
                if not enterprises[entity_num].get("name"):
                    enterprises[entity_num]["name"] = row["Denomination"]

    # Load address.csv
    with open(data_dir / "address.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_num = row["EntityNumber"]
            if entity_num in enterprises:
                enterprises[entity_num]["addresses"].append(
                    {
                        "type": row["TypeOfAddress"],
                        "country": row["CountryNL"],
                        "street": row["StreetNL"],
                        "house_number": row["HouseNumber"],
                        "zipcode": row["Zipcode"],
                        "municipality": row["MunicipalityNL"],
                    }
                )

    # Load activity.csv
    with open(data_dir / "activity.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_num = row["EntityNumber"]
            if entity_num in enterprises:
                enterprises[entity_num]["activities"].append(row["NaceCode"])

    # Load contact.csv
    with open(data_dir / "contact.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_num = row["EntityNumber"]
            if entity_num in enterprises:
                contact_type = row["ContactType"].lower()
                enterprises[entity_num]["contacts"][contact_type] = row["Value"]

    return list(enterprises.values())


def transform_to_tracardi_profile(enterprise: dict) -> dict:
    """Convert KBO record to Tracardi profile format"""
    contacts = enterprise.get("contacts", {})
    enterprise_num = enterprise["enterprise_number"]

    # Format ID like existing profiles (with dots)
    formatted_id = (
        f"{enterprise_num[:4]}.{enterprise_num[4:7]}.{enterprise_num[7:]}"
        if len(enterprise_num) == 10
        else enterprise_num
    )

    # Build traits
    traits = {
        "kbo": {
            "enterpriseNumber": enterprise_num,
            "denominations": enterprise.get("denominations", []),
            "juridicalForm": enterprise.get("juridical_form"),
            "status": enterprise.get("status"),
            "startDate": enterprise.get("start_date"),
            "addresses": enterprise.get("addresses", []),
            "activities": enterprise.get("activities", []),
        }
    }

    # Add contacts to traits
    if contacts:
        traits["kbo"]["contacts"] = contacts

    # Build PII
    pii = {
        "name": enterprise.get(
            "name",
            enterprise.get("denominations", ["Unknown"])[0]
            if enterprise.get("denominations")
            else "Unknown",
        )
    }

    if "email" in contacts:
        pii["email"] = contacts["email"]
    if "tel" in contacts:
        pii["telephone"] = contacts["tel"]

    return {"id": formatted_id, "ids": [enterprise_num], "traits": traits, "pii": pii}


def ingest_profiles_to_tracardi(profiles: list[dict], token: str) -> dict:
    """Bulk ingest profiles to Tracardi"""
    url = f"{TRACARDI_HOST}/profiles/import"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    response = requests.post(url, json=profiles, headers=headers, timeout=60)  # 60s timeout
    return response


def main():
    logger.info("Starting KBO data ingestion")

    # Get access token
    logger.info("Authenticating with Tracardi")
    token = get_access_token()
    logger.info("Authentication successful")

    # Load data
    data_dir = Path("/home/ff/.openclaw/workspace/CDP_Merged/data/kbo")
    logger.info("Loading KBO data", extra={"data_dir": str(data_dir)})
    enterprises = load_kbo_data(data_dir)
    logger.info("Loaded enterprises", extra={"count": len(enterprises)})

    # Transform
    logger.info("Transforming to Tracardi profiles")
    profiles = [transform_to_tracardi_profile(e) for e in enterprises]

    # Ingest
    logger.info("Ingesting profiles to Tracardi", extra={"count": len(profiles)})
    response = ingest_profiles_to_tracardi(profiles, token)

    if response.status_code == 200:
        result = response.json()
        logger.info("Ingestion complete", extra={"result": result})
    else:
        logger.error(
            "Ingestion failed", extra={"status_code": response.status_code, "error": response.text}
        )


if __name__ == "__main__":
    main()
