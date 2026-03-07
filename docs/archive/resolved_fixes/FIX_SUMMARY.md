# Segment Creation Bug Fix - Complete Solution

## Problem
Search returned N profiles (e.g., 2799 IT companies in Antwerpen), but creating a segment from those results returned 0 profiles.

## Root Cause
The TQL query from `search_profiles` was not being reliably passed to `create_segment`. The previous attempts using:
1. Global variables - Failed due to process isolation in serverless environments
2. AgentState with checkpointer - Sometimes unreliable depending on checkpointer configuration

## Solution
Implemented a **dual-layer persistence strategy** using both:
1. **AgentState** (fast, same-turn access via checkpointer)
2. **SearchCache** (reliable SQLite-backed cache with conversation_id as key)

### Files Changed

#### 1. `src/core/search_cache.py` (NEW)
New SQLite-backed cache for persisting search TQL:
- `SearchCache` class with TTL support (default 1 hour)
- Uses conversation_id (thread_id) as the key
- Async operations with proper WAL mode for SQLite
- Cleanup of expired entries on read

#### 2. `src/graph/nodes.py`
Updated `tools_node` to:
- Accept `config` parameter to extract `conversation_id` (thread_id)
- Store TQL in SearchCache after successful search
- Fall back to SearchCache when state doesn't have TQL
- Log which source was used (state vs cache)

#### 3. `src/ai_interface/tools/search.py`
Added backward compatibility wrappers:
- `get_last_search_tql()` - Returns None in async context (tools_node handles it)
- `_store_search_tql()` - No-op in async context (tools_node handles it)

#### 4. `tests/unit/ai_interface/tools/test_search.py`
Updated tests to use the new SearchCache architecture:
- Tests now use `SearchCache` directly instead of global/contextvar storage
- Verified conversation isolation works correctly

#### 5. `tests/test_segment_creation_fix.py` (NEW)
Integration test that verifies:
- Search returns TQL in results
- TQL is stored in cache
- Cache retrieval works
- Segment creation uses the stored TQL

## How It Works

### Search Flow
1. User: "How many IT companies in Antwerpen?"
2. `search_profiles` executes and returns results with TQL in `result.query.tql`
3. `tools_node` extracts TQL and:
   - Stores in `state.last_search_tql` (via checkpointer)
   - Stores in `SearchCache` with `conversation_id` as key

### Segment Creation Flow
1. User: "Create a segment for these results"
2. `tools_node` receives `create_segment` tool call
3. Tries to get TQL from:
   - First: `state.last_search_tql` (fast path)
   - Fallback: `SearchCache.get_last_search(conversation_id)`
4. Injects TQL into `create_segment` arguments as `condition`
5. Segment is created with the exact TQL from the search

## Verification

### Unit Tests
```bash
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
poetry run python -m pytest tests/unit/test_workflow.py tests/unit/ai_interface/tools/test_search.py -v
# 35 passed
```

### Integration Test
```bash
PYTHONPATH=/home/ff/.openclaw/workspace/repos/CDP_Merged/src poetry run python tests/test_segment_creation_fix.py
# ✅ All SearchCache tests passed!
# ✅ tools_node processed successfully with cache fallback
```

### Production Verification Steps
1. Deploy the updated code
2. Open the chatbot: https://ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io/
3. Test: "How many IT companies in Antwerpen?" → Should return ~2799
4. Test: "Create a segment for these results" → Should create segment with 2799 profiles
5. Test: "How many restaurants in Gent?" → Should return count
6. Test: "Create a segment" → Should create segment with matching count

## Key Design Decisions

1. **Dual-layer persistence**: State for speed, cache for reliability
2. **SQLite backend**: No external dependencies (Redis optional)
3. **TTL support**: Old searches expire after 1 hour (configurable)
4. **Conversation isolation**: Each thread_id has its own cache entry
5. **Backward compatibility**: Old function signatures still work (no-op in async context)

## Monitoring

The fix includes comprehensive logging:
- `search_cache_stored` - When TQL is stored
- `search_cache_retrieved` - When TQL is retrieved
- `tools_node_using_cached_tql` - When fallback to cache is used
- `create_segment_injecting_stored_tql` - When TQL is injected
- `create_segment_no_stored_tql` - Warning when no TQL found

## Rollback

If issues occur:
1. Revert `src/graph/nodes.py` to previous version
2. Remove `src/core/search_cache.py`
3. Revert changes to `src/ai_interface/tools/search.py`

The fix is additive - removing it will restore the previous behavior (which had the bug).
