# KBO Full Import Guide

Complete guide for importing all 1.94M enterprises from the KBO zip file into PostgreSQL and Tracardi with maximum enrichment.

## Overview

This import pipeline will:
1. **Extract** all data from the KBO zip (enterprises, addresses, contacts, activities, denominations)
2. **Import** to PostgreSQL with complete data fields
3. **Enrich** using free and Azure services:
   - **FREE**: CBE Integration (industry classification, size estimates)
   - **FREE**: OpenStreetMap Geocoding (lat/lon coordinates)
   - **FREE**: Website Discovery (URL pattern matching + scraping)
   - **AZURE**: AI Descriptions via Azure OpenAI (GPT-4o-mini)
4. **Sync** to Tracardi for CDP functionality

## Prerequisites

### Required
- Python 3.11+
- PostgreSQL 14+ (local or Azure PostgreSQL Flexible Server)
- 10GB+ free disk space
- Azure OpenAI deployment (for AI descriptions)

### Optional
- Docker (for local PostgreSQL setup)
- 16GB+ RAM (for faster processing)

## Quick Start

### Option 1: Full Automated Pipeline

```bash
# 1. Start PostgreSQL (if using Docker)
docker-compose -f docker-compose.postgres.yml up -d

# 2. Run the complete pipeline
python scripts/run_full_kbo_import.py

# 3. For test mode (1000 records only)
python scripts/run_full_kbo_import.py --test
```

### Option 2: Step-by-Step

```bash
# 1. Prepare database schema
python scripts/migrate_schema_v2.2.py

# 2. Import KBO data
python scripts/import_kbo_full_enriched.py

# 3. Run enrichment
python scripts/enrich_companies_batch.py
```

## Database Setup

### Option A: Local PostgreSQL (Docker)

```bash
docker-compose -f docker-compose.postgres.yml up -d
```

Connection string: `postgresql://cdpadmin:cdpadmin123@localhost:5432/cdp?sslmode=disable`

### Option B: Azure PostgreSQL Flexible Server

1. Create Azure PostgreSQL Flexible Server in Azure Portal
2. Configure firewall rules to allow access
3. Update `.env.database`:

```ini
[connection_string]
url = postgresql://cdpadmin:<password>@your-server.postgres.database.azure.com:5432/cdp?sslmode=require
```

## Import Stages

### Stage 1: Schema Preparation

```bash
python scripts/migrate_schema_v2.2.py
```

Adds extended columns for KBO data:
- `enrichment_data` (JSONB) - Flexible storage for additional data
- `all_names` (TEXT[]) - Alternative company names
- `all_nace_codes` (VARCHAR[]) - All NACE activity codes
- `nace_descriptions` (TEXT[]) - NACE code descriptions
- `legal_form_code`, `status`, `juridical_situation`
- `type_of_enterprise`, `main_fax`, `establishment_count`

### Stage 2: Data Import

```bash
# Full import (1.94M enterprises, ~2-3 hours)
python scripts/import_kbo_full_enriched.py

# Test mode (1000 records, ~2 minutes)
python scripts/import_kbo_full_enriched.py --test

# Resume from checkpoint
python scripts/import_kbo_full_enriched.py --resume

# PostgreSQL only (skip Tracardi sync)
python scripts/import_kbo_full_enriched.py --skip-tracardi
```

**Data extracted:**
- Enterprise data (KBO number, status, legal form, founded date)
- Addresses (street, city, postal code, country)
- Contacts (email, phone, fax, website)
- Activities (all NACE codes with classifications)
- Denominations (all company names)
- Establishments (branch locations)

### Stage 3: Enrichment

```bash
# All enrichers
python scripts/enrich_companies_batch.py

# Specific enrichers only
python scripts/enrich_companies_batch.py --enrichers cbe,geocoding

# Limit number of companies
python scripts/enrich_companies_batch.py --limit 10000
```

**Enrichment sources:**

| Enricher | Cost | Description | Rate |
|----------|------|-------------|------|
| CBE | FREE | Industry classification, size estimates | Unlimited |
| Geocoding | FREE | Lat/lon via OpenStreetMap | 1 req/sec |
| Website | FREE | URL discovery + scraping | 20 req/sec |
| Description | AZURE | AI-generated descriptions | ~$20-40 for 500K |

### Stage 4: Verification

```bash
# Check PostgreSQL stats
python -c "
import asyncio
import asyncpg
import configparser

config = configparser.ConfigParser()
config.read('.env.database')
conn_str = config.get('connection_string', 'url')

async def check():
    conn = await asyncpg.connect(conn_str)
    total = await conn.fetchval('SELECT COUNT(*) FROM companies')
    enriched = await conn.fetchval(\"SELECT COUNT(*) FROM companies WHERE sync_status = 'enriched'\")
    with_nace = await conn.fetchval('SELECT COUNT(*) FROM companies WHERE industry_nace_code IS NOT NULL')
    with_geo = await conn.fetchval('SELECT COUNT(*) FROM companies WHERE geo_latitude IS NOT NULL')
    with_web = await conn.fetchval('SELECT COUNT(*) FROM companies WHERE website_url IS NOT NULL')
    with_ai = await conn.fetchval('SELECT COUNT(*) FROM companies WHERE ai_description IS NOT NULL')
    
    print(f'Total: {total:,}')
    print(f'Enriched: {enriched:,}')
    print(f'With NACE: {with_nace:,}')
    print(f'With geocoding: {with_geo:,}')
    print(f'With website: {with_web:,}')
    print(f'With AI description: {with_ai:,}')
    await conn.close()

asyncio.run(check())
"
```

## Expected Results

### Data Volumes

| Source | Records | Size |
|--------|---------|------|
| Enterprises | ~1,940,000 | 90MB CSV |
| Activities | ~35,000,000 | 1.5GB CSV |
| Addresses | ~2,860,000 | 300MB CSV |
| Contacts | ~698,000 | 34MB CSV |
| Denominations | ~3,320,000 | 150MB CSV |

### Processing Time

| Stage | Time | Notes |
|-------|------|-------|
| Import | 2-3 hours | Limited by disk I/O |
| CBE Enrichment | 30-60 min | Local processing |
| Geocoding | 6-8 hours | Rate limited to 1 req/sec |
| Website Discovery | 2-4 hours | Parallel processing |
| AI Descriptions | 2-3 hours | Depends on NACE diversity |
| **Total** | **12-18 hours** | Can run incrementally |

## Cost Estimation

### Free Tier (No Azure Credits)
- CBE Integration: €0
- Geocoding: €0
- Website Discovery: €0
- **Total: €0**

### With Azure OpenAI (AI Descriptions)
- GPT-4o-mini: ~$0.00015/1K input + $0.0006/1K output tokens
- For 500K unique NACE combinations: ~$20-40
- For full 1.94M companies: ~$30-50

## Checkpoint and Resume

All scripts support checkpointing:

```bash
# Import is interrupted, resume with:
python scripts/import_kbo_full_enriched.py --resume

# Check current checkpoint:
cat logs/import_kbo_full_state.json

# Clear checkpoint to start fresh:
rm logs/import_kbo_full_state.json
```

## Troubleshooting

### PostgreSQL Connection Failed

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check logs
docker logs cdp-postgres

# Restart
docker-compose -f docker-compose.postgres.yml restart
```

### Import Too Slow

- Increase batch size: `--batch-size 5000`
- Use SSD storage
- Run on machine with more RAM
- Skip Tracardi sync during import: `--skip-tracardi`

### Geocoding Rate Limited

- Geocoding is rate-limited to 1 req/sec (OpenStreetMap policy)
- This is intentional and cannot be increased
- Process runs in background, can be interrupted and resumed

### Tracardi Sync Failed

- Check Tracardi is running: `curl http://137.117.212.154:8686/health`
- Verify credentials in `.env`
- Can skip with `--skip-tracardi` and sync later

## Data Quality

### What Gets Imported

✅ **All active enterprises** from KBO (~1.94M)
✅ **Complete addresses** (street, city, postal code)
✅ **All contact info** (email, phone, fax, website when available)
✅ **All NACE codes** with descriptions
✅ **All company names** (alternative names)
✅ **Establishment counts**

### Enrichment Coverage

Expected coverage after full enrichment:
- CBE industry data: ~100% (all with NACE codes)
- Geocoding: ~85-90% (addresses that can be geocoded)
- Website discovery: ~30-40% (companies with discoverable websites)
- AI descriptions: ~100% (all with NACE codes)

## Next Steps

After import completes:

1. **Verify in chatbot**: Test queries like "How many IT companies in Oost-Vlaanderen?"
2. **Check Tracardi**: Visit http://137.117.212.154:8787 and verify profiles
3. **Run analytics**: Generate reports on industry distribution, geography
4. **Set up monitoring**: Schedule regular imports for KBO updates

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review checkpoint files in `logs/` directory
3. Consult `AGENTS.md` for architecture details
4. Check `WORKLOG.md` for recent changes
