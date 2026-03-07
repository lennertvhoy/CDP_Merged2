#!/usr/bin/env python3
"""
Exact Online Integration Demo for CDP_Merged.

Demonstrates the capability to sync financial and invoice data from Exact Online
to the CDP for a complete 360° customer view.

This is a READ-ONLY demo showing the integration architecture.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from typing import Any

sys.path.insert(0, "/home/ff/.openclaw/workspace/repos/CDP_Merged")

from src.core.logger import get_logger

logger = get_logger(__name__)
MOCK_CONTRACT_VERSION = "2026-03-04"


class ExactOnlineDemo:
    """Demo client showing Exact Online integration capabilities."""

    def __init__(self) -> None:
        self.base_url = "https://start.exactonline.be/api/v1"
        self.demo_data = self._load_demo_data()
        self.provenance = "mock"
        self.mock_scenario_id = "exact-mock-financial-happy-path"
        self.contract_version = MOCK_CONTRACT_VERSION
        self.source_modes = {
            "financials": "mock",
            "invoices": "mock",
        }

    @property
    def mode_description(self) -> str:
        """Describe how the Exact demo currently runs."""
        return "MOCK (no Exact trial/demo tenant verified; Exact-shaped fixture data only)"

    def _load_demo_data(self) -> dict[str, Any]:
        """Load realistic demo data for Exact Online."""
        return {
            "company": {
                "name": "Tech Solutions B.V.",
                "exact_code": "TECH001",
                "kvk": "12345678",
                "vat": "BE1234567890",
                "source_record_url": "https://start.exactonline.be/docs/HlpRestAPIResourcesDetails.aspx?name=SalesInvoiceSalesInvoices",
            },
            "invoices": [
                {
                    "id": "INV-2024-001",
                    "date": "2024-01-15",
                    "amount": 15000.00,
                    "status": "Paid",
                    "description": "Software License Q1 2024",
                    "source_record_url": "https://start.exactonline.be/api/v1/{division}/salesinvoice/SalesInvoices",
                },
                {
                    "id": "INV-2024-002",
                    "date": "2024-02-20",
                    "amount": 8500.00,
                    "status": "Paid",
                    "description": "Consultancy Services",
                    "source_record_url": "https://start.exactonline.be/api/v1/{division}/salesinvoice/SalesInvoices",
                },
                {
                    "id": "INV-2024-003",
                    "date": "2024-03-10",
                    "amount": 12000.00,
                    "status": "Open",
                    "description": "Cloud Migration Project",
                    "source_record_url": "https://start.exactonline.be/api/v1/{division}/salesinvoice/SalesInvoices",
                },
            ],
            "financial_summary": {
                "total_revenue_ytd": 125000.00,
                "total_outstanding": 12000.00,
                "average_payment_days": 14,
                "last_invoice_date": "2024-03-10",
                "customer_since": "2022-03-15",
            },
        }

    async def authenticate(self) -> dict[str, Any]:
        """Demo OAuth2 authentication flow."""
        print("🔐 Step 1: Authenticating with Exact Online...")
        print("   ├─ OAuth2 Authorization Code flow")
        print("   ├─ Scopes: financial.read invoicing.read")
        print("   └─ Redirect: https://cdp.it1.be/callback/exact")
        await asyncio.sleep(0.5)
        print(f"   ✅ Authenticated ({self.mode_description})\n")
        return {
            "access_token": "demo_token",
            "expires_in": 3600,
            "provenance": self.provenance,
            "mock_scenario_id": self.mock_scenario_id,
        }

    async def get_company_financials(self) -> dict[str, Any]:
        """Fetch company financial data from Exact."""
        print("📊 Step 2: Fetching Financial Data...")
        print("   ├─ GET /financial/Receivables")
        print("   ├─ GET /salesinvoice/SalesInvoices")
        print("   └─ GET /cashflow/PaymentTerms")
        await asyncio.sleep(0.5)
        data = self.demo_data["financial_summary"]
        print("   ✅ Retrieved:")
        print(f"      • Total Revenue YTD: €{data['total_revenue_ytd']:,.2f}")
        print(f"      • Outstanding: €{data['total_outstanding']:,.2f}")
        print(f"      • Avg Payment: {data['average_payment_days']} days\n")
        return data

    async def get_invoice_history(self) -> list[dict[str, Any]]:
        """Fetch invoice history from Exact."""
        print("📄 Step 3: Fetching Invoice History...")
        print("   ├─ Query: Last 12 months")
        print("   ├─ Status: All (Paid, Open, Overdue)")
        print("   └─ Include: Line items, VAT, payment dates")
        await asyncio.sleep(0.5)
        invoices = self.demo_data["invoices"]
        print(f"   ✅ Retrieved {len(invoices)} invoices:")
        for inv in invoices:
            status_icon = "✅" if inv["status"] == "Paid" else "⏳"
            print(f"      • {inv['id']}: €{inv['amount']:,.2f} {status_icon}")
        print()
        return invoices

    async def sync_to_cdp(self) -> dict[str, Any]:
        """Sync Exact data to CDP profile."""
        print("🔄 Step 4: Syncing to CDP Profile...")
        print("   ├─ Mapping Exact customer → CDP Profile")
        print("   ├─ Enriching with financial traits:")
        print("   │  • traits.exact_customer_since")
        print("   │  • traits.total_revenue_ytd")
        print("   │  • traits.average_invoice_amount")
        print("   │  • traits.payment_behavior (fast/slow)")
        print("   │  • traits.last_invoice_date")
        print("   └─ Storing invoice history in metadata")
        await asyncio.sleep(0.5)

        invoices = self.demo_data["invoices"]
        company = dict(self.demo_data["company"])
        financial_summary = self.demo_data["financial_summary"]
        generated_at = datetime.now().isoformat()
        avg_amount = sum(inv["amount"] for inv in invoices) / len(invoices)
        payment_behavior = "fast" if financial_summary["average_payment_days"] < 21 else "slow"

        cdp_enrichment = {
            "traits": {
                "exact_customer_since": financial_summary["customer_since"],
                "total_revenue_ytd": financial_summary["total_revenue_ytd"],
                "average_invoice_amount": avg_amount,
                "payment_behavior": payment_behavior,
                "last_invoice_date": financial_summary["last_invoice_date"],
                "outstanding_amount": financial_summary["total_outstanding"],
            },
            "metadata": {
                "exact_sync_date": generated_at,
                "generated_at": generated_at,
                "invoice_count": len(invoices),
                "data_source": "exact_online",
                "provenance": self.provenance,
                "mock_scenario_id": self.mock_scenario_id,
                "contract_version": self.contract_version,
                "source_modes": dict(self.source_modes),
                "company": company,
                "invoices": invoices,
                "source_record_url": company["source_record_url"],
            },
        }

        print("   ✅ CDP Profile enriched:")
        for trait, value in cdp_enrichment["traits"].items():
            if isinstance(value, float):
                print(f"      • {trait}: €{value:,.2f}")
            else:
                print(f"      • {trait}: {value}")
        print(f"      • provenance: {self.provenance}")
        print(f"      • mock_scenario_id: {self.mock_scenario_id}")
        print()

        return cdp_enrichment

    async def show_use_cases(self) -> None:
        """Display potential use cases for this integration."""
        print("💡 Use Cases Enabled by Exact Integration:\n")

        use_cases = [
            {
                "title": "💰 Payment Behavior Segmentation",
                "description": "Segment customers by payment speed to prioritize collections",
                "example": "Segment: 'Slow payers with outstanding > €5,000'",
            },
            {
                "title": "📈 Customer Lifetime Value",
                "description": "Calculate true CLV using invoice history from Exact",
                "example": "Trait: 'High CLV customers' for VIP treatment",
            },
            {
                "title": "🔄 Cross-sell Opportunities",
                "description": "Identify customers who buy certain services but not others",
                "example": "Target: 'Cloud customers without support contract'",
            },
            {
                "title": "⚠️ Churn Risk Detection",
                "description": "Flag customers with declining invoice frequency",
                "example": "Alert: 'No invoice in 90 days' for sales follow-up",
            },
            {
                "title": "📊 Financial Health Scoring",
                "description": "Score leads based on financial stability of similar customers",
                "example": "Priority: 'Companies with >€50K revenue, fast payers'",
            },
        ]

        for i, uc in enumerate(use_cases, 1):
            print(f"{i}. {uc['title']}")
            print(f"   {uc['description']}")
            print(f"   → {uc['example']}\n")


async def main() -> None:
    """Run the Exact Online integration demo."""
    client = ExactOnlineDemo()

    print("=" * 70)
    print("🚀 Exact Online Integration Demo")
    print("=" * 70)
    print()
    print("This demo shows how Exact Online financial data enriches CDP profiles")
    print("for a complete 360° customer view.")
    print()
    print(f"Mode: {client.mode_description}")
    print("Company: Tech Solutions B.V. (demo)")
    print()
    print("-" * 70)
    print()

    try:
        # Run demo steps
        await client.authenticate()
        await client.get_company_financials()
        await client.get_invoice_history()
        await client.sync_to_cdp()

        print("-" * 70)
        print()
        await client.show_use_cases()

        print("=" * 70)
        print("✅ Demo Complete!")
        print("=" * 70)
        print()
        print("Next Steps:")
        print(
            "  1. Request or activate an Exact trial/demo tenant; no live Exact credentials are configured in this repo today."
        )
        print("  2. Keep Exact marked as mock in current docs until live access is verified.")
        print("  3. Add a real Exact client and sync job before advertising live API calls.")
        print(
            "  4. Keep provenance and failure-mode behavior aligned with docs/DEMO_SOURCE_MOCK_CONTRACT.md."
        )
        print()
        print("Current References:")
        print("  • scripts/demo_exact_integration.py - current mock Exact demo")
        print("  • docs/DEMO_SOURCE_MOCK_CONTRACT.md - mock contract requirements")
        print("  • docs/DEMO_GUIDE.md - demo provenance rules")
        print()

    except Exception as exc:
        logger.error("demo_failed", error=str(exc))
        print(f"\n❌ Demo failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
