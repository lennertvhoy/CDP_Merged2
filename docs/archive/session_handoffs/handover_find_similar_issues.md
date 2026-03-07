# Handover: Find Similar Parameter Propagation Issues

## Context

**Project**: CDP_Merged - Customer Data Platform with PostgreSQL-based enrichment pipeline
**Architecture**: Azure-Only Hybrid v2.0 (PostgreSQL + Event Hub + local VM enrichment)
**Current Phase**: Phase 2 (CBE Integration) - Enriching 1.8M company profiles

## Issue Pattern Found

### The Bug
**Silent parameter dropping in async call chains** - The `--limit` CLI parameter was not being passed through the entire call chain, causing the enrichment to use incorrect total counts.

### Root Cause
In `src/enrichment/postgresql_pipeline.py`, the `run_from_postgresql()` method was calling `run_phase_streaming()` but NOT passing the `limit` parameter.

### Symptoms
- Process exits cleanly (exit code 0) after processing ~500-1000 records
- No errors in logs
- Progress seems to work but process restarts constantly
- Checkpoint file keeps growing but process never completes

---

## INVESTIGATION FINDINGS (Session 2026-03-01)

### Critical Issues Found

| File | Method | Issue | Severity | Status |
|------|--------|-------|----------|--------|
| `src/enrichment/pipeline.py` | `run_enrichment()` | `limit` parameter accepted but NOT passed to `run_phase_streaming()` | **HIGH** | NOT FIXED |
| `src/enrichment/pipeline.py` | `run_from_tracardi()` | `limit` passed to `fetch_profiles()` but NOT to `run_full_pipeline()` | **HIGH** | NOT FIXED |
| `src/enrichment/pipeline.py` | `run_full_pipeline()` | Does NOT accept `limit` parameter | **HIGH** | NOT FIXED |
| `src/enrichment/pipeline.py` | `run_phase_streaming()` | Does NOT accept `limit` parameter | **HIGH** | NOT FIXED |

### Already Fixed

| File | Method | Fix Description |
|------|--------|-----------------|
| `src/enrichment/postgresql_pipeline.py` | `run_from_postgresql()` | Now passes `limit=limit` to `run_phase_streaming()` |
| `src/enrichment/postgresql_pipeline.py` | `run_phase_streaming()` | Added `limit` parameter and implements limit checking |

---

## Detailed Issue Analysis

### Issue 1: `run_enrichment()` in `pipeline.py` (lines 729-799)

**Problem**: The `limit` parameter is accepted but never passed downstream.

```python
# Line 729-735 - accepts limit
async def run_enrichment(
    query: str = "*",
    limit: int | None = None,  # <-- Parameter accepted
    phases: list[str] | None = None,
    dry_run: bool = True,
    batch_size: int = 100,
) -> dict:

# Lines 781-786 - limit NOT passed
result = await pipeline.run_phase_streaming(
    phase_name=job_id,
    enricher_name=phase_name,
    query=query,
    dry_run=dry_run,
    # limit=limit,  # <-- MISSING!
)
```

**Fix Required**: Either:
1. Add `limit` parameter to `run_phase_streaming()` and pass it
2. OR remove `limit` from `run_enrichment()` if not supported (but better to add support)

---

### Issue 2: `run_from_tracardi()` in `pipeline.py` (lines 690-716)

**Problem**: The `limit` is used for `fetch_profiles()` but not passed to `run_full_pipeline()`.

```python
# Lines 690-696 - accepts limit
async def run_from_tracardi(
    self,
    query: str = "*",
    limit: int | None = None,  # <-- Parameter accepted
    phases: list[str] | None = None,
    dry_run: bool = False,
) -> dict:

# Line 710 - limit used for fetch_profiles (GOOD)
profiles = await self.fetch_profiles(query, limit)

# Line 716 - limit NOT passed to run_full_pipeline
return await self.run_full_pipeline(profiles, phases, dry_run)
# Should be: return await self.run_full_pipeline(profiles, phases, dry_run, limit)
```

**Fix Required**: 
1. Add `limit` parameter to `run_full_pipeline()` 
2. Pass `limit=limit` when calling it

---

### Issue 3: `run_full_pipeline()` in `pipeline.py` (lines 611-716)

**Problem**: Does NOT accept `limit` parameter.

```python
# Lines 611-616 - NO limit parameter
async def run_full_pipeline(
    self,
    profiles: list[dict],
    phases: list[str] | None = None,
    dry_run: bool = False,
    # limit: int | None = None,  # <-- MISSING!
) -> dict:
```

**Fix Required**: 
1. Add `limit` parameter to method signature
2. Use limit when processing profiles in the loop
3. Pass limit to `run_phase()` if needed

---

### Issue 4: `run_phase_streaming()` in `pipeline.py` (lines 241-423)

**Problem**: Does NOT accept `limit` parameter.

```python
# Lines 241-248 - NO limit parameter
async def run_phase_streaming(
    self,
    phase_name: str,
    enricher_name: str,
    query: str,
    job_id: str | None = None,
    dry_run: bool = False,
    # limit: int | None = None,  # <-- MISSING!
) -> dict:
```

**Fix Required**: 
1. Add `limit` parameter to method signature
2. Implement limit checking in the streaming loop (see postgresql_pipeline.py for reference implementation)

---

## Code Changes Required

### Fix 1: `run_phase_streaming()` in `pipeline.py`

**Current signature (line 241-248):**
```python
async def run_phase_streaming(
    self,
    phase_name: str,
    enricher_name: str,
    query: str,
    job_id: str | None = None,
    dry_run: bool = False,
) -> dict:
```

**Required signature:**
```python
async def run_phase_streaming(
    self,
    phase_name: str,
    enricher_name: str,
    query: str,
    job_id: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,  # <-- ADD THIS
) -> dict:
```

**Also need to add limit logic** similar to postgresql_pipeline.py (around line 345 in the streaming loop).

---

### Fix 2: `run_full_pipeline()` in `pipeline.py`

**Current signature (line 611-616):**
```python
async def run_full_pipeline(
    self,
    profiles: list[dict],
    phases: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
```

**Required signature:**
```python
async def run_full_pipeline(
    self,
    profiles: list[dict],
    phases: list[str] | None = None,
    dry_run: bool = False,
    limit: int | None = None,  # <-- ADD THIS
) -> dict:
```

---

### Fix 3: `run_from_tracardi()` call (line 716)

**Current:**
```python
return await self.run_full_pipeline(profiles, phases, dry_run)
```

**Required:**
```python
return await self.run_full_pipeline(profiles, phases, dry_run, limit)
```

---

### Fix 4: `run_enrichment()` call (lines 781-786)

**Current:**
```python
result = await pipeline.run_phase_streaming(
    phase_name=job_id,
    enricher_name=phase_name,
    query=query,
    dry_run=dry_run,
)
```

**Required:**
```python
result = await pipeline.run_phase_streaming(
    phase_name=job_id,
    enricher_name=phase_name,
    query=query,
    dry_run=dry_run,
    limit=limit,  # <-- ADD THIS
)
```

---

## Search Strategy

### 1. Find All Async Call Chains with Optional Parameters

Search for patterns where methods accept optional parameters but may not pass them to downstream calls:

```bash
# Find methods with optional limit/offset/dry_run parameters
grep -rn "limit: int | None" src/ --include="*.py"
grep -rn "dry_run: bool" src/ --include="*.py" 
grep -rn "batch_size.*| None" src/ --include="*.py"

# Find async method calls that might be missing parameters
grep -rn "await self\.run_" src/ --include="*.py" -A 5
```

### 2. Check CLI Entry Points

Look at all CLI scripts to see what parameters they accept vs what gets passed:

```bash
# List all CLI entry points
ls -la scripts/*.py

# Check which ones have --limit, --batch-size, --dry-run
for f in scripts/*.py; do echo "=== $f ==="; grep -n "limit\|batch_size\|dry_run" "$f" | head -20; done
```

### 3. Trace Parameter Flow

For each suspicious method, trace the parameter flow:

```bash
# Example: trace 'limit' parameter
grep -rn "limit" src/enrichment/*.py | grep -E "def |await |limit="
```

### 4. Look for Similar Method Signatures

Find methods that have similar signatures to the fixed one:

```bash
# Methods with similar patterns
grep -rn "async def run_.*phase" src/ --include="*.py" -A 3
```

## Specific Files to Check

### High Priority
1. **`src/enrichment/postgresql_pipeline.py`**
   - `run_from_postgresql()` - Fixed
   - `run_phase_streaming()` - Fixed
   - Check `run_full_pipeline()` - does it handle limit correctly?
   - Check `run_phase()` - does it handle limit correctly?

2. **`src/enrichment/pipeline.py`** (Tracardi legacy pipeline)
   - `run_from_tracardi()` - limit NOT passed to run_full_pipeline
   - `run_full_pipeline()` - does NOT accept limit parameter
   - `run_phase_streaming()` - does NOT accept limit parameter  
   - `run_enrichment()` - limit NOT passed to run_phase_streaming

3. **`scripts/enrich_profiles.py`**
   - Fixed datetime warnings
   - Check if all CLI args are passed to both PostgreSQL and Tracardi pipelines

### Medium Priority
4. **`src/enrichment/cbe_integration.py`**
   - Check if batch processing respects limits
   
5. **`src/enrichment/cbe_extended.py`**
   - Check financial data enrichment limits

6. **`src/enrichment/website_discovery.py`**
   - Check rate limiting and batch handling

### Low Priority (but worth checking)
7. Any other enrichment modules in `src/enrichment/`
8. Import/migration scripts in `scripts/`

## Common Bug Patterns to Look For

### Pattern 1: Parameter Not Passed
```python
# BAD - missing limit
result = await downstream_method(
    arg1=value1,
    arg2=value2,
)

# GOOD
result = await downstream_method(
    arg1=value1,
    arg2=value2,
    limit=limit,  # <-- was missing
)
```

### Pattern 2: Wrong Default Value
```python
# BAD - wrong default causes early exit
limit: int = 100  # Should be None for "no limit"

# GOOD
limit: int | None = None
```

### Pattern 3: Shadowing Outer Variable
```python
# BAD - inner loop shadows limit
for limit in range(10):  # Shadows outer limit parameter!
    ...
```

### Pattern 4: Type Mismatch
```python
# BAD - string vs int
total_matches = min(total_in_db, limit)  # Fails if limit is "1000" (string)

# GOOD
total_matches = min(total_in_db, int(limit)) if limit else total_in_db
```

## Testing Strategy

For each suspicious method:

1. **Run with small limit** (`--limit 10`) - should process ~10-25 records and exit
2. **Check exit code** - should be 0 on success
3. **Verify checkpoint** - should be updated correctly
4. **Run with large limit** (`--limit 2000000`) - should run for minutes without exiting

## Commands to Run

```bash
# Quick test with small limit (PostgreSQL - should work after fix)
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
timeout 10 poetry run python scripts/enrich_profiles.py \
    --use-postgresql \
    --phase phase2_cbe_integration \
    --dry-run \
    --batch-size 25 \
    --limit 10 \
    --log-level INFO 2>&1 | tail -20

# Quick test with small limit (Tracardi - will FAIL until fixes applied)
timeout 10 poetry run python scripts/enrich_profiles.py \
    --use-tracardi \
    --phase phase2_cbe_integration \
    --dry-run \
    --batch-size 25 \
    --limit 10 \
    --log-level INFO 2>&1 | tail -20

# Check checkpoint
cat data/progress/streaming_last_offset_phase2_cbe_integration.json

# Verify process runs continuously (should run for 60s without exit)
timeout 60 poetry run python scripts/enrich_profiles.py \
    --use-postgresql \
    --phase phase2_cbe_integration \
    --dry-run \
    --batch-size 25 \
    --limit 2000000 \
    --log-level WARNING &
PID=$!
sleep 60
ps -p $PID > /dev/null && echo "Running" || echo "Exited"
```

## Files Modified in This Session

1. `src/enrichment/postgresql_pipeline.py` - Fixed limit propagation in `run_from_postgresql()` and `run_phase_streaming()`
2. `scripts/enrich_profiles.py` - Fixed datetime deprecation warnings
3. `run_phase2.sh` - Improved logging level

## Files Requiring Fixes (Next Session)

1. `src/enrichment/pipeline.py` - Multiple fixes needed:
   - Add `limit` parameter to `run_phase_streaming()`
   - Add `limit` parameter to `run_full_pipeline()`
   - Pass `limit` in `run_from_tracardi()` call to `run_full_pipeline()`
   - Pass `limit` in `run_enrichment()` call to `run_phase_streaming()`
   - Implement limit logic in streaming loop

## Checkpoint Status

Current Phase 2 progress:
- **Total profiles**: 1,813,016
- **Current offset**: Check `data/progress/streaming_last_offset_phase2_cbe_integration.json`
- **Progress**: ~2.6% complete (as of last report)

## Verification Commands

After any fixes, verify with:

```bash
# Syntax check
python -m py_compile src/enrichment/pipeline.py
python -m py_compile src/enrichment/postgresql_pipeline.py
python -m py_compile scripts/enrich_profiles.py

# Quick functional test (PostgreSQL - should work)
timeout 30 poetry run python scripts/enrich_profiles.py \
    --use-postgresql \
    --phase phase2_cbe_integration \
    --dry-run \
    --limit 100 \
    --batch-size 25 \
    --log-level INFO 2>&1 | grep -E "processed|enriched|limit"

# Quick functional test (Tracardi - will work after fixes)
timeout 30 poetry run python scripts/enrich_profiles.py \
    --use-tracardi \
    --phase phase2_cbe_integration \
    --dry-run \
    --limit 100 \
    --batch-size 25 \
    --log-level INFO 2>&1 | grep -E "processed|enriched|limit"
```

## Implementation Reference

See `src/enrichment/postgresql_pipeline.py` for the correct implementation:
- `run_phase_streaming()` (line 325+) - Shows how to implement limit checking in streaming loop
- `run_from_postgresql()` (line 700+) - Shows proper limit parameter passing

---

**Verification phrase**: okdennieh
