# Pre-Flight Check Report

**Date:** 2026-02-25  
**Time:** 16:06 CET  
**Resource Group:** `rg-cdpmerged-fast`  
**Status:** ✅ READY FOR SHUTDOWN TEST

---

## Check Results

### ✅ [1/5] Azure Login
- **Subscription:** Visual Studio Enterprise-abonnement – MPN
- **User:** l.vanhoyweghen@it1.be
- **Status:** Authenticated and authorized

### ✅ [2/5] Resource Status
All 20 resources provisioned and healthy:
- Container Apps: ca-cdpmerged-fast ✅
- Container Registry: ca67b3b5dbe8acr ✅
- Cognitive Services: aoai-cdpmerged-fast ✅
- Search Services: cdpmerged-search ✅
- VMs: vm-tracardi-cdpmerged-prod, vm-data-cdpmerged-prod ✅
- Storage: stcdpmergedpr5roe ✅
- Networking: VNets, NSGs, NICs, Public IPs ✅

### ✅ [3/5] Container App Scale Configuration
```json
{
  "minReplicas": 0,         // ✅ Scale-to-zero enabled
  "maxReplicas": 5,         // ✅ Reduced from 10
  "hasScaleRules": [{       // ✅ HTTP scale rule configured
    "name": "http-rule",
    "http": {
      "metadata": {
        "concurrentRequests": "10"
      }
    }
  }]
}
```

### ✅ [4/5] Tracardi VM Status
```json
{
  "name": "vm-tracardi-cdpmerged-prod",
  "size": "Standard_B2s",
  "osDisk": "osdisk-tracardi-cdpmerged-prod"
}
```
- VM identified for snapshot
- OS disk: `osdisk-tracardi-cdpmerged-prod`

### ✅ [5/5] Secrets Configuration
All 7 secrets configured:
1. ✅ azure-openai-key
2. ✅ ca67b3b5dbe8acrazurecrio-ca67b3b5dbe8acr
3. ✅ ghcrio-lennertvhoy
4. ✅ openai-api-key
5. ✅ tracardi-password
6. ✅ azure-search-api-key
7. ✅ resend-api-key

---

## Cost Optimizations Applied

| Optimization | Status | Impact |
|--------------|--------|--------|
| Container App scale-to-zero | ✅ Applied | ~€25-30/month savings |
| HTTP auto-scaling rule | ✅ Applied | Efficient scaling |
| Secrets documentation | ✅ Complete | IaC reproducibility |
| Backup procedures | ✅ Documented | Data preservation |
| Migration guide | ✅ Complete | Risk mitigation |

---

## Pre-Shutdown Checklist Status

| Item | Status |
|------|--------|
| All secrets documented in SECRETS_AUDIT.md | ✅ |
| Backup procedure reviewed | ✅ |
| VM snapshot can be created | ✅ |
| Container App scale-to-zero verified | ✅ |
| IaC files created | ✅ |
| Test script validated | ✅ |
| Rollback plan documented | ✅ |

---

## Recommended Test Sequence

```bash
# Step 1: Run export phase
bash /home/ff/.openclaw/workspace/CDP_Merged/infra/scripts/shutdown-restart-test.sh export

# Step 2: Create VM snapshot
bash /home/ff/.openclaw/workspace/CDP_Merged/infra/scripts/shutdown-restart-test.sh backup

# Step 3: Stop resources (with confirmation)
bash /home/ff/.openclaw/workspace/CDP_Merged/infra/scripts/shutdown-restart-test.sh stop

# Step 4: Manually verify stopped state, then restart
bash /home/ff/.openclaw/workspace/CDP_Merged/infra/scripts/shutdown-restart-test.sh restart

# Step 5: Full verification
bash /home/ff/.openclaw/workspace/CDP_Merged/infra/scripts/shutdown-restart-test.sh verify
```

---

## Quick Commands for Tonight

### Create VM Snapshot (CRITICAL)
```bash
az snapshot create \
  --resource-group rg-cdpmerged-fast \
  --source /subscriptions/ed9400bc-d5eb-4aa6-8b3f-2d4c11b17b9f/resourceGroups/RG-CDPMERGED-FAST/providers/Microsoft.Compute/disks/osdisk-tracardi-cdpmerged-prod \
  --name tracardi-snapshot-$(date +%Y%m%d) \
  --sku Standard_ZRS \
  --tags backup-type=pre-shutdown
```

### Verify Container App Scale-to-Zero
```bash
az containerapp show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --query "properties.template.scale.minReplicas"
# Should return: 0
```

### Emergency Rollback
```bash
# If Container App doesn't start
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --min-replicas 1

# If Tracardi VM is stopped
az vm start \
  --name vm-tracardi-cdpmerged-prod \
  --resource-group rg-cdpmerged-fast
```

---

## Estimated Savings

| Resource | Monthly Cost Before | Monthly Cost After | Savings |
|----------|--------------------|--------------------|---------|
| Container App (idle) | ~€30 | ~€5 | €25 |
| **Total** | **~€30** | **~€5** | **~€25/month** |

*Additional savings possible with Log Analytics consolidation and Search tier optimization.*

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Container App cold start issues | Low | Medium | HTTP scale rule configured, 3-5s delay acceptable |
| Tracardi VM data loss | Very Low | Critical | VM snapshot before shutdown |
| Secrets not restored | Low | High | All secrets documented with recreation steps |
| IaC drift | Medium | Medium | Full config exported before shutdown |

**Overall Risk Level:** LOW ✅

---

## Sign-off

| Check | Status |
|-------|--------|
| Cost optimizations implemented | ✅ PASS |
| Documentation complete | ✅ PASS |
| Secrets audit complete | ✅ PASS |
| Backup procedures ready | ✅ PASS |
| Reproducibility test script ready | ✅ PASS |
| Pre-flight checks passed | ✅ PASS |

**READY FOR SHUTDOWN/RESTART TEST:** ✅ YES

---

**Report Generated:** 2026-02-25 16:06 CET  
**Next Action:** Run shutdown-restart-test.sh when ready
