import asyncio
import os
import sys

# Add src to python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.enrichment.pipeline import run_enrichment

async def main():
    print("Testing streaming with small batch first for phase: contact_validation")
    print("NOTE: Only targeting profiles that HAVE email OR phone")
    result = await run_enrichment(
        query='traits.email EXISTS OR traits.phone EXISTS',
        phases=['contact_validation'],
        dry_run=False,
        batch_size=500
    )
    print("Enrichment run result:", result)

if __name__ == "__main__":
    asyncio.run(main())
