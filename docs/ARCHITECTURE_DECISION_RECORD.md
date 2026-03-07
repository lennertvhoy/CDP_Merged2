# Architecture Decision Records (ADRs)

**Project:** CDP_Merged
**Last Updated:** 2026-03-03

This document records significant architectural decisions made during the CDP_Merged project, along with their context and consequences.

## Current Reading Rule

Read ADRs as a decision history, not as a substitute for current implementation verification. If an older ADR conflicts with current code or current root workflow docs, verify implementation first and then reconcile the docs.

---

## ADR-008: Canonical Production Architecture Is PostgreSQL-First

### Status
**Accepted (Refined by ADR-009)** - 2026-03-03

### Context

The repo had drifted into multiple overlapping narratives:

1. PostgreSQL as the canonical profile store
2. Tracardi as a broad queryable profile system
3. Demo-oriented docs that still implied the chatbot could rely on Tracardi as the primary data plane

This created a critical ambiguity. By 2026-03-03, the local import evidence showed a completed KBO import into PostgreSQL with `1,940,603` rows, while the same run synced `0` profiles to Tracardi. At the same time, the chatbot search implementation still used Tracardi/TQL as the primary search backend.

### Decision

The canonical production architecture is:

- **Source systems** = PII and operational master truth
- **PostgreSQL** = customer-intelligence and analytical truth for master data copies, enrichment, analytics, identity mapping, consent/audit, and the chatbot query plane
- **Tracardi** = event ingestion, scoring, workflow automation, and activation layer
- **Chatbot** = PostgreSQL-first for authoritative counts, search, analytics, and 360 views; Tracardi only for workflow/action execution and recent operational context

### Consequences

**Positive:**
- Eliminates ambiguity about the truth layers
- Aligns the chatbot with the largest and richest dataset
- Preserves Tracardi where it adds value
- Supports privacy-by-design and cross-system UID mapping more cleanly

**Negative:**
- Requires a deliberate refactor of the current chatbot retrieval path
- Forces tighter discipline around segment definition, projection, and synchronization
- Invalidates some older demo-oriented assumptions in current docs and handoffs

### Implementation Rule

No current doc should describe:

- Tracardi as the primary source of truth
- Tracardi as the canonical broad historical query plane
- the chatbot as Tracardi-first for authoritative answers

If implementation temporarily diverges from this target, the gap must be documented explicitly in current root docs.

---

## ADR-009: Clarify Truth Layers, Deterministic Querying, and Tracardi Projection Boundaries

### Status
**Accepted** - 2026-03-03

### Context

The project has a strict privacy-by-design goal:

- source systems hold PII
- Tracardi should work primarily on UID-linked operational state
- the AI intelligence layer may derive tags from sensitive upstream content

That introduced a deeper architectural risk. If KBO/master data stays in PostgreSQL while AI tags and behavioral state live only in Tracardi, the chatbot ends up with a split brain. It can either query PostgreSQL and miss important traits, or query Tracardi and miss the master-data joins.

The accepted production refinement on 2026-03-03 made the correction explicit: Tracardi should be treated as a real-time runtime and projection layer, not as the analytical backend for the chatbot.

### Decision

The refined production architecture is:

- **Source systems** = PII and operational master truth
- **PostgreSQL** = customer-intelligence and analytical truth
- **Tracardi** = projected activation runtime

Additional implementation rules:

1. AI-derived tags, scores, and analytically relevant behavioral state must be durable PostgreSQL facts with provenance.
2. Segment definitions must be canonical in SQL or explicit metadata outside Tracardi.
3. The chatbot must use deterministic PostgreSQL-backed tools for authoritative answers.
4. The LLM should perform intent classification, filter extraction, clarification, and summarization, not uncontrolled production SQL generation.
5. Mutating actions must write to PostgreSQL first, then emit operational updates to Tracardi or downstream systems.
6. Prefer lazy or need-based Tracardi profile creation for active UIDs unless a verified requirement justifies broader projection.

### Consequences

**Positive:**
- Removes the split-brain risk between KBO/master data and AI/behavioral traits
- Preserves privacy-by-design more cleanly
- Gives the chatbot one analytical query plane
- Makes segments and scores auditable and reproducible

**Negative:**
- Requires explicit reverse-sync or dual-projection design for analytically relevant Tracardi state
- Requires additional PostgreSQL schema work for traits, AI decisions, and segment provenance
- Prevents shortcuts where the chatbot asks Tracardi directly for broad analytical answers

### Operational Rule

Do not call a design "production-ready" if:

- the chatbot still depends on Tracardi for authoritative counts or broad filtering
- analytically relevant tags live only in Tracardi
- segment logic exists only inside Tracardi
- mutating actions bypass PostgreSQL as the canonical write path

---

## ADR-001: Migration from Tracardi-Only to Hybrid Architecture

### Status
**Accepted (Historical; partially superseded by ADR-008)** - Implemented 2026-02-28

### Context
The original CDP_Merged architecture (v1.0) used Tracardi as the sole data platform for all customer profiles. Tracardi was deployed on a Standard_B2s VM (2 vCPU, 4GB RAM) with Elasticsearch as the backend database.

**Problems encountered:**
1. Tracardi crashed when attempting to load 516K KBO profiles
2. Elasticsearch ran out of memory with large datasets
3. System became unresponsive during enrichment pipeline runs
4. Query performance degraded significantly beyond 10K profiles

The system was fundamentally unable to handle the scale required for the Belgian KBO dataset (516,382 companies).

### Decision
Migrate to a **Hybrid Architecture** with:
- **PostgreSQL** as the primary data store (516K+ profiles)
- **Tracardi** as an operational event/workflow layer

### Consequences

**Positive:**
- ✅ Can handle 516K profiles (tested and working)
- ✅ 46% cost reduction (€26/mo vs €48/mo)
- ✅ Better query performance on historical data
- ✅ Separation of concerns (storage vs real-time processing)
- ✅ Can scale PostgreSQL independently of Tracardi

**Negative:**
- ❌ Added complexity (two systems to maintain)
- ❌ Need sync job between Tracardi and PostgreSQL
- ❌ Potential sync lag (15-minute window)
- ❌ Need to update all documentation and code

### Alternatives Considered

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| **Larger Tracardi VM** (B4ms) | Simple migration | €70/mo, still might crash, no guarantee of scale | ❌ Rejected |
| **Apache Unomi** | Designed for scale | Java stack (team unfamiliar), migration effort | ❌ Rejected |
| **RudderStack** | Good integrations | More of a data router than full CDP | ❌ Rejected |
| **PostgreSQL-only** | Simple, cheap | No real-time event processing | ❌ Rejected |
| **Hybrid (selected)** | Best of both worlds | Added complexity | ✅ **Accepted** |

### Implementation Notes
- Destroyed old Tracardi infrastructure (28 resources)
- Deployed new PostgreSQL instance (Standard_B1ms)
- Deployed minimal Tracardi (Standard_B1ms, MySQL only, no ES)
- Created PostgreSQL pipeline (asyncpg-based)
- Updated all environment configs

---

## ADR-002: PostgreSQL over Elasticsearch for Profile Storage

### Status
**Accepted** - Implemented 2026-02-28

### Context
The original architecture used Elasticsearch as the primary database for Tracardi. Elasticsearch is designed for search and analytics, not as a primary transactional datastore.

**Problems with Elasticsearch:**
1. High memory usage (crashed with 516K documents)
2. Complex query syntax (TQL) limited functionality
3. Schema migrations difficult
4. No ACID transactions
5. Backup/restore complexity

PostgreSQL, while not a "search engine," has:
- Full-text search capabilities (pg_trgm, though not enabled in Azure B1ms)
- ACID transactions
- Better memory efficiency
- Familiar SQL interface
- Native JSON support

### Decision
Use **PostgreSQL** as the primary profile store with:
- Relational schema for structured data (companies, contacts)
- JSONB columns for flexible enrichment data
- Standard SQL for queries (easier for AI chatbot)

### Consequences

**Positive:**
- ✅ Handles 516K profiles with B1ms SKU (1 vCPU, 2GB RAM)
- ✅ Simple SQL queries (better for AI NL→SQL translation)
- ✅ ACID transactions for data integrity
- ✅ Familiar tooling (psql, ORMs)
- ✅ Better backup/restore options

**Negative:**
- ❌ Full-text search less powerful than Elasticsearch
- ❌ No built-in faceted search (would need Azure Cognitive Search addon)
- ❌ Slower for complex aggregations (mitigated by materialized views)

### Mitigations
- For simple search: Use ILIKE with trigram indexes (if pg_trgm enabled)
- For complex search: Add Azure Cognitive Search later if needed
- For aggregations: Pre-compute in materialized views or sync job

---

## ADR-003: Tracardi Role Redefinition (Event Hub)

### Status
**Accepted (Historical; refined by ADR-008)** - Implemented 2026-02-28

### Context
Originally, Tracardi was intended to be the "everything platform":
- Event ingestion
- Profile storage (516K profiles)
- Workflow engine
- Analytics
- Real-time personalization

This ambition exceeded its capabilities at our scale.

### Decision
Redefine Tracardi's role as an **Event Hub** only:
- **Does:** Event ingestion, identity resolution, real-time scoring, workflow triggers
- **Does NOT:** act as the canonical system of record or broad historical query plane
- **Operational projections only:** selected profiles, events, and workflow state needed for activation
- **Retention and operational limits:** implementation-specific and subject to current infrastructure verification

### Consequences

**Positive:**
- ✅ Tracardi operates within its capabilities
- ✅ Real-time processing still works
- ✅ Can handle event spikes (burstable B1ms)
- ✅ Workflow engine still functional

**Negative:**
- ❌ Historical queries must go to PostgreSQL
- ❌ Need sync job (added complexity)
- ❌ Potential data inconsistency during sync windows

### Implementation
- Deployed Tracardi with MySQL only (no Elasticsearch)
- Configured 30-day event retention policy
- Current repo audit did **not** find a live `scripts/sync_tracardi_to_postgres.py` file
- Current implementation direction uses PostgreSQL projection/writeback services plus webhook/runtime integration; any additional sync loop must be re-verified before being described as live

---

## ADR-004: Standard_B1ms SKU for Production

### Status
**Accepted (Historical capacity decision; verify against current infra before reuse)** - Implemented 2026-02-28

### Context
Azure offers multiple SKU tiers for VMs and databases. We needed to balance cost vs performance.

**Options considered:**
- **B1ms** (1 vCPU, 2GB RAM): €13/mo - Burstable, good for light workloads
- **B2s** (2 vCPU, 4GB RAM): €35/mo - More consistent performance
- **D2s_v3** (2 vCPU, 8GB RAM): €65/mo - General purpose
- **D4s_v3** (4 vCPU, 16GB RAM): €130/mo - High performance

### Decision
Use **Standard_B1ms** for both PostgreSQL and Tracardi in production.

**Rationale:**
- PostgreSQL B1ms handles 516K profiles (tested)
- Tracardi was treated as an operational layer rather than the canonical store
- Burstable credits handle traffic spikes
- 46% cost savings vs B2s approach

### Consequences

**Positive:**
- ✅ €26/mo total (affordable for KMO)
- ✅ Sufficient for current load
- ✅ Can upgrade later if needed

**Negative:**
- ⚠️ Burstable: Sustained high CPU will exhaust credits
- ⚠️ No redundancy (single instance)
- ⚠️ Limited to 2GB RAM (PostgreSQL must be tuned)

### Monitoring
- Alert if CPU credits exhausted
- Alert if sync lag > 30 minutes
- Plan upgrade path to B2s if growth exceeds capacity

---

## ADR-005: UID-Based Privacy Architecture

### Status
**Accepted** - Implemented from project start

### Context
GDPR compliance requires careful handling of personal data. We wanted a "privacy-by-design" approach.

**Requirements:**
- No direct PII (names, emails, phones) in CDP
- Ability to delete all data for a person (right to be forgotten)
- Audit trail of data access
- Data minimization

### Decision
Implement **UID-based architecture**:
- **Source Systems** (Teamleader, Brevo): Store PII
- **CDP (PostgreSQL)**: Store UID (Teamleader ID or KBO number) + behavioral data only
- **Tracardi**: Store events linked to UID
- **Activation**: Re-link UID to PII only when sending messages

### Example Flow
```
Teamleader:     David Mertens (david@acme.com) → UID: tl_9876
                      ↓
CDP PostgreSQL: UID: tl_9876, KBO: 0123456789, engagement_score: 75
                      ↓
Tracardi:       Event: "tl_9876 opened email at 08:15"
                      ↓
Activation:     Brevo looks up tl_9876 → david@acme.com, sends email
```

### Consequences

**Positive:**
- ✅ CDP contains no direct PII (reduces breach risk)
- ✅ Easy GDPR compliance: delete UID → all data gone
- ✅ Can share CDP data internally without privacy concerns
- ✅ Simplifies data retention policies

**Negative:**
- ❌ Need identity resolution layer (mapping PII ↔ UID)
- ❌ Slightly more complex queries (join with source systems for display)
- ❌ If source system deleted, can't resolve UID anymore

### Implementation
- All PostgreSQL tables use `kbo_number` or `source_id` as primary key
- No email, phone, or name columns (except for public KBO business names)
- Sync job updates engagement without exposing PII
- Chatbot queries return UIDs, display layer fetches PII from source APIs

---

## ADR-006: Python + AsyncIO for Data Pipeline

### Status
**Accepted** - Implemented 2026-02-27

### Context
The enrichment pipeline needs to process 516K profiles with multiple API calls per profile (geocoding, AI descriptions, CBE lookups).

**Requirements:**
- Handle 516K records
- Multiple external APIs (rate limited)
- Resume capability (checkpointing)
- Cost tracking

### Decision
Use **Python with AsyncIO** for the pipeline:
- `asyncpg` for PostgreSQL (async PostgreSQL driver)
- `aiohttp` for HTTP requests
- `asyncio.gather` for parallel processing
- Batch processing with checkpointing

### Consequences

**Positive:**
- ✅ High concurrency (100+ concurrent API calls)
- ✅ Efficient I/O utilization
- ✅ Familiar language (team knows Python)
- ✅ Rich ecosystem (asyncpg, pydantic, structlog)

**Negative:**
- ⚠️ Debugging async code harder than sync
- ⚠️ Need to handle backpressure (API rate limits)
- ⚠️ GIL limits CPU parallelism (but we're I/O bound)

### Alternatives
- **Apache Airflow**: Too heavy for current needs
- **Prefect**: Good, but adds dependency
- **Dagster**: Overkill for simple ETL
- **Go**: Faster, but team less familiar
- **Node.js**: Good async, but Python has better ML/AI libraries

---

## ADR-007: Azure-Only Cloud Strategy

### Status
**Accepted** - Ongoing

### Context
Decision needed on cloud provider for all infrastructure.

**Options:**
- AWS: Largest market share, most services
- GCP: Good AI/ML, competitive pricing
- Azure: Existing Microsoft ecosystem, GDPR compliance
- Multi-cloud: Avoid vendor lock-in, more complex

### Decision
Use **Microsoft Azure exclusively**.

**Rationale:**
- Existing Azure subscription and expertise
- Integration with Microsoft stack (Teams, Outlook, Entra ID)
- Strong GDPR compliance for EU data
- Azure OpenAI integration
- Belgium region available (West Europe)

### Consequences

**Positive:**
- ✅ Single billing/management portal
- ✅ Native Teams/Outlook integrations
- ✅ GDPR-compliant EU data centers
- ✅ Azure OpenAI (GPT-4o-mini) availability

**Negative:**
- ❌ Vendor lock-in (mitigated by open-source software)
- ❌ Some services more expensive than AWS
- ❌ Less third-party tooling than AWS

### Services Used
- Azure Database for PostgreSQL Flexible Server
- Azure Virtual Machines (Tracardi)
- Azure OpenAI Service
- Azure Monitor / Log Analytics
- Azure Key Vault (future)

---

## Summary of Key Decisions

| ADR | Decision | Status | Date |
|-----|----------|--------|------|
| ADR-001 | Hybrid Architecture (PostgreSQL + Tracardi) | ✅ Accepted | 2026-02-28 |
| ADR-002 | PostgreSQL over Elasticsearch | ✅ Accepted | 2026-02-28 |
| ADR-003 | Tracardi as Event Hub only | ✅ Accepted | 2026-02-28 |
| ADR-004 | Standard_B1ms SKU for production | ✅ Accepted | 2026-02-28 |
| ADR-005 | UID-based privacy architecture | ✅ Accepted | 2026-02-27 |
| ADR-006 | Python + AsyncIO for pipeline | ✅ Accepted | 2026-02-27 |
| ADR-007 | Azure-Only cloud strategy | ✅ Accepted | 2026-02-20 |

---

## Revision History

| Date | Changes | Author |
|------|---------|--------|
| 2026-02-28 | Initial ADR document created | Jarvis |
| 2026-02-28 | Added ADR-001, ADR-002, ADR-003, ADR-004 | Jarvis |
