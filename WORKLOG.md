# WORKLOG

**Purpose:** Append-only session log for meaningful task updates

---

## 2026-03-14 (Privacy Boundary Fix - Gap Resolution)

### Task: Resolve event metadata privacy divergence (Gap #3)

**Type:** code_and_docs
**Status:** COMPLETE
**Timestamp:** 2026-03-14 11:03 CET
**Git Head:** `fca9637` (docs checkpoint) + uncommitted changes

**Summary:**
Fixed the "event metadata privacy divergence" gap that was marked as ⚠️ Partial. The issue was that `cdp_event_processor.py` stored raw emails and unsanitized event data in the `company_engagement` table, while the gateway properly sanitized downstream data.

**Changes Made:**

1. **Code Changes (`scripts/cdp_event_processor.py`):**
   - Added `hash_identifier()` function for SHA-256 hashing
   - Added `extract_email_domain()` function for domain-only extraction
   - Added `sanitize_event_data()` function to remove PII before storage
   - Modified `update_engagement_score()` to store hashed email (`email_hash`) instead of raw email
   - Modified `update_engagement_score()` to store sanitized event data (no raw emails/subjects)
   - Updated table schema: `email` column → `email_hash VARCHAR(64)`

2. **Migration (`scripts/migrations/008_privacy_boundary_fix.sql`):**
   - Adds `email_hash` column to existing table
   - Migrates existing email data to hashed format
   - Sanitizes existing `event_data` JSONB records
   - Creates index on `email_hash` for lookups

3. **Tests (`tests/unit/test_cdp_event_processor.py`):**
   - Added `test_hash_identifier_produces_deterministic_sha256()`
   - Added `test_extract_email_domain_extracts_domain_only()`
   - Added `test_sanitize_event_data_removes_pii_preserves_metadata()`
   - Added `test_sanitize_event_data_handles_click_data()`
   - Added `test_update_engagement_score_uses_hashed_email_and_sanitized_data()`

4. **Documentation Updates:**
   - `docs/BUSINESS_CONFORMITY_MATRIX.md`: Privacy boundary now ✅ Verified
   - `docs/ILLUSTRATED_GUIDE.md`: Updated privacy section, checklist item #9 now ✅ Verified
   - `docs/ACCEPTANCE_CRITERIA.md`: AC-5 now PASS (was PARTIAL)

**Privacy Layers (All Now Verified):**
| Layer | Status |
|-------|--------|
| PostgreSQL core | ✅ UID-first |
| Tracardi profiles | ✅ Anonymous |
| Event metadata (stored) | ✅ Hashed only (fixed) |
| Event metadata (gateway) | ✅ Sanitized |
| Engagement records | ✅ No raw PII (fixed) |

**Test Results:**
- `test_cdp_event_processor.py`: 11 passed (was 6)
- `test_webhook_gateway.py`: 48 passed (unchanged)

**Verification:**
- Raw emails no longer stored in `company_engagement`
- Event data sanitized before JSONB storage
- Deterministic SHA-256 hashing for matching
- All existing tests pass + 5 new privacy tests

---

## 2026-03-14 (Backlog v2 Restructuring)

### Task: Compress the overloaded backlog into 5 active epics with a tight NOW/Next/Later/Watchlist queue

**Type:** docs_or_process_only
**Status:** COMPLETE
**Timestamp:** 2026-03-14 10:44 CET
**Git Head:** `not rechecked`

**Summary:**
Received comprehensive feedback that the existing backlog (v1) had become operationally mature but editorially overloaded. It was trying to be: strategic roadmap, execution backlog, risk register, architecture guardrail, verification ledger, documentation audit, product critique, and future standards watchlist all at once.

Restructured into **Backlog v2** with:
1. **Five Active Epics** (replacing 14 milestones POC/0A/0B/0C/0D/0-7):
   - Epic 1: Credible Local Demo (packaging > backend now)
   - Epic 2: Enrichment Coverage (background throughput program)
   - Epic 3: Colleague-Facing Product Shell (per-user workspaces)
   - Epic 4: Data Model and Runtime Hardening (src/models/ fate decision)
   - Epic 5: Production Hardening (secrets, observability, runbooks)

2. **Active Queue** (NOW ≤10 items, Next, Later, Watchlist) — agents start from NOW, not from the bottom of the file

3. **Azure Language Frozen** to match PROJECT_STATE.yaml's `local_only_permanent` reality — no more "paused" implying possible return to full Azure hosting

4. **Explicit src/models/ Decision Point** — keep-and-complete or archive; no half-alive state

5. **Watchlist Moved to Appendix** — A2A, AG-UI/A2UI, MCP expansion, Responses API alignment, etc. Not active bottlenecks

6. **Architectural Truth Preserved** — PostgreSQL truth layer, source PII boundaries, Tracardi activation layer, chatbot query plane all remain prominent

**Key Feedback Incorporated:**
- Demo packaging layer is the risk, not fundamental capability (backend is further along than presentation)
- Enrichment is a background throughput program, not the main daily narrative
- The 5-epic structure compresses without losing rigor
- Removed duplication (conformity matrix, acceptance criteria, maturity labels appeared in multiple places)

**Files Changed:**
- `BACKLOG.md` (complete rewrite from v1 → v2)
- `STATUS.md` (updated last-updated header to reference v2)

**Verification:**
- `wc -l BACKLOG.md` -> ~340 lines (down from ~633 lines, ~46% reduction)
- `rg "Epic [1-5]" BACKLOG.md` -> 5 epics found
- `rg "^### (NOW|NEXT|LATER|WATCHLIST)" BACKLOG.md` -> queue structure confirmed
