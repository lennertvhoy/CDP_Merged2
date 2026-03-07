# CDP_Merged Migration Plan v2.0

**From:** Tracardi (Broken, Deleted)
**To:** Azure-Only Architecture (PostgreSQL + Cognitive Search)
**Budget:** €150/month maximum
**Timeline:** 12 weeks
**Status:** In Progress (Infrastructure cleanup complete)

---

## Executive Summary

**Why We Migrated:**
- Tracardi's 10,000 record hard limit made our 516K dataset unqueryable
- Deep pagination was broken, enrichment kept failing
- VMs cost €140/month and couldn't handle the data volume

**New Architecture:**
- **Azure Database for PostgreSQL** (B1ms): Primary data store, unlimited pagination
- **Azure Cognitive Search**: Full-text search, AI vectors, faceted search
- **Azure Container Apps**: API hosting, AI chatbot service
- **Azure OpenAI**: NL→SQL translation, description generation

**Cost:** €150/month (fits budget)

---

## Current State (Post-Cleanup)

### ✅ Deleted (Old Tracardi Infrastructure)
| Resource | Savings |
|----------|---------|
| vm-tracardi-cdpmerged-prod | ~€70/mo |
| vm-data-cdpmerged-prod | ~€70/mo |
| Associated NICs, IPs, NSGs, disks | ~€20/mo |
| **Total Savings** | **~€160/mo** |

### ✅ Keeping (New Architecture Foundation)
| Resource | Purpose | Cost |
|----------|---------|------|
| aoai-cdpmerged-fast | Azure OpenAI (GPT-4o-mini) | ~€20/mo |
| cdpmerged-search | Cognitive Search | ~€60/mo |
| ca-cdpmerged-fast | Container Apps | ~€25/mo |
| ca67b3b5dbe8acr | Container Registry | ~€5/mo |
| stcdpmergedpr5roe | Storage Account | ~€15/mo |
| workspace-rgcdpmergedfastF2eP | Log Analytics | ~€25/mo |
| **Current Total** | | **~€150/mo** |

### ⚠️ Missing: PostgreSQL Database
Need to provision: Azure Database for PostgreSQL Flexible Server (B1ms) ~€12/mo

**With B1ms:** Total ~€162/mo (slightly over, optimize Container Apps to compensate)

---

## Architecture Decisions

### 1. Deep Pagination: PostgreSQL Primary Read Model

**Decision:** PostgreSQL handles all pagination from day one. No Tracardi dependency.

**Rationale:**
- Tracardi VMs deleted — no longer an option
- PostgreSQL `OFFSET/LIMIT` works for any page depth (no 10K limit)
- Full SQL + JOINs for complex queries
- Cost: €12/mo vs €140/mo for VMs

**Implementation:**
```python
# Native deep pagination — works for page 1 to page 5000+
def get_companies(page=1, page_size=100):
    sql = """
        SELECT c.*, json_agg(cp.*) as contacts
        FROM companies c
        LEFT JOIN contacts cp ON cp.company_id = c.id
        ORDER BY c.updated_at DESC
        LIMIT %s OFFSET %s
    """
    offset = (page - 1) * page_size
    return db.execute(sql, (page_size, offset))
```

### 2. Search Strategy: Hybrid PostgreSQL + Cognitive Search

**Pattern 1: Simple filters + pagination** → PostgreSQL only
**Pattern 2: Full-text search + relevance** → Cognitive Search → PostgreSQL for details

```python
def search_companies(query, filters=None, page=1):
    # Phase 1: Cognitive Search for text relevance
    es_results = cognitive_search.search(query, top=1000)
    ids = [r["id"] for r in es_results]
    
    if not ids:
        return {"results": [], "total": 0}
    
    # Phase 2: PostgreSQL for relational data + pagination
    sql = """
        SELECT c.*, json_agg(cp.*) as contacts
        FROM companies c
        LEFT JOIN contacts cp ON cp.company_id = c.id
        WHERE c.id = ANY(%s)
        ORDER BY array_position(%s, c.id)  -- Preserve ES relevance order
        LIMIT %s OFFSET %s
    """
    offset = (page - 1) * page_size
    return db.execute(sql, (ids, ids, page_size, offset))
```

### 3. AI Chatbot: NL→SQL with Validation Layer

**Architecture:**
```
User Query → Intent Classification → Template Selection OR Schema-Constrained Generation
                                         ↓
                              information_schema Validation
                                         ↓
                              pglast SQL Parsing
                                         ↓
                              EXPLAIN (ANALYZE) Pre-flight
                                         ↓
                              Parameterized Query Execution
                                         ↓
                              Result Formatting
```

**Safety Guardrails:**
- Schema-constrained generation (no hallucinated tables/columns)
- 50+ validated query templates covering 80% of use cases
- Whitelist: SUM, COUNT, AVG, MIN, MAX only
- Parameterized queries (no string interpolation)
- pglast SQL structure validation

---

## 12-Week Implementation Plan

### Phase 1: Infrastructure (Week 1)
**Goal:** PostgreSQL provisioned, schema deployed

| Task | Owner | Deliverable |
|------|-------|-------------|
| Provision PostgreSQL B1ms | Azure | Running database |
| Deploy schema | Dev | Tables, indexes, constraints |
| Configure backups | Azure | 7-day retention |
| Set up monitoring | Dev | Azure Monitor alerts |

**Cost Impact:** +€12/mo (PostgreSQL)

### Phase 2: Data Migration (Week 2-3)
**Goal:** 516K profiles migrated from Tracardi dump to PostgreSQL

| Task | Owner | Deliverable |
|------|-------|-------------|
| Export Tracardi data | Dev | JSON/Parquet dump |
| Build ETL pipeline | Dev | Python ingestion script |
| Import to PostgreSQL | Dev | 516K rows loaded |
| Data quality validation | Dev | 95%+ completeness |
| Build deduplication | Dev | Merge duplicates |

**Key Decision:** Use existing KBO backup file if Tracardi export fails

### Phase 3: API Layer (Week 4-5)
**Goal:** REST API with pagination, filtering, CRUD

| Task | Owner | Deliverable |
|------|-------|-------------|
| FastAPI scaffold | Dev | Running container |
| Company endpoints | Dev | GET/POST/PUT/DELETE |
| Contact endpoints | Dev | Full CRUD |
| Deep pagination | Dev | Tested to page 1000+ |
| Search integration | Dev | Hybrid PG + CS queries |
| Authentication | Dev | Microsoft Entra ID |

### Phase 4: AI Chatbot (Week 6-8)
**Goal:** Natural language querying with validation

| Task | Owner | Deliverable |
|------|-------|-------------|
| NL→SQL service | Dev | Azure OpenAI integration |
| Template library | Dev | 50+ validated templates |
| Schema validator | Dev | Pre-flight checks |
| Query builder UI | Dev | Web interface |
| Context management | Dev | Conversation history |

### Phase 5: Source Connectors (Week 9-10)
**Goal:** Exact Online, Autotask, Teamleader sync

| Task | Owner | Deliverable |
|------|-------|-------------|
| Exact Online connector | Dev | OAuth + OData integration |
| Autotask connector | Dev | API key + rate limiting |
| Teamleader connector | Dev | OAuth + JSON:API |
| Sync orchestration | Dev | Scheduled sync jobs |
| Conflict resolution | Dev | Merge strategy |

**Critical:** Autotask circuit breaker at 95% rate limit (prevents tenant disablement)

### Phase 6: Security & Compliance (Week 11-12)
**Goal:** GDPR compliant, production-ready

| Task | Owner | Deliverable |
|------|-------|-------------|
| Field-level encryption | Dev | PII encryption |
| Audit logging | Dev | Complete audit trail |
| Consent management | Dev | GDPR consent workflow |
| Data retention policies | Dev | Automated deletion |
| Security review | Dev | Penetration test |
| Documentation | Dev | API docs, runbooks |

---

## Technical Specifications

### PostgreSQL Schema (B1ms: 1 vCPU, 2GB RAM)

**Tables:**
- `companies` — 516K rows, 30+ columns
- `contact_persons` — ~1M rows (est.)
- `interactions` — Partitioned monthly
- `segments` — Dynamic segments
- `consent_records` — GDPR compliance
- `audit_log` — Partitioned monthly

**Key Indexes:**
```sql
-- For pagination
CREATE INDEX idx_companies_updated ON companies(updated_at DESC);

-- For search
CREATE INDEX idx_companies_name ON companies USING GIN(company_name gin_trgm_ops);

-- For KBO lookups
CREATE INDEX idx_companies_kbo ON companies(kbo_number);

-- For geospatial
CREATE INDEX idx_companies_geo ON companies USING GIST(
    point(geo_longitude, geo_latitude)
) WHERE geo_latitude IS NOT NULL;
```

### Cognitive Search Index

```json
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1
  },
  "mappings": {
    "properties": {
      "id": {"type": "keyword"},
      "company_name": {
        "type": "text",
        "fields": {
          "suggest": {"type": "completion"}
        }
      },
      "industry_description": {"type": "text"},
      "city": {"type": "keyword"},
      "geo_location": {"type": "geo_point"},
      "search_vector": {"type": "dense_vector", "dims": 384}
    }
  }
}
```

---

## Cost Optimization (€150 Budget)

### Current Spend: ~€150/mo
| Service | SKU | Cost |
|---------|-----|------|
| Cognitive Search | Basic | €60 |
| Container Apps | 0.5 vCPU, 1GB | €25 |
| Azure OpenAI | GPT-4o-mini pay-per-use | €20 |
| Log Analytics | Pay-as-you-go | €25 |
| Storage | Standard | €15 |
| Container Registry | Basic | €5 |
| **Subtotal** | | **€150** |

### PostgreSQL Addition: +€12/mo
**To stay under €150:**
- Option A: Downgrade Cognitive Search to **Free tier** (limited, but works for <10K index) = Save €55
- Option B: Reduce Container Apps to **0.25 vCPU** = Save €12
- Option C: Accept €162/mo (€12 over) and optimize later

**Recommendation:** Option A for Phase 1-2, upgrade Cognitive Search to Basic in Phase 4 when AI search needed.

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| B1ms PostgreSQL too slow | Medium | Monitor query latency, upgrade to D2s if p99 > 2s |
| Data migration fails | High | KBO backup file as fallback, incremental migration |
| Autotask rate limit | High | Circuit breaker at 95%, queue management |
| NL→SQL hallucination | Medium | Template-based + validation layer, 80% template coverage |
| Budget overrun | Medium | Start with Free tier Cognitive Search, upgrade gradually |

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Query latency p99 | <500ms | Application Insights |
| Deep pagination | Page 5000+ works | Automated test |
| Data completeness | >95% | Data quality dashboard |
| Chatbot accuracy | >90% | NL→SQL test set (100 queries) |
| Monthly cost | ≤€150 | Azure Cost Management |
| Uptime | >99% | Azure Monitor |
| GDPR compliance | 100% | Audit checklist |

---

## Immediate Next Actions

1. **Today:** Provision Azure Database for PostgreSQL Flexible Server (B1ms)
2. **This week:** Deploy schema, begin Tracardi data export
3. **Next week:** Start data migration (ETL pipeline)

---

## Document References

- `docs/research/RESEARCH_ANALYSIS_2026-02-28.md` — Technical research report
- `docs/specs/DATABASE_SCHEMA.md` — Complete PostgreSQL schema
- `BACKLOG.md` — 30+ implementation stories
- `docs/ARCHITECTURE_AZURE.md` — Service mapping

---

**Status:** Infrastructure cleanup complete ✅
**Next:** Provision PostgreSQL and begin migration
**Budget:** €150/month target
**Timeline:** 12 weeks to production

---

*Migration Plan v2.0 — PostgreSQL Primary Read Model*
*Date: 2026-02-28*

---

⚠️ **WARNING: THIS DOCUMENT IS OUTDATED**

This document was created during a period of confusion (Feb 28, 2026) when Tracardi was incorrectly assumed to be unable to handle 516K profiles.

**The Reality:**
- The TQL bug was fixed on Feb 26 (commit 447814b)
- All 516K profiles were intact in Elasticsearch
- Tracardi was deleted prematurely based on incorrect assumptions

**Current Source of Truth:**
- See AGENTS.md for correct architecture
- See NEXT_ACTIONS.md for immediate priorities
- Tracardi needs to be RE-DEPLOYED

**Status:** ARCHIVED - Superseded by AGENTS.md
---
