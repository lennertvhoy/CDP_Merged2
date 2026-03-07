# Data Backup Procedure

**Resource Group:** `rg-cdpmerged-fast`  
**Date:** 2026-02-25  
**Priority:** CRITICAL - Must complete before shutdown

---

## Overview

This document outlines the step-by-step procedure for backing up all critical data before the shutdown/restart test. Data integrity is paramount - no data loss is acceptable.

---

## Critical Data Components

### 1. Tracardi Data (HIGHEST PRIORITY)
**Location:** VM `vm-tracardi-cdpmerged-prod` (52.148.232.140)  
**Components:**
- MySQL database (customer data, events, profiles)
- Elasticsearch indices (event data, analytics)
- Configuration files

**Backup Methods:**

#### Option A: VM Snapshot (Recommended for speed)
```bash
# Create OS disk snapshot
az snapshot create \
  --resource-group rg-cdpmerged-fast \
  --source $(az vm show --name vm-tracardi-cdpmerged-prod --resource-group rg-cdpmerged-fast --query storageProfile.osDisk.managedDisk.id -o tsv) \
  --name tracardi-osdisk-snapshot-$(date +%Y%m%d) \
  --sku Standard_ZRS

# Create data disk snapshot (if separate)
az snapshot create \
  --resource-group rg-cdpmerged-fast \
  --source $(az disk list --resource-group rg-cdpmerged-fast --query "[?contains(name,'tracardi')].id" -o tsv | head -1) \
  --name tracardi-datadisk-snapshot-$(date +%Y%m%d) \
  --sku Standard_ZRS
```

#### Option B: Application-Level Backup (More granular)
```bash
# SSH into Tracardi VM
ssh azureuser@52.148.232.140

# Backup MySQL (inside VM)
docker exec tracardi-mysql mysqldump -u root -p<password> tracardi > /tmp/tracardi-mysql-$(date +%Y%m%d).sql

# Backup Elasticsearch indices (inside VM)
curl -X PUT "localhost:9200/_snapshot/backup_repo/%3Ctracardi-snapshot-%7Bnow%2Fd%7D%3E?wait_for_completion=true"

# Copy backups to Azure Storage (from VM)
az storage blob upload \
  --account-name stcdpmergedpr5roe \
  --container-name backups \
  --file /tmp/tracardi-mysql-$(date +%Y%m%d).sql \
  --name tracardi-mysql-$(date +%Y%m%d).sql
```

#### Option C: Tracardi Built-in Export
```bash
# Via Tracardi API
curl -X POST "http://52.148.232.140:8686/export" \
  -H "Authorization: Bearer <token>" \
  -d '{"indices": ["event", "profile", "session"]}'
```

---

### 2. Azure Search Index
**Service:** `cdpmerged-search`  
**Index:** `companies`  
**Status:** Can be rebuilt from source (Tracardi) but backup recommended

**Backup Procedure:**
```bash
# Export index documents
python3 << 'PY'
import requests
import json

endpoint = "https://cdpmerged-search.search.windows.net"
index_name = "companies"
api_key = "<azure-search-api-key>"  # From secrets

url = f"{endpoint}/indexes/{index_name}/docs/search?api-version=2023-11-01"
headers = {
    "Content-Type": "application/json",
    "api-key": api_key
}

# Get all documents (use $top=1000 for pagination)
response = requests.post(url, headers=headers, json={"search": "*", "top": 1000})
data = response.json()

with open(f"/tmp/cdp-search-backup-{index_name}.json", "w") as f:
    json.dump(data, f, indent=2)

print(f"Exported {len(data.get('value', []))} documents")
PY
```

**Index Schema Backup:**
```bash
# Save index schema
az rest --method get \
  --url "https://cdpmerged-search.search.windows.net/indexes/companies?api-version=2023-11-01" \
  --headers "api-key=<azure-search-api-key>" \
  --output json > /tmp/cdp-search-schema-companies.json
```

---

### 3. Container App Configuration
**App:** `ca-cdpmerged-fast`

**Backup Commands:**
```bash
mkdir -p /tmp/cdp-backup-$(date +%Y%m%d)

# Full configuration
az containerapp show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --output json > /tmp/cdp-backup-$(date +%Y%m%d)/containerapp-full-config.json

# Secret names (not values)
az containerapp secret list \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --query "[].name" -o tsv > /tmp/cdp-backup-$(date +%Y%m%d)/secrets-list.txt

# Environment variables
az containerapp show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --query "properties.template.containers[0].env" \
  -o json > /tmp/cdp-backup-$(date +%Y%m%d)/env-vars.json

# Scale configuration
az containerapp show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --query "properties.template.scale" \
  -o json > /tmp/cdp-backup-$(date +%Y%m%d)/scale-config.json
```

---

### 4. Azure OpenAI Configuration
**Service:** `aoai-cdpmerged-fast`

**Backup:**
```bash
# Save deployment information
az cognitiveservices account show \
  --name aoai-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --output json > /tmp/cdp-backup-$(date +%Y%m%d)/openai-config.json

# List deployments
az cognitiveservices account deployment list \
  --name aoai-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --output json > /tmp/cdp-backup-$(date +%Y%m%d)/openai-deployments.json
```

---

## Step-by-Step Backup Procedure

### Phase 1: Pre-Backup Verification (5 min)
```bash
# Verify all resources are healthy
echo "=== Resource Health Check ==="
az vm show --name vm-tracardi-cdpmerged-prod --resource-group rg-cdpmerged-fast --query "{name:name, powerState:instanceView.statuses[1].displayStatus}" -o table
az containerapp show --name ca-cdpmerged-fast --resource-group rg-cdpmerged-fast --query "{name:name, runningStatus:properties.runningStatus}" -o table
az search service show --name cdpmerged-search --resource-group rg-cdpmerged-fast --query "{name:name, status:status, provisioningState:provisioningState}" -o table
```

### Phase 2: Create VM Snapshot (10 min)
```bash
#!/bin/bash
set -e

RESOURCE_GROUP="rg-cdpmerged-fast"
VM_NAME="vm-tracardi-cdpmerged-prod"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

echo "=== Creating Tracardi VM Snapshot ==="
echo "Timestamp: $TIMESTAMP"

# Get OS disk ID
OS_DISK_ID=$(az vm show --name $VM_NAME --resource-group $RESOURCE_GROUP --query storageProfile.osDisk.managedDisk.id -o tsv)
echo "OS Disk: $OS_DISK_ID"

# Create snapshot
az snapshot create \
  --resource-group $RESOURCE_GROUP \
  --source $OS_DISK_ID \
  --name "tracardi-osdisk-snapshot-$TIMESTAMP" \
  --sku Standard_ZRS \
  --tags backup-type=pre-shutdown reason=iac-reproducibility-test

echo "✅ Snapshot created: tracardi-osdisk-snapshot-$TIMESTAMP"
```

### Phase 3: Backup Container App Config (2 min)
```bash
mkdir -p /tmp/cdp-backup-$(date +%Y%m%d)

az containerapp show --name ca-cdpmerged-fast --resource-group rg-cdpmerged-fast -o json > /tmp/cdp-backup-$(date +%Y%m%d)/containerapp-config.json
az containerapp secret list --name ca-cdpmerged-fast --resource-group rg-cdpmerged-fast -o json > /tmp/cdp-backup-$(date +%Y%m%d)/containerapp-secrets.json

echo "✅ Container App config backed up"
```

### Phase 4: Backup Search Index (5 min)
```bash
# Save schema
az rest --method get \
  --url "https://cdpmerged-search.search.windows.net/indexes/companies?api-version=2023-11-01" \
  --headers "api-key=$(az search admin-key show --service-name cdpmerged-search --resource-group rg-cdpmerged-fast --query primaryKey -o tsv)" \
  --output json > /tmp/cdp-backup-$(date +%Y%m%d)/search-index-schema.json

echo "✅ Search index schema backed up"
```

### Phase 5: Verify Backups (3 min)
```bash
echo "=== Backup Verification ==="
echo "Backup location: /tmp/cdp-backup-$(date +%Y%m%d)"
ls -la /tmp/cdp-backup-$(date +%Y%m%d)/

echo ""
echo "=== Snapshots ==="
az snapshot list --resource-group rg-cdpmerged-fast --query "[?contains(name,'tracardi')].{name:name, timeCreated:timeCreated, diskSizeGb:diskSizeGb}" -o table

echo ""
echo "✅ All backups complete. Review output above."
```

---

## Post-Backup Checklist

- [ ] VM snapshot created and verified in Azure Portal
- [ ] Container App config exported
- [ ] Search index schema exported
- [ ] Backup files exist in `/tmp/cdp-backup-YYYYMMDD/`
- [ ] Snapshot tags include `backup-type=pre-shutdown`
- [ ] All secrets documented in SECRETS_AUDIT.md

---

## Restore Procedures

### Restore Tracardi from Snapshot
```bash
# If VM needs restoration
az vm create \
  --name vm-tracardi-cdpmerged-prod-restored \
  --resource-group rg-cdpmerged-fast \
  --attach-os-disk $(az snapshot show --name tracardi-osdisk-snapshot-YYYYMMDD --resource-group rg-cdpmerged-fast --query id -o tsv) \
  --os-type Linux \
  --size Standard_B2s
```

### Restore Container App Config
```bash
# Re-apply configuration from backup
# Note: Secrets must be re-created manually or via IaC
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --yaml /tmp/cdp-backup-YYYYMMDD/containerapp-config.yaml
```

---

## Important Notes

1. **Tracardi VM must NOT be deleted** - Only snapshots/exports are safe
2. **Test the snapshot** - Verify it can create a working VM before shutdown
3. **Keep backups for 30 days** - Minimum retention for safety
4. **Document any manual changes** - Anything done outside IaC needs documentation

---

**Document Version:** 1.0  
**Last Updated:** 2026-02-25
