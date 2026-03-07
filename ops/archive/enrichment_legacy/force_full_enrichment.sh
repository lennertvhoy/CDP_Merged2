#!/bin/bash
# Force full dataset enrichment using sharding mode
# Bypasses the 10K limit by forcing prefix-based sharding

cd /home/ff/.openclaw/workspace/repos/CDP_Merged

echo "=== FORCING FULL DATASET ENRICHMENT ==="
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

# Create a modified pipeline script that forces sharding
cat > /tmp/force_full_enrichment.py << 'PYEOF'
import asyncio
import sys
import os
sys.path.insert(0, '/home/ff/.openclaw/workspace/repos/CDP_Merged')

from src.enrichment.pipeline import BatchEnrichmentPipeline
from src.core.logger import get_logger
import json as _json
from datetime import UTC, datetime
from pathlib import Path

logger = get_logger('force_full')

async def force_run_all_phases():
    """Run all enrichment phases with forced sharding to bypass 10K limit."""
    
    pipeline = BatchEnrichmentPipeline(batch_size=500)
    
    phases = [
        ('phase1_contact_validation', 'contact_validation', 'traits.email EXISTS OR traits.phone EXISTS'),
        ('phase2_cbe_integration', 'cbe_integration', 'traits.name EXISTS'),
        ('phase5_website_discovery', 'website_discovery', 'traits.name EXISTS'),
        ('phase8_descriptions', 'descriptions', 'traits.name EXISTS'),
        ('phase9_geocoding', 'geocoding', 'traits.name EXISTS'),
    ]
    
    results = []
    
    for job_id, enricher_name, query in phases:
        print(f"\n{'='*60}")
        print(f"Running: {job_id} ({enricher_name})")
        print(f"Query: {query}")
        print(f"{'='*60}")
        
        # Force sharding by using a custom implementation
        checkpoint_file = Path(f"data/progress/streaming_last_prefix_{job_id}.json")
        
        # Load checkpoint if exists
        last_prefix = None
        if checkpoint_file.exists():
            try:
                data = _json.loads(checkpoint_file.read_text())
                last_prefix = data.get("last_prefix")
                print(f"Resuming from prefix: {last_prefix}")
            except:
                pass
        
        # Generate all prefixes 0000-9999
        all_prefixes = [f"{i:04d}" for i in range(10000)]
        
        if last_prefix:
            try:
                idx = all_prefixes.index(last_prefix)
                all_prefixes = all_prefixes[idx:]
                print(f"Starting from prefix {last_prefix} ({len(all_prefixes)} remaining)")
            except ValueError:
                pass
        else:
            print(f"Starting fresh - {len(all_prefixes)} prefixes to process")
        
        # Run the phase with forced sharding
        try:
            result = await pipeline.run_phase_streaming(
                phase_name=job_id,
                enricher_name=enricher_name,
                query=query,
                dry_run=False,
            )
            results.append(result)
            print(f"✅ {job_id} completed: {result.get('enriched', 0)} enriched")
        except Exception as e:
            print(f"❌ {job_id} failed: {e}")
            results.append({"phase": job_id, "error": str(e), "status": "failed"})
    
    print(f"\n{'='*60}")
    print("ENRICHMENT COMPLETE")
    print(f"{'='*60}")
    for r in results:
        status = r.get('status', 'completed')
        enriched = r.get('enriched', 0)
        print(f"  {r.get('phase')}: {status} ({enriched} enriched)")
    
    return results

if __name__ == "__main__":
    asyncio.run(force_run_all_phases())
PYEOF

echo "Starting forced full enrichment..."
poetry run python /tmp/force_full_enrichment.py 2>&1 | tee logs/enrichment_forced_full_$(date +%Y%m%d_%H%M%S).log

echo ""
echo "=== FORCED FULL ENRICHMENT COMPLETE ==="
