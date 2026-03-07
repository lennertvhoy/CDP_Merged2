#!/usr/bin/env python3
"""
Autotask Integration Demo for CDP_Merged.

Demonstrates the capability to sync service desk, ticketing, contracts,
and asset data from Autotask to the CDP for IT service intelligence.

This is a READ-ONLY demo showing the integration architecture.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Any

sys.path.insert(0, "/home/ff/.openclaw/workspace/repos/CDP_Merged")

from src.core.logger import get_logger

logger = get_logger(__name__)

# Demo configuration
DEMO_MODE = True  # Set to False for live API calls


class AutotaskDemo:
    """Demo client showing Autotask PSA integration capabilities."""

    def __init__(self):
        self.base_url = "https://webservices.autotask.net/atservicesrest"
        self.demo_data = self._load_demo_data()

    def _load_demo_data(self) -> dict:
        """Load realistic demo data for Autotask."""
        return {
            "company": {
                "id": "at_company_98765",
                "name": "Tech Solutions B.V.",
                "account_number": "IT1-2022-0042",
                "phone": "+32 9 123 45 67",
                "email": "support@techsolutions.be",
                "address": "Industrielaan 25, 9000 Gent, BE",
                "classification": "Class A",
                "customer_type": "Managed Services",
                "sla": "Premium 4h Response",
                "account_manager": "John Smith",
                "created_date": "2022-03-15",
            },
            "tickets": [
                {
                    "id": "TKT-2024-0156",
                    "title": "Email sync issue on mobile devices",
                    "status": "Open",
                    "priority": "Medium",
                    "queue": "Level 1 Support",
                    "created": "2024-03-05T09:15:00Z",
                    "due": "2024-03-06T09:15:00Z",
                    "assigned": "Support Engineer A",
                    "category": "Email/Exchange",
                },
                {
                    "id": "TKT-2024-0142",
                    "title": "VPN connection unstable",
                    "status": "In Progress",
                    "priority": "High",
                    "queue": "Network Team",
                    "created": "2024-03-01T14:30:00Z",
                    "due": "2024-03-01T18:30:00Z",
                    "assigned": "Network Specialist B",
                    "category": "Network/VPN",
                },
                {
                    "id": "TKT-2024-0128",
                    "title": "New workstation setup request",
                    "status": "Completed",
                    "priority": "Low",
                    "queue": "Level 1 Support",
                    "created": "2024-02-25T11:00:00Z",
                    "due": "2024-03-01T11:00:00Z",
                    "assigned": "Support Engineer A",
                    "category": "Hardware/Setup",
                },
            ],
            "contracts": [
                {
                    "id": "CON-2024-001",
                    "name": "Managed Services Premium",
                    "type": "Recurring Service",
                    "status": "Active",
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "value": 45000.00,
                    "billing": "Monthly",
                    "services": [
                        "24/7 Monitoring",
                        "4h Response SLA",
                        "Unlimited Remote Support",
                        "Quarterly Business Reviews",
                    ],
                },
                {
                    "id": "CON-2023-012",
                    "name": "Project: Cloud Migration",
                    "type": "Fixed Price",
                    "status": "Active",
                    "start_date": "2024-02-01",
                    "end_date": "2024-05-31",
                    "value": 25000.00,
                    "billing": "Milestone",
                    "services": [
                        "Azure Migration",
                        "Data Transfer",
                        "User Training",
                    ],
                },
            ],
            "assets": [
                {
                    "id": "AST-2024-001",
                    "name": "SRV-PROD-01",
                    "type": "Server",
                    "manufacturer": "Dell",
                    "model": "PowerEdge R740",
                    "serial": "ABC123456",
                    "warranty_expiry": "2027-01-15",
                    "last_patched": "2024-03-01",
                    "rmm_status": "Online",
                },
                {
                    "id": "AST-2024-045",
                    "name": "WS-DAVID-01",
                    "type": "Workstation",
                    "manufacturer": "HP",
                    "model": "EliteDesk 800",
                    "serial": "XYZ789012",
                    "warranty_expiry": "2026-06-20",
                    "last_patched": "2024-02-28",
                    "rmm_status": "Online",
                },
                {
                    "id": "AST-2023-128",
                    "name": "FW-MAIN-01",
                    "type": "Firewall",
                    "manufacturer": "SonicWall",
                    "model": "NSa 2650",
                    "serial": "FW456789",
                    "warranty_expiry": "2025-08-10",
                    "last_patched": "2024-02-15",
                    "rmm_status": "Warning - Firmware outdated",
                },
            ],
            "service_stats": {
                "tickets_ytd": 24,
                "avg_resolution_hours": 8.5,
                "sla_compliance": 96.2,
                "open_tickets": 2,
                "critical_issues": 0,
                "last_review": "2024-02-15",
            },
        }

    async def authenticate(self) -> dict[str, Any]:
        """Demo API authentication flow."""
        print("🔐 Step 1: Authenticating with Autotask...")
        print("   ├─ Username/API Key authentication")
        print("   ├─ Zone: webservices.autotask.net")
        print("   └─ Integration Code: CDP_Merged")
        
        if DEMO_MODE:
            await asyncio.sleep(0.5)
            print("   ✅ Authenticated (Demo Mode)\n")
            return {"session_token": "demo_token", "zone": "5"}
        
        raise NotImplementedError("Live API requires credentials")

    async def get_company_info(self) -> dict[str, Any]:
        """Fetch company information from Autotask."""
        print("🏢 Step 2: Fetching Company Information...")
        print("   ├─ GET /Companies")
        print("   ├─ GET /CompanyLocations")
        print("   └─ GET /CompanyNotes")
        
        if DEMO_MODE:
            await asyncio.sleep(0.5)
            company = self.demo_data["company"]
            print(f"   ✅ Retrieved:")
            print(f"      • Account: {company['account_number']}")
            print(f"      • Classification: {company['classification']}")
            print(f"      • SLA: {company['sla']}")
            print(f"      • Account Manager: {company['account_manager']}\n")
            return company
        
        raise NotImplementedError("Live API requires authentication")

    async def get_service_tickets(self) -> list[dict]:
        """Fetch active service tickets."""
        print("🎫 Step 3: Fetching Service Tickets...")
        print("   ├─ GET /Tickets")
        print("   ├─ Filter: Last 90 days")
        print("   └─ Include: Status, Priority, Queue, Assigned resource")
        
        if DEMO_MODE:
            await asyncio.sleep(0.5)
            tickets = self.demo_data["tickets"]
            
            status_counts = {}
            for t in tickets:
                status_counts[t["status"]] = status_counts.get(t["status"], 0) + 1
            
            print(f"   ✅ Retrieved {len(tickets)} tickets:")
            for ticket in tickets:
                priority_icon = "🔴" if ticket["priority"] == "High" else "🟡" if ticket["priority"] == "Medium" else "🟢"
                status_icon = "✅" if ticket["status"] == "Completed" else "🔄" if ticket["status"] == "In Progress" else "📋"
                print(f"      • {status_icon} {ticket['id']}: {ticket['title'][:40]}... {priority_icon}")
            print()
            return tickets
        
        raise NotImplementedError("Live API requires authentication")

    async def get_contracts(self) -> list[dict]:
        """Fetch active contracts and services."""
        print("📄 Step 4: Fetching Contracts...")
        print("   ├─ GET /Contracts")
        print("   ├─ GET /ContractServiceUnits")
        print("   └─ Filter: Active status")
        
        if DEMO_MODE:
            await asyncio.sleep(0.5)
            contracts = self.demo_data["contracts"]
            total_value = sum(c["value"] for c in contracts)
            
            print(f"   ✅ Retrieved {len(contracts)} contracts:")
            print(f"      • Total Contract Value: €{total_value:,.2f}")
            for contract in contracts:
                status_icon = "✅" if contract["status"] == "Active" else "⚠️"
                print(f"      • {status_icon} {contract['name']}: €{contract['value']:,.2f} ({contract['type']})")
                for service in contract["services"]:
                    print(f"         └─ {service}")
            print()
            return contracts
        
        raise NotImplementedError("Live API requires authentication")

    async def get_assets(self) -> list[dict]:
        """Fetch managed assets and configurations."""
        print("💻 Step 5: Fetching Assets & Configurations...")
        print("   ├─ GET /ConfigurationItems")
        print("   ├─ GET /InstalledProducts")
        print("   └─ Include: Warranty status, RMM health")
        
        if DEMO_MODE:
            await asyncio.sleep(0.5)
            assets = self.demo_data["assets"]
            
            # Count by type
            type_counts = {}
            warning_count = 0
            for asset in assets:
                type_counts[asset["type"]] = type_counts.get(asset["type"], 0) + 1
                if "Warning" in asset["rmm_status"]:
                    warning_count += 1
            
            print(f"   ✅ Retrieved {len(assets)} assets:")
            for asset_type, count in type_counts.items():
                print(f"      • {asset_type}: {count}")
            if warning_count > 0:
                print(f"      ⚠️  Assets needing attention: {warning_count}")
            
            for asset in assets:
                if "Warning" in asset["rmm_status"]:
                    print(f"         └─ {asset['name']}: {asset['rmm_status']}")
            print()
            return assets
        
        raise NotImplementedError("Live API requires authentication")

    async def get_service_statistics(self) -> dict[str, Any]:
        """Fetch service desk statistics."""
        print("📊 Step 6: Fetching Service Statistics...")
        print("   ├─ Calculating: Ticket volume, Resolution times")
        print("   ├─ SLA compliance metrics")
        print("   └─ Resource utilization")
        
        if DEMO_MODE:
            await asyncio.sleep(0.5)
            stats = self.demo_data["service_stats"]
            
            print(f"   ✅ Service Statistics (YTD):")
            print(f"      • Tickets: {stats['tickets_ytd']}")
            print(f"      • Avg Resolution: {stats['avg_resolution_hours']} hours")
            print(f"      • SLA Compliance: {stats['sla_compliance']}%")
            print(f"      • Open Tickets: {stats['open_tickets']}")
            if stats['critical_issues'] > 0:
                print(f"      🔴 Critical Issues: {stats['critical_issues']}")
            else:
                print(f"      ✅ No Critical Issues")
            print()
            return stats
        
        raise NotImplementedError("Live API requires authentication")

    async def sync_to_cdp(self) -> dict[str, Any]:
        """Sync Autotask data to CDP profile."""
        print("🔄 Step 7: Syncing to CDP Profile...")
        print("   ├─ Mapping Autotask account → CDP Profile")
        print("   ├─ Enriching with service intelligence:")
        print("   │  • traits.autotask_account_id")
        print("   │  • traits.sla_level")
        print("   │  • traits.service_tier")
        print("   │  • traits.support_ticket_count_90d")
        print("   │  • traits.avg_resolution_time")
        print("   │  • traits.contract_value")
        print("   │  • traits.asset_count")
        print("   │  • traits.satisfaction_score")
        print("   └─ Storing tickets, contracts, assets in metadata")
        
        if DEMO_MODE:
            await asyncio.sleep(0.5)
            
            contracts = self.demo_data["contracts"]
            tickets = self.demo_data["tickets"]
            assets = self.demo_data["assets"]
            stats = self.demo_data["service_stats"]
            
            # Calculate derived traits
            contract_value = sum(c["value"] for c in contracts)
            active_contracts = len([c for c in contracts if c["status"] == "Active"])
            
            cdp_enrichment = {
                "traits": {
                    "autotask_account_id": self.demo_data["company"]["id"],
                    "sla_level": self.demo_data["company"]["sla"],
                    "service_tier": self.demo_data["company"]["classification"],
                    "account_manager": self.demo_data["company"]["account_manager"],
                    "support_ticket_count_90d": stats["tickets_ytd"],
                    "open_tickets": stats["open_tickets"],
                    "avg_resolution_hours": stats["avg_resolution_hours"],
                    "sla_compliance": stats["sla_compliance"],
                    "contract_value": contract_value,
                    "active_contracts": active_contracts,
                    "managed_assets": len(assets),
                    "assets_needing_attention": len([a for a in assets if "Warning" in a["rmm_status"]]),
                },
                "metadata": {
                    "autotask_sync_date": datetime.now().isoformat(),
                    "data_source": "autotask_psa",
                    "contracts": contracts,
                    "recent_tickets": tickets,
                    "assets": assets,
                    "service_stats": stats,
                }
            }
            
            print("   ✅ CDP Profile enriched:")
            print(f"      • SLA: {cdp_enrichment['traits']['sla_level']}")
            print(f"      • Contract Value: €{cdp_enrichment['traits']['contract_value']:,.2f}")
            print(f"      • Support Tickets: {cdp_enrichment['traits']['support_ticket_count_90d']} (90d)")
            print(f"      • Assets Managed: {cdp_enrichment['traits']['managed_assets']}")
            print()
            
            return cdp_enrichment
        
        raise NotImplementedError("Live sync requires CDP connection")

    async def show_use_cases(self):
        """Display potential use cases for this integration."""
        print("💡 Use Cases Enabled by Autotask Integration:\n")
        
        use_cases = [
            {
                "title": "🎯 Service-Based Segmentation",
                "description": "Segment customers by service tier and SLA level",
                "example": "Segment: 'Premium SLA customers' for priority offers",
            },
            {
                "title": "🔧 Proactive Support Campaigns",
                "description": "Target customers with aging assets or recurring issues",
                "example": "Campaign: 'Hardware refresh' for 3+ year old assets",
            },
            {
                "title": "💰 Contract Renewal Automation",
                "description": "Trigger renewal campaigns based on contract end dates",
                "example": "Alert: 'Contract expires in 60 days' + renewal offer",
            },
            {
                "title": "⭐ Satisfaction-Based Targeting",
                "description": "Adjust messaging based on support satisfaction",
                "example": "VIP treatment for high satisfaction + high value",
            },
            {
                "title": "📊 Service Upsell Opportunities",
                "description": "Identify customers who could benefit from additional services",
                "example": "Target: 'High ticket volume' → 'Premium support' upsell",
            },
            {
                "title": "🚨 Emergency Communication",
                "description": "Rapidly notify affected customers during incidents",
                "example": "Alert all customers with specific firewall model",
            },
            {
                "title": "📈 Usage-Based Recommendations",
                "description": "Suggest services based on actual usage patterns",
                "example": "Cloud backup for customers with high data growth",
            },
        ]
        
        for i, uc in enumerate(use_cases, 1):
            print(f"{i}. {uc['title']}")
            print(f"   {uc['description']}")
            print(f"   → {uc['example']}\n")


async def main():
    """Run the Autotask integration demo."""
    print("=" * 70)
    print("🚀 Autotask PSA Integration Demo")
    print("=" * 70)
    print()
    print("This demo shows how Autotask service data enriches CDP profiles")
    print("for IT service intelligence and proactive customer engagement.")
    print()
    print("Mode: DEMO (simulated data - no live API calls)")
    print("Company: Tech Solutions B.V. (demo)")
    print()
    print("-" * 70)
    print()
    
    client = AutotaskDemo()
    
    try:
        # Run demo steps
        await client.authenticate()
        await client.get_company_info()
        await client.get_service_tickets()
        await client.get_contracts()
        await client.get_assets()
        await client.get_service_statistics()
        enrichment = await client.sync_to_cdp()
        
        print("-" * 70)
        print()
        await client.show_use_cases()
        
        print("=" * 70)
        print("✅ Demo Complete!")
        print("=" * 70)
        print()
        print("Next Steps:")
        print("  1. Configure Autotask API credentials in .env")
        print("  2. Set DEMO_MODE = False for live API calls")
        print("  3. Run: python scripts/sync_autotask_to_cdp.py")
        print("  4. See enriched profiles in Tracardi GUI")
        print()
        print("Documentation:")
        print("  • src/services/autotask.py - Full implementation")
        print("  • docs/integrations/autotask.md - Setup guide")
        print()
        
    except Exception as e:
        logger.error("demo_failed", error=str(e))
        print(f"\n❌ Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
