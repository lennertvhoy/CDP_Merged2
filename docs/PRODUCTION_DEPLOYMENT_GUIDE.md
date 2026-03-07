# CDP_Merged Production Deployment Guide

This guide provides step-by-step instructions for deploying the optimized CDP_Merged configuration to production.

## Prerequisites

- Azure CLI installed and authenticated
- PostgreSQL client (`psql`)
- Python 3.11+
- Access to Azure resources (Owner or Contributor role)

## Quick Start

```bash
# 1. Deploy database schema
psql -h cdp-postgres-b1ms.postgres.database.azure.com \
  -U cdpadmin -d postgres -f schema_optimized.sql

# 2. Run optimized import
python scripts/import_kbo_streaming.py --batch-size 1000

# 3. Deploy Azure Function
func azure functionapp publish cdpmerged-processor

# 4. Deploy monitoring
az deployment group create \
  --resource-group rg-cdpmerged \
  --template-file config/monitoring_dashboard.json
```

## Detailed Deployment

### 1. Database Migration

#### 1.1 Backup Current Database

```bash
# Create backup
BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
pg_dump -h cdp-postgres-b1ms.postgres.database.azure.com \
  -U cdpadmin -d postgres > $BACKUP_FILE

echo "Backup saved to: $BACKUP_FILE"
```

#### 1.2 Deploy Optimized Schema

```bash
# Connect and apply schema
psql "postgresql://cdpadmin:${DB_PASSWORD}@cdp-postgres-b1ms.postgres.database.azure.com:5432/postgres?sslmode=require" \
  -f schema_optimized.sql

# Verify indexes
psql "postgresql://cdpadmin:${DB_PASSWORD}@cdp-postgres-b1ms.postgres.database.azure.com:5432/postgres?sslmode=require" \
  -c "\di" | grep idx_companies

# Analyze tables
psql "postgresql://cdpadmin:${DB_PASSWORD}@cdp-postgres-b1ms.postgres.database.azure.com:5432/postgres?sslmode=require" \
  -c "ANALYZE companies;"
```

#### 1.3 Verify Database Health

```bash
python -c "
import asyncio
from src.services.postgresql_client_optimized import get_postgresql_client

async def check():
    client = get_postgresql_client()
    await client.connect()
    health = await client.health_check()
    print(f'Status: {health[\"status\"]}')
    print(f'Companies: {health[\"tables\"][\"companies\"]:,}')
    print(f'Pool size: {health[\"pool\"][\"size\"]}')
    await client.disconnect()

asyncio.run(check())
"
```

### 2. Import Process

#### 2.1 Test Mode (Recommended First)

```bash
# Import 10,000 records to verify setup
python scripts/import_kbo_streaming.py --test --batch-size 1000
```

#### 2.2 Full Import

```bash
# Start full import with resume capability
python scripts/import_kbo_streaming.py \
  --batch-size 1000 \
  --checkpoint-interval 10000

# Monitor progress
tail -f logs/import_kbo_streaming.log
```

#### 2.3 Resume Interrupted Import

```bash
# If import is interrupted, resume from checkpoint
python scripts/import_kbo_streaming.py --resume
```

### 3. Event Hub Configuration

#### 3.1 Deploy with ARM Template

```bash
# Deploy Event Hub with auto-inflate
az deployment group create \
  --name eventhub-deployment \
  --resource-group rg-cdpmerged \
  --template-file config/eventhub_production.json \
  --parameters namespaceName=cdpmerged-eventhub
```

#### 3.2 Verify Configuration

```bash
# Check throughput units
az eventhubs namespace show \
  --name cdpmerged-eventhub \
  --resource-group rg-cdpmerged \
  --query "sku"

# Check partition count
az eventhubs eventhub show \
  --name cdp-events \
  --namespace-name cdpmerged-eventhub \
  --resource-group rg-cdpmerged \
  --query "partitionCount"
```

#### 3.3 Update Application Settings

```bash
# Get connection string
EVENTHUB_CONNECTION=$(az eventhubs namespace authorization-rule keys list \
  --name RootManageSharedAccessKey \
  --namespace-name cdpmerged-eventhub \
  --resource-group rg-cdpmerged \
  --query primaryConnectionString -o tsv)

# Store in Key Vault (recommended)
az keyvault secret set \
  --vault-name cdpmerged-kv \
  --name eventhub-connection \
  --value "$EVENTHUB_CONNECTION"
```

### 4. Azure Functions Deployment

#### 4.1 Premium Plan (Recommended)

```bash
# Create Premium plan for cold start mitigation
az functionapp plan create \
  --name cdpmerged-premium \
  --resource-group rg-cdpmerged \
  --location northeurope \
  --sku EP2 \
  --min-instances 2 \
  --max-burst 10

# Create function app
az functionapp create \
  --name cdpmerged-processor \
  --resource-group rg-cdpmerged \
  --plan cdpmerged-premium \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --os-type Linux
```

#### 4.2 Deploy Function Code

```bash
cd functions

# Deploy
func azure functionapp publish cdpmerged-processor --build remote

# Verify deployment
az functionapp function show \
  --name cdpmerged-processor \
  --resource-group rg-cdpmerged \
  --function-name event_processor_optimized
```

#### 4.3 Configure Application Settings

```bash
# Required settings
az functionapp config appsettings set \
  --name cdpmerged-processor \
  --resource-group rg-cdpmerged \
  --settings \
    "PG_CONNECTION_STRING=postgresql://..." \
    "EventHubConnectionString=Endpoint=sb://..." \
    "PYTHON_ENABLE_WORKER_EXTENSIONS=1" \
    "FUNCTIONS_WORKER_PROCESS_COUNT=4"

# Enable always ready instances
az resource update \
  --ids $(az functionapp show --name cdpmerged-processor --resource-group rg-cdpmerged --query id -o tsv) \
  --set properties.siteConfig.minimumElasticInstanceCount=2
```

### 5. Monitoring Setup

#### 5.1 Deploy Dashboard

```bash
# Deploy monitoring dashboard
az deployment group create \
  --name monitoring-deployment \
  --resource-group rg-cdpmerged \
  --template-file config/monitoring_dashboard.json \
  --parameters \
    dashboardName=CDP-Production-Dashboard \
    postgresqlServerName=cdp-postgres-b1ms \
    eventHubNamespace=cdpmerged-eventhub \
    functionAppName=cdpmerged-processor
```

#### 5.2 Deploy Alert Rules

```bash
# Deploy alerts with email notification
az deployment group create \
  --name alerts-deployment \
  --resource-group rg-cdpmerged \
  --template-file config/alert_rules.json \
  --parameters \
    actionGroupName=CDP-Critical-Alerts \
    emailReceivers='["admin@yourcompany.com","ops@yourcompany.com"]'
```

#### 5.3 Verify Monitoring

```bash
# Check dashboard
az portal dashboard show \
  --name CDP-Production-Dashboard \
  --resource-group rg-cdpmerged

# List alert rules
az monitor metrics alert list \
  --resource-group rg-cdpmerged \
  --output table
```

## Configuration Reference

### PostgreSQL Connection Pool

| Setting | Development | Production | Description |
|---------|-------------|------------|-------------|
| min_size | 1 | 5 | Minimum connections |
| max_size | 10 | 25 | Maximum connections |
| command_timeout | 60 | 60 | Query timeout (seconds) |
| max_queries | 50000 | 100000 | Connection recycle |

### Event Hub

| Setting | Development | Production | Description |
|---------|-------------|------------|-------------|
| TUs | 1 | 2-10 | Throughput units |
| Partitions | 2 | 8 | Parallel processing |
| Retention | 1 day | 3 days | Message retention |
| Auto-inflate | Off | On | Auto-scaling |

### Azure Functions

| Setting | Consumption | Premium | Description |
|---------|-------------|---------|-------------|
| Cold start | 2-10s | <100ms | Function startup |
| Min instances | 0 | 2 | Always ready |
| Max burst | 200 | 10 | Scale limit |
| Cost | ~$20/mo | ~$150/mo | Monthly estimate |

## Troubleshooting

### Database Connection Issues

```bash
# Test connection
psql "postgresql://cdpadmin:${DB_PASSWORD}@cdp-postgres-b1ms.postgres.database.azure.com:5432/postgres?sslmode=require" \
  -c "SELECT version();"

# Check active connections
psql "postgresql://cdpadmin:${DB_PASSWORD}@cdp-postgres-b1ms.postgres.database.azure.com:5432/postgres?sslmode=require" \
  -c "SELECT count(*) FROM pg_stat_activity;"

# View slow queries
psql "postgresql://cdpadmin:${DB_PASSWORD}@cdp-postgres-b1ms.postgres.database.azure.com:5432/postgres?sslmode=require" \
  -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

### Import Issues

```bash
# Check checkpoint file
cat logs/import_kbo_streaming_state.json

# Resume import
python scripts/import_kbo_streaming.py --resume

# Reset and restart
rm logs/import_kbo_streaming_state.json
python scripts/import_kbo_streaming.py
```

### Function App Issues

```bash
# View function logs
az functionapp logs tail \
  --name cdpmerged-processor \
  --resource-group rg-cdpmerged

# Restart function app
az functionapp restart \
  --name cdpmerged-processor \
  --resource-group rg-cdpmerged

# Check function status
az functionapp function show \
  --name cdpmerged-processor \
  --resource-group rg-cdpmerged \
  --function-name event_processor_optimized \
  --query "properties/state"
```

### Event Hub Issues

```bash
# Check Event Hub metrics
az monitor metrics list \
  --resource $(az eventhubs namespace show --name cdpmerged-eventhub --resource-group rg-cdpmerged --query id -o tsv) \
  --metric IncomingMessages ThrottledRequests \
  --interval PT1M

# Check consumer lag
# (Use Azure Monitor or custom tooling)
```

## Rollback Procedures

### Database Rollback

```bash
# Restore from backup
psql -h cdp-postgres-b1ms.postgres.database.azure.com \
  -U cdpadmin -d postgres < backup_YYYYMMDD.sql
```

### Function Rollback

```bash
# Deploy previous version
func azure functionapp publish cdpmerged-processor \
  --slot staging

# Swap slots
az functionapp deployment slot swap \
  --name cdpmerged-processor \
  --resource-group rg-cdpmerged \
  --slot staging \
  --target-slot production
```

### Event Hub Rollback

```bash
# Scale down TUs
az eventhubs namespace update \
  --name cdpmerged-eventhub \
  --resource-group rg-cdpmerged \
  --sku Standard \
  --capacity 1
```

## Security Checklist

- [ ] Database credentials in Key Vault
- [ ] Event Hub connection strings in Key Vault
- [ ] Function App using Managed Identity
- [ ] SSL/TLS enforced for PostgreSQL
- [ ] Network restrictions configured
- [ ] Audit logging enabled
- [ ] Alert rules configured
- [ ] Backup strategy in place

## Performance Validation

```bash
# Run validation script
python scripts/benchmark_memory.py

# Expected results:
# - Import: >500 records/second
# - Query: <10ms for indexed lookups
# - Connection pool: 5-25 active connections
```

## Support Contacts

- **Database Issues**: Database Administrator
- **Azure Infrastructure**: Cloud Operations Team
- **Application Issues**: Development Team
- **Monitoring/Alerts**: DevOps Team

---

**Last Updated:** 2026-02-28  
**Version:** 1.0
