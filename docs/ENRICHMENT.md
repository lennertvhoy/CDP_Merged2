# Data Enrichment Module

This module provides batch enrichment capabilities for Tracardi profiles, adding external data from 5 sources.

## Architecture

```
src/enrichment/
├── __init__.py              # Module exports
├── base.py                  # Base classes (BaseEnricher, EnrichmentResult, EnrichmentStats)
├── geocoding.py             # OpenStreetMap/Nominatim integration
├── descriptions.py          # Azure OpenAI company descriptions
├── website_discovery.py     # Pattern-based website discovery
├── cbe_integration.py       # CBE Open Data cross-reference
├── contact_validation.py    # Email/phone validation
├── pipeline.py              # Batch processing pipeline
└── progress.py              # Progress tracking & cost monitoring
```

## Data Sources

### 1. Contact Validation (Phase 1 - Quick Win)
- **Cost**: €0
- **Time**: ~2 hours for 516K profiles
- **Validates**: Email format, Belgian phone normalization
- **Adds**: `contact_quality_score`, normalized contacts

### 2. CBE Integration (Phase 2 - OPTIONAL)
- **Cost**: €0
- **Time**: ~2 hours for 516K profiles
- **Note**: ⚠️ **OPTIONAL** - Core KBO data (NACE codes, legal form, dates) already present from ingestion
- **Provides**: Industry classification labels, company size estimates, KBO normalization
- **Adds**: `cbe_enrichment` with industry_sector, size_estimate

**When to Skip:** If you can work with raw NACE codes and don't need human-readable labels.

**When to Enable:** When you need human-readable industry names (e.g., "Software" instead of NACE 62.01).

### 3. Website Discovery (Phase 3)
- **Cost**: €0
- **Time**: ~4 hours for 516K profiles (parallel)
- **Method**: Email domain extraction, pattern matching, HTTP validation
- **Adds**: `website_url`, `website_domain`, `website_verified`

### 4. AI Descriptions (Phase 4)
- **Cost**: ~€20-40 (depends on unique NACE codes)
- **Time**: ~8 hours for 516K profiles
- **Provider**: Azure OpenAI (GPT-4o-mini)
- **Adds**: `business_description` from NACE codes
- **Caching**: By NACE code to minimize costs

### 5. Geocoding (Phase 5 - Slow)
- **Cost**: €0
- **Time**: ~6 days for 516K profiles (1 req/sec)
- **Provider**: Nominatim (OpenStreetMap)
- **Rate Limit**: 1 request/second
- **Adds**: `geo_latitude`, `geo_longitude`

## Usage

### Quick Test (Dry Run)
```bash
# Test on 100 profiles (no updates)
python -m scripts.enrich_profiles --dry-run --limit 100

# Run contact validation only
python -m scripts.enrich_profiles --phase phase1_contact_validation --limit 1000
```

### Production Run
```bash
# Full pipeline on 10K profiles
python -m scripts.enrich_profiles --live --full --limit 10000

# Specific query
python -m scripts.enrich_profiles --live --query "traits.province:Antwerpen" --limit 5000
```

### Cost Estimation
```bash
# Estimate costs for 516K profiles
python -m scripts.enrich_profiles --estimate-costs
```

### Check Progress
```bash
# View current stats
python -m scripts.enrich_profiles --stats
```

## API Usage

### Basic Pipeline
```python
import asyncio
from src.enrichment.pipeline import BatchEnrichmentPipeline

async def run():
    pipeline = BatchEnrichmentPipeline(batch_size=100)
    
    # Run from Tracardi
    results = await pipeline.run_from_tracardi(
        query="*",
        limit=1000,
        phases=["phase1_contact_validation"],
        dry_run=True,
    )
    
    print(results)

asyncio.run(run())
```

### Individual Enricher
```python
import asyncio
from src.enrichment.contact_validation import ContactValidationEnricher

async def run():
    enricher = ContactValidationEnricher()
    
    profile = {
        "id": "test-1",
        "traits": {
            "email": "contact@company.be",
            "phone": "03 123 45 67",
        }
    }
    
    enriched = await enricher.enrich_profile(profile)
    print(enriched["traits"]["contact_quality_score"])

asyncio.run(run())
```

## Configuration

### Environment Variables
```bash
# Azure OpenAI (for descriptions)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini

# Tracardi (already configured)
TRACARDI_API_URL=http://localhost:8686
TRACARDI_USERNAME=admin
TRACARDI_PASSWORD=<redacted>
```

### Cache Files
Caches are stored in `./data/cache/`:
- `contact_validation_cache.json` - Validated contact cache
- `website_cache.json` - Discovered websites
- `cbe_cache.json` - CBE data
- `geocoding_cache.json` - Geocoded addresses
- `descriptions_cache.json` - AI-generated descriptions (by NACE)

## Progress Tracking

Progress is tracked in `./data/progress/`:
- Each job gets a JSON file with status
- Can resume interrupted batches
- Stats available via `--stats` flag

## Cost Tracking

Costs are tracked in `./data/costs.json`:
- Tracks API usage by source
- Budget limit: €150/month (configurable)
- Cost estimates before running

## Success Criteria

| Source | Target | Time | Cost |
|--------|--------|------|------|
| Contact Validation | 100% | ~2h | €0 |
| CBE Integration | 100% | ~2h | €0 |
| Website Discovery | 30%+ | ~4h | €0 |
| AI Descriptions | 100% (unique NACE) | ~8h | €20-40 |
| Geocoding | 80%+ | ~6 days | €0 |

**Total Estimated Cost: <€50** (well under €150 budget)

## Monitoring

### Check Job Status
```python
from src.enrichment.progress import ProgressTracker

tracker = ProgressTracker()
jobs = tracker.list_jobs()
for job in jobs:
    print(f"{job.job_id}: {job.status} ({job.progress_percent}%)")
```

### Get Cost Summary
```python
from src.enrichment.progress import CostTracker

tracker = CostTracker()
summary = tracker.get_summary()
print(f"Spent: €{summary['total_spent_eur']}")
print(f"Remaining: €{summary['remaining_eur']}")
```

## Testing

```bash
# Run enrichment tests
pytest tests/unit/test_enrichment.py -v

# Run with coverage
pytest tests/unit/test_enrichment.py --cov=src.enrichment -v
```

## Notes

- **Geocoding is slow** by design (1 req/sec Nominatim limit)
- **Run phases separately** for better control
- **Always use `--dry-run`** first to test
- **Monitor costs** with `--stats` flag
- **Caches persist** between runs for efficiency
