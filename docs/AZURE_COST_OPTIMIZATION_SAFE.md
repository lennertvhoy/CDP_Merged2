# Azure Cost Optimization - SAFE Options Only

**Date:** 2026-03-04  
**Status:** Analysis Complete - No Critical Resources Touched  
**CRITICAL NOTE:** PostgreSQL, Tracardi VMs, and enrichment processes are FULLY PROTECTED

---

## ⚠️ MAJOR COST DRIVERS FOUND

### 1. AVD Workshop VMs (HIGHEST PRIORITY)

| VM Name | Resource Group | Size | Status | Monthly Cost* |
|---------|----------------|------|--------|---------------|
| v-lennertvhoy01 | avd-azure-ai-one-day-workshop-lennertvhoy-20260303 | Standard_D2s_v3 | **RUNNING** | ~€75-95 |
| v-lennertvhoy01 | avd-azure-ai-one-day-workshop-lennertvhoy-20260303-24h2 | Standard_D2s_v3 | **RUNNING** | ~€75-95 |
| v-lennertdc8d01 | avd-azure-ai-one-day-workshop-lennertvhoy-20260303-24h2b | Standard_D2s_v3 | **RUNNING** | ~€75-95 |
| **TOTAL** | | | | **€225-285/month** |

*_Estimated based on 730 hours/month at pay-as-you-go rates_

**Analysis:**
- These are Azure Virtual Desktop workshop VMs from March 3, 2026 (yesterday)
- Workshop name suggests "one-day" event
- **ALL 3 ARE RUNNING 24/7** since yesterday
- **NOT RELATED TO CDP PRODUCTION** - Safe to stop

**Safe Action:** Deallocate (stop) these VMs immediately
- Monthly savings: **€225-285**
- Risk: **ZERO** - No connection to CDP/Tracardi/PostgreSQL
- VMs can be restarted if needed for future workshops

---

### 2. Empty Resource Groups (CLEANUP)

| Resource Group | Status | Monthly Cost |
|----------------|--------|--------------|
| avd--lennertvhoy-20260224 | Empty (0 resources) | €0 |
| avd--lennertvhoy-20260220 | Empty (0 resources) | €0 |

**Safe Action:** Delete these empty resource groups
- Savings: €0 (but cleaner subscription)
- Risk: **ZERO** - Confirmed empty

---

### 3. Log Analytics Workspaces

| Workspace | Resource Group | Retention | Status |
|-----------|----------------|-----------|--------|
| law-tracardi-cdpmerged-prod-nq6x | rg-cdpmerged-fast | 30 days | ✅ IN USE |
| DefaultWorkspace-ed9400bc-d5eb-4aa6-8b3f-2d4c11b17b9f-WEU | DefaultResourceGroup-WEU | 30 days | ⚠️ Check usage |

**Analysis:**
- Default workspace may be auto-created but unused
- **DO NOT TOUCH** law-tracardi-cdpmerged-prod-nq6x (CDP production)
- Can verify if default workspace has any data before action

**Safe Action:** Only after verification - delete if truly unused
- Potential savings: €20-40/month
- Risk: **LOW** - Only after confirming zero data/queries

---

## 🛡️ CRITICAL RESOURCES - FULLY PROTECTED

These resources are **NEVER TO BE TOUCHED** - actively running production workloads:

| Resource | Resource Group | Role | Status |
|----------|----------------|------|--------|
| cdp-postgres-661 | rg-cdpmerged-fast | PostgreSQL database | ✅ RUNNING - ENRICHMENT ACTIVE |
| vm-tracardi-cdpmerged-prod | rg-cdpmerged-fast | Tracardi application | ✅ RUNNING - CRITICAL |
| vm-data-cdpmerged-prod | rg-cdpmerged-fast | Elasticsearch | ✅ RUNNING - CRITICAL |
| ca-cdpmerged-fast | rg-cdpmerged-fast | Container App (chatbot) | ✅ RUNNING - CRITICAL |
| aoai-cdpmerged-fast | rg-cdpmerged-fast | Azure OpenAI | ✅ ACTIVE - CRITICAL |

---

## 📊 SUMMARY

| Category | Monthly Savings | Risk Level |
|----------|-----------------|------------|
| Stop AVD workshop VMs (3x) | **€225-285** | **ZERO** |
| Delete empty resource groups | €0 | ZERO |
| Optimize Log Analytics (verify first) | €20-40 | LOW |
| **TOTAL POTENTIAL** | **€245-325/month** | **MINIMAL** |

---

## RECOMMENDED ACTIONS (ORDERED BY SAFETY)

### Immediate (ZERO Risk)
```bash
# 1. Deallocate AVD workshop VMs (saves €225-285/month)
az vm deallocate \
  --name v-lennertvhoy01 \
  --resource-group avd-azure-ai-one-day-workshop-lennertvhoy-20260303

az vm deallocate \
  --name v-lennertvhoy01 \
  --resource-group avd-azure-ai-one-day-workshop-lennertvhoy-20260303-24h2

az vm deallocate \
  --name v-lennertdc8d01 \
  --resource-group avd-azure-ai-one-day-workshop-lennertvhoy-20260303-24h2b

# 2. Delete empty resource groups
az group delete --name avd--lennertvhoy-20260224 --yes
az group delete --name avd--lennertvhoy-20260220 --yes
```

### After Verification (LOW Risk)
```bash
# Check if default Log Analytics workspace has any data
az monitor log-analytics workspace show \
  --workspace-name DefaultWorkspace-ed9400bc-d5eb-4aa6-8b3f-2d4c11b17b9f-WEU \
  --resource-group DefaultResourceGroup-WEU

# If confirmed unused, delete it
az monitor log-analytics workspace delete \
  --workspace-name DefaultWorkspace-ed9400bc-d5eb-4aa6-8b3f-2d4c11b17b9f-WEU \
  --resource-group DefaultResourceGroup-WEU --yes
```

---

## CURRENT MONTH ESTIMATE

| Resource Type | Estimated Monthly Cost |
|---------------|----------------------|
| CDP Production (VMs, PostgreSQL, Container App, etc.) | €205-370 |
| AVD Workshop VMs (3x running) | €225-285 |
| **TOTAL CURRENT** | **€430-655/month** |

### After Safe Optimizations
| Resource Type | Estimated Monthly Cost |
|---------------|----------------------|
| CDP Production only | €205-370 |
| **TOTAL AFTER** | **€205-370/month** |

**Savings: €225-285/month (35-45% reduction)**

---

## SAFEGUARDS APPLIED

✅ Verified NO impact on running enrichment processes  
✅ Verified NO impact on Tracardi VMs or PostgreSQL  
✅ Identified workshop VMs as completely separate from CDP  
✅ Only targeting empty or clearly unused resources  
✅ All production-critical resources explicitly protected  

---

*Document generated: 2026-03-04*
*Analysis tool: Azure CLI via terraform environment*

---

## Log Analytics Investigation - 2026-03-04

### Findings

**CRITICAL DISCOVERY:** Container App Environment logging is MISCONFIGURED

| Component | Configuration | Status |
|-----------|--------------|--------|
| Container App Environment (ca-cdpmerged-fast-env) | customerId: 156d285c-... | ❌ **NON-EXISTENT WORKSPACE** |
| law-tracardi-cdpmerged-prod-nq6x | customerId: d128bbb1-... | ✅ Exists but NOT LINKED |
| DefaultWorkspace-... | customerId: 26b591fc-... | ✅ Linked to App Insights |

### Impact

**Container App logs are being sent to a non-existent workspace** - effectively being lost/dropped.

### Attempted Optimizations

| Action | Status | Result |
|--------|--------|--------|
| Reduce DefaultWorkspace retention to 7 days | ❌ BLOCKED | PerGB2018 SKU requires min 30 days |
| Set daily cap | ⚠️ RISKY | Could lose critical production logs |
| Delete unused workspace | ❌ UNSAFE | DefaultWorkspace is used by Application Insights |

### Safe Conclusion

**NO CHANGES MADE TO LOG ANALYTICS** - Risk exceeds savings potential

Current Log Analytics cost: ~€20-40/month
Potential savings: €10-20/month (after retention/cap changes)
Risk: Breaking production monitoring or losing logs

### Recommendation

**ACCEPT CURRENT COST** - Log Analytics optimization is NOT worth the risk for €10-20/month savings.

Container App logging should be fixed separately by:
1. Recreating Container App Environment with correct workspace
2. OR accepting that Container App logs are not being collected

This is a known configuration drift issue that should be addressed during a planned maintenance window, not during active enrichment.

---

## Final Cost Summary - After All Safe Optimizations

| Resource Category | Monthly Cost | Notes |
|-------------------|--------------|-------|
| **CDP Production (VMs, PostgreSQL, Container App, etc.)** | €205-370 | Protected |
| **Log Analytics (both workspaces)** | €20-40 | Left unchanged - too risky |
| **TOTAL AFTER OPTIMIZATIONS** | **€225-410/month** | |

### Savings Achieved

| Optimization | Monthly Savings | Status |
|--------------|-----------------|--------|
| Stopped 3 AVD workshop VMs | €225-285 | ✅ COMPLETE |
| Deleted empty resource groups | €0 | ✅ COMPLETE |
| Log Analytics changes | €0 | ❌ BLOCKED/TOO RISKY |
| **TOTAL SAVINGS** | **€225-285/month** | |

### Gap to €150 Target

Current: €225-410/month  
Target: €150/month  
Gap: €75-260/month

**Remaining safe options to reach €150:**
1. Downsize data VM (vm-data-cdpmerged-prod) from B2s to B1ms during low activity - save €15-20
2. Optimize PostgreSQL storage (if over-provisioned) - minimal savings
3. Reduce Azure OpenAI usage - already optimized

**Note:** The enrichment process must complete before considering VM downsizing.

