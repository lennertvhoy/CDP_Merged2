# Database Schema Specification

**Status:** Canonical production target  
**Last Updated:** 2026-03-03  
**Platform:** Azure Database for PostgreSQL Flexible Server

This document supersedes older mixed schema drafts that stored direct private PII inside the CDP or treated Elasticsearch/Tracardi as the primary analytical path.

## 1. Truth Layers

### Source Systems

Source systems such as Teamleader, Exact, Autotask, websites, and campaign tools remain the PII and operational master-record layer.

- names, emails, phones, and similar private contact details stay there
- the CDP works on public business data, UIDs, derived facts, and approved references
- activation resolves PII only when an authorized workflow requires it

### PostgreSQL

PostgreSQL is the **customer-intelligence and analytical truth layer**.

It must hold:

- public and business master data
- UID and identity bridge tables
- analytically relevant traits and scores
- AI decision provenance
- consent and suppression state
- canonical segment definitions and memberships
- audit logs
- semantic views and materialized aggregates for the chatbot

### Tracardi

Tracardi is the **projected activation runtime**.

It may hold:

- UID-linked profile projections
- recent events
- operational tags and workflow state
- audience state for campaigns

It must not be treated as:

- the analytical source of truth
- the canonical segment-definition store
- the only durable home of analytically relevant tags

## 2. Design Rules

1. If a tag, score, or trait matters for chatbot answers, it must be durable in PostgreSQL with provenance.
2. Canonical segment logic lives in SQL or explicit metadata outside Tracardi.
3. Mutating actions write to PostgreSQL first, then emit downstream operational updates.
4. Prefer lazy or need-based Tracardi profile creation for active UIDs.
5. Keep raw unstructured PII out of Tracardi and out of general chatbot logs.
6. Query logs, tool traces, audit records, and conversation logs should use UIDs or controlled references wherever feasible; resolve PII only at an authorized presentation or activation step.
7. Identity merges and splits from source systems must be reconciled in the canonical UID bridge before downstream profile links, audiences, or workflow state are updated.
8. Downstream send tools should receive the minimum operational payload; prefer resolving destination PII from a source system or controlled service at authorized send time.

## 3. Canonical PostgreSQL Schema

### 3.1 Organizations

Public company and account-level data. Public KBO company names are allowed here; private contact details are not.

```sql
CREATE TABLE organizations (
    organization_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL UNIQUE,
    uid_type VARCHAR(50) NOT NULL,  -- kbo_number, teamleader_company_id, etc.
    kbo_number VARCHAR(20),
    vat_number VARCHAR(20),
    legal_name VARCHAR(500) NOT NULL,
    legal_form VARCHAR(100),
    nace_code VARCHAR(10),
    nace_description VARCHAR(500),
    employee_count INTEGER,
    company_size VARCHAR(50),
    annual_revenue DECIMAL(15, 2),
    website_url VARCHAR(500),
    city VARCHAR(200),
    postal_code VARCHAR(20),
    province VARCHAR(100),
    country_code VARCHAR(2) DEFAULT 'BE',
    geo_latitude DECIMAL(10, 8),
    geo_longitude DECIMAL(11, 8),
    source_system VARCHAR(50) NOT NULL,
    source_record_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_organizations_uid ON organizations(uid);
CREATE INDEX idx_organizations_kbo ON organizations(kbo_number);
CREATE INDEX idx_organizations_nace ON organizations(nace_code);
CREATE INDEX idx_organizations_city ON organizations(city);
```

### 3.2 Source Identity Links

UID bridge across systems. This is where source-system IDs are connected without copying raw PII into the CDP.

```sql
CREATE TABLE source_identity_links (
    identity_link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL,
    subject_type VARCHAR(50) NOT NULL,  -- organization, contact, household, user
    source_system VARCHAR(50) NOT NULL,
    source_entity_type VARCHAR(50) NOT NULL,  -- company, person, ticket_requester, etc.
    source_record_id VARCHAR(100) NOT NULL,
    tracardi_profile_id VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_system, source_entity_type, source_record_id)
);

CREATE INDEX idx_identity_links_uid ON source_identity_links(uid);
CREATE INDEX idx_identity_links_tracardi ON source_identity_links(tracardi_profile_id);
```

The canonical identity bridge must support merge reconciliation. When an upstream CRM or marketing system merges or splits records, PostgreSQL should record the canonical result first and only then repair downstream Tracardi links or activation audiences.

```sql
CREATE TABLE identity_merge_events (
    identity_merge_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system VARCHAR(50) NOT NULL,
    source_entity_type VARCHAR(50) NOT NULL,
    losing_source_record_id VARCHAR(100) NOT NULL,
    surviving_source_record_id VARCHAR(100) NOT NULL,
    losing_uid VARCHAR(100),
    surviving_uid VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,         -- merge, split, remap
    event_at TIMESTAMP NOT NULL,
    reconciled_at TIMESTAMP,
    reconciliation_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_identity_merge_events_surviving_uid
    ON identity_merge_events(surviving_uid, event_at DESC);
CREATE INDEX idx_identity_merge_events_losing_uid
    ON identity_merge_events(losing_uid, event_at DESC);
```

### 3.3 Contact Roles

Business relationships and decision roles without storing direct private contact coordinates.

```sql
CREATE TABLE contact_roles (
    contact_role_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_uid VARCHAR(100) NOT NULL,
    contact_uid VARCHAR(100) NOT NULL,
    role_name VARCHAR(100),
    department VARCHAR(100),
    seniority VARCHAR(100),
    is_decision_maker BOOLEAN DEFAULT FALSE,
    source_system VARCHAR(50) NOT NULL,
    source_record_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_uid, contact_uid, source_system, source_record_id)
);

CREATE INDEX idx_contact_roles_org ON contact_roles(organization_uid);
CREATE INDEX idx_contact_roles_contact ON contact_roles(contact_uid);
```

### 3.4 Event Facts

Normalized behavioral and operational facts. Store references and derived metrics, not raw private message bodies.

```sql
CREATE TABLE event_facts (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL,
    organization_uid VARCHAR(100),
    event_type VARCHAR(100) NOT NULL,
    event_channel VARCHAR(50),
    event_source VARCHAR(50) NOT NULL,  -- website, resend, flexmail, tracardi, support, crm
    source_event_id VARCHAR(100),
    occurred_at TIMESTAMP NOT NULL,
    event_value NUMERIC,
    attributes JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (occurred_at);

CREATE INDEX idx_event_facts_uid ON event_facts(uid, occurred_at DESC);
CREATE INDEX idx_event_facts_org ON event_facts(organization_uid, occurred_at DESC);
CREATE INDEX idx_event_facts_type ON event_facts(event_type, occurred_at DESC);
```

### 3.5 Profile Traits

Durable analytical traits used by the chatbot and canonical segments.

```sql
CREATE TABLE profile_traits (
    trait_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL,
    trait_name VARCHAR(100) NOT NULL,
    trait_value_text TEXT,
    trait_value_number NUMERIC,
    trait_value_boolean BOOLEAN,
    confidence DECIMAL(5, 4),
    source_system VARCHAR(50) NOT NULL,   -- intelligence_layer, tracardi_projection, batch_model
    source_reference VARCHAR(200),
    effective_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_profile_traits_uid_name ON profile_traits(uid, trait_name, effective_at DESC);
CREATE INDEX idx_profile_traits_name ON profile_traits(trait_name, effective_at DESC);
```

### 3.6 AI Decisions

Explicit provenance for AI-enriched tags and recommendations.

```sql
CREATE TABLE ai_decisions (
    ai_decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL,
    decision_type VARCHAR(100) NOT NULL,      -- tag_assignment, nba, classification
    decision_name VARCHAR(100) NOT NULL,      -- pref_contact_morning, interest_low_maintenance
    decision_value TEXT,
    confidence DECIMAL(5, 4),
    source_system VARCHAR(50) NOT NULL,       -- intelligence_layer
    source_content_hash VARCHAR(128),
    model_name VARCHAR(100),
    model_version VARCHAR(100),
    decided_at TIMESTAMP NOT NULL,
    explanation JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ai_decisions_uid ON ai_decisions(uid, decided_at DESC);
CREATE INDEX idx_ai_decisions_name ON ai_decisions(decision_name, decided_at DESC);
```

### 3.7 Consent Ledger

Immutable consent and suppression events by UID and purpose.

```sql
CREATE TABLE consent_events (
    consent_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL,
    purpose VARCHAR(100) NOT NULL,            -- marketing_email, tracking, sms, etc.
    status VARCHAR(50) NOT NULL,              -- granted, revoked, suppressed
    lawful_basis VARCHAR(50),
    source_system VARCHAR(50) NOT NULL,
    source_record_id VARCHAR(100),
    event_at TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_consent_events_uid ON consent_events(uid, purpose, event_at DESC);
```

### 3.7.1 Delivery Resolution Audit

When a downstream campaign or operational send resolves private contact coordinates at activation time, record the authorized resolution event without copying the raw destination into general-purpose analytical logs.

```sql
CREATE TABLE pii_resolution_audit (
    pii_resolution_audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL,
    purpose VARCHAR(100) NOT NULL,           -- marketing_send, support_callback, invoice_delivery
    destination_type VARCHAR(50) NOT NULL,   -- email, phone, address
    resolver_system VARCHAR(50) NOT NULL,    -- teamleader, exact, controlled_api
    resolved_by VARCHAR(100),
    workflow_reference VARCHAR(200),
    approved_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pii_resolution_audit_uid
    ON pii_resolution_audit(uid, approved_at DESC);
```

### 3.8 Canonical Segments

Canonical segment logic belongs here, not only in Tracardi.

```sql
CREATE TABLE segment_definitions (
    segment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_key VARCHAR(100) NOT NULL UNIQUE,
    segment_name VARCHAR(200) NOT NULL,
    description TEXT,
    definition_type VARCHAR(50) NOT NULL,     -- sql, metadata, rule_graph
    definition_sql TEXT,
    definition_json JSONB,
    owner VARCHAR(100),
    refresh_schedule VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE segment_memberships (
    segment_id UUID NOT NULL REFERENCES segment_definitions(segment_id) ON DELETE CASCADE,
    uid VARCHAR(100) NOT NULL,
    calculated_at TIMESTAMP NOT NULL,
    membership_reason JSONB,
    projected_to_tracardi BOOLEAN DEFAULT FALSE,
    projected_at TIMESTAMP,
    PRIMARY KEY (segment_id, uid)
);

CREATE INDEX idx_segment_memberships_uid ON segment_memberships(uid, calculated_at DESC);
```

### 3.9 Projection State

Track what has been projected into Tracardi and other downstream systems.

```sql
CREATE TABLE activation_projection_state (
    projection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL,
    target_system VARCHAR(50) NOT NULL,       -- tracardi, resend, flexmail
    projected_entity_type VARCHAR(50) NOT NULL,
    projected_entity_key VARCHAR(100) NOT NULL,
    projection_hash VARCHAR(128),
    projection_status VARCHAR(50) NOT NULL,
    projected_at TIMESTAMP,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (target_system, projected_entity_type, projected_entity_key)
);
```

### 3.10 Audit Log

Record reads, mutations, tool actions, and downstream activations.

```sql
CREATE TABLE audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actor_type VARCHAR(50),
    actor_id VARCHAR(100),
    request_id VARCHAR(100),
    correlation_id VARCHAR(100),
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    action_type VARCHAR(50),
    action_status VARCHAR(20),
    details JSONB DEFAULT '{}'::jsonb
) PARTITION BY RANGE (event_timestamp);
```

## 4. Semantic Views And Materialized Aggregates

The chatbot should query stable views or parameterized query templates rather than raw table sprawl.

Recommended outputs:

- `mv_engagement_30d`
- `mv_last_touch_by_uid`
- `mv_segment_ready_organizations`
- `vw_chatbot_company_360`
- `vw_marketing_eligibility`

Example:

```sql
CREATE MATERIALIZED VIEW mv_engagement_30d AS
SELECT
    uid,
    COUNT(*) FILTER (WHERE event_type IN ('email.opened', 'email.clicked')) AS email_engagement_events_30d,
    MAX(occurred_at) AS last_event_at
FROM event_facts
WHERE occurred_at >= NOW() - INTERVAL '30 days'
GROUP BY uid;

CREATE UNIQUE INDEX idx_mv_engagement_30d_uid ON mv_engagement_30d(uid);
```

## 5. Chatbot Query Contract

Production flow:

1. user asks a question in natural language
2. LLM classifies intent and extracts filters
3. application maps intent to an approved SQL template or parameterized builder
4. PostgreSQL returns authoritative results
5. LLM summarizes or explains the result

The chatbot must not rely on:

- direct Tracardi queries for authoritative analytics
- free-form unvalidated SQL generation
- segment logic that exists only in Tracardi

## 6. Reverse Sync And Projection Rules

1. Event streams may enter Tracardi first for operational speed.
2. If the resulting tag, score, or audience state matters analytically, mirror it into PostgreSQL with provenance.
3. Campaign engagement writes back to PostgreSQL first, then optionally updates Tracardi.
4. Projection state must be traceable and retryable.

## 7. Explicit Non-Canonical Patterns

The following patterns are not canonical for production:

- storing private emails or phone numbers directly in PostgreSQL core intelligence tables without an explicit approved design change
- storing raw private message bodies in Tracardi
- treating Tracardi as the only durable home for analytical tags
- defining canonical segments only in Tracardi
- using Elasticsearch as the primary analytical query plane for the chatbot
