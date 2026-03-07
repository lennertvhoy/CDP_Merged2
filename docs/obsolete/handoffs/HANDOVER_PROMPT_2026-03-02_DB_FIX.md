# Handover Prompt: Database Connection Fix Required

**Date**: 2026-03-02  
**Status**: Tracardi connection fixed, database issue still blocking query execution  
**Source**: Migrated from the stale duplicate working tree on 2026-03-02

---

## Completed in That Session

### 1. Tracardi connection error fixed

**Problem**: Chatbot showed a connection error during auth.

**Root Cause**: NSG rules blocked the Container App from reaching the Tracardi VM.

**Result**:
- Tracardi auth started succeeding
- Sessions were created successfully
- Remaining blocker moved to the workflow checkpoint/database layer

---

## New Issue Discovered: Database Connection Error

**Problem**: Query execution failed with:

```text
'Connection' object has no attribute 'is_alive'
```

**Likely Cause**: SQLite/LangGraph checkpoint dependency mismatch.

**Relevant Files**:
- `pyproject.toml`
- `poetry.lock`
- `src/app.py`
- `src/graph/workflow.py`

---

## Next Session Priorities

### Priority 1: Validate the dependency pin locally

1. Install dependencies in the canonical repo:
   ```bash
   cd /home/ff/.openclaw/workspace/repos/CDP_Merged
   poetry install
   ```
2. Run the app locally:
   ```bash
   chainlit run src/app.py
   ```
3. Confirm the `is_alive` error is gone.

### Priority 2: Verify chatbot behavior end to end

1. Test a simple search query
2. Test a filtered query with employee constraints
3. Test segment creation
4. Re-check deployment logs if the issue persists

---

## Notes

- This migrated copy is sanitized. Sensitive credentials from the original scratch note were intentionally removed.
- The canonical repo path is `/home/ff/.openclaw/workspace/repos/CDP_Merged`.
