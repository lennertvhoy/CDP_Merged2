# ACP Execution Plan - Strategic Improvements

**Source:** STRATEGIC_ROADMAP.md  
**Execution Model:** Sequential ACP sessions, one at a time  
**Constraint:** Only one active implementation agent per stream

---

## ACP-1: Real-Time Pipeline Foundation - Webhook Listener
**Priority:** P0  
**Estimated Duration:** 45-60 minutes  
**Agent:** codex  
**Status:** ✅ COMPLETE (2026-03-03)

### Completed Deliverables
- [x] `infra/cbe_webhook/` directory created
- [x] `main.py` - FastAPI app with `/webhook/cbe` endpoint
- [x] `Dockerfile` - Multi-stage Python 3.12 container
- [x] `requirements.txt` - Dependencies
- [x] `infra/terraform/cbe_webhook.tf` - Azure deployment
- [x] `tests/integration/test_cbe_webhook.py` - 10 tests passing

### Commit
`7c9065d` - feat(infra): add CBE webhook listener for real-time pipeline

### Scope
Create the CBE webhook listener infrastructure only - not the full pipeline.

### Deliverables
1. `infra/cbe_webhook/` directory with:
   - `main.py` - FastAPI webhook endpoint
   - `Dockerfile` - Container for webhook listener
   - `requirements.txt` - Dependencies
2. Webhook endpoint at `/webhook/cbe` that:
   - Validates payload signature
   - Parses company change events
   - Logs events to stdout
3. Terraform config for Azure Container App deployment
4. Basic tests:
   - `tests/integration/test_cbe_webhook.py`
   - Payload validation tests

### Out of Scope (Future ACPs)
- Event Hub integration
- PostgreSQL CDC
- Streaming workers
- Dashboard

### Verification
```bash
# Local test
curl -X POST http://localhost:8080/webhook/cbe \
  -H "Content-Type: application/json" \
  -d '{"company_number": "0200225413", "change_type": "update"}'

# Deployed test (after CD)
curl -X POST https://cbe-webhook-*.azurecontainerapps.io/webhook/cbe \
  -H "Content-Type: application/json" \
  -d '{"company_number": "0200225413", "change_type": "update"}'
```

### Handoff Criteria
- [ ] Code committed and pushed
- [ ] CI/CD green
- [ ] Deployed to Azure
- [ ] Webhook receiving and logging events
- [ ] Handoff block in WORKLOG.md

---

## ACP-2: Multi-Tenant Schema Foundation  
**Priority:** P0  
**Estimated Duration:** 60-90 minutes  
**Agent:** codex  
**Status:** PENDING ACP-1 COMPLETION

### Relationship to Demo Readiness
**Parallel Track:** ACP-2 (strategic architecture) runs parallel to "DEMO READINESS - Chainlit OAuth" (immediate demo needs). They are complementary:

- **ACP-2:** Full multi-tenant architecture (schema-per-tenant, enterprise-grade)
- **Demo Track:** Quick OAuth for immediate demo (sufficient for presentations)

**Execute both in parallel** - ACP-2 for long-term architecture, demo track for immediate stakeholder demos.

### Scope
Tenant provisioning service and schema-per-tenant foundation.

### Deliverables
1. `src/services/tenant_provisioning.py`:
   - `create_tenant()` - Create isolated schema
   - `delete_tenant()` - Cleanup
   - `list_tenants()` - Management
2. Database migration for tenant metadata table
3. `src/core/tenant_db.py` - Connection routing
4. Tests for tenant isolation

### Out of Scope
- JWT/RBAC (ACP-3)
- Admin dashboard (ACP-7)
- Billing (ACP-8)

---

## ACP-3: Tenant Authentication & RBAC
**Priority:** P0  
**Estimated Duration:** 45-60 minutes  
**Agent:** codex  
**Status:** PENDING ACP-2 COMPLETION

### Scope
JWT authentication and role-based access for multi-tenancy.

### Deliverables
1. `src/core/auth.py`:
   - JWT token validation
   - Tenant extraction from token
   - Role checking
2. `src/middleware/tenant_auth.py`:
   - FastAPI middleware
   - Automatic tenant context
3. Update existing endpoints to use auth
4. Tests for auth flow

---

## ACP-4: Predictive Scoring - Feature Engineering
**Priority:** P1  
**Estimated Duration:** 60-75 minutes  
**Agent:** codex  
**Status:** PENDING ACP-3 COMPLETION

### Scope
Feature extraction and storage for ML scoring.

### Deliverables
1. `src/ml/features.py`:
   - Feature extraction from companies
   - Feature store (Redis/PostgreSQL)
2. `scripts/compute_features.py`:
   - Batch feature computation
   - Incremental updates
3. Feature definitions and schema

---

## ACP-5: Predictive Scoring - Model Training Pipeline
**Priority:** P1  
**Estimated Duration:** 75-90 minutes  
**Agent:** codex  
**Status:** PENDING ACP-4 COMPLETION

### Scope
XGBoost propensity model training and persistence.

### Deliverables
1. `src/ml/propensity_model.py`:
   - Model training
   - Model evaluation
   - Model persistence to Azure Blob
2. `scripts/train_propensity_model.py`:
   - Training pipeline
   - Evaluation metrics
3. Model performance tracking

---

## Execution Protocol

### Before Each ACP
1. Read current PROJECT_STATE.yaml
2. Verify previous ACP handoff complete
3. Confirm no other ACP running
4. Update NEXT_ACTIONS.md with current ACP

### During ACP
1. Follow AGENTS.md protocol
2. Small, verified commits
3. CI/CD green before handoff
4. Document in WORKLOG.md

### After ACP
1. Update PROJECT_STATE.yaml
2. Update STRATEGIC_ROADMAP.md progress
3. Mark ACP complete in this file
4. Trigger next ACP only after review

### Never Parallel
- Only one ACP session active at a time
- Coordinator (human or automated) starts next ACP
- No overlapping development work

---

*This plan separates strategic work into manageable, verifiable increments.*
