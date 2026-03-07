#!/bin/bash
# Restart enrichment with full dataset processing
# Uses CDP_FORCE_FULL_SHARDING=1 to bypass 10K limit

cd /home/ff/.openclaw/workspace/repos/CDP_Merged

echo "=== FULL DATASET ENRICHMENT RESTART ==="
echo "Time: $(date)"
echo ""

# Export required env vars
export GOOGLE_PLACES_API_KEY="<redacted>"
export TRACARDI_API_URL="http://52.148.232.140:8686"
export TRACARDI_USERNAME="admin@cdpmerged.local"
export TRACARDI_PASSWORD="admin"
export TRACARDI_SOURCE_ID="kbo-source"
export AZURE_OPENAI_ENDPOINT="https://aoai-cdpmerged-fast.openai.azure.com/"
export AZURE_OPENAI_API_KEY="$(az cognitiveservices account keys list --name aoai-cdpmerged-fast --resource-group rg-cdpmerged-fast --query key1 --output tsv 2>/dev/null)"
export AZURE_OPENAI_DEPLOYMENT="gpt-4o-mini"
export LLM_PROVIDER="azure"

# CRITICAL: Force full sharding mode to process all 516K profiles
export CDP_FORCE_FULL_SHARDING=1

echo "Environment configured:"
echo "  CDP_FORCE_FULL_SHARDING=$CDP_FORCE_FULL_SHARDING"
echo "  Google API Key: ${GOOGLE_PLACES_API_KEY:+SET}"
echo "  Azure Endpoint: ${AZURE_OPENAI_ENDPOINT}"
echo ""

LOG_FILE="logs/enrichment_full_$(date +%Y%m%d_%H%M%S).log"
echo "Logging to: $LOG_FILE"
echo ""

# Run the enrichment
poetry run python -c "
import asyncio
import sys
sys.path.insert(0, '.')
from src.enrichment.pipeline import run_enrichment

async def main():
    print('=== STARTING FULL DATASET ENRICHMENT ===')
    print('This will process ALL profiles via sharding mode')
    print('')
    
    # Phase 1: Contact validation
    print('Phase 1: Contact Validation...')
    result1 = await run_enrichment(
        query='traits.email EXISTS OR traits.phone EXISTS',
        limit=None,
        phases=['contact_validation'],
        dry_run=False,
        batch_size=500
    )
    print(f'Phase 1 complete: {result1.get(\"phases_run\", 0)} phases')
    
    # Phases 2+: All other enrichments
    print('')
    print('Phases 2+: CBE, Website, Descriptions, Geocoding...')
    result2 = await run_enrichment(
        query='traits.name EXISTS',
        limit=None,
        phases=['cbe_integration', 'website_discovery', 'descriptions', 'geocoding'],
        dry_run=False,
        batch_size=500
    )
    print(f'Phases 2+ complete: {result2.get(\"phases_run\", 0)} phases')
    
    # Combine results
    result1['phases'].extend(result2.get('phases', []))
    
    print('')
    print('=== ENRICHMENT COMPLETE ===')
    for phase in result1.get('phases', []):
        status = phase.get('status', 'unknown')
        enriched = phase.get('enriched', 0)
        print(f'  {phase.get(\"phase\", \"unknown\")}: {status} ({enriched} enriched)')

asyncio.run(main())
" 2>&1 | tee "$LOG_FILE"

echo ""
echo "=== RESTART COMPLETE ==="
echo "Log saved to: $LOG_FILE"
