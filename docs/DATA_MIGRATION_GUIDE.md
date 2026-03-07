# Data Migration Guide

**Resource Group:** `rg-cdpmerged-fast`  
**Purpose:** Document data preservation during IaC redeployment  
**Date:** 2026-02-25

---

## Overview

This guide outlines how to safely migrate data when redeploying infrastructure via IaC. The goal is zero data loss while maintaining reproducibility.

---

## Pre-Migration Checklist

### 1. Inventory Data Sources
- [ ] Tracardi VM (`vm-tracardi-cdpmerged-prod`) - MySQL & Elasticsearch
- [ ] Azure Search Index (`companies`)
- [ ] Container App Configuration & Secrets
- [ ] Azure OpenAI fine-tuned models (if any)

### 2. Verify Backups Exist
```bash
# Check VM snapshot
az snapshot list --resource-group rg-cdpmerged-fast \
  --query "[?contains(name,'tracardi')].{name:name, timeCreated:timeCreated}"

# Check local backups
ls -la /tmp/cdp-backup-$(date +%Y%m%d)/
```

### 3. Document Current State
```bash
# Export all resource configurations
az resource list --resource-group rg-cdpmerged-fast --output json > /tmp/pre-migration-resources.json
```

---

## Migration Scenarios

### Scenario 1: Container App Only (No Data Loss Risk)
**When:** Updating Container App configuration, scale settings, or secrets

**Steps:**
1. Export current configuration
2. Apply IaC changes
3. Verify secrets are recreated
4. Test application

```bash
# Before migration
az containerapp show --name ca-cdpmerged-fast --resource-group rg-cdpmerged-fast -o json > /tmp/ca-pre-migration.json

# Apply IaC (terraform apply or deployment script)
# ...

# After migration - verify
az containerapp show --name ca-cdpmerged-fast --resource-group rg-cdpmerged-fast -o json > /tmp/ca-post-migration.json
diff <(jq -S . /tmp/ca-pre-migration.json) <(jq -S . /tmp/ca-post-migration.json)
```

---

### Scenario 2: Full Resource Group Redeployment (HIGH RISK)
**When:** Complete infrastructure tear-down and rebuild

**⚠️ WARNING:** Tracardi VM must be preserved or fully backed up!

**Steps:**

#### Phase 1: Data Export
```bash
#!/bin/bash
set -e

RESOURCE_GROUP="rg-cdpmerged-fast"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="/tmp/cdp-migration-$TIMESTAMP"

mkdir -p $BACKUP_DIR

echo "=== Phase 1: Exporting All Data ==="

# 1. Tracardi VM Snapshot (CRITICAL)
echo "Creating VM snapshot..."
VM_OS_DISK=$(az vm show --name vm-tracardi-cdpmerged-prod --resource-group $RESOURCE_GROUP --query storageProfile.osDisk.managedDisk.id -o tsv)
az snapshot create \
  --resource-group $RESOURCE_GROUP \
  --source $VM_OS_DISK \
  --name "tracardi-migration-snapshot-$TIMESTAMP" \
  --sku Standard_ZRS

# 2. Export MySQL Data (if accessible)
echo "Exporting MySQL data..."
# Note: Requires SSH access to VM
ssh azureuser@52.148.232.140 "docker exec tracardi-mysql mysqldump -u root -p\$MYSQL_PASSWORD tracardi" > $BACKUP_DIR/tracardi-mysql-$TIMESTAMP.sql

# 3. Export Search Index
echo "Exporting search index..."
SEARCH_KEY=$(az search admin-key show --service-name cdpmerged-search --resource-group $RESOURCE_GROUP --query primaryKey -o tsv)
curl -s "https://cdpmerged-search.search.windows.net/indexes/companies/docs?api-version=2023-11-01&search=*&\$top=1000" \
  -H "api-key: $SEARCH_KEY" > $BACKUP_DIR/search-index-$TIMESTAMP.json

# 4. Export All Configurations
echo "Exporting configurations..."
az containerapp show --name ca-cdpmerged-fast --resource-group $RESOURCE_GROUP -o json > $BACKUP_DIR/containerapp-config.json
az cognitiveservices account show --name aoai-cdpmerged-fast --resource-group $RESOURCE_GROUP -o json > $BACKUP_DIR/openai-config.json
az search service show --name cdpmerged-search --resource-group $RESOURCE_GROUP -o json > $BACKUP_DIR/search-config.json

echo "✅ Phase 1 Complete. Backups in: $BACKUP_DIR"
```

#### Phase 2: Resource Migration
```bash
echo "=== Phase 2: Resource Migration ==="

# Option A: If VM must be preserved (RECOMMENDED)
# 1. Stop VM (don't delete)
az vm deallocate --name vm-tracardi-cdpmerged-prod --resource-group $RESOURCE_GROUP

# 2. Delete other resources (Container App, Search, etc.)
# Note: Delete in reverse dependency order
az containerapp delete --name ca-cdpmerged-fast --resource-group $RESOURCE_GROUP --yes
az search service delete --name cdpmerged-search --resource-group $RESOURCE_GROUP --yes
# ... etc

# 3. Redeploy via IaC
# terraform apply

# 4. Update VM network configuration if needed
# (new VNet, subnets, NSG rules)

# Option B: Full rebuild (requires data restore)
# 1. Destroy all resources
# terraform destroy

# 2. Recreate VM from snapshot
az disk create \
  --resource-group $RESOURCE_GROUP \
  --name tracardi-osdisk-restored \
  --source "tracardi-migration-snapshot-$TIMESTAMP"

az vm create \
  --name vm-tracardi-cdpmerged-prod \
  --resource-group $RESOURCE_GROUP \
  --attach-os-disk $(az disk show --name tracardi-osdisk-restored --resource-group $RESOURCE_GROUP --query id -o tsv) \
  --os-type Linux \
  --size Standard_B2s

# 3. Redeploy other resources
# terraform apply
```

#### Phase 3: Data Restoration
```bash
echo "=== Phase 3: Data Restoration ==="

# Restore Search Index (if needed)
SEARCH_KEY=$(az search admin-key show --service-name cdpmerged-search --resource-group $RESOURCE_GROUP --query primaryKey -o tsv)

# Upload documents back to index
python3 << 'PY'
import json
import requests

with open(f"{BACKUP_DIR}/search-index-$TIMESTAMP.json") as f:
    data = json.load(f)

endpoint = "https://cdpmerged-search.search.windows.net"
index_name = "companies"
api_key = "$SEARCH_KEY"

for doc in data.get('value', []):
    # Remove system properties
    doc.pop('@search.score', None)
    
    response = requests.post(
        f"{endpoint}/indexes/{index_name}/docs/index?api-version=2023-11-01",
        headers={"Content-Type": "application/json", "api-key": api_key},
        json={"value": [{"@search.action": "upload", **doc}]}
    )
    if response.status_code not in [200, 201]:
        print(f"Failed to upload doc: {response.text}")

print("Index restoration complete")
PY

echo "✅ Phase 3 Complete"
```

---

### Scenario 3: Secrets Rotation During Migration

When secrets need to be rotated during migration:

```bash
# 1. Generate new secrets
NEW_OPENAI_KEY=$(az cognitiveservices account keys regenerate \
  --name aoai-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --key-name key1 \
  --query key1 -o tsv)

NEW_SEARCH_KEY=$(az search admin-key regenerate \
  --service-name cdpmerged-search \
  --resource-group rg-cdpmerged-fast \
  --key-name primary \
  --query primaryKey -o tsv)

# 2. Update Container App with new secrets
az containerapp secret set \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --secrets \
    azure-openai-key="$NEW_OPENAI_KEY" \
    azure-search-api-key="$NEW_SEARCH_KEY"

# 3. Verify application works
curl -s https://ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io/health
```

---

## Post-Migration Verification

### Automated Verification Script
```bash
#!/bin/bash
set -e

RESOURCE_GROUP="rg-cdpmerged-fast"
CONTAINER_APP="ca-cdpmerged-fast"
SEARCH_SERVICE="cdpmerged-search"
OPENAI_SERVICE="aoai-cdpmerged-fast"

echo "=== Post-Migration Verification ==="

# 1. Container App Health
echo "[1/6] Checking Container App..."
CA_FQDN=$(az containerapp show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv)
CA_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://$CA_FQDN/project/settings || echo "FAILED")
if [ "$CA_STATUS" = "200" ]; then
    echo "✅ Container App: HEALTHY"
else
    echo "❌ Container App: UNHEALTHY (HTTP $CA_STATUS)"
fi

# 2. Azure Search
echo "[2/6] Checking Azure Search..."
SEARCH_STATUS=$(az search service show --name $SEARCH_SERVICE --resource-group $RESOURCE_GROUP --query status -o tsv)
if [ "$SEARCH_STATUS" = "running" ]; then
    echo "✅ Azure Search: RUNNING"
else
    echo "❌ Azure Search: $SEARCH_STATUS"
fi

# 3. Azure OpenAI
echo "[3/6] Checking Azure OpenAI..."
OPENAI_ENDPOINT=$(az cognitiveservices account show --name $OPENAI_SERVICE --resource-group $RESOURCE_GROUP --query properties.endpoint -o tsv)
if [ -n "$OPENAI_ENDPOINT" ]; then
    echo "✅ Azure OpenAI: CONFIGURED ($OPENAI_ENDPOINT)"
else
    echo "❌ Azure OpenAI: NOT CONFIGURED"
fi

# 4. Tracardi Connection
echo "[4/6] Checking Tracardi connection..."
TRACARDI_IP=$(az vm show --name vm-tracardi-cdpmerged-prod --resource-group $RESOURCE_GROUP --query publicIps -o tsv 2>/dev/null || echo "52.148.232.140")
TRACARDI_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://$TRACARDI_IP:8686/health || echo "FAILED")
if [ "$TRACARDI_STATUS" = "200" ]; then
    echo "✅ Tracardi: HEALTHY"
else
    echo "⚠️  Tracardi: Status $TRACARDI_STATUS (may be expected if VM stopped)"
fi

# 5. Secrets Configured
echo "[5/6] Checking secrets..."
SECRET_COUNT=$(az containerapp secret list --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --query "length(@)" -o tsv)
if [ "$SECRET_COUNT" -ge 5 ]; then
    echo "✅ Secrets: $SECRET_COUNT configured"
else
    echo "⚠️  Secrets: Only $SECRET_COUNT configured (expected 7)"
fi

# 6. End-to-End Test
echo "[6/6] End-to-end query test..."
TEST_RESPONSE=$(curl -s -X POST "https://$CA_FQDN/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}' \
  -w "\n%{http_code}" 2>/dev/null || echo "FAILED")

if echo "$TEST_RESPONSE" | grep -q "200\|201\|202"; then
    echo "✅ E2E Test: PASSED"
else
    echo "⚠️  E2E Test: Response was: $TEST_RESPONSE"
fi

echo ""
echo "=== Verification Complete ==="
```

---

## Data Integrity Checklist

After migration, verify:

- [ ] Tracardi VM boots successfully
- [ ] MySQL data is accessible
- [ ] Elasticsearch indices exist
- [ ] Container App responds to requests
- [ ] Azure Search returns results
- [ ] Azure OpenAI generates responses
- [ ] All 7 secrets are configured
- [ ] Search index document count matches pre-migration
- [ ] Sample queries return expected results

---

## Rollback Procedure

If migration fails:

```bash
#!/bin/bash
# Emergency rollback

# 1. Stop new deployment
az containerapp update --name ca-cdpmerged-fast --resource-group rg-cdpmerged-fast --min-replicas 0

# 2. Restore VM from snapshot (if VM was recreated)
az vm delete --name vm-tracardi-cdpmerged-prod --resource-group rg-cdpmerged-fast --yes --force

az disk create \
  --resource-group rg-cdpmerged-fast \
  --name tracardi-osdisk-rollback \
  --source "tracardi-migration-snapshot-YYYYMMDD"

az vm create \
  --name vm-tracardi-cdpmerged-prod \
  --resource-group rg-cdpmerged-fast \
  --attach-os-disk $(az disk show --name tracardi-osdisk-rollback --resource-group rg-cdpmerged-fast --query id -o tsv) \
  --os-type Linux \
  --size Standard_B2s

# 3. Restore original Container App config
az containerapp update --name ca-cdpmerged-fast --resource-group rg-cdpmerged-fast --yaml /tmp/cdp-backup-YYYYMMDD/containerapp-config.yaml

# 4. Restart
az containerapp update --name ca-cdpmerged-fast --resource-group rg-cdpmerged-fast --min-replicas 1

echo "Rollback complete. Verify application functionality."
```

---

## Important Notes

1. **Always backup before migration** - No exceptions
2. **Test restore procedure** - Verify snapshots work before you need them
3. **Document deviations** - Any manual changes from IaC must be documented
4. **Keep migration window short** - Minimize downtime between backup and restore
5. **Have rollback plan ready** - Know how to undo if things go wrong

---

**Document Version:** 1.0  
**Last Updated:** 2026-02-25
