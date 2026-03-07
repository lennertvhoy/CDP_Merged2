# PostgreSQL ↔ Tracardi Projection Contract

**Status:** DRAFT - Ready for Review  
**Date:** 2026-03-03  
**Version:** 1.0  
**Platform:** Azure (PostgreSQL + Tracardi on VMs)

---

## 1. Purpose

This document defines the formal contract between PostgreSQL (customer-intelligence and analytical truth layer) and Tracardi (projected activation runtime). It specifies:

- Which data flows from PostgreSQL → Tracardi (projection)
- Which data flows from Tracardi → PostgreSQL (writeback)
- When and how profiles are created in Tracardi
- How identity reconciliation is handled
- How PII boundaries are maintained

---

## 2. Core Principles

### 2.1 Write Order Rule
**ALL mutating actions write to PostgreSQL first, then emit operational updates to Tracardi.**

```
User/Agent Action → PostgreSQL (canonical update) → Event Emitter → Tracardi (projection)
                           ↓
                    Audit Log + Provenance
```

### 2.2 Lazy Profile Creation
Tracardi profiles are created **on-demand** or **lazily** rather than bulk-provisioned:

| Trigger | Action |
|---------|--------|
| Event ingestion for unknown UID | Create minimal profile with UID reference |
| Segment activation | Create profiles for segment members |
| Workflow target | Create profile when workflow is triggered |
| Manual operator lookup | Create profile on first chatbot-initiated action |

### 2.3 PII Boundary
- **PostgreSQL stores:** UIDs, business data, derived facts, scores, tags
- **Tracardi stores:** UID-linked projections, operational state
- **PII resolution:** Only at authorized activation time from source systems

---

## 3. PostgreSQL → Tracardi Projection

### 3.1 What Gets Projected

| Data Type | Projection Trigger | Tracardi Destination | Notes |
|-----------|-------------------|---------------------|-------|
| **Core Identity** | Profile creation | `profile.id`, `profile.ids` | UID as primary key |
| **Business Traits** | Enrichment completion, trait update | `profile.traits.business.*` | Public company data only |
| **NACE/Industry** | Enrichment completion | `profile.traits.industry.*` | For segmentation |
| **Contact Status** | Validation completion | `profile.traits.contact.*` | Has_email, has_phone flags (not the actual values) |
| **AI Tags** | AI decision recorded | `profile.traits.ai.*` | Derived classifications |
| **Segment Membership** | Segment calculation | `profile.segments` | Projected from canonical segment store |
| **Consent State** | Consent event | `profile.consents` | Marketing eligibility flags |

### 3.2 What Does NOT Get Projected

| Data Type | Stays In | Reason |
|-----------|----------|--------|
| Email addresses | PostgreSQL + Source Systems | PII boundary |
| Phone numbers | PostgreSQL + Source Systems | PII boundary |
| Raw PII | Source Systems | Privacy compliance |
| Full AI decision provenance | PostgreSQL `ai_decisions` table | Audit trail |
| Historical trait versions | PostgreSQL `profile_traits` table | Analytics |
| Canonical segment definitions | PostgreSQL `segment_definitions` table | Source of truth |

### 3.3 Projection Process

```python
# Pseudocode for projection
async def project_to_tracardi(uid: str, projection_type: str):
    # 1. Fetch canonical data from PostgreSQL
    org = await postgresql.get_organization(uid)
    traits = await postgresql.get_traits(uid)
    segments = await postgresql.get_segment_memberships(uid)
    consent = await postgresql.get_consent_state(uid)
    
    # 2. Build PII-light projection payload
    payload = {
        "id": uid,
        "traits": {
            "business": {
                "legal_name": org.legal_name,
                "legal_form": org.legal_form,
                "nace_code": org.nace_code,
                "city": org.city,
                "has_email": org.main_email is not None,
                "has_phone": org.main_phone is not None,
            },
            "ai": {t.trait_name: t.trait_value for t in traits},
            "segments": [s.segment_key for s in segments],
            "consent": consent.flags,
        }
    }
    
    # 3. Send to Tracardi
    result = await tracardi.import_profiles([payload])
    
    # 4. Record projection state in PostgreSQL
    await postgresql.record_projection_state(
        uid=uid,
        target_system="tracardi",
        projected_entity_type="profile",
        projected_entity_key=uid,
        projection_hash=hash(payload),
        status="success"
    )
```

### 3.4 Projection Frequency

| Data Type | Projection Schedule |
|-----------|---------------------|
| New enriched profiles | Real-time on enrichment completion |
| Trait updates | Real-time on trait change |
| Segment memberships | Batch (hourly) or on-demand for activation |
| Consent changes | Real-time on consent event |

---

## 4. Tracardi → PostgreSQL Writeback

### 4.1 What Gets Written Back

| Data Type | Source | PostgreSQL Destination | Notes |
|-----------|--------|------------------------|-------|
| **Event facts** | Tracardi events | `event_facts` table | Normalized behavioral data |
| **Operational tags** | Workflow outputs | `profile_traits` table | With provenance |
| **Scores** | Real-time scoring | `profile_traits` table | As traits with confidence |
| **Workflow outcomes** | Workflow results | `event_facts` + `ai_decisions` | Action taken, result |
| **Campaign engagement** | Email/SMS events | `event_facts` table | Opens, clicks, bounces |

### 4.2 Writeback Process

```python
# Pseudocode for writeback
async def writeback_from_tracardi(event: dict):
    # 1. Normalize event to canonical format
    fact = EventFact(
        uid=event.profile_id,
        event_type=event.type,
        event_source="tracardi",
        occurred_at=event.timestamp,
        attributes=event.properties,
    )
    
    # 2. Write to PostgreSQL first (canonical truth)
    await postgresql.insert_event_fact(fact)
    
    # 3. If AI-relevant, record decision provenance
    if event.type in AI_DECISION_EVENTS:
        decision = AIDecision(
            uid=event.profile_id,
            decision_type=event.properties.get("decision_type"),
            decision_name=event.properties.get("decision_name"),
            decision_value=event.properties.get("decision_value"),
            confidence=event.properties.get("confidence"),
            source_system="tracardi_projection",
            decided_at=event.timestamp,
        )
        await postgresql.insert_ai_decision(decision)
    
    # 4. Update trait if analytically relevant
    if event.type in TRAIT_GENERATING_EVENTS:
        trait = ProfileTrait(
            uid=event.profile_id,
            trait_name=event.properties.get("trait_name"),
            trait_value=event.properties.get("trait_value"),
            source_system="tracardi_projection",
            effective_at=event.timestamp,
        )
        await postgresql.insert_or_update_trait(trait)
```

---

## 5. Profile Lifecycle

### 5.1 Profile Creation Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Trigger: Event/Action for UID not in Tracardi              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Check PostgreSQL for UID existence                      │
│     - If not found: Reject or queue for identity resolution │
│     - If found: Continue                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Build minimal projection from PostgreSQL                │
│     - Core business traits (PII-light)                      │
│     - Current segment memberships                           │
│     - Consent flags                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Create profile in Tracardi                              │
│     - Store Tracardi profile ID in source_identity_links    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Record projection state                                 │
│     - activation_projection_state table                     │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Profile Update Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Trigger: Enrichment, trait update, or segment change       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Update PostgreSQL (canonical truth)                     │
│     - Update organization record                            │
│     - Insert new trait version                              │
│     - Update segment membership                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Check if profile exists in Tracardi                     │
│     - If not: Skip (will be created on next activation)     │
│     - If yes: Continue                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Calculate delta and project if significant              │
│     - Compare hash with last projection                     │
│     - Project only changed fields                           │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Profile Merge/Split Handling

When a source system merges or splits records:

```
┌─────────────────────────────────────────────────────────────┐
│  Source System Merge Event                                  │
│  (e.g., Teamleader merges duplicate companies)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Record merge in identity_merge_events                   │
│     - losing_uid, surviving_uid                             │
│     - status: pending                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. PostgreSQL: Reconcile UID bridge                        │
│     - Update source_identity_links                          │
│     - Merge traits (surviving record wins)                  │
│     - Recalculate segments                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Tracardi: Repair downstream state                       │
│     - Delete losing profile                                 │
│     - Update surviving profile traits                       │
│     - Rebuild segment memberships                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Mark merge as reconciled                                │
│     - identity_merge_events.reconciliation_status = done    │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Implementation Checklist

### 6.1 Current State (as of 2026-03-03)

| Component | Status | Notes |
|-----------|--------|-------|
| PostgreSQL schema | ✅ Exists | `companies` table with sync_status |
| Enrichment pipeline | ✅ Running | CBE phase in progress |
| Tracardi client | ✅ Exists | `src/services/tracardi.py` |
| Lazy profile creation | ⚠️ Partial | Manual triggers only |
| Projection service | ❌ Missing | Needs implementation |
| Writeback service | ❌ Missing | Needs implementation |
| Identity merge handling | ❌ Missing | Schema exists, no implementation |
| Projection state tracking | ❌ Missing | Table exists, not used |

### 6.2 Required Implementation

1. **Projection Service** (`src/services/projection.py`)
   - Project profiles from PostgreSQL to Tracardi
   - Handle delta detection
   - Record projection state

2. **Writeback Service** (`src/services/writeback.py`)
   - Poll Tracardi events or use webhooks
   - Normalize and write to PostgreSQL
   - Handle trait extraction

3. **Identity Reconciliation** (`src/services/identity_reconciliation.py`)
   - Process identity_merge_events
   - Repair downstream Tracardi state
   - Maintain UID bridge integrity

4. **Segment Projection** (`src/services/segment_projection.py`)
   - Calculate segments in PostgreSQL
   - Project membership to Tracardi
   - Track projection state

---

## 7. API Contract

### 7.1 Projection API

```python
class ProjectionService:
    async def project_profile(self, uid: str) -> ProjectionResult:
        """Project a single profile to Tracardi."""
        
    async def project_batch(self, uids: list[str]) -> BatchProjectionResult:
        """Project multiple profiles."""
        
    async def project_segment(self, segment_key: str) -> SegmentProjectionResult:
        """Project all members of a segment."""
        
    async def get_projection_state(self, uid: str) -> ProjectionState:
        """Get last projection state for a UID."""
```

### 7.2 Writeback API

```python
class WritebackService:
    async def process_events(self, since: datetime) -> WritebackResult:
        """Process Tracardi events and write back to PostgreSQL."""
        
    async def handle_webhook(self, event: dict) -> WritebackResult:
        """Handle real-time event webhook from Tracardi."""
        
    async def sync_traits(self, uid: str) -> TraitSyncResult:
        """Sync traits from Tracardi to PostgreSQL."""
```

---

## 8. Monitoring and Observability

### 8.1 Key Metrics

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Projection lag | `activation_projection_state` | > 1 hour |
| Writeback lag | `event_facts` vs Tracardi | > 5 minutes |
| Failed projections | `activation_projection_state` | > 1% failure rate |
| Pending merges | `identity_merge_events` | > 10 pending |
| Profile count drift | PostgreSQL vs Tracardi | > 5% difference |

### 8.2 Audit Requirements

All projection and writeback operations must log:
- Source UID
- Target system
- Operation type (project, writeback, merge)
- Timestamp
- Success/failure status
- Hash of projected data (for idempotency)

---

## 9. Decision Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-03-03 | Lazy profile creation vs bulk | Cost efficiency, only activate engaged profiles |
| 2026-03-03 | PostgreSQL first write rule | Maintain canonical truth, enable audit |
| 2026-03-03 | PII-light projection | Privacy compliance, source system remains PII owner |
| 2026-03-03 | Segment definitions in PostgreSQL | Source of truth for analytics and activation |

---

## 10. Related Documents

- [DATABASE_SCHEMA.md](./specs/DATABASE_SCHEMA.md) - Canonical schema specification
- [ARCHITECTURE_AZURE.md](./ARCHITECTURE_AZURE.md) - Overall architecture
- [AGENTS.md](../AGENTS.md) - Operating rules and verification policy
- [PROJECT_STATE.yaml](../PROJECT_STATE.yaml) - Current implementation state
