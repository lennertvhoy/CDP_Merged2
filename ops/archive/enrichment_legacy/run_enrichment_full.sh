#!/bin/bash
# Enrichment Pipeline - Full Run
# Usage: ./run_enrichment_full.sh [--with-derived-labels]
# 
# By default, skips Phase 2 (CBE derived labels) for speed.
# Use --with-derived-labels to enable human-readable industry/size labels.

# Check for optional flags
WITH_DERIVED_LABELS=false
for arg in "$@"; do
    case $arg in
        --with-derived-labels)
            WITH_DERIVED_LABELS=true
            shift
            ;;
    esac
done

export GOOGLE_PLACES_API_KEY="<redacted>"
export TRACARDI_API_URL="http://52.148.232.140:8686"
export TRACARDI_USERNAME="admin@cdpmerged.local"
export TRACARDI_PASSWORD="admin"
export TRACARDI_SOURCE_ID="kbo-source"
export AZURE_OPENAI_ENDPOINT="https://aoai-cdpmerged-fast.openai.azure.com/"
export AZURE_OPENAI_API_KEY="$(az cognitiveservices account keys list --name aoai-cdpmerged-fast --resource-group rg-cdpmerged-fast --query key1 --output tsv 2>/dev/null)"
export AZURE_OPENAI_DEPLOYMENT="gpt-4o-mini"
export LLM_PROVIDER="azure"

cd /home/ff/.openclaw/workspace/repos/CDP_Merged

echo "=== ENRICHMENT PIPELINE ==="
echo "Date: $(date)"
echo "With Derived Labels (Phase 2): $WITH_DERIVED_LABELS"
echo ""

poetry run python -c "
import asyncio
import os
import sys

print(f'Google API Key: {bool(os.environ.get(\"GOOGLE_PLACES_API_KEY\"))}')
print(f'Tracardi URL: {os.environ.get(\"TRACARDI_API_URL\")}')
print(f'Azure Endpoint: {os.environ.get(\"AZURE_OPENAI_ENDPOINT\")}')
print(f'Phase 2 (CBE derived labels): {\"ENABLED\" if \"$WITH_DERIVED_LABELS\" == \"true\" else \"SKIPPED (optional)\"}')
print('')

sys.path.insert(0, '.')
from src.enrichment.pipeline import run_enrichment

async def main():
    # Phase 1: Contact validation (useful for profiles with contacts)
    result = await run_enrichment(
        query='traits.email EXISTS OR traits.phone EXISTS',
        limit=None,
        phases=['contact_validation'],
        dry_run=False,
        batch_size=500
    )
    print(f'Phase 1 (contact_validation) complete: {result}')
    
    # Build phase list based on flags
    # Phase 2 (cbe_integration) is OPTIONAL - adds derived labels only
    # Core KBO data (NACE codes, legal form, dates) already present from ingestion
    phases = ['website_discovery', 'google_places', 'descriptions', 'geocoding', 'deduplication']
    
    if \"$WITH_DERIVED_LABELS\" == \"true\":
        phases.insert(0, 'cbe_integration')
        print('Phase 2 (cbe_integration - derived labels) ENABLED')
    else:
        print('Phase 2 (cbe_integration - derived labels) SKIPPED (use --with-derived-labels to enable)')
    
    result2 = await run_enrichment(
        query='traits.name EXISTS',
        limit=516382,
        phases=phases,
        dry_run=False,
        batch_size=500
    )
    print(f'Phases complete: {result2}')
    
    result['phases'].extend(result2.get('phases', []))
    print(f'All phases completed')

asyncio.run(main())
" 2>&1 | tee logs/enrichment_full_$(date +%Y%m%d_%H%M%S).log
