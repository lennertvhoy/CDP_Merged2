# Handoff: KBO Full Import to Azure PostgreSQL

**Date:** 2026-03-03  
**Status:** Infrastructure Ready - Pending Deployment  
**Task:** Import all 1.94M KBO enterprises into Azure PostgreSQL with enrichment

---

## What Was Completed

### 1. Azure PostgreSQL Flexible Server Infrastructure (IaC)

**New Terraform Files Created:**
- `infra/terraform/postgresql.tf` - Azure PostgreSQL Flexible Server resources
- `infra/terraform/variables-postgresql.tf` - PostgreSQL configuration variables

**Resources Defined:**
- `azurerm_postgresql_flexible_server.cdp` - Managed PostgreSQL server
- `azurerm_postgresql_flexible_server_database.cdp` - CDP database
- Firewall rules for Azure services and app VM access
- PostgreSQL extensions: UUID_OSSP, PG_TRGM, PG_STAT_STATEMENTS
- Performance-optimized settings for bulk imports

**Infrastructure Fixes Applied:**
- Removed duplicate variable declarations (`variables-cost.tf`)
- Removed duplicate Log Analytics workspace resource
- Commented out incomplete Container App resources in `cost-optimization.tf`
- Added missing variables: `budget_alert_email`, `monthly_budget_eur`, `enable_container_app`

### 2. Import Pipeline Scripts

**Scripts Created:**
- `scripts/import_kbo_full_enriched.py` - Full KBO import with all data fields
- `scripts/enrich_companies_batch.py` - Batch enrichment pipeline
- `scripts/run_full_kbo_import.py` - Master orchestration script
- `scripts/migrate_schema_v2.2.py` - Database schema migration

**Data Extracted:**
- All enterprises (~1.94M records)
- All addresses (street, city, postal code)
- All contacts (email, phone, fax, website)
- All activities (NACE codes with classifications)
- All denominations (alternative names)
- Establishment counts

**Enrichment Sources:**
| Service | Cost | Description |
|---------|------|-------------|
| CBE Integration | FREE | Industry classification, size estimates |
| OpenStreetMap | FREE | Geocoding (1 req/sec rate limited) |
| Website Discovery | FREE | URL pattern matching + scraping |
| Azure OpenAI | ~$30-50 | AI-generated descriptions |

### 3. Schema Extensions

**New Columns Added to `companies` table:**
```sql
enrichment_data JSONB
all_names TEXT[]
all_nace_codes VARCHAR(10)[]
nace_descriptions TEXT[]
legal_form_code VARCHAR(10)
status VARCHAR(20)
juridical_situation VARCHAR(50)
type_of_enterprise VARCHAR(20)
main_fax VARCHAR(50)
establishment_count INTEGER
```

---

## Execution Steps

### Step 1: Deploy Azure PostgreSQL Flexible Server

```bash
cd /home/ff/.openclaw/workspace/repos/CDP_Merged/infra/terraform

# Login to Azure
az login

# Initialize Terraform (if not already done)
terraform init

# Plan the deployment
terraform plan -target=azurerm_postgresql_flexible_server.cdp \
  -target=azurerm_postgresql_flexible_server_database.cdp \
  -target=azurerm_postgresql_flexible_server_firewall_rule.allow_azure_services \
  -target=azurerm_postgresql_flexible_server_firewall_rule.allow_app_vm

# Apply the deployment
terraform apply -target=azurerm_postgresql_flexible_server.cdp \
  -target=azurerm_postgresql_flexible_server_database.cdp \
  -target=azurerm_postgresql_flexible_server_firewall_rule.allow_azure_services \
  -target=azurerm_postgresql_flexible_server_firewall_rule.allow_app_vm
```

**Expected Output:**
- PostgreSQL server FQDN: `psql-cdpmerged-prod-XXXX.postgres.database.azure.com`
- Database: `cdp`
- Username: `cdpadmin`
- Password: Auto-generated (see Terraform output)

### Step 2: Configure Database Connection

```bash
# Get connection string from Terraform output
cd /home/ff/.openclaw/workspace/repos/CDP_Merged/infra/terraform
terraform output postgresql_connection_string

# Update local .env.database
cat > .env.database << 'EOF'
[database]
host = psql-cdpmerged-prod-XXXX.postgres.database.azure.com
port = 5432
database = cdp
username = cdpadmin
password = <PASSWORD_FROM_TERRAFORM>
ssl_mode = require

[connection_string]
url = postgresql://cdpadmin:<PASSWORD>@psql-cdpmerged-prod-XXXX.postgres.database.azure.com:5432/cdp?sslmode=require

[azure]
resource_group = rg-cdpmerged-prod
server_name = psql-cdpmerged-prod-XXXX
location = westeurope
EOF
```

### Step 3: Run Schema Migration

```bash
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
source .venv/bin/activate

# Run migration
python scripts/migrate_schema_v2.2.py
```

**Expected Result:**
- All extended columns created
- Indexes added for new columns
- ~10-15 seconds execution time

### Step 4: Run Full Import Pipeline

#### Option A: Automated Pipeline (Recommended)

```bash
# Full pipeline (~12-18 hours total)
python scripts/run_full_kbo_import.py

# Or test mode first (1000 records, ~5 minutes)
python scripts/run_full_kbo_import.py --test
```

#### Option B: Step-by-Step

```bash
# Step 1: Import only (~2-3 hours)
python scripts/import_kbo_full_enriched.py --skip-tracardi

# Step 2: Enrichment (~8-12 hours)
# CBE + Geocoding + Website (free)
python scripts/enrich_companies_batch.py --enrichers cbe,geocoding,website

# Step 3: AI Descriptions (~2-3 hours, uses Azure OpenAI credits)
python scripts/enrich_companies_batch.py --enrichers description

# Step 4: Sync to Tracardi
python scripts/import_kbo_full_enriched.py --skip-tracardi  # Already synced during import
```

### Step 5: Verify Results

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
    
    print(f'PostgreSQL Statistics:')
    print(f'  Total companies: {total:,}')
    print(f'  Enriched: {enriched:,}')
    print(f'  With NACE code: {with_nace:,}')
    print(f'  With geocoding: {with_geo:,}')
    print(f'  With website: {with_web:,}')
    print(f'  With AI description: {with_ai:,}')
    await conn.close()

asyncio.run(check())
"

# Check Tracardi
curl -s http://137.117.212.154:8686/profiles/count
```

---

## Monitoring & Troubleshooting

### Progress Monitoring

```bash
# Watch import progress
tail -f logs/import_kbo_full.log

# Watch enrichment progress
tail -f logs/enrichment.log

# Check checkpoint status
cat logs/import_kbo_full_state.json
```

### Resume from Interruption

```bash
# Resume import
python scripts/import_kbo_full_enriched.py --resume

# Resume enrichment (tracks progress in database)
python scripts/enrich_companies_batch.py
```

### Common Issues

**1. PostgreSQL Connection Failed**
```bash
# Check firewall rules
az postgres flexible-server firewall-rule list \
  --resource-group rg-cdpmerged-prod \
  --name psql-cdpmerged-prod-XXXX

# Add client IP if needed
az postgres flexible-server firewall-rule create \
  --resource-group rg-cdpmerged-prod \
  --name psql-cdpmerged-prod-XXXX \
  --rule-name AllowClientIP \
  --start-ip-address $(curl -s ifconfig.me) \
  --end-ip-address $(curl -s ifconfig.me)
```

**2. Import Too Slow**
- Increase batch size: `--batch-size 5000`
- Scale up PostgreSQL SKU in Terraform
- Run import from Azure VM in same region

**3. Geocoding Rate Limited**
- This is expected (1 req/sec to OpenStreetMap)
- Process runs in background
- Can be interrupted and resumed anytime

---

## Cost Estimation

### Azure PostgreSQL Flexible Server

| SKU | Monthly Cost | Use Case |
|-----|--------------|----------|
| B_Standard_B2s (default) | ~€15-20 | Dev/Test |
| GP_Standard_D2s_v3 | ~€60-80 | Production |
| GP_Standard_D4s_v3 | ~€120-150 | High volume |

**Storage:** €0.10/GB/month (32GB = ~€3.20/month)

**Backup:** Included up to 7 days

### Azure OpenAI (AI Descriptions)

- GPT-4o-mini: $0.00015/1K input + $0.0006/1K output tokens
- Estimated: ~$30-50 for full 1.94M dataset
- Only processes unique NACE combinations (cached)

### Total Expected Cost

| Phase | Cost |
|-------|------|
| Infrastructure (B2s) | ~€20/month |
| AI Descriptions | ~$30-50 one-time |
| **Total First Month** | **~€70-100** |

---

## Files Modified/Created

**Infrastructure:**
- `infra/terraform/postgresql.tf` (NEW)
- `infra/terraform/variables-postgresql.tf` (NEW)
- `infra/terraform/outputs.tf` (MODIFIED - added PostgreSQL outputs)
- `infra/terraform/cost-optimization.tf` (MODIFIED - fixed validation errors)
- `infra/terraform/variables-cost-opt.tf` (MODIFIED - added missing variables)
- `infra/terraform/variables-cost.tf` (DELETED - duplicates)

**Scripts:**
- `scripts/import_kbo_full_enriched.py` (NEW)
- `scripts/enrich_companies_batch.py` (NEW)
- `scripts/run_full_kbo_import.py` (NEW)
- `scripts/migrate_schema_v2.2.py` (NEW)

**Documentation:**
- `docs/KBO_IMPORT_GUIDE.md` (NEW)
- `docs/HANDOFF_KBO_IMPORT_AZURE_POSTGRESQL.md` (NEW - this file)
- `schema_optimized.sql` (MODIFIED - added extended columns)
- `.env.database` (NEW - local config template)
- `docker-compose.postgres.yml` (NEW - for local testing)

---

## Next Actions

1. **Deploy Azure PostgreSQL:**
   ```bash
   cd infra/terraform && terraform apply
   ```

2. **Run Test Import:**
   ```bash
   python scripts/run_full_kbo_import.py --test
   ```

3. **If test succeeds, run full import:**
   ```bash
   python scripts/run_full_kbo_import.py
   ```

4. **Verify results in chatbot:**
   - Start chatbot: `chainlit run src/app.py`
   - Test query: "How many IT companies in Oost-Vlaanderen?"

5. **Monitor costs in Azure Portal:**
   - Set up budget alerts
   - Review PostgreSQL metrics

---

## Contact & References

- **AGENTS.md** - Project operating rules
- **PROJECT_STATE.yaml** - Structured state tracking
- **docs/KBO_IMPORT_GUIDE.md** - Detailed import documentation
- **WORKLOG.md** - Session log with recent changes

**Terraform State Location:** `infra/terraform/terraform.tfstate`

**Log Files:**
- `logs/import_kbo_full.log`
- `logs/enrichment.log`
- `logs/import_kbo_full_state.json`
