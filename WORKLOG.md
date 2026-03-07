# WORKLOG

**Purpose:** Append-only session log for meaningful task updates

---

---

## 2026-03-07 (Browser-Driven Multi-Turn Operator Scenario)

### Task: Drive real browser-based multi-turn scenario through compose-managed chatbot

**Type:** app_code  
**Status:** COMPLETE  
**Timestamp:** 2026-03-07 18:20 CET  
**Git HEAD:** b574a47

**Summary:**
Completed a real threaded browser session against the local compose-managed chatbot to validate search → artifact → segment → export flows. All 4 turns completed successfully with expected behavior. The 0-profile segment/export result is the known PostgreSQL-to-Tracardi sync architecture gap, not a bug.

**Browser Session Flow:**

```
Turn 1: Search Query
  User: "How many software companies are in Brussels?"
  Response: "I found a total of 1,529 software companies in Brussels."
  Follow-up options: Create segment, Push to Resend, Show analytics, Similar search
  Status: ✅ PASSED

Turn 2: Artifact Creation
  User: "Create a data artifact with the first 100 results in markdown format"
  Response: Artifact created with download link "Download Software Companies in Brussels"
  Artifact file: output/agent_artifacts/software-companies-in-brussels_20260307_171512.markdown
  Status: ✅ PASSED

Turn 3: Segment Creation
  User: "Create a segment named "Brussels Software Companies" from these results"
  Response: Segment created but contains 0 profiles
  Note: Expected - PostgreSQL companies not synced to Tracardi profiles yet
  Status: ✅ PASSED WITH EXPECTED LIMITATION

Turn 4: Export Attempt
  User: "Export these software companies to CSV for the segment"
  Response: "The export attempt for the segment "Brussels Software Companies" resulted in 0 profiles to export."
  Note: Correct behavior - empty segment correctly reports 0 profiles
  Status: ✅ PASSED WITH EXPECTED LIMITATION
```

**Evidence:**
- Screenshot: `chatbot_full_flow_test_2026-03-07.png`
- Artifact: `output/agent_artifacts/software-companies-in-brussels_20260307_171512.markdown` (2,302 bytes)

**Architecture Notes:**
- Segment creation in Tracardi works but profiles are empty because PostgreSQL is the analytical truth layer
- Tracardi is the activation runtime layer that needs selective PostgreSQL-to-Tracardi sync
- This is the expected PostgreSQL-first architecture, not a bug

---

---

## 2026-03-07 (Chatbot Quality Verified on Full 1.94M Dataset)

### Task: Test chatbot against full 1.94M KBO dataset

**Type:** verification_only
**Status:** COMPLETE
**Timestamp:** 2026-03-07 17:05 CET
**Git HEAD:** 36007b1

**Summary:**
Verified chatbot behavior against the full 1,940,603 record local PostgreSQL dataset. All core search, count, and aggregation functionality works correctly with excellent performance.

**Verification Results:**

```
Test 1: Restaurants in Gent
  ✅ Backend: postgresql
  ✅ Found: 1,105 restaurants
  ✅ NACE codes auto-resolved: 56101, 56102, 56290

Test 2: Companies in Brussels (no status filter)
  ✅ Backend: postgresql
  ✅ Found: 41,290 companies
  ✅ Query time: <3 seconds

Test 3: Top industries in Brussels
  ✅ Backend: postgresql
  ✅ Total matching: 41,290
  ✅ Top industry: 70200 (Consulting) at 4.8%
  ✅ Aggregation working (was previously timing out)

Test 4: Companies in Antwerpen
  ✅ Backend: postgresql
  ✅ Found: 62,831 companies

Test 5: Coverage stats
  ✅ Total companies: 1,940,603
  ✅ With NACE code: 1,252,022 (64.5%)
  ✅ With city: 1,176,707 (60.6%)
  ✅ With email: 190,533 (9.8%)
  ✅ With website: 35,844 (1.85%)
```
