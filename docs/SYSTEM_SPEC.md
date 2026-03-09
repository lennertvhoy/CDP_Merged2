# CDP_Merged System Specification

**Purpose:** Technical architecture, API contracts, and implementation details  
**Audience:** Engineers, architects, DevOps, security reviewers  
**Last Updated:** 2026-03-08  
**Version:** 2.0 (Aligned with hardening handoff f9d1906)

---

## Architecture Overview

### Canonical Truth Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  SOURCE SYSTEMS (PII & Operational Master)                       │
│  ├── KBO (Official Registry)                                    │
│  ├── Teamleader (CRM)                                           │
│  ├── Exact Online (Financial)                                   │
│  └── Autotask (Support)                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ ETL Pipelines with KBO matching
┌─────────────────────────────────────────────────────────────────┐
│  POSTGRESQL (Customer Intelligence & Analytical Truth)          │
│  ├── companies (1.94M canonical KBO records)                    │
│  ├── unified_company_360 (multi-source identity-resolved view)  │
│  ├── segment_definitions (canonical segment logic)              │
│  ├── segment_memberships (canonical segment membership)         │
│  ├── company_engagement (engagement scoring facts)              │
│  └── event_facts (anonymized behavioral events)                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ Projection (selective, operational slice)
┌─────────────────────────────────────────────────────────────────┐
│  TRACARDI (Activation Runtime)                                  │
│  ├── Anonymous profiles (UID-first design)                      │
│  ├── Event intake (page views, email engagement)                │
│  └── Workflow engine (CE: draft only; see Event Processor)      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ Natural Language Interface
┌─────────────────────────────────────────────────────────────────┐
│  AI CHATBOT (Operator Interface)                                │
│  ├── LangGraph agent with tool selection                        │
│  ├── Deterministic routing guard for 360° queries               │
│  └── PostgreSQL-first query execution                           │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Principle
**PostgreSQL is the source of truth for all analytical and customer-intelligence queries.** Tracardi receives only the operational projection needed for activation workflows.

---

## Data Layer Specification

### PostgreSQL Schema

#### Core Entities

**companies** (Canonical KBO data)
```sql
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_number VARCHAR(20) UNIQUE NOT NULL,  -- KBO number
    status VARCHAR(10),                             -- AC, ST, etc.
    juridical_situation VARCHAR(100),
    legal_form_code VARCHAR(10),
    type_of_enterprise VARCHAR(10),
    denomination VARCHAR(500),                      -- Company name
    main_email VARCHAR(255),
    main_phone VARCHAR(50),
    main_fax VARCHAR(50),
    main_address_line1 VARCHAR(255),
    main_city VARCHAR(100),
    main_zipcode VARCHAR(20),
    industry_nace_code VARCHAR(10),
    nace_descriptions TEXT[],
    all_nace_codes TEXT[],
    all_names TEXT[],
    establishment_count INTEGER,
    -- metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**unified_company_360** (Identity-resolved multi-source view)
```sql
CREATE VIEW unified_company_360 AS
SELECT 
    c.id,
    c.enterprise_number AS kbo_number,
    c.denomination AS kbo_company_name,
    -- Teamleader fields
    tc.id AS tl_company_id,
    tc.name AS tl_company_name,
    tc.email AS tl_email,
    -- Exact fields
    ec.account_id AS exact_account_id,
    ec.account_name AS exact_company_name,
    -- Autotask fields
    ac.company_id AS autotask_company_id,
    ac.company_name AS autotask_company_name,
    ac.open_tickets AS autotask_open_tickets,
    -- Identity linkage status
    CASE 
        WHEN tc.id IS NOT NULL AND ec.account_id IS NOT NULL AND ac.company_id IS NOT NULL THEN 'linked_all'
        WHEN tc.id IS NOT NULL AND ec.account_id IS NOT NULL THEN 'linked_kbo_teamleader_exact'
        WHEN ec.account_id IS NOT NULL AND ac.company_id IS NOT NULL THEN 'linked_kbo_exact_autotask'
        ELSE 'linked_kbo_only'
    END AS identity_link_status,
    -- Source count
    (CASE WHEN tc.id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN ec.account_id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN ac.company_id IS NOT NULL THEN 1 ELSE 0 END) AS total_source_count
FROM companies c
LEFT JOIN teamleader_companies tc ON c.enterprise_number = tc.company_number
LEFT JOIN exact_accounts ec ON c.enterprise_number = ec.vat_number
LEFT JOIN autotask_companies ac ON c.enterprise_number = ac.kbo_number;
```

#### Segment Infrastructure

**segment_definitions** (Canonical segment logic)
```sql
CREATE TABLE segment_definitions (
    id UUID PRIMARY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    filter_criteria JSONB NOT NULL,  -- Stored filter parameters
    nace_codes TEXT[],
    city VARCHAR(100),
    has_email BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**segment_memberships** (Canonical membership, PostgreSQL-authoritative)
```sql
CREATE TABLE segment_memberships (
    segment_id UUID REFERENCES segment_definitions(id),
    company_id UUID REFERENCES companies(id),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (segment_id, company_id)
);
```

#### Engagement Scoring

**company_engagement** (NBA scoring facts)
```sql
CREATE TABLE company_engagement (
    id SERIAL PRIMARY KEY,
    company_id UUID REFERENCES companies(id),
    kbo_number VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    event_type VARCHAR(50) NOT NULL,
    event_weight INTEGER NOT NULL DEFAULT 0,
    event_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Engagement Scoring Model

**Version:** 2026-03-08
**Endpoint:** `GET /api/scoring-model` (defined in `scripts/cdp_event_processor.py`; refresh any older long-running local daemon before treating the route as live-runtime verified)

```json
{
    "version": "2026-03-08",
    "engagement_thresholds": {
        "high": {"min_inclusive": 50},
        "low": {"min_inclusive": 0, "max_exclusive": 20},
        "medium": {"min_inclusive": 20, "max_exclusive": 50}
    },
    "event_weights": {
        "email.bounced": -5,
        "email.clicked": 10,
        "email.complained": -10,
        "email.delivered": 2,
        "email.opened": 5,
        "email.sent": 1,
    },
    "recommendation_rules": {
        "cross_sell": {
            "trigger": "nace_code in CROSS_SELL_MAP",
            "priority": "medium"
        },
        "multi_division": {
            "trigger": "source_systems < 3",
            "priority": "medium"
        },
        "re_activation": {
            "trigger": "engagement_score < 20",
            "priority": "medium"
        },
        "sales_opportunity": {
            "trigger": "engagement_score >= 50 and open_deals == 0",
            "priority": "high"
        },
        "support_expansion": {
            "trigger": "open_tickets > 0",
            "priority": "medium"
        }
    }
}
```

---

## API Contracts

### Event Processor API

**Base:** `http://localhost:5001` (local)
**Source:** `scripts/cdp_event_processor.py`

#### Get Scoring Model
```
GET /api/scoring-model
```

Response:
```json
{
  "version": "2026-03-08",
  "event_weights": {...},
  "engagement_thresholds": {...},
  "recommendation_rules": {...}
}
```

#### Get Next Best Action
```
GET /api/next-best-action/{kbo_number}
```

Response:
```json
{
  "status": "success",
  "kbo_number": "0438437723",
  "company_name": "B.B.S. Entreprise",
  "engagement_level": "low",
  "engagement_score": 15,
  "source_systems": 4,
  "priority": "medium",
  "recommendations": [
    {
      "type": "support_expansion",
      "action": "Review support contract for expansion",
      "reason": "1 open ticket(s) indicate support needs"
    },
    {
      "type": "re_activation",
      "action": "Send re-engagement campaign with special offer",
      "reason": "Low engagement - risk of churn"
    }
  ],
  "timestamp": "2026-03-09T06:34:11.388686+00:00"
}
```

#### Get Engagement Leads
```
GET /api/engagement/leads?min_score=5&limit=50
```

Response:
```json
{
  "status": "success",
  "count": 2,
  "min_score": 5,
  "leads": [
    {
      "kbo_number": "0438437723",
      "company_name": "B.B.S. ENTREPRISE",
      "engagement_score": 15,
      "email_opens": 1,
      "email_clicks": 1,
      "last_activity": "2026-03-08T19:04:49.972044+00:00"
    },
    {
      "kbo_number": "0408340801",
      "company_name": "Accountantskantoor Dubois",
      "engagement_score": 5,
      "email_opens": 1,
      "email_clicks": 0,
      "last_activity": "2026-03-08T19:06:03.392552+00:00"
    }
  ]
}
```

### Webhook Gateway API

**Base:** `http://localhost:8000`  
**Source:** `scripts/webhook_gateway.py`

#### Webhook Endpoints

| Endpoint | Method | Description | Security |
|----------|--------|-------------|----------|
| `/webhook/teamleader` | POST | Teamleader CRM events | HMAC-SHA256 signature |
| `/webhook/brevo` | POST | Brevo email events | HMAC-SHA256 signature |
| `/webhook/resend` | POST | Resend email events (Svix) | Svix signature verification |
| `/webhook/website` | POST | Website behavior events | Rate limiting, IP allowlist |

#### Resend Webhook: Privacy-Safe Forwarding

The gateway sanitizes Resend webhook payloads before downstream projection:

**Input (from Resend):**
```json
{
  "type": "email.opened",
  "data": {
    "to": "customer@example.com",
    "from": "noreply@company.com",
    "subject": "Your Invoice",
    "email_id": "..."
  }
}
```

**Output (to Tracardi):**
```json
{
  "profile": {"id": "opaque-uid-123", "traits": {"recipient_domain": "example.com"}},
  "events": [{
    "type": "email.opened",
    "properties": {
      "recipient_hash": "sha256-of-email",
      "sender_domain": "company.com",
      "subject_hash": "sha256-of-subject"
    }
  }]
}
```

**Privacy Controls:**
- Raw email addresses replaced with SHA256 hashes
- Raw subject lines replaced with hashes
- Only domain names preserved (for routing/analysis)
- UID-first profile identifiers

---

## Privacy Architecture

### UID-First Design

**Principle:** PII is resolved only at presentation time; the core system operates on opaque identifiers.

```
┌─────────────────────────────────────────────────────────────────┐
│  OPERATOR QUERY (PII visible)                                   │
│  "Show me info@bbsentreprise.be"                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ Resolve at query time
┌─────────────────────────────────────────────────────────────────┐
│  CORE SYSTEM (UID-only)                                         │
│  Profile ID: "profile-abc-123"                                  │
│  Tools: get_company_360, update_engagement_score                │
│  Logging: UID references only                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ Project for activation
┌─────────────────────────────────────────────────────────────────┐
│  ACTIVATION LAYER (hashed/anonymized)                           │
│  Tracardi: Anonymous profiles                                   │
│  Webhook forward: domain + hash only                            │
└─────────────────────────────────────────────────────────────────┘
```

### Known Runtime Divergence

**Current State:** The system operates with documented privacy divergence:

| Layer | Design Target | Current Reality | Gap |
|-------|---------------|-----------------|-----|
| PostgreSQL core | UID-first | UID-first | ✅ Aligned |
| Tracardi profiles | Anonymous | Anonymous | ✅ Aligned |
| Event metadata | Hashed only | Raw email in event payload | ⚠️ Divergent |
| Webhook forward | Sanitized | Sanitized (gateway strips PII) | ✅ Aligned |

**Mitigation:** `scripts/webhook_gateway.py` implements `sanitize_resend_event_data()` and `build_tracardi_forward_payload()` to strip raw PII before downstream projection.

---

## AI Tool Selection Architecture

### Routing Guard (Option D)

**Location:** `src/graph/nodes.py` - `critic_node()`  
**Purpose:** Prevent LLM from selecting incorrect tools for specific query patterns

```python
QUERY_ROUTING_RULES = [
    {
        "patterns": ["linked to kbo", "match rate", "kbo link", "link quality"],
        "required_tool": "get_identity_link_quality",
        "forbidden_tools": ["get_data_coverage_stats", "search_profiles", "aggregate_profiles"]
    },
    {
        "patterns": ["revenue distribution", "revenue by city", "geographic distribution"],
        "required_tool": "get_geographic_revenue_distribution",
        "forbidden_tools": ["aggregate_profiles", "search_profiles"]
    },
    {
        "patterns": ["pipeline value for", "total pipeline", "industry pipeline"],
        "required_tool": "get_industry_summary",
        "forbidden_tools": ["search_profiles", "aggregate_profiles"]
    }
]
```

**Validation:** `tests/unit/test_critic_routing.py` - 27 tests

---

## Deployment Architecture

### Local-First Mode (Current)

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgis/postgis:15-3.4
    volumes:
      - postgres_data:/var/lib/postgresql/data
    
  tracardi:
    image: tracardi/tracardi:0.9.0
    depends_on:
      - elasticsearch
      
  chatbot:
    build: .
    depends_on:
      - postgres
      - tracardi
```

### Azure Target (Paused)

| Resource | Type | Purpose |
|----------|------|---------|
| `ca-cdpmerged-fast` | Container App | Chatbot API |
| `vm-tracardi-cdpmerged-prod` | Azure VM | Tracardi + Elasticsearch |
| `vm-data-cdpmerged-prod` | Azure VM | PostgreSQL |
| `gpt-4o-mini` | Azure OpenAI | LLM inference |

**Status:** Deployment path paused by user direction to save costs.

---

## Testing & Verification

### Unit Test Coverage

| Component | Test File | Status |
|-----------|-----------|--------|
| Webhook Gateway | `tests/unit/test_webhook_gateway.py` | ✅ 48 passing |
| Event Processor | `tests/unit/test_cdp_event_processor.py` | ✅ 6 passing |
| Critic Routing | `tests/unit/test_critic_routing.py` | ✅ 27 passing |

### Verification Commands

```bash
# Webhook gateway tests
poetry run pytest tests/unit/test_webhook_gateway.py -vv

# Event processor tests
poetry run pytest tests/unit/test_cdp_event_processor.py -vv

# Combined (no hang observed)
poetry run pytest tests/unit/test_webhook_gateway.py tests/unit/test_cdp_event_processor.py -vv
```

---

## References

- **Business Case:** `docs/BUSINESS_CASE.md`
- **Illustrated Evidence:** `docs/ILLUSTRATED_GUIDE.md`
- **Implementation:** `scripts/webhook_gateway.py`, `scripts/cdp_event_processor.py`
- **Tests:** `tests/unit/test_webhook_gateway.py`, `tests/unit/test_cdp_event_processor.py`
