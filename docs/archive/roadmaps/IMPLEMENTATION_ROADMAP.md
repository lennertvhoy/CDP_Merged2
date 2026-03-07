# IMPLEMENTATION ROADMAP — CDP_Merged

Prioritized development queue to resolve deployment blockers and achieve production readiness.

---

## 📊 PRIORITY LEGEND

| Priority | Color | Description | SLA |
|----------|-------|-------------|-----|
| P0 | 🔴 | Critical - Blocking production use | Fix within 24-48 hours |
| P1 | 🟡 | High - Required for production readiness | Complete within 1-2 weeks |
| P2 | 🟢 | Medium - Important enhancements | Complete within 1 month |
| P3 | 🔵 | Low - Nice to have | Future sprints |

---

## 🔴 P0 — CRITICAL (Blocking Functionality)

### ✅ P0.1 Fix Tracardi Authentication [4-8 hours] - COMPLETED 2026-03-01

**Status:** ✅ COMPLETE  
**Deployed:** Tracardi at 137.117.212.154  
**Initialized:** Tracardi GUI with admin credentials  
**Fixed:** Container App auth alignment

**Verified Credentials:**
- **Email:** `admin@cdpmerged.local`
- **Password:** `<redacted>` (from terraform output)
- **Installation Token:** `<redacted>`

**Problem:** Authentication failing with "Incorrect username or password"

**Tasks:**
1. SSH to Tracardi VM and verify actual admin credentials
2. Check if username should be `admin` vs `admin@cdpmerged.local`
3. Reset Tracardi admin password if needed
4. Update Container App secret with correct credentials
5. Verify connection and auth flow

**Verification:**
```bash
# Should return valid token
curl -X POST http://52.148.232.140:8686/user/token \
  -d "username=admin&password=correctpass&grant_type=password"
```

**Acceptance Criteria:**
- [ ] Container App can authenticate to Tracardi
- [ ] Profile search returns results
- [ ] No `tracardi_auth_failed` errors in logs

---

### P0.2 Verify Required Environment Variables [2 hours]

**Problem:** Missing or incorrect env vars may cause silent failures

**Tasks:**
1. Audit all required vs configured environment variables
2. Set `TRACARDI_SOURCE_ID=kbo-source` explicitly
3. Verify `TRACARDI_USERNAME` format
4. Document all configured values (redact secrets)

**Verification:**
```bash
az containerapp show -n ca-cdpmerged-fast -g rg-cdpmerged-fast \
  --query "properties.template.containers[0].env"
```

---

### P0.3 Fix Health Endpoint Response Format [2 hours]

**Problem:** Health endpoints return Chainlit HTML instead of JSON

**Tasks:**
1. Verify `/healthz` returns JSON with `status`, `service`, `llm_provider`
2. If returning HTML, debug Chainlit routing
3. Consider adding dedicated health check route before Chainlit init

**Current Code:** (in `src/app.py`)
```python
@chainlit_server_app.get("/project/healthz")
@chainlit_server_app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "cdp-merged", "llm_provider": settings.LLM_PROVIDER}
```

**Acceptance Criteria:**
- [ ] `curl /healthz` returns valid JSON
- [ ] `curl /project/healthz` returns valid JSON
- [ ] Response includes `status`, `service`, `llm_provider`

---

## 🟡 P1 — PRODUCTION READY

### P1.1 Deploy Redis Cache [4 hours]

**Problem:** No session persistence across Container App restarts

**Tasks:**
1. Deploy Azure Cache for Redis (Basic tier sufficient)
2. Configure connection string in Container App
3. Update code to use Redis for session storage if needed
4. Document Redis usage

**Azure CLI:**
```bash
az redis create \
  --name redis-cdpmerged \
  --resource-group rg-cdpmerged-fast \
  --location westeurope \
  --sku Basic \
  --vm-size C0

# Get connection string
az redis list-keys -n redis-cdpmerged -g rg-cdpmerged-fast
```

---

### P1.2 Add Tracardi Auth Retry Tests [4 hours]

**Problem:** No test coverage for auth failure scenarios

**Tasks:**
1. Create test for auth failure handling
2. Create test for retry logic with backoff
3. Create test for graceful degradation when Tracardi unavailable

**File:** `tests/unit/test_tracardi_auth.py`

---

### P1.3 Implement Deployment Verification Tests [6 hours]

**Problem:** No automated post-deployment validation

**Tasks:**
1. Create `tests/integration/test_deployment.py`
2. Test health endpoints
3. Test LLM connectivity
4. Test Tracardi connectivity
5. Test end-to-end query flow

**Example Test:**
```python
async def test_deployment_health():
    """Verify all components are accessible."""
    # Health endpoint responds
    # Tracardi auth works
    # LLM responds
    # End-to-end query succeeds
```

---

### P1.4 Add Application Insights [4 hours]

**Problem:** No application performance monitoring

**Tasks:**
1. Deploy Application Insights resource
2. Add instrumentation to code
3. Configure distributed tracing
4. Set up alerts for error rates

**Azure CLI:**
```bash
az monitor app-insights component create \
  --app appi-cdpmerged \
  --resource-group rg-cdpmerged-fast \
  --location westeurope \
  --application-type web
```

---

### P1.5 Improve Error Handling in Tools [6 hours]

**Problem:** Some tools return empty dicts instead of raising proper exceptions

**Tasks:**
1. Audit all tool functions for error handling gaps
2. Ensure consistent error responses
3. Add structured error payloads for UI consumption
4. Log all errors with context

**Files:**
- `src/ai_interface/tools.py`
- `src/services/tracardi.py`
- `src/services/flexmail.py`

---

### P1.6 Create Missing Test Coverage [8 hours]

**Problem:** Several critical paths lack test coverage

**Tasks:**
1. Add tests for webhook handlers
2. Add tests for NACE code resolution edge cases
3. Add tests for Azure auth fallback scenarios
4. Add tests for Flexmail client error paths

**Target Coverage:** >80%

---

### P1.7 Consolidate Log Analytics Workspaces [2 hours]

**Problem:** 3 Log Analytics workspaces exist (confusion/cost)

**Tasks:**
1. Identify which workspace is actively used
2. Migrate any important data
3. Delete unused workspaces
4. Document the correct workspace

---

### P1.8 Document Local Dev Environment for VM [4 hours]

**Problem:** Developers need clear guidance for VM-based development

**Tasks:**
1. Create VM-specific setup guide
2. Document Poetry/pip installation
3. Document how to run tests on VM
4. Document Azure CLI authentication setup

**Output:** Update `docs/development.md`

---

## 🟢 P2 — ENHANCEMENTS

### P2.1 Enable Azure AI Search Shadow Mode [8 hours]

**Problem:** Cannot evaluate Azure Search vs Tracardi retrieval quality

**Tasks:**
1. Deploy Azure AI Search if not already present
2. Enable `ENABLE_AZURE_SEARCH_SHADOW_MODE=true`
3. Run parallel queries
4. Log comparison metrics
5. Analyze results

---

### P2.2 Implement Webhook Handler for Flexmail [6 hours]

**Problem:** Flexmail webhooks not processed

**Tasks:**
1. Create webhook endpoint in Chainlit
2. Implement signature verification
3. Process engagement events
4. Update Tracardi profiles

**File:** New `src/api/webhooks.py`

---

### P2.3 Add Rate Limiting [6 hours]

**Problem:** No protection against abuse

**Tasks:**
1. Implement request rate limiting
2. Add per-user limits
3. Add global limits
4. Return appropriate 429 responses

**Library:** `slowapi` or custom middleware

---

### P2.4 Add Metrics Endpoint [4 hours]

**Problem:** Prometheus metrics configured but not easily accessible

**Tasks:**
1. Ensure metrics endpoint is exposed
2. Document available metrics
3. Create sample dashboards
4. Set up alerts

---

### P2.5 Implement Blue-Green Deployment [8 hours]

**Problem:** No zero-downtime deployment strategy

**Tasks:**
1. Use Container App revision management
2. Implement traffic splitting
3. Create deployment scripts
4. Document rollback procedures

---

### P2.6 Add Additional LLM Providers [8 hours]

**Problem:** Limited to OpenAI/Azure/Ollama

**Tasks:**
1. Add Anthropic Claude provider
2. Add Google Gemini provider
3. Add local model support (llama.cpp)
4. Document provider selection criteria

---

### P2.7 Optimize Query Performance [8 hours]

**Problem:** No query optimization or caching

**Tasks:**
1. Add query result caching
2. Implement query plan analysis
3. Add query timeout handling
4. Optimize NACE code lookup

---

### P2.8 Implement Automated Backups [4 hours]

**Problem:** No automated backup strategy for Tracardi data

**Tasks:**
1. Configure ES snapshot schedule
2. Automate backup to blob storage
3. Document restore procedures
4. Test restore process

---

## 🔵 P3 — FUTURE ENHANCEMENTS

### P3.1 Multi-Region Deployment

- Deploy secondary instance in another region
- Implement geo-routing
- Set up cross-region replication

### P3.2 Advanced Analytics Dashboard

- Real-time query analytics
- User behavior tracking
- Performance metrics visualization

### P3.3 Natural Language Improvements

- Intent classification model
- Better entity extraction
- Multi-turn conversation improvements

### P3.4 Custom Model Fine-Tuning

- Fine-tune model on domain-specific data
- Improve NACE code resolution accuracy
- Better legal form classification

---

## 📅 RECOMMENDED TIMELINE

### Week 1 (Days 1-7)
- [ ] **P0.1** Fix Tracardi Authentication
- [ ] **P0.2** Verify Environment Variables
- [ ] **P0.3** Fix Health Endpoint
- [ ] **P1.1** Deploy Redis Cache
- [ ] **P1.7** Consolidate Log Analytics

### Week 2 (Days 8-14)
- [ ] **P1.2** Tracardi Auth Tests
- [ ] **P1.3** Deployment Verification Tests
- [ ] **P1.4** Application Insights
- [ ] **P1.8** VM Dev Documentation

### Week 3 (Days 15-21)
- [ ] **P1.5** Error Handling Improvements
- [ ] **P1.6** Missing Test Coverage
- [ ] **P2.1** Azure Search Shadow Mode

### Week 4 (Days 22-28)
- [ ] **P2.2** Flexmail Webhook Handler
- [ ] **P2.3** Rate Limiting
- [ ] **P2.5** Blue-Green Deployment

---

## 📈 SUCCESS METRICS

| Metric | Current | Target | Priority |
|--------|---------|--------|----------|
| Tracardi Auth Success Rate | 0% | 100% | P0 |
| Health Endpoint JSON | ❌ HTML | ✅ JSON | P0 |
| Test Coverage | ~55% | >80% | P1 |
| Session Persistence | ❌ None | ✅ Redis | P1 |
| Error Rate | Unknown | <1% | P1 |
| Response Time (p95) | Unknown | <2s | P1 |
| Deploy Frequency | Manual | Daily | P2 |

---

## 🎯 DEFINITION OF DONE

### P0 Complete When:
- [ ] Tracardi authentication succeeds consistently
- [ ] All required environment variables are documented and set
- [ ] Health endpoints return proper JSON
- [ ] No critical errors in production logs

### P1 Complete When:
- [ ] Redis deployed and operational
- [ ] Test coverage >80%
- [ ] Application Insights collecting data
- [ ] Deployment verification tests automated
- [ ] Error handling consistent across all modules

### P2 Complete When:
- [ ] Azure Search shadow mode running
- [ ] Flexmail webhooks processed
- [ ] Rate limiting active
- [ ] Blue-green deployment working

---

## 💰 COST ESTIMATES

| Task | Azure Resources | Est. Monthly Cost |
|------|-----------------|-------------------|
| P1.1 Redis Cache | Azure Cache for Redis (Basic C0) | ~€15 |
| P1.4 App Insights | Application Insights | ~€10 |
| P2.1 Azure Search | Azure AI Search (Basic) | ~€50 |
| **Total P1** | | **~€25** |
| **Total P2** | | **~€75** |

---

## 📝 NOTES

### Technical Debt
- Terraform defines VMs but deployment uses Container Apps (architecture drift)
- Some hardcoded values should be configurable
- Error messages need standardization

### Dependencies
- P0.1 blocks most P1 tasks (need working Tracardi)
- P1.1 blocks P2.1 (Redis recommended for Search shadow mode)
- P1.4 recommended before P2 (better observability)

### Risk Mitigation
- All P0 changes tested in non-production first
- P2 changes behind feature flags
- Rollback procedures documented and tested

---

*Last Updated: 2026-02-25*
