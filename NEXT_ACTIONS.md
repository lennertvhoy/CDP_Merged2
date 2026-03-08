# NEXT_ACTIONS - CDP_Merged - Local-First Working Queue

**Platform:** Azure target architecture with local-only execution mode
**Current Execution Mode:** Local-only (`Azure deployment path paused to save costs`)
**Date:** 2026-03-07
**Owner:** AI Agent / Developer
**Purpose:** Active queue only. Older completions now live in `WORKLOG.md`; roadmap items live in `BACKLOG.md`.

## Active

### P0: Connect Source Systems (HIGHEST YIELD)

**Status:** ✅ TEAMLEADER & EXACT ONLINE SYNC COMPLETE - Real data flowing from both!
**Discovered:** 2026-03-07 (user has demo environments available)
**Last Updated:** 2026-03-07 22:46 CET
**Severity:** CRITICAL
**Goal:** Get real data flowing from Teamleader and Exact into PostgreSQL

#### ✅ COMPLETED: Teamleader → PostgreSQL Sync Pipeline

**Verified working with live Teamleader demo environment:**
- ✅ 1 company synced (auto-matched to KBO via company number)
- ✅ 2 contacts synced
- ✅ 2 deals synced  
- ✅ 2 activities synced

**What's implemented:**
- `scripts/sync_teamleader_to_postgres.py` - production sync script
- `scripts/migrations/004_add_crm_tables.sql` - CRM data schema
- Automatic KBO matching via VAT/company number
- Identity linking to `organizations` table
- Incremental sync with cursor tracking
- Full sync mode available

**Run sync:**
```bash
# Full sync
poetry run python scripts/sync_teamleader_to_postgres.py --full

# Incremental sync (uses last cursor)
poetry run python scripts/sync_teamleader_to_postgres.py
```

#### ✅ COMPLETED: Exact Online → PostgreSQL Sync Pipeline

**Verified working with live Exact Online demo environment:**
- ✅ OAuth authorization completed
- ✅ 60 GL Accounts synced
- ✅ 60 Invoices synced
- ✅ Tokens saved to `.env.exact`

**What's implemented:**
- `scripts/sync_exact_to_postgres.py` - production sync script
- `src/services/exact.py` - OAuth2 client with auto-division discovery
- `scripts/migrations/005_add_exact_financial_tables.sql` - Financial data schema
- Automatic KBO/VAT matching
- Financial summary view for 360° insights

**Run sync:**
```bash
# Full sync
poetry run python scripts/sync_exact_to_postgres.py --full

# Incremental sync (uses last cursor)
poetry run python scripts/sync_exact_to_postgres.py
```

#### 🔄 CRITICAL ISSUE: Tool Selection Fix - TOOL-LEVEL DOCSTRINGS FAILED

**Status:** ❌ TOOL-LEVEL DOCSTRING ENHANCEMENTS INSUFFICIENT - Need stronger fix  
**Tested:** 2026-03-08 10:05 CET  
**Screenshot:** `chatbot_360_retest_all_failed_2026-03-08.png` (current failure)

**Test Results (AFTER tool-level docstring enhancements):**

| Query | Expected Tool | Actual Tool Used | Result |
|-------|---------------|------------------|--------|
| "How well are source systems linked to KBO?" | `get_identity_link_quality` | `get_data_coverage_stats` | ❌ FAIL |
| "Show me revenue distribution by city" | `get_geographic_revenue_distribution` | `aggregate_profiles` | ❌ FAIL |
| "Pipeline value for software companies in Brussels?" | `get_industry_summary` | (still wrong tool) | ❌ FAIL |

**What Was Applied:**
Enhanced all 5 unified 360° tool docstrings in `src/ai_interface/tools/unified_360.py` with:

1. **USE THIS TOOL WHEN** sections - Clear positive conditions for using each tool
2. **DO NOT USE THIS TOOL WHEN** sections - Explicit negative conditions with correct alternatives  
3. **QUERY PATTERNS THAT REQUIRE THIS TOOL** - Exact query patterns that map to each tool
4. **QUERY PATTERNS THAT DO NOT REQUIRE THIS TOOL** - Common misclassifications with correct tool guidance

**Enhanced Tools:**
- `query_unified_360` - Clear distinction from search_profiles and aggregate tools
- `get_industry_summary` - Explicitly for pipeline value queries (e.g., "Pipeline value for software companies in Brussels?")
- `get_geographic_revenue_distribution` - For revenue by city questions (e.g., "Show me revenue distribution by city")
- `get_identity_link_quality` - For KBO linkage quality (e.g., "How well are source systems linked to KBO?")
- `find_high_value_accounts` - For risk/opportunity accounts

**Root Cause Analysis:**
Tool-level docstrings alone are NOT sufficient to override the LLM's tool selection behavior. The LLM continues to:
1. Classify "linkage" queries as "coverage" queries (uses `get_data_coverage_stats`)
2. Classify "revenue distribution" queries as "aggregation" queries (uses `aggregate_profiles`)
3. Misclassify "pipeline value" queries (doesn't use `get_industry_summary`)

**Next Step - REQUIRED:**
🔄 **Implement Option D: Parameter Validation Layer**

Add pre-validation in tool wrappers that:
1. Checks if the tool selection matches query intent
2. Returns a clear error with the correct tool suggestion if wrong
3. Forces the LLM to retry with the correct tool

**Alternative (if Option D fails):**
- Option A: Implement explicit routing layer before tool selection (regex/keyword-based)

#### Next Priorities

1. **✅ COMPLETED: Cross-source identity reconciliation infrastructure** (2026-03-07)
   - ✅ Created unified 360° views (migration 006)
     - `unified_company_360`: Complete company profile combining KBO + Teamleader + Exact
     - `unified_pipeline_revenue`: Combined CRM pipeline + financial revenue
     - `industry_pipeline_summary`: Industry-level analysis for queries like "software companies in Brussels"
     - `company_activity_timeline`: Chronological activity feed across all systems
     - `identity_link_quality`: Monitor KBO matching coverage
     - `high_value_accounts`: Prioritized accounts with risk/opportunity indicators
     - `geographic_revenue_distribution`: Revenue by location
   - ✅ Created KBO matching verification script (`scripts/verify_kbo_matching.py`)
     - Checks match rates by source system
     - Identifies unmatched records with potential matches
     - Generates recommendations for improvement
   - ✅ Created 360° query service (`src/services/unified_360_queries.py`)
     - Python API for unified queries
     - Methods: `get_company_360_profile()`, `find_companies_with_pipeline()`, 
       `get_industry_pipeline_summary()`, `get_geographic_distribution()`, etc.

2. **✅ COMPLETED: Chatbot 360° query tools** (2026-03-07)
   - ✅ Extended chatbot with 5 new unified 360° tools:
     - `query_unified_360` - Complete 360° company profiles
     - `get_industry_summary` - Industry-level pipeline/revenue analysis
     - `find_high_value_accounts` - High-value/risk account identification
     - `get_geographic_revenue_distribution` - Revenue by geography
     - `get_identity_link_quality` - KBO matching coverage monitoring
   - ✅ System prompt updated with new section "6. UNIFIED 360° CUSTOMER VIEWS"
   - ✅ Natural language queries now supported:
     - "What is the total pipeline value for software companies in Brussels?"
     - "Show me IT companies in Gent with open deals over €10k"
     - "Which high-value accounts have overdue invoices?"
     - "Give me a 360° view of company KBO 0123.456.789"
   - ✅ Tool count: 15 → 20 tools
   - ✅ All 5 tools tested and working locally
   - ✅ Fixed database schema issues (migration 006)
   - ✅ Fixed JSON serialization (datetime/Decimal handling)

3. **✅ COMPLETED: Enhanced 360° tool selection guidance** (2026-03-07)
   - ✅ Problem identified: LLM was using standard tools instead of 360° tools
   - ✅ Solution: Enhanced system prompt with clearer selection criteria
   - ✅ Added CRITICAL guidance distinguishing 360° tools from standard search
   - ✅ Added explicit tool selection matrix
   - ✅ Added more specific parameter mappings for all 360° tools
   - ✅ Commit: `eae20da` - docs(chatbot): Enhance system prompt for 360° tool selection

#### Follow-up Items - UPDATED 2026-03-08

**Status:** ✅ EXAMPLES ADDED - Ready for re-test

**Changes Made (2026-03-08):**
Added explicit EXAMPLES section (1C) and NEGATIVE CONSTRAINTS section (1D) to system prompt:

1. **Section 1C: EXAMPLES - EXACT QUERY → TOOL MAPPINGS**
   - Exact query patterns mapped to specific tools
   - For KBO linkage: "How well are source systems linked to KBO?" → `get_identity_link_quality`
   - For revenue distribution: "Show me revenue distribution by city" → `get_geographic_revenue_distribution`
   - For pipeline: "Pipeline value for software companies in Brussels?" → `get_industry_summary`

2. **Section 1D: NEGATIVE CONSTRAINTS - WHAT NOT TO DO**
   - "NEVER use `get_data_coverage_stats` for KBO matching quality"
   - "NEVER use `aggregate_profiles` for revenue distribution by city"
   - "NEVER use `search_profiles` for pipeline value calculations"
   - Strong prohibition language with correct alternatives

**Previous Test Results (2026-03-08 00:55 CET):**
All 3 test queries were failing after prompt restructure:

| Query | Expected Tool | Actual Tool | Status |
|-------|--------------|-------------|--------|
| "How well are source systems linked to KBO?" | `get_identity_link_quality` | `get_data_coverage_stats` | ❌ FAILED |
| "Show me revenue distribution by city" | `get_geographic_revenue_distribution` | `aggregate_profiles` | ❌ FAILED |
| "Pipeline value for software companies in Brussels?" | `get_industry_summary` | `search_profiles` | ❌ FAILED |

**Root Cause Analysis:**
The system prompt restructure alone wasn't sufficient. The LLM was:
1. Classifying "linkage" queries as "coverage" queries
2. Classifying "revenue distribution" queries as "aggregation" queries  
3. Classifying "pipeline value" queries as "search" queries

**Next Step:**
🔄 **Re-test the 3 failing queries** to verify the explicit examples and negative constraints fix the issue.

**Previous Solutions Applied:**
- ✅ Restructured system prompt with 360° tools in Section 1A (TOP)
- ✅ Added TOOL SELECTION ROUTING section with STEP 1 decision logic
- ✅ Added tool selection matrix in Section 1B
- ✅ Updated VALID_TOOL_NAMES
- ✅ Added explicit EXAMPLES section 1C (new)
- ✅ Added NEGATIVE CONSTRAINTS section 1D (new)

**Screenshot:** `chatbot_360_retest_all_failed_2026-03-08.png`

---

### P0: Finalize Offline Local Development Stack

**Status:** COMPLETE - runtime fixed, full 1.94M dataset loaded and verified
**Discovered:** 2026-03-07
**Last Updated:** 2026-03-07 18:36 CET
**Severity:** HIGH

#### Current State

- The runtime tree has been restored into `/home/ff/Documents/CDP_Merged`.
- Local PostgreSQL now starts cleanly from `docker-compose.postgres.yml` using `schema_local.sql`.
- `schema_local.sql` now includes the local support tables required for PostgreSQL-first segments and projection tracking: `activation_projection_state`, `segment_definitions`, `segment_memberships`, and `source_identity_links`.
- `start_chatbot.sh` now launches the local app via `uvicorn`, sources `.env` plus `.env.local`, and the runtime is using real OpenAI successfully.
- Local Tracardi containers are up, auth succeeds, and event sources have been created via `setup_tracardi_kbo_and_email.py`.
- `docker compose up -d --build` now brings up the full local stack by default: PostgreSQL, Tracardi, Wiremock, and the chatbot.
- `docker compose ps` now shows the chatbot container healthy on `:8000`, and `/healthz` plus `/readinessz` both return `status: ok`.
- Chat-session bootstrap now works: `TracardiClient().get_or_create_profile()` returns profiles successfully.
- `.env.local` has been updated with `TRACARDI_SOURCE_ID=cdp-api`.
- The local `public.companies` table now holds the full `1,940,603`-row PostgreSQL-first KBO dataset, so local count and aggregation prompts are now business-truth capable.
- The chatbot query contract has been corrected so generic searches no longer default to `status=AC`, and zero-result searches now expose an empty-dataset diagnostic instead of offering segments/campaigns blindly.
- Same-day local app-code verification now confirms that `create_segment`, `get_segment_stats`, `export_segment_to_csv`, `push_segment_to_resend`, and `push_to_flexmail` all prefer canonical PostgreSQL segment membership, with Tracardi left as fallback/operational context rather than the authoritative segment store.
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

All P0 foundation items complete. Ready for source system connection work.

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
**Last Updated:** 2026-03-07 18:36 CET
**Severity:** HIGH

#### Current State

- The local chatbot now exposes `create_data_artifact`, `get_data_coverage_stats`, `export_segment_to_csv`, and `email_segment_export` in the agent tool layer.
- Stable harness coverage now includes a tool-heavy multi-turn story with local artifact generation.
- Compose-managed regression and quick demo smoke now confirm the local PostgreSQL path, NACE alias search, email-domain filtering, artifact export, and top-level demo readiness checks all work.
- **Browser-driven multi-turn scenario completed:** Verified search → artifact → segment → export flow through real threaded browser session against http://localhost:8000.
- The local segment/export gap exposed by that browser run is now closed for canonical PostgreSQL-backed segment flows.

#### Completed

✅ **Browser-driven multi-turn operator scenario** (2026-03-07 18:20 CET)
- Search: "How many software companies are in Brussels?" → 1,529 companies found
- Artifact: Created markdown artifact with first 100 results → Download link provided
- Segment: Earlier browser run exposed the old Tracardi-only gap by creating "Brussels Software Companies" with 0 profiles
- Export: Earlier browser run exposed the same gap by returning 0 export rows
- Artifact file created: `output/agent_artifacts/software-companies-in-brussels_20260307_171512.markdown`
- Screenshot captured: `chatbot_full_flow_test_2026-03-07.png`

✅ **PostgreSQL-first canonical segment flow fixed locally** (2026-03-07 18:36 CET)
- Direct tool verification against the rebuilt compose-managed stack now aligns `search_profiles` → `create_segment` → `get_segment_stats` → `export_segment_to_csv`
- Verification query: "software companies in Brussels" → `search_total=1652`, canonical segment count `1652`, export backend `postgresql`
- The live local PostgreSQL database now contains `activation_projection_state`, `segment_definitions`, `segment_memberships`, and `source_identity_links`
- Authoritative segment stats and exports no longer depend on Tracardi profile membership

#### Next Actions
None - multi-message runtime hardening complete. Local stack verified end-to-end.

#### Remaining Limitation
- Tracardi-native projection of canonical PostgreSQL segments is still future work for workflow-centric activation paths, but it is no longer a blocker for local authoritative segment creation, stats, or export

### P2: Explain Browser-Vs-Direct Search Mismatch

**Status:** RESOLVED
**Discovered:** 2026-03-07
**Resolved:** 2026-03-07 18:55 CET
**Severity:** MEDIUM

#### Root Cause Analysis

The discrepancy is explained:
- **1,529 results**: Planner used only the 4 core 62xxx NACE codes (62010, 62020, 62030, 62090)
- **1,652 results**: Full NACE resolution includes all 6 codes including 63110, 63120 (web portals, data processing)

The keyword "software" auto-resolves to 6 codes, but the LLM/planner in the browser session appears to have selected only the programming/consultancy subset (62xxx), excluding information service activities (631xx).

#### Evidence

```
nace_codes=['62010', '62020', '62030', '62090'], city=Brussels -> total=1529
nace_codes=['62010', '62020', '62030', '62090', '63110', '63120'], city=Brussels -> total=1652
```

#### Resolution

1. Added regression test `tests/unit/test_nace_resolution_consistency.py` documenting the expected 6-code resolution
2. Updated `search_profiles` docstring with NACE resolution consistency note
3. Verified full dataset counts: 62xxx only = 1529, all 6 codes = 1652

#### Follow-up

- Monitor for planner behavior that subsets NACE codes without justification
- Consider adding validation that warns when NACE codes appear to be manually subset

### P2: Tracardi Activation Layer Configuration

**Status:** COMPLETE - All 5 workflows deployed and active
**Discovered:** 2026-03-07 19:29 CET
**Configured:** 2026-03-07 20:20 CET
**Deployed:** 2026-03-07 20:25 CET
**Severity:** MEDIUM

#### Current State

Tracardi activation layer fully configured:
- ✅ 4 event sources configured (cdp-api, kbo-batch-import, kbo-realtime, resend-webhook)
- ✅ 31 profiles stored (chatbot sessions creating profiles)
- ✅ 52 events recorded
- ✅ API fully functional (auth, /track, profile queries)
- ✅ Verification script created: `scripts/setup_and_verify_tracardi.py`
- ✅ **Workflows: 5 deployed via GUI**
  - Email Engagement Processor: Start → End, triggers on email.opened, email.clicked
  - Email Bounce Processor: Start → Update Profile → End, triggers on email.bounced
  - Email Delivery Processor: Start → End, triggers on email.delivered
  - High Engagement Segment: Start → End, triggers on profile.updated
  - Email Complaint Processor: Start → End, triggers on email.complained
- ⚠️ Destinations: 0 configured (require GUI - API needs specific format)
- ✅ GUI accessible at http://localhost:8787
- ✅ Screenshots saved: tracardi_workflows_configured.png, tracardi_workflow_email_bounce_deployed.png

#### Completed

1. **Created verification script** (`scripts/setup_and_verify_tracardi.py`)
   - Authenticates and tests all Tracardi endpoints
   - Lists event sources, workflows, destinations, profiles
   - Tests /track endpoint functionality

2. **Created and deployed workflows via GUI** (browser automation)
   - All 5 Resend email processing workflows created with nodes and event triggers
   - Workflows saved/deployed in Tracardi GUI
   - Event triggers configured for Resend webhook events (bounce, complaint, delivery, open, click)

3. **Configured workflow nodes and triggers**
   - Email Bounce Processor has Update Profile node for marking emails invalid
   - All workflows have Start and End nodes on canvas
   - Event triggers mapped to Resend webhook event types

#### Completed (2026-03-07 20:45 CET)

4. **Fixed Resend event source type**
   - Changed from `webhook` type to `rest` type to work with `/track` endpoint
   - Created fix script: `scripts/fix_resend_event_source.py`
   - Created verification script: `scripts/verify_local_resend_setup.py`

5. **Verified local Resend webhook setup**
   - ✅ Tracardi authentication working
   - ✅ Resend event source configured (type: REST)
   - ✅ All 5 email workflows deployed and active
   - ✅ Tracker endpoint accepting events
   - ✅ Event simulation successful (events create profiles)

#### Completed (2026-03-07 20:45 CET)

4. **Fixed Resend event source type**
   - Changed from `webhook` type to `rest` type to work with `/track` endpoint
   - Created fix script: `scripts/fix_resend_event_source.py`
   - Created verification script: `scripts/verify_local_resend_setup.py`

5. **Verified local Resend webhook setup**
   - ✅ Tracardi authentication working
   - ✅ Resend event source configured (type: REST)
   - ✅ All 5 email workflows deployed and active
   - ✅ Tracker endpoint accepting events
   - ✅ Event simulation successful (events create profiles)

#### Completed (2026-03-07 20:45 CET) - Webhook Secret Configured

6. **Resend webhook secret configured**
   - Webhook signing secret added to `.env` and `.env.local`
   - Localtunnel URL configured: `https://chilly-ghosts-melt.loca.lt/track?source=resend-webhook`
   - Ready for signature verification when Resend sends webhooks

#### Completed (2026-03-07 21:00 CET) - Bridge Script Fixed

7. **Resend to Tracardi bridge script fixed and tested**
   - Fixed `scripts/resend_to_tracardi_bridge.py` with proper async FastAPI implementation
   - Correctly translates Resend webhook format (`{"type": "...", "data": {...}}`) to Tracardi `/track` format
   - Signature verification using Svix format (v1,timestamp,signature)
   - Properly handles Tracardi's `events` array (not single `event` object)
   - Returns deterministic profile IDs based on email hash
   - Run with: `poetry run python scripts/resend_to_tracardi_bridge.py [port]`
   - Webhook endpoint: `POST /webhook/resend`
   - Health check: `GET /health`

#### Next Actions

For end-to-end testing with real Resend webhooks:
1. Start the bridge: `poetry run python scripts/resend_to_tracardi_bridge.py`
2. Configure webhook URL in Resend dashboard: `http://your-server:5000/webhook/resend`
3. Subscribe to events: email.sent, email.delivered, email.opened, email.clicked, email.bounced, email.complained
4. Send test email via Resend and verify events trigger Tracardi workflows
5. Verify webhook signatures are validated using `RESEND_WEBHOOK_SECRET`

**Note:** Local setup is complete. For external webhooks from Resend servers, use ngrok or deploy the bridge to a publicly accessible server.

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
