# KBO Data Cleanup and Enrichment Scripts

This directory contains Python scripts for cleaning, validating, and enriching KBO (Kruispuntbank Ondernemingen) data before ingestion into Tracardi.

## Installation

```bash
pip install -r requirements.txt
```

## Scripts

### 1. cleanup_kbo.py

Cleans raw KBO data by performing deduplication, validation, and normalization.

**Features:**
- KBO number format and check digit validation
- Postal code validation (Belgian format)
- Email format validation
- Phone number normalization to international format (+32)
- Company name normalization
- Address standardization
- Deduplication of enterprises
- Filtering of test/inactive records

**Usage:**
```bash
# Standard cleanup (strict KBO validation)
python cleanup_kbo.py --input-dir ./data/kbo --output-dir ./data/cleaned

# Lenient mode (skip KBO check digit validation for sample data)
python cleanup_kbo.py --input-dir ./data/kbo --output-dir ./data/cleaned --lenient
```

### 2. enrich_kbo.py

Enriches cleaned KBO data with additional information.

**Features:**
- Geocoding of addresses via Nominatim (OpenStreetMap) - FREE
- AI-generated company descriptions via Azure OpenAI
- Website discovery via pattern matching
- Caching to avoid redundant API calls

**Usage:**
```bash
# Basic enrichment (geocoding only, no AI)
python enrich_kbo.py --input-dir ./data/cleaned --output-dir ./data/enriched

# With Azure OpenAI for descriptions
python enrich_kbo.py \
    --input-dir ./data/cleaned \
    --output-dir ./data/enriched \
    --azure-endpoint https://your-resource.openai.azure.com \
    --azure-key your-api-key
```

**Environment Variables:**
You can also set Azure credentials via environment variables:
```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_DEPLOYMENT="gpt-4o-mini"
```

### 3. validate_kbo.py

Validates data quality and generates a quality report.

**Features:**
- KBO format and check digit validation
- Postal code validation
- Email format validation
- Relationship integrity checks
- Duplicate detection
- Quality scoring

**Usage:**
```bash
# Validate raw data
python validate_kbo.py --input-dir ./data/kbo --report ./reports/quality_report.json

# Validate cleaned data
python validate_kbo.py --input-dir ./data/cleaned --report ./reports/cleaned_quality.json

# Verbose output
python validate_kbo.py --input-dir ./data/cleaned -v
```

## Pipeline Workflow

```
Raw Data → Cleanup → Validation → Enrichment → Ingestion
    ↓           ↓           ↓             ↓           ↓
  enterprise  cleaned    quality       enriched    Tracardi
  address     data       report        data
  contact
  activity
  denomination
```

## Complete Example

```bash
# Step 1: Cleanup
python scripts/cleanup_kbo.py \
    --input-dir ./data/kbo \
    --output-dir ./data/cleaned \
    --lenient

# Step 2: Validate cleaned data
python scripts/validate_kbo.py \
    --input-dir ./data/cleaned \
    --report ./reports/cleaned_quality.json

# Step 3: Enrich
python scripts/enrich_kbo.py \
    --input-dir ./data/cleaned \
    --output-dir ./data/enriched \
    --geocoding-cache ./data/geocoding_cache.json

# Step 4: Ingest to Tracardi (separate process)
# python ingest_to_tracardi.py --input-dir ./data/enriched
```

## Cost Estimates

| Enrichment | Source | Monthly Cost | Priority |
|------------|--------|--------------|----------|
| Geocoding | Nominatim | €0 | P0 |
| Descriptions | Azure OpenAI | €20-40 | P0 |
| Websites | Pattern matching | €0 | P1 |
| Contact validation | Regex + MX | €0 | P1 |

**Total: €20-40/month** (well within €150 budget)

## Data Quality Metrics

The validation script checks for:
- Valid KBO numbers (format + check digit)
- Valid postal codes (Belgian 4-digit format)
- Valid email formats
- No duplicate enterprises
- Referential integrity between tables
- Complete address information

## Troubleshooting

### All enterprises filtered out
If using sample data with fake KBO numbers, use the `--lenient` flag to skip check digit validation.

### Geocoding rate limits
Nominatim has a 1 request/second rate limit. The script includes automatic throttling and caching.

### Missing optional dependencies
For website discovery, install dnspython:
```bash
pip install dnspython requests
```

## License

Internal use only - Portia Labs
