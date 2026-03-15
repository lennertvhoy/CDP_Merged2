# Azure OpenAI Rate Limit Fix - Comprehensive Report

**Date:** 2026-03-15  
**Status:** IMPLEMENTED - Pending public path verification  
**Azure Resource:** aoai-cdpmerged-fast (West Europe, S0 Standard)  
**Primary Deployment:** gpt-5 (GlobalStandard)

---

## Executive Summary

The root cause was **TPM (Tokens Per Minute) throttling**, not RPM. Azure OpenAI throttles based on:
- `prompt_tokens + max_completion_tokens` estimate
- Not actual output tokens
- 10K TPM limit at capacity 10 = ~3-4 requests/minute with 800 max_completion_tokens

**Solution implemented:**
1. Reduced `max_completion_tokens` from 800 → 400 (default), 100 (routing)
2. Increased deployment capacity from 10 → 20 (20K TPM, 200 RPM)
3. Stage-specific token limits (routing vs final answer)
4. Deterministic shortcuts bypass second LLM call for 4 tools

---

## Part 1: Hard Evidence Collection

### 1.1 Azure Deployment Configuration

```bash
$ az cognitiveservices account deployment list -g rg-cdpmerged-fast -n aoai-cdpmerged-fast
```

| Deployment | Model | SKU | Capacity | RPM | TPM |
|------------|-------|-----|----------|-----|-----|
| **gpt-5** | gpt-5 | GlobalStandard | **20** (was 10) | **200** | **20K** |
| gpt-4o | gpt-4o | GlobalStandard | 10 | 60 | 10K |
| gpt-5-mini | gpt-5-mini | GlobalStandard | 10 | 10 | 10K |
| gpt-4.1 | gpt-4.1 | GlobalStandard | 10 | 10 | 10K |

**Dynamic Quota:** NOT AVAILABLE for GlobalStandard SKU  
**Account-level limits:** 30 req/s (not the bottleneck)

### 1.2 Token Estimation Math (Before Fix)

```
Azure throttling estimate = prompt_tokens + max_completion_tokens

System prompt ≈ 800 tokens
Tools definitions ≈ 500 tokens  
User message ≈ 50 tokens
max_completion_tokens = 800

Total estimate per request = 800 + 500 + 50 + 800 = 2150 tokens

With 10K TPM limit:
10,000 / 2150 = 4.6 requests per minute maximum

With 2 LLM calls per query (tool selection + answer):
4.6 / 2 = 2.3 user queries per minute maximum
```

**This explains the 429s on consecutive queries.**

### 1.3 Token Estimation Math (After Fix)

```
Routing call (first LLM):
- System prompt + tools + message = 1350 tokens
- max_completion_tokens = 100 (reduced from 800)
- Total estimate = 1450 tokens

Final answer call (second LLM):
- System prompt + tools + message + tool result = 1500 tokens
- max_completion_tokens = 400 (reduced from 800)
- Total estimate = 1900 tokens

With 20K TPM limit:
20,000 / ((1450 + 1900) / 2) = 11.9 request pairs per minute

With deterministic shortcuts (skip second LLM):
20,000 / 1450 = 13.8 routing calls per minute
```

---

## Part 2: Demand-Side Fixes Implemented

### 2.1 Configuration Changes (`src/config.py`)

```python
# BEFORE
AZURE_OPENAI_MAX_TOKENS: int = Field(default=800, ...)

# AFTER
AZURE_OPENAI_MAX_TOKENS: int = Field(default=400, ...)  # Reduced from 800

# Stage-specific limits
AZURE_OPENAI_MAX_TOKENS_ROUTING: int = Field(default=100, ...)   # Tool selection
AZURE_OPENAI_MAX_TOKENS_MEDIUM: int = Field(default=400, ...)    # Final answer
```

### 2.2 Stage-Aware Token Selection (`src/graph/nodes.py`)

Added `_determine_token_limit_for_stage()` function:

```python
def _determine_token_limit_for_stage(messages: list) -> int:
    has_tool_message = any(isinstance(m, ToolMessage) for m in messages)
    
    if not has_tool_message:
        # First call: Tool selection/routing
        return settings.AZURE_OPENAI_MAX_TOKENS_ROUTING  # 100 tokens
    else:
        # Second call: Final answer generation
        return settings.AZURE_OPENAI_MAX_TOKENS_MEDIUM    # 400 tokens
```

### 2.3 Deterministic Shortcuts (Already Implemented)

4 tools bypass second LLM call:
- `get_identity_link_quality`
- `get_geographic_revenue_distribution`
- `get_industry_summary`
- `get_data_coverage_stats`

**Impact:** ~50% reduction in LLM calls for analytical queries.

---

## Part 3: Supply-Side Fixes Implemented

### 3.1 Deployment Capacity Increase

```bash
# Azure CLI command executed:
az rest --method PUT \
  --uri "https://management.azure.com/subscriptions/.../deployments/gpt-5?api-version=2023-05-01" \
  --body '{"sku":{"name":"GlobalStandard","capacity":20},...}'
```

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Capacity | 10 | 20 | 2x |
| TPM | 10,000 | 20,000 | 2x |
| RPM | 100 | 200 | 2x |

### 3.2 Dynamic Quota

**Status:** NOT AVAILABLE for GlobalStandard SKU  
**Evidence:** API returns `null` for dynamicQuota property  
**Alternative:** Manual capacity scaling (implemented)

---

## Part 4: 429 UX Safety (Already Implemented)

### 4.1 Client-Side Rate Limiter

```python
# 1.1s spacing between Azure requests
_azure_min_interval: float = 1.1
```

### 4.2 Fail-Fast Retry Config

```python
AZURE_OPENAI_MAX_RETRIES: int = 1  # Reduced from default (2-3)
AZURE_OPENAI_TIMEOUT: float = 25.0  # Fail fast instead of hanging
```

### 4.3 Streaming Timeout

```python
MAX_TOTAL_TIME_SECONDS = 60.0  # Absolute maximum in stream generator
```

### 4.4 User-Friendly Error Messages

Rate limit errors return:
```
⚠️ **Rate Limit Reached**

The AI service is currently experiencing high demand. Please wait a moment and try again.

**What you can do:**
- Wait 10-20 seconds and retry your query
- Try a simpler query (e.g., just "hello" to test)
- If this persists, the service may need capacity adjustment
```

---

## Part 5: Public Path Validation

### 5.1 Architecture Verification

| Check | Status | Evidence |
|-------|--------|----------|
| ngrok → port 3000 | ✅ | `curl https://kbocdpagent.ngrok.app/` returns HTML |
| Shell proxies to API | ✅ | `/operator-api/bootstrap` works |
| Auth enabled | ✅ | Returns `access_gate` phase |
| Port 8170 (API) | ✅ | `ss -tlnp` shows uvicorn on 8170 |

### 5.2 Files Modified

| File | Changes |
|------|---------|
| `src/config.py` | +16 lines: Stage-specific token limits |
| `src/graph/nodes.py` | +45 lines: `_determine_token_limit_for_stage()`, logging |

### 5.3 Azure Resources Modified

| Resource | Change |
|----------|--------|
| `aoai-cdpmerged-fast/deployments/gpt-5` | Capacity: 10 → 20 |

---

## Part 6: Remaining Work

To fully complete SC-17/SC-18 acceptance testing:

1. **Login to public URL:** https://kbocdpagent.ngrok.app/
2. **Test simple greeting** (no tools)
3. **Test count query** (one tool, deterministic shortcut)
4. **Test search query** (one tool + LLM)
5. **Test SC-17** (multi-step)
6. **Test SC-18** (multi-step)

---

## Part 7: Key Insights

### Why "100 RPM" Was Misleading

Azure OpenAI has **two** rate limits:
1. **RPM** - Requests per minute (100 for gpt-5)
2. **TPM** - Tokens per minute (10K at capacity 10)

**The bottleneck was TPM**, not RPM. With large `max_completion_tokens`, the token estimate per request was so high that TPM limits kicked in before RPM limits.

### Why Dynamic Quota Wasn't Available

Dynamic Quota is a preview feature for **Standard** SKU, not **GlobalStandard**. Our deployment uses GlobalStandard which has different scaling characteristics.

### Proper Fix Pattern

1. **Measure actual token estimates** (prompt + max_completion_tokens)
2. **Reduce max_completion_tokens** to minimum viable for each use case
3. **Increase capacity** to scale TPM proportionally
4. **Skip unnecessary LLM calls** with deterministic shortcuts

---

## Appendix: Commands Used

```bash
# Check deployment rate limits
az rest --method GET \
  --uri "https://management.azure.com/subscriptions/$SUB/resourceGroups/rg-cdpmerged-fast/providers/Microsoft.CognitiveServices/accounts/aoai-cdpmerged-fast/deployments?api-version=2023-05-01"

# Increase deployment capacity
az rest --method PUT \
  --uri "https://management.azure.com/subscriptions/$SUB/resourceGroups/rg-cdpmerged-fast/providers/Microsoft.CognitiveServices/accounts/aoai-cdpmerged-fast/deployments/gpt-5?api-version=2023-05-01" \
  --body '{"sku":{"name":"GlobalStandard","capacity":20},"properties":{"model":{"name":"gpt-5","version":"2025-08-07","format":"OpenAI"},"raiPolicyName":"Microsoft.DefaultV2"}}'

# Verify public path
curl https://kbocdpagent.ngrok.app/operator-api/bootstrap
```

---

*Report generated: 2026-03-15*  
*Next step: Browser-based acceptance testing on public URL*
