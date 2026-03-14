# CDP_Merged Backlog v2

**Architecture:** Source systems PII truth + PostgreSQL intelligence truth + Operator shell control plane + Optional Tracardi activation adapter
**Deployment:** Local-only permanent; Azure limited to Entra ID + Azure OpenAI only
**Last Updated:** 2026-03-14
**Purpose:** Actionable roadmap from current state to credible demo, then to production

---

## How To Use This File

- **NOW** = Active execution queue (≤10 items). Pick from here.
- **NEXT** = Immediate follow-up once NOW clears.
- **LATER** = Important but blocked or lower priority.
- **WATCHLIST** = Future standards and trends, not active bottlenecks.

Live state lives in `PROJECT_STATE.yaml` and `STATUS.md`. If files conflict, verify implementation first.

---

## Active Queue

### NOW (≤10 items — pick from here)

| # | Item | Epic | Why It Matters |
|---|------|------|----------------|
| 0 | **Architecture hardening: Tracardi optionalization** | Architecture | Formalize Tracardi demotion from core to optional; update docs, docker-compose, and default stack. Core delivery no longer blocked by CE limitations. |
| 1 | **Operator shell admin/RBAC verification** | Product Shell | Verify admin panel exists (currently 404 at /admin), document RBAC model, confirm is_admin flag usage. |
| 2 | **Guide v3.3 credibility pass** | Demo | Fix timestamp consistency, maturity labels, CSV export proof. Demo packaging > backend work now. |
| 2 | **Business-case conformity matrix** | Demo | Requirement-by-requirement mapping: `Conforms / Partial / Not yet covered`. Makes POC scope explicit. |
| 3 | **Acceptance-criteria appendix** | Demo | `>=95%` prompt/tool-selection proof, audit-log evidence, deploy repeatability for reviewers. |
| 4 | **Decide `src/models/` fate** | Runtime | Keep-and-complete or archive. Half-alive ORM layer causes agent drift. |
| 5 | **Enrichment progress verification** | Enrichment | Re-query PostgreSQL counts after each phase. Don't trust runner logs alone. |
| 6 | **Geocoding visibility fix** | Enrichment | Current batch has weak live visibility (cursor only advances on chunk completion). |
| 7 | **Entra auth verification** | Product Shell | Verify end-to-end sign-in after quota reset (post-2026-03-14). |
| 8 | **Typed intents for chatbot** | Runtime | Convert prompt-heavy branching to validated filters. Deterministic execution. |
| 9 | **Secret rotation + sweep** | Hardening | Rotate exposed Entra client secret; sweep remaining admin-style credential fallbacks. |
| 10 | **User-scoped chat persistence** | Product Shell | Verify conversation ownership works under Entra (already working under dev auth). |

### NEXT (immediate follow-up)

- Preview-and-approve flows for mutating actions
- Query-plan/citation output for analytical answers
- Integration tests for count/search/segment alignment
- Chainlit UX polish (ChatGPT-like sidebar, reduced default rough edges)
- Web search enablement decision (policy exists, UX exposure unresolved)
- Ollama description throughput tuning
- Maturity label system completion (partially done)
- PDF export quality (ligature/encoding artifacts)

### LATER (important but blocked or deferred)

- Live Autotask credentials validation (blocked: vendor access)
- Consent/suppression flow (blocked: needs source system integrations)
- Server-farm deployment target decision (k3s/RKE2 vs alternatives)
- Kubernetes manifests (pending server-farm decision)
- ~~Full Tracardi CE workflow runtime~~ → MOVED TO OPTIONAL/PREMIUM PATH (2026-03-14 decision: Tracardi no longer core dependency)
- Hyperrealistic mock data expansion (50+ companies — only if demo needs breadth)
- Website behavior proof upgrade (only if business case requires live public-site evidence)
- Tracardi Premium activation (only if paid-feature path justified later)

---

## The Five Epics

### Epic 0 — Architecture Hardening (NEW)

**Goal:** Solidify architecture decisions and decouple optional components from core delivery path.

**Decision Recorded 2026-03-14:** Tracardi is demoted from core dependency to optional activation adapter.

| Item | Status | Exit Criteria |
|------|--------|---------------|
| Tracardi optionalization | ✅ Complete | Docker compose profiles implemented; core stack runs without Tracardi; opt-in via `--profile tracardi` |
| Core path verification | Pending | First-party event processor + PostgreSQL satisfy all demo/runtime needs without Tracardi |
| Admin panel verification | Pending | Operator shell admin features verified or documented as not implemented |
| RBAC model documentation | Pending | Access control model documented beyond simple `is_admin` flag |

**Key Principle:** Core delivery should not be blocked by optional component limitations.

---

### Epic 1 — Credible Local Demo

**Goal:** A reviewer can read the guide, run the demo, and trust the evidence.

| Item | Status | Exit Criteria |
|------|--------|---------------|
| Guide v3.3 credibility pass | In progress | Timestamp consistency fixed, maturity labels applied, CSV export has checksum proof |
| Business-case conformity matrix | Pending | `BUSINESS_CASE.md` requirements mapped to current evidence |
| Acceptance-criteria appendix | Pending | `>=95%` prompt/tool proof, audit-log evidence, deploy repeatability |
| Canonical count semantics | Pending | Explicit rules for base rows, verified-email rows, deduped contacts |
| PDF/export quality | Pending | Ligature/encoding artifacts eliminated, copy/paste clean |
| Stable demo path | ✅ | End-to-end flow verified repeatable |

**Key Principle:** The backend is further along than the presentation suggests. Demo packaging is the risk, not capability.

---

### Epic 2 — Enrichment Coverage

**Goal:** Production-usable enriched customer intelligence, not raw KBO imports.

| Item | Status | Exit Criteria |
|------|--------|---------------|
| CBE enrichment | ✅ | 1.25M+ companies enriched |
| Website discovery | Running | Continuous runner, progress visible |
| Ollama descriptions | Running | 2,866+ descriptions, sustained throughput |
| Geocoding | Running | 53,779+ geocoded, visibility gap fixed |
| Per-phase metrics | Partial | Direct PostgreSQL counts established |
| Trust/freshness labeling | Pending | Distinguish KBO import from enrichment facts |

**Execution Mode:** Background throughput program. Monitor but don't let it dominate daily narrative unless demo queries are weak due to sparse data.

**Current Verified Counts (2026-03-09):**
- `website_url`: 65,349
- `geo_latitude`: 53,779
- `ai_description`: 2,866
- `cbe_enriched`: 1,252,019

---

### Epic 3 — Colleague-Facing Product Shell

**Goal:** The project feels like a product, not a technical demo.

| Item | Status | Exit Criteria |
|------|--------|---------------|
| Entra auth | Partial | App registered, config wired; verify post-quota |
| Per-user chat history | ✅ | Repo-owned `app_chat_*` persistence, thread isolation |
| Conversation ownership | Partial | Works under dev auth; verify under Entra |
| Chainlit UX polish | Partial | History/titles work; sidebar/layout polish remains |
| Web search boundary | Partial | Policy exists; UX exposure decision pending |

**Privacy Rule:** No public deployment without Entra ID auth. Colleague-facing rollout uses Microsoft work accounts with private workspaces, not shared chat.

---

### Epic 4 — Data Model and Runtime Hardening

**Goal:** Resolve architectural ambiguity, deterministic execution, operator safety.

| Item | Status | Exit Criteria |
|------|--------|---------------|
| `src/models/` decision | **DECIDE NOW** | Either integrate fully (promote SQLAlchemy, wire tests) or archive |
| Typed intents | Partial | Reduce prompt branching, validated filters |
| Preview/approve mutations | Pending | Segment creation, exports, actions gated |
| Provenance/citations | Pending | Query-plan output for analytical answers |
| Integration tests | Pending | Count/search/segment alignment coverage |
| Audit/log discipline | Pending | UID-first logging, tool traces |

**Critical Decision:** `src/models/` and `src/repository/` exist but are runtime-disconnected. SQLAlchemy is in dev dependencies only; pytest excludes repository tests. **Decision: Either promote to full runtime dependency with test coverage, or archive the layer.** No half-alive state.

---

### Epic 5 — Production Hardening

**Goal:** Security, observability, and operational safety.

| Item | Status | Exit Criteria |
|------|--------|---------------|
| Secret rotation | **URGENT** | Rotate exposed Entra client secret; keep future values in untracked env only |
| Credential fallback sweep | Pending | Remove admin-style defaults from operational code |
| Webhook replay/idempotency | Partial | HMAC/Svix exists; replay/retry coverage needed |
| Server-farm target | Pending | Decide k3s/RKE2 vs alternatives |
| Observability | Pending | Tracing, latency, token/cost tracking |
| Runbooks | Pending | Enrichment restart, webhook replay, rollback |
| End-to-end verification | Pending | Prove whole system works as one |

---

## WATCHLIST (Future Standards, Not Active Bottlenecks)

These are reasonable but not urgent. Revisit only when they become real blockers.

| Topic | Current Stance | Revisit When |
|-------|----------------|--------------|
| **A2A (Agent2Agent)** | Do not prioritize | Architecture becomes truly multi-agent |
| **AG-UI / A2UI** | Do not prioritize | Chainlit replacement actually needed |
| **MCP expansion** | Add to roadmap only | Standardizing query plane + source adapters behind reusable contract |
| **OpenAI Responses API alignment** | Track passively | Building new agentic features or replacing Assistants patterns |
| **OpenTelemetry GenAI** | Add to roadmap only | Standardizing traces, latency, token/cost observability |
| **Agent evals / trace grading** | Partial (evals dir exists) | Locking demo stability, preventing regressions |
| **Agent skill library** | Add to roadmap only | Standardizing demo prep, mock-authoring, eval workflows |
| **Service mesh** | Do not prioritize | Kubernetes chosen AND mTLS/traffic management actually needed |

---

## Architectural Truth (Preserved)

These boundaries prevent agent drift. Do not violate without explicit architecture change decision.

| Layer | Role | Data |
|-------|------|------|
| **Source systems** | PII and operational master truth | Names, emails, phones, contact details |
| **PostgreSQL** | Customer intelligence and analytical truth | Enriched facts, identity links, consent, audit trails, segments |
| **Tracardi** | Activation/runtime projection | Event hub, workflow engine, score/tag projection, audience activation |
| **Chatbot** | Natural-language operator interface | Deterministic PostgreSQL reads, controlled Tracardi actions |

**Key Constraints:**
- Source systems remain PII system of record
- LLM classifies intent, extracts filters, summarizes results — **not** authoritative SQL execution
- UID-first logging; resolve PII only at authorized presentation step
- Downstream tools receive minimum operational payload

---

## Deployment Posture

**Current:** Local-only permanent
**Azure Scope:** Entra ID + Azure OpenAI only (when public mode needed)
**Target:** Internal server farm (k3s/RKE2 or equivalent evaluation pending)

Do not reopen full Azure hosting for PostgreSQL, Tracardi, or compose stack.

---

## Finish Line

Complete when:
1. ✅ PostgreSQL contains production-usable enriched intelligence
2. ✅ Tracardi is verified activation/runtime layer with healthy projection/writeback
3. ✅ Chatbot uses deterministic PostgreSQL reads with controlled, auditable actions
4. ✅ Source integrations, identity reconciliation, consent implemented for real flows
5. ✅ Security, secrets, monitoring, deployment verification production-safe

---

## Notes For Future Agents

- Start from `NOW` queue, not from the bottom of this file.
- Do not reopen architecture debate unless implementation forces it.
- Do not confuse "implemented skeleton" with "productionized."
- Re-query PostgreSQL for enrichment counts — don't trust runner logs.
- No secret-handling shortcuts; no inline real secrets in tracked files.
- Handoff-driven workflow: one verified increment, explicit next step.
