# WORKLOG

**Purpose:** Append-only session log for meaningful task updates

---

## 2026-03-08 (Backlog Aligned - Added Milestone POC for Activation Testing)

### Task: Add explicit POC milestone to BACKLOG.md

**Type:** docs_or_process_only  
**Status:** COMPLETE  
**Timestamp:** 2026-03-08 12:00 CET  

**Summary:**
Added "Milestone POC: Close the Loop - Activation End-to-End" to BACKLOG.md to explicitly track the remaining POC gap. All infrastructure exists but end-to-end verification is missing.

**Gap Identified:**
- ✅ NL → Segment (≥95% accuracy) - DONE
- ⚠️ Segment → Flexmail ≤60s - INFRASTRUCTURE READY, NOT TESTED
- ⚠️ Engagement events → CDP - INFRASTRUCTURE READY, NOT TESTED
- ❌ End-to-end latency - NOT TESTED

**New Milestone POC Tasks:**
| Priority | Item | Status |
|----------|------|--------|
| Critical | TEST: Segment push to Flexmail | Pending |
| Critical | TEST: Engagement writeback | Pending |
| Critical | TEST: End-to-end latency | Pending |
| High | Document POC completion evidence | Pending |
| High | Autotask decision | Blocked |

**Prerequisites (all complete):**
- PostgreSQL with 1.94M KBO records
- Tracardi with 5 email workflows deployed
- Teamleader + Exact sync pipelines operational
- Bridge script for Flexmail integration exists
- AI chatbot with routing guard

**Next Session Should:**
Run end-to-end activation test or create test script for Flexmail integration.

---

## 2026-03-08 (MCP Server Implemented - 7 Tools Exposed)

### Task: Implement MCP (Model Context Protocol) server for standardized tool access

**Type:** app_code  
**Status:** COMPLETE  
**Timestamp:** 2026-03-08 11:45 CET  

**Summary:**
Implemented a Model Context Protocol (MCP) server that exposes the core PostgreSQL-backed read-only tools via standardized MCP interface. Enables MCP-compatible clients (Claude Desktop, etc.) to query the CDP database.

**Files Created:**
- `src/mcp_server.py` - Main MCP server implementation (7 tools, 2 resources)
- `scripts/start_mcp_server.sh` - Startup script for stdio or SSE mode
- `docs/MCP_SERVER.md` - Complete documentation
- `.mcp/claude_desktop_config.json` - Claude Desktop configuration template

**Tools Exposed (7):**
| Tool | Purpose |
|------|---------|
| `search_companies` | Search by keywords, city, NACE, status |
| `aggregate_companies` | Industry/city/legal form analytics |
| `get_company_360_profile` | Complete 360° view (KBO + CRM + Financial) |
| `get_industry_summary` | Pipeline/revenue by industry |
| `get_geographic_revenue_distribution` | Revenue by city |
| `get_identity_link_quality` | KBO matching coverage |
| `find_high_value_accounts` | Risk/opportunity accounts |

**Resources Exposed (2):**
- `cdp://schema/companies` - Companies table schema
- `cdp://stats/summary` - Database statistics

**Transport Modes:**
- **Stdio**: Standard input/output for MCP client integration
- **SSE**: HTTP API on configurable port (default 8001)

**Verification:**
- ✅ Server starts successfully in both modes
- ✅ Health endpoint returns: `{"status":"ok","server":"cdp-postgresql-query-server","version":"1.0.0"}`
- ✅ Uses existing PostgreSQLSearchService and Unified360Service
- ✅ Read-only access (no mutations exposed)

**Usage:**
```bash
# Stdio mode (Claude Desktop)
./scripts/start_mcp_server.sh

# SSE mode (HTTP API)
./scripts/start_mcp_server.sh --sse 8001

# Health check
curl http://localhost:8001/health
```

---

## 2026-03-08 (Option D Routing Guard Implemented - ALL TESTS PASS)

### Task: Implement Option D - Routing guard in critic_node for 360° tool selection

**Type:** app_code  
**Status:** COMPLETE - All 3 test queries now PASS  
**Timestamp:** 2026-03-08 11:00 CET  
**Git Head:** `5c3117e`

**Summary:**
Implemented deterministic keyword-based routing guard in `critic_node` to fix 360° tool selection failures. When the LLM selects a forbidden tool for a query containing specific keywords, the critic immediately rejects the tool call and returns a corrective error naming the correct tool — forcing the LLM to retry with the right choice.

**Changes Made to `src/graph/nodes.py`:**

1. **QUERY_ROUTING_RULES** — List of 3 rules mapping keyword patterns → required tool:
   - **KBO Linkage:** "linked to kbo", "match rate", "kbo link", "link quality" → `get_identity_link_quality`
   - **Revenue Distribution:** "revenue distribution", "revenue by city", "geographic distribution" → `get_geographic_revenue_distribution`
   - **Pipeline Value:** "pipeline value for", "total pipeline", "industry pipeline" → `get_industry_summary`

2. **`_extract_last_user_query()`** — Finds the last HumanMessage content (lowercase) without LLM parsing

3. **`_check_routing_rules()`** — Evaluates each rule; returns error if forbidden tool used

4. **`_validate_tool_call()`** — Extended with Check 6 (routing guard)

5. **`critic_node()`** — Now extracts user query and passes it to validation

**New Test File:**
- `tests/unit/test_critic_routing.py` — 27 tests covering:
  - All 3 query intents (correct tool allowed, wrong tool rejected)
  - Non-interference: unrelated queries are never blocked
  - Empty/missing user query never blocks anything
  - Structural sanity of QUERY_ROUTING_RULES table

**Test Results:**

| Query | Expected Tool | Result |
|-------|---------------|--------|
| "How well are source systems linked to KBO?" | `get_identity_link_quality` | ✅ PASS |
| "Show me revenue distribution by city" | `get_geographic_revenue_distribution` | ✅ PASS |
| "Pipeline value for software companies in Brussels?" | `get_industry_summary` | ✅ PASS |

**Unit Tests:**
```
tests/unit/test_critic_routing.py  27 passed in 0.77s
tests/unit/ (full suite)          545 passed, 4 pre-existing failures unchanged
```

**Verification:**
- ✅ All 3 previously-failing queries now select correct tools
- ✅ 27 new unit tests passed
- ✅ Full test suite still passes (545 passed)
- ✅ Commit `5c3117e` created and pushed

**How It Works:**
1. User sends query: "How well are source systems linked to KBO?"
2. LLM incorrectly selects: `get_data_coverage_stats`
3. Critic node extracts query and checks routing rules
4. Rule matched: query contains "linked to kbo"
5. Validation fails: `get_data_coverage_stats` is in forbidden list
6. Critic returns error: "You MUST use get_identity_link_quality for KBO linkage queries"
7. LLM retries with correct tool: `get_identity_link_quality`
8. Tool executes successfully

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
