# NEXT_ACTIONS - Active Execution Queue

**Updated At:** 2026-03-14 19:15 CET  
**Execution Mode:** Local-only  
**Max Items:** 10 (enforced)

---

### P0: Enrichment Coverage (Background)

**Status:** ACTIVE  
**Owner:** Background runners  
**Summary:** Keep enrichment progressing: geocoding, website discovery, Ollama descriptions  
**Next Action:** Monitor from PostgreSQL counts; intervene only on error regression  
**Exit Criteria:** Continuous progress with no manual intervention required

Canonical counts (as_of: 2026-03-09): `website_url=70,922`, `geo_latitude=63,979`, `ai_description=31,033`

See: WORKLOG.md (2026-03-09 entries) for detailed runner history

---

### P0: Illustrated Guide v3.3 Credibility Pass

**Status:** ACTIVE  
**Owner:** Agent  
**Summary:** Fix timestamp consistency, maturity labels, CSV export proof  
**Next Action:** Align prose timestamps with evidence, tighten maturity wording  
**Exit Criteria:** Guide evidence is self-consistent and reviewer-ready

---

### P1: Microsoft Entra Auth Verification

**Status:** PAUSED  
**Owner:** Agent/Human  
**Summary:** Entra implementation complete, activation blocked until Azure quota reset  
**Next Action:** Enable CHAINLIT_ENABLE_AZURE_AD after March 14, 2026 quota reset  
**Exit Criteria:** End-to-end work-account sign-in verified

---

### P1: Business-Case Conformity Matrix

**Status:** ACTIVE  
**Owner:** Agent  
**Summary:** Map BUSINESS_CASE.md requirements to current evidence  
**Next Action:** Create requirement-by-requirement mapping: Conforms/Partial/Not covered  
**Exit Criteria:** Matrix shows explicit POC scope coverage

---

### P1: src/models/ Decision

**Status:** ACTIVE  
**Owner:** Agent  
**Summary:** Half-alive ORM layer causes drift; decide integrate or archive  
**Next Action:** Evaluate usage, make keep-or-archive decision  
**Exit Criteria:** Clear decision recorded, action taken

---

### P1: Preview/Approve Mutations

**Status:** ACTIVE  
**Owner:** Agent  
**Summary:** Segment creation, exports, actions should be gated with preview  
**Next Action:** Design preview flow for mutating operations  
**Exit Criteria:** User sees preview before segment creation/export

---

### P1: Query-Plan Citations

**Status:** ACTIVE  
**Owner:** Agent  
**Summary:** Analytical answers should show query plan and sources  
**Next Action:** Add tool-trace output to analytical responses  
**Exit Criteria:** "How many..." answers include query provenance

---

### P2: Chainlit UX Polish (Deprecated Path)

**Status:** PAUSED  
**Owner:** Agent  
**Summary:** Chainlit deprecated; Operator Shell is the path forward  
**Next Action:** Resume only if Operator Shell hits blockers  
**Exit Criteria:** ChatGPT-like UX in Operator Shell

---

## Recently Closed

Moved to WORKLOG.md. See:
- Tracardi optionalization (COMPLETE 2026-03-14)
- Admin panel + basic authorization (COMPLETE 2026-03-14)
- Typed intents implementation (COMPLETE 2026-03-14)
- Chainlit deprecation (COMPLETE 2026-03-14)
- UV migration + CI repair (COMPLETE 2026-03-10)

---

## References

- **Roadmap:** BACKLOG.md
- **History:** WORKLOG.md
- **Operating rules:** AGENTS.md
