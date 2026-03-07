"""
CBE Open Data integration.

Cross-references with official CBE (Crossroads Bank for Enterprises) data.
Cost: €0 (public data)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx

from src.core.logger import get_logger
from src.enrichment.base import BaseEnricher

logger = get_logger(__name__)


class CBEIntegrationEnricher(BaseEnricher):
    """
    Enrich profiles with official CBE Open Data.

    Data source: https://economie.fgov.be/en/themes/enterprises/crossroads-bank

    Provides:
    - Employee count (when available)
    - Revenue estimates
    - Industry classifications
    - Status verification
    """

    # CBE Open Data API endpoints
    CBE_API_BASE = "https://kbopub.economie.fgov.be/kbo-open-data/api/v1"

    def __init__(
        self,
        cache_dir: str | None = "./data/cache",
        cache_file: str = "cbe_cache.json",
        data_dir: str | None = "./data/cbe",
        use_api: bool = True,
    ):
        super().__init__(cache_dir=cache_dir, cache_file=cache_file)
        self.data_dir = Path(data_dir) if data_dir else None
        self.use_api = use_api
        self._cbe_data: dict | None = None

        # NACE code to industry mapping (simplified)
        self.nace_to_industry = self._load_nace_mapping()

    def _load_nace_mapping(self) -> dict:
        """Load NACE to industry mapping."""
        return {
            # Section A - Agriculture
            **{f"{i:02d}{j:02d}0": "Agriculture" for i in range(1, 4) for j in range(10)},
            # Section B - Mining
            **{f"0{i}{j:02d}0": "Mining & Quarrying" for i in range(5, 10) for j in range(10)},
            # Section C - Manufacturing
            **{f"{i:02d}{j:02d}0": "Manufacturing" for i in range(10, 34) for j in range(10)},
            # Section D - Utilities
            **{f"{i:02d}{j:02d}0": "Electricity & Gas" for i in range(35, 37) for j in range(10)},
            # Section E - Water/Sewerage
            **{f"{i:02d}{j:02d}0": "Water & Waste" for i in range(36, 40) for j in range(10)},
            # Section F - Construction
            **{f"{i:02d}{j:02d}0": "Construction" for i in range(41, 44) for j in range(10)},
            # Section G - Wholesale/Retail
            **{f"{i:02d}{j:02d}0": "Wholesale & Retail" for i in range(45, 48) for j in range(10)},
            # Section H - Transportation
            **{f"{i:02d}{j:02d}0": "Transportation" for i in range(49, 54) for j in range(10)},
            # Section I - Accommodation/Food
            **{
                f"{i:02d}{j:02d}0": "Accommodation & Food"
                for i in range(55, 57)
                for j in range(10)
            },
            # Section J - Information/Communication
            **{
                f"{i:02d}{j:02d}0": "IT & Communications" for i in range(58, 64) for j in range(10)
            },
            # Section K - Financial
            **{f"{i:02d}{j:02d}0": "Financial Services" for i in range(64, 67) for j in range(10)},
            # Section L - Real Estate
            **{f"{i:02d}{j:02d}0": "Real Estate" for i in range(68, 69) for j in range(10)},
            # Section M - Professional Services
            **{
                f"{i:02d}{j:02d}0": "Professional Services"
                for i in range(69, 76)
                for j in range(10)
            },
            # Section N - Administrative
            **{
                f"{i:02d}{j:02d}0": "Administrative Services"
                for i in range(77, 83)
                for j in range(10)
            },
            # Section O - Public Administration
            **{f"84{i}0": "Public Administration" for i in range(10)},
            # Section P - Education
            **{f"85{i}0": "Education" for i in range(10)},
            # Section Q - Health
            **{f"{i:02d}{j:02d}0": "Healthcare" for i in range(86, 89) for j in range(10)},
            # Section R - Arts/Entertainment
            **{
                f"{i:02d}{j:02d}0": "Arts & Entertainment"
                for i in range(90, 93)
                for j in range(10)
            },
            # Section S - Other Services
            **{f"{i:02d}{j:02d}0": "Other Services" for i in range(94, 97) for j in range(10)},
            # Section T - Household Employers
            **{f"97{i}0": "Household Employers" for i in range(10)},
            # Section U - Extraterritorial
            **{f"99{i}0": "Extraterritorial" for i in range(10)},
        }

    def _get_kbo_number(self, profile: dict) -> str | None:
        """Extract KBO number from profile."""
        # PostgreSQL v2.0 format (direct field)
        kbo = profile.get("kbo_number")
        if kbo:
            return self._normalize_kbo(kbo)

        # Legacy Tracardi format (traits structure)
        traits = profile.get("traits", {})
        kbo = traits.get("enterprise_number") or traits.get("kbo_number")
        if kbo:
            return self._normalize_kbo(kbo)

        # From kbo structure
        kbo_data = traits.get("kbo", {})
        if kbo_data:
            kbo = kbo_data.get("enterprise_number") or kbo_data.get("entity_number")
            if kbo:
                return self._normalize_kbo(kbo)

        return None

    def _normalize_kbo(self, kbo: str) -> str:
        """Normalize KBO number to standard format."""
        # Remove non-digits
        digits = "".join(c for c in kbo if c.isdigit())

        # Belgian KBO numbers are 10 digits
        # Format: 0XXX.XXX.XXX
        if len(digits) == 9:
            digits = "0" + digits

        return digits

    def _get_nace_codes(self, profile: dict) -> list[str]:
        """Extract NACE codes from profile."""
        nace_codes: list[str] = []

        # PostgreSQL v2.0 format (industry.nace_code)
        industry = profile.get("industry", {})
        if industry and industry.get("nace_code"):
            nace_codes.append(str(industry["nace_code"]))

        # Legacy Tracardi format (traits structure)
        traits = profile.get("traits", {})
        codes = traits.get("nace_codes", [])
        if isinstance(codes, list):
            nace_codes.extend(str(c) for c in codes)

        kbo = traits.get("kbo", {})
        if kbo:
            activities = kbo.get("activities", [])
            if isinstance(activities, list):
                for activity in activities:
                    if isinstance(activity, dict):
                        code = activity.get("naceCode") or activity.get("nace_code")
                        if code:
                            nace_codes.append(str(code))

        return list(set(nace_codes))  # Remove duplicates

    def _classify_industry(self, nace_codes: list[str]) -> str | None:
        """Classify industry from NACE codes."""
        if not nace_codes:
            return None

        # Use first/main NACE code
        main_nace = nace_codes[0]

        # Try exact match first
        if main_nace in self.nace_to_industry:
            return self.nace_to_industry[main_nace]

        # Try section match (first 2 digits)
        section = main_nace[:2] + "000"
        if section in self.nace_to_industry:
            return self.nace_to_industry[section]

        # Try division match (first 3 digits + 0)
        division = main_nace[:3] + "0"
        if division in self.nace_to_industry:
            return self.nace_to_industry[division]

        return "Unknown"

    def _estimate_company_size(self, nace_codes: list[str], start_date: str | None) -> dict:
        """
        Estimate company size based on NACE and age.

        This is a heuristic based on typical patterns in Belgian business data.
        """
        # Default: unknown
        size_category = "unknown"
        estimated_employees = None

        # Some NACE codes tend to be smaller businesses
        small_business_naces = ["47110", "47190", "56101", "68201", "86210"]

        # Some tend to be larger
        large_business_naces = ["64201", "70101", "72110", "55101", "56510"]

        main_nace = nace_codes[0] if nace_codes else None

        if main_nace:
            if main_nace in small_business_naces:
                size_category = "micro_small"
                estimated_employees = "1-10"
            elif main_nace in large_business_naces:
                size_category = "large"
                estimated_employees = "250+"
            else:
                size_category = "unknown"

        return {
            "category": size_category,
            "estimated_employees": estimated_employees,
            "method": "heuristic",
        }

    async def fetch_cbe_data(self, kbo_number: str) -> dict | None:
        """
        Fetch CBE data from API.

        Args:
            kbo_number: Normalized KBO number

        Returns:
            CBE data dict or None
        """
        if not self.use_api:
            return None

        cache_key = f"cbe_{kbo_number}"
        cached = await self.cache.get(cache_key, default="MISS")
        if cached != "MISS":
            return cached

        try:
            async with httpx.AsyncClient() as client:
                # Note: This is a placeholder - actual CBE API may differ
                # The CBE publishes data via opendata store, not always REST API
                url = f"{self.CBE_API_BASE}/enterprise/{kbo_number}"
                response = await client.get(url, timeout=10.0)

                if response.status_code == 200:
                    data = response.json()
                    await self.cache.set(cache_key, data)
                    return data

        except httpx.HTTPStatusError as e:
            logger.debug(
                f"CBE API HTTP error for {kbo_number}",
                extra={"status_code": e.response.status_code},
            )
        except httpx.RequestError as e:
            logger.debug(f"CBE API request error for {kbo_number}: {e}")

        await self.cache.set(cache_key, None)
        return None

    def can_enrich(self, profile: dict) -> bool:
        """Check if profile has KBO number or NACE codes."""
        return bool(self._get_kbo_number(profile) or self._get_nace_codes(profile))

    async def enrich_profile(self, profile: dict) -> dict:
        """
        Enrich profile with CBE data.

        Args:
            profile: Tracardi profile dict

        Returns:
            Enriched profile
        """
        self.stats.total += 1

        kbo_number = self._get_kbo_number(profile)
        nace_codes = self._get_nace_codes(profile)

        if not kbo_number and not nace_codes:
            self.stats.skipped += 1
            return profile

        if "traits" not in profile:
            profile["traits"] = {}

        # Add CBE enrichment
        from typing import Any

        cbe_enrichment: dict[str, Any] = {
            "enriched_at": datetime.now(UTC).isoformat(),
            "source": "cbe_open_data",
        }

        # Add KBO normalization
        if kbo_number:
            cbe_enrichment["kbo_normalized"] = kbo_number
            cbe_enrichment["kbo_formatted"] = (
                f"{kbo_number[:4]}.{kbo_number[4:7]}.{kbo_number[7:]}"
            )

        # Add industry classification
        if nace_codes:
            industry = self._classify_industry(nace_codes)
            if industry:
                cbe_enrichment["industry_sector"] = industry

            # Estimate company size
            traits = profile.get("traits", {})
            start_date = traits.get("start_date") or traits.get("foundation_date")
            size_info = self._estimate_company_size(nace_codes, start_date)
            cbe_enrichment["size_estimate"] = size_info

        # Try to fetch from CBE API
        if kbo_number and self.use_api:
            try:
                cbe_data = await self.fetch_cbe_data(kbo_number)
                if cbe_data:
                    cbe_enrichment["api_data"] = cbe_data

                    # Enhanced field extraction: Status
                    status = cbe_data.get("status", "") or cbe_data.get("enterpriseStatus", "")
                    if status:
                        cbe_enrichment["status"] = status
                        profile["traits"]["company_status"] = status

                    # Enhanced field extraction: Officers
                    officers = cbe_data.get("officers", []) or cbe_data.get("functions", [])
                    if officers:
                        cbe_enrichment["officers"] = officers

                    # Enhanced field extraction: Linkages
                    linkages = cbe_data.get("linkages", []) or cbe_data.get("related_entities", [])
                    if linkages:
                        cbe_enrichment["linked_entities"] = linkages

                    # Extract contacts
                    emails = []
                    phones = []

                    if cbe_data.get("email"):
                        emails.append(cbe_data["email"])
                    if cbe_data.get("phone"):
                        phones.append(cbe_data["phone"])
                    if cbe_data.get("telephone"):
                        phones.append(cbe_data["telephone"])

                    for contact in cbe_data.get("contacts", []) + cbe_data.get(
                        "contactPoints", []
                    ):
                        if isinstance(contact, dict):
                            if (
                                contact.get("type") == "EMAIL"
                                or contact.get("contactType") == "EMAIL"
                            ):
                                email_val = (
                                    contact.get("value")
                                    or contact.get("Value")
                                    or contact.get("email")
                                )
                                if email_val:
                                    emails.append(email_val)
                            elif (
                                contact.get("type") == "PHONE"
                                or contact.get("contactType") == "PHONE"
                            ):
                                phone_val = (
                                    contact.get("value")
                                    or contact.get("Value")
                                    or contact.get("telephone")
                                    or contact.get("phone")
                                )
                                if phone_val:
                                    phones.append(phone_val)

                            # check direct attributes on contactPoint
                            if contact.get("email"):
                                emails.append(contact.get("email"))
                            if contact.get("telephone"):
                                phones.append(contact.get("telephone"))
                            if contact.get("tel"):
                                phones.append(contact.get("tel"))

                    emails = list({e.lower().strip() for e in emails if e})
                    phones = list({p.strip() for p in phones if p})

                    # Apply emails
                    if emails:
                        existing_emails = set(
                            profile["traits"].get("emails", [])
                            if isinstance(profile["traits"].get("emails"), list)
                            else []
                        )
                        existing_email = profile["traits"].get("email")
                        if existing_email:
                            existing_emails.add(existing_email)

                        new_emails = [e for e in emails if e not in existing_emails]
                        if new_emails:
                            if "emails" not in profile["traits"]:
                                profile["traits"]["emails"] = []
                            if isinstance(profile["traits"]["emails"], list):
                                profile["traits"]["emails"].extend(new_emails)
                            else:
                                profile["traits"]["emails"] = new_emails

                            if not profile["traits"].get("email"):
                                profile["traits"]["email"] = new_emails[0]

                    # Apply phones
                    if phones:
                        if not (
                            profile["traits"].get("phone")
                            or profile["traits"].get("contact_phone")
                            or profile["traits"].get("telephone")
                        ):
                            profile["traits"]["phone"] = phones[0]
                            profile["traits"]["phone_source"] = "cbe_open_data"

            except Exception as e:
                logger.debug(f"Could not fetch CBE data: {e}")

        profile["traits"]["cbe_enrichment"] = cbe_enrichment

        self.stats.success += 1
        return profile

    async def process_change_notification(self, notification: dict) -> dict | None:
        """
        Consume a CBE change notification (e.g. from a polling service or webhook).
        Expected events: liquidation, merger, branch opening, address change.
        Returns a dict of updates to apply to the profile.
        """
        kbo_number = notification.get("kbo_number") or notification.get("enterpriseNumber")
        if not kbo_number:
            return None

        event_type = notification.get("event_type") or notification.get("type")
        timestamp = notification.get("timestamp")

        updates = {
            "last_cbe_update": timestamp or datetime.now(UTC).isoformat(),
            "latest_event": event_type,
        }

        if event_type in ["LIQUIDATION", "BANKRUPTCY"]:
            updates["company_status"] = "inactive"
            updates["status_reason"] = event_type
        elif event_type in ["MERGER", "ACQUISITION"]:
            updates["company_status"] = "merged"
            updates["linked_entities"] = notification.get("related_entities", [])
        elif event_type == "ADDRESS_CHANGE":
            updates["address_updated"] = True

        return {"kbo_number": self._normalize_kbo(kbo_number), "updates": updates}
