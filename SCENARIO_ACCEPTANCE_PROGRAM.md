# CDP_Merged Scenario Acceptance Program

**Purpose:** Formal 50-scenario validation program moving from partial proof to fully functional platform  
**Started:** 2026-03-14  
**Status:** In Progress  
**Non-negotiable Rule:** All scenarios executed against real platform — no mocked surfaces

---

## Program Rules

1. **No Fake Surfaces:** All UI surfaces, operator flows, and backend behavior must be real implementation paths
2. **Real Evidence:** Each scenario requires screenshot/artifact evidence from the actual running app
3. **Attached Edge:** Use the already-running logged-in Edge session on 127.0.0.1:9223 for browser work
4. **One-by-One:** Execute scenarios sequentially, marking each as passed only when the real flow succeeds
5. **Fix-First:** If a scenario fails, investigate root cause, fix implementation, rerun before marking passed
6. **Living Docs:** Add each passed scenario to the Illustrated Guide with evidence
7. **PDF Export:** Export updated Illustrated Guide PDF after each meaningful scenario session

## Quality Criteria (Added 2026-03-14)

For chat scenarios (SC-01 through SC-18), quality metrics are now tracked:

| Metric | Target | Notes |
|--------|--------|-------|
| Time to first visible response | < 10s | From click to first text appearing |
| Full completion time | < 20s | For simple count queries |
| Streaming visible | Yes | Content should appear incrementally, not all at end |
| Answer correctness | Yes | Must match expected value |
| Answer-first format | Yes | Answer before explanation/tool details |

Scenario status labels:
- `functional_pass` - Correct answer but may have UX issues
- `quality_pass` - Correct answer + good latency + visible streaming
- `failed_investigating` - Does not meet criteria, under investigation
- `blocked` - Cannot proceed due to external dependency

---

## Scenario Tracker

### Foundation search / count / retrieval (SC-01 to SC-10)

| ID | Title | Status | Evidence | Notes |
|----|-------|--------|----------|-------|
| SC-01 | Brussels company count baseline | ✅ quality_pass | `reports/scenarios/sc01/sc01_rerun_after_fix.png` | Answer: 41,290; First content: ~10s; Total: ~11s; Streaming: ✓; Fix: UI now shows content incrementally |
| SC-02 | Antwerpen company count baseline | ✅ quality_pass | `reports/scenarios/sc02/sc02_antwerpen_count.png` | Answer: 62,831; First content: ~10s; Total: ~11s; Streaming: ✓; Correct count verified |
| SC-03 | Gent restaurant baseline | ✅ quality_pass | `reports/scenarios/sc03/sc03_gent_restaurant.png` | Answer: 1,050; Expected: ~~1,105~~ → 1,050; Canonical SQL verified: NACE 56101, 56102 (restaurant activities); Streaming: ✓; Semantics reconciled |
| SC-04 | All-status vs active-only semantics | ⚠️ functional_pass | `reports/scenarios/sc04/sc04_followup_semantics.png` | Context reuse: ✓ (mentions Brussels vs Gent); Count: 1,495/1,495; Missing: explicit explanation why unchanged; All companies AC in dataset |
| SC-05 | Brussels software scope clarity | ⏳ pending | — | — |
| SC-06 | Top industries in Brussels | ⏳ pending | — | — |
| SC-07 | Companies with websites in Brussels | ⏳ pending | — | — |
| SC-08 | Companies with email in Brussels | ⏳ pending | — | — |
| SC-09 | Search Antwerp software companies | ⏳ pending | — | — |
| SC-10 | Legal-form aggregation | ⏳ pending | — | — |

### Follow-up continuity / narrowing (SC-11 to SC-18)

| ID | Title | Status | Evidence | Notes |
|----|-------|--------|----------|-------|
| SC-11 | Follow-up narrowing by status | ⏳ pending | — | — |
| SC-12 | Follow-up narrowing by city | ⏳ pending | — | — |
| SC-13 | Follow-up result limiting | ⏳ pending | — | — |
| SC-14 | Follow-up export from last search | ⏳ pending | — | — |
| SC-15 | Follow-up segment creation from last search | ⏳ pending | — | — |
| SC-16 | Follow-up 360 from prior result | ⏳ pending | — | — |
| SC-17 | Follow-up count after search | ⏳ pending | — | — |
| SC-18 | Follow-up resume after refresh | ⏳ pending | — | — |

### Segments / exports / operational flow (SC-19 to SC-28)

| ID | Title | Status | Evidence | Notes |
|----|-------|--------|----------|-------|
| SC-19 | Create segment from real search | ⏳ pending | — | — |
| SC-20 | Segment stats alignment | ⏳ pending | — | — |
| SC-21 | Export segment to CSV | ⏳ pending | — | — |
| SC-22 | CSV field validation | ⏳ pending | — | — |
| SC-23 | Search segments by name | ⏳ pending | — | — |
| SC-24 | Segment details view | ⏳ pending | — | — |
| SC-25 | Segment export alignment | ⏳ pending | — | — |
| SC-26 | Graceful handling when no prior search exists | ⏳ pending | — | — |
| SC-27 | Real search → segment → export flow | ⏳ pending | — | — |
| SC-28 | Segment search field in UI | ⏳ pending | — | — |

### 360 / analytics / linked-source scenarios (SC-29 to SC-38)

| ID | Title | Status | Evidence | Notes |
|----|-------|--------|----------|-------|
| SC-29 | 360 by KBO number | ⏳ pending | — | — |
| SC-30 | 360 by company name | ⏳ pending | — | — |
| SC-31 | Linked source visibility | ⏳ pending | — | — |
| SC-32 | Financial/Exact summary | ⏳ pending | — | — |
| SC-33 | Teamleader commercial summary | ⏳ pending | — | — |
| SC-34 | Autotask support summary | ⏳ pending | — | — |
| SC-35 | Identity link quality | ⏳ pending | — | — |
| SC-36 | High-value accounts | ⏳ pending | — | — |
| SC-37 | Geographic revenue distribution | ⏳ pending | — | — |
| SC-38 | Industry pipeline summary | ⏳ pending | — | — |

### Admin / auth / persistence / multi-user (SC-39 to SC-45)

| ID | Title | Status | Evidence | Notes |
|----|-------|--------|----------|-------|
| SC-39 | Non-admin denied admin page | ✅ passed | `reports/compound_slice_42/admin_access_denied_non_admin.png` | Previously verified |
| SC-40 | Admin positive path | ✅ passed | `reports/compound_slice_43/admin_panel_positive_path.png` | Previously verified |
| SC-41 | Admin users API | ✅ passed | API verified with curl | Previously verified |
| SC-42 | Admin me API | ✅ passed | API verified with curl | Previously verified |
| SC-43 | User-scoped thread isolation | ⏳ pending | — | — |
| SC-44 | Thread persistence after refresh | ⏳ pending | — | — |
| SC-45 | Thread title/history visibility | ⏳ pending | — | — |

### Intent determinism / quality / robustness (SC-46 to SC-50)

| ID | Title | Status | Evidence | Notes |
|----|-------|--------|----------|-------|
| SC-46 | Typed intent: count query | ⏳ pending | — | — |
| SC-47 | Typed intent: search query | ⏳ pending | — | — |
| SC-48 | Typed intent: 360 query | ⏳ pending | — | — |
| SC-49 | Typed intent: segment/export query | ⏳ pending | — | — |
| SC-50 | Primary operator journey end-to-end | ⏳ pending | — | — |

---

## Scenario Definitions

### SC-01 — Brussels company count baseline
**User prompt:** "How many companies are in Brussels?"  
**Expected result:**
- Real chat flow in the operator shell
- Attached Edge/CDP path used
- Answer-first response
- No tool leakage
- Correct numeric result from the real PostgreSQL-backed system
- Canonical expected answer: 41,290 companies in Brussels
- Screenshot artifact captured
- Scenario marked passed only if the real flow succeeds

### SC-02 — Antwerpen company count baseline
**User prompt:** "How many companies are in Antwerpen?"  
**Expected result:** Real chat flow returns 62,831 companies, answer-first, no tool leakage, screenshot captured.

### SC-03 — Gent restaurant baseline
**User prompt:** "How many restaurant companies are in Gent?"  
**Expected result:** Real chat flow returns 1,050 (NACE 56101, 56102 - restaurant activities), answer-first, no tool leakage, screenshot captured.

**Canonical semantics:**
- NACE codes: 56101, 56102 (mapped from keyword "restaurant")
- SQL: `WHERE city IN ('Gent', ...) AND (nace_code IN ('56101', '56102') OR all_nace_codes && ARRAY['56101', '56102'])`
- Note: 1,105 was an estimate using broader NACE 56* (all food & beverage); 1,050 is correct for strict restaurant activities

### SC-04 — All-status vs active-only semantics
**User scenario:**
- Turn 1: "How many restaurant companies are in Brussels?"
- Turn 2: "Only active ones."
**Expected result:** The second answer is narrower than the first (or explains why unchanged) and clearly reflects the status filter; no silent default-status confusion.

**Quality note:** Response should explicitly explain when count unchanged (e.g., "All 1,495 are already active companies") rather than just repeating the number.

### SC-05 — Brussels software scope clarity
**User prompt:** "How many software companies are in Brussels?"  
**Expected result:** Returns a real count and clearly states the applied scope/filter semantics if needed; no stale NACE confusion.

### SC-06 — Top industries in Brussels
**User prompt:** "What are the top industries in Brussels?"  
**Expected result:** Returns a ranked aggregation from real data, not a generic answer; includes counts or percentages.

### SC-07 — Companies with websites in Brussels
**User prompt:** "How many companies in Brussels have a website?"  
**Expected result:** Uses real field-level enrichment data and returns a count from PostgreSQL-backed truth.

### SC-08 — Companies with email in Brussels
**User prompt:** "How many companies in Brussels have an email address?"  
**Expected result:** Returns a real count from the current dataset, with correct field semantics.

### SC-09 — Search Antwerp software companies
**User prompt:** "Find software companies in Antwerp."  
**Expected result:** Returns a real result set/search summary, not just a count; supports follow-up actions.

### SC-10 — Legal-form aggregation
**User prompt:** "What legal forms are most common in Brussels?"  
**Expected result:** Returns a real grouped result from the data model, not vague prose.

### SC-11 — Follow-up narrowing by status
**User scenario:**
- Turn 1: "Find companies in Brussels."
- Turn 2: "Only active ones."
**Expected result:** The follow-up correctly reuses prior context and narrows the prior result set.

### SC-12 — Follow-up narrowing by city
**User scenario:**
- Turn 1: "Find software companies."
- Turn 2: "Only the ones in Antwerp."
**Expected result:** The second query narrows the first instead of starting a random unrelated search.

### SC-13 — Follow-up result limiting
**User scenario:**
- Turn 1: "Find software companies in Antwerp."
- Turn 2: "Show me the first 20."
**Expected result:** The system returns a bounded preview/list rather than re-answering only in prose.

### SC-14 — Follow-up export from last search
**User scenario:**
- Turn 1: "Find software companies in Antwerp."
- Turn 2: "Export these to CSV."
**Expected result:** Uses the last-search context correctly and generates a real export artifact.

### SC-15 — Follow-up segment creation from last search
**User scenario:**
- Turn 1: "Find software companies in Antwerp."
- Turn 2: "Create a segment from that."
**Expected result:** A real PostgreSQL-backed segment is created from the last search context.

### SC-16 — Follow-up 360 from prior result
**User scenario:**
- Turn 1: "Find companies named B.B.S."
- Turn 2: "Give me the 360 view of the first one."
**Expected result:** Correctly resolves the follow-up target and returns a real 360 result.

### SC-17 — Follow-up count after search
**User scenario:**
- Turn 1: "Find restaurant companies in Gent."
- Turn 2: "How many is that exactly?"
**Expected result:** Returns the exact count for the current thread context, not a fresh unrelated query.

### SC-18 — Follow-up resume after refresh
**User scenario:** Start a thread, perform a search, refresh/reopen, then ask "Export that one."  
**Expected result:** Thread context persists and the flow continues correctly.

### SC-19 — Create segment from real search
**User prompt:** "Create a segment for software companies in Antwerp."  
**Expected result:** Creates a real PostgreSQL-backed segment with a member count aligned to the search.

### SC-20 — Segment stats alignment
**User scenario:** Create a segment, then inspect its stats.  
**Expected result:** Segment count matches the originating search logic.

### SC-21 — Export segment to CSV
**User prompt:** "Export the segment to CSV."  
**Expected result:** Generates a real file artifact with expected rows, not a placeholder success.

### SC-22 — CSV field validation
**User scenario:** Open/download the produced CSV.  
**Expected result:** File contains real expected columns such as name/city/status and is not empty or malformed.

### SC-23 — Search segments by name
**User prompt:** "Find the segment for software companies in Antwerp."  
**Expected result:** Segment lookup works in the live UI/runtime.

### SC-24 — Segment details view
**User scenario:** Open a segment from the UI.  
**Expected result:** Details panel shows real metrics and member stats.

### SC-25 — Segment export alignment
**User scenario:** Compare search count, segment count, export count.  
**Expected result:** Counts align or any deliberate preview limit is explicitly explained.

### SC-26 — Graceful handling when no prior search exists
**User prompt:** "Create a segment from that."  
**Expected result:** If no valid prior search exists, the app responds helpfully instead of fake-successing.

### SC-27 — Real search → segment → export flow
**User scenario:** Search, create segment, export, inspect export.  
**Expected result:** Full real operational flow works end to end.

### SC-28 — Segment search field in UI
**User scenario:** Use the Segments UI search box.  
**Expected result:** Real filtering/search behavior works in the surface, not static UI chrome.

### SC-29 — 360 by KBO number
**User prompt:** "Give me a 360 view of company KBO 0438437723."  
**Expected result:** Returns a real linked-company profile from the unified 360 path.

### SC-30 — 360 by company name
**User prompt:** "Give me a 360 view of B.B.S. Entreprise."  
**Expected result:** Resolves the company and returns linked-source info.

### SC-31 — Linked source visibility
**User scenario:** Ask for source coverage of a known linked company.  
**Expected result:** Answer clearly shows which sources are linked: KBO, Teamleader, Exact, Autotask where applicable.

### SC-32 — Financial/Exact summary
**User prompt:** "Show me the financial summary for B.B.S. Entreprise."  
**Expected result:** Uses real Exact-backed data if present and labels it accurately.

### SC-33 — Teamleader commercial summary
**User prompt:** "Show me deals and activities for B.B.S. Entreprise."  
**Expected result:** Uses real Teamleader-backed synced data if present.

### SC-34 — Autotask support summary
**User prompt:** "Show me support activity for B.B.S. Entreprise."  
**Expected result:** Returns real mock-backed Autotask support data if linked.

### SC-35 — Identity link quality
**User prompt:** "How well are source systems linked to KBO?"  
**Expected result:** Deterministically routes to the identity-link-quality path and returns real metrics.

### SC-36 — High-value accounts
**User prompt:** "Which high-value accounts should I look at first?"  
**Expected result:** Returns a real ranked analytical answer, not generic sales advice.

### SC-37 — Geographic revenue distribution
**User prompt:** "Show me revenue distribution by city."  
**Expected result:** Deterministically routes correctly and returns grouped data.

### SC-38 — Industry pipeline summary
**User prompt:** "What is the total pipeline value for software companies?"  
**Expected result:** Deterministically routes correctly and returns a real analytical summary.

### SC-39 — Non-admin denied admin page
**User scenario:** Visit `/admin` as non-admin.  
**Expected result:** Access denied message in UI plus server-side protection.

### SC-40 — Admin positive path
**User scenario:** Sign in as admin and open `/admin`.  
**Expected result:** Admin UI loads and shows real admin information.

### SC-41 — Admin users API
**User scenario:** Call or exercise `/api/operator/admin/users` as admin.  
**Expected result:** Real success response and live UI/API evidence.

### SC-42 — Admin me API
**User scenario:** Call or exercise `/api/operator/admin/me` as admin.  
**Expected result:** Returns real current-admin status and matches the UI state.

### SC-43 — User-scoped thread isolation
**User scenario:** Two users create/open threads.  
**Expected result:** One user cannot access the other's conversation/thread data.

### SC-44 — Thread persistence after refresh
**User scenario:** Send a message, refresh/reopen.  
**Expected result:** Thread content and composer state persist correctly.

### SC-45 — Thread title/history visibility
**User scenario:** Create a meaningful thread and inspect thread history.  
**Expected result:** Real history entry/title appears and is reusable.

### SC-46 — Typed intent: count query
**User prompt:** "How many companies are in Brussels?"  
**Expected result:** Deterministic count intent classification and correct execution path.

### SC-47 — Typed intent: search query
**User prompt:** "Find software companies in Antwerp."  
**Expected result:** Deterministic search intent classification and correct execution path.

### SC-48 — Typed intent: 360 query
**User prompt:** "Give me a 360 view of 0438437723."  
**Expected result:** Deterministic 360 intent classification and correct execution path.

### SC-49 — Typed intent: segment/export query
**User prompt:** "Create a segment from these results and export it."  
**Expected result:** Deterministic action/segment path or a clear preview/approval flow if required.

### SC-50 — Primary operator journey end-to-end
**User scenario:**
1. Ask a real market question
2. Narrow results
3. Create a segment
4. Export it
5. Ask for a 360 on one company from the same workflow
**Expected result:** Full real operator flow works end to end in the actual platform, with screenshots, no mock UI surfaces, no tool leakage, clean evidence in the Illustrated Guide.

---

## Progress Summary

**Total Scenarios:** 50  
**Passed:** 5 (SC-01, SC-39, SC-40, SC-41, SC-42)  
**In Progress:** 0  
**Pending:** 45  
**Blocked:** 0  
**Failed:** 0

---

## Session Log

| Date | Session | Scenarios Passed | Notes |
|------|---------|------------------|-------|
| 2026-03-14 | Initial | SC-39, SC-40, SC-41, SC-42 | Admin scenarios from previous verification |
| 2026-03-14 | SC-01 | SC-01 | SC-01 passed: 41,290 Brussels companies; fixed Azure OpenAI → OpenAI provider; LLM_PROVIDER=openai |

---

*For business context, see `docs/BUSINESS_CASE.md`. For technical details, see `docs/SYSTEM_SPEC.md`.*
