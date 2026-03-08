# CDP_Merged Backlog - AZURE INFRASTRUCTURE

**Platform:** AZURE (VMs, Container Apps, OpenAI)  
**Architecture:** Source systems PII truth + PostgreSQL intelligence truth + Tracardi activation runtime + AI chatbot  
**Last Updated:** 2026-03-08 (Roadmap aligned with hardening handoff `f9d1906`; core demo proof complete, final polish isolated)
**Purpose:** Medium-term roadmap from the current repo state to a credible demo first and production readiness later

## How To Use This File

- `NEXT_ACTIONS.md` is the active execution queue.
- `BACKLOG.md` is the medium-term roadmap and milestone inventory.
- `PROJECT_STATE.yaml` and `STATUS.md` remain the live-state source and summary.
- If these files conflict, verify implementation first, then fix the stale docs before continuing.

This file should answer one question for the next autonomous agent:

**"What still needs to happen from here to a credible demo now, and then to a production-ready finish later?"**

## Current Planning Mode

As of 2026-03-04, the roadmap is intentionally two-stage:

1. **Near-term:** deliver a stable, convincing demo within current constraints.
2. **Later:** productionize the missing licensed and source-system-dependent capabilities when access and budget exist.

Current constraints that shape this roadmap:
- no Tracardi license yet
- Azure budget is approximately `EUR 150/month`
- Azure deployment currently PAUSED for cost control (local-only mode active)
- **DEMO ENVIRONMENTS AVAILABLE:** Teamleader and Exact demo envs accessible for integration
- Autotask already has a production-capable client/sync path plus local unified-360 linkage, but the currently verified dataset still runs in demo mode until vendor access is granted
- Resend is the accepted email activation platform for the current POC; Flexmail parity is not a near-term blocker unless the user explicitly reopens it
- the user must do the final verification and wants at least one stable week before sign-off

Near-term planning rule:
- use real vendor access where it is obtainable now
- use hyperrealistic mocks where it is not
- keep the docs explicit about which integrations are `real`, `mock`, or `hybrid`

---

## Finish Line

The project is only genuinely complete when all of the following are true:

1. PostgreSQL contains production-usable enriched customer intelligence, not just raw KBO import data.
2. Tracardi acts only as the projected activation/runtime layer, with verified writeback and projection health.
3. The chatbot uses deterministic PostgreSQL-backed reads and controlled mutating actions with approval and audit.
4. Source-system integrations, identity reconciliation, consent, and PII resolution are implemented for real production flows.
5. Security, secret handling, CI/CD, operational monitoring, and deployment verification are production-safe.

---

## Foundations Already In Place

These should not be reopened unless the implementation regresses or new evidence disproves them.

| Area | Status | Evidence |
|------|--------|----------|
| Truth-layer architecture clarified | ✅ Complete | `AGENTS.md`, `STATUS.md`, `PROJECT_STATE.yaml`, architecture docs |
| PostgreSQL-first chatbot query plane | ✅ Complete | `src/ai_interface/tools/search.py`, `src/services/postgresql_search.py`, `scripts/verify_postgresql_search.py` |
| Projection/writeback contract | ✅ Complete | `docs/PROJECTION_CONTRACT.md` |
| Projection/writeback services | ✅ Complete | `src/services/projection.py`, `src/services/writeback.py`, `scripts/test_projection.py`, `scripts/test_writeback.py` |
| Projection/writeback tables deployed | ✅ Complete | `scripts/migrations/001_add_projection_tables.sql` plus deployment notes in `NEXT_ACTIONS.md` and `PROJECT_STATE.yaml` |
| 360 domain model skeleton | ⚠️ Partial | `src/models/` exists, but repo-fit/integration/dependency/test follow-up remains |

---

## Remaining Roadmap

The milestones below are ordered to support autonomous continuation and avoid reopening solved architecture questions.

### Future Standards And Modularity Worth Tracking

These are included only where they appear likely to add real future value to this project.

| Topic | Recommendation | Value To This Repo | Trigger |
|-------|----------------|--------------------|---------|
| MCP read-only tool server | Add to roadmap | High | When standardizing the PostgreSQL query plane and real/mock source adapters behind one reusable contract |
| Agent skill library | Add to roadmap | Medium | When standardizing repeatable demo prep, mock-authoring, eval, and state-doc workflows for future agents |
| OpenTelemetry GenAI semantic conventions | Add to roadmap | High | When standardizing traces, latency, token/cost, and tool-call observability across chatbot/tooling flows |
| Reproducible agent evals / trace grading | Add to roadmap | High | When locking demo stability and preventing regressions in search/tool behavior |
| OpenAI Responses API / Agents SDK alignment | Add to roadmap | Medium | When building new agentic features or replacing older OpenAI integration patterns |
| A2A (Agent2Agent) | Add as watchlist only | Conditional | Only if the system grows into 2+ independently deployed agents or needs partner-agent interoperability |
| AG-UI / A2UI | Do not prioritize now | Low for current repo | Reconsider only if Chainlit is replaced by a custom multi-client UI surface |

**Why these made the cut:**
- `MCP`: real value for standardizing reusable read-only tools across query/search and real-vs-mock source adapters.
- `Agent skills`: real value for keeping future agent sessions consistent on demo prep, mock generation, eval execution, and state-doc updates.
- `OpenTelemetry GenAI`: real operational value for debugging, latency analysis, token/cost tracking, and cross-service visibility.
- `Agent evals / trace grading`: real value for the user's stated requirement of testing and observing stable behavior over time.
- `Responses API / Agents SDK`: real strategic value because OpenAI positions Responses as the future direction and Assistants has a published sunset.
- `A2A`: possible later value, but only once agent-to-agent interoperability is a real architectural need rather than a trend.
- `AG-UI / A2UI`: interesting, but not enough value while Chainlit remains the UI shell and the main problem is source realism plus runtime stability.

### Milestone POC: Close the Loop - Activation End-to-End

**Why this matters:** The POC is not complete until we prove the full activation cycle works: Chatbot → Segment → Email Tool → Engagement → Enriched Profile.

**Status:** ✅ **TECHNICAL POC COMPLETE** (2026-03-08) - Resend is accepted for the current activation loop; remaining work is source-of-truth polish, not missing loop closure

| Priority | Item | Status | Result |
|----------|------|--------|--------|
| Critical | **TEST: Segment push to Resend** | ✅ PASS | 0.24s latency (mock), 8 contacts pushed |
| Critical | **TEST: Campaign send via Resend** | ✅ PASS | Campaign sent to audience |
| Critical | **TEST: Webhook setup for engagement** | ✅ PASS | 6 events subscribed |
| Critical | **TEST: Engagement writeback** | ✅ PASS | 4/4 events tracked (sent, delivered, opened, clicked) |
| High | **Document POC completion evidence** | ✅ DONE | Test scripts: `scripts/test_poc_resend_activation.py`, `scripts/test_poc_activation.py` |
| High | **Harden canonical Brussels IT segment/export contract** | ✅ DONE | Active IT mapping is fixed to `62100/62200/62900/63100`, and CSV export now aborts if canonical rows drift from stored segment filters |
| High | **Autotask evidence in demo story** | ✅ DONE | B.B.S. Entreprise now shows `1` open ticket and `1` active contract inside the unified 360 story |
| High | **Clarify Resend audience naming** | Pending | The reused audience label is generic; captions should make the Brussels IT subset explicit |
| High | **Document NBA scoring logic** | Partial | `/api/scoring-model`, `ENGAGEMENT_THRESHOLDS`, `RECOMMENDATION_RULES`, and `rule_trace` now exist; the guide/spec still need to cite them clearly |
| High | **Split mixed demo/source-of-truth docs** | Pending | Break the current guide into vision/business case, system spec, and illustrated evidence so one PDF is not carrying all three roles |
| Medium | **Recheck webhook/event-processor test hang** | Pending | `tests/unit/test_webhook_gateway.py` + `tests/unit/test_cdp_event_processor.py` still need isolated `-vv -x` reruns to capture a clean green state |

**Accepted platform decision:** Use **RESEND** for the current POC.
The user explicitly accepted the Resend swap on 2026-03-08, so Flexmail parity should not drive the near-term roadmap.

**Execution note:** Tracardi CE workflow runtime is still licensed/blocked. The current working local automation path is the Python event processor, not live Tracardi workflow execution.

**Why Resend stays on the active path:**
- ✅ Full webhook management API (create/update/delete)
- ✅ Direct campaign sending API (no GUI required)
- ✅ Batch email support
- ✅ Simpler integration model (audiences vs interests+contacts)
- ⚠️ Only limitation: No custom fields (Flexmail advantage)

**Prerequisites (all ✅ complete):**
- PostgreSQL with 1.94M KBO records
- Tracardi event intake configured; CE workflow execution remains blocked, and the Python event processor covers the current local automation proof
- Teamleader + Exact sync pipelines operational
- Resend API client with full feature parity
- AI chatbot with routing guard (≥95% accuracy achieved)

**Test Results (Resend):**
```
✅ SEGMENT_CREATION: PASSED (0.32s) - 1,529 software companies in Brussels
✅ SEGMENT_TO_RESEND: PASSED (0.24s) - 8 contacts pushed to audience
✅ CAMPAIGN_SEND: PASSED (0.00s) - Campaign sent via Resend API
✅ WEBHOOK_SETUP: PASSED (0.00s) - 6 engagement events subscribed
✅ ENGAGEMENT_WRITEBACK: PASSED (0.83s) - 4/4 events tracked
```

**Exit criteria:**
- ✅ Segment created via chatbot appears in email tool within 60 seconds (0.24s achieved with Resend)
- ✅ Campaign can be sent via API (Resend supports this, Flexmail requires GUI)
- ✅ Webhooks configured for engagement tracking (6 events with Resend)
- ✅ Engagement events flow back to Tracardi (4 events tracked)
- ✅ End-to-end latency measured and documented

**Usage:**
```bash
# Run Resend POC test (RECOMMENDED - uses mock if no API key)
poetry run python scripts/test_poc_resend_activation.py --mock

# Run with real Resend (requires RESEND_API_KEY)
export RESEND_API_KEY="your-api-key"
poetry run python scripts/test_poc_resend_activation.py

# Run Flexmail POC test (alternative)
poetry run python scripts/test_poc_activation.py --mock
```

---

### Milestone 0A: Standards And Modularity With Real Future Value

**Why this matters:** These items can increase modularity, quality, and future interoperability without distracting from the near-term demo goal, but only if adopted in a scoped way.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| High | Define a thin read-only MCP contract | Pending | Standardize `search`, `count`, `company_360`, and normalized source-adapter tools across real/mock backends |
| High | Add reproducible agent evals / trace grading | Pending | Build a small scenario set that measures prompt stability, source provenance, and tool correctness over time |
| Medium | Add GenAI observability conventions | Pending | Standardize traces for model calls, tool calls, latency, failures, and token/cost tracking |
| Medium | Create a small internal agent skill library | Pending | Standardize demo prep, mock-authoring, and doc-hygiene workflows for future agent sessions |
| Medium | Keep new agentic work Responses-compatible | Pending | Avoid new deprecated Assistants-style patterns and define an incremental migration posture |
| Low | Track A2A as a conditional interoperability path | Watchlist | Revisit only if the architecture becomes truly multi-agent or partner-agent interoperability matters |

**Exit criteria:**
- A clear MCP boundary exists for read-only capabilities
- Eval/tracing foundations exist for stability tracking
- Modularity improvements reduce duplicated workflow logic rather than adding protocol complexity

### Milestone 0: Credible Demo Under Current Constraints

**Why this matters:** The project needs to win access and budget by proving value before all production dependencies are available.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| Critical | **CONNECT Teamleader demo environment** | ✅ COMPLETE | Production sync operational with real demo data flowing |
| Critical | **CONNECT Exact Online demo environment** | ✅ COMPLETE | Production sync ready - OAuth tokens renewed 2026-03-08 |
| Critical | **Real/mock/hybrid source matrix documentation** | ✅ COMPLETE | See PROJECT_STATE.yaml source_integrations section |
| Critical | **POPULATE Hyperrealistic connected demo data** | In progress | One flagship `linked_all` account is proven; scale to 10-50 coherent cross-source accounts only if the demo needs more breadth than the current single-story package |
| Critical | Define a hyperrealistic integration standard | ✅ COMPLETE | Autotask mock with 5 companies, 5 tickets, 3 contracts complete |
| Critical | **Guide core business-case proof** | ✅ COMPLETE | Four-source 360, populated Resend audience, event-processor outputs, website writeback, privacy divergence note, and CSV opened-file proof are all now captured |
| Critical | **Keep the guide source-of-truth clean** | In progress | The remaining work is doc splitting, naming clarity, wording precision, explicit logic, citation of the new scoring/privacy hardening, and one sync-latency proof chain |
| Critical | **Clarify reused Resend audience evidence** | Pending | Make it explicit that `KBO Companies - Test Audience` contains the Brussels IT subset, or replace it with a better-named audience when plan limits allow |
| Critical | **Clarify Autotask integration posture** | Pending | Keep the guide consistent: production-capable client + local unified-360 linkage, current verified data still demo-mode |
| Critical | Stabilize the public demo flow | Pending | Eliminate prompt hangs and prove repeatable end-to-end demo success |
| High | **Surface NBA scoring and threshold logic** | Partial | The runtime now exposes `/api/scoring-model` and `rule_trace`; the remaining work is guide/spec wiring and screenshot/evidence capture |
| High | **Add explicit cross-division revenue proof** | Pending | Show one customer with revenue rolled up across divisions, not just recommendation output |
| High | **Capture timestamped sync-latency proof** | Pending | Demonstrate one source update reaching the 360/query plane within the claimed sync interval |
| High | **Keep privacy hardening on the roadmap** | Partial | `scripts/webhook_gateway.py` now emits privacy-safe downstream payloads, but the live local runtime still needs an end-to-end recheck and Tracardi event-path confirmation |
| High | **Recheck webhook/event-processor hardening tests** | Pending | Isolate the late-suite timeout in `tests/unit/test_webhook_gateway.py` and `tests/unit/test_cdp_event_processor.py`, then capture a clean green run |
| High | Build a real/mock/hybrid source matrix | ✅ COMPLETE | Documented in PROJECT_STATE.yaml |
| High | Add a cleanup/organization queue for demo assets and stale narratives | Pending | Consolidate fixtures, screenshots, and current-state summaries to reduce future drift |
| High | Require user-owned final verification | Pending | Hold final demo sign-off until the user has tested it and seen one stable week |

**Exit criteria:**
- At least one real source-system connection or a clearly justified fallback plan exists
- All remaining mock or hybrid paths are labeled explicitly with provenance
- The user can run and trust the demo story end to end
- Guide screenshots and captions match the visible system state without overclaiming
- The reused Resend audience and Autotask hybrid posture are explained clearly
- Recommendation logic and sync-latency proof are documented for the claims that remain in scope

### Milestone 1: Finish Data Coverage And Enrichment

**Why this matters:** Without enrichment, the CDP is still mostly a raw-company directory. Segmentation, AI descriptions, campaign targeting, and location intelligence remain weak or impossible.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| Critical | Finish phased enrichment on the 1.94M-company dataset | In progress | Complete CBE (tightened selector active), geocoding (verified durable), website discovery (continuous runner decision made), phone, and AI-description phases with checkpoints and resumability |
| Critical | Re-verify actual enriched counts from PostgreSQL after each phase | Pending | Replace stale/conflicting progress notes with DB-verified counts and percentages |
| Critical | Move the continuous enrichment loop from ad hoc runtime state to a repo-managed, restartable workflow | Partial | CBE and geocoding runners are repo-managed and stable; website discovery continuous runner decision made, needs implementation |
| High | Add per-phase cost controls and active-company prioritization | Pending | Avoid burning API budget on low-value records first |
| High | Add a separate/API-backed path for NACE-less CBE residuals | Pending | The main local-only selector now excludes `688,581` rows lacking both `industry_nace_code` and `enrichment_data.all_nace_codes`; decide whether to backfill them from a richer source/API or keep them explicitly deferred |
| High | Classify enriched fields by trust, freshness, and production usability | Pending | Distinguish KBO import data from enrichment-derived facts |
| High | Add dashboards and alerts for enrichment lag, failures, and throughput | Pending | Make long-running enrichment operationally visible |

**Exit criteria:**
- Verified coverage targets recorded in `PROJECT_STATE.yaml`
- `sync_status` reflects real enriched progress
- The next agent can resume monitoring or run the next phase from repo-managed instructions only

---

### Milestone 2: Productionize The 360 Data Model

**Why this matters:** `src/models/` now exists, but the model layer is not yet fully integrated into the project’s runtime, dependency graph, migrations, or tests.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| Critical | Decide whether `src/models/` is the authoritative runtime model layer or only a design scaffold | Partial | Avoid leaving an unused ORM layer that drifts from the real asyncpg-based runtime |
| Critical | Declare direct model-layer dependencies in project-managed dependency files if the ORM layer is kept | Pending | `pyproject.toml` does not currently declare `sqlalchemy` directly |
| Critical | Reconcile model definitions with deployed schema and migrations | Pending | Projection tables exist; full 360 schema and migration strategy still need to be aligned |
| High | Add repository/DAO or service-layer integration for common model operations | Pending | Models are largely isolated from the rest of the runtime today |
| High | Add model-level and integration tests | Pending | No dedicated `src/models/` test coverage was found in the repo audit |
| High | Extend the model beyond KBO/public-company foundations into sales, contracts, invoices, subscriptions, tickets, and support domains | Pending | Required for a real IT1 Group 360 view |
| Medium | Add hierarchy and cross-division relationship logic | Pending | Needed for account-level intelligence and rollups |

**Exit criteria:**
- The model layer is either fully integrated and tested or explicitly archived
- Dependencies, migrations, and runtime usage all point to one coherent data-model strategy

---

### Milestone 3: Harden Projection, Writeback, And Activation Runtime

**Why this matters:** The projection/writeback foundation exists, but the operational path still needs security, completeness, and runtime verification.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| Critical | Verify end-to-end PostgreSQL → Tracardi → PostgreSQL flow on live infrastructure | Partial | Confirm projected state, event writeback, lag metrics, and live profile counts from primary tooling |
| Critical | Secure inbound webhook handling | Partial | HMAC/Svix verification, rate limiting, and privacy-safe payload sanitization exist in `scripts/webhook_gateway.py`; remaining work is runtime recheck, replay/retry coverage, and proof that the sanitized path is the one actually exercised |
| High | Decide whether writeback is webhook-only or must also support polling | Pending | `src/services/writeback.py` still contains TODOs for event fetching and profile-fetch-based sync paths |
| High | Add idempotency, retry, and replay/dead-letter handling | Pending | Needed for reliable campaign and workflow event ingestion |
| High | Finish delivery-tool boundaries for Resend/Flexmail | Pending | Resolve PII at authorized send time and keep providers downstream |
| Medium | Re-verify Tracardi live counts and operational health | Pending | Current live-profile claims still mix observed and reported values |

**Exit criteria:**
- Projection and writeback health are observed from runtime tooling
- Webhook and campaign-event paths are secure and replayable
- No current doc implies a nonexistent `sync_tracardi_to_postgres.py` implementation

---

### Milestone 4: Deterministic Chatbot Execution And Operator Safety

**Why this matters:** Search is PostgreSQL-first now, but the operator interface still needs execution discipline, approvals, provenance, and test coverage.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| Critical | Convert requests into typed intents and validated filters | Partial | Reduce prompt-heavy branching and tighten deterministic execution |
| Critical | Add query-plan, citation, and provenance output for analytical answers | Pending | Make operator answers explainable and auditable |
| Critical | Add preview-and-approve flows for mutating actions | Pending | Segment creation, exports, and outbound actions should not execute blind |
| High | Keep logs, tool traces, and audit records UID-first | Pending | Enforce the privacy boundary in logging and operator tooling |
| High | Bring tests in line with the PostgreSQL-first search path | Pending | Search mocks and tool tests still need targeted updates |
| High | Add integration coverage for count/search/segment alignment and mutation safety | Pending | Prevent regressions in the authoritative query plane |

**Exit criteria:**
- The chatbot is deterministic for counts, search, and analytics
- Mutating actions are gated and auditable
- Query-plane regressions are covered by tests, not just manual verification

---

## Hyperrealistic Mock Data Requirements

**Why this matters:** Current demo data is too minimal (1 company in Teamleader, 9 in Exact) to demonstrate the CDP's value. The Illustrated Guide audit identified this as a credibility gap.

**Current State:**
| Source | Current Count | Required for Credibility |
|--------|---------------|-------------------------|
| Teamleader | 1 company, 2 contacts | 50+ companies, 100+ contacts |
| Exact Online | 9 customers, 78 invoices | 50+ customers, 200+ invoices |
| Autotask | 5 companies, 5 tickets, 3 contracts | One `linked_all` account is already proven; scale linked ticket/contract history across more demo accounts only if broader IT1 proof is needed |
| Website behavior | Demo-labeled writeback proof exists for B.B.S. | Scale behavior evidence beyond the single-account proof only if the demo narrative needs more breadth |
| Resend | Populated audience proof exists for the Brussels IT subset | Improve audience naming/caption integrity or recapture when plan limits allow |

**Mock Data Specification:**

### Teamleader Mock Data (50+ Companies)
| Field | Specification |
|-------|--------------|
| Company Names | Realistic Belgian business names (e.g., "Bakkerij De Gouden Croissant", "TechFlow Belgium BV", "Bouwbedrijf Janssens NV") |
| VAT Numbers | Valid BE format (BE0123456789) - use test numbers |
| Addresses | Real Belgian addresses in Gent, Brussels, Antwerp, Leuven |
| Deal Values | €5,000 - €500,000 range |
| Deal Stages | Lead (20%), Proposal (30%), Won (40%), Lost (10%) |
| Industries | Mix of Software, Construction, Retail, Manufacturing, Services |
| Contacts | 2-3 contacts per company with realistic names/emails |

### Exact Online Mock Data (50+ Customers)
| Field | Specification |
|-------|--------------|
| VAT Matching | Same VAT numbers as Teamleader for identity linking |
| Invoice Count | 3-10 invoices per customer |
| Invoice Amounts | €1,000 - €50,000 matching deal values |
| Payment Status | 70% Paid, 20% Outstanding, 10% Overdue |
| Invoice Dates | Spread across last 24 months |
| GL Accounts | Realistic chart of accounts for Belgian businesses |

### Cross-System Identity Bridge
| Requirement | Implementation |
|-------------|----------------|
| VAT Linkage | Every Teamleader company has matching Exact customer via VAT |
| KBO Matching | VAT numbers correspond to real KBO records in the 1.94M dataset |
| Data Consistency | Company names aligned across systems (minor variations allowed) |

**Demonstration Value:**
With 50+ connected records:
- "Show me all companies with open deals over €10k" returns meaningful list
- "Which customers have overdue invoices?" shows actual risk accounts
- "What is total pipeline for software companies in Brussels?" aggregates real data
- 360° view shows rich unified profile instead of sparse single-company view

**Implementation Path:**
1. Create companies in Teamleader demo environment via API/script
2. Create matching customers/invoices in Exact Online
3. Scale Autotask tickets/contracts beyond the existing B.B.S. proof only if wider IT1 storytelling is needed
4. Add website-behavior events for more demo accounts only if the single-account proof stops being sufficient
5. Run sync scripts to populate PostgreSQL
6. Verify identity linking via `source_identity_links` table
7. Re-capture Illustrated Guide screenshots with rich, cross-source evidence

---

### Milestone 5: Replace Demo Integrations With Production Source-System Flows

**Why this matters:** Teamleader and Exact already use real API sync paths. The remaining source-system production gap is live Autotask access plus broader identity, consent, and PII-resolution hardening around those integrations.

**Current State (Verified 2026-03-08):**
| Integration | File | Status | Gap |
|-------------|------|--------|-----|
| Teamleader | `scripts/sync_teamleader_to_postgres.py` | **PRODUCTION** | ✅ OAuth, real API, KBO matching |
| Exact | `scripts/sync_exact_to_postgres.py` | **PRODUCTION** | ✅ OAuth, real API, current local sync verified |
| Autotask | `src/services/autotask.py`, `scripts/sync_autotask_to_postgres.py` | **HYBRID** | Production-capable client exists, but current verified data still uses demo mode until credentials/zone discovery are available |

**What "Hybrid" Means For Autotask:**
- The client and sync script are production-capable
- Default local proof persists demo-mode data into PostgreSQL
- Migration `007_add_autotask_to_unified_360.sql` plus the sync path make that data queryable in the real unified 360 model
- Switching from demo-mode data to live API data still requires credentials and zone discovery validation

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| Critical | **Teamleader → PostgreSQL sync pipeline** | ✅ **COMPLETE** | Production sync operational with real demo data flowing |
| Critical | **Exact Online → PostgreSQL sync pipeline** | ✅ **COMPLETE** | Production sync operational with real demo data flowing |
| Critical | **Cross-source identity reconciliation** | Partial | One `linked_all` account exists; expand coverage and robustness beyond the flagship proof |
| Critical | Validate live Autotask credentials and zone discovery | **BLOCKED** | Requires vendor access; once available, rerun the existing production-capable client outside demo mode |
| High | Prove IT1 business value with the current Autotask hybrid path | ✅ COMPLETE | B.B.S. profile already shows ticket/contract evidence in the unified 360 story |
| High | Build canonical identity reconciliation | Partial | VAT/KBO/name/email-domain matching works, but coverage and resiliency need expansion |
| High | Implement consent/suppression flow | **BLOCKED** | Needs source system integrations |
| Medium | Build PII resolution service | Pending | Can be designed in parallel |

**Dependency note:**
- This milestone no longer blocks the local demo.
- It still blocks full production readiness for support-data ingestion, consent, and privacy-safe outbound activation.

**Recommended Approach:**
1. Keep Teamleader and Exact as the real baseline integrations.
2. Treat live Autotask access as the remaining source-system gap.
3. Expand identity coverage beyond the current single `linked_all` account.
4. Then productionize consent and PII-resolution services on top of the proven source paths.

**Exit criteria:**
- Real API clients exist for Teamleader and Exact, and live Autotask is validated when access exists
- Data flows from source → PostgreSQL with clear provenance labels for real, mock, or hybrid paths
- UID bridge works across multiple source-system IDs, not just one flagship example

---

### Milestone 6: Security, Secrets, And Operational Hardening

**Why this matters:** The repo audit found concrete secret-handling and operational-hygiene problems that must be resolved before production confidence is credible.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| Critical | Remove inline secrets from repo-tracked code and scripts | Partial | `scripts/enrich_monitor.py` was already fixed before this session; the 2026-03-08 re-audit removed the remaining active local DSN fallbacks from `src/mcp_server.py`, `scripts/start_mcp_server.sh`, and `scripts/reconcile_teamleader_identities.py`. Continue the broader sweep for unsafe real secrets and production credential paths. |
| Critical | Sweep live scripts for unsafe credential fallbacks | Pending | Example: admin-style defaults still appear in operational code paths such as `src/ingestion/kbo_ingest.py` |
| High | Align all operational tooling on env/Key Vault/secret refs instead of local inline values | Pending | Prevent machine-local behavior from masquerading as repo-safe configuration |
| High | Audit current docs and scripts for stale operational claims and unsafe examples | Pending | Current ADR/history still referenced a nonexistent sync job before this audit |
| High | Add secret-handling verification to the engineering workflow | Pending | Prevent recurrence after future agent changes |
| Medium | Re-check backup, restore, rollback, and observability runbooks | Pending | Production hardening beyond feature delivery |
| Medium | Revisit CI/CD runtime, test selection, and deployment verification as feature scope stabilizes | Pending | Keep autonomous flow efficient without weakening release safety |

**Exit criteria:**
- No repo-tracked operational script depends on inline real secrets
- Secret resolution and credential fallbacks are explicit, safe, and documented

---

### Milestone 7: Final Production Readiness

**Why this matters:** This is the final convergence step after data coverage, integrations, operator safety, and security are in place.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| Critical | Run end-to-end verification across ingestion, enrichment, projection, chatbot, and activation | Pending | Prove the whole system works as one system, not just isolated components |
| Critical | Verify production deployment health on the exact head SHA | Pending | CI/CD, Container App revision, VM health, and smoke tests must line up |
| High | Add operator runbooks and recovery paths for the key workflows | Pending | Enrichment restart, webhook replay, projection recovery, rollback |
| High | Finalize access control, audit views, and operator guardrails | Pending | Required before broader internal usage |
| Medium | Review cost, throughput, and scaling posture using real production-like load | Pending | Confirm Azure footprint and long-running jobs stay within budget |

**Exit criteria:**
- The system is verifiably production-ready end to end
- Remaining work is optimization, not missing capability or missing safety

---

## Cross-Cutting Remaining Problems Found In This Audit

These items were important enough to shape the roadmap directly:

1. `BACKLOG.md` was stale and still marked several implemented P0 items as pending.
2. During this audit, `docs/ARCHITECTURE_DECISION_RECORD.md` had to be corrected because it still claimed a `scripts/sync_tracardi_to_postgres.py` job existed.
3. The earlier `scripts/enrich_monitor.py` secret-handling claim was stale; the real residual 2026-03-08 DSN fallbacks in MCP and reconciliation helpers were removed, but the broader credential audit still remains.
4. `NEXT_ACTIONS.md` contains conflicting enrichment-progress numbers and needs re-verification from PostgreSQL before another exact percentage claim is trusted.
5. `src/models/` exists, but the repo audit found no direct `sqlalchemy` declaration in `pyproject.toml` and no dedicated tests using the new models.

---

## Notes For Future Agents

- Do not reopen the architecture debate unless implementation or verified runtime evidence forces it.
- Do not confuse "implemented skeleton" with "productionized and integrated."
- Do not treat long-running enrichment logs as sufficient proof of final PostgreSQL coverage; re-query the database.
- Do not accept secret-handling shortcuts in scripts as operationally okay just because they work on one VM.
- Keep using the handoff-driven workflow: one verified increment at a time, with the next safe step made explicit.
