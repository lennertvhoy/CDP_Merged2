# CDP Phase 2 Enrichment Investigation Report

**Investigation Date:** 2026-03-01  
**Verification Phrase:** okdennieh  
**Status:** Fixes Applied ✅

---

## Summary

The Phase 2 enrichment process (CBE Integration) was experiencing frequent exits/crashes every few minutes. Investigation revealed **multiple root causes**:

1. **Out of Memory (OOM) Kills** - Exit code 137
2. **SIGTERM/External Termination** - Exit code 143  
3. **Datetime Bug** - "can't subtract offset-naive and offset-aware datetimes"
4. **Aggressive Restart Loop** - Runner script had no memory protection

---

## Root Cause Analysis

### 1. Memory Exhaustion (Exit Code 137)

The Python process was being killed by the Linux OOM killer:
- Exit code 137 = 128 + 9 (SIGKILL from OOM killer)
- Memory was accumulating over time despite streaming processing
- Garbage collection was not frequent enough
- Batch size of 100 may have been too large for some profiles

### 2. Datetime Bug

Error message in logs:
```
"error": "invalid input for query argument $2: datetime.datetime(2026, 3, 1, 9, 35, 22,... (can't subtract offset-naive and offset-aware datetimes)"
```

**Cause:** In `postgresql_pipeline.py`, the `_extract_updates()` method was using `datetime.now(UTC)` which returns a timezone-aware datetime. PostgreSQL was trying to subtract this from another datetime, causing the error.

**Fix:** Changed to `datetime.now(UTC).replace(tzinfo=None)` to create naive datetimes compatible with PostgreSQL.

### 3. Runner Script Issues

The original `run_phase2.sh` had several problems:
- No handling for OOM kills (exit 137)
- Immediate restart after crash with only 5 second delay
- No timeout protection
- Could potentially spawn multiple processes if not careful

---

## Fixes Applied

### 1. Enhanced Runner Script (`run_phase2.sh`)

**Changes:**
- Added OOM kill detection and backoff strategy
- Implemented timeout protection (1 hour max runtime)
- Added consecutive OOM tracking with escalating delays (30s → 60s)
- Changed batch size from 100 to 50 for lower memory footprint
- Added separate error logging for better visibility

### 2. Fixed Datetime Bug (`src/enrichment/postgresql_pipeline.py`)

**Changes:**
```python
# Before:
updates["ai_description_generated_at"] = datetime.now(UTC)
updates["last_sync_at"] = datetime.now(UTC)

# After:
updates["ai_description_generated_at"] = datetime.now(UTC).replace(tzinfo=None)
updates["last_sync_at"] = datetime.now(UTC).replace(tzinfo=None)
```

### 3. Improved Memory Management

**Changes in `run_phase_streaming()`:**
- Added explicit `del` statements for `enriched_batch`, `profiles`, and `enrichable`
- Increased garbage collection frequency (every 5 batches instead of 10)
- Fixed offset calculation bug (was using `len(profiles)`, now uses `len(rows)`)

---

## Current Status

**Progress at time of investigation:**
- Total profiles: 1,813,016
- Processed: ~30,500 (1.7%)
- Checkpoint: offset 41,500

**Current State:**
- Phase1 contact validation is currently running (different process)
- Phase2 needs to be restarted with the fixed runner script

---

## Recommendations

1. **Monitor memory usage** during the first few runs:
   ```bash
   watch -n 5 'ps aux | grep enrich_profiles'
   ```

2. **Check logs for datetime errors** after restart:
   ```bash
   tail -f /home/ff/.openclaw/workspace/repos/CDP_Merged/logs/enrichment_errors.log
   ```

3. **If OOM kills persist**, consider:
   - Reducing batch size further (try 25)
   - Running on a machine with more RAM
   - Processing in smaller chunks with longer delays

4. **To start Phase 2** with the fixed script:
   ```bash
   cd /home/ff/.openclaw/workspace/repos/CDP_Merged
   bash run_phase2.sh
   ```

---

## Files Modified

1. `/home/ff/.openclaw/workspace/repos/CDP_Merged/run_phase2.sh` - Enhanced runner with memory protection
2. `/home/ff/.openclaw/workspace/repos/CDP_Merged/src/enrichment/postgresql_pipeline.py` - Fixed datetime bug and memory management

---

## Expected Behavior After Fixes

- Process should run for longer periods without crashing
- OOM kills should be handled gracefully with backoff
- No more "can't subtract offset-naive and offset-aware datetimes" errors
- Progress should steadily increase without skipping records
