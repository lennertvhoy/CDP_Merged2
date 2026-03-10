# WORKLOG

**Purpose:** Append-only session log for meaningful task updates

---

## 2026-03-09 (Repo Audit Backlog Pass And Secret Sanitization)

### Task: Scan the repo for unfinished, legacy, organizational, and hygiene issues; fold the real findings into the backlog

**Type:** docs_or_process_only
**Status:** COMPLETE
**Timestamp:** 2026-03-09 22:26 CET
**Git Head:** `20be6b1`

**Summary:**
Ran a scoped repo audit aimed at backlog curation rather than broad refactoring. The highest-priority finding was security, not organization: the current repo state had a real Microsoft Entra client secret written into tracked docs (`NEXT_ACTIONS.md` and `docs/MICROSOFT_ENTRA_SETUP.md`). I sanitized those tracked examples to placeholders and recorded the remaining follow-up as a live risk because the exposed secret still needs rotation. I then updated `BACKLOG.md` to reflect the current implementation state more accurately and to capture the most concrete cleanup items the audit surfaced: the partially orphaned SQLAlchemy model/repository layer, tracked Python bytecode/cache artifacts, stale script setup docs that still point at `pip install -r requirements.txt`, and the stray tracked `src/enrichment/website_discovery.py.patch` file. I also corrected the backlog’s stale chat/auth statuses so it now reflects the already-implemented local chat persistence, title generation, and Entra groundwork instead of treating those items as untouched.

**Files Changed:**
- `docs/MICROSOFT_ENTRA_SETUP.md`
- `NEXT_ACTIONS.md`
- `PROJECT_STATE.yaml`
- `STATUS.md`
- `BACKLOG.md`
- `WORKLOG.md`

**Verification:**
- `rg -n "AZURE_AD_CLIENT_SECRET=|Client Secret:|client secret" NEXT_ACTIONS.md STATUS.md WORKLOG.md PROJECT_STATE.yaml BACKLOG.md docs/MICROSOFT_ENTRA_SETUP.md .env.example .env.local.example .chainlit/config.toml` -> exposed concrete secret in tracked docs before sanitization; placeholders remain afterward
- `find src tests scripts -type f \\( -name '*.pyc' -o -name '*.pyo' \\) | wc -l` -> `197`
- `find docs -type f | wc -l` -> `217`
- `find docs/archive -type f | wc -l` -> `75`
- `find docs -maxdepth 1 -type f | wc -l` -> `54`
- `rg -n "TODO|FIXME|TBD|NotImplemented|pragma: no cover" src scripts tests --glob '!scripts/archive/**' --glob '!**/__pycache__/**'` -> confirmed live unfinished paths in `src/services/writeback.py`, `scripts/populate_hyperrealistic_demo_data.py`, and `scripts/demo_autotask_integration.py`
- `git grep -n "tests/unit/repository"` plus `sed -n '1,260p' pyproject.toml` -> confirmed repository tests exist but pytest currently excludes them with `norecursedirs = ["tests/unit/repository"]`
- `git grep -n "website_discovery.py.patch"` -> no references found

**Follow-up:**
1. Rotate the exposed Microsoft Entra client secret before enabling Entra auth locally.
2. Remove tracked cache artifacts and tighten ignore/check rules so they do not come back.
3. Decide whether the SQLAlchemy model/repository layer is being kept and, if so, promote it out of its current half-wired state.

---

## 2026-03-09 (Microsoft Entra ID Authentication Implementation)

### Task: Implement Microsoft Entra ID (Azure AD) OAuth authentication for colleague-facing rollout

**Type:** app_code
**Status:** COMPLETE
**Timestamp:** 2026-03-09 22:45 CET
**Git Head:** `8c2e5cf`

**Summary:**
Implemented Microsoft Entra ID (Azure AD) OAuth authentication to enable colleague work-account login. Created Azure AD App Registration "CDP Chatbot" (d13725b8-ce4e-4103-9518-2d66bcce5beb) in tenant ce408fd5-2526-4cbb-bbe6-f0c2e188b89d with redirect URI http://localhost:8000/auth/oauth/azure-ad/callback. Added comprehensive configuration: CHAINLIT_ENABLE_AZURE_AD, AZURE_AD_TENANT_ID, AZURE_AD_CLIENT_ID, AZURE_AD_CLIENT_SECRET, AZURE_AD_REDIRECT_URI, AZURE_AD_ALLOWED_DOMAINS. Implemented domain validation in oauth_user_callback to restrict access to allowed email domains. Also implemented web search policy framework with four modes (disabled, restricted, opt-in, default-on), PII pattern blocking (emails, phone numbers), domain allowlist for restricted mode, and audit logging. Web search defaults to disabled for security. All code is ready but Azure AD testing is blocked until March 14, 2026 when quota resets.

**Azure Resources Created:**
- App Registration: "CDP Chatbot" (d13725b8-ce4e-4103-9518-2d66bcce5beb)
- Tenant ID: ce408fd5-2526-4cbb-bbe6-f0c2e188b89d
- Client Secret: Created (expires 2027-03-09)
- Redirect URIs: http://localhost:8000/auth/oauth/azure-ad/callback

**Files Changed:**
- `src/config.py` - Added AZURE_AD_* and WEB_SEARCH_* configuration
- `src/app.py` - Added domain validation and Azure AD metadata capture in oauth_user_callback
- `.chainlit/config.toml` - Added OAuth configuration template
- `.env.example` - Added configuration templates
- `src/services/web_search_policy.py` - New web search policy enforcement module
- `scripts/setup_azure_ad_auth.py` - New setup validation script
- `docs/MICROSOFT_ENTRA_SETUP.md` - New comprehensive documentation
- `tests/unit/test_web_search_policy.py` - New unit tests (14 passing)
- `PROJECT_STATE.yaml` - Updated state
- `STATUS.md` - Updated status
- `NEXT_ACTIONS.md` - Updated actions
- `WORKLOG.md` - This entry

**Verification:**
- `az ad app show --id d13725b8-ce4e-4103-9518-2d66bcce5beb` -> App registration exists and configured
- `poetry run python scripts/setup_azure_ad_auth.py` -> All required config set, auth currently disabled
- `poetry run pytest tests/unit/test_web_search_policy.py -v` -> 14 passed
- `poetry run pytest tests/unit/test_config.py -v` -> 7 passed
- `git status --short` -> 8 files changed, 815 insertions
- `git log --oneline --decorate -n 3` -> 8c2e5cf at HEAD

**Environment Variables (in .env.local, not committed):**
```
CHAINLIT_ENABLE_AZURE_AD=false  # Set to true to enable
AZURE_AD_TENANT_ID=ce408fd5-2526-4cbb-bbe6-f0c2e188b89d
AZURE_AD_CLIENT_ID=d13725b8-ce4e-4103-9518-2d66bcce5beb
AZURE_AD_CLIENT_SECRET=***
AZURE_AD_REDIRECT_URI=http://localhost:8000/auth/oauth/azure-ad/callback
WEB_SEARCH_POLICY=disabled
```

**Follow-up:**
1. Enable Azure AD locally after March 14, 2026 quota reset: Set CHAINLIT_ENABLE_AZURE_AD=true
2. Test work account login flow end-to-end
3. Verify domain restrictions if AZURE_AD_ALLOWED_DOMAINS configured
4. Decide on web search policy (currently disabled) and enable if needed
5. Deploy to production server farm with production redirect URI

---

## 2026-03-09 (Browser Chat Continuity Fixes For Local Dev Auth)

### Task: Complete the browser-driven localhost history walkthrough and fix the issues it exposed

**Type:** app_code
**Status:** COMPLETE
**Timestamp:** 2026-03-09 21:47 CET
**Git Head:** `8a2676c`

**Summary:**
Continued directly from the `8a2676c` handoff and took the next unblocked chat-product increment: a real browser walkthrough of the new dev-auth localhost path. That walkthrough surfaced three genuine product issues. First, the repo-owned `.chainlit/translations/*.json` overrides were stale relative to the installed Chainlit frontend, which left login labels blank and history/search UI strings rendering as raw translation keys; I resynced those translation files from the installed package. Second, real thread persistence was failing because `src/services/chainlit_data_layer.py` could insert `NULL` into the non-null JSONB `metadata` and `tags` columns when Chainlit created sparse thread rows; I fixed `update_thread()` to default those fields to `{}` / `[]` for new rows while preserving existing JSON on sparse upserts. Third, reopened threads were only showing history because `src/app.py` had no `@cl.on_chat_resume` hook; I added resume-time workflow/checkpointer/bootstrap wiring so reopened threads restore a live composer without sending a fresh welcome message. After those fixes, the browser flow on `127.0.0.1:8010` showed readable auth/history labels, isolated thread lists, owner thread fetches returning `200`, cross-user thread access returning `401`, and direct `/thread/{thread_id}` reopen restoring the composer so follow-up messages stayed on the same stored thread. A low-severity residual warning remains in Chainlit itself: `chainlit/session.py` still logs `RuntimeWarning: coroutine 'set_chat_profiles' was never awaited` during profile restore, but resume behavior still worked.

**Files Changed:**
- `.chainlit/translations/*.json`
- `src/app.py`
- `src/services/chainlit_data_layer.py`
- `tests/unit/chainlit_test_harness.py`
- `tests/unit/test_app.py`
- `tests/unit/test_chainlit_data_layer.py`
- `PROJECT_STATE.yaml`
- `STATUS.md`
- `NEXT_ACTIONS.md`
- `WORKLOG.md`

**Verification:**
- `git status --short` -> session-owned changes limited to `.chainlit/translations/*.json`, `src/app.py`, `src/services/chainlit_data_layer.py`, `tests/unit/chainlit_test_harness.py`, `tests/unit/test_app.py`, `tests/unit/test_chainlit_data_layer.py`, `PROJECT_STATE.yaml`, `STATUS.md`, `NEXT_ACTIONS.md`, and `WORKLOG.md`
- `git log --oneline --decorate -n 5` -> confirmed `8a2676c` at `HEAD` before the follow-on commit
- `poetry run pytest tests/unit/test_app.py tests/unit/test_chainlit_data_layer.py tests/unit/test_config.py -q` -> `48 passed` (plus one unrelated `PydanticDeprecatedSince20` warning from `traceloop`)
- `poetry run ruff check src/app.py src/config.py src/services/chainlit_data_layer.py tests/unit/chainlit_test_harness.py tests/unit/test_app.py tests/unit/test_chainlit_data_layer.py tests/unit/test_config.py` -> `All checks passed!`
- temporary auth-enabled app on `127.0.0.1:8010` -> browser walkthrough confirmed login labels rendered, history/search labels rendered, direct `/thread/{thread_id}` reopen kept the same URL, reopened threads exposed `#chat-input`, and follow-up stayed on the same stored thread while owner `/project/thread/{thread_id}` returned `200`
- server log during the same browser walkthrough -> `/home/ff/Documents/CDP_Merged/.venv/lib/python3.12/site-packages/chainlit/session.py:306: RuntimeWarning: coroutine 'set_chat_profiles' was never awaited`

**Follow-up:**
1. ✅ COMPLETE - Added and verified Microsoft Entra work-account login infrastructure (2026-03-09 22:45 CET)
2. Decide whether the current first-message-derived sidebar titles and default history affordances are sufficient for colleague testing; if not, implement the smallest polish needed.
3. Keep the Chainlit `set_chat_profiles` warning documented and only add a repo workaround if it starts affecting UX, tests, or rollout confidence.

## 2026-03-09 (Local Dev Auth For Chat History Verification)

### Task: Unblock authenticated local history checks before Microsoft Entra by adding a dev-only Chainlit login path

**Type:** app_code
**Status:** COMPLETE
**Timestamp:** 2026-03-09 21:15 CET

---

## 2026-03-09 (Entra Secret Rotation And Doc Guard)

### Task: Retire the compromised Microsoft Entra client secret and prevent tracked docs from reintroducing live values

**Type:** infrastructure
**Status:** COMPLETE
**Timestamp:** 2026-03-09 22:41 CET
**Git Head:** `3088bbb`

**Summary:**
Continued directly from the repo-audit handoff and took the highest-priority unfinished security step. Verified Azure CLI access for tenant `ce408fd5-2526-4cbb-bbe6-f0c2e188b89d` and the `CDP Chatbot` app registration, confirmed the app still had a single active password credential, then rotated that credential in Entra and replaced the local active value in untracked `.env.local` immediately so the exposed secret is no longer usable from this workspace. Tightened `.env.local` permissions from `644` to `600`. While closing that loop, I found one additional tracked leak surface: `scripts/setup_azure_ad_auth.py` printed the first 20 characters of `AZURE_AD_CLIENT_SECRET`; that helper now prints `<redacted>` for secret fields instead. I also fixed the stale `STATUS.md` table row that still showed a truncated secret prefix, added placeholder-only Entra secret checks to `scripts/doc_lint.py`, and wired that lint into CI for both docs-only and mixed change sets.

**Files Changed:**
- `.github/workflows/ci.yml`
- `scripts/doc_lint.py`
- `scripts/setup_azure_ad_auth.py`
- `PROJECT_STATE.yaml`
- `STATUS.md`
- `NEXT_ACTIONS.md`
- `WORKLOG.md`

**Local Environment Mutation (not committed):**
- `.env.local` - replaced `AZURE_AD_CLIENT_SECRET` with the rotated value and set permissions to `600`

**Verification:**
- `az account show --query '{tenantId:tenantId,user:user.name}' -o json` -> tenant `ce408fd5-2526-4cbb-bbe6-f0c2e188b89d`, user `l.vanhoyweghen@it1.be`
- `az ad app show --id d13725b8-ce4e-4103-9518-2d66bcce5beb --query '{appId:appId,displayName:displayName}' -o json` -> confirmed `CDP Chatbot`
- `az ad app credential list --id d13725b8-ce4e-4103-9518-2d66bcce5beb --query "[].{keyId:keyId,start:startDateTime,end:endDateTime,displayName:displayName}" -o json` before reset -> one pre-rotation credential `e658e308-ed91-4f60-ae90-883359438ed5`
- `az ad app credential reset --id d13725b8-ce4e-4103-9518-2d66bcce5beb --display-name CDP-Chatbot-Prod --query password -o tsv` -> rotation completed; new secret captured directly into `.env.local` without printing it back into tracked files
- `az ad app credential list --id d13725b8-ce4e-4103-9518-2d66bcce5beb --query "[].{keyId:keyId,start:startDateTime,end:endDateTime,displayName:displayName}" -o json` after reset -> one replacement credential `193346f1-d892-4c8a-b792-92d342575564`, start `2026-03-09T21:38:52Z`, end `2027-03-09T21:38:52Z`
- `rg -n "^AZURE_AD_CLIENT_SECRET=" .env.local | sed 's/=.*$/=<redacted>/'` -> local env points at the replacement secret
- `stat -c '%a %n' .env.local` -> `600 .env.local`

**Follow-up:**
1. Keep `CHAINLIT_ENABLE_AZURE_AD=false` until the user wants the Entra login validation step resumed.
2. Use the new doc-lint guard to catch future placeholder regressions before commit/CI drift.
3. When the server-farm rollout path resumes, move the active secret into a vault-backed source instead of environment-only storage.

## 2026-03-09 (Geocoding Post-Fix Live Verification)

### Task: Verify the first geocoding chunk launched after commit `5bf2595` no longer emits nullable-trait `strip()` failures

**Type:** verification_only
**Status:** COMPLETE
**Timestamp:** 2026-03-09 22:56 CET
**Git Head:** `7914d96`

**Summary:**
Continued directly from the security handoff and took the next explicit enrichment verification step. The pre-fix geocoding batch child from `18:25:29 CET` finished `Batch 20/20` at `21:39:54 CET`. The chunked parent immediately launched a new batch child PID `3236076` from cursor `1366466e-b3d5-4d7f-8cfd-ab91e7c9b503`, which is after commit `5bf2595`. Precise post-launch log checks showed Batches `1/20` through `5/20` complete at `21:52:17`, `22:04:45`, `22:17:05`, `22:29:13`, and `22:41:25 CET`, with fresh geocoded rows still streaming through `22:55:21 CET` and no new `'NoneType' object has no attribute 'strip'` lines in that post-launch window. That closes the live-verification gap for the nullable address-trait guard. With this blocker cleared, geocoding can go back to routine background monitoring, and the next foreground repo-hygiene increment is removing tracked `.pyc` / `__pycache__` artifacts and adding a minimal guard so they do not return.

**Files Changed:**
- `PROJECT_STATE.yaml`
- `STATUS.md`
- `NEXT_ACTIONS.md`
- `WORKLOG.md`

**Verification:**
- `git status --short` -> clean at session start
- `git log --oneline --decorate -n 5` -> `7914d96 (HEAD -> main) fix(security): rotate Entra secret and guard docs`
- `git show -s --format='%h %ci %s' 5bf2595` -> `5bf2595 2026-03-09 18:33:29 +0100 fix(enrichment): verify geocoding relaunch`
- `ps -o pid,ppid,lstart,etime,cmd -p 1308025,2961612,3236076` -> bash supervisor still active, chunked parent started `18:25:28 CET`, post-fix batch child `3236076` started `21:39:54 CET`
- `cat logs/enrichment/geocoding_parallel_cursor.json` -> cursor now `1366466e-b3d5-4d7f-8cfd-ab91e7c9b503`, updated at `2026-03-09T20:39:54.699757+00:00`
- `awk 'flag{print} /Running chunk: start_after_id=1366466e-b3d5-4d7f-8cfd-ab91e7c9b503, limit=10000/{flag=1}' logs/enrichment/geocoding_parallel_20260308_140529.log | rg "Running chunk: start_after_id=1366466e-b3d5-4d7f-8cfd-ab91e7c9b503|Batch [1-5]/20 complete|NoneType"` -> Batches `1/20` through `5/20` completed cleanly and no post-launch `NoneType` lines appeared
- `tail -n 20 logs/enrichment/geocoding_parallel_20260308_140529.log` -> fresh `Geocoded:` / `No geocoding results` lines continued through `22:55:21 CET` without new nullable-trait failures

**Follow-up:**
1. Remove tracked `.pyc` / `__pycache__` artifacts and add the smallest repeatable guard.
2. Keep geocoding on background monitoring and only reopen the nullable-trait issue if fresh `NoneType`/`strip()` failures recur.
3. Recheck canonical enrichment counts from PostgreSQL after additional runner activity before refreshing coverage narratives again.

## 2026-03-09 (Repo Hygiene Queue Correction)

### Task: Correct the stale cache-artifact cleanup claim and point repo hygiene at the verified stale script workflow docs

**Type:** docs_or_process_only
**Status:** COMPLETE
**Timestamp:** 2026-03-09 23:03 CET
**Git Head:** `d1532b0`

**Summary:**
After committing the geocoding state refresh, I verified the next queued repo-hygiene item and found the premise was false. Fresh git-tracked checks showed `git ls-files '*.pyc' -> 0` and `git ls-files | rg '(__pycache__/|\\.py[co]$)'` returned no matches, so the earlier `find` count of `197` referred to local untracked cache files rather than tracked git paths. I corrected `NEXT_ACTIONS.md`, `STATUS.md`, and `BACKLOG.md` to remove that stale cleanup target and replace it with the next verified mismatch: `scripts/README.md` still instructs `pip install -r requirements.txt`, and `scripts/requirements.txt` still implies a separate pip-managed dependency path instead of the repo's Poetry workflow.

**Files Changed:**
- `PROJECT_STATE.yaml`
- `STATUS.md`
- `NEXT_ACTIONS.md`
- `BACKLOG.md`
- `WORKLOG.md`

**Verification:**
- `git status --short` -> clean immediately before starting the queue correction
- `git log --oneline --decorate -n 5` -> `d1532b0 (HEAD -> main) docs(state): confirm geocoding guard live`
- `git ls-files '*.pyc' | wc -l` -> `0`
- `git ls-files | rg "(__pycache__/|\\.py[co]$)"` -> no matches
- `rg -n "pip install -r requirements\\.txt|requirements\\.txt|poetry" scripts/README.md scripts/requirements.txt` -> `scripts/README.md:8:pip install -r requirements.txt`
- `git ls-files src/enrichment/website_discovery.py.patch && rg -n "website_discovery\\.py\\.patch" -g '!src/enrichment/website_discovery.py.patch'` -> patch file is still tracked and still unreferenced outside backlog/worklog context

**Follow-up:**
1. Update `scripts/README.md` to match the Poetry-based workflow actually used by the repo.
2. Decide whether `scripts/requirements.txt` should be deleted, quarantined, or marked historical.
3. After the script-doc cleanup, re-evaluate whether `src/enrichment/website_discovery.py.patch` should remain tracked.

## 2026-03-09 (Script Workflow Docs Cleanup)

### Task: Replace the stale per-directory pip instructions with the repo-root Poetry workflow and remove the dead script requirements file

**Type:** docs_or_process_only
**Status:** COMPLETE
**Timestamp:** 2026-03-09 23:08 CET
**Git Head:** `5ddc324`

**Summary:**
Continued directly from the queue-correction handoff and closed the next verified repo-hygiene gap. `scripts/README.md` was rewritten to document the actual repo-root workflow: install dependencies with Poetry, run Python helpers as `poetry run python scripts/...`, and treat `scripts/archive/` as legacy-only material. Because no live repo path consumed `scripts/requirements.txt` and the maintained dependency source already lives in the root `pyproject.toml`, I deleted that stale file instead of preserving a second package-management path. While doing that cleanup, I found `docs/KBO_CLEANUP_COMPLETION_SUMMARY.md` still presenting removed and moved legacy artifacts as if they were current deliverables, so I explicitly quarantined that document as historical rather than letting it silently contradict the new script guidance. With that mismatch closed, the next repo-hygiene target is the unreferenced `src/enrichment/website_discovery.py.patch` file.

**Files Changed:**
- `scripts/README.md`
- `docs/KBO_CLEANUP_COMPLETION_SUMMARY.md`
- `scripts/requirements.txt` (deleted)
- `PROJECT_STATE.yaml`
- `STATUS.md`
- `NEXT_ACTIONS.md`
- `BACKLOG.md`
- `WORKLOG.md`

**Verification:**
- `rg -n "pip install -r requirements\\.txt|requirements\\.txt" scripts/README.md docs/KBO_CLEANUP_COMPLETION_SUMMARY.md` -> README no longer points to the removed pip workflow; the historical summary now references the removal in a quarantine banner instead of acting as current setup guidance
- `test ! -f scripts/requirements.txt && echo missing` -> `missing`
- `python3 scripts/doc_lint.py` -> clean
- `git diff --check` -> clean

**Follow-up:**
1. Inspect `src/enrichment/website_discovery.py.patch` against the live implementation and decide whether it is justified or leftover patch debris.
2. If the patch file is unnecessary, remove it and scrub remaining live references from the queue/backlog docs.
3. Keep historical KBO cleanup material clearly separated from maintained operator docs until a broader docs-surface pass is scheduled.

## 2026-03-09 (Website Discovery Patch Artifact Cleanup)

### Task: Remove the stray `website_discovery.py.patch` file after verifying it had no live repo purpose

**Type:** docs_or_process_only
**Status:** COMPLETE
**Timestamp:** 2026-03-09 23:14 CET
**Git Head:** `eaaf4d4`

**Summary:**
Continued directly from the latest repo-hygiene handoff and verified that `src/enrichment/website_discovery.py.patch` was stale tracked debris, not maintained project history. The file was zero bytes, its git history only pointed back to the initial repository import, `rg --files -g '*.patch'` showed it was the only tracked patch file in the repo, and all remaining references lived only in queue/backlog/worklog notes rather than runtime code or operator docs. I deleted the file, removed the now-stale active queue entry, updated the state/backlog summaries to record why the removal was safe, and kept the foreground focus pointed back at real verified work instead of speculative hygiene.

**Files Changed:**
- `src/enrichment/website_discovery.py.patch` (deleted)
- `PROJECT_STATE.yaml`
- `STATUS.md`
- `NEXT_ACTIONS.md`
- `BACKLOG.md`
- `WORKLOG.md`

**Verification:**
- `ls -l src/enrichment/website_discovery.py.patch src/enrichment/website_discovery.py` -> patch file was `0` bytes while the live module was populated
- `git log --oneline --decorate -- src/enrichment/website_discovery.py.patch` -> only initial commit `4518742` referenced the patch file
- `rg --files -g '*.patch'` -> `src/enrichment/website_discovery.py.patch` was the only tracked patch file before deletion
- `rg -n "website_discovery\\.py\\.patch|patch artifact|unreferenced patch artifact" -S .` -> remaining references were queue/backlog/worklog only

**Follow-up:**
1. Keep foreground repo hygiene limited to fresh verified contradictions instead of speculative cleanup sweeps.
2. Return the next foreground slot to enrichment monitoring or another directly verified local blocker.

## 2026-03-09 (Fresh Enrichment Progress Recheck)

### Task: Recheck canonical enrichment progress from PostgreSQL plus current website/description chunk logs before making new coverage claims

**Type:** verification_only
**Status:** COMPLETE
**Timestamp:** 2026-03-09 23:20 CET
**Git Head:** `dcdc6b0`

**Summary:**
Continued directly from the patch-artifact cleanup handoff and took the next explicit follow-up step: refresh the live enrichment snapshot from PostgreSQL instead of repeating the older `20:43 CET` numbers. The direct recheck at `23:19 CET` showed canonical coverage had moved materially to `website_url=70,922`, `geo_latitude=63,979`, `ai_description=31,033`, and `cbe_enriched=1,252,019`, with `companies.updated_at` still moving through `23:19:15 CET`. Website discovery also remained active, finishing four more 250-row chunks at `23:10:35`, `23:13:42`, `23:16:24`, and `23:19:39 CET` for `57`, `64`, `53`, and `56` discoveries respectively. `description_ollama` finished four more 1000-row chunks at `22:55:59`, `23:02:55`, `23:09:47`, and `23:16:27 CET` for `622`, `645`, `660`, and `648` descriptions, pushing `ai_description_generated_at` to `6,058` fresh descriptions in the last five minutes. A short geocoding recheck found fresh geocoded rows still streaming through `23:19 CET` with no new nullable-trait `strip()` failures after the already-known `21:27 CET` lines, so the runner stays on background monitoring.

**Files Changed:**
- `PROJECT_STATE.yaml`
- `STATUS.md`
- `NEXT_ACTIONS.md`
- `WORKLOG.md`

**Verification:**
- `poetry run python ... SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE website_url IS NOT NULL AND website_url <> ''), COUNT(*) FILTER (WHERE geo_latitude IS NOT NULL), COUNT(*) FILTER (WHERE ai_description IS NOT NULL AND ai_description <> ''), COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '5 minutes'), COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '10 minutes'), COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'), MAX(updated_at) FROM companies` -> `1940603|70922|63979|31033|1635|2805|14003|2026-03-09 22:19:15.114548`
- `poetry run python ... SELECT COUNT(*) FILTER (WHERE industry_nace_code IS NOT NULL AND industry_nace_code <> ''), COUNT(*) FILTER (WHERE nace_description IS NOT NULL AND nace_description <> ''), COUNT(*) FILTER (WHERE legal_form IS NOT NULL AND legal_form <> '') FROM companies` -> `1252022|1252019|1176853`
- `poetry run python ... SELECT COUNT(*) FILTER (WHERE ai_description_generated_at >= NOW() - INTERVAL '5 minutes'), COUNT(*) FILTER (WHERE (ai_description IS NULL OR ai_description = '') AND industry_nace_code IS NOT NULL AND industry_nace_code <> '') FROM companies` -> `6058|1220784`
- `rg -n "Batch 10/10 complete|Website discoveries:|Last company ID:" logs/enrichment/website_discovery_20260308_140530.log | tail -n 12` -> latest completed website chunks at `23:10:35`, `23:13:42`, `23:16:24`, `23:19:39 CET`
- `rg -n "Batch 50/50 complete|AI descriptions:|Last company ID:" logs/enrichment/description_ollama_20260309_172601.log | tail -n 12` -> latest completed description chunks at `22:55:59`, `23:02:55`, `23:09:47`, `23:16:27 CET`
- `ps -eo pid,ppid,lstart,etime,cmd | rg 'enrich_companies_batch.py --enrichers (geocoding|website|description)'` -> current worker pids `3236076` (geo), `3334304` (description), `3337387` (website)
- `tail -n 60 logs/enrichment/geocoding_parallel_20260308_140529.log` plus `rg -n "NoneType|strip\\(\\)" logs/enrichment/geocoding_parallel_20260308_140529.log | tail -n 20` -> fresh geocoded rows through `23:19:17 CET`; no fresh `NoneType.strip()` lines beyond the already-known `21:27:39 CET` entries

**Follow-up:**
1. Keep geocoding on routine background monitoring unless fresh `NoneType`/`strip()` lines reappear or throughput materially changes.
2. Keep `description_ollama` at `CHUNK_SIZE=1000` / `BATCH_SIZE=20` while recent completed chunks stay in the current `2.4-2.6/s` band.
3. Recheck PostgreSQL counts again before the next documentation refresh if additional enrichment runtime keeps moving for another material interval.

## 2026-03-09 (Event Processor Daemon Refresh For Live Scoring Model Route)

### Task: Refresh the local event-processor daemon so `/api/scoring-model` matches the checked-in API contract

**Type:** verification_only
**Status:** COMPLETE
**Timestamp:** 2026-03-09 23:26 CET
**Git Head:** `545c173`

**Summary:**
Continued directly from the enrichment-state refresh and took the next smallest pending credibility-pass item. The checked-in `scripts/cdp_event_processor.py` already defined `GET /api/scoring-model`, but the long-running local daemon on `127.0.0.1:5001` was stale and returned `404`. I verified the mismatch directly, stopped the stale process, confirmed the route worked immediately when the current script was run in the foreground, and then re-launched the daemon as a detached background process using the repo virtualenv interpreter. The refreshed daemon is now stable as PID `3344307`, `/health` is green, `/api/scoring-model` returns the live deterministic model JSON, and the root endpoint advertises the scoring-model route. I then updated the live state and guide/spec notes so they no longer preserve the stale runtime caveat.

**Files Changed:**
- `PROJECT_STATE.yaml`
- `NEXT_ACTIONS.md`
- `docs/ILLUSTRATED_GUIDE.md`
- `docs/SYSTEM_SPEC.md`
- `WORKLOG.md`

**Verification:**
- `curl -fsS http://127.0.0.1:5001/health` before refresh -> local event processor reachable
- `curl -fsS -i http://127.0.0.1:5001/api/scoring-model` before refresh -> `404 Not Found`
- `rg -n "@app\\.(get|post)\\(\"/api/scoring-model|/api/scoring-model\"" scripts/cdp_event_processor.py` -> checked-in route exists
- `poetry run python scripts/cdp_event_processor.py` -> foreground run started cleanly and served the route
- `curl -fsS http://127.0.0.1:5001/api/scoring-model` during foreground run -> returned deterministic scoring model JSON
- `bash -lc 'setsid .venv/bin/python scripts/cdp_event_processor.py > logs/event_processor.log 2>&1 < /dev/null & echo $!'` -> launched detached daemon PID `3344307`
- `ps -p 3344307 -o pid,ppid,lstart,etime,cmd` -> background daemon still running
- `curl -fsS http://127.0.0.1:5001/health` after refresh -> `{"status":"ok","service":"cdp-event-processor","database":"ok","signature_verification":true}`
- `curl -fsS http://127.0.0.1:5001/api/scoring-model` after refresh -> live scoring model JSON returned
- `curl -fsS http://127.0.0.1:5001/` after refresh -> root endpoint advertises `GET /api/scoring-model`

**Follow-up:**
1. Treat `/api/scoring-model` as live-runtime verified in the next guide/spec export.
2. If the local event processor is restarted again, use the detached `.venv/bin/python scripts/cdp_event_processor.py` launch rather than the short-lived `nohup poetry run ...` attempt from this session.
3. Continue the next v3.3 credibility-pass item: tighten the remaining Autotask maturity wording or improve the API/code-page styling / PDF text-layer quality.

## 2026-03-09 (Operator Eval Run-Prep Harness)

### Task: Resume a different backlog item by turning the operator-eval bank into a repeatable local run-prep workflow

**Type:** app_code
**Status:** COMPLETE
**Timestamp:** 2026-03-09 23:38 CET
**Git Head:** `946ccf4`

**Summary:**
The user redirected the immediate session away from the v3.3 guide pass and onto another backlog item, so I resumed the paused operator-eval harness work instead of continuing guide polish. Added a repo-owned run-prep module at `src/evals/operator_eval_run_prep.py` plus a thin CLI at `scripts/prepare_operator_eval_run.py`. The new path turns `docs/evals/operator_eval_cases.v1.json` into a timestamped review bundle with `manifest.json`, `cases.json`, `scorecard.csv`, and `prompts.md` under `output/operator_eval_runs/<run_id>/`, and prefills per-case scorecard rows with run metadata, revision, and case metadata. I also added targeted unit coverage, ignored generated run bundles in `.gitignore`, updated the eval docs to point at the new workflow, and rewrote the queue/state docs so operator evals are no longer described as static assets only. The guide-credibility pass remains open, but its immediate follow-up is explicitly paused until this eval-harness increment is recorded.

**Files Changed:**
- `.gitignore`
- `src/evals/__init__.py`
- `src/evals/operator_eval_run_prep.py`
- `scripts/prepare_operator_eval_run.py`
- `tests/unit/test_operator_eval_run_prep.py`
- `docs/evals/README.md`
- `docs/evals/OPERATOR_EVAL_STANDARD.md`
- `PROJECT_STATE.yaml`
- `STATUS.md`
- `NEXT_ACTIONS.md`
- `BACKLOG.md`
- `WORKLOG.md`

**Verification:**
- `poetry run pytest tests/unit/test_operator_eval_assets.py tests/unit/test_operator_eval_run_prep.py -q` -> `5 passed`
- `poetry run ruff check src/evals/operator_eval_run_prep.py scripts/prepare_operator_eval_run.py tests/unit/test_operator_eval_run_prep.py` -> all checks passed after Ruff normalized the new module imports
- `poetry run python scripts/prepare_operator_eval_run.py --output-dir /tmp/operator_eval_runs_smoke --case-id copy_troubleshooting_clipboarditem_not_defined --app-revision 946ccf4 --model-provider openai --model-name gpt-5 --reviewer agent` -> emitted a timestamped smoke bundle with `manifest.json`, `cases.json`, `scorecard.csv`, and `prompts.md`

**Follow-up:**
1. Use `scripts/prepare_operator_eval_run.py` to create the first full baseline bundle against the current local chatbot revision and actually fill the scorecard.
2. Decide whether the first baseline should be captured through the live localhost UI, a direct conversation-driver path, or both, then codify that execution path.
3. Resume the paused v3.3 guide pass only after the operator-eval baseline path is recorded cleanly.

## 2026-03-10 (Poetry To uv Pivot)

### Task: Pause the in-flight CI repair and redirect the session to a Poetry-to-uv migration

**Type:** docs_or_process_only
**Status:** COMPLETE
**Timestamp:** 2026-03-10 17:00 CET
**Git Head:** `d88f69b`

**Summary:**
Started the session by triaging the current GitHub CI state for `d88f69b`. Verified that run `22891271161` is genuinely red, with failures in `Lint & Type Check`, `Unit Tests (3.12)`, and `Security Scan`. The concrete causes observed before the pivot were a large Ruff backlog, a `tests/unit/test_cdp_event_processor.py` collection failure because `scripts/cdp_event_processor.py` imports `psycopg2` under the Poetry-based CI environment, and a Bandit `B104` finding on the hardcoded `0.0.0.0` bind in `src/mcp_server.py`. Before landing any of those fixes, the user redirected the work to make Poetry-to-uv migration the priority. Per repo protocol, I paused the CI repair in `NEXT_ACTIONS.md`, recorded the red CI state in `PROJECT_STATE.yaml` and `STATUS.md`, and moved the queue/backlog to make the dependency-manager migration the active foreground task. No partial CI-fix code changes were left in the worktree.

**Files Changed:**
- `NEXT_ACTIONS.md`
- `PROJECT_STATE.yaml`
- `STATUS.md`
- `BACKLOG.md`
- `WORKLOG.md`

**Verification:**
- `gh run list --workflow ci.yml --limit 5` -> latest CI run `22891271161` for `d88f69b` completed with `failure`
- `gh run view 22891271161` -> `Lint & Type Check`, `Unit Tests (3.12)`, and `Security Scan` failed; `Detect Change Scope` and `Secret Detection` passed
- `gh run view 22891271161 --job 66414843105 --log | rg -n "test_cdp_event_processor|ModuleNotFoundError|psycopg2" -C 3` -> collection failure because `scripts/cdp_event_processor.py` imports `psycopg2`
- `gh run view 22891271161 --job 66414843128 --log` -> Bandit `B104` on `src/mcp_server.py:596`
- `poetry run ruff check src/ tests/` -> `165` violations reported locally
- `git status --short` -> clean before starting the uv migration edits

**Follow-up:**
1. Inventory all active Poetry touchpoints and migrate the repo to `uv`.
2. After the migration lands, rerun local validation and GitHub CI on the uv-based path.
3. Resume the paused code-level CI repair only if failures remain after the dependency-manager migration.

## 2026-03-10 (Poetry To uv Migration)

### Task: Replace Poetry with uv across the repo's active dependency-manager, CI, Docker, and operator workflow surfaces

**Type:** app_code
**Status:** PARTIAL
**Timestamp:** 2026-03-10 17:21 CET

**Summary:**
Implemented the repo's local `uv` migration end-to-end. `pyproject.toml` now uses PEP 621 plus `[dependency-groups]`, a fresh tracked `uv.lock` was generated, and the active install/run path was switched off Poetry across `.github/workflows/ci.yml`, `.github/workflows/cd.yml`, `Dockerfile`, `Makefile`, `scripts/setup.sh`, `scripts/start_mcp_server.sh`, `scripts/run_enrichment_persistent.sh`, `scripts/seed_data.sh`, and the current operator docs. I also removed the tracked `poetry.lock`, `requirements.txt`, and `requirements-dev.txt` files so the repo no longer carries a second dependency-manager story. While validating the new path, I folded in the small CI-adjacent fixes that were directly blocked by the old tooling surface: the event-processor tests now install `psycopg2-binary` under uv, and the MCP SSE server no longer hardcodes `0.0.0.0`, which cleared the local Bandit finding. The migration itself is working, but the repo is still not CI-clean: the Ruff backlog remains at `165` issues, and a fresh uv-based non-integration test run still reports `11` failures. Remote GitHub CI has not been rerun yet on the uv-based tree.

**Files Changed:**
- `pyproject.toml`
- `uv.lock`
- `poetry.lock` (deleted)
- `requirements.txt` (deleted)
- `requirements-dev.txt` (deleted)
- `.github/workflows/ci.yml`
- `.github/workflows/cd.yml`
- `Dockerfile`
- `Makefile`
- `scripts/setup.sh`
- `scripts/start_mcp_server.sh`
- `scripts/run_enrichment_persistent.sh`
- `scripts/seed_data.sh`
- `scripts/setup_azure_ad_auth.py`
- `scripts/setup_exact_oauth.py`
- `scripts/setup_resend_audience.py`
- `scripts/sync_teamleader_to_postgres.py`
- `scripts/sync_exact_to_postgres.py`
- `scripts/sync_autotask_to_postgres.py`
- `scripts/populate_hyperrealistic_demo_data.py`
- `scripts/generate_teamleader_mock_data.py`
- `scripts/test_poc_activation.py`
- `scripts/test_poc_resend_activation.py`
- `scripts/verify_kbo_matching.py`
- `scripts/README.md`
- `src/mcp_server.py`
- `docs/MICROSOFT_ENTRA_SETUP.md`
- `docs/TEST_PLAN.md`
- `docs/TROUBLESHOOTING.md`
- `docs/AUTOTASK_INTEGRATION.md`
- `docs/evals/README.md`
- `docs/ILLUSTRATED_GUIDE.md`
- `docs/illustrated_guide/ILLUSTRATED_GUIDE.md`
- `docs/SYSTEM_SPEC.md`
- `PROJECT_STATE.yaml`
- `STATUS.md`
- `NEXT_ACTIONS.md`
- `BACKLOG.md`
- `WORKLOG.md`

**Verification:**
- `UV_CACHE_DIR=/tmp/uv-cache uv lock` -> resolved `216` packages and generated `uv.lock`
- `UV_CACHE_DIR=/tmp/uv-cache uv sync --locked` -> created `.venv` and installed the locked environment successfully
- `UV_CACHE_DIR=/tmp/uv-cache uv export --frozen --all-groups --no-emit-project --no-hashes --output-file /tmp/cdp_requirements_audit.txt` -> succeeded, so the security job can audit the lock-derived requirements without tracked `requirements*.txt` files
- `UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/unit/test_cdp_event_processor.py -q` -> `6 passed`
- `UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/unit/test_config.py tests/unit/test_nodes.py tests/unit/test_tools.py tests/unit/test_validation.py -k "citation or shadow or azure_search" -q` -> `7 passed`, `2 skipped`
- `UV_CACHE_DIR=/tmp/uv-cache uv run --with bandit bandit -c .bandit.yml -r src/ -ll` -> no issues identified
- `UV_CACHE_DIR=/tmp/uv-cache uv run --frozen ruff check src/ tests/ --statistics` -> still `165` issues
- `UV_CACHE_DIR=/tmp/uv-cache uv run --frozen ruff format --check src/ tests/` -> `25` files would be reformatted
- `UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/ -m "not integration and not e2e" -q` -> still `11` failing tests (`tests/integration/test_api_suite.py`, `tests/unit/test_ai_email.py`, `tests/unit/test_app.py`, `tests/unit/test_tql_builder.py`)

**Follow-up:**
1. Commit and push the uv migration snapshot, then rerun GitHub CI on the new SHA.
2. Fix the remaining Ruff backlog and the `11` non-integration test failures that still reproduce locally under uv.
3. Only claim CI/CD success after the new uv-based GitHub Actions run is green for the pushed SHA.


---

## 2026-03-10 (Fix CI/CD Failures After uv Migration)

### Task: Fix test failures and Ruff issues following Poetry-to-uv migration

**Type:** app_code  
**Status:** PARTIAL  
**Timestamp:** 2026-03-10 17:35 CET  
**Git Head:** `fb85742`  

**Summary:**
Following the Poetry-to-uv migration (commit 1978e31), CI was failing with test errors and 165 Ruff issues. Fixed all unit test failures and auto-resolved Ruff issues. The remaining 3 failures are in `tests/integration/test_api_suite.py` - these are integration tests not marked with `@pytest.mark.integration` that require PostgreSQL (not available in CI).

**Fixes Applied:**
1. **email.py line 132**: Fixed `_load_segment_contacts` unpacking to handle 4 return values (profiles, total_count, backend, diagnostics)
2. **TQL builder**: Fixed to only add status filter when explicitly provided (aligns with schema description)
3. **test_app.py line 416**: Updated metadata assertion to include email field that code adds
4. **test_ai_email.py**: Updated 4 tests to check JSON structure instead of old string format
5. **test_tql_builder.py**: Updated empty params test to expect `traits.name EXISTS` (no default status)
6. **Ruff auto-fixes**: Fixed 165 issues (W293 blank line whitespace, W291 trailing whitespace, I001 unsorted imports, F401 unused imports, UP028 yield-in-for-loop, UP035 deprecated imports, F541 f-string without placeholders)

**Files Changed:**
- `src/ai_interface/tools/email.py` (unpacking fix)
- `src/search_engine/builders/tql_builder.py` (status filter logic)
- `tests/unit/test_app.py` (metadata assertion)
- `tests/unit/test_ai_email.py` (JSON assertions)
- `tests/unit/test_tql_builder.py` (empty params expectation)
- Plus 17 files with Ruff auto-fixes

**Test Results:**
- Unit tests: 628 passed, 2 skipped (100% pass rate)
- Ruff: 2 remaining B904 issues (exception chaining - pre-existing)
- CI run: https://github.com/lennertvhoy/CDP_Merged2/actions/runs/22913216042

**Remaining Work:**
The 3 failing tests in `tests/integration/test_api_suite.py` need to be marked with `@pytest.mark.integration` so they're excluded from the unit test run, OR the CI needs PostgreSQL service configured for integration tests.

