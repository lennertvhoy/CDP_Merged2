# Illustrated Guide Audit Report
**Date:** 2026-03-08  
**Auditor:** AI Agent following AGENTS.md protocol  
**Purpose:** Verify screenshots match descriptions, identify mismatches, define required demonstrations

---

## Executive Summary

The Illustrated Guide presents a compelling POC narrative but contains **critical mismatches** between screenshots and descriptions, **missing demonstrations** of core value propositions, and **data inconsistencies** that undermine its credibility as a source of truth.

**Grade: C+** - Components exist but end-to-end integration is not proven with realistic data.

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

### 2. ❌ DATA SCALE TABLE - INCONSISTENT NUMBERS
| Source | Guide Shows | Actual (PROJECT_STATE.yaml) |
|--------|-------------|----------------------------|
| Exact Online invoices | 60 | 78 |
| Software in Brussels | 1,652 (Phase 2) vs 1,897 (Phase 3) | 1,897 (as of latest verification) |

**Issue:** Phase 2 shows 1,652 software companies in Brussels, Phase 3 shows 1,897. The difference is explained in PROJECT_STATE.yaml (NACE code resolution scope), but this discrepancy without explanation undermines credibility.

**Fix Required:** Explain the NACE resolution difference or use consistent numbers throughout.

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

**Current State:** The `unified_company_360` view exists and query tools are implemented, but NO DEMONSTRATION exists in the guide.

---

### ❌ Segment Activation with Real Data
**What it is:** Actually pushing a segment of 1,652 companies to Resend and verifying they appear as a populated audience.

**Current Gap:** 
- Guide shows Resend dashboard with 9 emails sent (test data)
- Guide shows "graceful handling of API limits" (error screenshot)
- **MISSING:** The success path - a Resend audience actually containing 1,652 contacts from the CDP

**Required Evidence:**
1. Chatbot: "Pushing 1,652 contacts to Resend..."
2. Resend Audience page showing "Software companies in Brussels" with 1,652 contacts
3. Audience detail showing actual email addresses from the CDP

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
- [ ] Fix data scale table with current accurate numbers

### Priority 2: Generate Missing Demonstrations
- [ ] **360° Golden Record:** Run query "Show me complete profile for [specific company]" and capture unified view
- [ ] **Segment Activation:** Push 1,652 software companies segment to Resend, capture populated audience
- [ ] **CSV Export:** Download and open CSV, screenshot showing all 9 fields with data

### Priority 3: Populate Realistic Mock Data
- [ ] Create 50+ hyperrealistic companies in Teamleader
- [ ] Create corresponding invoices in Exact Online
- [ ] Ensure VAT number matching across systems
- [ ] Re-run syncs to populate PostgreSQL with rich test data

### Priority 4: Additional Technical Verifications
- [ ] Capture MCP server logs showing PostgreSQL queries
- [ ] Trigger test bounce event, capture workflow execution logs
- [ ] Document NACE resolution discrepancy (1,652 vs 1,897) with explanation

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
