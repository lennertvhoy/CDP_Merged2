# CDP_Merged Backlog v2

**Architecture:** Source systems PII truth + PostgreSQL intelligence truth + Operator shell control plane + Optional Tracardi activation adapter  
**Deployment:** Local-only permanent; Azure limited to Entra ID + Azure OpenAI only  
**Azure Deployment Status:** Disabled for cost control (not paused, not blocked — intentionally disabled)  
**Last Updated:** 2026-03-14

---

## How To Use This File

- **NOW** = Active execution queue (≤10 items). Pick from NEXT_ACTIONS.md.
- **NEXT** = Immediate follow-up once NOW clears.
- **LATER** = Important but blocked or lower priority.
- **WATCHLIST** = Future standards and trends, not active bottlenecks.

Live state lives in `PROJECT_STATE.yaml` and `STATUS.md`. If files conflict, verify implementation first.

---

## NOW (≤10 items)

| # | Item | Epic | Why It Matters |
|---|------|------|----------------|
| 0 | Architecture hardening: Tracardi optionalization | Architecture | ✅ COMPLETE — Core stack runs without Tracardi |
| 1 | Operator shell admin/RBAC | Product Shell | ✅ COMPLETE — /admin live, basic authorization verified |
| 2 | Guide v3.3 credibility pass | Demo | Fix timestamps, maturity labels, CSV proof |
| 3 | Business-case conformity matrix | Demo | Requirement-by-requirement mapping |
| 4 | Enrichment progress verification | Enrichment | Monitor via PostgreSQL counts (see PROJECT_STATE.yaml) |
| 5 | Entra auth verification | Product Shell | Activate after quota reset (post-2026-03-14) |
| 6 | Typed intents expansion | Runtime | Extend beyond 10 core intents |
| 7 | src/models/ fate decision | Runtime | Integrate or archive |
| 8 | Preview/approve mutations | Runtime | Safety for segment creation/export |
| 9 | Query-plan citations | Runtime | Provenance for analytical answers |

**Canonical enrichment counts as_of 2026-03-09:**
- `website_url`: 70,922
- `geo_latitude`: 63,979  
- `ai_description`: 31,033
- `cbe_enriched`: 1,252,019

*(See PROJECT_STATE.yaml section `enrichment.canonical_counts` for authoritative numbers.)*

---

## NEXT (Immediate Follow-up)

- Acceptance-criteria appendix (≥95% prompt/tool proof)
- Integration tests for count/search/segment alignment
- Ollama description throughput tuning
- Maturity label system completion
- PDF export quality (ligature/encoding)

---

## LATER (Blocked or Deferred)

- Live Autotask credentials validation (blocked: vendor access)
- Consent/suppression flow (blocked: source system integrations)
- Server-farm deployment target decision (k3s/RKE2)
- Kubernetes manifests (pending server-farm decision)
- ~~Full Tracardi CE workflow runtime~~ → MOVED TO OPTIONAL/PREMIUM PATH

---

## The Five Epics

### Epic 0 — Architecture Hardening

| Item | Status | Exit Criteria |
|------|--------|---------------|
| Tracardi optionalization | ✅ Complete | Core stack runs without Tracardi |
| Core path verification | ✅ Complete | PostgreSQL + Operator Shell satisfy all demo needs |
| Admin panel verification | ✅ Complete | /admin accessible, authorization enforced |
| RBAC model documentation | Pending | Document beyond simple `is_admin` flag |

**Key Principle:** Core delivery should not be blocked by optional component limitations.

---

### Epic 1 — Credible Local Demo

| Item | Status | Exit Criteria |
|------|--------|---------------|
| Guide v3.3 credibility pass | In progress | Timestamp consistency, maturity labels, CSV checksum proof |
| Business-case conformity matrix | Pending | Requirements mapped to evidence |
| Acceptance-criteria appendix | Pending | ≥95% prompt/tool proof, audit-log evidence |
| Stable demo path | ✅ | End-to-end flow verified repeatable |

**Key Principle:** The backend is further along than the presentation suggests.

---

### Epic 2 — Enrichment Coverage

| Item | Status | Exit Criteria |
|------|--------|---------------|
| CBE enrichment | ✅ | 1.25M+ companies enriched |
| Website discovery | Running | Continuous runner |
| Ollama descriptions | Running | 31K+ descriptions |
| Geocoding | Running | 63K+ geocoded |
| Per-phase metrics | ✅ | Direct PostgreSQL counts established |

**Execution Mode:** Background throughput program. See PROJECT_STATE.yaml for live counts.

---

### Epic 3 — Colleague-Facing Product Shell

| Item | Status | Exit Criteria |
|------|--------|---------------|
| Entra auth | ✅ Implemented | Code complete, activate post-quota |
| Per-user chat history | ✅ | Repo-owned `app_chat_*` persistence |
| Conversation ownership | Partial | Dev auth works; verify under Entra |

**Privacy Rule:** No public deployment without Entra ID auth.

---

### Epic 4 — Data Model and Runtime Hardening

| Item | Status | Exit Criteria |
|------|--------|---------------|
| `src/models/` decision | DECIDE NOW | Integrate or archive |
| Typed intents | ✅ Core 10 | Pattern established, expand coverage |
| Preview/approve mutations | Pending | UX for segment/export gates |
| Provenance/citations | Pending | Query-plan output |

---

## References

- **Active queue:** NEXT_ACTIONS.md
- **Structured state:** PROJECT_STATE.yaml  
- **History:** WORKLOG.md
- **Operating rules:** AGENTS.md
