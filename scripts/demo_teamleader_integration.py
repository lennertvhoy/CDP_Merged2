#!/usr/bin/env python3
"""
Teamleader Integration Demo for CDP_Merged.

Demonstrates the capability to sync CRM data, contacts, deals, and activities
from Teamleader to the CDP for unified customer insights.

The demo auto-detects local `.env.teamleader` credentials and upgrades the
company, contacts, and deals steps to live reads when possible. Activity
history remains mock-backed until a verified live path is wired in.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from typing import Any

sys.path.insert(0, "/home/ff/.openclaw/workspace/repos/CDP_Merged")

from src.core.logger import get_logger
from src.services.teamleader import TeamleaderClient, load_teamleader_env_file

logger = get_logger(__name__)
TEAMLEADER_APP_BASE_URL = "https://app.teamleader.eu"


def _first_value(*values: Any) -> Any:
    """Return the first non-empty value."""
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    """Return a dict value or an empty dict."""
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    """Return a list value or an empty list."""
    return value if isinstance(value, list) else []


def _stringify_name(first_name: str | None, last_name: str | None, fallback: str) -> str:
    parts = [part.strip() for part in (first_name or "", last_name or "") if part and part.strip()]
    if parts:
        return " ".join(parts)
    return fallback


def _extract_email(record: dict[str, Any]) -> str | None:
    emails = _as_list(record.get("emails"))
    for email in emails:
        if isinstance(email, dict):
            value = _first_value(email.get("email"), email.get("value"), email.get("type"))
            if value:
                return str(value)
        elif email:
            return str(email)
    return _first_value(record.get("email"), record.get("primary_email"))


def _extract_phone(record: dict[str, Any]) -> str | None:
    phone_fields = (
        record.get("phone"),
        record.get("mobile"),
        record.get("telephone"),
        record.get("primary_phone"),
    )
    for value in phone_fields:
        if value:
            return str(value)

    for field in ("telephones", "phones", "phone_numbers"):
        for phone in _as_list(record.get(field)):
            if isinstance(phone, dict):
                value = _first_value(phone.get("number"), phone.get("value"), phone.get("phone"))
                if value:
                    return str(value)
            elif phone:
                return str(phone)

    return None


def _extract_money(value: Any) -> float:
    """Return a best-effort numeric value from a Teamleader money field."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    if isinstance(value, dict):
        for key in ("amount", "value", "total", "base_amount"):
            nested_value = value.get(key)
            if nested_value is not None:
                return _extract_money(nested_value)
    return 0.0


class TeamleaderDemo:
    """Demo client showing Teamleader CRM integration capabilities."""

    def __init__(self, full_pagination: bool = False, max_contacts: int = 50, max_deals: int = 50) -> None:
        self.base_url = "https://api.focus.teamleader.eu"
        self.demo_data = self._load_demo_data()
        self.teamleader_client = self._build_teamleader_client()
        self.provenance = "mock"
        self.source_modes = {
            "company": "mock",
            "contacts": "mock",
            "deals": "mock",
            "activities": "mock",
        }
        self.company: dict[str, Any] = self.demo_data["company"]
        self.contacts: list[dict[str, Any]] = list(self.demo_data["contacts"])
        self.deals: list[dict[str, Any]] = list(self.demo_data["deals"])
        self.activities: list[dict[str, Any]] = list(self.demo_data["activities"])

        # Pagination settings
        self.full_pagination = full_pagination
        self.max_contacts = max_contacts
        self.max_deals = max_deals
        self.rate_limit_hits = 0
        self.pages_fetched = {"contacts": 0, "deals": 0, "activities": 0}

    @property
    def mode_description(self) -> str:
        """Describe how the Teamleader demo will run."""
        if self.teamleader_client:
            return "AUTO (local Teamleader credentials detected; live company/contact/deal reads plus best-effort events when auth succeeds)"
        return "MOCK (no local Teamleader credentials detected)"

    def _refresh_provenance(self) -> None:
        """Keep the top-level provenance aligned with per-surface source modes."""
        modes = set(self.source_modes.values())
        if modes == {"real"}:
            self.provenance = "real"
        elif "real" in modes:
            self.provenance = "hybrid"
        else:
            self.provenance = "mock"

    def _build_teamleader_client(self) -> TeamleaderClient | None:
        load_teamleader_env_file()
        if not TeamleaderClient.is_configured():
            return None

        try:
            return TeamleaderClient.from_env()
        except Exception as exc:
            logger.warning("teamleader_demo_client_init_failed", error=str(exc))
            return None

    def _load_demo_data(self) -> dict[str, Any]:
        """Load realistic demo data for Teamleader."""
        return {
            "company": {
                "id": "tl_company_12345",
                "name": "Tech Solutions B.V.",
                "address": {
                    "street": "Industrielaan 25",
                    "city": "Gent",
                    "postal_code": "9000",
                    "country": "BE",
                },
                "vat_number": "BE1234567890",
                "email": "info@techsolutions.be",
                "phone": "+32 9 123 45 67",
                "website": "www.techsolutions.be",
                "business_type": "Klant",
                "status": "Actief",
                "created_at": "2022-03-15T10:30:00Z",
                "source_record_url": "https://app.teamleader.eu/company/tl_company_12345",
            },
            "contacts": [
                {
                    "id": "tl_contact_001",
                    "first_name": "David",
                    "last_name": "Mertens",
                    "email": "david.mertens@techsolutions.be",
                    "phone": "+32 9 123 45 68",
                    "mobile": "+32 495 12 34 56",
                    "job_title": "Hoofd IT",
                    "decision_maker": True,
                    "last_contacted": "2024-03-01T14:30:00Z",
                    "source_record_url": "https://app.teamleader.eu/contact/tl_contact_001",
                },
                {
                    "id": "tl_contact_002",
                    "first_name": "Sarah",
                    "last_name": "Janssen",
                    "email": "sarah.janssen@techsolutions.be",
                    "phone": "+32 9 123 45 69",
                    "mobile": "+32 495 98 76 54",
                    "job_title": "Financial Controller",
                    "decision_maker": False,
                    "last_contacted": "2024-02-15T09:00:00Z",
                    "source_record_url": "https://app.teamleader.eu/contact/tl_contact_002",
                },
            ],
            "deals": [
                {
                    "id": "tl_deal_001",
                    "title": "Cloud Migration Project 2024",
                    "value": 45000.00,
                    "currency": "EUR",
                    "status": "open",
                    "phase": "Voorstel verstuurd",
                    "probability": 60,
                    "expected_close": "2024-04-15",
                    "created_at": "2024-01-20T11:00:00Z",
                    "source_record_url": "https://app.teamleader.eu/deal/tl_deal_001",
                },
                {
                    "id": "tl_deal_002",
                    "title": "Annual Support Contract",
                    "value": 18000.00,
                    "currency": "EUR",
                    "status": "won",
                    "phase": "Afgesloten",
                    "probability": 100,
                    "expected_close": "2024-01-15",
                    "created_at": "2023-12-10T09:30:00Z",
                    "source_record_url": "https://app.teamleader.eu/deal/tl_deal_002",
                },
            ],
            "activities": [
                {
                    "id": "tl_activity_001",
                    "type": "call",
                    "subject": "Follow-up cloud migration",
                    "date": "2024-03-01T14:30:00Z",
                    "user": "Account Manager",
                    "outcome": "Positive - awaiting budget approval",
                    "source_record_url": "https://app.teamleader.eu/activity/tl_activity_001",
                },
                {
                    "id": "tl_activity_002",
                    "type": "meeting",
                    "subject": "Quarterly review",
                    "date": "2024-02-15T10:00:00Z",
                    "user": "Sales Director",
                    "outcome": "Upsell opportunity identified",
                    "source_record_url": "https://app.teamleader.eu/activity/tl_activity_002",
                },
                {
                    "id": "tl_activity_003",
                    "type": "email",
                    "subject": "Proposal sent",
                    "date": "2024-01-25T16:00:00Z",
                    "user": "Account Manager",
                    "outcome": "Opened 3 times",
                    "source_record_url": "https://app.teamleader.eu/activity/tl_activity_003",
                },
            ],
        }

    def _normalize_company(self, record: dict[str, Any]) -> dict[str, Any]:
        address = _as_dict(_first_value(record.get("address"), record.get("primary_address")))
        company_id = str(_first_value(record.get("id"), "unknown-company"))
        return {
            "id": company_id,
            "name": str(_first_value(record.get("name"), "Unknown Teamleader company")),
            "address": {
                "street": _first_value(address.get("line_1"), address.get("street"), "Unknown"),
                "city": _first_value(address.get("city"), record.get("city"), "Unknown"),
                "postal_code": _first_value(
                    address.get("postal_code"), address.get("zip"), "Unknown"
                ),
                "country": _first_value(address.get("country"), record.get("country"), "Unknown"),
            },
            "vat_number": _first_value(
                record.get("vat_number"),
                record.get("enterprise_number"),
                "Unknown",
            ),
            "email": _extract_email(record),
            "phone": _extract_phone(record),
            "website": _first_value(record.get("website"), record.get("websites"), "Unknown"),
            "business_type": _first_value(
                record.get("type"), record.get("business_type"), "Customer"
            ),
            "status": _first_value(record.get("status"), "active"),
            "created_at": _first_value(record.get("created_at"), datetime.now().isoformat()),
            "source_record_url": f"{TEAMLEADER_APP_BASE_URL}/company/{company_id}",
        }

    def _normalize_contact(self, record: dict[str, Any]) -> dict[str, Any]:
        contact_id = str(_first_value(record.get("id"), "unknown-contact"))
        first_name = _first_value(record.get("first_name"), record.get("firstname"))
        last_name = _first_value(
            record.get("last_name"), record.get("lastname"), record.get("surname")
        )
        return {
            "id": contact_id,
            "first_name": str(_first_value(first_name, record.get("name"), "Unknown")),
            "last_name": str(_first_value(last_name, "")),
            "full_name": _stringify_name(
                str(first_name) if first_name else None,
                str(last_name) if last_name else None,
                str(_first_value(record.get("name"), "Unknown Contact")),
            ),
            "email": _extract_email(record),
            "phone": _extract_phone(record),
            "mobile": _first_value(record.get("mobile"), _extract_phone(record)),
            "job_title": _first_value(record.get("position"), record.get("job_title"), "Contact"),
            "decision_maker": bool(record.get("decision_maker", False)),
            "last_contacted": _first_value(
                record.get("updated_at"),
                record.get("created_at"),
                datetime.now().isoformat(),
            ),
            "source_record_url": f"{TEAMLEADER_APP_BASE_URL}/contact/{contact_id}",
        }

    def _normalize_deal(self, record: dict[str, Any]) -> dict[str, Any]:
        deal_id = str(_first_value(record.get("id"), "unknown-deal"))
        phase = _first_value(
            _as_dict(record.get("phase")).get("name"),
            record.get("phase"),
            "Open",
        )
        status = str(_first_value(record.get("status"), "open")).lower()
        return {
            "id": deal_id,
            "title": str(_first_value(record.get("title"), record.get("name"), "Untitled Deal")),
            "value": _extract_money(
                _first_value(
                    record.get("value"), record.get("total"), record.get("estimated_value")
                )
            ),
            "currency": _first_value(
                _as_dict(record.get("value")).get("currency"),
                _as_dict(record.get("total")).get("currency"),
                "EUR",
            ),
            "status": status,
            "phase": phase,
            "probability": int(_first_value(record.get("probability"), 0)),
            "expected_close": _first_value(
                record.get("expected_close"),
                record.get("estimated_closing_date"),
                "Unknown",
            ),
            "created_at": _first_value(record.get("created_at"), datetime.now().isoformat()),
            "source_record_url": f"{TEAMLEADER_APP_BASE_URL}/deal/{deal_id}",
        }

    def _show_rate_limit_status(self) -> None:
        """Display current rate limit status from the Teamleader client."""
        if not self.teamleader_client:
            return

        try:
            status = self.teamleader_client.get_rate_limit_status()
            remaining = status.get("remaining_calls", 100)
            max_calls = status.get("max_calls", 100)

            if remaining < 20:
                print(f"      ⚠️ Rate limit warning: {remaining}/{max_calls} calls remaining")
            else:
                print(f"      📊 Rate limit: {remaining}/{max_calls} calls remaining")
        except Exception as exc:
            logger.debug("rate_limit_status_failed", error=str(exc))

    def _normalize_event(self, record: dict[str, Any]) -> dict[str, Any]:
        event_id = str(_first_value(record.get("id"), "unknown-event"))
        starts_at = str(_first_value(record.get("starts_at"), datetime.now().isoformat()))
        title = str(_first_value(record.get("title"), "Untitled Teamleader event"))
        description = _first_value(record.get("description"), "")
        activity_type = _as_dict(record.get("activity_type"))
        event_type = str(
            _first_value(
                activity_type.get("type"),
                record.get("type"),
                "event",
            )
        )
        creator = _as_dict(record.get("creator"))
        creator_label = str(_first_value(creator.get("type"), "teamleader-user"))
        return {
            "id": event_id,
            "type": event_type,
            "subject": title,
            "date": starts_at,
            "user": creator_label,
            "outcome": str(description) if description else "Scheduled Teamleader event",
            "source_record_url": f"{TEAMLEADER_APP_BASE_URL}/event/{event_id}",
        }

    async def authenticate(self) -> dict[str, Any]:
        """Authenticate with Teamleader or fall back to mock mode."""
        print("🔐 Step 1: Authenticating with Teamleader...")

        if self.teamleader_client:
            print("   ├─ OAuth2 refresh-token flow via local .env.teamleader")
            print("   ├─ Live reads: companies.list, contacts.list, deals.list")
            print(
                "   └─ Activity history now attempts events.list before falling back to mock data"
            )
            try:
                access_token = self.teamleader_client.refresh_access_token()
            except Exception as exc:
                logger.warning("teamleader_demo_live_auth_failed", error=str(exc))
                print(f"   ⚠️ Live auth failed, falling back to mock data: {exc}\n")
                return {"access_token": "demo_token", "expires_in": 3600, "provenance": "mock"}

            self.provenance = "hybrid"
            self.source_modes["company"] = "real"
            self.source_modes["contacts"] = "real"
            self.source_modes["deals"] = "real"
            self._refresh_provenance()
            print("   ✅ Authenticated (live Teamleader access enabled)\n")
            return {
                "access_token": access_token,
                "expires_in": 3600,
                "provenance": self.provenance,
            }

        print("   ├─ OAuth2 Authorization Code flow")
        print("   ├─ Scopes: companies contacts deals activities")
        print("   └─ Redirect: https://cdp.it1.be/callback/teamleader")
        await asyncio.sleep(0.5)
        print("   ✅ Authenticated (Mock Mode)\n")
        return {"access_token": "demo_token", "expires_in": 3600, "provenance": "mock"}

    async def get_company_profile(self) -> dict[str, Any]:
        """Fetch company details from Teamleader."""
        print("🏢 Step 2: Fetching Company Profile...")

        if self.source_modes["company"] == "real" and self.teamleader_client:
            print("   ├─ POST /companies.list")
            print("   ├─ Payload: page[size]=1, page[number]=1")
            print("   └─ Using the first live company returned by Teamleader")

            payload = self.teamleader_client.list_records(
                "companies.list",
                page_size=1,
                page_number=1,
            )
            live_records = payload.get("data") or []
            if not live_records:
                raise RuntimeError("Live Teamleader company read returned no records")

            self.company = self._normalize_company(live_records[0])
            company = self.company
            print("   ✅ Retrieved:")
            print(f"      • Name: {company['name']}")
            print(f"      • Type: {company['business_type']}")
            print(
                f"      • Location: {company['address']['city']}, {company['address']['country']}"
            )
            print(f"      • Status: {company['status']}")
            print(f"      • Provenance: {self.source_modes['company']}\n")
            return company

        print("   ├─ GET /companies.info")
        print("   ├─ GET /companies.addresses")
        print("   └─ GET /companies.tags")
        await asyncio.sleep(0.5)
        company = self.company
        print("   ✅ Retrieved:")
        print(f"      • Name: {company['name']}")
        print(f"      • Type: {company['business_type']}")
        print(f"      • Location: {company['address']['city']}, {company['address']['country']}")
        print(f"      • Status: {company['status']}\n")
        return company

    async def get_contacts(self) -> list[dict[str, Any]]:
        """Fetch contacts associated with the company."""
        print("👥 Step 3: Fetching Contacts...")

        if self.source_modes["contacts"] == "real" and self.teamleader_client:
            if self.full_pagination:
                return await self._get_contacts_paginated()
            return await self._get_contacts_single_page()

        print("   ├─ GET /contacts.list")
        print("   ├─ Filter: company_id = current")
        print("   └─ Include: custom fields, decision maker status")
        await asyncio.sleep(0.5)
        print(f"   ✅ Retrieved {len(self.contacts)} contacts:")
        for contact in self.contacts:
            role = "🎯 Decision Maker" if contact["decision_maker"] else "👤 Contact"
            print(
                f"      • {contact['first_name']} {contact['last_name']} - {contact['job_title']} {role}"
            )
        print()
        return self.contacts

    async def _get_contacts_single_page(self) -> list[dict[str, Any]]:
        """Fetch contacts from a single page (backward compatible)."""
        print("   ├─ POST /contacts.list")
        print("   ├─ Payload: page[size]=5, page[number]=1")
        print("   └─ Decision-maker flag falls back to False when the live record omits it")

        payload = self.teamleader_client.list_records(
            "contacts.list",
            page_size=5,
            page_number=1,
        )
        live_records = payload.get("data") or []
        if not live_records:
            raise RuntimeError("Live Teamleader contacts read returned no records")

        self.contacts = [self._normalize_contact(record) for record in live_records]
        print(f"   ✅ Retrieved {len(self.contacts)} contacts:")
        for contact in self.contacts:
            role = "🎯 Decision Maker" if contact["decision_maker"] else "👤 Contact"
            print(f"      • {contact['full_name']} - {contact['job_title']} {role}")
        print(f"      • Provenance: {self.source_modes['contacts']}\n")
        return self.contacts

    async def _get_contacts_paginated(self) -> list[dict[str, Any]]:
        """Fetch contacts with full pagination and rate limit awareness."""
        print("   ├─ POST /contacts.list (paginated)")
        print(f"   ├─ Max contacts to fetch: {self.max_contacts}")
        print("   ├─ Rate limit: 100 requests/minute")
        print("   └─ Using list_all_records generator with progress reporting")

        contacts = []
        pages_fetched = 0

        try:
            for record in self.teamleader_client.list_all_records(
                "contacts.list",
                page_size=20,
                max_pages=(self.max_contacts + 19) // 20,  # Ceiling division
            ):
                contacts.append(self._normalize_contact(record))
                pages_fetched = self.teamleader_client.pages_fetched if hasattr(self.teamleader_client, 'pages_fetched') else pages_fetched + 1

                # Progress reporting every 10 contacts
                if len(contacts) % 10 == 0:
                    print(f"      📊 Fetched {len(contacts)} contacts...", end="\r")

                if len(contacts) >= self.max_contacts:
                    break

        except Exception as exc:
            logger.warning("teamleader_demo_contacts_pagination_error", error=str(exc))
            print(f"   ⚠️ Pagination error: {exc}")
            if not contacts:
                raise RuntimeError("Live Teamleader contacts read returned no records") from exc

        self.contacts = contacts[:self.max_contacts]
        self.pages_fetched["contacts"] = pages_fetched

        # Show rate limit status
        self._show_rate_limit_status()

        print(f"   ✅ Retrieved {len(self.contacts)} contacts:")
        for contact in self.contacts[:10]:  # Show first 10
            role = "🎯 Decision Maker" if contact["decision_maker"] else "👤 Contact"
            print(f"      • {contact['full_name']} - {contact['job_title']} {role}")
        if len(self.contacts) > 10:
            print(f"      ... and {len(self.contacts) - 10} more")
        print(f"      • Provenance: {self.source_modes['contacts']}")
        print(f"      • Pages fetched: {pages_fetched}\n")
        return self.contacts

    async def get_deals_pipeline(self) -> list[dict[str, Any]]:
        """Fetch deals and opportunities."""
        print("💼 Step 4: Fetching Deals Pipeline...")

        if self.source_modes["deals"] == "real" and self.teamleader_client:
            if self.full_pagination:
                return await self._get_deals_paginated()
            return await self._get_deals_single_page()

        print("   ├─ GET /deals.list")
        print("   ├─ Filter: company_id = current")
        print("   └─ Include: phase, value, probability, expected close")
        await asyncio.sleep(0.5)
        total_pipeline = sum(deal["value"] for deal in self.deals if deal["status"] == "open")
        total_won = sum(deal["value"] for deal in self.deals if deal["status"] == "won")

        print(f"   ✅ Retrieved {len(self.deals)} deals:")
        print(f"      • Active Pipeline: €{total_pipeline:,.2f}")
        print(f"      • Won (YTD): €{total_won:,.2f}")
        for deal in self.deals:
            status_icon = "🟢" if deal["status"] == "won" else "🟡"
            print(
                f"      • {status_icon} {deal['title']}: €{deal['value']:,.2f} ({deal['probability']}%)"
            )
        print()
        return self.deals

    async def _get_deals_single_page(self) -> list[dict[str, Any]]:
        """Fetch deals from a single page (backward compatible)."""
        print("   ├─ POST /deals.list")
        print("   ├─ Payload: page[size]=5, page[number]=1")
        print(
            "   └─ Value and phase fields are normalized from the live Teamleader record shape"
        )

        payload = self.teamleader_client.list_records(
            "deals.list",
            page_size=5,
            page_number=1,
        )
        live_records = payload.get("data") or []
        if not live_records:
            raise RuntimeError("Live Teamleader deals read returned no records")

        self.deals = [self._normalize_deal(record) for record in live_records]
        total_pipeline = sum(deal["value"] for deal in self.deals if deal["status"] == "open")
        total_won = sum(deal["value"] for deal in self.deals if deal["status"] == "won")

        print(f"   ✅ Retrieved {len(self.deals)} deals:")
        print(f"      • Active Pipeline: EUR {total_pipeline:,.2f}")
        print(f"      • Won (visible page): EUR {total_won:,.2f}")
        for deal in self.deals:
            status_icon = "🟢" if deal["status"] == "won" else "🟡"
            print(
                f"      • {status_icon} {deal['title']}: "
                f"{deal['currency']} {deal['value']:,.2f} ({deal['probability']}%)"
            )
        print(f"      • Provenance: {self.source_modes['deals']}\n")
        return self.deals

    async def _get_deals_paginated(self) -> list[dict[str, Any]]:
        """Fetch deals with full pagination and rate limit awareness."""
        print("   ├─ POST /deals.list (paginated)")
        print(f"   ├─ Max deals to fetch: {self.max_deals}")
        print("   ├─ Rate limit: 100 requests/minute")
        print("   └─ Using list_all_records generator with progress reporting")

        deals = []
        pages_fetched = 0

        try:
            for record in self.teamleader_client.list_all_records(
                "deals.list",
                page_size=20,
                max_pages=(self.max_deals + 19) // 20,  # Ceiling division
            ):
                deals.append(self._normalize_deal(record))

                # Progress reporting every 5 deals
                if len(deals) % 5 == 0:
                    print(f"      📊 Fetched {len(deals)} deals...", end="\r")

                if len(deals) >= self.max_deals:
                    break

        except Exception as exc:
            logger.warning("teamleader_demo_deals_pagination_error", error=str(exc))
            print(f"   ⚠️ Pagination error: {exc}")
            if not deals:
                raise RuntimeError("Live Teamleader deals read returned no records") from exc

        self.deals = deals[:self.max_deals]
        self.pages_fetched["deals"] = pages_fetched

        # Show rate limit status
        self._show_rate_limit_status()

        total_pipeline = sum(deal["value"] for deal in self.deals if deal["status"] == "open")
        total_won = sum(deal["value"] for deal in self.deals if deal["status"] == "won")

        print(f"   ✅ Retrieved {len(self.deals)} deals:")
        print(f"      • Active Pipeline: EUR {total_pipeline:,.2f}")
        print(f"      • Won (visible): EUR {total_won:,.2f}")
        for deal in self.deals[:10]:  # Show first 10
            status_icon = "🟢" if deal["status"] == "won" else "🟡"
            print(
                f"      • {status_icon} {deal['title']}: "
                f"{deal['currency']} {deal['value']:,.2f} ({deal['probability']}%)"
            )
        if len(self.deals) > 10:
            print(f"      ... and {len(self.deals) - 10} more")
        print(f"      • Provenance: {self.source_modes['deals']}")
        print(f"      • Pages fetched: {pages_fetched}\n")
        return self.deals

    async def get_activity_history(self) -> list[dict[str, Any]]:
        """Fetch recent activities and interactions."""
        print("📅 Step 5: Fetching Activity History...")
        if self.teamleader_client and self.source_modes["company"] == "real":
            print("   ├─ POST /events.list")
            print("   ├─ Payload: page[size]=20, page[number]=1")
            print("   └─ Filtering live events to those linked to the current Teamleader company")
            try:
                payload = self.teamleader_client.list_records(
                    "events.list",
                    page_size=20,
                    page_number=1,
                )
                live_records = payload.get("data") or []
                company_id = self.company.get("id")
                matching_records = [
                    record
                    for record in live_records
                    if any(
                        _as_dict(link).get("type") == "company"
                        and _as_dict(link).get("id") == company_id
                        for link in _as_list(record.get("links"))
                    )
                ]
                if matching_records:
                    self.activities = [
                        self._normalize_event(record) for record in matching_records
                    ]
                    self.source_modes["activities"] = "real"
                    self._refresh_provenance()
                    print(f"   ✅ Retrieved {len(self.activities)} linked Teamleader events:")
                    for activity in self.activities:
                        print(f"      • 🗓️ {activity['subject']} ({activity['date']})")
                    print(f"      • Provenance: {self.source_modes['activities']}\n")
                    return self.activities

                print(
                    "   ⚠️ No company-linked Teamleader events found on the visible page; falling back to mock activity history"
                )
            except Exception as exc:
                logger.warning("teamleader_demo_live_events_failed", error=str(exc))
                print(
                    f"   ⚠️ Live Teamleader events read failed, falling back to mock activity history: {exc}"
                )

        print("   ├─ Mock fallback")
        print("   ├─ Live Teamleader company/contact/deal reads remain enabled")
        print(
            "   └─ Activity history uses demo data when events.list has no visible company-linked records"
        )
        await asyncio.sleep(0.5)

        type_counts: dict[str, int] = {}
        for activity in self.activities:
            type_counts[activity["type"]] = type_counts.get(activity["type"], 0) + 1

        print(f"   ✅ Retrieved {len(self.activities)} activities:")
        for activity_type, count in type_counts.items():
            icon = {"call": "📞", "meeting": "🤝", "email": "📧"}.get(activity_type, "📝")
            print(f"      • {icon} {activity_type.capitalize()}: {count}")
        print(f"      • Provenance: {self.source_modes['activities']}\n")
        return self.activities

    async def sync_to_cdp(self) -> dict[str, Any]:
        """Sync Teamleader data to the CDP profile."""
        print("🔄 Step 6: Syncing to CDP Profile...")
        print("   ├─ Mapping Teamleader company → CDP Profile")
        print("   ├─ Enriching with CRM traits:")
        print("   │  • traits.teamleader_id")
        print("   │  • traits.crm_status (active/inactive)")
        print("   │  • traits.customer_type")
        print("   │  • traits.decision_makers[]")
        print("   │  • traits.deal_pipeline_value")
        print("   │  • traits.last_crm_activity")
        print("   │  • traits.activity_frequency")
        print("   └─ Preserving source provenance per Teamleader surface")
        await asyncio.sleep(0.5)

        decision_makers = [contact for contact in self.contacts if contact["decision_maker"]]
        open_deals = [deal for deal in self.deals if deal["status"] == "open"]
        pipeline_value = sum(deal["value"] for deal in open_deals)
        last_activity = max(activity["date"] for activity in self.activities)
        activity_count = len(self.activities)

        cdp_enrichment = {
            "traits": {
                "teamleader_id": self.company["id"],
                "crm_status": str(self.company["status"]).lower(),
                "customer_type": self.company["business_type"],
                "decision_makers": [
                    {
                        "name": _first_value(
                            contact.get("full_name"), contact.get("first_name"), "Unknown"
                        ),
                        "email": contact.get("email"),
                        "title": contact["job_title"],
                    }
                    for contact in decision_makers
                ],
                "deal_pipeline_value": pipeline_value,
                "deal_count": len(self.deals),
                "contact_count": len(self.contacts),
                "last_crm_activity": last_activity,
                "activity_90d_count": activity_count,
            },
            "metadata": {
                "teamleader_sync_date": datetime.now().isoformat(),
                "data_source": "teamleader_crm",
                "provenance": self.provenance,
                "source_modes": dict(self.source_modes),
                "company": self.company,
                "deals": self.deals,
                "contacts": self.contacts,
                "activities": self.activities,
            },
        }

        print("   ✅ CDP Profile enriched:")
        print(
            f"      • Pipeline Value: EUR {cdp_enrichment['traits']['deal_pipeline_value']:,.2f}"
        )
        print(f"      • Decision Makers: {len(cdp_enrichment['traits']['decision_makers'])}")
        print(f"      • Recent Activity: {activity_count} interactions (90d)")
        print(f"      • Provenance: {cdp_enrichment['metadata']['provenance']}")
        print(f"      • Source Modes: {cdp_enrichment['metadata']['source_modes']}")
        print()

        return cdp_enrichment

    async def show_use_cases(self) -> None:
        """Display potential use cases for this integration."""
        print("💡 Use Cases Enabled by Teamleader Integration:\n")

        use_cases = [
            {
                "title": "🎯 Decision Maker Identification",
                "description": "Automatically identify and tag decision makers for targeted campaigns",
                "example": "Segment: 'IT Decision Makers in Oost-Vlaanderen'",
            },
            {
                "title": "💼 Pipeline-Based Campaigns",
                "description": "Target companies based on deal stage and probability",
                "example": "Nurture: 'Proposal sent but not closed in 30 days'",
            },
            {
                "title": "📞 Activity-Based Triggers",
                "description": "Trigger actions based on sales activity (or lack thereof)",
                "example": "Alert: 'No activity in 45 days' for re-engagement",
            },
            {
                "title": "🔄 Cross-Department Visibility",
                "description": "Marketing sees sales activity, sales sees marketing engagement",
                "example": "Sales notified when lead opens pricing email",
            },
            {
                "title": "⭐ Lead Scoring Enhancement",
                "description": "Score leads based on CRM behavior + marketing engagement",
                "example": "High score: Active in CRM + High email engagement",
            },
            {
                "title": "📍 Geographic Segmentation",
                "description": "Use Teamleader address data for location-based campaigns",
                "example": "Event invite: 'Gent-based companies, IT sector'",
            },
        ]

        for index, use_case in enumerate(use_cases, 1):
            print(f"{index}. {use_case['title']}")
            print(f"   {use_case['description']}")
            print(f"   → {use_case['example']}\n")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the demo."""
    parser = argparse.ArgumentParser(
        description="Teamleader CRM Integration Demo for CDP_Merged"
    )
    parser.add_argument(
        "--full-pagination",
        action="store_true",
        help="Enable full pagination mode to fetch all records with progress reporting",
    )
    parser.add_argument(
        "--max-contacts",
        type=int,
        default=50,
        help="Maximum number of contacts to fetch in full pagination mode (default: 50)",
    )
    parser.add_argument(
        "--max-deals",
        type=int,
        default=50,
        help="Maximum number of deals to fetch in full pagination mode (default: 50)",
    )
    return parser.parse_args()


async def main() -> None:
    """Run the Teamleader integration demo."""
    args = parse_args()

    print("=" * 70)
    print("🚀 Teamleader CRM Integration Demo")
    print("=" * 70)
    print()
    print("This demo shows how Teamleader CRM data enriches CDP profiles")
    print("for unified sales and marketing insights.")
    print()

    if args.full_pagination:
        print("⚙️  Mode: FULL PAGINATION (production-ready)")
        print(f"   • Max contacts: {args.max_contacts}")
        print(f"   • Max deals: {args.max_deals}")
        print("   • Rate limiting: Enabled with monitoring")
        print("   • Progress reporting: Enabled")
        print()

    client = TeamleaderDemo(
        full_pagination=args.full_pagination,
        max_contacts=args.max_contacts,
        max_deals=args.max_deals,
    )
    print(f"Mode: {client.mode_description}")
    if client.teamleader_client:
        print(
            "Provenance target: real if linked Teamleader events are present on the visible page, otherwise hybrid"
        )
    else:
        print("Provenance target: mock")
    print()
    print("-" * 70)
    print()

    try:
        await client.authenticate()
        await client.get_company_profile()
        await client.get_contacts()
        await client.get_deals_pipeline()
        await client.get_activity_history()
        enrichment = await client.sync_to_cdp()

        print("-" * 70)
        print()
        await client.show_use_cases()

        print("=" * 70)
        print("✅ Demo Complete!")
        print("=" * 70)
        print()
        print(f"Company Shown: {enrichment['metadata']['company']['name']}")
        print(f"Provenance: {enrichment['metadata']['provenance']}")
        print(f"Source Modes: {enrichment['metadata']['source_modes']}")
        print()
        print("Next Steps:")
        if enrichment["metadata"]["provenance"] == "real":
            print("  1. Re-run: .venv/bin/python scripts/verify_teamleader_access.py")
            print("  2. Harden pagination and rate-limit handling for the Teamleader demo slice")
            print("  3. Project the Teamleader sync output into the CDP flow")
        elif enrichment["metadata"]["provenance"] == "hybrid":
            print("  1. Re-run: .venv/bin/python scripts/verify_teamleader_access.py")
            print(
                "  2. Expand the events.list window or filtering so company-linked Teamleader events are surfaced reliably"
            )
            print("  3. Project the Teamleader sync output into the CDP flow")
        else:
            print("  1. Configure Teamleader OAuth credentials in .env.teamleader")
            print("  2. Re-run: .venv/bin/python scripts/verify_teamleader_access.py")
            print("  3. Re-run this demo to upgrade Teamleader to hybrid mode")
        print()
        print("Documentation:")
        print("  • src/services/teamleader.py - shared Teamleader client")
        print("  • scripts/verify_teamleader_access.py - live access verifier")
        print()

    except Exception as exc:
        logger.error("demo_failed", error=str(exc))
        print(f"\n❌ Demo failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
