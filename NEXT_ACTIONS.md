# NEXT_ACTIONS - CDP_Merged - AZURE INFRASTRUCTURE

**Platform:** AZURE (VMs, Container Apps, OpenAI)  
**Date:** 2026-03-06  
**Owner:** AI Agent / Developer  
**Purpose:** Active queue only. Older completions now live in `WORKLOG.md`; roadmap items live in `BACKLOG.md`.

## Active

### P0: Finalize Offline Local Development Stack

**Status:** ACTIVE - runtime fixed, 1000-row local smoke dataset loaded, full-truth dataset still pending
**Discovered:** 2026-03-07
**Last Updated:** 2026-03-07 16:10 CET
**Severity:** HIGH

#### Current State

- The runtime tree has been restored into `/home/ff/Documents/CDP_Merged`.
- Local PostgreSQL now starts cleanly from `docker-compose.postgres.yml` using `schema_local.sql`.
- `start_chatbot.sh` now launches the local app via `uvicorn`, sources `.env` plus `.env.local`, and the runtime is using real OpenAI successfully.
- Local Tracardi containers are up, auth succeeds, and event sources have been created via `setup_tracardi_kbo_and_email.py`.
- Chat-session bootstrap now works: `TracardiClient().get_or_create_profile()` returns profiles successfully.
- `.env.local` has been updated with `TRACARDI_SOURCE_ID=cdp-api`.
- The local `public.companies` table currently has `1,000` rows from a PostgreSQL-only smoke import, so local prompts are no longer blocked by an empty dataset.
- The chatbot query contract has been corrected so generic searches no longer default to `status=AC`, and zero-result searches now expose an empty-dataset diagnostic instead of offering segments/campaigns blindly.
- The main importer path defect is fixed: `scripts/import_kbo_full_enriched.py` now resolves the KBO zip from `KBO_ZIP_PATH` or the active repo, and `scripts/run_full_kbo_import.py` uses the same resolver.
- The main importer now writes canonical `companies` columns directly, including `status`, `juridical_situation`, `legal_form_code`, `type_of_enterprise`, `main_fax`, `establishment_count`, `all_names`, `all_nace_codes`, and `nace_descriptions`.
- Local direct SQL verification on the 1000-row smoke slice showed `status=1000`, `juridical_situation=1000`, `legal_form_code=1000`, `type_of_enterprise=1000`, `all_names=1000`, `all_nace_codes=687`, `nace_descriptions=687`, and `establishment_count>0=682`.
- The importer retry path was also fixed in this session: an off-by-one record-limit bug and a COPY fallback INSERT placeholder mismatch no longer block idempotent reruns.
- Bulk full-dataset Tracardi sync during initial import is lower priority than a correct PostgreSQL-first load; use Tracardi projection selectively after the canonical dataset is trustworthy.

#### Completed

✅ **Local Tracardi event sources created** (2026-03-07 15:24 CET)
- Created 4 event sources: `kbo-batch-import`, `kbo-realtime`, `resend-webhook`, `cdp-api`
- Verified `/track` endpoint works and returns profiles
- `TracardiClient` bootstrap now functional

#### Next Actions

1. **Expand the local PostgreSQL-first import beyond the 1000-row smoke slice, or point local `DATABASE_URL` at a populated PostgreSQL instance.**
   - Current direct localhost probe shows `companies.total = 1000`
   - Until the local dataset is representative, local count answers still verify behavior more than business truth
2. **Re-run the chatbot quality prompts on the now non-empty local dataset.**
   - Start with `How many restaurants are in Sint-Niklaas?`
   - Verify the answer no longer says `active` unless the user asked for it
3. **Smoke the deployed environment with the same prompt.**
   - Confirm production uses the same no-default-status behavior and does not regress on populated data
4. **Carry the KBO zip resolver and canonical-column mapping discipline into the remaining helper scripts that still assume `.openclaw` paths or older insert shapes.**

### P1: PostgreSQL City Query Performance Investigation - PARTIALLY RESOLVED

**Status:** ACTIVE - Root causes identified and partially fixed  
**Discovered:** 2026-03-06  
**Last Updated:** 2026-03-06 20:35 CET  
**Severity:** HIGH (partially mitigated)

#### Problems Identified & Fixes Applied

**1. Table Bloat - FIXED ✅**
- Root cause: 231,766 dead tuples (12% bloat) causing 267 MB heap reads per query
- Fix: `VACUUM ANALYZE companies` executed
- Result: Count queries improved from 18s → 0.088s

**2. Missing Composite Index - FIXED ✅**
- Root cause: Existing `idx_companies_city_status` was on `(city, sync_status)`, not `(city, status)`
- Fix: Created `idx_companies_city_status_real` on `(city, status)`  
- Schema updated: `schema_optimized.sql`

**3. Status Column Empty - IMPORT/BACKFILL ISSUE ⚠️**
- Discovery: Both `status` and `juridical_situation` columns are NULL for all 1.94M records
- Impact: Status filtering (`status='AC'`) returns 0 results (not a performance issue)
- Action needed: Correct the KBO import/backfill path so those dedicated columns are populated from source data

#### Current Performance (After All Fixes)

| Query Type | Brussels (41k) | Antwerp (62k) | Ghent (29k) |
|------------|----------------|---------------|-------------|
| Count | 0.088s ✅ | <1s ✅ | <1s ✅ |
| Aggregation | 25.3s ⚠️ | TBD | 0.168s ✅ |

**Root cause for aggregation slowness:** Large cities require processing 40K+ rows for GROUP BY. Ghent now fast due to covering index. Brussels/Antwerp need application-layer LIMIT.

#### Fixes Applied
1. ✅ **VACUUM ANALYZE** - Removed 231K dead tuples, count queries now 0.07s
2. ✅ **Composite index** - Created idx_companies_city_status_real on (city, status)
3. ✅ **Covering index** - Created idx_companies_city_nace on (city, industry_nace_code)

#### Next Actions
1. **Application fix:** Add LIMIT to aggregation queries to cap processing time
2. **Data fix:** Backfill `status` and `juridical_situation` via a corrected KBO import/backfill path
3. **Test:** Verify live chatbot behavior (Ghent should work, Brussels may need LIMIT fix)
4. **Background:** Schedule periodic VACUUM to prevent future bloat

## Paused

### P1: Reconcile Canonical Enrichment Truth And Runner Behavior

**Status:** PAUSED  
**Paused:** 2026-03-06  
**Reason:** The enrichment runners are currently active and PostgreSQL remains usable; user priority shifted to chatbot performance work.

Resume when:
- a runner exits non-zero, PostgreSQL-backed counts stop moving, or chatbot work no longer blocks higher-value progress

Next action:
1. If website, geocoding, or CBE supervision degrades, resume runner-specific verification from the current logs and rerun canonical PostgreSQL counts.

### P1: Chatbot Performance Tracing

**Status:** PAUSED  
**Paused:** 2026-03-06  
**Reason:** The user redirected the active task toward answer quality, scenario utility, and multi-session behavior.

Resume when:
- answer-quality work is no longer the highest-value chatbot task

Next action:
1. Return to latency tracing after the quality/scenario audit produces a clearer functional target.

### P1: Production UX And Operator Layer

**Status:** PAUSED  
**Paused:** 2026-03-06  
**Reason:** The current priority is trustworthy data and runtime behavior, not broader operator-surface expansion.

Resume when:
- enrichment progress and Antwerp latency are no longer the primary active risks

Next action:
1. Re-scope the operator-layer work against the stabilized PostgreSQL-first query path.

### P1: Azure Observability And RG Cleanup

**Status:** PAUSED  
**Paused:** 2026-03-06  
**Reason:** The 2026-03-06 resource audit found only narrow cleanup candidates in `rg-cdpmerged-fast`, while website-runner durability is still the higher-leverage blocker.

Resume when:
- website supervision is stable enough to spend time on Azure cleanup and observability drift

Next action:
1. Verify whether storage account `stcdpmergedprtnlp` and the `Application Insights Smart Detection` action group can be deleted without losing needed backup or alerting state.
2. Decide whether to attach `ca-cdpmerged-fast-env` to a real Log Analytics workspace or retire the currently unlinked workspace after a retention review.

## Recently Closed

### 2026-03-06: Chatbot Analytics Aggregation Tool Debugging - VERIFIED ✅

**Status:** COMPLETE (FIX VERIFIED)  
**Deployed:** Revision `ca-cdpmerged-fast--stg-877f0e9`  
**Fixed:** Analytics aggregation tool now supports "industry" as an alias for "nace_code"

Problem:
- "top industries" queries failed because the LLM used `group_by="industry"` which was not in the valid_group_by set
- The critic_node validation was also missing `legal_form` which was valid in the tool

Fix applied:
1. Added `"industry": "industry_nace_code"` alias to field_map in `src/services/postgresql_search.py`
2. Added `"industry"` to valid_group_by in `src/ai_interface/tools/search.py` aggregate_profiles
3. Added `"industry"` and `"legal_form"` to critic_node validation in `src/graph/nodes.py`
4. Updated aggregate_profiles docstring to document the alias

Verification:
- All 519 unit tests pass
- CI/CD workflows completed successfully
- Deployment: revision `ca-cdpmerged-fast--stg-877f0e9` now serving 100% traffic
- **LIVE VERIFICATION:** Query "What are the top industries in Brussels?" correctly used `group_by='nace_code'`
- Screenshot: `analytics_test_brussels_timeout_2026-03-06.png`

Secondary Issue Discovered:
- Database queries with city filters are timing out systematically (tracked separately)

### 2026-03-06: Chatbot Quality Matrix Evaluation

- Quality matrix completed on deployed `20e4e35` after Azure OpenAI rate limit fix
- Results: count queries ✅, follow-up narrowing ✅, multi-turn continuity ✅, segment creation ⚠️, analytics ❌
- Azure OpenAI rate limiting: FIXED - no 429 errors, response times under 25 seconds
- Multi-turn continuity: WORKING - thread correctly remembers previous search context
- Status filtering: WORKING - active vs all statuses return different results
- Segment creation: FUNCTIONAL - creates segments but single-company results may not meet criteria
- Analytics aggregation: FIXED ✅ - "top industries" queries now correctly map to nace_code

### 2026-03-06: Verify Geocoding Durability

- Eight post-cutover chunks completed with enrichments: 101, 405, 400, 397, 418, 407, 407, 405.
- Zero explicit 429 or unexpected-error lines in the new supervised runner log.
- Canonical `geo_latitude` increased from 4,142 to 5,779 (+1,637 records).
- Geocoding durability risk is now closed.

### 2026-03-06: Tighten Main Local-Only CBE Selector

- `scripts/enrich_companies_batch.py` now requires usable NACE input for CBE selection instead of re-targeting rows solely because `industry_nace_code` is blank.
- Same-day selector recheck counted `1,226,399` main-selector rows and `688,581` deferred NACE-less rows; the first post-edit chunk completed `2,000` enriched / `0` skipped.

### 2026-03-06: Fix Chunked Failure Exit Propagation

- `scripts/enrich_companies_chunked.py` now returns non-zero when an inner chunk fails, when a full chunk omits `Last company ID`, or when the run is interrupted.
- `tests/unit/test_enrich_companies_batch.py` now covers the failing-chunk exit path so the supervisor cannot silently treat a failed chunk as success again.
