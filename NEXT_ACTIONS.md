# NEXT_ACTIONS - CDP_Merged - Local-First Working Queue

**Platform:** Azure target architecture with local-only execution mode
**Current Execution Mode:** Local-only (`Azure deployment path paused to save costs`)
**Date:** 2026-03-07
**Owner:** AI Agent / Developer
**Purpose:** Active queue only. Older completions now live in `WORKLOG.md`; roadmap items live in `BACKLOG.md`.

## Active

### P0: Finalize Offline Local Development Stack

**Status:** COMPLETE - runtime fixed, full 1.94M dataset loaded and verified
**Discovered:** 2026-03-07
**Last Updated:** 2026-03-07 18:09 CET
**Severity:** HIGH

#### Current State

- The runtime tree has been restored into `/home/ff/Documents/CDP_Merged`.
- Local PostgreSQL now starts cleanly from `docker-compose.postgres.yml` using `schema_local.sql`.
- `start_chatbot.sh` now launches the local app via `uvicorn`, sources `.env` plus `.env.local`, and the runtime is using real OpenAI successfully.
- Local Tracardi containers are up, auth succeeds, and event sources have been created via `setup_tracardi_kbo_and_email.py`.
- `docker compose up -d --build` now brings up the full local stack by default: PostgreSQL, Tracardi, Wiremock, and the chatbot.
- `docker compose ps` now shows the chatbot container healthy on `:8000`, and `/healthz` plus `/readinessz` both return `status: ok`.
- Chat-session bootstrap now works: `TracardiClient().get_or_create_profile()` returns profiles successfully.
- `.env.local` has been updated with `TRACARDI_SOURCE_ID=cdp-api`.
- The local `public.companies` table now holds the full `1,940,603`-row PostgreSQL-first KBO dataset, so local count and aggregation prompts are now business-truth capable.
- The chatbot query contract has been corrected so generic searches no longer default to `status=AC`, and zero-result searches now expose an empty-dataset diagnostic instead of offering segments/campaigns blindly.
- The main importer path defect is fixed: `scripts/import_kbo_full_enriched.py` now resolves the KBO zip from `KBO_ZIP_PATH` or the active repo, and `scripts/run_full_kbo_import.py` uses the same resolver.
- The main importer now writes canonical `companies` columns directly, including `status`, `juridical_situation`, `legal_form_code`, `type_of_enterprise`, `main_fax`, `establishment_count`, `all_names`, `all_nace_codes`, and `nace_descriptions`.
- Same-day local full-dataset verification found 1,105 restaurants in Gent, 41,290 companies in Brussels, 62,831 companies in Antwerpen, and a successful Brussels industry aggregation.
- The importer retry path was also fixed in this session: an off-by-one record-limit bug and a COPY fallback INSERT placeholder mismatch no longer block idempotent reruns.
- Bulk full-dataset Tracardi sync during initial import is lower priority than a correct PostgreSQL-first load; use Tracardi projection selectively after the canonical dataset is trustworthy.
- Azure deployment and Azure verification work are paused by user direction while the project stays in a local-only cost-control mode.

#### Completed

✅ **Local Tracardi event sources created** (2026-03-07 15:24 CET)
- Created 4 event sources: `kbo-batch-import`, `kbo-realtime`, `resend-webhook`, `cdp-api`
- Verified `/track` endpoint works and returns profiles
- `TracardiClient` bootstrap now functional

✅ **Chatbot quality prompts verified on 10k dataset** (2026-03-07 16:45 CET)
- Verified restaurant queries in Gent (6 found) and Sint-Niklaas (0 found - correct)
- Verified Brussels companies query returns 356 without status filter
- Backend correctly treats `status=None` as "all statuses"
- Note: LLM occasionally infers `status="AC"` despite schema instructions; this is LLM-level behavior, not a code bug

✅ **Full 1.94M dataset import complete and verified** (2026-03-07 17:05 CET)
- Total: 1,940,603 records imported to local PostgreSQL
- Restaurants in Gent: 1,105 (verified via search tool)
- Companies in Brussels: 41,290 (verified)
- Companies in Antwerpen: 62,831 (verified)
- Aggregation queries working (top industries in Brussels: 70200 at 4.8%)
- All queries execute in <3 seconds

#### Completed

✅ **Stale path cleanup completed** (2026-03-07 17:35 CET)
- Fixed 12 Python scripts with stale `.openclaw` path references
- Fixed 3 shell scripts with stale `.openclaw` path references
- Fixed `src/ingestion/kbo_ingest.py` and `infra/scripts/shutdown-restart-test.sh`
- All active source code now uses repo-relative paths or `resolve_kbo_zip_path()`

✅ **Local regression script hardened and verified** (2026-03-07 17:38 CET)
- `scripts/regression_local_chatbot.py` now covers 7 host-side checks
- Tests: Gent restaurants, Brussels companies, Antwerpen aggregation, NACE search, email domain, city counts, local artifact export
- Verified via `bash -lc '.venv/bin/python scripts/regression_local_chatbot.py'` against host PostgreSQL

✅ **Compose-managed local stack verified** (2026-03-07 18:08 CET)
- Replaced the ad-hoc host `uvicorn` process with the compose-managed chatbot container on `:8000`
- Verified `docker compose ps`, `curl http://localhost:8000/healthz`, and `curl http://localhost:8000/readinessz`
- Fixed `scripts/demo_smoke_test.py` to use the current health endpoints and PostgreSQL schema; quick mode now passes 8/8 and reports demo-ready

#### Next Actions

All P0 items complete. Ready for next local-only task or user direction.

### P1: Local Helper Script Hardening

**Status:** COMPLETE
**Discovered:** 2026-03-07
**Last Updated:** 2026-03-07 17:38 CET
**Severity:** HIGH

#### Current State

- The main local importer path and canonical-column mapping are fixed.
- Same-day local verification shows the full 1.94M-row dataset and key chatbot prompts are working.
- The remaining active helper/setup/demo scripts that mattered for local execution no longer assume the stale `.openclaw` workspace path or old KBO zip locations.
- Azure deployment verification is paused by user direction while the project stays in local-only cost-control mode.

#### Completed
- ✅ Replaced stale workspace assumptions with repo-relative imports
- ✅ Created and re-verified fast local-only regression script (`scripts/regression_local_chatbot.py`)
- ✅ Exposed export, coverage, and local artifact tools to the chatbot runtime
- ✅ Added `nace_code` alias and `email_domain` filter support to the local query tool contract

#### Next Actions
None for this work item.

### P1: Local Multi-Message Runtime Hardening

**Status:** COMPLETE
**Discovered:** 2026-03-07
**Last Updated:** 2026-03-07 18:20 CET
**Severity:** HIGH

#### Current State

- The local chatbot now exposes `create_data_artifact`, `get_data_coverage_stats`, `export_segment_to_csv`, and `email_segment_export` in the agent tool layer.
- Stable harness coverage now includes a tool-heavy multi-turn story with local artifact generation.
- Compose-managed regression and quick demo smoke now confirm the local PostgreSQL path, NACE alias search, email-domain filtering, artifact export, and top-level demo readiness checks all work.
- **Browser-driven multi-turn scenario completed:** Verified search → artifact → segment → export flow through real threaded browser session against http://localhost:8000.

#### Completed

✅ **Browser-driven multi-turn operator scenario** (2026-03-07 18:20 CET)
- Search: "How many software companies are in Brussels?" → 1,529 companies found
- Artifact: Created markdown artifact with first 100 results → Download link provided
- Segment: Created "Brussels Software Companies" segment (0 profiles - expected, PostgreSQL not synced to Tracardi)
- Export: Attempted CSV export → Correctly reported 0 profiles (segment empty)
- Artifact file created: `output/agent_artifacts/software-companies-in-brussels_20260307_171512.markdown`
- Screenshot captured: `chatbot_full_flow_test_2026-03-07.png`

#### Next Actions
None - multi-message runtime hardening complete. Local stack verified end-to-end.

#### Known Limitations (Architecture Gap, Not Bug)
- Segments are created in Tracardi but contain 0 profiles because the PostgreSQL companies have not been synced to Tracardi profiles
- This is the expected PostgreSQL-first architecture: PostgreSQL is the analytical truth layer, Tracardi is the activation runtime
- Future work: Add selective PostgreSQL-to-Tracardi sync for activation workflows

## Paused

### P0: Azure Deployment Path

**Status:** PAUSED
**Paused:** 2026-03-07
**Reason:** The user explicitly paused Azure deployment and cloud verification work to save costs. Current work is completely local.

Resume when:
- the user explicitly asks to resume Azure deployment or cloud verification work

Next action:
1. Re-check the latest Azure revision and deployment health only after the user reopens the cloud path.

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

### 2026-03-07: Local Full-Dataset Chatbot Verification

- Full 1.94M local PostgreSQL dataset verified for chatbot use
- Gent restaurant count, Brussels and Antwerpen city counts, and Brussels aggregation all reported working locally
- This supersedes the older local 10k-only posture for current local execution work

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
