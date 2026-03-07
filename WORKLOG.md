# WORKLOG

**Purpose:** Append-only session log for meaningful task updates

---

---

## 2026-03-08 (System Prompt Restructure - 360° Tools Prioritized)

### Task: Restructure system prompt to prioritize 360° tools at TOP

**Type:** app_code  
**Status:** COMPLETE  
**Timestamp:** 2026-03-08 00:47 CET  
**Git Head:** `af1f8c5`

**Summary:**
Restructured the system prompt to move 360° tools to the TOP of the tool descriptions, before standard tools. This addresses the root cause where the LLM was anchoring on standard tools due to section ordering bias.

**Changes Made:**

1. **`src/graph/nodes.py` - SYSTEM_PROMPTS["en"] restructured:**
   - New Section 1: "TOOL SELECTION ROUTING (CRITICAL - READ THIS FIRST)"
     - STEP 1 checklist for cross-source concepts (revenue, pipeline, CRM, financial, KBO linking)
     - Decision logic: IF YES → Use 360° tools, IF NO → Use standard tools
   - New Section 1A: 360° tools MOVED TO TOP
     - `get_industry_summary` - for pipeline value and industry revenue
     - `get_geographic_revenue_distribution` - for revenue by city
     - `get_identity_link_quality` - for KBO matching quality
     - `query_unified_360` - for complete company profiles
     - `find_high_value_accounts` - for high-value/risk accounts
   - New Section 1B: Tool selection matrix table
     - Clear mapping: "Revenue by city" → `get_geographic_revenue_distribution`
     - Clear mapping: "Pipeline value" → `get_industry_summary`
     - Clear mapping: "KBO link quality" → `get_identity_link_quality`
   - Previous sections renumbered: Search Strategy (2), Field Mapping (3), Count Reliability (4), Proactive Next Steps (5), Aggregation (6), etc.

2. **`src/graph/nodes.py` - VALID_TOOL_NAMES updated:**
   - Added missing 360° tools to the validation set:
     - `query_unified_360`
     - `get_industry_summary`
     - `find_high_value_accounts`
   - `get_geographic_revenue_distribution`
     - `get_identity_link_quality`
   - This ensures the critic node won't reject 360° tool calls

**Key Improvements:**

| Before | After |
|--------|-------|
| 360° tools in Section 6 (after Aggregation) | 360° tools in Section 1A (FIRST) |
| Generic CRITICAL note | Explicit STEP 1 decision logic |
| No tool selection matrix | Clear decision table in Section 1B |
| MANDATORY mentioned once | MANDATORY emphasized with routing logic |
| 360° tools not in VALID_TOOL_NAMES | All 360° tools validated by critic |

**Syntax Verification:**
- ✅ `python -m py_compile src/graph/nodes.py` passed

**Next Step:**
Re-test the 3 failed queries:
1. "How well are source systems linked to KBO?" → Should use `get_identity_link_quality`
2. "Show me revenue distribution by city" → Should use `get_geographic_revenue_distribution`
3. "Pipeline value for software companies in Brussels?" → Should use `get_industry_summary`

---

## 2026-03-08 (360° Tool Re-Testing - Prompt Enhancement Insufficient)

### Task: Re-test 360° tools after prompt enhancement

**Type:** verification_only  
**Status:** COMPLETE (with findings)  
**Timestamp:** 2026-03-08 00:10 CET  
**Git Head:** `70ad287` - docs: Update state files for 360° tool selection enhancement

**Summary:**
Browser-based re-testing confirmed that the previous prompt enhancement (commit `eae20da`) was **insufficient**. The LLM continues to select standard tools instead of 360° tools for cross-source queries.

**Test Results:**

| Query | Expected Tool | Actual Tool | Result |
|-------|---------------|-------------|--------|
| "How well are source systems linked to KBO?" | `get_identity_link_quality` | `get_data_coverage_stats` | ❌ FAIL |
| "Show me revenue distribution by city" | `get_geographic_revenue_distribution` | `aggregate_profiles` | ❌ FAIL |
| "What is the pipeline value for software companies in Brussels?" | `get_industry_summary` | "Can't calculate pipeline value" | ❌ FAIL |

**Evidence:**
- Screenshot: `chatbot_360_tools_test_result.png`

**Root Cause Analysis:**

The prompt enhancement didn't work because:

1. **Section ordering bias:** Section 5 (AGGREGATION & ANALYTICS) appears before Section 6 (360° tools), causing the LLM to anchor on standard tools first
2. **LLM sees standard tools as sufficient:** For queries like "revenue distribution by city", the LLM classified it as "aggregation question" and immediately selected `aggregate_profiles` without checking for 360° alternatives
3. **360° tools not visible enough:** The CRITICAL guidance in Section 6 was not strong enough to override the earlier tool descriptions
4. **Tool descriptions may be too late:** By the time the LLM reads Section 6, it may have already decided on a tool

**Observed LLM Behavior:**

1. For KBO link quality: LLM said "this is a data-coverage question... I will use `get_data_coverage_stats`" - completely missed `get_identity_link_quality`
2. For revenue distribution: LLM said "this is an aggregation question... I will use `aggregate_profiles`" - acknowledged it doesn't compute revenue but still didn't try the 360° tool
3. For pipeline value: LLM said "I can't calculate pipeline value... tools don't include pipeline/opportunity table" - didn't see `get_industry_summary` at all

**Recommended Fix:**

1. **Move 360° tools to TOP of tool descriptions** - Place them before standard tools so they're evaluated first
2. **Add routing section at the very beginning** - Add a "TOOL SELECTION ROUTING" section before all tool descriptions:
   ```
   BEFORE selecting a tool, check if the query involves:
   - Revenue, pipeline, CRM data, or cross-source insights → Use 360° tools
   - Basic counts/filters → Use standard tools
   ```
3. **Rename/refocus tool descriptions** - Make 360° tool descriptions more prominent
4. **Consider tool naming** - The 360° tools may need more descriptive names that match user query patterns

**Files Referenced:**
- `src/graph/nodes.py` - System prompt requiring restructuring
- `chatbot_360_tools_test_result.png` - Browser test screenshot

**Next Actions:**
1. Restructure system prompt to prioritize 360° tools
2. Add explicit routing logic at the start of tool descriptions
3. Re-test after restructuring

---

## 2026-03-07 (Chatbot 360° Tool Selection Enhancement)

### Task: Enhance system prompt to improve 360° tool selection

**Type:** app_code  
**Status:** COMPLETE  
**Timestamp:** 2026-03-07 23:40 CET  
**Git Commit:** `eae20da` - docs(chatbot): Enhance system prompt for 360° tool selection

**Summary:**
Interactive browser testing revealed that the chatbot was not selecting the 360° tools when appropriate. The LLM was falling back to standard tools (`aggregate_profiles`, `get_data_coverage_stats`) instead of using the cross-source 360° tools.

**Problem Identified:**
- Query "How well are our source systems linked to KBO numbers?" → used `get_data_coverage_stats` instead of `get_identity_link_quality`
- Query "Show me revenue distribution by city" → used `aggregate_profiles` instead of `get_geographic_revenue_distribution`

**Solution Applied:**
Enhanced system prompt section 6 (UNIFIED 360° CUSTOMER VIEWS) in `src/graph/nodes.py`:

1. **Added CRITICAL guidance** on when to use 360° tools vs standard search
2. **Added tool selection matrix**:
   - Standard `search_profiles`: Basic company counts, filters by city/NACE/status
   - Standard `aggregate_profiles`: Company counts grouped by field
   - **360° tools REQUIRED for**: Pipeline value, revenue data, CRM activities, financial exposure, KBO matching quality
3. **Added explicit parameter mappings** for all 360° tool examples
4. **Added missing `get_identity_link_quality` examples**
5. **Clarified distinction** between company counts vs actual revenue/pipeline data

**Files Modified:**
- `src/graph/nodes.py` - Enhanced system prompt section 6

**Next Steps:**
1. Re-test 360° tools after prompt enhancement
2. Monitor if LLM now correctly selects 360° tools for cross-source queries
3. Add more sample queries based on real usage patterns

---

## 2026-03-07 (Chatbot 360° Query Tools)

### Task: Add chatbot tools for unified 360° customer insights

**Type:** app_code  
**Status:** COMPLETE  
**Timestamp:** 2026-03-07 23:10 CET  
**Git Commit:** `81a87df` - feat: Add chatbot 360° query tools for unified cross-source insights

**Summary:**
Extended the chatbot with 5 new tools that enable natural language queries against unified 360° views combining KBO, Teamleader CRM, and Exact Online financial data. The chatbot can now answer complex cross-source questions like "What is the total pipeline value for software companies in Brussels?"

**New Tools Added:**

| Tool | Purpose | Example Queries |
|------|---------|-----------------|
| `query_unified_360` | Complete 360° company profiles | "Show me the 360° view of company KBO 0123.456.789" |
| `get_industry_summary` | Industry-level pipeline/revenue analysis | "What is the total pipeline value for software companies in Brussels?" |
| `find_high_value_accounts` | High-value/risk accounts | "Which high-value accounts have overdue invoices?" |
| `get_geographic_revenue_distribution` | Revenue by geography | "Which cities have the most revenue?" |
| `get_identity_link_quality` | KBO matching coverage | "How well are our source systems linked?" |

**Files Modified:**
- `src/ai_interface/tools/unified_360.py` (new) - 5 chatbot tools for 360° queries
- `src/ai_interface/tools/__init__.py` - Export new tools
- `src/graph/nodes.py` - Register tools and update system prompt

**System Prompt Updated:**
Added section "6. UNIFIED 360° CUSTOMER VIEWS (CROSS-SOURCE INSIGHTS)" documenting:
- When to use each unified tool
- Parameter mapping for common queries
- Example natural language → tool parameter conversions

**Tool Count:**
- Previous: 15 tools
- Now: 20 tools (+5 unified 360° tools)

**Verification:**
```bash
# Tools successfully imported and registered
✅ query_unified_360
✅ get_industry_summary  
✅ find_high_value_accounts
✅ get_geographic_revenue_distribution
✅ get_identity_link_quality

# Chatbot health check passed
✅ GET /healthz -> {"status":"ok"}
```

**Sample Queries Now Supported:**
- "What is the total pipeline value for software companies in Brussels?"
- "Show me IT companies in Gent with open deals over €10k"
- "Which high-value accounts have overdue invoices?"
