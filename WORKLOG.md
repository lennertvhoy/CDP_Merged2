# WORKLOG

**Purpose:** Append-only session log for meaningful task updates

---

## 2026-03-15 (3 Scenarios Verified + Documentation Fixes)

### Task: Test 3 scenarios with live Edge CDP + Fix documentation contradictions

**Type:** verification_only + docs_or_process_only  
**Status:** COMPLETE  
**Timestamp:** 2026-03-15 17:00 CET  
**Git Head:** (after commit)  
**Worktree:** Clean

**User Directive:** Required: test 3 scenarios, fix documentation contradictions, provide exact evidence.

**Correction from User Feedback:** Previous report had insufficient evidence and tracker contradictions. This entry provides exact evidence.

---

### SC-18 Public Path Verification — EXACT EVIDENCE

**Test Method:** Live Edge CDP at `http://127.0.0.1:9223`, public URL `https://kbocdpagent.ngrok.app`

| Step | Prompt | Response | Evidence |
|------|--------|----------|----------|
| 1 | "Find software companies in Antwerp" | "I found **3,062** software companies in Antwerp" | `sc18_evidence_step2.png` |
| 2 | Refresh page | Page reloads, conversation context persists | `sc18_evidence_step3.png` |
| 3 | "Export that one" | "Your export is ready! You can download the CSV file..." | `sc18_evidence_step4.png` |

**Extracted Download URL:**
```
/download/artifacts/exported-company-data_20260315_111753.csv
```

**Verification:**
- Contains "localhost": NO ✅
- Is relative URL: YES ✅
- Works on public path: YES ✅

**Status:** ✅ **quality_pass**

---

### SC-29 — 360° View by KBO Number — EXACT EVIDENCE

**Prompt:** "Show 360 view for KBO 0438437723"

**Response:** Full 360° golden record for **B.B.S ENTREPRISE**
- KBO: 0438437723
- 4 sources linked: KBO + Teamleader + Exact + Autotask
- Link status: `linked_all`

**Status:** ✅ **quality_pass**

**Evidence:** `reports/scenarios/sc29_360_kbo.png`

---

### SC-46 — Typed Intent Count Query — EXACT EVIDENCE

**Prompt:** "How many companies are in Brussels?"

**Response:** "I found **41,290** companies in Brussels"

**Status:** ✅ **quality_pass**

**Evidence:** `reports/scenarios/sc46_count_result.png`

---

### SC-19 — Create Segment from Real Search — CORRECTED STATUS

**Test Performed:**
- Turn 1: "Find software companies in Brussels" → "I found **1,821** software companies"
- Turn 2: "Create a segment from these results" → "Please provide the search criteria..."

**Analysis:**
- Search works correctly (1,821 companies found)
- Segment creation **failed to use context** from Turn 1
- Same root cause as SC-17 (context reuse broken)

**Status:** ❌ **functional_fail** (was incorrectly reported as functional_pass)

**Evidence:** `reports/scenarios/sc19_segment_created.png`

---

### Documentation Contradictions Fixed

1. **SC-18:** Added exact evidence (download URL, proof of no localhost)
2. **SC-19:** Corrected from `functional_pass` to `functional_fail`
3. **Tracker:** Fixed summary counts to match per-scenario statuses
4. **GPT-5 refs:** Changed to `gpt-4.1-mini` in ILLUSTRATED_GUIDE.md

### Corrected Scenario Tracker

| Category | Passed | Failed | Pending |
|----------|--------|--------|---------|
| Foundation (SC-01 to SC-10) | 10 | 0 | 0 |
| Follow-up (SC-11 to SC-18) | 7 | 1 | 0 |
| Segments/Exports (SC-19 to SC-28) | 0 | 1 | 9 |
| 360/Analytics (SC-29 to SC-38) | 1 | 0 | 9 |
| Admin/Auth (SC-39 to SC-45) | 4 | 0 | 3 |
| Intent (SC-46 to SC-50) | 1 | 0 | 4 |
| **Total** | **23** | **2** | **25** |

### Files Changed
- `AGENTS.md` - Strengthened live Edge browser requirement
- `SCENARIO_ACCEPTANCE_PROGRAM.md` - Updated SC-18, SC-19, SC-29, SC-46 statuses; fixed tracker
- `docs/ILLUSTRATED_GUIDE.md` - Added Phase 25 with exact evidence
- `WORKLOG.md` - This entry with exact evidence

---

## 2026-03-15 (SC-18 Bug Fix + Chat UI Redesign)

### Task: Fix CSV export public URL bug + Redesign chat page for vertical space

**Type:** app_code  
**Status:** COMPLETE (pending retest on public path)  
**Timestamp:** 2026-03-15 12:00 CET  
**Git Head:** `4ac26da`  
**Worktree:** Modified (changes to be committed)

**Critical Bug Discovered:**
The SC-18 "export success" claim was false. The assistant was returning `http://localhost:3000/download/artifacts/...` links when running on the public ngrok deployment (`https://kbocdpagent.ngrok.app/`). This made exports fail for real users.

**Fix 1: Export URL Generation (artifact.py)**
- Changed `_get_base_url()` to return empty string (relative URLs) by default
- Changed `_build_download_url()` to return `/download/artifacts/{filename}` instead of `http://localhost:3000/...`
- Relative URLs work on any deployment without hardcoding origins
- `OPERATOR_SHELL_URL` env var can still override if needed

**Fix 2: Chat Page Vertical Space Redesign (chat-surface.tsx)**
- Replaced verbose `SectionHeader` with compact header bar
- Reduced outer padding from `px-6 py-6` to `px-3 py-3`
- Compressed conversation header:
  - Removed large icon and stacked text
  - Single row: icon + "New/Saved conversation" + subtitle + Feedback button
  - Reduced padding from `px-5 py-3.5` to `px-4 py-2`
- Reduced textarea rows from 3 to 2
- Reduced composer padding
- Chat surface now dominates the viewport

**Verification:**
| Component | Expected | Actual | Status |
|-----------|----------|--------|--------|
| Export URL (default) | `/download/artifacts/filename` | `/download/artifacts/test.csv` | ✅ |
| Export URL (with env) | Full URL | `https://kbocdpagent.ngrok.app/download/artifacts/test.csv` | ✅ |
| UI compact header | Visible | Compact "Chat + LIVE + Report issue" bar | ✅ |
| UI conversation card | More vertical space | Reduced padding, compact header | ✅ |
| Worktree | Modified | 2 files changed, 1 new screenshot | ✅ |

**Files Changed:**
- `src/ai_interface/tools/artifact.py` - Export URL fix
- `apps/operator-shell/components/chat-surface.tsx` - UI redesign
- `reports/scenarios/sc18_fixed_ui_redesign.png` - Evidence

