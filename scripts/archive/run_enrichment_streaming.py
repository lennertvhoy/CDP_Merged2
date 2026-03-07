import asyncio
import os
import sys
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.enrichment.pipeline import run_enrichment

async def main():
    print("Starting full enrichment pipeline in streaming mode.")

    # Phase 1: Only target profiles that have email or phone
    # Contact validation can't enrich profiles without contact info
    print("Phase 1: Contact validation - targeting profiles with email OR phone...")
    result = await run_enrichment(
        query="traits.email EXISTS OR traits.phone EXISTS",
        limit=None,
        phases=["contact_validation"],
        dry_run=False,
        batch_size=500
    )

    # Phase 2-5: Run remaining phases on all profiles with names
    print("Phase 3-5: website, descriptions, geocoding - targeting all named profiles...")
    result2 = await run_enrichment(
        query="traits.name EXISTS",
        limit=None,
        phases=[
            "website_discovery",
            "descriptions",
            "geocoding"
        ],
        dry_run=False,
        batch_size=200
    )
    result["phases"].extend(result2.get("phases", []))
    with open("enrichment_run_result.json", "w") as f:
        json.dump(result, f, indent=2)
    print("Enrichment run phases 1-5 completed. Check logs and results.")

if __name__ == "__main__":
    asyncio.run(main())
