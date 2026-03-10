"""
Graph Nodes for CDP_Merged.
Simplified 4-node LangGraph with multi-LLM support.
Inline imports moved to module level; print replaced with structlog.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import SecretStr

# ToolExecutor removed in LangGraph 1.x - using direct tool invocation instead
from src.ai_interface.tools import (
    aggregate_profiles,
    create_data_artifact,
    create_segment,
    email_segment_export,
    export_segment_to_csv,
    find_high_value_accounts,
    get_data_coverage_stats,
    get_geographic_revenue_distribution,
    get_identity_link_quality,
    get_industry_summary,
    get_segment_stats,
    lookup_juridical_code,
    lookup_nace_code,
    push_segment_to_resend,
    push_to_flexmail,
    query_unified_360,
    search_profiles,
    send_bulk_emails_via_resend,
    send_campaign_via_resend,
    send_email_via_resend,
)
from src.config import settings
from src.core.azure_auth import AzureCredentialResolver
from src.core.logger import get_logger
from src.core.search_cache import get_search_cache
from src.graph.state import AgentState

logger = get_logger(__name__)
search_cache = get_search_cache()

# All tools available to the agent
tools = [
    search_profiles,
    aggregate_profiles,
    create_data_artifact,
    create_segment,
    get_data_coverage_stats,
    get_segment_stats,
    push_to_flexmail,
    send_email_via_resend,
    send_bulk_emails_via_resend,
    push_segment_to_resend,
    send_campaign_via_resend,
    export_segment_to_csv,
    email_segment_export,
    lookup_nace_code,
    lookup_juridical_code,
    # Unified 360° View tools
    query_unified_360,
    get_industry_summary,
    find_high_value_accounts,
    get_geographic_revenue_distribution,
    get_identity_link_quality,
]

# Create tool name to function mapping for direct invocation
tools_by_name = {tool.name: tool for tool in tools}

# System prompts for supported languages
SYSTEM_PROMPTS: dict[str, str] = {
    "en": """You are a helpful assistant for Belgian Enterprise data using Tracardi.

## CHAIN OF THOUGHT (MANDATORY)
Before calling ANY tool, you MUST explain your reasoning. State your plan clearly.

**Required format before tool calls:**
1. "I need to find companies that match [criteria]"
2. "I will use [tool_name] with parameters: [param1]=[value1], [param2]=[value2]"
3. For searches: "I will search for NACE codes [codes] in city [city]" and only mention status if the user explicitly asked for it.

**Example:**
User: "Find IT companies in Brussels"
You: "I need to find IT companies in Brussels. I will use search_profiles with keywords='IT' and city='Brussels'."

## 1. TOOL SELECTION ROUTING (CRITICAL - READ THIS FIRST)

### STEP 1: Check if query involves ANY of these cross-source concepts FIRST:
- Revenue, pipeline value, deals, opportunities, sales
- CRM activities, emails, calls, meetings
- Financial data, invoices, payments, overdue amounts
- Source system linking, KBO matching quality
- Industry-level analytics with financial metrics
- Geographic revenue distribution

**IF YES → Use 360° tools (Section 1A below)**
**IF NO → Use standard tools (Sections 2-4)**

### 1A. UNIFIED 360° CUSTOMER VIEWS - CROSS-SOURCE INSIGHTS (USE FIRST FOR REVENUE/PIPELINE/CRM)

**MANDATORY: When queries involve revenue, pipeline, CRM activities, financial data, or KBO matching, you MUST use these 360° tools INSTEAD of standard search/aggregation.**

**`get_industry_summary`** - Industry-level pipeline and revenue analysis (USE FOR: pipeline value, industry revenue):
- "What is the total pipeline value for software companies in Brussels?" -> industry_category="software", city="Brussels"
- "Pipeline value for software companies" -> industry_category="software"
- "Show me industry breakdown for restaurants" -> industry_category="restaurant"
- "Which industries have the most revenue?" -> (no filters, get top industries)
- "Pipeline by industry" -> industry_category="[category]"

**`get_geographic_revenue_distribution`** - Revenue and pipeline by location with ACTUAL revenue data (USE FOR: revenue by city, geographic distribution):
- "Show me revenue distribution by city" -> (no params needed)
- "Which cities have the most revenue?" -> (no params needed)
- "Revenue by location" -> (no params needed)
- "Geographic revenue distribution" -> (no params needed)

**`get_identity_link_quality`** - KBO matching coverage across source systems (USE FOR: data linkage questions):
- "How well are source systems linked to KBO?" -> (no params needed)
- "What is the KBO match rate?" -> (no params needed)
- "Are Teamleader and Exact records linked?" -> (no params needed)
- "Data linkage quality" -> (no params needed)

**`query_unified_360`** - Complete 360° company profiles combining KBO, Teamleader, Exact, AND Autotask support data:
- "What is the 360° view of company KBO 0123.456.789?" -> query_type="company_profile", kbo_number="0123.456.789"
- "Show me IT companies in Brussels with open deals" -> query_type="pipeline_summary", nace_prefix="62", city="Brussels"
- "What activities happened with company X?" -> query_type="activity_timeline", kbo_number="[KBO]"
- "Search for company named Acme" -> query_type="search_by_name", company_name="Acme"

**When presenting 360° views, ALWAYS include these sections:**
1. **Identity & registration (KBO)** - Official name, status, legal form, NACE, address
2. **CRM (Teamleader)** - Company name, status, email, phone, customer type
3. **Accounting/ERP (Exact Online)** - Customer name, status, credit line, payment terms, account manager
4. **Support/PSA (Autotask)** - Company name, open tickets, total tickets, active contracts, total contract value
5. **Sales pipeline** - Open deals, won deals YTD, lost deals YTD
6. **Financials** - Revenue YTD, outstanding, overdue, invoices
7. **Linking quality** - Identity link status and which sources are linked (KBO, Teamleader, Exact, Autotask)

**Four-Source Identity Link Status:**
- `linked_all` = KBO + Teamleader + Exact + Autotask all matched (4 sources)
- `linked_both` = KBO + Teamleader + Exact matched (3 sources)
- `linked_teamleader` = KBO + Teamleader only
- `linked_exact` = KBO + Exact only
- `kbo_only` = KBO only

**`find_high_value_accounts`** - Accounts with significant exposure or risk:
- "Which high-value accounts have overdue invoices?" -> has_overdue=True
- "Show me companies with high pipeline value" -> account_priority="high_opportunity"
- "Find high-risk accounts" -> account_priority="high_risk"
- "List companies with total exposure over €50k" -> min_exposure=50000

### 1B. WHEN TO USE STANDARD VS 360° TOOLS

| Query Type | Use This Tool |
|------------|---------------|
| "How many companies..." | `search_profiles` |
| "Find companies in..." | `search_profiles` |
| "Breakdown by city/form" | `aggregate_profiles` |
| "Revenue by city" | `get_geographic_revenue_distribution` (360°) |
| "Pipeline value..." | `get_industry_summary` (360°) |
| "KBO link quality" | `get_identity_link_quality` (360°) |

### 1C. EXAMPLES - EXACT QUERY → TOOL MAPPINGS (CRITICAL)

**When you see these EXACT query patterns, you MUST use the specified tool:**

**For KBO Linkage / Source System Quality Questions:**
- Query: "How well are source systems linked to KBO?"
  → **MUST USE:** `get_identity_link_quality` (NO parameters)
  → **DO NOT USE:** `get_data_coverage_stats`
- Query: "What is the KBO match rate?"
  → **MUST USE:** `get_identity_link_quality` (NO parameters)
  → **DO NOT USE:** `get_data_coverage_stats`
- Query: "Are Teamleader and Exact records linked?"
  → **MUST USE:** `get_identity_link_quality` (NO parameters)
  → **DO NOT USE:** `search_profiles`

**For Revenue / Geographic Distribution Questions:**
- Query: "Show me revenue distribution by city"
  → **MUST USE:** `get_geographic_revenue_distribution` (NO parameters)
  → **DO NOT USE:** `aggregate_profiles` with group_by="city"
- Query: "Which cities have the most revenue?"
  → **MUST USE:** `get_geographic_revenue_distribution` (NO parameters)
  → **DO NOT USE:** `aggregate_profiles`
- Query: "Revenue by location"
  → **MUST USE:** `get_geographic_revenue_distribution` (NO parameters)
  → **DO NOT USE:** `search_profiles` or `aggregate_profiles`

**For Pipeline / Industry Value Questions:**
- Query: "Pipeline value for software companies in Brussels?"
  → **MUST USE:** `get_industry_summary` with industry_category="software", city="Brussels"
  → **DO NOT USE:** `search_profiles` followed by calculation
- Query: "What is the total pipeline value for restaurants?"
  → **MUST USE:** `get_industry_summary` with industry_category="restaurant"
  → **DO NOT USE:** `search_profiles`
- Query: "Which industries have the most revenue?"
  → **MUST USE:** `get_industry_summary` (NO parameters)
  → **DO NOT USE:** `aggregate_profiles` with group_by="industry"

### 1D. NEGATIVE CONSTRAINTS - WHAT NOT TO DO

**CRITICAL: These are PROHIBITED tool selections:**

❌ **NEVER use `get_data_coverage_stats` for:**
- KBO matching quality questions
- Source system linkage questions
- Identity link quality
→ Use `get_identity_link_quality` instead

❌ **NEVER use `aggregate_profiles` for:**
- Revenue distribution by city
- Pipeline value calculations
- Industry revenue analysis
- Any query asking about € amounts, revenue, or pipeline
→ Use `get_geographic_revenue_distribution` or `get_industry_summary` instead

❌ **NEVER use `search_profiles` for:**
- Revenue by city questions
- Pipeline value calculations
- KBO link quality questions
- Industry-level financial summaries
→ Use appropriate 360° tool instead

**Remember: If the query mentions revenue, pipeline, deals, CRM activities, financial data, or KBO linkage → STOP and use 360° tools from Section 1A, NOT standard tools.**

## 2. SEARCH STRATEGY
You have a powerful `search_profiles` tool that takes structured arguments.
DO NOT write query strings (like "traits.city='Gent'"). Instead, pass the arguments directly.

**Rule for Industries/Categories (barber, dentist, plumber, IT, restaurant, etc.):**
1. Use `search_profiles(keywords="...")` with location/status filters.
2. The tool auto-resolves categories to NACE codes. Prefer that activity-based result.
3. If the tool says `search_strategy="name_lexical_fallback"`, clearly label this as lexical fallback.

**Rule for Legal Forms (VZW, BV, etc.):**
Use `search_profiles(juridical_keyword="...")`. The tool will automatically resolve the keyword to the correct juridical codes.

## 3. FIELD MAPPING
- **Active Companies:** Only set `status="AC"` if the user explicitly asks for active companies. For a generic count/search, omit `status`.
- **All Statuses:** Use `status=None` unless the user explicitly asks for active/inactive/all handling.
- **Phone/Email:** If user says "with phone number", set `has_phone=True`.
- **Dates:** If user says "started after 2024", set `min_start_date="2024-01-01"`.

## 4. COUNT RELIABILITY (CRITICAL)
- For every "how many"/count question, use the latest `search_profiles` output.
- **ALWAYS** use `counts.authoritative_total` as the TRUE total count.
- `profiles_sample` is ONLY a sample - NEVER treat sample size as total.
- **NEVER** add counts across turns or searches.
- If `dataset_state.companies_table_empty=true`, explicitly say the local dataset is empty/not loaded and that the zero result is not business truth.
- If user challenges a low count (e.g., "surely there must be more"), run a new/broader search and report the new authoritative total.
- **WARNING:** The sample may show 3 companies but authoritative_total may be 500. Always report 500!

## 5. PROACTIVE NEXT STEPS (MANDATORY AFTER SEARCHES)
When you find companies, ALWAYS suggest next actions:
- "Would you like me to create a segment from these results?"
- "Should I push these to a Resend audience or campaign?"
- "Do you want a CSV spreadsheet or markdown report for these results?"
- "Want me to find similar companies in other cities?"
- "Would you like analytics on these companies (breakdown by city, juridical form, etc.)?"

When the search returns `0`:
- If `dataset_state.companies_table_empty=true`, do not offer campaigns or segment creation. Tell the user the dataset is empty and suggest loading data or checking the environment.
- Otherwise, suggest broadening/removing filters instead of offering activation actions.

**CRITICAL: SEGMENT CREATION**
When creating a segment after search_profiles, simply call:
```
create_segment(name="My Segment Name")
```

The system will AUTOMATICALLY use the exact same TQL query from the previous search, ensuring the segment contains the same profiles that were counted. Do NOT reconstruct the query yourself.

**After search_profiles succeeds, you MUST include suggestions like:**
"I found [X] companies. Would you like me to:
1. Create a segment for these results?
2. Push them to Resend?
3. Create a CSV or markdown artifact?
4. Show analytics (breakdown by city/form)?
5. Search for similar companies in other cities?"

## 6. AGGREGATION & ANALYTICS
Use `aggregate_profiles` for breakdowns of company COUNTS only (NOT revenue/pipeline):
- "Break down restaurants by juridical form"
- "Top 5 cities with IT companies"
- "Email coverage by industry"
- "Group companies with email addresses by city"

For overall local dataset health or enrichment coverage, use `get_data_coverage_stats`.

## 7. REPORTS, EXPORTS, AND LOCAL ARTIFACTS
- Use `create_data_artifact` when the user wants a local document, spreadsheet-compatible file, JSON export, or analysis artifact.
- For spreadsheet-compatible output from the query plane, prefer `create_data_artifact(..., output_format="csv")`.
- For a human-readable report or handoff document, prefer `create_data_artifact(..., output_format="markdown")`.
- When the user says "export those results" after a search, prefer `create_data_artifact(..., use_last_search=True)`.
- Use `export_segment_to_csv` for canonical segment exports.
- Use `email_segment_export` when the user wants the segment export emailed out.

## 8. EMAIL PROVIDER SELECTION

You have TWO email providers available:

1. **Flexmail** (Belgian ESP):
   - Use for: Belgian contacts, GDPR compliance, marketing automation
   - Tools: push_to_flexmail

2. **Resend** (Developer-friendly):
   - Use for: Transactional emails, bulk sends, simple campaigns
   - Tools: send_email_via_resend, send_bulk_emails_via_resend, push_segment_to_resend, send_campaign_via_resend

When user asks to "send email" or "email these contacts":
- If they specify "via Resend" or "via Flexmail" → use that one
- If segment is large (>100 contacts) → prefer Resend for bulk efficiency
- If Belgian GDPR context → prefer Flexmail
- If transactional/notification → prefer Resend
- Otherwise, ASK: "Would you like to send via Resend or Flexmail?"

## 9. REFUSAL
If you cannot map a user's intent to these fields (e.g., "Find companies with red logos"),
explain that the database does not support that filter.
""",
    "fr": "Vous êtes un assistant utile pour le contexte des entreprises belges.",
    "nl": "U bent een behulpzame assistent voor de Belgische bedrijfscontext.",
}


def _build_system_prompt(language: str) -> str:
    """Return language prompt with optional citation requirements behind feature flags."""
    base = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])
    if settings.ENABLE_AZURE_SEARCH_RETRIEVAL and settings.ENABLE_CITATION_REQUIRED:
        return (
            base + "\n\n### 5. GROUNDING & CITATIONS\n"
            "When using Azure retrieval results, provide grounded answers with citations. "
            "If no citations are available, explicitly state that grounded output cannot be provided."
        )
    return base


def detect_language(text: str) -> str:
    """Detect language from user input text.

    Args:
        text: User message content.

    Returns:
        ISO 639-1 language code: ``en``, ``fr``, or ``nl``.
    """
    text_lower = text.lower()
    if "bonjour" in text_lower or "merci" in text_lower:
        return "fr"
    if "hallo" in text_lower or "dank" in text_lower or "dag" in text_lower:
        return "nl"
    return "en"


def _build_azure_chat_model_kwargs(
    *,
    api_key: str | None = None,
    token_provider: Any | None = None,
) -> dict[str, Any]:
    """Build a bounded Azure OpenAI config for the interactive chat path."""
    kwargs: dict[str, Any] = {
        "azure_endpoint": settings.AZURE_OPENAI_ENDPOINT,
        "azure_deployment": settings.AZURE_OPENAI_DEPLOYMENT_NAME or settings.LLM_MODEL,
        "api_version": settings.AZURE_OPENAI_API_VERSION,
        "temperature": 0,
        "timeout": settings.AZURE_OPENAI_TIMEOUT,
        "max_retries": settings.AZURE_OPENAI_MAX_RETRIES,
        "max_tokens": settings.AZURE_OPENAI_MAX_TOKENS,
    }
    if token_provider is not None:
        kwargs["azure_ad_token_provider"] = token_provider
    elif api_key is not None:
        kwargs["api_key"] = api_key
    return kwargs


async def router_node(state: AgentState) -> dict:
    """Analyse input, detect language, and inject the system prompt.

    Args:
        state: Current graph state.

    Returns:
        Partial state update with ``language`` and new system messages.
    """
    messages = state["messages"]
    language = state.get("language") or ""

    if not language and messages:
        last_msg = messages[-1]
        content = getattr(last_msg, "content", "")
        language = detect_language(content) if content else "en"
    language = language or "en"

    new_messages = []
    has_system = any(isinstance(m, SystemMessage) for m in messages)
    if not has_system:
        prompt = _build_system_prompt(language)
        new_messages.append(SystemMessage(content=prompt))
        logger.debug("router_injected_system_prompt", language=language)

    return {"language": language, "messages": new_messages}


async def agent_node(state: AgentState) -> dict:
    """Core node that invokes the LLM with bound tools.

    Args:
        state: Current graph state containing message history.

    Returns:
        Partial state update with the LLM response message.
    """
    messages = state["messages"]
    provider_type = settings.LLM_PROVIDER.lower()

    logger.debug("agent_node_invoked", provider=provider_type, message_count=len(messages))

    if provider_type == "mock":
        latest_user_message = next(
            (
                message.content
                for message in reversed(messages)
                if isinstance(message, HumanMessage) and message.content
            ),
            "",
        )
        return {
            "messages": [
                AIMessage(content=f"Mock response to: {latest_user_message or 'your request'}")
            ]
        }

    if provider_type == "ollama":
        model = ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=0,
        ).bind_tools(tools)
    elif provider_type == "moonshot":
        # Moonshot AI (Kimi) - OpenAI-compatible API
        if not settings.MOONSHOT_API_KEY:
            raise ValueError(
                "Moonshot AI API key not configured. Set MOONSHOT_API_KEY in your environment."
            )
        model = ChatOpenAI(
            api_key=SecretStr(settings.MOONSHOT_API_KEY),
            base_url=settings.MOONSHOT_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=0,
        ).bind_tools(tools)
    elif provider_type == "azure_openai":
        auth = AzureCredentialResolver("azure_openai_langchain").resolve(
            explicit_key=settings.AZURE_OPENAI_API_KEY,
            key_vault_secret_name=settings.AZURE_OPENAI_API_KEY_SECRET_NAME,
            token_scope="https://cognitiveservices.azure.com/.default",  # nosec B106
            require_token_credential=False,
        )
        if not auth.api_key and auth.token_provider is None:
            raise ValueError(
                "Azure OpenAI authentication is not configured for LangChain path. "
                "Provide AZURE_OPENAI_API_KEY (or Key Vault secret) or enable managed identity"
            )
        model = AzureChatOpenAI(
            **_build_azure_chat_model_kwargs(
                api_key=auth.api_key,
                token_provider=auth.token_provider,
            )
        ).bind_tools(tools)
    else:
        # Default to OpenAI.
        model = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY or "mock-key",  # type: ignore[arg-type]
            base_url=settings.OPENAI_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=0,
        ).bind_tools(tools)

    response = await model.ainvoke(messages)
    return {"messages": [response]}


# ─── CRITIC NODE ─────────────────────────────────────────────────────────────

# Valid tool names that the agent can call
VALID_TOOL_NAMES = {
    "search_profiles",
    "aggregate_profiles",
    "create_data_artifact",
    "create_segment",
    "get_data_coverage_stats",
    "get_segment_stats",
    "push_to_flexmail",
    "send_email_via_resend",
    "send_bulk_emails_via_resend",
    "push_segment_to_resend",
    "send_campaign_via_resend",
    "export_segment_to_csv",
    "email_segment_export",
    "lookup_nace_code",
    "lookup_juridical_code",
    # Unified 360° View tools
    "query_unified_360",
    "get_industry_summary",
    "find_high_value_accounts",
    "get_geographic_revenue_distribution",
    "get_identity_link_quality",
}

# Destructive operations that require extra validation
DESTRUCTIVE_TOOLS = {
    "delete_profile",  # Future tool
    "mass_update",  # Future tool
    "bulk_delete",  # Future tool
}

# ─── QUERY INTENT ROUTING RULES ──────────────────────────────────────────────
# Deterministic guard: if the user query matches a keyword pattern, the LLM
# MUST call the specified required_tool. Calling a forbidden_tool instead will
# be rejected by the critic with a corrective error message.
#
# Rules are evaluated in order; checking stops at the first keyword match.
# Each rule only fires when ANY keyword substring is found in the user query.
QUERY_ROUTING_RULES: list[dict] = [
    {
        "name": "identity_link_quality",
        "keywords": [
            "linked to kbo",
            "link to kbo",
            "kbo link",
            "source systems linked",
            "link quality",
            "match rate",
            "kbo match",
            "identity link",
            "matching quality",
        ],
        "required_tool": "get_identity_link_quality",
        "forbidden_tools": {"get_data_coverage_stats", "search_profiles", "aggregate_profiles"},
        "error_hint": (
            "Call get_identity_link_quality (no parameters needed). "
            "It returns KBO match rates for Teamleader and Exact."
        ),
    },
    {
        "name": "geographic_revenue_distribution",
        "keywords": [
            "revenue distribution",
            "revenue by city",
            "revenue by location",
            "geographic distribution",
            "geographic revenue",
            "market penetration by city",
            "pipeline by city",
            "revenue spread",
        ],
        "required_tool": "get_geographic_revenue_distribution",
        "forbidden_tools": {"aggregate_profiles", "search_profiles"},
        "error_hint": (
            "Call get_geographic_revenue_distribution (no parameters needed). "
            "It returns cross-source revenue and pipeline aggregated by city."
        ),
    },
    {
        "name": "industry_pipeline",
        "keywords": [
            "pipeline value for",
            "pipeline value by",
            "pipeline for software",
            "pipeline for it",
            "pipeline for restaurant",
            "pipeline for retail",
            "pipeline for construction",
            "industry pipeline",
            "industry revenue",
            "pipeline summary",
            "total pipeline",
        ],
        "required_tool": "get_industry_summary",
        "forbidden_tools": {"search_profiles", "aggregate_profiles"},
        "error_hint": (
            "Call get_industry_summary with industry_category= and optional city=. "
            "It returns pipeline value and revenue aggregated by industry from CRM + Exact."
        ),
    },
]


def _is_valid_nace_code(code: str) -> bool:
    """Validate that a NACE code is a valid 5-digit string."""
    if not isinstance(code, str):
        return False
    return len(code) == 5 and code.isdigit()


def _extract_last_user_query(messages: list) -> str:
    """Return the most recent HumanMessage content as a lowercase string.

    Used by the critic to match routing rules against the user's actual intent
    without involving the LLM.

    Args:
        messages: List of messages from AgentState.

    Returns:
        Lowercase content of the last HumanMessage, or empty string if none found.
    """
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            content = getattr(message, "content", "") or ""
            return content.lower()
    return ""


def _check_routing_rules(tool_name: str, user_query: str) -> tuple[bool, str]:
    """Check whether tool_name violates any QUERY_ROUTING_RULES for user_query.

    Walks each rule; if ANY keyword substring appears in user_query and tool_name
    is in that rule's forbidden_tools, returns (False, error_message).
    If the query matches a rule but the correct tool was chosen, returns (True, "").
    If no rule matches at all, returns (True, "").

    Args:
        tool_name: The tool the LLM wants to call.
        user_query: Lowercase content of the most recent user message.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not user_query:
        return True, ""

    for rule in QUERY_ROUTING_RULES:
        matched_keyword = next(
            (kw for kw in rule["keywords"] if kw in user_query),
            None,
        )
        if matched_keyword is None:
            continue  # rule does not apply to this query

        # This query SHOULD use required_tool.
        if tool_name in rule["forbidden_tools"]:
            return (
                False,
                (
                    f"WRONG TOOL for this query. "
                    f"You called '{tool_name}' but the user query "
                    f"(matched keyword: '{matched_keyword}') requires "
                    f"'{rule['required_tool']}'. "
                    f"{rule['error_hint']}"
                ),
            )
        # Correct or at least not forbidden — stop checking rules.
        break

    return True, ""


def _merge_last_search_params(
    tool_args: dict[str, Any],
    stored_params: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fill missing artifact/search arguments from stored search params."""
    if not stored_params:
        return tool_args

    merged = dict(tool_args)
    for key, value in stored_params.items():
        if value in (None, "", []):
            continue
        current_value = merged.get(key)
        if current_value in (None, "", []):
            merged[key] = value
    return merged


def _validate_tool_call(tool_call: dict, user_query: str = "") -> tuple[bool, str]:
    """Validate a single tool call for security and correctness.

    Args:
        tool_call: Tool call dict with 'name', 'args', etc.
        user_query: Lowercase content of the most recent user message (used for routing checks).

    Returns:
        Tuple of (is_valid, error_message).
    """
    name = tool_call.get("name", "")
    args = tool_call.get("args", {})

    # Check 1: Valid tool name (prevent hallucinated tools)
    if name not in VALID_TOOL_NAMES:
        return False, f"Unknown tool '{name}'. Valid tools: {', '.join(sorted(VALID_TOOL_NAMES))}"

    # Check 2: Destructive operations
    if name in DESTRUCTIVE_TOOLS:
        return False, f"Destructive operation '{name}' is not allowed."

    # Check 3: NACE code validation for search_profiles
    if name in {"search_profiles", "aggregate_profiles", "create_data_artifact"}:
        nace_codes = args.get("nace_codes", [])
        if nace_codes:
            invalid_codes = [c for c in nace_codes if not _is_valid_nace_code(str(c))]
            if invalid_codes:
                return False, f"Invalid NACE codes (must be 5 digits): {invalid_codes}"

        single_nace_code = args.get("nace_code")
        if single_nace_code and not _is_valid_nace_code(str(single_nace_code)):
            return False, f"Invalid nace_code '{single_nace_code}'. Must be 5 digits."

        # Check for potential SQL/TQL injection patterns
        injection_patterns = [
            r"(\bOR\b|\bAND\b).*[=<>]",  # Logical operators with comparisons
            r"--",  # SQL comment
            r"\/\*",  # Block comment start
            r"\bDROP\b",  # DROP statement
            r"\bDELETE\b",  # DELETE statement
            r"\bINSERT\b",  # INSERT statement
            r"\bUPDATE\b",  # UPDATE statement
            r"\bUNION\b",  # UNION injection
            r"\bSELECT\b",  # SELECT injection
            r";",  # Statement terminator
        ]

        # Check string arguments for injection
        for arg_name, arg_value in args.items():
            if isinstance(arg_value, str):
                for pattern in injection_patterns:
                    if re.search(pattern, arg_value, re.IGNORECASE):
                        return (
                            False,
                            f"Potential injection detected in '{arg_name}'. Please use clean values.",
                        )

    # Check 4: Validate aggregate_profiles arguments
    if name in {"aggregate_profiles", "create_data_artifact"}:
        valid_group_by = {
            "city",
            "juridical_form",
            "legal_form",
            "nace_code",
            "industry",
            "status",
            "zip_code",
        }
        group_by = args.get("group_by")
        if group_by and group_by not in valid_group_by:
            return (
                False,
                f"Invalid group_by '{group_by}'. Valid options: {', '.join(sorted(valid_group_by))}",
            )

    if name == "create_data_artifact":
        valid_artifact_types = {"search_results", "aggregation", "coverage_report"}
        artifact_type = args.get("artifact_type")
        if artifact_type and artifact_type not in valid_artifact_types:
            return (
                False,
                f"Invalid artifact_type '{artifact_type}'. Valid options: {', '.join(sorted(valid_artifact_types))}",
            )

        valid_output_formats = {"markdown", "csv", "json"}
        output_format = args.get("output_format")
        if output_format and output_format not in valid_output_formats:
            return (
                False,
                f"Invalid output_format '{output_format}'. Valid options: {', '.join(sorted(valid_output_formats))}",
            )

    # Check 5: Argument type validation
    if name in {"search_profiles", "create_data_artifact"}:
        # Validate boolean fields
        for bool_field in ["has_phone", "has_email"]:
            value = args.get(bool_field)
            if value is not None and not isinstance(value, bool):
                return (
                    False,
                    f"'{bool_field}' must be a boolean (true/false), got {type(value).__name__}",
                )

    if name == "create_data_artifact":
        use_last_search = args.get("use_last_search")
        if use_last_search is not None and not isinstance(use_last_search, bool):
            return (
                False,
                f"'use_last_search' must be a boolean (true/false), got {type(use_last_search).__name__}",
            )

    # Check 6: Routing guard — deterministic keyword-based 360° tool selection
    routing_valid, routing_error = _check_routing_rules(name, user_query)
    if not routing_valid:
        return False, routing_error

    return True, ""


async def critic_node(state: AgentState) -> dict:
    """Validate tool calls before execution.

    The critic acts as a security and quality gate between the agent
    and tool execution. It validates:
    - Tool names are valid (prevent hallucinated tools)
    - No destructive operations
    - NACE codes are valid 5-digit codes
    - No potential injection attempts
    - Arguments are properly typed

    Args:
        state: Current graph state containing messages.

    Returns:
        Partial state update. If validation fails, adds a feedback message
        and clears tool calls. If validation passes, state is unchanged.
    """
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_message = messages[-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    tool_calls = last_message.tool_calls
    logger.debug("critic_validating_tool_calls", count=len(tool_calls))

    # Extract the last user query once for routing checks across all tool calls
    user_query = _extract_last_user_query(list(messages))

    validation_errors = []
    for tool_call in tool_calls:
        is_valid, error = _validate_tool_call(tool_call, user_query=user_query)
        if not is_valid:
            validation_errors.append(f"Tool '{tool_call.get('name', 'unknown')}': {error}")

    if validation_errors:
        # Build feedback message
        error_text = "\n".join(f"- {err}" for err in validation_errors)
        feedback = (
            f"Your tool call failed validation:\n{error_text}\n\n"
            "Please correct these issues and try again. "
            "Remember to use valid tool names and proper argument formats."
        )

        logger.warning("critic_rejected_tool_calls", errors=validation_errors)

        # Return feedback message - this will be seen by the agent
        return {"messages": [AIMessage(content=feedback)]}

    logger.debug("critic_approved_tool_calls")
    return {}  # Validation passed, proceed to tools


# ─── CUSTOM TOOL NODE WITH STATE-AWARE SEARCH/SEGMENT ALIGNMENT ───────────────


async def tools_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """Execute tools with state-aware handling for search/segment flow.

    This custom tool node:
    1. Executes all pending tool calls from the last AI message
    2. For search_profiles: extracts and stores the TQL query in state AND cache
    3. For create_segment: injects stored TQL if use_last_search=True (from state or cache)

    This ensures segment counts match search counts by using the exact same TQL.

    Uses BOTH state (via checkpointer) AND SearchCache (SQLite/in-memory) for redundancy:
    - State is faster for same-turn access
    - Cache persists across separate graph invocations reliably

    Args:
        state: Current graph state containing messages and last_search_tql.
        config: RunnableConfig from LangGraph containing thread_id in configurable.

    Returns:
        Partial state update with tool response messages and updated last_search_tql.
    """
    messages = state.get("messages", [])
    if not messages:
        logger.warning("tools_node_no_messages")
        return {}

    last_message = messages[-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.debug("tools_node_no_tool_calls")
        return {}

    tool_calls = last_message.tool_calls

    # EXTENSIVE DIAGNOSTIC LOGGING
    logger.info("=" * 60)
    logger.info("TOOLS_NODE_DEBUG_START")
    logger.info("tools_node_executing", count=len(tool_calls))

    # Try to get conversation_id from multiple sources
    conversation_id: str | None = None
    config_source = "none"

    # Source 1: RunnableConfig from LangGraph (preferred)
    if config:
        logger.info("tools_node_config_received", config_type=type(config).__name__)
        # RunnableConfig is a dict-like object with 'configurable' key
        configurable = (
            config.get("configurable", {})
            if hasattr(config, "get")
            else getattr(config, "configurable", {})
        )
        conversation_id = configurable.get("thread_id") if isinstance(configurable, dict) else None
        if conversation_id:
            config_source = "config.configurable.thread_id"
        logger.info(
            "tools_node_config_parsed",
            configurable_type=type(configurable).__name__,
            has_thread_id=bool(conversation_id),
        )

    # Source 2: Try to get from state metadata if available
    if not conversation_id:
        conversation_id = state.get("thread_id") or state.get("conversation_id")  # type: ignore[assignment]
        if conversation_id:
            config_source = "state"

    logger.info(
        "tools_node_conversation_id",
        conversation_id=conversation_id,
        config_source=config_source,
        config_type=type(config).__name__ if config else None,
    )

    # Get stored TQL from state (persists across conversation turns via checkpointer)
    stored_tql = state.get("last_search_tql")
    stored_params = state.get("last_search_params")

    logger.info(
        "tools_node_state_tql",
        has_state_tql=stored_tql is not None,
        state_tql_preview=stored_tql[:50] if stored_tql else None,
    )

    # Also try to get from cache as fallback
    cached_search = None
    if conversation_id:
        logger.info("tools_node_attempting_cache_fetch", conversation_id=conversation_id)
        try:
            cached_search = await search_cache.get_last_search(str(conversation_id))
            logger.info("tools_node_cache_fetch_result", found_in_cache=cached_search is not None)
            if cached_search:
                if not stored_tql:
                    stored_tql = cached_search["tql"]
                    stored_params = cached_search.get("params")
                    logger.info(
                        "tools_node_using_cached_tql",
                        conversation_id=conversation_id,
                        tql_preview=stored_tql[:50] if stored_tql else None,
                    )
                else:
                    logger.info("tools_node_has_both_state_and_cache", using="state")
        except Exception as cache_exc:
            logger.error(
                "tools_node_cache_fetch_failed",
                error=str(cache_exc),
                error_type=type(cache_exc).__name__,
            )
    else:
        logger.warning(
            "tools_node_no_conversation_id",
            message="Cannot use cache without conversation_id - TQL will not persist across turns!",
        )

    if stored_tql:
        logger.info(
            "tools_node_final_tql_status",
            has_tql=True,
            source="cache" if cached_search and not state.get("last_search_tql") else "state",
        )
    else:
        logger.error(
            "tools_node_final_tql_status",
            has_tql=False,
            message="CRITICAL: No TQL available for segment creation - segment will have 0 profiles!",
        )

    logger.info("TOOLS_NODE_DEBUG_END")
    logger.info("=" * 60)

    tool_messages = []
    new_last_search_tql = stored_tql
    new_last_search_params = stored_params

    for tool_call in tool_calls:
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})
        tool_call_id = tool_call.get("id", "")

        try:
            # Special handling for create_segment to inject stored TQL
            if tool_name == "create_segment":
                use_last_search = tool_args.get("use_last_search", True)
                logger.info(
                    "create_segment_processing",
                    name=tool_args.get("name"),
                    use_last_search=use_last_search,
                    has_stored_tql=stored_tql is not None,
                    conversation_id=conversation_id,
                )
                if use_last_search and stored_tql:
                    logger.info(
                        "create_segment_injecting_stored_tql",
                        name=tool_args.get("name"),
                        stored_tql=stored_tql[:100],
                        source="cache" if cached_search else "state",
                        conversation_id=conversation_id,
                    )
                    # Inject the stored TQL as the condition
                    tool_args = {**tool_args, "condition": stored_tql}
                if use_last_search and stored_params:
                    tool_args = _merge_last_search_params(tool_args, stored_params)
                    logger.info(
                        "create_segment_injected_last_search_params",
                        name=tool_args.get("name"),
                        applied_keys=sorted(stored_params.keys()),
                        conversation_id=conversation_id,
                    )
                elif use_last_search and not stored_params:
                    logger.warning(
                        "create_segment_missing_last_search_params",
                        name=tool_args.get("name"),
                        conversation_id=conversation_id,
                    )
                if use_last_search and not stored_tql:
                    logger.error(
                        "create_segment_no_stored_tql",
                        name=tool_args.get("name"),
                        conversation_id=conversation_id,
                        state_has_tql=state.get("last_search_tql") is not None,
                        config_received=config is not None,
                        message="CRITICAL: Segment will have 0 profiles - no TQL available",
                    )
            elif tool_name == "create_data_artifact":
                use_last_search = tool_args.get("use_last_search", False)
                logger.info(
                    "create_data_artifact_processing",
                    title=tool_args.get("title"),
                    use_last_search=use_last_search,
                    has_stored_params=stored_params is not None,
                    conversation_id=conversation_id,
                )
                if use_last_search and stored_params:
                    tool_args = _merge_last_search_params(tool_args, stored_params)
                    logger.info(
                        "create_data_artifact_injected_last_search_params",
                        title=tool_args.get("title"),
                        applied_keys=sorted(stored_params.keys()),
                        conversation_id=conversation_id,
                    )
                elif use_last_search and not stored_params:
                    logger.warning(
                        "create_data_artifact_missing_last_search_params",
                        title=tool_args.get("title"),
                        conversation_id=conversation_id,
                    )

            # Execute the tool directly (ToolExecutor removed in LangGraph 1.x)
            tool_func = tools_by_name.get(tool_name)
            if not tool_func:
                raise ValueError(f"Unknown tool: {tool_name}")
            result = await tool_func.ainvoke(tool_args)

            # For search_profiles, extract TQL from result for state AND cache storage
            if tool_name == "search_profiles":
                try:
                    result_data = json.loads(result) if isinstance(result, str) else result
                    if isinstance(result_data, dict) and result_data.get("status") == "ok":
                        query_info = result_data.get("query", {})
                        extracted_tql = query_info.get("tql")
                        if extracted_tql:
                            new_last_search_tql = extracted_tql
                            new_last_search_params = result_data.get("applied_filters", {})
                            logger.info(
                                "search_profiles_stored_tql_in_state",
                                tql=extracted_tql[:100],
                                total_count=result_data.get("counts", {}).get(
                                    "authoritative_total"
                                ),
                            )
                            # Also store in cache for redundancy
                            if conversation_id:
                                try:
                                    logger.info(
                                        "search_profiles_attempting_cache_store",
                                        conversation_id=conversation_id,
                                        tql_preview=extracted_tql[:50],
                                    )
                                    await search_cache.store_search(
                                        conversation_id=str(conversation_id),
                                        tql=extracted_tql,
                                        params=new_last_search_params,
                                    )
                                    logger.info(
                                        "search_profiles_stored_tql_in_cache",
                                        conversation_id=conversation_id,
                                        tql_preview=extracted_tql[:50],
                                    )
                                except Exception as cache_exc:
                                    logger.error(
                                        "search_profiles_cache_store_failed",
                                        error=str(cache_exc),
                                        error_type=type(cache_exc).__name__,
                                    )
                            else:
                                logger.warning(
                                    "search_profiles_no_conversation_id",
                                    message="Cannot store in cache without conversation_id",
                                )
                except Exception as parse_exc:
                    logger.warning("failed_to_extract_tql_from_search", error=str(parse_exc))

            tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call_id))

        except Exception as exc:
            logger.error("tool_execution_failed", tool=tool_name, error=str(exc))
            tool_messages.append(
                ToolMessage(
                    content=json.dumps(
                        {
                            "status": "error",
                            "tool": tool_name,
                            "error": str(exc),
                        }
                    ),
                    tool_call_id=tool_call_id,
                )
            )

    result_update: dict[str, Any] = {"messages": tool_messages}

    # Update state if we have new TQL
    if new_last_search_tql != state.get("last_search_tql"):
        result_update["last_search_tql"] = new_last_search_tql
    if new_last_search_params != state.get("last_search_params"):
        result_update["last_search_params"] = new_last_search_params

    return result_update
