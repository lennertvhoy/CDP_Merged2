#!/bin/bash
# Auto-continuation monitor for enrichment
# Run this in background to spawn continuation when main subagent times out

SUBAGENT_SESSION="agent:main:subagent:b3c222ce-2fc2-4cfd-a08f-d0fc13ebe793"
CHECK_INTERVAL=300  # Check every 5 minutes

echo "=== ENRICHMENT CONTINUATION MONITOR ==="
echo "Started: $(date)"
echo "Monitoring subagent: $SUBAGENT_SESSION"
echo ""

while true; do
    sleep $CHECK_INTERVAL
    
    # Check if subagent is still running
    if openclaw subagent list 2>/dev/null | grep -q "$SUBAGENT_SESSION"; then
        echo "[$(date)] Subagent still running - continuing to monitor..."
    else
        echo "[$(date)] Subagent stopped/timed out - spawning continuation..."
        
        # Spawn continuation subagent
        openclaw subagent spawn \
            --label "production-enrichment-continuation" \
            --mode run \
            --timeout 7200 \
            --task "ENRICHMENT CONTINUATION - PICKING UP FROM CHECKPOINT

Previous subagent timed out. Resume enrichment from checkpoint.

cd /home/ff/.openclaw/workspace/repos/CDP_Merged

# Environment
export GOOGLE_PLACES_API_KEY='<redacted>'
export TRACARDI_API_URL='http://52.148.232.140:8686'
export TRACARDI_USERNAME='admin@cdpmerged.local'
export TRACARDI_PASSWORD='admin'
export AZURE_OPENAI_ENDPOINT='https://aoai-cdpmerged-fast.openai.azure.com/'
export AZURE_OPENAI_API_KEY=\$(az cognitiveservices account keys list --name aoai-cdpmerged-fast --resource-group rg-cdpmerged-fast --query key1 --output tsv)
export AZURE_OPENAI_DEPLOYMENT='gpt-4o-mini'

# Resume from checkpoint
poetry run python -c '
import asyncio
import sys
sys.path.insert(0, ".")
from src.enrichment.pipeline import run_enrichment

async def main():
    print("=== CONTINUING ENRICHMENT ===")
    print("Loading checkpoint automatically...")
    
    result = await run_enrichment(
        query='traits.email EXISTS OR traits.phone EXISTS',
        limit=None,
        phases=['contact_validation'],
        dry_run=False,
        batch_size=500
    )
    print(f'Phase 1 (contact_validation) complete')
    
    # Phase 2-7: Run on ALL profiles (these phases enrich from external sources)
    result2 = await run_enrichment(
        query='traits.name EXISTS',
        limit=516382,
        phases=['cbe_integration', 'website_discovery', 'google_places', 'descriptions', 'geocoding', 'deduplication'],
        dry_run=False,
        batch_size=500
    )
    print(f'Phases 2-7 complete')
    
    # Combine results
    result['phases'].extend(result2.get('phases', []))
    print(f'Completed: {result}')

asyncio.run(main())
' 2>&1 | tee logs/enrichment_continued_\$(date +%Y%m%d_%H%M%S).log

echo "Continuation complete at $(date)"
"
        
        echo "Continuation subagent spawned at $(date)"
        break
    fi
done
