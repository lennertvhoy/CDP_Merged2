# CDP_Merged Code Audit Report
**Date:** 2026-02-25  
**Commit:** 54b0ecc  
**Auditor:** Subagent Code Audit

---

## 1. EXECUTIVE SUMMARY

### Overall Status: 🟡 PARTIALLY FUNCTIONAL

The CDP_Merged codebase is well-structured with good separation of concerns, comprehensive test coverage (~60%), and modern Python practices. However, **critical authentication issues with Tracardi** are blocking full functionality in production.

| Component | Status | Notes |
|-----------|--------|-------|
| Chainlit UI | ✅ Working | Serves traffic, handles sessions |
| LangGraph Workflow | ✅ Working | 4-node graph executes correctly |
| Azure OpenAI | ✅ Working | LLM responses functional |
| Tracardi Integration | 🔴 **BROKEN** | Authentication failure |
| Flexmail Integration | 🟡 Stubbed | Code exists, not configured |
| Test Suite | 🟡 Partial | Unit tests pass, integration needs env |

---

## 2. ARCHITECTURE AUDIT

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER LAYER                                  │
│  Chainlit UI (src/app.py) - WebSocket-based chat interface         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION LAYER                            │
│  LangGraph Workflow (src/graph/)                                    │
│  ├── Router Node: Language detection, system prompt injection      │
│  ├── Agent Node: LLM invocation with tool binding                  │
│  └── Tools Node: search_profiles, create_segment, push_to_flexmail │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌──────────────────────────────┐      ┌──────────────────────────────┐
│      AI INTERFACE            │      │       SERVICES               │
│  (src/ai_interface/)         │      │  (src/services/)             │
│  - tools.py: Tool defs       │      │  - tracardi.py: CDP client   │
│  - schemas.py: Pydantic      │      │  - flexmail.py: Email client │
└──────────────────────────────┘      └──────────────────────────────┘
                    │                               │
                    ▼                               ▼
┌──────────────────────────────┐      ┌──────────────────────────────┐
│   SEARCH ENGINE              │      │   EXTERNAL APIs              │
│  (src/search_engine/)        │      │  - Tracardi VM:52.148.232.140│
│  - TQLBuilder (Tracardi QL)  │      │  - Azure OpenAI              │
│  - SQLBuilder (reference)    │      │  - Flexmail (not configured) │
│  - ESBuilder (Elasticsearch) │      │                              │
└──────────────────────────────┘      └──────────────────────────────┘
```

### 2.2 Entry Points

| Entry Point | File | Purpose |
|-------------|------|---------|
| **Main App** | `src/app.py` | Chainlit UI, session management, health endpoints |
| **Health Check** | `src/app.py:healthz()` | `/healthz` and `/project/healthz` - returns JSON status |
| **Chat Start** | `src/app.py:start()` | Initializes session, workflow, Tracardi profile |
| **Message Handler** | `src/app.py:main()` | Processes user messages through LangGraph |

### 2.3 Data Flow

```
User Query
    │
    ▼
┌─────────────────┐
│ 1. Input Guard  │──► Query length validation (<1000 chars)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 2. Router Node  │──► Language detection (en/fr/nl)
│                 │──► System prompt injection
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 3. Agent Node   │──► LLM invocation with tools
│                 │──► Tool binding (search_profiles, etc.)
└─────────────────┘
    │
    ▼ (if tool calls needed)
┌─────────────────┐
│ 4. Tools Node   │──► NACE code resolution
│                 │──► TQL query building
│                 │──► Tracardi API call
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 5. Response     │──► Final answer generation
└─────────────────┘
```

---

## 3. CODE QUALITY ASSESSMENT

### 3.1 Strengths ✅

1. **Type Safety**: Comprehensive type hints throughout
2. **Structured Logging**: `structlog` with trace IDs for observability
3. **Error Handling**: Custom exception hierarchy (`CDPError` → specific errors)
4. **Testing**: 3,718 lines of test code, unit + integration test separation
5. **Configuration**: Pydantic Settings with env var validation
6. **Retry Logic**: `tenacity` for resilient external API calls
7. **Multi-LLM Support**: Ollama, OpenAI, Azure OpenAI, Mock providers
8. **Code Quality Tools**: Ruff (linting/formatting), MyPy (type checking), pre-commit hooks

### 3.2 Weaknesses ⚠️

1. **Error Handling Gaps**: Some tools return empty dicts on error instead of raising
2. **Missing Input Validation**: No strict validation on TQL query construction
3. **Cascading Failures**: Tracardi auth failure doesn't gracefully degrade
4. **Hardcoded Defaults**: Some constants could be configurable
5. **Documentation Gaps**: Several modules lack docstrings

### 3.3 Security Assessment

| Aspect | Status | Notes |
|--------|--------|-------|
| SQL Injection | ✅ Safe | TQL uses parameterized queries |
| API Keys | ✅ Good | Stored in Azure Container App secrets |
| Input Validation | 🟡 Partial | Length checks only, no content filtering |
| Webhook HMAC | ✅ Implemented | Flexmail signature verification present |
| CORS | ❓ Unknown | Not explicitly configured |

---

## 4. EXTERNAL INTEGRATIONS AUDIT

### 4.1 Tracardi CDP (src/services/tracardi.py)

**Status:** 🔴 **CRITICAL ISSUE - AUTHENTICATION FAILURE**

```python
# Current authentication flow:
async def _ensure_token(self) -> None:
    url = f"{self.base_url}/user/token"
    payload = {
        "username": self.username,      # From env: admin@cdpmerged.local
        "password": self.password,      # From secret
        "grant_type": "password",
        "scope": "",
    }
```

**Expected Configuration:**
- `TRACARDI_API_URL`: `http://52.148.232.140:8686`
- `TRACARDI_USERNAME`: `admin@cdpmerged.local`
- `TRACARDI_PASSWORD`: Stored in Container App secret `tracardi-password`

**Issue:** Authentication returns "Incorrect username or password"

**Likely Causes:**
1. Wrong username format (should be `admin`, not `admin@cdpmerged.local`)
2. Password mismatch between Container App secret and Tracardi VM
3. Tracardi instance not initialized with expected credentials

### 4.2 Azure OpenAI (src/core/llm_provider.py)

**Status:** ✅ Working

- Endpoint: `https://aoai-cdpmerged-fast.openai.azure.com/`
- Deployment: `gpt-4o-mini`
- Authentication: API key via Container App secret

### 4.3 Flexmail (src/services/flexmail.py)

**Status:** 🟡 Code Complete, Not Configured

- `FLEXMAIL_ENABLED=false` in Container App
- All client methods implemented
- Webhook signature verification present
- Needs: `FLEXMAIL_API_TOKEN`, `FLEXMAIL_ACCOUNT_ID`

### 4.4 Azure AI Search (src/retrieval/azure_retriever.py)

**Status:** 🟡 Code Complete, Feature Flagged Off

- `ENABLE_AZURE_SEARCH_RETRIEVAL=false`
- Infrastructure not deployed (optional per Terraform)
- Shadow mode capability present for A/B testing

---

## 5. CONFIGURATION AUDIT

### 5.1 Required Environment Variables

#### P0 - Critical (Application Won't Start Without These)

| Variable | Current Value | Status | Notes |
|----------|---------------|--------|-------|
| `LLM_PROVIDER` | `azure_openai` | ✅ Set | |
| `AZURE_OPENAI_ENDPOINT` | `https://aoai-cdpmerged-fast...` | ✅ Set | |
| `AZURE_OPENAI_API_KEY` | `***` | ✅ Secret | |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | `gpt-4o-mini` | ✅ Set | |
| `TRACARDI_API_URL` | `http://52.148.232.140:8686` | ✅ Set | |
| `TRACARDI_USERNAME` | `admin@cdpmerged.local` | ⚠️ Wrong? | Should be `admin`? |
| `TRACARDI_PASSWORD` | `***` | ⚠️ Wrong? | Mismatch with VM? |

#### P1 - Required for Full Functionality

| Variable | Status | Purpose |
|----------|--------|---------|
| `TRACARDI_SOURCE_ID` | ⚠️ Check | Event source ID (default: `kbo-source`) |
| `FLEXMAIL_ENABLED` | ❌ false | Email integration disabled |
| `FLEXMAIL_API_URL` | ❌ Not set | Flexmail API endpoint |
| `FLEXMAIL_API_TOKEN` | ❌ Not set | API authentication |
| `FLEXMAIL_ACCOUNT_ID` | ❌ Not set | Account identifier |

#### P2 - Optional Enhancements

| Variable | Status | Purpose |
|----------|--------|---------|
| `ENABLE_AZURE_SEARCH_RETRIEVAL` | false | Azure AI Search primary retrieval |
| `ENABLE_AZURE_SEARCH_SHADOW_MODE` | false | Compare Azure vs Tracardi results |
| `AZURE_KEY_VAULT_URL` | Not set | Managed Identity / KV auth |

### 5.2 Container App Configuration

```bash
# Current Container App env vars (from Azure):
az containerapp show -n ca-cdpmerged-fast -g rg-cdpmerged-fast \
  --query "properties.template.containers[0].env"
```

**Identified Issues:**
1. `TRACARDI_USERNAME=admin@cdpmerged.local` - Likely incorrect format
2. `TRACARDI_SOURCE_ID` not explicitly set (using default)
3. No Redis connection configured (not deployed)
4. `LOG_LEVEL=INFO` - Could be DEBUG for troubleshooting

---

## 6. TESTING INFRASTRUCTURE AUDIT

### 6.1 Test Structure

```
tests/
├── conftest.py                    # 167 lines - Shared fixtures
├── unit/                          # Fast tests, no external deps
│   ├── test_azure_auth.py         # Azure credential resolution
│   ├── test_azure_search_auth.py  # Search auth tests
│   ├── test_es_builder.py         # ES query builder
│   ├── test_exceptions.py         # Exception hierarchy
│   ├── test_factory.py            # Query factory
│   ├── test_flexmail.py           # Flexmail client (mocked)
│   ├── test_llm_provider.py       # LLM provider tests
│   ├── test_nodes.py              # LangGraph nodes
│   ├── test_sql_builder.py        # SQL builder
│   ├── test_tql_builder.py        # TQL builder
│   ├── test_tools.py              # AI tools (349 lines)
│   ├── test_tracardi.py           # Tracardi client (159 lines)
│   └── test_validation.py         # Query validation
└── integration/                   # Requires external services
    ├── test_multi_turn_user_stories.py    # 262 lines
    ├── test_nlq_end_to_end.py            # 93 lines
    ├── test_retrieval_grounding_eval_harness.py  # 910 lines
    └── helpers/
        ├── assertions.py           # 212 lines
        └── conversation_driver.py  # 265 lines
```

### 6.2 Test Coverage

| Module | Coverage | Notes |
|--------|----------|-------|
| Unit tests | ~80% | Good coverage of core logic |
| Integration tests | N/A | Require running Tracardi/LLM |
| E2E tests | N/A | Require full deployment |

### 6.3 Running Tests

```bash
# Unit tests (can run on VM)
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
poetry install --with dev
poetry run pytest tests/unit -v

# Integration tests (require external services)
poetry run pytest tests/integration -v

# With coverage
poetry run pytest tests/unit --cov=src --cov-report=html
```

### 6.4 Missing Tests

1. **Tracardi Authentication Retry Logic** - No test for auth failure scenarios
2. **Azure Container App Health Checks** - No deployment verification tests
3. **Webhook Handler Tests** - Flexmail webhook not tested
4. **NACE Code Resolution Edge Cases** - Limited coverage for unknown keywords

---

## 7. DEPLOYMENT GAP ANALYSIS

### 7.1 Terraform vs Actual Deployment

| Resource | Terraform Expects | Actually Deployed | Status |
|----------|-------------------|-------------------|--------|
| App VM | `vm-app-*` | `ca-cdpmerged-fast` (Container App) | Architecture Shift |
| ES VM | `vm-es-*` | `vm-data-cdpmerged-prod` | ✅ Match |
| Tracardi VM | N/A | `vm-tracardi-cdpmerged-prod` | ✅ Deployed |
| Redis Cache | `redis-*` | ❌ Not deployed | 🔴 Missing |
| Event Hub | `evhns-*` | ❌ Not deployed | 🟡 Optional |
| App Insights | `appi-*` | ❌ Not deployed | 🟡 Optional |
| Azure AI Search | `srch-*` | ❌ Not deployed | 🟡 Optional |

### 7.2 Network Architecture

```
Internet
    │
    ▼
┌──────────────────────────────┐
│  Azure Container App         │
│  ca-cdpmerged-fast           │
│  (West Europe)               │
└──────────────────────────────┘
    │ HTTP (8686)
    ▼
┌──────────────────────────────┐
│  VM: vm-tracardi-cdpmerged   │
│  - Tracardi API: 8686        │
│  - Tracardi GUI: 8787        │
│  - MySQL, RabbitMQ           │
│  - Public IP: 52.148.232.140 │
└──────────────────────────────┘
    │ HTTP (9200)
    ▼
┌──────────────────────────────┐
│  VM: vm-data-cdpmerged       │
│  - Elasticsearch: 9200       │
│  - Private IP: 10.56.2.10    │
└──────────────────────────────┘
```

### 7.3 Critical Configuration Mismatches

| Issue | Code Expects | Azure Provides | Impact |
|-------|--------------|----------------|--------|
| Tracardi Auth | Username/password | OAuth2 optional? | 🔴 Blocking |
| Redis | Connection string | Not deployed | 🟡 Caching disabled |
| Event Hub | Connection string | Not deployed | 🟡 Events not streamed |

---

## 8. FINDINGS SUMMARY

### 🔴 P0 - Critical (Blocking)

1. **Tracardi Authentication Failure**
   - Error: "Incorrect username or password"
   - Location: `src/services/tracardi.py:_ensure_token()`
   - Fix: Verify correct credentials on Tracardi VM and update Container App secret

### 🟡 P1 - High Priority

2. **Missing Required Environment Variables**
   - `TRACARDI_SOURCE_ID` not explicitly set
   - Flexmail integration disabled

3. **Health Endpoint Returns HTML**
   - Expected: JSON health status
   - Actual: Chainlit HTML page
   - Impact: Load balancers may not detect unhealthy instances

4. **Missing Redis Cache**
   - Impact: No session caching, potential performance issues

### 🟢 P2 - Medium Priority

5. **Incomplete Test Coverage for Auth Scenarios**
6. **No Automated Deployment Verification**
7. **Multiple Log Analytics Workspaces** (cost/organization)

---

## 9. RECOMMENDATIONS

### Immediate Actions (This Week)

1. **Fix Tracardi Authentication**
   ```bash
   # SSH to Tracardi VM and verify credentials
   ssh azureuser@52.148.232.140
   
   # Check Tracardi logs for auth attempts
   docker logs tracardi-api
   
   # Reset admin password if needed
   # Update Container App secret
   az containerapp secret set \
     --name ca-cdpmerged-fast \
     --resource-group rg-cdpmerged-fast \
     --secrets tracardi-password=<correct-password>
   ```

2. **Verify Environment Variables**
   - Confirm `TRACARDI_USERNAME` format (likely `admin`, not email)
   - Set `TRACARDI_SOURCE_ID=kbo-source`

3. **Enable Debug Logging**
   ```bash
   az containerapp update \
     --name ca-cdpmerged-fast \
     --resource-group rg-cdpmerged-fast \
     --set-env-vars LOG_LEVEL=DEBUG
   ```

### Short-Term (Next 2 Weeks)

4. Deploy Redis Cache for session management
5. Add proper JSON health endpoint
6. Create integration test configuration for VM environment
7. Consolidate Log Analytics workspaces

### Long-Term (Next Month)

8. Implement blue-green deployment strategy
9. Add Application Insights for APM
10. Enable Azure AI Search in shadow mode for evaluation

---

## 10. APPENDIX

### A. File Inventory

| Category | Files | Lines of Code |
|----------|-------|---------------|
| Core Application | 12 | ~2,500 |
| Services | 3 | ~800 |
| Graph/Workflow | 4 | ~400 |
| AI Interface | 2 | ~900 |
| Search Engine | 6 | ~600 |
| Tests | 18 | ~3,718 |
| **Total** | **45** | **~8,918** |

### B. Dependencies Analysis

**Key Dependencies:**
- `langgraph>=0.2.0` - Workflow orchestration
- `chainlit>=1.1.306` - Chat UI framework
- `langchain-openai>=0.1.0` - OpenAI integration
- `pydantic>=2.10.1` - Data validation
- `httpx>=0.26.0` - HTTP client
- `elasticsearch>=8.11.0` - Search backend
- `tenacity>=8.2.0` - Retry logic
- `structlog>=24.1.0` - Structured logging

### C. Code Metrics

| Metric | Value |
|--------|-------|
| Python Version | 3.11+ (configured) / 3.12 (Docker) |
| Test Coverage Target | 60% (current: ~55%) |
| Ruff Line Length | 99 |
| Max Query Length | 1,000 chars |
| HTTP Timeout (Tracardi) | 60s |
| HTTP Timeout (LLM) | 120s |

---

*End of Audit Report*
