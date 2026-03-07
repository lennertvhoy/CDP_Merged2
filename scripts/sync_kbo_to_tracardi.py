#!/usr/bin/env python3
"""
Sync POC-relevant KBO profiles from the KBO zip archive into Tracardi.
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
import sys
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, "/home/ff/.openclaw/workspace/repos/CDP_Merged")

from src.core.logger import get_logger

logger = get_logger(__name__)


DEFAULT_TRACARDI_API_URL = "http://137.117.212.154:8686"
DEFAULT_KBO_ZIP_PATH = Path(
    "/home/ff/.openclaw/workspace/repos/CDP_Merged/KboOpenData_0285_2026_02_27_Full.zip"
)
DEFAULT_BATCH_SIZE = 100
DEFAULT_TARGET_COUNT = 10000
DEFAULT_VERIFY_ATTEMPTS = 5
DEFAULT_VERIFY_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class SyncConfig:
    tracardi_api_url: str
    tracardi_username: str
    tracardi_password: str
    kbo_zip_path: Path
    batch_size: int
    target_count: int
    verify_attempts: int
    verify_delay_seconds: float


# East Flanders cities (Dutch names as they appear in KBO data)
EAST_FLANDERS_CITIES = {
    "Gent",
    "Aalst",
    "Sint-Niklaas",
    "Lokeren",
    "Dendermonde",
    "Oudenaarde",
    "Eeklo",
    "Deinze",
    "Waregem",
    "Zottegem",
    "Aalter",
    "Wetteren",
    "Kruibeke",
    "Evergem",
    "Destelbergen",
    "Lochristi",
    "Lede",
    "Zele",
    "Hamme",
    "Waasmunster",
    "Bornem",
    "Temse",
    "Sint-Gillis-Waas",
    "Stekene",
    "Maldegem",
    "Ninove",
    "Geraardsbergen",
    "Ronse",
    "Sint-Lievens-Houtem",
    "Beveren",
    "Zwijndrecht",
    "Haaltert",
    "Erpe-Mere",
    "Berlare",
    "Moerbeke-Waas",
    "Wachtebeke",
    "Steendorp",
    "Elversele",
    "Tielrode",
    "Bazel",
    "Rupelmonde",
    "Kallo",
    "Melsele",
    "Doel",
    "Kieldrecht",
    "Verrebroek",
    "Vrasene",
    "Hingene",
    "Marnix",
    "Sint-Amands",
    "Mariekerke",
    "Terhagen",
    "Booischot",
    "Heist-op-den-Berg",
    "Hallaar",
    "Itegem",
    "Wiekevorst",
    "Schriek",
    "Grootlo",
    "Houtvenne",
    "Massenhoven",
    "Rijkevorsel",
    "Acastus",
    "Morkhoven",
}

# IT-related NACE code prefixes
IT_NACE_PREFIXES = ("62", "63", "58.2", "61")

# Postal code ranges for East Flanders (9000-9999)
EAST_FLANDERS_POSTAL_PREFIXES = ("9",)


def load_runtime_config(env: Mapping[str, str] | None = None) -> SyncConfig:
    """Load runtime configuration from environment variables."""
    source = dict(os.environ if env is None else env)

    tracardi_username = source.get("TRACARDI_USERNAME")
    if not tracardi_username:
        raise RuntimeError("TRACARDI_USERNAME must be set before running sync_kbo_to_tracardi.py")

    tracardi_password = source.get("TRACARDI_PASSWORD")
    if not tracardi_password:
        raise RuntimeError("TRACARDI_PASSWORD must be set before running sync_kbo_to_tracardi.py")

    return SyncConfig(
        tracardi_api_url=source.get("TRACARDI_API_URL", DEFAULT_TRACARDI_API_URL),
        tracardi_username=tracardi_username,
        tracardi_password=tracardi_password,
        kbo_zip_path=Path(source.get("KBO_ZIP_PATH", str(DEFAULT_KBO_ZIP_PATH))),
        batch_size=int(source.get("TRACARDI_BATCH_SIZE", str(DEFAULT_BATCH_SIZE))),
        target_count=int(source.get("TRACARDI_TARGET_COUNT", str(DEFAULT_TARGET_COUNT))),
        verify_attempts=int(source.get("TRACARDI_VERIFY_ATTEMPTS", str(DEFAULT_VERIFY_ATTEMPTS))),
        verify_delay_seconds=float(
            source.get(
                "TRACARDI_VERIFY_DELAY_SECONDS",
                str(DEFAULT_VERIFY_DELAY_SECONDS),
            )
        ),
    )


def load_enterprises_from_zip(zip_path: Path) -> dict[str, dict[str, str]]:
    """Load enterprises from zip file."""
    print(f"Loading enterprises from {zip_path}...")

    enterprises: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("enterprise.csv") as handle:
            reader = csv.DictReader(io.TextIOWrapper(handle, "utf-8"))
            for row in reader:
                kbo = row["EnterpriseNumber"].replace(".", "")
                enterprises[kbo] = {
                    "kbo_number": kbo,
                    "status": row["Status"],
                    "juridical_form": row["JuridicalForm"],
                    "start_date": row["StartDate"],
                }

    print(f"Loaded {len(enterprises)} enterprises")
    return enterprises


def load_addresses_from_zip(zip_path: Path) -> dict[str, dict[str, str]]:
    """Load registered-office addresses from zip file."""
    print("Loading addresses...")

    addresses: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("address.csv") as handle:
            reader = csv.DictReader(io.TextIOWrapper(handle, "utf-8"))
            for row in reader:
                if row["TypeOfAddress"] != "REGO":
                    continue
                kbo = row["EntityNumber"].replace(".", "")
                addresses[kbo] = {
                    "zipcode": row["Zipcode"],
                    "city": row["MunicipalityNL"],
                    "street": row["StreetNL"],
                    "house_number": row["HouseNumber"],
                    "box": row["Box"],
                    "country": "BE",
                }

    print(f"Loaded {len(addresses)} addresses")
    return addresses


def load_activities_from_zip(zip_path: Path) -> dict[str, list[dict[str, str]]]:
    """Load activities (NACE codes) from zip file."""
    print("Loading activities...")

    activities: dict[str, list[dict[str, str]]] = {}
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("activity.csv") as handle:
            reader = csv.DictReader(io.TextIOWrapper(handle, "utf-8"))
            for row in reader:
                kbo = row["EntityNumber"].replace(".", "")
                activities.setdefault(kbo, []).append(
                    {
                        "nace_code": row["NaceCode"],
                        "classification": row["Classification"],
                        "version": row["NaceVersion"],
                    }
                )

    print(f"Loaded activities for {len(activities)} enterprises")
    return activities


def load_denominations_from_zip(zip_path: Path) -> dict[str, str]:
    """Load company names from zip file."""
    print("Loading denominations...")

    names: dict[str, str] = {}
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("denomination.csv") as handle:
            reader = csv.DictReader(io.TextIOWrapper(handle, "utf-8"))
            for row in reader:
                kbo = row["EntityNumber"].replace(".", "")
                name = row.get("Denomination", "")
                denomination_type = row.get("TypeOfDenomination", "")
                if not name:
                    continue
                if kbo not in names or denomination_type == "001":
                    names[kbo] = name

    print(f"Loaded names for {len(names)} enterprises")
    return names


def filter_poc_companies(
    enterprises: dict[str, dict[str, str]],
    addresses: dict[str, dict[str, str]],
    activities: dict[str, list[dict[str, str]]],
    names: dict[str, str],
    *,
    target_count: int | None = None,
) -> list[dict[str, object]]:
    """Filter companies matching the POC criteria."""
    print("Filtering for POC criteria...")

    effective_target = DEFAULT_TARGET_COUNT if target_count is None else target_count
    filtered: list[dict[str, object]] = []

    for kbo, enterprise in enterprises.items():
        if enterprise["status"] != "AC":
            continue

        address = addresses.get(kbo)
        if not address:
            continue

        city = address.get("city", "")
        zipcode = address.get("zipcode", "")
        is_east_flanders = city in EAST_FLANDERS_CITIES or any(
            zipcode.startswith(prefix) for prefix in EAST_FLANDERS_POSTAL_PREFIXES
        )
        if not is_east_flanders:
            continue

        company_activities = activities.get(kbo, [])
        is_it = False
        main_nace = None
        all_nace_codes: list[str] = []

        for activity in company_activities:
            nace = activity["nace_code"]
            all_nace_codes.append(nace)
            if any(nace.startswith(prefix) for prefix in IT_NACE_PREFIXES):
                is_it = True
                if activity["classification"] == "MAIN" and not main_nace:
                    main_nace = nace

        company_data: dict[str, object] = {
            "kbo_number": kbo,
            "company_name": names.get(kbo, f"Company_{kbo}"),
            "status": enterprise["status"],
            "legal_form": enterprise["juridical_form"],
            "street_address": (
                f"{address.get('street', '')} {address.get('house_number', '')}".strip()
            ),
            "city": city,
            "postal_code": zipcode,
            "country": address.get("country", "BE"),
            "nace_code": main_nace or (all_nace_codes[0] if all_nace_codes else None),
            "all_nace_codes": all_nace_codes,
            "is_it_company": is_it,
            "province": "Oost-Vlaanderen",
        }

        if is_it:
            filtered.insert(0, company_data)
        else:
            filtered.append(company_data)

        if effective_target > 0 and len(filtered) >= effective_target * 2:
            break

    filtered.sort(key=lambda item: (not bool(item["is_it_company"]), str(item["company_name"])))
    if effective_target > 0:
        filtered = filtered[:effective_target]

    it_count = sum(1 for company in filtered if company["is_it_company"])
    print(f"Found {len(filtered)} companies ({it_count} IT-related)")
    return filtered


def transform_to_tracardi(company: Mapping[str, object]) -> dict[str, object]:
    """Transform company data to Tracardi format."""
    now_iso = datetime.now().isoformat()
    traits = {
        "company_name": company["company_name"],
        "kbo_number": company["kbo_number"],
        "street_address": company["street_address"],
        "city": company["city"],
        "postal_code": company["postal_code"],
        "country": company["country"],
        "province": company["province"],
        "legal_form": company["legal_form"],
        "nace_code": company["nace_code"],
        "status": company["status"],
        "is_it_company": company["is_it_company"],
        "data_source": "KBO_Belgium",
        "segment_tags": ["poc_test", "oost_vlaanderen"],
    }
    traits = {key: value for key, value in traits.items() if value is not None}

    return {
        "id": company["kbo_number"],
        "traits": traits,
        "metadata": {
            "time": {
                "insert": now_iso,
                "create": now_iso,
                "update": now_iso,
            },
            "system": {
                "inserted": now_iso,
                "created": now_iso,
                "updated": now_iso,
            },
        },
    }


async def get_tracardi_token(config: SyncConfig) -> str:
    """Authenticate to Tracardi, falling back to JSON auth for older deployments."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        form_response = await client.post(
            f"{config.tracardi_api_url}/user/token",
            data={
                "username": config.tracardi_username,
                "password": config.tracardi_password,
                "grant_type": "password",
                "scope": "",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if form_response.status_code != 422:
            form_response.raise_for_status()
            return form_response.json()["access_token"]

        json_response = await client.post(
            f"{config.tracardi_api_url}/user/token",
            json={
                "username": config.tracardi_username,
                "password": config.tracardi_password,
            },
        )
        json_response.raise_for_status()
        return json_response.json()["access_token"]


async def import_profiles_to_tracardi(
    companies: list[dict[str, object]],
    token: str,
    config: SyncConfig,
) -> tuple[int, int]:
    """Import profiles to Tracardi in batches."""
    headers = {"Authorization": f"Bearer {token}"}
    total_imported = 0
    total_failed = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        for index in range(0, len(companies), config.batch_size):
            batch = companies[index : index + config.batch_size]
            tracardi_profiles = [transform_to_tracardi(company) for company in batch]

            success = False
            error_message = None
            for endpoint in [f"{config.tracardi_api_url}/profiles/import"]:
                try:
                    response = await client.post(
                        endpoint,
                        json=tracardi_profiles,
                        headers=headers,
                    )
                    if response.status_code == 200:
                        print(
                            f"Batch {index // config.batch_size + 1}/"
                            f"{(len(companies) - 1) // config.batch_size + 1}: "
                            f"{len(batch)} profiles"
                        )
                        total_imported += len(batch)
                        success = True
                        break
                    error_message = f"{response.status_code}: {response.text[:100]}"
                except Exception as exc:  # pragma: no cover - network failure path
                    error_message = str(exc)[:100]

            if not success:
                print(f"Batch {index // config.batch_size + 1} failed: {error_message}")
                total_failed += len(batch)

            await asyncio.sleep(0.3)

    return total_imported, total_failed


async def verify_sync(token: str, config: SyncConfig) -> int:
    """Verify profiles were synced."""
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(config.verify_attempts):
            try:
                response = await client.get(
                    f"{config.tracardi_api_url}/profiles/count",
                    headers=headers,
                )
                if response.status_code == 200:
                    count = response.json().get("count", 0)
                    print(f"Total profiles in Tracardi: {count}")
                    return int(count)
            except Exception:  # pragma: no cover - fallback path
                pass

            try:
                response = await client.post(
                    f"{config.tracardi_api_url}/profiles/search",
                    json={"limit": 1},
                    headers=headers,
                )
                if response.status_code == 200:
                    total = response.json().get("total", 0)
                    print(f"Total profiles in Tracardi (via search): {total}")
                    return int(total)
            except Exception:  # pragma: no cover - fallback path
                pass

            if attempt < config.verify_attempts - 1:
                await asyncio.sleep(config.verify_delay_seconds)

    return 0


async def main(config: SyncConfig) -> int:
    print("=" * 70)
    print("KBO to Tracardi Sync - POC Profile Import")
    print("=" * 70)
    print(f"Target: {config.target_count} companies from East Flanders")
    print(f"Source: {config.kbo_zip_path}")
    print(f"Tracardi: {config.tracardi_api_url}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    print("Loading data from KBO zip file...")
    enterprises = load_enterprises_from_zip(config.kbo_zip_path)
    addresses = load_addresses_from_zip(config.kbo_zip_path)
    activities = load_activities_from_zip(config.kbo_zip_path)
    names = load_denominations_from_zip(config.kbo_zip_path)

    companies = filter_poc_companies(
        enterprises,
        addresses,
        activities,
        names,
        target_count=config.target_count,
    )
    if not companies:
        print("No matching companies found")
        return 1

    print(f"Selected top {len(companies)} companies for import")
    print("Authenticating with Tracardi...")
    try:
        token = await get_tracardi_token(config)
        print("Authenticated")
    except Exception as exc:
        print(f"Authentication failed: {exc}")
        return 1

    print(f"Importing {len(companies)} companies to Tracardi...")
    imported, failed = await import_profiles_to_tracardi(companies, token, config)

    print("Verifying sync...")
    count = await verify_sync(token, config)

    print("=" * 70)
    print("SYNC SUMMARY")
    print("=" * 70)
    print(f"Companies selected: {len(companies)}")
    print(f"Successfully imported: {imported}")
    print(f"Failed to import: {failed}")
    print(f"Total in Tracardi: {count}")

    it_count = sum(1 for company in companies if company["is_it_company"])
    print(f"IT companies in selection: {it_count}")
    print(f"Cities covered: {len({company['city'] for company in companies})}")

    success_rate = (imported / len(companies) * 100) if companies else 0
    print(f"Success rate: {success_rate:.1f}%")

    if success_rate >= 90:
        print("SUCCESS: Sync completed with high success rate")
        return 0
    if success_rate >= 50:
        print("PARTIAL: Some profiles synced, but with issues")
        return 0

    print("FAILED: Low success rate")
    return 1


if __name__ == "__main__":
    runtime_config = load_runtime_config()
    sys.exit(asyncio.run(main(runtime_config)))
