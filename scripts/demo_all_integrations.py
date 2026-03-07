#!/usr/bin/env python3
"""
Unified Integration Demo for CDP_Merged.

Runs all integration demos in sequence to showcase the complete
360° customer view capabilities of the CDP.

This demonstrates how data from Exact, Teamleader, and Autotask
converge into a unified CDP profile.
"""

import asyncio
import sys

sys.path.insert(0, "/home/ff/.openclaw/workspace/repos/CDP_Merged")

from demo_autotask_integration import AutotaskDemo
from demo_exact_integration import ExactOnlineDemo
from demo_teamleader_integration import TeamleaderDemo


class UnifiedCDPDemo:
    """Unified demo showing all integrations converging in CDP."""

    def __init__(self):
        self.exact_demo = ExactOnlineDemo()
        self.teamleader_demo = TeamleaderDemo()
        self.autotask_demo = AutotaskDemo()

    async def run_all_demos(self):
        """Run all integration demos sequentially."""

        print("╔" + "=" * 68 + "╗")
        print("║" + " " * 15 + "CDP_Merged - Unified Integration Demo" + " " * 16 + "║")
        print("╚" + "=" * 68 + "╝")
        print()
        print("🎯 Objective: Demonstrate 360° Customer View")
        print()
        print("This demo shows how data from multiple business systems")
        print("(Exact, Teamleader, Autotask) converges into a single")
        print("unified customer profile in the CDP.")
        print()
        input("Press Enter to begin the demo...")
        print()

        # Run each integration demo
        demos = [
            ("Exact Online", self.run_exact_demo),
            ("Teamleader CRM", self.run_teamleader_demo),
            ("Autotask PSA", self.run_autotask_demo),
        ]

        all_enrichments = {}

        for name, demo_func in demos:
            print("\n" + "─" * 70)
            print(f"📊 Phase: {name}")
            print("─" * 70 + "\n")

            try:
                enrichment = await demo_func()
                all_enrichments[name.lower().replace(" ", "_")] = enrichment
            except Exception as e:
                print(f"\n⚠️  {name} demo encountered an issue: {e}")
                print("   Continuing with other demos...")

        # Show unified profile
        await self.show_unified_profile(all_enrichments)

        # Show cross-system insights
        await self.show_cross_system_insights(all_enrichments)

    async def run_exact_demo(self):
        """Run Exact Online demo."""
        print("💰 Financial Data from Exact Online\n")

        await self.exact_demo.authenticate()
        await self.exact_demo.get_company_financials()
        await self.exact_demo.get_invoice_history()
        return await self.exact_demo.sync_to_cdp()

    async def run_teamleader_demo(self):
        """Run Teamleader demo."""
        print("👥 CRM Data from Teamleader\n")

        await self.teamleader_demo.authenticate()
        await self.teamleader_demo.get_company_profile()
        await self.teamleader_demo.get_contacts()
        await self.teamleader_demo.get_deals_pipeline()
        await self.teamleader_demo.get_activity_history()
        return await self.teamleader_demo.sync_to_cdp()

    async def run_autotask_demo(self):
        """Run Autotask demo."""
        print("🔧 Service Data from Autotask\n")

        await self.autotask_demo.authenticate()
        await self.autotask_demo.get_company_info()
        await self.autotask_demo.get_service_tickets()
        await self.autotask_demo.get_contracts()
        await self.autotask_demo.get_assets()
        await self.autotask_demo.get_service_statistics()
        return await self.autotask_demo.sync_to_cdp()

    async def show_unified_profile(self, enrichments: dict):
        """Display the unified CDP profile."""
        teamleader_enrichment = enrichments.get("teamleader_crm", {})
        teamleader_traits = teamleader_enrichment.get("traits", {})
        teamleader_metadata = teamleader_enrichment.get("metadata", {})
        teamleader_company = teamleader_metadata.get("company", {})
        company_name = teamleader_company.get("name", "Tech Solutions B.V.")
        decision_makers = teamleader_traits.get("decision_makers", [])
        decision_makers_label = (
            ", ".join(
                filter(
                    None,
                    [
                        (
                            f"{decision_maker.get('name')} ({decision_maker.get('title')})"
                            if decision_maker.get("title")
                            else decision_maker.get("name")
                        )
                        for decision_maker in decision_makers
                    ],
                )
            )
            or "No decision makers tagged"
        )
        crm_status = teamleader_traits.get("crm_status", "active")
        pipeline_value = teamleader_traits.get("deal_pipeline_value", 45000.0)
        activity_count = teamleader_traits.get("activity_90d_count", 3)
        last_contact = teamleader_traits.get("last_crm_activity", "2024-03-01")
        teamleader_provenance = teamleader_metadata.get("provenance", "mock")
        teamleader_source_modes = teamleader_metadata.get("source_modes", {})
        source_modes_label = (
            ", ".join(f"{name}={mode}" for name, mode in teamleader_source_modes.items())
            or "company=mock, contacts=mock, deals=mock, activities=mock"
        )
        pipeline_tag = (
            "[Active Pipeline] Open deals > €0"
            if pipeline_value > 0
            else "[No Active Pipeline] No open Teamleader deals on the visible page"
        )
        decision_maker_tag = (
            "[Decision Maker Engaged] Tagged contact present"
            if decision_makers
            else "[CRM Coverage Gap] No decision maker tagged in the visible Teamleader page"
        )

        print("\n" + "═" * 70)
        print(f"🌟 UNIFIED CDP PROFILE - {company_name}")
        print("═" * 70)
        print()
        print("All data sources have been merged into a single 360° profile:")
        print()

        # Financial Summary (from Exact)
        print("💰 FINANCIAL (Exact Online)")
        print("   ├─ Total Revenue YTD: €125,000.00")
        print("   ├─ Outstanding: €12,000.00")
        print("   ├─ Payment Behavior: fast")
        print("   └─ Last Invoice: 2024-03-10")
        print()

        # CRM Summary (from Teamleader)
        print("👥 CRM (Teamleader)")
        print(f"   ├─ Status: {crm_status}")
        print(f"   ├─ Decision Makers: {decision_makers_label}")
        print(f"   ├─ Pipeline Value: €{pipeline_value:,.2f}")
        print(f"   ├─ Recent Activity: {activity_count} interactions (90d)")
        print(f"   ├─ Last Contact: {last_contact}")
        print(f"   ├─ Provenance: {teamleader_provenance}")
        print(f"   └─ Source Modes: {source_modes_label}")
        print()

        # Service Summary (from Autotask)
        print("🔧 SERVICE (Autotask)")
        print("   ├─ SLA: Premium 4h Response")
        print("   ├─ Account Manager: John Smith")
        print("   ├─ Contracts: €70,000.00 total value")
        print("   ├─ Assets: 3 managed devices")
        print("   ├─ Tickets: 24 YTD, 2 open")
        print("   └─ SLA Compliance: 96.2%")
        print()

        # Unified Traits
        print("🏷️  UNIFIED SEGMENTS & TAGS")
        print("   ├─ [High Value] Revenue > €100K")
        print("   ├─ [Premium Service] SLA = Premium")
        print(f"   ├─ {pipeline_tag}")
        print("   ├─ [Fast Payer] Payment < 21 days")
        print(f"   ├─ {decision_maker_tag}")
        print("   └─ [Upsell Opportunity] Cloud migration candidate")
        print()

    async def show_cross_system_insights(self, enrichments: dict):
        """Display insights that only exist when systems are unified."""
        teamleader_enrichment = enrichments.get("teamleader_crm", {})
        teamleader_metadata = teamleader_enrichment.get("metadata", {})
        teamleader_traits = teamleader_enrichment.get("traits", {})
        teamleader_provenance = teamleader_metadata.get("provenance", "mock")
        pipeline_value = teamleader_traits.get("deal_pipeline_value", 45000.0)
        activity_count = teamleader_traits.get("activity_90d_count", 3)
        decision_maker_count = len(teamleader_traits.get("decision_makers", []))
        decision_maker_summary = (
            f"{decision_maker_count} tagged decision maker(s)"
            if decision_maker_count
            else "no tagged decision makers on the visible Teamleader page"
        )

        print("═" * 70)
        print("🔍 CROSS-SYSTEM INSIGHTS (Only possible with CDP)")
        print("═" * 70)
        print()
        print(
            "Source provenance in this run: "
            f"Exact=mock, Teamleader={teamleader_provenance}, Autotask=mock"
        )
        print()

        insights = [
            {
                "title": "💡 Upsell Opportunity Detected",
                "sources": ["Exact", "Teamleader", "Autotask"],
                "insight": (
                    "Customer has €12K outstanding invoice + "
                    f"€{pipeline_value:,.0f} open Teamleader pipeline + Premium SLA"
                ),
                "action": "Schedule executive call to discuss expansion",
            },
            {
                "title": "⚠️  Attention Required",
                "sources": ["Autotask", "Teamleader"],
                "insight": (
                    "2 open support tickets + "
                    f"{activity_count} recent CRM activities (activity step provenance-aware)"
                ),
                "action": "Proactive outreach from account manager",
            },
            {
                "title": "🎯 Perfect Timing",
                "sources": ["Exact", "Teamleader"],
                "insight": f"Fast payer + active Teamleader pipeline + {decision_maker_summary}",
                "action": "Send case study of similar successful migration",
            },
            {
                "title": "📊 Health Score: 92/100",
                "sources": ["All systems"],
                "insight": "Combining financial, engagement, and service metrics",
                "breakdown": {
                    "Financial Health": 95,
                    "Engagement Score": 88,
                    "Service Satisfaction": 96,
                },
            },
        ]

        for i, insight in enumerate(insights, 1):
            print(f"{i}. {insight['title']}")
            print(f"   Sources: {', '.join(insight['sources'])}")
            print(f"   Insight: {insight['insight']}")
            if "action" in insight:
                print(f"   🎯 Action: {insight['action']}")
            if "breakdown" in insight:
                print("   Breakdown:")
                for metric, score in insight["breakdown"].items():
                    bar = "█" * (score // 10) + "░" * ((100 - score) // 10)
                    print(f"      • {metric}: {bar} {score}")
            print()

        print("═" * 70)
        print("🚀 DEMO COMPLETE")
        print("═" * 70)
        print()
        print("Summary:")
        print("  ✅ Exact Online: Financial data & invoice history")
        print(
            "  ✅ Teamleader: CRM contacts, deals & activities "
            f"({self.teamleader_demo.provenance})"
        )
        print("  ✅ Autotask: Service tickets, contracts & assets")
        print("  ✅ Unified Profile: 360° customer view in CDP")
        print()
        print("Next Steps:")
        if self.teamleader_demo.provenance == "real":
            print("  1. Harden the Teamleader demo slice for pagination and rate-limit handling")
        elif self.teamleader_demo.provenance == "hybrid":
            print(
                "  1. Expand the Teamleader events.list window so company-linked events stay visible"
            )
        else:
            print(
                "  1. Configure Teamleader credentials so the CRM slice can move beyond mock mode"
            )
        print("  2. Add Exact and Autotask credentials when real access becomes available")
        print("  3. Run: python scripts/sync_all_to_cdp.py")
        print("  4. Explore enriched profiles in Tracardi GUI")
        print("  5. Create segments based on unified traits")
        print()
        print("Documentation:")
        print("  • docs/DEMO_GUIDE.md - Full demo walkthrough")
        print("  • docs/integrations/ - Individual integration guides")
        print()


async def main():
    """Run the unified integration demo."""
    demo = UnifiedCDPDemo()

    try:
        await demo.run_all_demos()
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
