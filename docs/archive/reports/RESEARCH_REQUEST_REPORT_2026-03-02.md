# CDP_Merged - Comprehensive Research Request Report

**Date:** 2026-03-02  
**Prepared for:** Research Agent Analysis  
**Scope:** Full project state analysis for improvement opportunities

---

## Executive Summary

The CDP_Merged project is an AI-assisted Customer Data Platform (CDP) built around three core pillars:
1. **PostgreSQL** - Primary storage for historical data and complex queries
2. **Tracardi** - Event ingestion, workflows, and outbound marketing integrations
3. **AI Chatbot** - Natural language to SQL/query interface (Chainlit-based)

**Current State:** Demo-First Mode - 95% demo-ready with chatbot environment recently fixed.

---

## 1. Project Architecture Overview

### Core Technology Stack

| Component | Technology | Purpose | Status |
|-----------|------------|---------|--------|
| Chatbot UI | Chainlit 2.9.6 | AI chat interface | ✅ Fixed & Running |
| LLM Framework | LangGraph + LangChain | AI orchestration | ✅ Working |
| Database | PostgreSQL | Primary data store | ✅ Reported running |
| Event Platform | Tracardi 0.9.x | CDP/Event ingestion | ✅ Deployed (2,500 profiles) |
| Search | Elasticsearch 8.x | Profile indexing | ✅ Green status |
| Cache | Redis | Session/cache | ✅ Running |
| Email | Resend API | Outbound email/webhooks | ✅ Configured |
| Infrastructure | Azure VMs + Container Apps | Hosting | ✅ Running |

### Infrastructure Layout

```
Azure Resource Group: rg-cdpmerged-fast
├── vm-tracardi-cdpmerged-prod (137.117.212.154)
│   ├── Tracardi API: :8686
│   ├── Tracardi GUI: :8787
│   └── MySQL (internal)
├── vm-data-cdpmerged-prod (10.57.3.10)
│   ├── Elasticsearch: :9200
│   └── Redis
└── ca-cdpmerged-fast (Container App - chatbot)
    └── Image: ghcr.io/lennertvhoy/cdp_merged:sha-6d88fa6
```

---

## 2. Codebase Structure

### Source Code (`src/`)

```
src/
├── app.py                    # Chainlit chatbot entry point
├── config.py                 # Pydantic settings (Azure OpenAI, Tracardi, PostgreSQL)
├── ai_interface/             # LLM interaction layer
│   ├── tools/                # Tool implementations
│   │   ├── email.py          # Resend email operations
│   │   ├── search.py         # Search/nl2sql
│   │   ├── export.py         # Data export
│   │   └── nace_resolver.py  # NACE code resolution
│   └── schemas.py            # Pydantic schemas
├── graph/                    # LangGraph workflow
│   ├── nodes.py              # Graph nodes
│   ├── edges.py              # Graph edges
│   ├── state.py              # Graph state
│   └── workflow.py           # Workflow builder
├── services/                 # External service clients
│   ├── tracardi.py           # Tracardi API client
│   ├── postgresql_client*.py # PostgreSQL clients
│   ├── resend.py             # Resend API client
│   ├── azure_search.py       # Azure Cognitive Search
│   └── flexmail.py           # Legacy (deprecated)
├── search_engine/            # Query builders
│   ├── builders/
│   │   ├── sql_builder.py    # SQL query builder
│   │   ├── tql_builder.py    # Tracardi Query Language
│   │   └── es_builder.py     # Elasticsearch builder
│   └── factory.py            # Search engine factory
├── core/                     # Core utilities
└── enrichment/               # Data enrichment pipeline
```

### Scripts (`scripts/`)

| Script | Purpose | Status |
|--------|---------|--------|
| `demo_*_integration.py` | Integration demos (Exact, Teamleader, Autotask) | ✅ Created |
| `sync_kbo_to_tracardi.py` | KBO data sync to Tracardi | ✅ Working |
| `setup_tracardi_*.py` | Tracardi configuration | ✅ Working |
| `setup_resend_*.py` | Resend webhook/audience setup | ⚠️ Pending test |
| `smoke_test_tracardi_e2e.py` | E2E smoke tests | ✅ Created |
| `import_kbo_streaming.py` | Streaming KBO import | ✅ Available |

---

## 3. Current Demo Readiness Status

### ✅ Working Components

| Component | Evidence | Notes |
|-----------|----------|-------|
| Tracardi CDP | 2,500 profiles loaded | East Flanders IT companies |
| Tracardi GUI | http://137.117.212.154:8787 | Professional, fast |
| Event Sources | 4 sources created | kbo-batch, kbo-realtime, resend-webhook, cdp-api |
| Profile Search API | Fixed wildcard queries | Hotfix applied to Tracardi |
| Chatbot Local | http://localhost:8000 | Python 3.12 fix applied |
| Integration Scripts | 4 demo scripts | Exact, Teamleader, Autotask |

### ⚠️ Pending for 100% Demo Readiness

| Item | Priority | Blocker/Action |
|------|----------|----------------|
| Tracardi Workflows | Critical | GUI-based creation needed |
| Resend Webhooks | Critical | Needs configuration |
| NL→SQL Query Testing | High | Environment ready, needs testing |
| Container App | Medium | Connection timeout issues |
| Tracardi Segments | Low | Requires license (use profile search instead) |

---

## 4. Data Assets

### KBO Dataset
- **File:** `KboOpenData_0285_2026_02_27_Full.zip` (312MB)
- **Enterprise Records:** 1,940,603 companies
- **Synced to Tracardi:** 2,500 East Flanders IT companies
- **Sync Script:** `scripts/sync_kbo_to_tracardi.py`

### Tracardi Profiles
- **Total:** 2,500 profiles
- **Source:** KBO data filtered by region (Oost-Vlaanderen) + NACE codes (IT companies)
- **Batch Size:** 100 profiles per batch
- **Success Rate:** 100% (25/25 batches)

---

## 5. Known Issues & Technical Debt

### Critical Issues

| Issue | Impact | Root Cause | Current Workaround |
|-------|--------|------------|-------------------|
| Python 3.14 incompatibility | Chatbot won't start | anyio/chainlit async changes | Fixed: Using Python 3.12 |
| Container App timeout | Remote chatbot unavailable | Unknown (needs investigation) | Use local chatbot |
| Tracardi segments require license | Can't create segments in GUI | Commercial feature | Use profile search with filters |

### CI/CD Status (Last Run: 22596584905)

| Stage | Status | Notes |
|-------|--------|-------|
| Secret Detection | ✅ Pass | |
| Lint & Type Check | ✅ Pass | Ruff + mypy clean |
| Bandit Security Scan | ✅ Pass | |
| pip-audit | ❌ 11 CVEs | Pre-existing (chainlit, langchain-core, etc.) |
| Unit Tests | ❌ Pre-existing failures | |

### Technical Debt (Post-Demo)

- Hardcoded credentials review needed
- 11 CVEs in dependencies
- Unit test failures
- Terraform provider plugin issues (local)
- poetry.lock staleness issues

---

## 6. Documentation State

### Source of Truth Hierarchy

| File | Purpose | Status |
|------|---------|--------|
| `AGENTS.md` | Operating rules | ✅ Current |
| `PROJECT_STATE.yaml` | Structured live state | ✅ Updated 2026-03-02 |
| `STATUS.md` | Narrative summary | ✅ Current |
| `NEXT_ACTIONS.md` | Active queue | ✅ Current |
| `BACKLOG.md` | Medium-term priorities | ✅ Current |
| `WORKLOG.md` | Session history | ✅ Updated |

### Key Documentation

| Document | Purpose | Status |
|----------|---------|--------|
| `docs/DEMO_GUIDE.md` | Step-by-step demo script | ✅ Created |
| `docs/TRACARDI_WORKFLOW_SETUP.md` | Workflow configuration | ✅ Created |
| `docs/ARCHITECTURE_*.md` | Architecture decisions | ⚠️ Needs review |
| `docs/HANDOFF_*` | Session handoffs | ✅ Current |

---

## 7. Integration Points

### External APIs

| Service | Integration | Status | Credentials |
|---------|-------------|--------|-------------|
| Azure OpenAI | LLM provider | ✅ Configured | In .env |
| Tracardi API | CDP/Events | ✅ Working | In .env |
| Resend API | Email/Webhooks | ✅ Configured | In .env |
| PostgreSQL | Primary DB | ✅ Reported | In .env.database |
| Exact Online | Financial data | ⚠️ Demo script only | User-provided |
| Teamleader | CRM data | ⚠️ Demo script only | User-provided |
| Autotask | Service desk | ⚠️ Demo script only | User-provided |

### Data Flows

```
KBO ZIP → sync_kbo_to_tracardi.py → Tracardi API → Elasticsearch
                                          ↓
User Query → Chatbot → LangGraph → NL→SQL → PostgreSQL/Tracardi
                                          ↓
                                    Resend API → Email Send
                                          ↓
                                    Webhook → Tracardi Events
```

---

## 8. Research Questions for Improvement

### Architecture & Design

1. **Technology Choices**
   - Is Tracardi the optimal CDP choice vs alternatives (Rudderstack, Segment, Apache Unomi)?
   - Should we consider migrating from Chainlit to a more production-ready framework (FastAPI + React)?
   - Is the dual-database approach (PostgreSQL + Elasticsearch) adding unnecessary complexity?

2. **Scalability**
   - Current: 2,500 profiles - how will this architecture handle 100K+ profiles?
   - Batch import (100 profiles/batch) - is this optimal for large datasets?
   - Elasticsearch on single VM - clustering strategy needed?

3. **Security**
   - Hardcoded credentials in scripts - automated secret scanning solution?
   - 11 CVEs in dependencies - dependency update strategy?
   - Azure Container App timeout - security group misconfiguration?

### Code Quality

4. **Technical Debt**
   - 26 mypy errors were fixed - systematic type annotation needed?
   - Unit test failures - test strategy review?
   - Poetry lock issues - dependency management improvement?

5. **Maintainability**
   - Two PostgreSQL clients (postgresql_client.py + postgresql_client_optimized.py) - consolidation?
   - Graph workflow complexity - documentation/refactoring needed?
   - Demo scripts have hardcoded data - make them truly dynamic?

### Operations

6. **Deployment**
   - Container App issues - debug and fix or migrate to AKS?
   - Terraform provider plugin issues - CI/CD pipeline improvement?
   - Hotfix management - all patches now in IaC, but process review needed?

7. **Monitoring**
   - No centralized logging visible - ELK/Loki needed?
   - Health checks - more comprehensive monitoring?
   - Alerting - PagerDuty/Opsgenie integration?

### Business Logic

8. **Data Pipeline**
   - KBO data sync is batch - should this be streaming?
   - Enrichment pipeline status - fully operational?
   - Data quality checks - automated validation?

9. **Feature Completeness**
   - Tracardi segments require license - build custom segmentation?
   - Workflows not created - automation opportunities?
   - Webhook processing - idempotency guarantees?

---

## 9. Recommendations for Research

### High-Impact Improvements

1. **Container App Fix or Migration**
   - Investigate connection timeout root cause
   - Consider migration to Azure Kubernetes Service (AKS) for better control
   - Implement proper health checks and monitoring

2. **Security Hardening**
   - Implement automated secret scanning (GitGuardian, TruffleHog)
   - Dependency vulnerability management (Snyk, Dependabot)
   - Credential injection via Azure Key Vault

3. **Scalability Planning**
   - Load testing with k6/Artillery
   - Elasticsearch cluster configuration
   - Database connection pooling review

### Medium-Impact Improvements

4. **Code Consolidation**
   - Merge duplicate PostgreSQL clients
   - Refactor demo scripts for dynamic data
   - Improve test coverage

5. **Observability**
   - Structured logging with correlation IDs
   - Distributed tracing (Jaeger/Tempo)
   - Metrics dashboard (Grafana)

### Low-Impact/Nice-to-Have

6. **Developer Experience**
   - Docker Compose for local development
   - Makefile improvements
   - Pre-commit hooks enhancement

7. **Documentation**
   - API documentation (OpenAPI/Swagger)
   - Architecture Decision Records (ADRs)
   - Runbooks for common operations

---

## 10. Files to Analyze

### Critical Files for Research

```
Core Application:
- src/app.py
- src/config.py
- src/graph/nodes.py
- src/graph/workflow.py
- src/services/tracardi.py
- src/services/postgresql_client*.py

Infrastructure:
- infra/tracardi/*.tf
- infra/tracardi/cloud-init/*.tftpl
- docker-compose.yml
- Dockerfile

Configuration:
- pyproject.toml
- poetry.lock
- .env (structure, not values)

Documentation:
- AGENTS.md
- PROJECT_STATE.yaml
- docs/ARCHITECTURE_*.md
- docs/DEMO_GUIDE.md
```

---

## 11. Success Criteria for Research Output

The research agent should provide:

1. **Comparative Analysis**
   - Alternative technology comparisons (CDP, chatbot framework, search)
   - Trade-off analysis with scoring matrix

2. **Risk Assessment**
   - Security vulnerability prioritization
   - Scalability bottlenecks identification
   - Technical debt prioritization

3. **Implementation Roadmap**
   - Prioritized improvement backlog
   - Effort estimates (S/M/L)
   - Dependency mapping

4. **Proof of Concepts**
   - For high-impact changes, provide POC code/strategy
   - Migration plans with rollback strategies

---

## Appendix: Quick Reference

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| Tracardi GUI | http://137.117.212.154:8787 | admin@admin.com / terraform output |
| Tracardi API | http://137.117.212.154:8686 | Same as GUI |
| Chatbot Local | http://localhost:8000 | N/A |

### Key Commands

```bash
# Start chatbot
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
source .venv/bin/activate
PYTHONPATH=/home/ff/.openclaw/workspace/repos/CDP_Merged CHAINLIT_AUTH_SECRET=test-secret-123 chainlit run src/app.py --host 0.0.0.0 --port 8000

# Get Tracardi password
terraform -chdir=infra/tracardi output -raw tracardi_admin_password

# Sync KBO data
TRACARDI_TARGET_COUNT=2500 python scripts/sync_kbo_to_tracardi.py
```

### Git Status
- **Branch:** push-clean
- **Ahead of main:** 3 commits
- **Last commit:** df16672 (chatbot fix)

---

*This report was generated on 2026-03-02 for comprehensive project analysis and improvement opportunity identification.*
