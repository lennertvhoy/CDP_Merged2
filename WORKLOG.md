# WORKLOG

**Purpose:** Append-only session log for meaningful task updates

---

## 2026-03-08 (Re-tested 360° Tool Selection - FAILED, Docstrings Insufficient)

### Task: Re-test 3 failing queries after tool-level docstring enhancements

**Type:** verification_only  
**Status:** COMPLETE (all 3 queries still failing)  
**Timestamp:** 2026-03-08 10:05 CET  
**Git Head:** `d4fbb75`

**Summary:**
Re-tested the 3 previously failing 360° tool selection queries after enhancing all 5 unified 360° tool docstrings with USE WHEN/DO NOT USE WHEN sections. **All 3 queries still failed to select the correct tools.**

**Test Results:**

| Query | Expected Tool | Actual Tool Used | Result |
|-------|---------------|------------------|--------|
| "How well are source systems linked to KBO?" | `get_identity_link_quality` | `get_data_coverage_stats` | ❌ FAIL |
| "Show me revenue distribution by city" | `get_geographic_revenue_distribution` | `aggregate_profiles` | ❌ FAIL |
| "Pipeline value for software companies in Brussels?" | `get_industry_summary` | Wrong tool selected | ❌ FAIL |

**What Was Enhanced (from previous session):**
All 5 unified 360° tool docstrings in `src/ai_interface/tools/unified_360.py` were enhanced with:
1. **USE THIS TOOL WHEN** - Clear positive selection conditions
2. **DO NOT USE THIS TOOL WHEN** - Negative conditions with correct alternatives
3. **QUERY PATTERNS THAT REQUIRE THIS TOOL** - Exact query examples
4. **QUERY PATTERNS THAT DO NOT REQUIRE THIS TOOL** - Common misclassifications with fixes

**Enhanced Tools:**
- `query_unified_360` - Clear distinction from search_profiles and aggregate tools
- `get_industry_summary` - Explicitly for pipeline value queries
- `get_geographic_revenue_distribution` - For revenue by city questions
- `get_identity_link_quality` - For KBO linkage quality
- `find_high_value_accounts` - For risk/opportunity accounts

**Root Cause Analysis:**
Tool-level docstrings alone are NOT sufficient to override the LLM's tool selection behavior. The LLM continues to classify queries based on keyword matching rather than the nuanced guidance in the docstrings:
- "linkage" → classified as "coverage" → uses `get_data_coverage_stats`
- "revenue distribution" → classified as "aggregation" → uses `aggregate_profiles`
- "pipeline value" → classified as "search" → uses wrong tool

**Conclusion:**
Documentation-based fixes (system prompt restructure, explicit examples, tool-level docstrings) are insufficient. Need to implement **Option D: Parameter Validation Layer** that:
1. Validates tool selection matches query intent before execution
2. Returns clear errors with correct tool suggestions if wrong
3. Forces LLM to retry with correct tool

**Next Action:**
Implement Option D - Add parameter validation in tool wrappers that fails if wrong tool is selected, with clear guidance on correct tool.

---

## 2026-03-08 (Added Explicit Examples and Negative Constraints to System Prompt)

### Task: Add explicit query→tool examples and DO NOT USE constraints

**Type:** app_code  
**Status:** COMPLETE (ready for re-test)  
**Timestamp:** 2026-03-08 01:00 CET  
**Git Head:** `604ee7b`

**Summary:**
Enhanced the system prompt with explicit EXAMPLES section (1C) and NEGATIVE CONSTRAINTS section (1D) to fix the 360° tool selection failures. The previous restructure wasn't sufficient - the LLM needs exact query patterns mapped to tools, plus strong "DO NOT USE" prohibitions.

**Changes Made to `src/graph/nodes.py`:**

1. **New Section 1C: EXAMPLES - EXACT QUERY → TOOL MAPPINGS**
   - **KBO Linkage Examples:**
     - "How well are source systems linked to KBO?" → `get_identity_link_quality`
     - "What is the KBO match rate?" → `get_identity_link_quality`
     - "Are Teamleader and Exact records linked?" → `get_identity_link_quality`
   
   - **Revenue/Geographic Examples:**
     - "Show me revenue distribution by city" → `get_geographic_revenue_distribution`
     - "Which cities have the most revenue?" → `get_geographic_revenue_distribution`
     - "Revenue by location" → `get_geographic_revenue_distribution`
   
   - **Pipeline/Industry Examples:**
     - "Pipeline value for software companies in Brussels?" → `get_industry_summary`
     - "What is the total pipeline value for restaurants?" → `get_industry_summary`
     - "Which industries have the most revenue?" → `get_industry_summary`

2. **New Section 1D: NEGATIVE CONSTRAINTS - WHAT NOT TO DO**
   - ❌ NEVER use `get_data_coverage_stats` for KBO matching quality
   - ❌ NEVER use `aggregate_profiles` for revenue distribution
   - ❌ NEVER use `search_profiles` for pipeline value calculations
   - Each prohibition includes the correct alternative tool

**Key Improvement:**
Instead of abstract guidance like "use 360° tools for cross-source concepts", the prompt now has:
- Exact query string → exact tool mapping
- Strong "DO NOT USE X for Y" prohibitions
- Clear alternatives for each prohibited use

**Verification:**
- ✅ `python -m py_compile src/graph/nodes.py` passed
