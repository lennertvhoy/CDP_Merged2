# Illustrated Guide Audit Report
**Date:** 2026-03-08  
**Auditor:** AI Agent following AGENTS.md protocol  
**Purpose:** Verify screenshots match descriptions, identify mismatches, define required demonstrations

---

## Executive Summary

The Illustrated Guide presents a compelling POC narrative but contains **critical mismatches** between screenshots and descriptions, **missing demonstrations** of core value propositions, and **data inconsistencies** that undermine its credibility as a source of truth.

**Grade: C+** - Components exist but end-to-end integration is not proven with realistic data.

**Update (2026-03-08 21:08 CET):** The guide has since been refreshed with populated Resend audience proof. The exact Brussels IT primary-code subset was verified at `190` company rows and `189` unique contact emails, then loaded into the empty Resend audience `KBO Companies - Test Audience` because the current Resend plan is capped at `3` audiences. Fresh screenshots were captured at `docs/illustrated_guide/demo_screenshots/resend_audiences_populated_2026-03-08.png` and `docs/illustrated_guide/demo_screenshots/resend_audience_detail_populated_2026-03-08.png`. The remaining active blockers are workflow execution evidence, website-behavior evidence, and stale screenshot/caption cleanup in a few older sections.

---

## Critical Mismatches (Screenshots ≠ Reality)

### 1. ❌ EXACT ONLINE SYNC - STALE DATA
| Aspect | Guide Claims | PROJECT_STATE.yaml Reality |
|--------|--------------|---------------------------|
| GL Accounts | 60 | 258 |
| Customers | Not mentioned | 9 |
| Invoices | 60 | 78 |
| Status | "Sync completed" | OAuth renewed 2026-03-08, working |

**Issue:** The "60 GL accounts, 60 invoices" numbers are stale. Current sync shows 258 GL accounts and 78 invoices. The screenshot may also show an OAuth error from earlier attempts while caption claims success.

**Fix Required:** Update screenshot and caption to reflect current sync state (258 GL accounts, 9 customers, 78 invoices).

---

### 2. ⚠️ DATA SCALE TABLE - SCOPE LABELS REQUIRED
| Source | Guide Shows | Actual (PROJECT_STATE.yaml) |
|--------|-------------|----------------------------|
| Exact Online invoices | 60 | 78 |
| Software in Brussels | 1,652 (canonical full scope) vs 1,529 (narrower activation test) | Both are valid when labeled by scope |

**Issue:** Earlier guide revisions mixed these numbers without explaining scope. The current guide now labels `1,652` as the canonical 6-code software segment, `1,529` as the narrower 62xxx-only activation test, and `101` as the preview export file size.

**Remaining Fix Required:** Keep those scope labels stable in future edits and avoid reverting to unlabeled counts.

---

### 3. ❌ RESTAURANT SEARCH - MISSING RESULTS
**Location:** Page 15 - "Search Results"

**Issue:** Caption says "Results showing companies with details" but screenshot only shows the query entry interface ("Let's proceed with the search"). No actual results with the 1,105 count are visible.

**Fix Required:** Screenshot must show the AI response with the actual count and at least sample company details.

---

### 4. ❌ EMAIL BOUNCE PROCESSOR - EMPTY WORKFLOW
**Location:** Page 17

**Issue:** Screenshot shows mostly white space with only "Update profile" node, but caption claims "Automated bounce handling workflow." The workflow structure is not visible.

**Fix Required:** Show full workflow diagram with Start → Condition → Update Profile → End nodes.

---

### 5. ⚠️ REPETITIVE SCREENSHOTS
**Issue:** Tracardi dashboard appears on pages 15, 18 with different event counts (64 vs 57). This suggests screenshots from different times without context.

**Fix Required:** Either show time progression or consolidate to one representative screenshot.

---

## Missing Core Value Demonstrations

### ❌ 360° Golden Record View (CRITICAL GAP)
**What it is:** Querying a single company and seeing unified data from ALL sources (KBO + Teamleader + Exact Online) in one view.

**Why it matters:** This is the PRIMARY value proposition - unified customer intelligence. The guide mentions 1.94M records but never shows a single enriched company profile.

**Required Screenshot Sequence:**
1. User asks: "Show me complete profile for [Company Name]"
2. AI response showing:
   - **KBO Section:** VAT BE0123..., Legal form, Employees, NACE codes
   - **CRM Section (Teamleader):** Open deals €15,000, Contact: John Doe
   - **Accounting Section (Exact):** Last invoice €8,500 (Paid), Outstanding: €0
   - **Enrichment:** Website, AI description, Geolocation

**Current State:** The guide now contains a fresh B.B.S. Entreprise screenshot that explicitly shows `identity_link_status=linked_all` and `Sources linked: KBO + Teamleader + Exact + Autotask (4 sources)`, plus matching SQL-backed backend proof. The remaining gap is not missing linkage proof; it is the absence of a UID-first runtime presentation and a richer single-shot business-value view.

---

### ✅ Segment Activation with Real Data (Resolved For Current POC)
**What it is:** Pushing the exact Brussels IT subset with real email coverage to Resend and verifying it appears as a populated audience.

**Resolved State:**
- The old `1,652` software-company claim is not usable for activation because those Brussels NACE codes do not exist in the KBO data
- The verified exact primary-code subset contains `190` Brussels IT company rows and `189` unique contact emails
- A fresh populated Resend audience proof now exists in the live dashboard using the reused empty audience `KBO Companies - Test Audience`
- The current operational constraint is plan-related, not data-related: the Resend account is capped at `3` audiences, so a new audience could not be created and an empty existing audience had to be reused

---

### ❌ Real-Time Sync Verification
**What it is:** Demonstrating that data changes in source systems flow through to chatbot queries within the 15-minute sync window.

**Current Gap:** Only shows initial sync, not incremental updates.

**Required Screenshot Sequence:**
1. Teamleader showing Deal "Open" for Company X
2. User updates Deal to "Won" in Teamleader
3. Terminal showing sync_teamleader with "Updated: 1"
4. Chatbot query: "What is the pipeline for Company X?" → Returns updated value

---

## 3 Additional Required Verifications

### 1. MCP Server Tools Querying PostgreSQL (Technical Proof)
**What to demonstrate:** The MCP server actually executes SQL queries against PostgreSQL, not returning mocked responses.

**Required Evidence:**
- Screenshot of logs showing SQL generated by MCP tools
- Or: Claude Desktop interface showing MCP tool calls with PostgreSQL results
- Or: Browser showing MCP Inspector with query traces

**Why it matters:** Proves the AI-to-database path is real, not simulated.

---

### 2. Tracardi Workflow Execution with Real Events
**What to demonstrate:** The Email Bounce Processor workflow actually executes when a bounce event is received.

**Required Evidence:**
1. Workflow diagram with execution log overlay
2. Profile before bounce (email_valid: true)
3. Resend webhook sending bounce event
4. Tracardi event log showing workflow triggered
5. Profile after bounce (email_valid: false)

**Current Gap:** Only shows workflow list, not execution.

---

### 3. CSV Export Field Validation
**What to demonstrate:** The exported CSV actually contains all 9 claimed fields with real data.

**Required Evidence:**
- Screenshot of downloaded CSV opened in Excel/LibreOffice
- Visible columns: name, email, phone, city, zip_code, status, nace_code, juridical_form, website
- Row count showing 1,652 (or sample of 100)
- Sample rows with actual company data

**Current Gap:** Only shows export link, not the actual file contents.

---

## Data Realism Issues

### Current Test Data Problems:

| Source | Current State | Required for Credibility |
|--------|---------------|-------------------------|
| Teamleader | 1 company, 2 contacts | 50-100 realistic Belgian companies |
| Exact Online | 9 customers, 78 invoices | Corresponding invoices for mock companies |
| Resend | 9 test emails | Audience with 1,652+ actual contacts |

### Recommended Mock Data Strategy:

**Teamleader (50+ companies):**
- Real Belgian company names (e.g., "Bakkerij De Gouden Croissant", "TechFlow Belgium BV")
- Valid Belgian VAT format (BE0123456789)
- Realistic deal values: €5K-€500K
- Various stages: Lead, Proposal, Won, Lost
- Real addresses in Gent, Brussels, Antwerp

**Exact Online (matching data):**
- Invoices linked to same VAT numbers as Teamleader
- Mix of paid/unpaid statuses
- Realistic amounts correlating with deal values
- Invoice dates spread across last 2 years

**KBO (existing):**
- The 1.94M records are real - use actual records that match VAT numbers above

---

## Action Items for Coding Agent

### Priority 1: Fix Critical Mismatches
- [ ] Update Exact Online sync screenshot/caption to show current state (258 GL accounts, 9 customers, 78 invoices)
- [ ] Capture restaurant search screenshot showing actual 1,105 count and sample results
- [ ] Capture email bounce processor showing full workflow diagram
- [x] Fix data scale table with current accurate numbers and scope labels

### Priority 2: Generate Missing Demonstrations
- [x] **360° Golden Record:** Capture fresh B.B.S. Entreprise `linked_all` view and align the guide caption to the four-source backend proof
- [x] **Segment Activation:** Populate the exact Brussels IT primary-code subset in Resend (`190` company rows, `189` unique contacts after one duplicate shared mailbox), capture audience-list and audience-detail screenshots
- [ ] **CSV Export:** Download and open CSV, screenshot showing all 9 fields with data

### Priority 3: Populate Realistic Mock Data
- [ ] Create 50+ hyperrealistic companies in Teamleader
- [ ] Create corresponding invoices in Exact Online
- [ ] Ensure VAT number matching across systems
- [ ] Re-run syncs to populate PostgreSQL with rich test data

### Priority 4: Additional Technical Verifications
- [ ] Capture MCP server logs showing PostgreSQL queries
- [ ] Trigger test bounce event, capture workflow execution logs
- [x] Document current Tracardi privacy divergence (anonymous profiles, email-bearing event metadata)
- [x] Document NACE resolution discrepancy (`1,652` canonical full scope vs `1,529` narrower activation-test scope)

---

## Screenshot Integrity Protocol (New Requirement)

Per AGENTS.md Screenshot and Demo Integrity rules:

1. **Every screenshot must be captured from actual running system**
2. **Every data claim must be verifiable via database query**
3. **Dates/times in screenshots must be recent** (within 24 hours of report)
4. **Test data must be explicitly labeled** - never imply test is production
5. **Caption must match visible content** exactly

### Verification Checklist for Each Screenshot:
- [ ] Captured from actual application (not mock/staged)
- [ ] Data visible matches database state at capture time
- [ ] Caption accurately describes what's shown
- [ ] If test data, explicitly labeled as such
- [ ] No LaTeX/code artifacts visible in rendered output

---

## Updated Guide Structure Recommendations

### Recommended Page Order:
1. **Executive Summary** (NEW - currently missing)
2. **Live Chatbot Interface** (Page 3 - most impressive, hook attention)
3. **360° Golden Record Demo** (NEW - core value proposition)
4. **Multi-Message User Story** (Page 5-9)
5. **Architecture** (Page 2 - context after seeing value)
6. **Data Integration** (Page 10-11)
7. **Email Activation** (Page 12-13)
8. **Backend Verification** (Page 18-20)
9. **Production Readiness** (Page 21)

### Content Additions:
- **Executive Summary** (1 paragraph at top)
- **Business Value Quantification** (bullet points on marketing/sales benefits)
- **Risk/Concern Section** (GDPR, sync frequency, OAuth failure mitigation)
- **Cost/Resource Section** (PostgreSQL hosting, OpenAI costs, Resend pricing)

---

## Conclusion

The Illustrated Guide demonstrates component existence but **fails to prove end-to-end integration** with realistic data. To become a credible source of truth, it must:

1. Fix all screenshot/caption mismatches
2. Add the 360° Golden Record demonstration (core value)
3. Prove segment activation actually works with real data volumes
4. Populate realistic mock data across all source systems
5. Add technical verifications (MCP, workflow execution, CSV validation)

**Current State:** Beta/POC with gaps  
**Target State:** Source of Truth with verified demonstrations  
**Estimated Work:** 2-3 sessions to generate missing screenshots and mock data

---

## NEW CRITICAL FINDING (2026-03-08 17:36 CET)

### ❌ FOUR-SOURCE 360° IS A FALSE CLAIM - OBSERVED CONTRADICTION

**Update (2026-03-08 19:20 CET):** Option B is now implemented in the codebase. Migration `007_add_autotask_to_unified_360.sql` plus a full Autotask resync produced `linked_all=1` for B.B.S. Entreprise, and `query_unified_360` now exposes Autotask support data. This section remains as historical audit evidence of the earlier contradiction; the active blocker has narrowed to refreshing the guide evidence/captions and proving the UID-first privacy boundary.

**Status:** VERIFIED via direct PostgreSQL query  
**Severity:** CRITICAL - Undermines core value proposition  
**Evidence Location:** Local PostgreSQL `unified_company_360` view

#### The Claim

The ILLUSTRATED_GUIDE implies a "four-source 360°" customer view:
- KBO (Official Registry)
- Teamleader (CRM)
- Exact Online (Accounting)
- Autotask (PSA/Tickets)

Specific claims from the guide:
- "15 Companies Linked Across All 3 Sources" (Phase 5)
- "Autotask (PSA): 5 companies, 5 tickets, ✅ Mock ready" (Data Foundation table)
- B.B.S. Entreprise example shows `linked_both` status (implying KBO + Teamleader + Exact)

#### The Verified Reality

```sql
-- Identity link status distribution from unified_company_360
SELECT identity_link_status, COUNT(*) FROM unified_company_360 GROUP BY identity_link_status;
```

| Status | Count | Meaning |
|--------|-------|---------|
| `kbo_only` | 1,940,588 | KBO data only, no CRM/Exact link |
| `linked_exact` | 8 | KBO + Exact only |
| `linked_teamleader` | 6 | KBO + Teamleader only |
| `linked_both` | **1** | **KBO + Teamleader + Exact** |

**ONLY 1 COMPANY** (B.B.S. Entreprise) has the `linked_both` status the guide showcases.

```sql
-- Source identity links table (canonical link table)
SELECT source_system, COUNT(*) FROM source_identity_links GROUP BY source_system;
```

| Source | Count |
|--------|-------|
| `teamleader` | **1** |

**The guide claims 15 linked companies. Reality: 1 link record exists.**

```sql
-- Autotask data exists but is NOT linked
SELECT COUNT(*) FROM autotask_companies;  -- Result: 5
\d autotask_companies  -- Shows columns
```

**Critical Schema Gap:**
- `autotask_companies` has: `id`, `name`, `address1`, `city`, `tax_id`, ...
- **MISSING:** `kbo_number` column
- **MISSING:** `organization_uid` column
- **Result:** Autotask companies CANNOT be linked via KBO-based identity resolution

```sql
-- Unified view column inspection
\d+ unified_company_360
```

**View Scope Verification:**
- Columns present: `kbo_*`, `tl_*` (Teamleader), `exact_*` (Exact)
- **NO `autotask_*` columns exist**
- The view definition in `006_add_unified_360_views.sql` only JOINs:
  - `companies` (KBO)
  - `crm_companies` (Teamleader)
  - `exact_customers` (Exact)

#### The Contradiction

| Guide Claim | Verified Fact | Status |
|-------------|---------------|--------|
| "15 Companies Linked Across All 3 Sources" | Only 1 company has linked_both status | **FALSE** |
| Autotask integrated into 360° view | Autotask NOT in unified_company_360 | **FALSE** |
| Four-source unified profile | Only 3 sources implemented (KBO+TL+Exact) | **FALSE** |
| source_identity_links populated | Only 1 record (teamleader) | **FALSE** |

#### Why This Matters

The **360° Golden Record** is the PRIMARY value proposition of the CDP. The guide implies this works across all four sources, but:

1. **Autotask data is orphaned** - 5 companies exist but can't be queried via the unified interface
2. **The "15 linked companies" story is fabricated** - only 1 company actually has the claimed linkage
3. **The IT1 division story is unproven** - No ticket/contract data appears in any 360° query
4. **User expectations are misaligned** - A reader would expect to query Autotask data through the chatbot

#### Required Fixes

**Option A - Correct the Guide (Minimal):**
1. Change "15 Companies Linked" to "1 Company with Full Linkage Demonstrated"
2. Change Autotask status from "✅ Mock ready" to "⚠️ Data exists (5 companies) but not yet linked to 360° view"
3. Explicitly state the 360° view covers **3 sources** (KBO + Teamleader + Exact)
4. Remove or qualify any claims implying Autotask integration

**Option B - Implement Four-Source (Complete):**
1. Add `kbo_number` column to `autotask_companies` table
2. Update `unified_company_360` view to LEFT JOIN `autotask_companies`
3. Add `autotask_*` columns to the view (tickets, contracts)
4. Populate `source_identity_links` for Autotask records
5. Update `unified_360_queries.py` to expose Autotask data
6. Re-verify with actual query: "Show me companies with open Autotask tickets"

#### Evidence Preservation

**Verification Timestamp:** 2026-03-08T17:36:00+01:00  
**Verified By:** PostgreSQL direct query on local Docker instance  
**Database:** `postgresql://cdpadmin:cdpadmin123@localhost:5432/cdp`  
**Files Examined:**
- `scripts/migrations/006_add_unified_360_views.sql` (view definition)
- `src/services/unified_360_queries.py` (query service)
- `src/services/projection.py` (Tracardi projection)

**Related Documentation Updates:**
- `PROJECT_STATE.yaml` - Added `verified_facts.four_source_360_gap`
- `STATUS.md` - Updated Integrations section
- `NEXT_ACTIONS.md` - Added CRITICAL blocker
- `WORKLOG.md` - Session log entry

---
