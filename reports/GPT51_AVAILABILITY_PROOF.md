# GPT-5.1 Availability Proof for CDP_Merged Azure Environment

**Date**: 2026-03-15  
**Status**: PROVEN - Cannot use GPT-5.1 on this subscription due to quota restrictions

---

## Executive Summary

**Conclusion**: We CANNOT use GPT-5.1 or GPT-5.1-codex on this subscription/resource/region right now because:
1. Subscription has **0 quota** for "Global Provisioned Managed Throughput Unit"
2. GPT-5.1 requires **ProvisionedManaged** SKU (not Standard)
3. ProvisionedManaged requires **minimum 15 capacity**
4. All existing deployments use **GlobalStandard** SKU (pay-as-you-go)

---

## Azure Identity Evidence

### Subscription Details
```json
{
  "subscriptionId": "ed9400bc-d5eb-4aa6-8b3f-2d4c11b17b9f",
  "name": "Visual Studio Enterprise-abonnement – MPN",
  "state": "Enabled",
  "tenantId": "ce408fd5-2526-4cbb-bbe6-f0c2e188b89d",
  "user": "l.vanhoyweghen@it1.be"
}
```

### Azure OpenAI Resource
```json
{
  "name": "aoai-cdpmerged-fast",
  "resourceGroup": "rg-cdpmerged-fast",
  "location": "westeurope",
  "endpoint": "https://aoai-cdpmerged-fast.openai.azure.com/",
  "sku": "S0",
  "provisioningState": "Succeeded"
}
```

---

## Models Available in This Region

### GPT-5.1 Family Models Listed
| Model | Version | Available SKUs |
|-------|---------|----------------|
| gpt-5.1 | 2025-11-13 | DataZoneProvisionedManaged, GlobalProvisionedManaged, GlobalBatch |
| gpt-5.1-codex | 2025-11-13 | DataZoneProvisionedManaged, GlobalProvisionedManaged |

**Source**: `az cognitiveservices account list-models` output

### Existing Deployments (All GlobalStandard)
| Deployment | Model | Version | SKU | Capacity |
|------------|-------|---------|-----|----------|
| gpt-5 | gpt-5 | 2025-08-07 | GlobalStandard | 10 |
| gpt-4o | gpt-4o | 2024-11-20 | GlobalStandard | 10 |
| gpt-5-mini | gpt-5-mini | 2025-08-07 | GlobalStandard | 10 |
| gpt-4-1 | gpt-4.1 | 2025-04-14 | GlobalStandard | 10 |
| gpt-5-nano | gpt-5-nano | 2025-08-07 | GlobalStandard | 10 |
| gpt-4-1-mini | gpt-4.1-mini | 2025-04-14 | GlobalStandard | 10 |

---

## Deployment Attempt Evidence

### Attempt 1: GlobalStandard SKU (Same as existing deployments)
**Command**:
```bash
az cognitiveservices account deployment create \
  --name aoai-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --deployment-name gpt-5-1 \
  --model-name gpt-5.1 \
  --model-version "2025-11-13" \
  --model-format OpenAI \
  --sku-name GlobalStandard \
  --sku-capacity 10
```

**Result**:
```
ERROR: (InvalidResourceProperties) The specified SKU 'GlobalStandard' for model 'gpt-5.1 2025-11-13' is not supported in this region 'westeurope'.
Code: InvalidResourceProperties
```

**Interpretation**: GPT-5.1 does NOT support pay-as-you-go GlobalStandard SKU.

---

### Attempt 2: GlobalProvisionedManaged SKU (Capacity 10)
**Command**:
```bash
az cognitiveservices account deployment create \
  --name aoai-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --deployment-name gpt-5-1 \
  --model-name gpt-5.1 \
  --model-version "2025-11-13" \
  --model-format OpenAI \
  --sku-name GlobalProvisionedManaged \
  --sku-capacity 10
```

**Result**:
```
ERROR: (InvalidCapacity) The specified capacity '10' of account deployment should be at least 15 and no more than 30000.
Code: InvalidCapacity
```

**Interpretation**: ProvisionedManaged SKU requires minimum 15 capacity (not 10).

---

### Attempt 3: GlobalProvisionedManaged SKU (Capacity 15)
**Command**:
```bash
az cognitiveservices account deployment create \
  --name aoai-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --deployment-name gpt-5-1 \
  --model-name gpt-5.1 \
  --model-version "2025-11-13" \
  --model-format OpenAI \
  --sku-name GlobalProvisionedManaged \
  --sku-capacity 15
```

**Result**:
```
ERROR: (InsufficientQuota) This operation require 15 new capacity in quota Global Provisioned Managed Throughput Unit, 
which is bigger than the current available capacity 0. 
The current quota usage is 0 and the quota limit is 0 for quota Global Provisioned Managed Throughput Unit.
Code: InsufficientQuota
```

**Interpretation**: Subscription has ZERO quota for Global Provisioned Managed Throughput Unit.

---

### Attempt 4: GPT-5.1-codex (Capacity 15)
**Command**:
```bash
az cognitiveservices account deployment create \
  --name aoai-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --deployment-name gpt-5-1-codex \
  --model-name gpt-5.1-codex \
  --model-version "2025-11-13" \
  --model-format OpenAI \
  --sku-name GlobalProvisionedManaged \
  --sku-capacity 15
```

**Result**:
```
ERROR: (InsufficientQuota) This operation require 15 new capacity in quota Global Provisioned Managed Throughput Unit, 
which is bigger than the current available capacity 0. 
The current quota usage is 0 and the quota limit is 0 for quota Global Provisioned Managed Throughput Unit.
Code: InsufficientQuota
```

**Interpretation**: Same quota issue for GPT-5.1-codex.

---

## Why This Subscription Cannot Use GPT-5.1

### The SKU Hierarchy

| SKU Type | Models Supported | Billing Model | GPT-5.1 Support |
|----------|-----------------|---------------|-----------------|
| GlobalStandard | GPT-4, GPT-4o, GPT-5 (base) | Pay-as-you-go | ❌ NO |
| GlobalProvisionedManaged | GPT-5.1, GPT-5.1-codex | Provisioned (hourly) | ✅ YES |

### Quota Status
- **GlobalStandard**: Has quota (all existing deployments use this)
- **GlobalProvisionedManaged**: **Quota = 0** (confirmed by Azure error)

### What This Means
1. GPT-5.1 exists in Azure OpenAI westeurope
2. This subscription type (Visual Studio Enterprise MPN) does NOT include ProvisionedManaged quota
3. To use GPT-5.1, would need to:
   - Request quota increase for "Global Provisioned Managed Throughput Unit"
   - OR switch to a different subscription type that includes this quota
   - OR use a different Azure region (if quota differs by region)

---

## Verified Facts vs Claims

### ✅ VERIFIED FACTS (with Azure CLI evidence)
1. Subscription ID: `ed9400bc-d5eb-4aa6-8b3f-2d4c11b17b9f`
2. Resource: `aoai-cdpmerged-fast` in `westeurope`
3. GPT-5.1 model version `2025-11-13` exists in this region
4. GPT-5.1-codex model version `2025-11-13` exists in this region
5. Existing deployments use GlobalStandard SKU
6. GPT-5.1 does NOT support GlobalStandard SKU
7. Subscription has 0 quota for GlobalProvisionedManaged
8. Cannot create GPT-5.1 deployment due to InsufficientQuota

### ❌ NOT CLAIMED (because unverified)
1. Whether other subscriptions/regions can use GPT-5.1
2. Whether quota can be requested/increased for this subscription
3. Cost implications of ProvisionedManaged SKU
4. Performance characteristics of GPT-5.1 vs GPT-4o

---

## Honest Conclusion

**We CANNOT use GPT-5.1 or GPT-5.1-codex on this subscription/resource/region right now because:**

The Visual Studio Enterprise MPN subscription (`ed9400bc-d5eb-4aa6-8b3f-2d4c11b17b9f`) has **zero quota** for "Global Provisioned Managed Throughput Unit", which is required to deploy GPT-5.1 or GPT-5.1-codex in the westeurope region.

**Azure Evidence**:
- Error Code: `InsufficientQuota`
- Error Message: `"The current quota usage is 0 and the quota limit is 0 for quota Global Provisioned Managed Throughput Unit"`
- Failed Command: `az cognitiveservices account deployment create` with SKU `GlobalProvisionedManaged` and capacity `15`

---

## Methodology Note

This proof follows the required methodology:
1. ✅ Used real Azure CLI commands
2. ✅ Showed actual subscription/resource details
3. ✅ Captured exact Azure error messages
4. ✅ Did not infer from public docs alone
5. ✅ Distinguished between "model exists" and "we can use it"
6. ✅ Documented the specific blocker (quota)
