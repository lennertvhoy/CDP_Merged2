#!/bin/bash
# Enrichment Continuation Script
# Run this when subagent times out to resume from checkpoint
# Usage: ./continue_enrichment.sh [--with-derived-labels]
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

cd /home/ff/.openclaw/workspace/repos/CDP_Merged

echo "=== ENRICHMENT CONTINUATION ==="
echo "Time: $(date)"
echo "With Derived Labels (Phase 2): $WITH_DERIVED_LABELS"
echo ""

# Check current progress
echo "Checking checkpoint files:"
ls -la data/progress/*.json 2>/dev/null | tail -5

echo ""
echo "Current coverage:"
TOKEN=$(curl -s -X POST "http://52.148.232.140:8686/user/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin@cdpmerged.local&password=<redacted>" \
    --max-time 10 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

if [ -n "$TOKEN" ]; then
    for field in email phone discovered_website ai_description geo_latitude; do
        COUNT=$(curl -s -X POST "http://52.148.232.140:8686/profile/select" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"where\":\"traits.$field EXISTS\",\"limit\":1}" \
            --max-time 5 2>/dev/null | \
            python3 -c "import sys,json; print(json.load(sys.stdin).get('total', 0))" 2>/dev/null)
        echo "  $field: $COUNT"
    done
fi

echo ""
echo "Resuming enrichment from checkpoint..."

# Run enrichment (will auto-resume from checkpoint)
export GOOGLE_PLACES_API_KEY="<redacted>"
export TRACARDI_API_URL="http://52.148.232.140:8686"
export TRACARDI_USERNAME="admin@cdpmerged.local"
export TRACARDI_PASSWORD="admin"
export AZURE_OPENAI_ENDPOINT="https://aoai-cdpmerged-fast.openai.azure.com/"
export AZURE_OPENAI_API_KEY="$(az cognitiveservices account keys list --name aoai-cdpmerged-fast --resource-group rg-cdpmerged-fast --query key1 --output tsv 2>/dev/null)"
export AZURE_OPENAI_DEPLOYMENT="gpt-4o-mini"

poetry run python -c "
import asyncio
import sys
sys.path.insert(0, '.')
from src.enrichment.pipeline import run_enrichment

async def main():
    print('=== RESUMING ENRICHMENT ===')
    print('Checkpoint will auto-load')
    print(f'Phase 2 (CBE derived labels): {\"ENABLED\" if \"$WITH_DERIVED_LABELS\" == \"true\" else \"SKIPPED (optional)\"}')
    print('')
    
    # Phase 1: Contact validation - only profiles WITH email/phone
    # (Skip this phase if already completed - it wastes time on profiles without contacts)
    result1 = await run_enrichment(
        query='traits.email EXISTS OR traits.phone EXISTS',
        limit=None,
        phases=['contact_validation'],
        dry_run=False,
        batch_size=500
    )
    print(f'Phase 1 (contact_validation) complete')
    
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
    print(f'Phases complete')
    
    # Combine results
    result1['phases'].extend(result2.get('phases', []))
    print(f'Completed: {result1}')

asyncio.run(main())
" 2>&1 | tee logs/enrichment_continued_$(date +%Y%m%d_%H%M%S).log

echo ""
echo "=== CONTINUATION COMPLETE ==="
