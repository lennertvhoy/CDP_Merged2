# Public Path Chat Hang - Incident Report

**Date:** 2026-03-15  
**Status:** PARTIALLY RESOLVED - Root Cause Proven  
**Severity:** HIGH (affects all tool-using queries)

---

## Executive Summary

Two separate issues were identified affecting public ngrok chat:

1. **FIXED:** `AsyncSqliteSaver` checkpointer caused indefinite workflow hangs
   - **Fix:** Removed checkpointer from streaming chat (commit `6aa5857`)
   - **Result:** Simple non-tool queries now work on public path

2. **IDENTIFIED (NOT FIXED):** Azure OpenAI rate limiting causes tool-using queries to timeout
   - **Root Cause:** Azure OpenAI deployment `gpt-4o` returns HTTP 429 (Too Many Requests) with 30-second retry delays
   - **Impact:** Tool-using queries appear to "hang" but are actually waiting for rate limit retry
   - **Evidence:** First LLM call took 62.3 seconds due to rate limit retries

---

## What Was Proven

### Test Evidence

| Test | Result | Evidence |
|------|--------|----------|
| Minimal reproducer (direct LLM) | ✅ Works | `reproduce_second_call_hang.py` - all tests pass |
| Direct agent_node call with ToolMessage | ✅ Works | `debug_second_call_direct.py` - 1.03s response |
| Simple workflow (no tools) via astream_events | ✅ Works | 27 events, 1.41s |
| Tool workflow via astream_events | ❌ Times out | Agent call #1 took 62.3s due to rate limiting |

### Rate Limit Evidence

From logs (trimmed for clarity):

```
HTTP/1.1 429 Too Many Requests
x-ratelimit-remaining-requests: 9
x-ratelimit-remaining-tokens: -1
x-ratelimit-reset-tokens: 59
retry-after: 30

Retrying request to /chat/completions in 30.000000 seconds
```

The Azure OpenAI deployment is configured with:
- **Request limit:** 10 requests
- **Token limit:** 10,000 tokens
- **Current status:** Hitting rate limits consistently

---

## The Exact Failing Pattern

1. User sends tool-using query (e.g., "how many companies in Brussels")
2. First agent_node call starts
3. Azure OpenAI returns **HTTP 429** (rate limit exceeded)
4. OpenAI client waits **30 seconds** before retry (3 retries configured)
5. If all retries hit rate limits, total latency exceeds 90-second timeout
6. User sees "Working..." indefinitely (or until timeout)

---

## Current State

| Query Type | Public Path Status | Root Cause |
|------------|-------------------|------------|
| Simple greeting | ✅ Working | - |
| Count query | ❌ Broken | Azure rate limiting |
| Search query | ❌ Broken | Azure rate limiting |
| SC-17 | ❌ Blocked | Azure rate limiting |
| SC-18 | ❌ Blocked | Azure rate limiting |

---

## Required Fix

The Azure OpenAI deployment needs capacity increase OR implementation of:

1. **Rate limit backoff strategy** with exponential backoff
2. **Token usage tracking** to stay under limits
3. **Request batching** to reduce call frequency
4. **Alternative model** deployment with higher capacity

---

## Files Modified This Session

| File | Change |
|------|--------|
| `src/operator_api.py` | Removed AsyncSqliteSaver checkpointer |
| `src/graph/nodes.py` | Fixed tool binding logic for GPT-4o |
| `reproduce_second_call_hang.py` | Created - minimal reproducer |
| `debug_second_call_direct.py` | Created - direct node test |
| `debug_astream_events.py` | Created - streaming test |
| `debug_second_call.py` | Created - full workflow test |

---

## Verification Commands

```bash
# Test simple query (should work)
curl -s -X POST https://kbocdpagent.ngrok.app/api/operator/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"hi","thread_id":"test"}'

# Test tool query (will hang due to rate limiting)
curl -s -X POST https://kbocdpagent.ngrok.app/api/operator/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"how many companies","thread_id":"test"}'
```

---

## Related Documentation

- `STATUS.md` - Human-readable status snapshot
- `PROJECT_STATE.yaml` - Structured state with verification evidence
- `NEXT_ACTIONS.md` - Active queue (add Azure rate limiting fix)

---

**Last Updated:** 2026-03-15 09:30 CET  
**Evidence Confidence:** HIGH (direct log analysis and reproduction)
