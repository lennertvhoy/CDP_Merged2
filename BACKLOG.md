# CDP_Merged Backlog

**Platform:** Azure target architecture with local-only execution mode
**Azure Scope:** Next cloud re-entry should be limited to Entra ID auth + Azure OpenAI
**Architecture:** Source systems PII truth + PostgreSQL intelligence truth + Tracardi activation runtime + AI chatbot  
**Last Updated:** 2026-03-09 (repo audit backlog pass added security, hygiene, and legacy-surface follow-up alongside the current local-first roadmap)
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
- Azure usage limit is reported reached until `2026-03-14`, so new Azure work is blocked until that reset
- enrichment is now the top operational priority
- **DEMO ENVIRONMENTS AVAILABLE:** Teamleader and Exact demo envs accessible for integration
- Autotask already has a production-capable client/sync path plus local unified-360 linkage, but the currently verified dataset still runs in demo mode until vendor access is granted
- Resend is the accepted email activation platform for the current POC; Flexmail parity is not a near-term blocker unless the user explicitly reopens it
- AI descriptions should use `Ollama`, not Azure OpenAI
- do **not** put the project online before Microsoft Entra ID auth exists
- when Azure work resumes, limit the first scoped re-entry to `Entra auth + Azure OpenAI`; keep PostgreSQL, Tracardi, and the rest of the runtime local
- colleague-facing rollout should use Microsoft work accounts with per-user chat history/workspace, not a shared chatbot surface
- the current Chainlit surface is a baseline only; the colleague-facing product should feel closer to ChatGPT and may include web search once privacy/policy boundaries are defined
- longer-term deployment target is the user's datacenter via Kubernetes (k3s/RKE2), not a return to full Azure app hosting
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

**Status:** ✅ **TECHNICAL POC COMPLETE** (2026-03-08) - Resend is accepted for the current activation loop; the guide now credibly proves the core CDP+AI POC slice, and the remaining work is a v3.3 credibility/presentation pass rather than missing loop closure

**Scope note:** As of the 2026-03-08 v3.2 review, the guide conforms well to the core POC/business-case logic (360 profile, NL segmentation, activation, engagement, revenue/identity proof), but it does **not** yet prove the full broader future-state scope across live website analytics, ads/social, group-wide web tracking, or formal governance criteria.

| Priority | Item | Status | Result |
|----------|------|--------|--------|
| Critical | **TEST: Segment push to Resend** | ✅ PASS | 0.24s latency (mock), 8 contacts pushed |
| Critical | **TEST: Campaign send via Resend** | ✅ PASS | Campaign sent to audience |
| Critical | **TEST: Webhook setup for engagement** | ✅ PASS | 6 events subscribed |
| Critical | **TEST: Engagement writeback** | ✅ PASS | 4/4 events tracked (sent, delivered, opened, clicked) |
| High | **Document POC completion evidence** | ✅ DONE | Test scripts: `scripts/test_poc_resend_activation.py`, `scripts/test_poc_activation.py` |
| High | **Harden canonical Brussels IT segment/export contract** | ✅ DONE | Active IT mapping is fixed to `62100/62200/62900/63100`, and CSV export now aborts if canonical rows drift from stored segment filters |
| High | **Autotask evidence in demo story** | ✅ DONE | B.B.S. Entreprise now shows `1` open ticket and `1` active contract inside the unified 360 story |
| High | **Clarify Resend audience naming** | Partial | The prose now explains the Brussels IT subset, but the visible screenshot still says `KBO Companies - Test Audience`; one final capture or caption rewrite is still needed |
| High | **Document NBA scoring logic** | ✅ DONE | `/api/scoring-model`, `ENGAGEMENT_THRESHOLDS`, `RECOMMENDATION_RULES`, and `rule_trace` now exist; documented in guide |
| High | **Split mixed demo/source-of-truth docs** | ✅ DONE | Split into BUSINESS_CASE.md (vision/value), SYSTEM_SPEC.md (architecture/APIs), and streamlined ILLUSTRATED_GUIDE.md (evidence only) |
| High | **Publish business-case conformity matrix** | Pending | Map the business-case requirements to current evidence as `Conforms`, `Partial`, or `Not yet covered`, so the guide's POC scope is explicit instead of implied |
| High | **Add acceptance-criteria appendix** | Pending | Show the `>=95%` prompt/tool-selection proof, audit-log/API-call control evidence, and deploy/IaC repeatability status in a reviewer-friendly appendix |
| High | **Fix guide evidence timestamp consistency** | Pending | Pages 8-9 still mix `2024-03-08` API timestamps into a guide otherwise dated `2026-03-08`; regenerate or relabel the evidence |
| High | **Add canonical count semantics dictionary** | Pending | Define explicit rules: base rows, verified-email rows, deduped activation contacts, test-scope rows (per v3.0 feedback) |
| High | **Upgrade CSV export integrity proof** | Partial | Opened-artifact page is now self-contained with scope, row count, field coverage, and timestamp/source traceability; checksum/query ID proof still missing |
| Medium | **Implement maturity label system** | Partial | Guide now labels evidence as Live system, Local runtime, Demo-backed, and Local artifact, but the full maturity system is not yet applied everywhere and the Autotask readiness wording still needs tightening |
| Medium | **Fix privacy statement wording precision** | ✅ DONE | Top-line privacy wording now matches the divergence table and no longer implies a fully sanitized runtime |
| Medium | **Improve guide API/code evidence styling** | Pending | Pages 8-11 still read like flat request/response dumps instead of deliberate evidence boxes |
| Medium | **Improve PDF text-layer/export quality** | Pending | Investigate ligature/encoding artifacts so copy/paste, searchability, and accessibility are clean |
| Medium | **Recheck webhook/event-processor test hang** | ✅ DONE | Both suites now pass cleanly (54 tests in 0.33s); issue resolved, likely by prior hardening |

**Accepted platform decision:** Use **RESEND** for the current POC.
The user explicitly accepted the Resend swap on 2026-03-08, so Flexmail parity should not drive the near-term roadmap.

**Execution note:** Tracardi CE workflow runtime is still licensed/blocked. The current working local automation path is the Python event processor, not live Tracardi workflow execution.

**Why Resend stays on the active path:**
- ✅ Full webhook management API (create/update/delete)
- ✅ Direct campaign sending API (no GUI required)
- ✅ Batch email support
- ✅ Simpler integration model (audiences vs interests+contacts)
- ⚠️ Only limitation: No custom fields (Flexmail advantage)

**Prerequisites (technical flow ready; acceptance-style packaging still incomplete):**
- PostgreSQL with 1.94M KBO records
- Tracardi event intake configured; CE workflow execution remains blocked, and the Python event processor covers the current local automation proof
- Teamleader + Exact sync pipelines operational
- Resend API client with full feature parity
- AI chatbot with routing guard in place; the guide still needs a reviewer-friendly appendix if the `>=95%` acceptance criterion must be shown explicitly

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
| High | Add reproducible agent evals / trace grading | Partial | `docs/evals/` now contains a starter bank, scorecard template, validation test, and a repo-owned run-prep harness (`scripts/prepare_operator_eval_run.py` + `src/evals/operator_eval_run_prep.py`); still need live-chatbot execution and scored baseline artifacts |
| High | Standardize self-contained eval prompt format | Partial | A canonical template plus `operator_eval_cases.v1.json` now exist under `docs/evals/`, and the run-prep harness can bundle them per revision; full historical scenario migration and live execution still need to happen |
| Medium | Add GenAI observability conventions | Pending | Standardize traces for model calls, tool calls, latency, failures, and token/cost tracking |
| Medium | Create a small internal agent skill library | Pending | Standardize demo prep, mock-authoring, and doc-hygiene workflows for future agent sessions |
| Medium | Keep new agentic work Responses-compatible | Pending | Avoid new deprecated Assistants-style patterns and define an incremental migration posture |
| Low | Track A2A as a conditional interoperability path | Watchlist | Revisit only if the architecture becomes truly multi-agent or partner-agent interoperability matters |

**Exit criteria:**
- A clear MCP boundary exists for read-only capabilities
- Eval/tracing foundations exist for stability tracking
- Modularity improvements reduce duplicated workflow logic rather than adding protocol complexity

**2026-03-09 user-feedback implications:**
- Eval prompts should be self-contained by default so each test still works if the previous conversation turns are wiped.
- The eval bank should include the visible product-failure cases from the screenshots, especially the `ClipboardItem is not defined` copy failure and export flows that return an internal path instead of a real download.
- Future scoring should separate `intent`, `autonomy`, `trust`, `actionability`, and `UX/product polish` so strong analysis does not hide weak operator experience.
- The first concrete assets now exist in `docs/evals/`, and a run-prep harness now emits per-run bundles, but live-chatbot execution and scoring still need to be wired in.

### Milestone 0B: Privacy-Critical Hybrid Azure Re-Entry

**Why this matters:** The user does not want to put the project online until authentication is handled through Microsoft Entra ID and the public-facing LLM path uses Azure OpenAI. At the same time, the rest of the stack should remain local for now, the colleague-facing access path should use Microsoft work accounts, and the longer-term deployment target is an internal server farm.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| Critical | Put Microsoft Entra ID work-account auth in front of any public deployment | Partial | App registration, callback/config wiring, and local feature-flag support are implemented. Remaining work is client-secret rotation, tenant/domain policy confirmation, and end-to-end sign-in verification after the reported `2026-03-14` quota reset |
| Critical | Use Azure OpenAI for the public-facing chatbot path | Blocked until `2026-03-14` | Re-enable the Azure OpenAI provider path, verify config/env handling, and document when public mode must use Azure OpenAI rather than a non-Azure provider |
| High | Keep the rest of the platform local during this phase | Pending | Do not reopen full Azure hosting for PostgreSQL, Tracardi, or the compose stack just to satisfy auth/LLM compliance requirements |
| High | Define the internal server-farm deployment target | Pending | Design the eventual on-prem/runtime target for the user's internal server farm; evaluate Kubernetes among the candidate deployment models while keeping Azure dependencies limited to Entra ID and OpenAI |
| High | Document the hybrid privacy/compliance posture clearly | Pending | Explain why `Entra auth + Azure OpenAI + local data/runtime` is the interim architecture and what still remains local vs cloud-managed |

**Exit criteria:**
- No public URL exists without Microsoft Entra work-account authentication in front of it
- Azure OpenAI is the active provider for the public-facing chatbot mode
- PostgreSQL, Tracardi, and the remaining runtime stay local until the server-farm deployment path is ready
- The hybrid boundary is documented clearly enough that future sessions do not accidentally reopen full Azure hosting

### Milestone 0C: Internal Server-Farm Deployment Target

**Why this matters:** The ultimate deployment target is the user's internal server farm, not Azure Container Apps. Kubernetes may be the right orchestration layer, but that is still an option to evaluate rather than a locked implementation decision.

**Deployment Path:**
| Phase | Environment | Stack | Purpose |
|-------|-------------|-------|---------|
| Current | Local laptop | docker-compose | Rapid development |
| Staging | Local k3s/k3d or equivalent | Candidate server-farm stack | Production-like testing |
| Target | Internal server farm | Orchestrator TBD | Production deployment |

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| High | Decide the server-farm orchestration model | Pending | Compare k3s/RKE2, simpler container/VM deployment, and other realistic options for the user's internal server farm before hardcoding a new platform layer |
| High | Create deployment manifests for core services | Pending | If Kubernetes wins, prepare Deployments/Services/ConfigMaps/Secrets for PostgreSQL, Tracardi, Elasticsearch, chatbot API, and Chainlit UI; otherwise define the equivalent deployment assets for the chosen stack |
| High | Design persistent volume strategy | Pending | Storage classes, PV claims for PostgreSQL data, Elasticsearch indices, uploaded files |
| High | Configure ingress and TLS | Pending | NGINX/Traefik ingress, cert-manager for internal TLS termination |
| High | Create environment templating structure | Pending | If Kubernetes wins, use Helm or equivalent templating for dev/staging/prod; otherwise define the environment-management pattern that matches the selected stack |
| High | Implement health checks and probes | Pending | Liveness, readiness, startup probes for all services |
| High | Configure scaling and resource limits | Pending | Define CPU/memory limits and scaling behavior for the chosen server-farm deployment model |
| Medium | Set up a reference architecture for the chosen platform | Pending | If Kubernetes wins, document node sizing, etcd backup, and control plane HA; otherwise document the equivalent operational topology |
| Medium | Implement deployment automation | Pending | Use GitOps if Kubernetes wins, otherwise codify the equivalent repeatable deployment flow |
| Medium | Add observability stack | Pending | Prometheus/Grafana/Loki/Jaeger or the equivalent stack that fits the chosen deployment model |
| Medium | Design disaster recovery | Pending | Backup strategies, cluster restore procedures |
| Low | Consider service mesh (Istio/Linkerd) | Watchlist | Evaluate only if Kubernetes becomes the chosen deployment model and mTLS/traffic management are actually needed |

**Migration Strategy:**
1. **Keep docker-compose for rapid local dev** - It's faster for debugging
2. **Evaluate the server-farm runtime shape first** - Do not lock Kubernetes before the tradeoff is explicit
3. **Prototype the chosen path locally** - If Kubernetes wins, use k3s/k3d before any datacenter deployment
4. **Codify environment-specific configuration** - Helm or the equivalent for the chosen stack
5. **Maintain the local path** until the server-farm target is validated

**Azure Boundary Preservation:**
- Entra ID remains the authentication provider (no change)
- Azure OpenAI remains the LLM provider for public-facing mode (no change)
- All application runtime eventually moves out of Azure hosting into the user's internal server farm
- PostgreSQL, Tracardi, and Elasticsearch stay local until the chosen server-farm deployment model is proven

**Exit criteria:**
- The eventual server-farm deployment model is explicitly chosen and documented
- The full stack is deployable in that model from repo-managed artifacts
- Persistent data survives restarts/failover in the chosen environment
- Health checks and rollout behavior work correctly
- Documentation exists for the operators who will run it

### Milestone 0D: Multi-User Chatbot Experience

**Why this matters:** A colleague-facing rollout is not just an auth problem. Each user should have a private chatbot workspace with stored conversations, and the interface should feel closer to ChatGPT than to a default Chainlit shell.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| Critical | Add user-scoped chat persistence and conversation ownership | Partial | Repo-owned `app_chat_*` persistence, per-user thread isolation, browser resume, and first-message titles are verified locally under dev auth. Remaining work is Microsoft Entra-backed verification and any final colleague-facing polish |
| High | Modernize the Chainlit surface toward ChatGPT-like UX | Partial | History continuity and title generation are working; remaining work is tighter sidebar/list affordances, layout polish, and reducing default Chainlit rough edges before broader rollout |
| High | Decide which colleague-facing options belong in the UI | Pending | Define what should be exposed directly to users, such as export actions, search modes, or tool/web-search toggles |
| High | Add web search as a deliberate capability with privacy/compliance guardrails | Partial | Policy enforcement exists in `src/services/web_search_policy.py`, but UX exposure, source attribution, and the final enablement mode are still unresolved |

**Exit criteria:**
- Authenticated users get isolated conversation history and a private workspace
- The product no longer depends on a shared or ephemeral chat session model
- The interface no longer feels like a bare default Chainlit surface
- Web-search behavior is either implemented with clear guardrails or explicitly deferred

### Milestone 0: Credible Demo Under Current Constraints

**Why this matters:** The project needs to win access and budget by proving value before all production dependencies are available.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| Critical | **CONNECT Teamleader demo environment** | ✅ COMPLETE | Production sync operational with real demo data flowing |
| Critical | **CONNECT Exact Online demo environment** | ✅ COMPLETE | Production sync ready - OAuth tokens renewed 2026-03-08 |
| Critical | **Real/mock/hybrid source matrix documentation** | ✅ COMPLETE | See PROJECT_STATE.yaml source_integrations section |
| Critical | **POPULATE Hyperrealistic connected demo data** | In progress | One flagship `linked_all` account is proven; scale to 10-50 coherent cross-source accounts only if the demo needs more breadth than the current single-story package |
| Critical | Define a hyperrealistic integration standard | ✅ COMPLETE | Autotask mock with 5 companies, 5 tickets, 3 contracts complete |
| Critical | **Guide core business-case proof** | ✅ COMPLETE | Four-source 360, populated Resend audience, event-processor outputs, website writeback, privacy divergence note, and CSV opened-file proof are all now captured for the core POC slice; the broader multi-channel business-case scope remains future work |
| Critical | **Keep the guide source-of-truth clean** | ✅ COMPLETE v3.0 | Phase-based proof structure, naming clarity, explicit logic, scoring/privacy citations, sync-latency proof all captured |
| Critical | **Clarify reused Resend audience evidence** | Partial | Guide now labels the Brussels IT subset explicitly, but the visible screenshot still shows the older generic audience name |
| Critical | **Clarify Autotask integration posture** | ✅ COMPLETE | Guide documents hybrid status: production-capable linkage + demo-mode data |
| Critical | Stabilize the public demo flow | ✅ COMPLETE | End-to-end demo flow verified repeatable |
| High | **Publish business-case conformity matrix** | Pending | Turn the current strong POC slice into a requirement-by-requirement `Conforms / Partial / Not yet covered` map against `BUSINESS_CASE.md` |
| High | **Add formal acceptance-criteria reporting** | Pending | Package the `>=95% on 5 prompts`, audit-log/control evidence, and deploy/IaC repeatability criteria so a reviewer can tick them off |
| High | **Fix guide evidence timestamp consistency** | Pending | Per v3.2 review: remove or clearly label the remaining `2024-03-08` API timestamps so the evidence pack has one coherent date story |
| High | **Add canonical count semantics dictionary** | Pending | Per v3.0 feedback: define explicit rules for base rows, verified-email rows, deduped activation contacts, test-scope rows |
| High | **Upgrade CSV export integrity proof** | Partial | Per v3.0 feedback: page is now self-contained and traceable, but checksum/query ID proof still needs to be added |
| High | **Implement maturity label system** | Partial | Per v3.0 feedback: guide now uses Live/Local runtime/Demo-backed/Local artifact labels, but the full system is not yet applied everywhere and Autotask wording still needs a cleaner maturity split |
| High | **Fix privacy statement wording precision** | ✅ COMPLETE | Per v3.0 feedback: top-line wording now matches the divergence table and no longer overstates runtime sanitization |
| High | **Surface NBA scoring and threshold logic** | ✅ COMPLETE | Guide/spec now document `/api/scoring-model`, event weights, thresholds, and the B.B.S. example calculation |
| High | **Add explicit cross-division revenue proof** | ✅ COMPLETE | B.B.S. Entreprise now shows a timestamped `€15,000` cross-source total in the guide |
| High | **Capture timestamped sync-latency proof** | ✅ COMPLETE | Guide now records Teamleader sample syncs at `2026-03-08 14:57:55` and Exact sample syncs at `2026-03-08 11:19:39` |
| High | **Improve guide API/code evidence styling** | Pending | Per v3.2 review: pages 8-11 still feel like a technical export and need boxed/shaded request-response styling |
| High | **Improve PDF text-layer/export quality** | Pending | Per v3.2 review: fix ligature/encoding artifacts that break extracted text and reduce accessibility |
| Medium | **Promote website-behavior proof from demo-labeled to live evidence** | Pending | Current guide proof is local demo-labeled writeback for a real UID; upgrade it only if the business-case scope requires live public-site evidence |
| Medium | **Broaden live channel coverage beyond CRM/email POC** | Pending | Add live Matomo/GA, Google Ads, social, and group-wide website/channel evidence when access exists so the guide can support the broader IT1/NewCo vision |
| High | **Keep privacy hardening on the roadmap** | Partial | `scripts/webhook_gateway.py` now emits privacy-safe downstream payloads, but the live local runtime still needs an end-to-end recheck and Tracardi event-path confirmation |
| High | **Recheck webhook/event-processor hardening tests** | ✅ COMPLETE | Both suites now pass cleanly (`54` tests in `0.33s`); the earlier late-suite timeout is closed |
| High | Build a real/mock/hybrid source matrix | ✅ COMPLETE | Documented in PROJECT_STATE.yaml |
| High | Add a cleanup/organization queue for demo assets and stale narratives | Partial | Historical handoffs and stale planning docs are now archived, duplicate guide-output screenshots are pruned, and the active guide assets are moving under tracked docs paths; broader log/output hygiene can continue incrementally |
| High | Require user-owned final verification | Pending | Hold final demo sign-off until the user has tested it and seen one stable week |

**Exit criteria (v3.0 COMPLETE):**
- ✅ At least one real source-system connection or a clearly justified fallback plan exists
- ✅ All remaining mock or hybrid paths are labeled explicitly with provenance
- ✅ The user can run and trust the demo story end to end
- ✅ Guide screenshots and captions match the visible system state without overclaiming
- ✅ The reused Resend audience and Autotask hybrid posture are explained clearly
- ✅ Recommendation logic and sync-latency proof are documented for the claims that remain in scope

**v3.3 Remaining Precision Improvements (tracked above):**
- Canonical count semantics dictionary for all reported numbers
- Strict CSV export integrity proof with validation and checksum
- Consistent evidence timestamps across the guide's API and screenshot proof
- Maturity label system (Live/Local/Demo-backed/Planned) with tighter Autotask wording
- Reviewer-friendly business-case conformity matrix and acceptance-criteria appendix
- Privacy statement wording aligned exactly with divergence table - ✅ complete

**v3.3 Remaining Formatting / Export Improvements (content direction good, major layout defects closed):**
| Priority | Item | Status | What needs to happen |
|----------|------|--------|----------------------|
| Critical | **Rebuild page 9 screenshot inventory table** | ✅ COMPLETE | Replaced the long filename table with a short evidence-ID matrix plus filename key; PDF export recheck shows the rows render readably |
| Critical | **Rebuild page 10 sync-latency table** | ✅ COMPLETE | Replaced the single wide table with source-specific sync proof tables; PDF export recheck shows no timestamp/company collisions |
| High | **Split page 1 into two pages** | ✅ COMPLETE | Page 1 is now a cover/introduction page and page 2 holds contents |
| High | **Align screenshot-visible audience naming with prose** | Pending | The screenshot still visibly shows `KBO Companies - Test Audience`; either recapture after rename or tighten the caption so the historical UI name is explicit |
| High | **Standardize phase page pattern** | Partial | Early sections now follow claim → evidence → verification more cleanly; finish the same pattern across the full guide |
| High | **Shaded code boxes for API/JSON** | Pending | Replace raw monospaced request/response dumps with contained shaded evidence boxes (pages 8-11) |
| Medium | **Fix page 6 line-break awkwardness** | Pending | Keep the renamed-for-clarity audience note together instead of stranding `for clarity)` across the page break |
| Medium | **Keep privacy divergence table + mitigation note together** | Pending | Reflow the page 10-11 split so the table and interpretation land on one page |
| Medium | **Fix blank space / page economy** | Pending | Tighten later pages, especially the oversized screenshots on page 12 and the sparse narrative page 14 |
| Medium | **Improve PDF text-layer/export quality** | Pending | Eliminate the ligature/encoding artifacts in extracted text so the PDF is searchable and accessible |
| Medium | **Standardize visual hierarchy** | Partial | Screenshot sizing and source labels are more controlled, but caption spacing and page rhythm still need a final pass |

### Milestone 1: Finish Data Coverage And Enrichment

**Why this matters:** Without enrichment, the CDP is still mostly a raw-company directory. Segmentation, AI descriptions, campaign targeting, and location intelligence remain weak or impossible.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| Critical | Finish phased enrichment on the 1.94M-company dataset | Top priority | CBE is complete; keep website discovery and `description_ollama` moving, and close the geocoding visibility gap before claiming that phase is operationally healthy |
| Critical | Re-verify actual enriched counts from PostgreSQL after each phase | Partial | 2026-03-09 direct counts now show `website_url=65,349`, `geo_latitude=53,779`, `ai_description=2,866`, and `cbe_enriched=1,252,019`; keep repeating this after each material runner change |
| Critical | Move the continuous enrichment loop from ad hoc runtime state to a repo-managed, restartable workflow | Partial | CBE, website discovery, and AI descriptions are now repo-managed and restartable; geocoding is also repo-managed, but its current 10,000-row batch still has weak live visibility because the cursor/log only advance on chunk completion |
| High | Add per-phase cost controls and active-company prioritization | Pending | Avoid burning API budget on low-value records first |
| High | Add a separate/API-backed path for NACE-less CBE residuals | Pending | The main local-only selector now excludes `688,581` rows lacking both `industry_nace_code` and `enrichment_data.all_nace_codes`; decide whether to backfill them from a richer source/API or keep them explicitly deferred |
| High | Classify enriched fields by trust, freshness, and production usability | Pending | Distinguish KBO import data from enrichment-derived facts |
| High | Add dashboards and alerts for enrichment lag, failures, and throughput | Pending | Make long-running enrichment operationally visible |
| High | Standardize AI-description enrichment on Ollama | Partial | `DESCRIPTION_ENRICHER=ollama` is already the default local runtime path and the `description_ollama` supervisor relaunched on 2026-03-09 has already completed three chunks; next work is sustained-throughput tuning and better runtime visibility, not provider selection |

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
| Critical | Move SQLAlchemy to the correct dependency boundary if the model layer is kept | Pending | `sqlalchemy` now exists only in dev dependencies even though `src/models/` and `src/repository/` live in the runtime tree; either promote it to runtime dependencies or archive the layer |
| Critical | Reconcile model definitions with deployed schema and migrations | Pending | Projection tables exist; full 360 schema and migration strategy still need to be aligned |
| High | Add repository/DAO or service-layer integration for common model operations | Pending | Models are largely isolated from the rest of the runtime today |
| High | Re-enable and expand model/repository tests if the layer survives | Pending | `tests/unit/repository/` exists, but pytest currently excludes it via `norecursedirs`; either wire it back into the suite or retire the unused repository path |
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
| High | Remove user-visible tool leakage in normal chatbot mode | Pending | Hide internal tool names and planning traces such as `I will use...`, `search_profiles`, or `query_unified_360`; default to answer-first phrasing unless the user explicitly asks for internals |
| High | Add interpretation-first response patterns for operator workflows | Pending | Make the bot explain what low contact coverage, cross-source mismatches, or uncertain data mean operationally instead of only listing fields |
| High | Add explicit validation and uncertainty blocks to 360/stats outputs | Pending | Standardize sections such as `Te valideren`, `Top onzekerheden`, and `Next best action` so account summaries do more than dump source data |
| High | Add end-to-end UX regression coverage for copy and export flows | Partial | Starter self-contained cases now exist in `docs/evals/operator_eval_cases.v1.json`; still need executable runtime coverage against the live chatbot |
| High | Rewrite legacy scenario tests into a self-contained operator eval suite | Partial | `docs/evals/` now defines the prompt standard, v1 starter bank, scorecard template, validation test, and run-prep harness; full scenario migration and live execution still remain |

**Exit criteria:**
- The chatbot is deterministic for counts, search, and analytics
- Mutating actions are gated and auditable
- Query-plane regressions are covered by tests, not just manual verification
- User-facing answers remain trustworthy even when each test starts from an empty conversation state
- Product-quality regressions in copy/export/download behavior are caught before demo use

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
| Critical | Rotate the exposed Microsoft Entra client secret and keep replacements out of tracked docs | Pending | A real `AZURE_AD_CLIENT_SECRET` was written into tracked docs on 2026-03-09; sanitize examples immediately, rotate the credential, and keep future values only in untracked env files or a vault |
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

### Milestone 6A: Repo Hygiene, Legacy Surface, And Documentation Shape

**Why this matters:** The repo audit found several low-glamour but high-leverage cleanup items that will keep future sessions faster, safer, and less confusing.

| Priority | Item | Status | What still needs to happen |
|----------|------|--------|-----------------------------|
| High | Keep Python cache artifacts out of git | Complete | A 2026-03-09 git-tracked recheck found `git ls-files '*.pyc' -> 0` and no `__pycache__` matches; the earlier `find` count referred to local untracked cache files, and `.gitignore` already blocks these paths |
| High | Reconcile legacy script docs with the actual Poetry-based workflow | Complete | Completed 2026-03-09: `scripts/README.md` now points to the repo-root Poetry flow, the stale `scripts/requirements.txt` file was removed, and the historical KBO cleanup completion summary was quarantined so it no longer reads like a current operator guide |
| High | Decide whether to keep or delete `src/enrichment/website_discovery.py.patch` | Complete | Completed 2026-03-09: the tracked file was a zero-byte initial-import artifact with no live non-doc references, so it was deleted |
| Medium | Break up oversized entry points that are accumulating unrelated responsibilities | Pending | `src/app.py`, `src/mcp_server.py`, `src/services/writeback.py`, and `scripts/cdp_event_processor.py` are each several hundred lines and should be split along clearer seams when adjacent work touches them |
| Medium | Reduce current-doc sprawl in `docs/` and make durable references easier to find | Pending | The audit counted `217` files under `docs/`, including `54` top-level docs plus multiple guide PDFs and screenshot trees; keep archiving history, but tighten the durable reference surface that active contributors actually need |

**Exit criteria:**
- Tracked cache artifacts are gone and stay gone
- Script setup guidance matches the real dependency manager and runtime
- Leftover patch or merge debris is either justified or removed
- The active documentation surface is easier to navigate than the archival one

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
5. `src/models/` and `src/repository/` exist, but the layer is still runtime-disconnected: SQLAlchemy only lives in dev dependencies, and pytest excludes the repository tests.
6. A real Microsoft Entra client secret was written into tracked docs; sanitizing the files is necessary but not sufficient because the credential still needs rotation.
7. The earlier `find` audit counted `197` local Python bytecode/cache files under `src/`, `tests/`, and `scripts/`, but a 2026-03-09 git-tracked recheck found `0` tracked `.pyc` or `__pycache__` matches.
---

## Notes For Future Agents

- Do not reopen the architecture debate unless implementation or verified runtime evidence forces it.
- Do not confuse "implemented skeleton" with "productionized and integrated."
- Do not treat long-running enrichment logs as sufficient proof of final PostgreSQL coverage; re-query the database.
- Do not accept secret-handling shortcuts in scripts as operationally okay just because they work on one VM.
- Keep using the handoff-driven workflow: one verified increment at a time, with the next safe step made explicit.
