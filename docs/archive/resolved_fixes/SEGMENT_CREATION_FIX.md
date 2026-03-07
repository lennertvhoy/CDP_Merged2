# Segment Creation Bug Fix

## Problem

When users searched for companies and then created a segment from those results, the segment would contain 0 profiles instead of the expected count.

**Example:**
- User: "How many IT companies in Antwerpen?"
- Bot: "I found 2799 active IT companies in Antwerpen."
- User: "Create a segment for these results"
- Bot: "Segment created but contains 0 profiles"

## Root Cause

The `MemorySaver` checkpointer used by LangGraph does **NOT** persist state across separate graph invocations. Each user message triggers a new `workflow.astream_events()` call, which:

1. Starts with fresh/empty state
2. Cannot access `last_search_tql` from previous invocations
3. `create_segment` receives no TQL → creates empty segment

### Why Previous Fixes Failed

1. **AgentState approach**: State doesn't persist across separate invocations with MemorySaver
2. **Global variable approach**: Tools run in isolated contexts; globals don't persist
3. **ContextVar approach**: Same issue - context doesn't persist across invocations

## Solution

Replace `MemorySaver` with `AsyncSqliteSaver` - a **persistent** checkpointer that saves state to SQLite.

### Changes Made

#### 1. `src/app.py`

```python
# BEFORE (not persistent):
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
workflow = compile_workflow(checkpointer=checkpointer)

# AFTER (persistent):
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import aiosqlite

checkpointer_path = Path("./data/checkpoints/checkpoints.db")
checkpointer_path.parent.mkdir(parents=True, exist_ok=True)

conn = await aiosqlite.connect(checkpointer_path)
checkpointer = AsyncSqliteSaver(conn)
workflow = compile_workflow(checkpointer=checkpointer)
```

**Key points:**
- Uses SQLite database for persistence
- State survives across separate `astream_events()` calls
- Creates checkpoint directory if needed

#### 2. `src/graph/nodes.py`

Enhanced logging to trace TQL flow:

```python
# Added debug logging for stored TQL
if stored_tql:
    logger.debug("tools_node_has_stored_tql", tql_preview=stored_tql[:50])
else:
    logger.debug("tools_node_no_stored_tql")

# Added warning when create_segment has no TQL
if use_last_search and not stored_tql:
    logger.warning(
        "create_segment_no_stored_tql",
        name=tool_args.get("name"),
        message="Segment may have 0 profiles - no previous search found",
    )
```

#### 3. `src/ai_interface/tools/search.py`

Added documentation explaining the persistence mechanism:

```python
"""
SEGMENT CREATION NOTE:
The segment creation flow relies on a persistent checkpointer (SQLite/Postgres)
to maintain last_search_tql across separate graph invocations. The default
MemorySaver does NOT persist state across separate astream_events calls.
"""
```

#### 4. `pyproject.toml`

Added dependency:
```toml
langgraph-checkpoint-sqlite = "^2.0.11"
```

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER SEARCH FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. User: "How many IT companies in Antwerpen?"                │
│     │                                                           │
│     ▼                                                           │
│  2. workflow.astream_events() - NEW INVOCATION                  │
│     │                                                           │
│     ▼                                                           │
│  3. search_profiles executes                                    │
│     │  Returns: {                                              │
│     │    counts: {authoritative_total: 2799},                  │
│     │    query: {tql: "traits.city=\"Antwerpen\"..."}           │
│     │  }                                                        │
│     │                                                           │
│     ▼                                                           │
│  4. tools_node extracts TQL                                     │
│     │  state.last_search_tql = "traits.city=\"Antwerpen\"..."   │
│     │                                                           │
│     ▼                                                           │
│  5. AsyncSqliteSaver SAVES to SQLite                            │
│     │  INSERT INTO checkpoints (thread_id, state, ...)          │
│     │                                                           │
│     ▼                                                           │
│  6. Response sent to user: "Found 2799 companies"               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ User sends next message
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SEGMENT CREATION FLOW                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  7. User: "Create a segment"                                    │
│     │                                                           │
│     ▼                                                           │
│  8. workflow.astream_events() - NEW INVOCATION                  │
│     │  But now: AsyncSqliteSaver RESTORES state                 │
│     │  SELECT state FROM checkpoints WHERE thread_id = ?        │
│     │                                                           │
│     ▼                                                           │
│  9. State restored with last_search_tql                         │
│     │  state.last_search_tql = "traits.city=\"Antwerpen\"..."   │
│     │                                                           │
│     ▼                                                           │
│  10. tools_node injects TQL into create_segment                 │
│     │  tool_args.condition = stored_tql                         │
│     │                                                           │
│     ▼                                                           │
│  11. create_segment executes with correct TQL                   │
│     │  Creates segment with 2799 profiles!                      │
│     │                                                           │
│     ▼                                                           │
│  12. Response: "Segment created with 2799 profiles"             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Testing

Run the test suite:

```bash
poetry run python test_segment_fix.py
```

Expected output:
```
============================================================
SEGMENT CREATION TQL PERSISTENCE FIX - TEST SUITE
============================================================

=== Testing search_profiles Returns TQL ===
✓ Search returned 1109 results
✓ Search returned TQL: (traits.city="Gent" OR ...

=== Testing AsyncSqliteSaver Import ===
✓ AsyncSqliteSaver imported successfully

=== Testing Full Flow Simulation ===
✓ Step 1: Search returned TQL
✓ Step 2: tools_node stored TQL in state
✓ Step 3: Checkpointer persists state (SQLite)
✓ Step 4: State restored with TQL
✓ Step 5: tools_node injected TQL into create_segment args
✓ Step 6: ✓✓✓ SEARCH TQL MATCHES SEGMENT TQL ✓✓✓

ALL TESTS PASSED ✓
```

## Verification in Production

After deploying, verify the fix works:

1. **Search test:**
   - "How many IT companies in Antwerpen?"
   - Note the count (e.g., 2799)

2. **Segment creation test:**
   - "Create a segment for these results"
   - Verify segment has same count (2799)

3. **Edge cases:**
   - Search with no results → Create segment (should be empty)
   - Multiple searches → Create segment (should use LAST search)
   - Wait 10+ minutes → Create segment (should still work)

## Files Changed

| File | Change |
|------|--------|
| `src/app.py` | Use AsyncSqliteSaver instead of MemorySaver |
| `src/graph/nodes.py` | Enhanced logging for TQL flow |
| `src/ai_interface/tools/search.py` | Added documentation |
| `pyproject.toml` | Added langgraph-checkpoint-sqlite dependency |
| `test_segment_fix.py` | New test file |

## Rollback Plan

If issues occur, revert to MemorySaver:

```python
# In src/app.py, replace:
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()
```

Note: This will re-introduce the segment creation bug.

## Success Criteria

- [x] Search returns N profiles
- [x] Create segment returns segment with N profiles (not 0)
- [x] Multiple test scenarios pass
- [x] Browser automation verification passes
- [x] Code committed and deployed
- [x] Production verification complete
