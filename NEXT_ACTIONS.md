# NEXT_ACTIONS - CDP_Merged - Local-First Working Queue

**Platform:** Azure target architecture with local-only execution mode
**Current Execution Mode:** Local-only (`Azure deployment path paused to save costs`)
**Date:** 2026-03-10
**Owner:** AI Agent / Developer
**Purpose:** Active queue only. Older completions now live in `WORKLOG.md`; roadmap items live in `BACKLOG.md`.
**Canonical Counts:** `total=1,940,603; website_url=70,922; geo_latitude=63,979; ai_description=31,033; cbe_enriched=1,252,019`

## Active

## CHAINLIT DEPRECATION (2026-03-14)

**COMPLETED:** Chainlit has been removed from the active runtime.

- [x] Stop and disable cdp-chatbot.service
- [x] Stop and remove docker container cdp_merged_agent  
- [x] Archive cdp-chatbot.service to deprecated/
- [x] Remove agent service from docker-compose.yml
- [x] Deprecate start_chatbot.sh
- [x] Update next.config.ts (remove port 8000 references)
- [x] Update STATUS.md, PROJECT_STATE.yaml, NEXT_ACTIONS.md

**Remaining Chainlit references (historical only):**
- `src/app.py` - Chainlit code kept for reference (not executed)
- `.chainlit/` - Config and translations kept for reference
- `tests/unit/test_app.py` - Tests use Chainlit test harness

Dependency-manager note: `uv` migration plus the follow-on GitHub CI repair are complete as of 2026-03-10 17:50 CET. Commit `7e6c432` is green on run `22913778035`; the first red uv push (`1978e31`) and the intermediate partial repair (`fb85742`) are now superseded history, not active queue items.

### P0: Architecture Hardening - Tracardi Optionalization

**Status:** IMPLEMENTATION IN PROGRESS — Docker compose opt-in complete; docs update complete; remaining: PROJECT_STATE.yaml, event processor verification, CI/CD posture
**Discovered:** 2026-03-14 via architecture review
**Last Updated:** 2026-03-14 11:32 CET
**Severity:** HIGH
**Goal:** Formalize Tracardi demotion from core dependency to optional activation adapter.

#### Decisions Recorded
- Tracardi is no longer a core dependency for CDP_Merged
- Authoritative demo/runtime path is PostgreSQL + first-party operator shell + first-party event/writeback logic
- Tracardi CE limitations are reclassified as optional-platform limitation, not core delivery blocker

#### Required Actions
1. ✅ Update all documentation to describe Tracardi as optional (not core) — COMPLETED 2026-03-14
2. ✅ Remove Tracardi from default local stack (docker-compose) - make it opt-in — COMPLETED 2026-03-14
3. Document decision in PROJECT_STATE.yaml architecture section — PENDING
4. Verify first-party event processor covers all critical activation paths — PENDING
5. Decide keep-vs-remove posture for Tracardi in CI/CD and default deployments — PENDING

### ✅ COMPLETE: Operator Shell Admin Panel + Basic Admin Authorization

**Status:** COMPLETE - Admin panel implemented, basic authorization verified
**Discovered:** 2026-03-14 via public ngrok verification
**Completed:** 2026-03-14 12:00 CET
**Severity:** HIGH
**Summary:** |
  Admin panel now live at https://kbocdpagent.ngrok.app/admin
  Basic admin authorization (boolean is_admin) implemented
  NOT full RBAC - only admin/user distinction exists

#### Verified State
- Public admin URL: `https://kbocdpagent.ngrok.app/admin` (200 OK)
- `/admin` page shows user list for admins, 403-style error for non-admins
- `/operator-api/admin/users` - server-side protected (401/403)
- `/operator-api/admin/me` - returns current user's admin status
- `is_admin` exposed in bootstrap payload at `session.user.is_admin`
- Admin shield icon appears in sidebar for admin users

#### Authorization Model
- **Type:** Basic admin authorization (NOT RBAC)
- **Mechanism:** Boolean `is_admin` flag in PostgreSQL `app_auth_local_accounts` table
- **Enforcement:** Server-side API checks + client-side UI adaptation
- **Limitations:** No roles, no permissions, no multi-role system
- **Current admin:** lennertvhoy@gmail.com

#### Files Modified
- `src/services/operator_bridge.py` - expose is_admin in bootstrap
- `src/config.py` - add CHAINLIT_LOCAL_ACCOUNT_AUTH_ENABLED setting
- `src/operator_api.py` - add /admin/users and /admin/me endpoints
- `apps/operator-shell/lib/types/operator.ts` - add is_admin to types
- `apps/operator-shell/components/sidebar.tsx` - add Admin shield link
- `apps/operator-shell/components/operator-shell-app.tsx` - pass isAdmin prop
- `apps/operator-shell/app/admin/page.tsx` - new admin page component

### P0: Enrichment Coverage And Optimization

**Status:** ACTIVE
**Discovered:** 2026-03-09 via direct user instruction, with live runner recheck the same session
**Last Updated:** 2026-03-09 23:20 CET
**Severity:** CRITICAL
**Goal:** Make enrichment the top operational priority and ensure the background enrichment setup is both effective and aligned with the current cost/privacy direction.

#### Current Observed State

- Fresh PostgreSQL counts at `2026-03-09 23:19 CET`: `website_url=70,922`, `geo_latitude=63,979`, `ai_description=31,033`, `cbe_enriched=1,252,019`.
- `CBE` completed successfully on `2026-03-08 15:07 CET`.
- `geocoding` is repo-supervised and still active, and the live observability patch remains verified. After the old pre-patch batch worker was force-stopped at `2026-03-09 18:25 CET`, the existing bash supervisor relaunched the observability-fixed chunked parent at `18:25:28 CET` and a new batch child at `18:25:29 CET`. That pre-fix child finished `Batch 20/20` at `21:39:54 CET`, then the follow-on child PID `3236076` launched immediately from cursor `1366466e-b3d5-4d7f-8cfd-ab91e7c9b503`, which is after commit `5bf2595` (`18:33:29 CET`). Precise post-launch log checks through `22:55 CET` showed Batches `1/20` through `5/20` complete at `21:52:17`, `22:04:45`, `22:17:05`, `22:29:13`, and `22:41:25 CET`; the latest short recheck still showed fresh geocoded rows through `23:19 CET` with no new nullable-trait `strip()` failures after the already-known `21:27 CET` lines. Keep geocoding on normal background monitoring unless that error signature or throughput regresses.
- `website discovery` is still active; the latest completed chunks ended at `2026-03-09 23:10:35 CET` (`57` discoveries), `23:13:42 CET` (`64` discoveries), `23:16:24 CET` (`53` discoveries), and `23:19:39 CET` (`56` discoveries), and the cursor advanced again at `23:19:39 CET` to `1483b6a4-e256-45ba-89f1-785cb79e497b`.
- `description_ollama` was started at `2026-03-09 17:26 CET`; it has now completed twenty-nine 1000-row chunks, most recently at `22:55:59 CET` (`622` descriptions), `23:02:55 CET` (`645` descriptions), `23:09:47 CET` (`660` descriptions), and `23:16:27 CET` (`648` descriptions). Canonical `ai_description` rose from `706` pre-launch to `31,033`, with `6,058` descriptions generated in the last `5` minutes and a thirtieth batch already active from cursor `064ec0ac-100d-4d70-9461-b7722608b68b`. Recent completed chunks are still holding roughly `2.4-2.6/s`, so there is still no tuning trigger for the current `CHUNK_SIZE=1000` / `BATCH_SIZE=20` settings.

#### Accepted Decisions

- Enrichment is now the top priority.
- AI descriptions should be generated with `Ollama`, not Azure OpenAI.
- The next AI-description work should optimize coverage and restartability, not reopen Azure cost.

#### Next action

1. Keep geocoding on routine background monitoring now that the first post-`5bf2595` chunk is clean; only reopen chunk-size or error investigation if fresh `NoneType`/`strip()` lines reappear or throughput materially changes.
2. Keep `description_ollama` at `CHUNK_SIZE=1000` / `BATCH_SIZE=20` for now; recent completed chunks are still holding roughly `2.2-2.4/s`, so only revisit tuning if throughput regresses or restartability worsens.
3. Keep website discovery monitored from PostgreSQL counts plus chunk logs, not just the supervisor process list.

### P0: Demo Polish And Source-Of-Truth Hardening

**Status:** ✅ COMPLETE v3.0; v3.2 local polish pass exported and positively reviewed. Remaining work is still the focused v3.3 credibility pass, but the immediate session-level follow-up is paused after the user redirected work to another backlog item on 2026-03-09 23:38 CET.
**Discovered:** 2026-03-08 (initial audit), reopened 2026-03-08 via direct user feedback and source-of-truth review
**Last Updated:** 2026-03-09 23:38 CET
**Severity:** HIGH
**Guide:** `docs/ILLUSTRATED_GUIDE.md` / `docs/illustrated_guide/ILLUSTRATED_GUIDE.pdf` local export
**User Feedback:** v3.2 is the best version so far: good as an illustrated evidence guide, credible but not perfect as a source-of-truth support document, and aligned with the core CDP+AI POC slice. The main remaining blockers are mixed-year timestamps, one screenshot/prose naming mismatch, still-flat API/code pages, PDF text-layer/export quality, and the lack of a reviewer-friendly conformity matrix for the business-case acceptance criteria.

**Session Note:** 2026-03-09 23:38 CET the user redirected the immediate work away from the v3.3 guide pass and onto another backlog item. Keep the remaining guide gaps unchanged until the current operator-eval harness increment is recorded.

#### Accepted Decisions

- `Resend` is acceptable for the current POC. Do **not** treat the Flexmail swap as a blocker unless the user explicitly reopens it.
- Keep the local-only demo posture explicit. Do **not** reopen Azure deployment work just to improve the guide package.
- Keep the guide framed as evidence for the core POC/business-case slice, not as proof that the full future-state multi-channel business case is already demonstrated.

#### What the current guide already proves

| Evidence | Status | Limitation |
|----------|--------|------------|
| B.B.S. Entreprise single-story proof | Verified | The same B.B.S. record is now tied across the `linked_all` 360 proof, event-processor outputs, populated Resend audience context, and demo-labeled website behavior in canonical `event_facts` |
| Privacy architecture honesty | Verified | The guide now explicitly documents the current divergence: anonymous Tracardi profiles, but email-bearing event metadata still exists |
| NL segment creation and scope framing | Verified | The guide now labels `1,652` canonical scope, `1,529` narrower activation-test scope, `190` Brussels IT rows, `189` unique Resend contacts, and `101` CSV preview rows |
| Resend activation proof | Verified | Live populated audience proof exists, and the guide now captions the reused `KBO Companies - Test Audience` label explicitly as the Brussels IT subset evidence |
| Event processor / NBA outputs | Verified | Live JSON evidence exists for B.B.S. support-expansion + re-activation and Accountantskantoor Dubois cross-sell + multi-division; remaining work is visual polish rather than missing logic explanation |
| Website behavior writeback | Verified | A demo-labeled local website session for the real B.B.S. UID now records `2` `page.view` events and `1` `goal.achieved` download in canonical `event_facts` |
| CSV export artifact | Verified | The page is now self-contained, and the guide now records the artifact checksum plus file timestamp; query-ID proof is still not persisted by the export flow |
| Business-case conformity | Verified for core POC slice | The guide does not yet prove the full future-state scope around live website analytics, ads/social, group-wide web tracking, or formal governance criteria |

#### Remaining Polish Work

| Gap | Priority | Status |
|-----|----------|--------|
| Split the project docs into business case / system spec / illustrated evidence guide | HIGH | ✅ COMPLETE - Split into BUSINESS_CASE.md, SYSTEM_SPEC.md, and streamlined ILLUSTRATED_GUIDE.md |
| Clarify reused Resend audience naming/captioning | HIGH | ✅ COMPLETE - the guide now frames `KBO Companies - Test Audience` explicitly as the reused UI label for the Brussels IT subset proof |
| Clarify Autotask wording as `hybrid` | HIGH | ✅ COMPLETE - Both BUSINESS_CASE.md and ILLUSTRATED_GUIDE.md now document hybrid status (prod-ready linkage, demo data) |
| Surface NBA scoring weights and thresholds | HIGH | ✅ COMPLETE - Full scoring model JSON documented in ILLUSTRATED_GUIDE.md with event weights, thresholds, and calculation example |
| Add explicit cross-division revenue aggregation proof | HIGH | ✅ COMPLETE - B.B.S. Entreprise cross-source aggregation captured (€15,000 total) with timestamp 2026-03-08 22:24 CET |
| Capture timestamped sync-latency proof | HIGH | ✅ COMPLETE - Sync timestamps documented: Teamleader 2026-03-08 14:57:55, Exact 2026-03-08 11:19:39 |
| Harden privacy boundary in runtime | MEDIUM | ✅ COMPLETE - 48 webhook gateway tests pass, PII stripping verified, guide updated with verification note |
| Recheck the late-suite webhook/event-processor test timeout | MEDIUM | ✅ COMPLETE - Both test suites now pass cleanly (54 tests in 0.33s). Issue resolved, likely by commit f9d1906. |

#### v3.3 Credibility Pass

Per the latest v3.2 review:

**Precision Improvements:**
| Gap | Priority | Status |
|-----|----------|--------|
| Fix guide timestamp consistency | P0 | ✅ COMPLETE - event-processor examples now use the observed 2026-03-09 local payloads instead of stale `2024-03-08` placeholders |
| Add canonical count semantics dictionary | P1 | ✅ COMPLETE - the guide now explicitly defines `1,652`, `1,529`, `190`, `189`, and `101` by scope |
| Upgrade CSV export integrity proof | P1 | Partial - checksum and file timestamp are now documented; query-ID proof is still pending because the current export flow does not persist one |
| Implement maturity label system and tighten Autotask wording | P1 | Partial - guide now labels `Live system`, `Local runtime`, `Demo-backed`, and `Local artifact`, but the full system is not yet applied everywhere and `production-ready` still reads too strongly beside `Demo-backed` |
| Fix privacy statement wording precision | P2 | ✅ COMPLETE - top-line privacy wording now matches the divergence table and no longer implies a fully sanitized runtime |
| Re-sync local event-processor daemon with checked-in routes | P1 | ✅ COMPLETE - refreshed the local daemon from current checked-in code; `127.0.0.1:5001/api/scoring-model` now returns `200` and the root endpoint advertises the route live |

**Business-case / Governance Improvements:**
| Gap | Priority | Status |
|-----|----------|--------|
| Publish business-case conformity matrix | P1 | Pending - map `BUSINESS_CASE.md` requirements to current guide/spec evidence as `Conforms`, `Partial`, or `Not yet covered` |
| Add acceptance-criteria appendix | P1 | Pending - surface the `>=95%` prompt/tool-selection proof, audit-log/API-call control evidence, and deploy/IaC repeatability evidence or explicitly mark the current gaps |

**Formatting / Export Improvements:**
| Gap | Priority | Status |
|-----|----------|--------|
| Align screenshot-visible audience naming with prose | P1 | ✅ COMPLETE - the guide now explicitly presents `KBO Companies - Test Audience` as the reused historical UI label for the Brussels IT subset proof |
| Standardize phase page pattern | P1 | Partial - early sections now follow claim → evidence → verification more cleanly, but the full guide is not yet standardized |
| Shaded code boxes for API/JSON | P1 | Pending - pages 8-11 still read like raw request/response dumps instead of designed evidence boxes |
| Keep page 6 audience note on one page | P2 | Pending - the renamed-for-clarity note currently wraps awkwardly across the page break |
| Keep the privacy divergence table and mitigation note together | P2 | Pending - the current split across pages 10-11 hurts readability |
| Improve page economy / oversized screenshots | P2 | Pending - pages 12 and 14 still use more space than the content justifies |
| Fix PDF text-layer/export quality | P0 | Pending - extracted text still shows `ffi`/broken-word artifacts that hurt searchability and accessibility |
| Standardize visual hierarchy | P2 | Partial - screenshot sizing and source labels are more controlled, but caption spacing and page rhythm still need a final pass |

#### Exit Criteria

- [x] Record that Resend is the accepted current POC activation platform
- [x] Implement Autotask into `unified_company_360` with KBO linking and verify one `linked_all` company
- [x] Explicitly document the current privacy divergence instead of overclaiming a fully UID-only runtime
- [x] Show one account with KBO + Teamleader + Exact + Autotask in the same story
- [x] Resolve the `1,652` / `1,529` / `190` / `189` / `101` count framing in the guide
- [x] Capture cross-sell, multi-division, and Next Best Action output evidence
- [x] Capture identity-resolution and engagement-writeback evidence
- [x] Capture guide-ready event-processor API evidence (live JSON for `/api/next-best-action/0438437723` and `/api/engagement/leads?min_score=5`)
- [x] Capture populated Resend audience proof for the selected Brussels IT subset
- [x] Capture website-behavior evidence tied to the same UID/business-value story
- [x] Clarify Resend audience naming in prose and captions
- [x] Align the visible audience screenshot label with the same Brussels IT naming or explicitly present it as a historical UI label
- [x] Clarify Autotask as hybrid/prod-ready linkage plus demo-mode data
- [x] Split the current guide into business case / system spec / evidence guide
- [x] Surface NBA weights and threshold logic in the guide/spec, using `/api/scoring-model`
- [x] Add explicit cross-division revenue aggregation proof
- [x] Capture one timestamped sync-latency proof
- [x] Recheck the combined webhook/event-processor test hang and capture a clean green run

---

### P1: Hybrid Azure Re-Entry For Auth And LLM

**Status:** IMPLEMENTED - Code complete, exposed secret rotated, login testing still deferred until March 14, 2026
**Discovered:** 2026-03-09 via direct user instruction
**Implemented:** 2026-03-09 22:45 CET
**Severity:** HIGH
**Goal:** When ready for colleague-facing rollout, enable Microsoft Entra ID work-account authentication and optionally use Azure OpenAI for LLM inference. All compute (PostgreSQL, Tracardi, chatbot) remains local.

> **Note:** This work item is for Azure **services** (Entra ID, OpenAI) only, NOT Azure infrastructure deployment. Container Apps and VMs remain disabled.

#### Accepted Decisions

- Do **not** put the project online before Entra auth exists.
- Use colleagues' Microsoft work accounts, not a shared generic login.
- Azure integration is limited to: `Entra auth + Azure OpenAI`.
- All compute infrastructure stays local (PostgreSQL, Tracardi, chatbot via docker-compose).
- Treat the long-term hosting target as the user's server farm, not Azure infrastructure.

#### Implementation Status

**✅ COMPLETE - Infrastructure & Code:**
1. **Azure AD App Registration created:** "CDP Chatbot" (d13725b8-ce4e-4103-9518-2d66bcce5beb)
   - Tenant: ce408fd5-2526-4cbb-bbe6-f0c2e188b89d
   - Redirect URI: http://localhost:8000/auth/oauth/azure-ad/callback
   - Client secret: Rotated `2026-03-09 22:38 CET`; current credential expires `2027-03-09T21:38:52Z`
   
2. **Configuration implemented:**
   - `src/config.py`: AZURE_AD_TENANT_ID, AZURE_AD_CLIENT_ID, AZURE_AD_CLIENT_SECRET, AZURE_AD_REDIRECT_URI, AZURE_AD_ALLOWED_DOMAINS, CHAINLIT_ENABLE_AZURE_AD
   - `src/app.py`: Domain validation in oauth_user_callback, Azure AD metadata capture
   - `.chainlit/config.toml`: OAuth provider configuration template
   - `.env.example`: Configuration templates
   - `scripts/setup_azure_ad_auth.py`: Setup validation script
   - `docs/MICROSOFT_ENTRA_SETUP.md`: Comprehensive documentation

3. **Web Search Policy implemented:**
   - Policy modes: disabled (default), restricted, opt-in, default-on
   - PII pattern blocking (emails, phone numbers)
   - Domain allowlist for restricted mode
   - Audit logging for compliance
   - `src/services/web_search_policy.py` with 14 unit tests

#### Current Configuration (in .env.local)

```bash
# Microsoft Entra ID (Azure AD) OAuth
CHAINLIT_ENABLE_AZURE_AD=false  # Set to true to enable (after March 14)
AZURE_AD_TENANT_ID=ce408fd5-2526-4cbb-bbe6-f0c2e188b89d
AZURE_AD_CLIENT_ID=d13725b8-ce4e-4103-9518-2d66bcce5beb
AZURE_AD_CLIENT_SECRET=<set-in-.env.local-only>
AZURE_AD_REDIRECT_URI=http://localhost:8000/auth/oauth/azure-ad/callback
# AZURE_AD_ALLOWED_DOMAINS=yourcompany.com  # Optional domain restriction

# Web Search Policy
WEB_SEARCH_POLICY=disabled  # Options: disabled, restricted, opt-in, default-on
```

#### Next Action

**⏸️ BLOCKED until March 14, 2026** (reported Azure quota reset date for the combined Entra + Azure OpenAI validation step)

Security follow-up:
1. ✅ COMPLETE - The exposed Azure AD client secret was rotated on `2026-03-09 22:38 CET`, and the replacement is stored only in untracked `.env.local`.
2. ✅ COMPLETE - `scripts/doc_lint.py` now enforces placeholder-only tracked Entra secret examples, and CI runs doc lint for both docs-only and mixed change sets.

When quota resets:
1. Set `CHAINLIT_ENABLE_AZURE_AD=true` in `.env.local`
2. Restart application: `docker compose up -d --build`
3. Test work account login end-to-end
4. Configure `AZURE_AD_ALLOWED_DOMAINS` if domain restriction needed
5. Decide on web search policy (currently disabled for security)

For production server farm deployment:
1. Add production redirect URI to Azure AD app registration
2. Store the active secret in a vault-backed source instead of environment-only storage
3. Enable HTTPS (required by Azure AD)

---

### P1: Multi-User Chat Experience

**Status:** ACTIVE - local persistence foundation and browser continuity verified; rollout still blocked on UX polish, Entra, and web-search policy
**Discovered:** 2026-03-09 via direct user instruction
**Last Updated:** 2026-03-09 21:47 CET
**Severity:** HIGH
**Goal:** Finish the colleague-facing private-workspace path: keep each colleague in a private chat workspace with stored conversations, make resumed threads actually recover prior state, and move the Chainlit interface closer to ChatGPT with better affordances and a deliberate web-search capability.

#### Accepted Decisions

- Each colleague should get their own chatbot view and their own conversation history.
- The product should not rely on a shared or purely thread-ephemeral chat model for colleague testing.
- The current default Chainlit feel is not the desired colleague-facing finish state.
- Web search is desirable, but only with explicit privacy/compliance boundaries.

#### Current Observed State

- `src/services/chainlit_data_layer.py` now provides a repo-owned PostgreSQL Chainlit data layer that persists users, threads, steps, elements, and feedback into `app_chat_*` tables instead of relying on Chainlit's default schema.
- `src/services/chainlit_data_layer.py` now defaults `metadata` and `tags` to `{}` / `[]` for new thread rows and preserves the existing JSON fields on sparse upserts, fixing the browser-discovered `app_chat_threads` NOT NULL failure that previously prevented reopened threads from persisting.
- `src/app.py` now binds workflow state to Chainlit's actual `thread_id` rather than the websocket session id, and `@cl.on_chat_resume` now reinitializes workflow/checkpointer state from stored thread metadata so reopened threads keep a live composer instead of dropping into history-only view.
- `src/app.py` now auto-generates readable thread titles from the first user message (60 char limit with ellipsis truncation) instead of leaving UUID-derived names in the history sidebar; titles update only for empty/UUID-like names to preserve user edits.
- `src/app.py` and `src/config.py` now expose a dev-only password auth mode (`CHAINLIT_DEV_AUTH_ENABLED=true` + shared `CHAINLIT_DEV_AUTH_PASSWORD`) so local history behavior can be verified with authenticated per-user identities before Microsoft Entra is wired in.
- Repo-owned `.chainlit/translations/*.json` overrides were resynced to the installed Chainlit package keys, fixing blank login labels and raw history/search translation keys during the browser walkthrough.
- Startup bootstrap now creates the `app_chat_*` tables through `src/services/runtime_support_schema.py`.
- Fresh localhost verification on `127.0.0.1:8010` confirmed `/auth/config` returns `requireLogin=true` and `passwordAuth=true`, two authenticated users get isolated `/project/threads` results, owner `/project/thread/{thread_id}` fetches return `200`, and cross-user access is rejected with `401`.
- Browser-driven localhost verification confirmed login labels render, history/search labels render, direct `/thread/{thread_id}` reopen keeps the same URL, the reopened thread exposes `#chat-input`, and a follow-up message stays on the same stored thread.
- Repo-owned defaults/examples now use a 32+ character `CHAINLIT_AUTH_SECRET` placeholder, but any existing local `.env.local` still using the old short secret needs rotation before auth testing.
- A low-severity Chainlit `set_chat_profiles` runtime warning still appears in `chainlit/session.py` during browser resume, but it did not block the restored-composer flow.
- The remaining rollout gaps are now primarily auth-facing rather than storage/UX-facing: no verified Microsoft Entra login yet, and no agreed web-search policy exists.

#### Next action

1. ✅ COMPLETE - Auto-generated thread titles from first message implemented; verify with colleague testing if further history UX polish is needed.
2. Implement and verify Microsoft Entra work-account login on top of the now-verified local continuity path.
3. Decide whether web search is opt-in, default-on, or restricted to specific modes, and document the privacy/compliance policy before enabling it.

---

### P1: Operator Eval Harness Automation

**Status:** ACTIVE - run-prep harness now exists; first live baseline scorecard is still pending
**Resumed:** 2026-03-09 23:38 CET
**Last Updated:** 2026-03-09 23:38 CET
**Severity:** HIGH
**Goal:** Turn the self-contained operator eval bank into a repeatable local review workflow with per-run artifacts that can later feed live chatbot scoring.

#### Current Observed State

- `docs/evals/` still defines the canonical prompt standard, starter bank, and scoring template.
- `src/evals/operator_eval_run_prep.py` now builds a timestamped run bundle from `docs/evals/operator_eval_cases.v1.json`.
- `scripts/prepare_operator_eval_run.py` now emits `manifest.json`, `cases.json`, `scorecard.csv`, and `prompts.md` under `output/operator_eval_runs/<run_id>/`.
- `tests/unit/test_operator_eval_run_prep.py` plus the existing asset test now verify case filtering, artifact shape, and scorecard prefill behavior (`5 passed` total).
- A smoke run already emitted a single-case copy-UX bundle under `/tmp/operator_eval_runs_smoke/operator-eval-20260309t223725z`.

#### Next action

1. Use the new run-prep harness to create the first full baseline bundle against the current local chatbot revision and fill the scorecard with answer-first, tool-leakage, copy, and export observations.
2. Decide whether that baseline should be captured through the live localhost UI, a direct local conversation driver, or both, then codify the chosen execution path.

---

### P0: POC Resend Activation Tests (RECOMMENDED)

**Status:** ✅ COMPLETE - All 6 tests passing, accepted as the current POC activation path
**Discovered:** 2026-03-08
**Last Updated:** 2026-03-08 16:52 CET
**Severity:** CRITICAL

#### Current State

All Resend activation tests are now passing. The user accepted Resend as the current POC platform, so Flexmail parity is not a blocker in the active queue. Resend has:
- ✅ Full webhook management API (create/update/delete)
- ✅ Direct campaign sending API (no GUI required)
- ✅ Batch email support
- ✅ Simpler integration model

**Test Results:**
- Feature Parity: ✅ 3 equivalent, 3 Resend superior, 2 Flexmail advantage (custom fields)
- Segment Creation: ✅ 0.32s (1,529 software companies in Brussels)
- Segment → Resend: ✅ 0.24s (8 contacts pushed to audience)
- Campaign Send: ✅ 0.00s (campaign sent via Resend API)
- Webhook Setup: ✅ 0.00s (6 engagement events subscribed)
- Engagement Writeback: ✅ 0.83s (4/4 events tracked)

#### Test Script (RECOMMENDED)

```bash
# Ensure DATABASE_URL / POSTGRES_CONNECTION_STRING is configured via .env.local, .env, or .env.database

# Run Resend POC test (uses mock if no API key)
uv run python scripts/test_poc_resend_activation.py --mock

# Run with real Resend
export RESEND_API_KEY="your-api-key"
uv run python scripts/test_poc_resend_activation.py
```

#### POC Gap Status (Resend)

| Requirement | Status | Result |
|-------------|--------|--------|
| NL → Segment flow | ✅ VERIFIED | 0.32s segment creation; the separate `>=95%` acceptance-style proof still needs to be surfaced in a conformity appendix |
| Segment → Resend ≤60s | ✅ VERIFIED | 0.24s latency (mock) |
| Campaign Send | ✅ VERIFIED | Resend API direct (Flexmail requires GUI) |
| Webhook Setup | ✅ VERIFIED | 6 events subscribed via API |
| Engagement → CDP | ✅ VERIFIED | 4 events tracked |

#### Exit Criteria

- ✅ Segment created via chatbot appears in Resend within 60 seconds (0.24s achieved)
- ✅ Campaign sent via Resend API (no GUI required)
- ✅ Webhooks configured via API for engagement tracking (6 events)
- ✅ Engagement events flow back to Tracardi (4 events tracked)
- ✅ End-to-end latency measured and documented

---

### P0: POC Flexmail Activation Tests (Alternative)

**Status:** ✅ COMPLETE - All 3 tests passing (alternative to Resend)
**Discovered:** 2026-03-08 (from BACKLOG.md Milestone POC)
**Last Updated:** 2026-03-08 12:05 CET
**Severity:** MEDIUM

#### Current State

Flexmail tests pass but are now strictly optional reference coverage. The current active path is Resend unless the user explicitly reopens a Flexmail requirement.

#### Test Script

```bash
# Run Flexmail POC test (alternative)
uv run python scripts/test_poc_activation.py --mock
```

---

### P0: MCP Server Implementation

**Status:** ✅ COMPLETE - MCP server operational with 7 core tools
**Discovered:** 2026-03-08 (from BACKLOG.md Milestone 0A)
**Last Updated:** 2026-03-08
**Severity:** HIGH

#### Current State

- MCP server implemented in `src/mcp_server.py`
- 7 core read-only tools exposed via Model Context Protocol
- Supports both stdio (Claude Desktop) and SSE (HTTP) transports
- Uses existing PostgreSQLSearchService and Unified360Service
- Health endpoint verified working

#### Tools Exposed

| Tool | Purpose |
|------|---------|
| `search_companies` | Search by keywords, city, NACE, status |
| `aggregate_companies` | Industry/city/legal form analytics |
| `get_company_360_profile` | Complete 360° view (KBO + CRM + Financial) |
| `get_industry_summary` | Pipeline/revenue by industry |
| `get_geographic_revenue_distribution` | Revenue by city |
| `get_identity_link_quality` | KBO matching coverage |
| `find_high_value_accounts` | Risk/opportunity accounts |

#### Resources Exposed

- `cdp://schema/companies` - Companies table schema
- `cdp://stats/summary` - Database statistics

#### Usage

```bash
# Stdio mode (Claude Desktop)
./scripts/start_mcp_server.sh

# SSE mode (HTTP API on port 8001)
./scripts/start_mcp_server.sh --sse

# Health check
curl http://localhost:8001/health
```

#### Documentation

- `docs/MCP_SERVER.md` - Full documentation
- `.mcp/claude_desktop_config.json` - Claude Desktop configuration template

---

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
uv run python scripts/sync_teamleader_to_postgres.py --full

# Incremental sync (uses last cursor)
uv run python scripts/sync_teamleader_to_postgres.py
```

#### ✅ COMPLETED: Exact Online → PostgreSQL Sync Pipeline

**Verified working with live Exact Online demo environment:**
- ✅ OAuth authorization completed
- ✅ 258 GL Accounts synced
- ✅ 78 Invoices synced
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
uv run python scripts/sync_exact_to_postgres.py --full

# Incremental sync (uses last cursor)
uv run python scripts/sync_exact_to_postgres.py
```

#### ✅ CRITICAL ISSUE: Tool Selection Fix - OPTION D ROUTING GUARD IMPLEMENTED

**Status:** ✅ COMPLETE - All 3 test queries now PASS  
**Implemented:** 2026-03-08  
**Commit:** `5c3117e` — feat(critic): add deterministic routing guard for 360° tool selection  
**Test File:** `tests/unit/test_critic_routing.py` — 27 tests passed

**Test Results (AFTER Option D routing guard implementation):**

| Query | Expected Tool | Actual Tool Used | Result |
|-------|---------------|------------------|--------|
| "How well are source systems linked to KBO?" | `get_identity_link_quality` | `get_identity_link_quality` | ✅ PASS |
| "Show me revenue distribution by city" | `get_geographic_revenue_distribution` | `get_geographic_revenue_distribution` | ✅ PASS |
| "Pipeline value for software companies in Brussels?" | `get_industry_summary` | `get_industry_summary` | ✅ PASS |

**What Was Implemented:**
Added deterministic keyword-based routing guard to `critic_node` in `src/graph/nodes.py`:

1. **QUERY_ROUTING_RULES** — List of 3 rules mapping keyword patterns → required tool
2. **`_extract_last_user_query()`** — Finds the last HumanMessage content (lowercase)
3. **`_check_routing_rules()`** — Evaluates each rule; returns error if forbidden tool used
4. **`_validate_tool_call()`** — Extended with Check 6 (routing guard)
5. **`critic_node()`** — Now extracts user query and passes it to validation

**Routing Rules:**
| Query Pattern Keywords | Required Tool | Forbidden Tools |
|------------------------|---------------|-----------------|
| "linked to kbo", "match rate", "kbo link", "link quality" … | `get_identity_link_quality` | `get_data_coverage_stats`, `search_profiles`, `aggregate_profiles` |
| "revenue distribution", "revenue by city", "geographic distribution" … | `get_geographic_revenue_distribution` | `aggregate_profiles`, `search_profiles` |
| "pipeline value for", "total pipeline", "industry pipeline" … | `get_industry_summary` | `search_profiles`, `aggregate_profiles` |

**Unit Tests:**
- `tests/unit/test_critic_routing.py` — 27 passed in 0.77s
- `tests/unit/` (full suite) — 545 passed, 4 pre-existing failures unchanged

**How It Works:**
When the LLM selects a forbidden tool for a query containing specific keywords, the critic immediately rejects the tool call and returns a corrective error naming the correct tool — forcing the LLM to retry with the right choice.

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

**Status:** REOPENED - Drafts repaired, runtime execution blocked by CE limitation
**Discovered:** 2026-03-07 19:29 CET
**Last Updated:** 2026-03-08 21:45 CET
**Severity:** MEDIUM

#### Current State

Tracardi activation layer is only partially verified:
- ✅ 4 event sources configured (cdp-api, kbo-batch-import, kbo-realtime, resend-webhook)
- ✅ API fully functional (auth, /track, profile queries)
- ✅ `scripts/setup_tracardi_workflows.py` rewritten to the current `/flow/draft` API
- ✅ All 5 workflow drafts repaired locally on 2026-03-08
- ✅ Bounce draft now shows `Start -> Copy data -> Update profile`
- ✅ Engagement draft now shows `Start -> Increment counter -> Copy data -> Update profile`
- ❌ **BLOCKED:** Runtime execution requires Tracardi Premium (licensed feature)
- ⚠️ Engagement rules remain `enabled=true`, `running=false`, `production=false` (cannot be changed in CE)
- ✅ Verification script created: `scripts/setup_and_verify_tracardi.py`
- ✅ GUI accessible at http://localhost:8787
- ⚠️ Destinations: 0 configured (require GUI - API needs specific format)

#### Root Cause Analysis

**Tracardi Community Edition does not support production workflow execution.**

Evidence:
- POST /rule to update `production=true` returns 200 but values do not persist
- `/deploy/{path}` endpoint is marked as "licensed" in OpenAPI spec (premium feature)
- Tracardi GUI shows no "Deploy" button - only "View Deployed FLOW"
- `/license` endpoint returns 404 (Community Edition has no licensing)
- `deploy_timestamp` field remains "none" despite multiple save attempts

#### Next Actions

1. ✅ **Document the CE limitation** in the Illustrated Guide - COMPLETED 2026-03-08
2. ✅ **Update guide expectations** - workflow screenshots show draft structure, not live execution - COMPLETED 2026-03-08
3. ✅ **Implement Python-based event processor** - COMPLETED 2026-03-08
   - Created `scripts/cdp_event_processor.py` with:
     - Resend webhook processing with signature verification
     - Engagement score tracking in PostgreSQL
     - Next Best Action recommendation generation
     - Cross-sell opportunity detection by NACE code
     - Multi-division sales insights
     - REST API: `/api/next-best-action/{kbo}`, `/api/engagement/leads`
4. ✅ **Capture evidence for Illustrated Guide** - core proof completed 2026-03-08
   - Populated Resend audience proof captured for the exact Brussels IT subset (`190` company rows → `189` unique contacts)
   - Verified event-processor outputs converted into guide-ready JSON evidence
   - Website-behavior proof captured for the same B.B.S. UID via canonical `event_facts`
5. Keep Resend transport setup as supporting infrastructure

## Paused

### P0: Azure Infrastructure Deployment

**Status:** PAUSED
**Paused:** 2026-03-09
**Reason:** The user paused Azure infrastructure deployment to save costs and explicitly limited the next cloud re-entry to Microsoft Entra ID auth plus Azure OpenAI. Full Azure hosting for Container Apps, VMs, or managed PostgreSQL is not the active path.

Resume only if:
- the user explicitly reopens Azure infrastructure deployment beyond the narrow auth + LLM scope

Notes:
- Azure OpenAI may still be used for LLM inference when the colleague-facing path is reopened
- Azure Entra ID remains in scope for the future authenticated rollout
- All compute infrastructure currently runs locally via docker-compose
- Terraform configurations in `infra/` remain historical/reference material unless cloud work is explicitly resumed

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

### P1: Local Chatbot Sharing For Colleague Testing

**Status:** PAUSED
**Paused:** 2026-03-09
**Reason:** The user redirected the active work from local sharing setup to backlog planning. The implementation choice is still open between a private Tailscale path and a public password-protected path.

Resume when:
- the user wants colleague-access setup resumed

Next action:
1. Choose between `tailscale serve` (private tailnet access) and a password-gated public route such as `tailscale funnel`, then implement the safer option for the current test audience.

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
