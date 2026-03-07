# CDP_Merged Architecture Roadmap

**Date:** 2026-03-01  
**Status:** Phase 2 In Progress (Critical Bug), Tracardi Deferred  
**Decision:** Complete data layer before deploying CDP hub

---

## Executive Summary

This document outlines the optimal path for the CDP_Merged project, addressing the current technical challenges and defining the phased approach to delivery.

### Current State
- ✅ **1,813,016 companies imported** to PostgreSQL
- 🔄 **Phase 2 enrichment** in progress (CBE integration)
- 🔴 **Critical bug:** Streaming exit issue blocking progress
- ⏸️ **Tracardi deferred** until after enrichment completes

### Key Decision
**Defer Tracardi deployment until Phase 2 enrichment is complete.**

Rationale:
1. Fix one critical bug at a time
2. Enriched data is required before intelligence is useful
3. Cost savings during development (€13/mo vs €48/mo)
4. Simpler architecture during active development

---

## Phase 1: Data Layer (Current - COMPLETE)

### What Was Built

```yaml
Infrastructure:
  - Azure PostgreSQL (B1ms): "1.8M companies stored"
  - Azure Event Hub: "Event streaming ready"
  - Optimized indexes: "10 indexes for fast queries"
  
Data Import:
  - KBO extraction: "10 CSV files processed"
  - Streaming importer: "Memory-efficient (10MB vs 500MB)"
  - Result: "1,813,016 companies imported"
```

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  DATA LAYER (Complete)                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  KBO CSV Files (10 files, 2GB+)                             │
│       │                                                     │
│       ▼                                                     │
│  Streaming Parser (10MB memory)                             │
│       │                                                     │
│       ▼                                                     │
│  PostgreSQL (1,813,016 companies)                           │
│       • companies table                                     │
│       • contact_persons table                               │
│       • Optimized indexes                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 2: Enrichment (Current - BLOCKED)

### The Problem

**Bug:** Phase 2 enrichment exits cleanly after ~500-1000 records.

**Impact:** Cannot complete CBE integration for 1.8M companies.

**Symptoms:**
- Exit code 0 (clean exit, not crash)
- Auto-restart wrapper keeps it running
- Very slow progress (2.6% after 1+ hour)
- Checkpoint file shows incremental progress

### What Should Happen

```
┌─────────────────────────────────────────────────────────────┐
│  ENRICHMENT PIPELINE (Expected)                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PostgreSQL (1.8M companies)                                │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Phase 1: Contact Validation                        │   │
│  │  • Validate email formats                           │   │
│  │  • Validate phone numbers                           │   │
│  └─────────────────────────────────────────────────────┘   │
│       │ ✅ COMPLETE                                       │
│       ▼                                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Phase 2: CBE Integration                           │   │
│  │  • Fetch industry classification                    │   │
│  │  • Company size estimates                           │   │
│  │  • Legal form details                               │   │
│  └─────────────────────────────────────────────────────┘   │
│       │ 🔄 BLOCKED (46,500 / 1,813,016)                   │
│       ▼                                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Phase 3-6: Geocoding, AI, Websites, etc.           │   │
│  └─────────────────────────────────────────────────────┘   │
│       │ 📋 PENDING                                        │
│       ▼                                                     │
│  PostgreSQL (1.8M ENRICHED companies)                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### What Actually Happens

```
┌─────────────────────────────────────────────────────────────┐
│  ENRICHMENT PIPELINE (Actual - Buggy)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PostgreSQL (1.8M companies)                                │
│       │                                                     │
│       ▼                                                     │
│  run_phase_streaming()                                      │
│       │                                                     │
│       ├── Fetch batch of 25                                 │
│       ├── Enrich profiles                                   │
│       ├── Update PostgreSQL                                 │
│       ├── Save checkpoint                                   │
│       └── ❌ EXIT CLEANLY (why?)                            │
│                                                             │
│  Auto-restart wrapper detects exit                          │
│       │                                                     │
│       └── Restart from checkpoint                           │
│                                                             │
│  Result: Very slow progress (500-1000 records per run)      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Investigation Plan

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Add debug logging to `run_phase_streaming()` | Identify exact exit point |
| 2 | Check `total_matches` calculation | Verify limit logic |
| 3 | Test with `--dry-run` | See if bug persists without DB writes |
| 4 | Test with larger batch size | Rule out batch-related issues |
| 5 | Check checkpoint file handling | Verify offset persistence |

### Files Involved

- `src/enrichment/postgresql_pipeline.py` - `run_phase_streaming()` method
- `src/enrichment/cbe_integration.py` - CBE enricher
- `scripts/enrich_profiles.py` - CLI entry point
- `run_phase2.sh` - Auto-restart wrapper

---

## Phase 3: Event Infrastructure (PENDING)

### What Will Be Built

After Phase 2 completes:

```yaml
Event Sources:
  Teamleader:
    webhook: /webhook/teamleader
    events: [contact.created, contact.updated, deal.won]
  Brevo:
    webhook: /webhook/brevo
    events: [delivered, opened, clicked, bounced]
  Website:
    endpoint: /webhook/website
    events: [page_view, form_submit, download]

Identity Resolution:
  - Teamleader ID → KBO number
  - Email domain → Company
  - KBO number → UID
```

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  EVENT LAYER (Pending)                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Teamleader ──┐                                             │
│  Brevo ───────┼──► Azure Event Hub ──► Azure Functions      │
│  Website ─────┘       (queue)            (process)          │
│                                                │            │
│                                                ▼            │
│                                        PostgreSQL           │
│                                        (event_archive)      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 4: Intelligence Layer (PENDING)

### What Will Be Built

```yaml
Real-Time Scoring:
  email_opened: +2 points
  email_clicked: +5 points
  page_view: +1 point
  form_submit: +10 points
  decay: -5% per day of inactivity

Lead Temperature:
  hot: "> 50 points"
  warm: "25-50 points"
  lukewarm: "10-25 points"
  cold: "< 10 points"

Contact Time Analysis:
  morning: "06:00-09:00"
  mid_morning: "09:00-12:00"
  lunch: "12:00-14:00"
  afternoon: "14:00-17:00"
  evening: "17:00-20:00"

Interest Detection:
  keywords:
    "onderhoud": interest_maintenance
    "prijs/kost": interest_pricing
    "support/help": interest_support
    "training/opleiding": interest_training
    "cloud": interest_cloud
    "security/beveiliging": interest_security
```

---

## Phase 5: Workflow Engine (PENDING)

### What Will Be Built

```yaml
Hot Lead Alert:
  trigger: "engagement_score > 50 AND lead_temperature == hot"
  action:
    - send_slack: "#sales"
    - trigger_brevo: "hot_lead_sequence"
  cooldown: "7 days"

Morning Person Follow-Up:
  trigger: "preferred_contact_time == morning AND days_since_contact > 7"
  schedule: "07:00 weekdays"
  action:
    - trigger_brevo: "morning_appointment_offer"
    - suggest_time: "08:00"

Re-Engagement Campaign:
  trigger: "inactivity > 30 days AND previous_score > 20"
  action:
    - add_tag: "re_engagement_candidate"
    - trigger_brevo: "win_back_001"
```

---

## Phase 6: Tracardi CDP Hub (DEFERRED)

### When to Deploy

**Trigger:** Phase 2 enrichment complete AND need for:
- Real-time workflows
- UID-based anonymization
- Intelligence layer
- 360° profile view

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  COMPLETE ARCHITECTURE (With Tracardi)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────┐     ┌─────────────────────────────┐   │
│  │  PostgreSQL         │     │  Tracardi (CDP Hub)         │   │
│  │  (1.8M profiles)    │     │  (10K active profiles)      │   │
│  │                     │◀────│  • Event aggregation        │   │
│  │  • Full KBO data    │     │  • Identity resolution      │   │
│  │  • Historical data  │     │  • Intelligence Layer       │   │
│  │  • Enrichment data  │     │  • Workflow engine          │   │
│  │  • Analytics        │     │  • UID anonymization        │   │
│  └─────────────────────┘     └──────────────┬──────────────┘   │
│           ▲                                  │                  │
│           │                                  │                  │
│           │         ┌────────────────────────┘                  │
│           │         │                                           │
│           │         ▼                                           │
│           │  ┌─────────────────────┐                           │
│           │  │  Azure Event Hub    │                           │
│           │  │  (Event streaming)  │                           │
│           │  └─────────────────────┘                           │
│           │         ▲                                           │
│           │         │                                           │
│  ┌────────┴─────────┴─────────────────────────┐                │
│  │  ACTIVATION LAYER                          │                │
│  │  • Brevo (email/SMS)                       │                │
│  │  • Slack (sales alerts)                    │                │
│  │  • WhatsApp Business                       │                │
│  │  • Teamleader (tasks)                      │                │
│  └────────────────────────────────────────────┘                │
│                                                                 │
│  Data Flow:                                                     │
│  1. Events → Event Hub → Tracardi (real-time)                  │
│  2. Tracardi syncs to PostgreSQL (every 15 min)                │
│  3. Activation queries Tracardi for UID → PII lookup           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Architecture

| Component | Responsibility | Why Separate? |
|-----------|----------------|---------------|
| PostgreSQL | Long-term storage, analytics | Handles 1.8M records efficiently |
| Tracardi | Real-time processing, workflows | Designed for event streaming |
| Event Hub | Event ingestion buffer | Decouples sources from processing |
| Activation | PII handling | Privacy compliance |

### Cost Impact

| Phase | Monthly Cost | Components |
|-------|--------------|------------|
| Current (Phase 2) | €33 | PostgreSQL + Event Hub |
| With Tracardi | €90-110 | + Tracardi VM + OpenAI |

---

## Decision Log

### Decision 1: Defer Tracardi

**Date:** 2026-03-01  
**Status:** Approved  

**Context:**
- Phase 2 has critical bug blocking progress
- Adding Tracardi would add complexity
- Enriched data required before intelligence useful

**Decision:**
Complete Phase 2 enrichment BEFORE deploying Tracardi.

**Consequences:**
- ✅ Simpler debugging
- ✅ Lower cost during development
- ✅ Clear focus on data quality first
- ❌ Delayed real-time workflows
- ❌ No UID anonymization yet

### Decision 2: Keep Auto-Restart Wrapper

**Date:** 2026-03-01  
**Status:** Temporary workaround  

**Context:**
- Phase 2 exits cleanly every 30-60 seconds
- Auto-restart wrapper keeps progress moving
- Very slow but functional

**Decision:**
Keep using `run_phase2.sh` until bug is fixed.

---

## Success Criteria

### Phase 2 Complete When:
- [ ] Bug fixed: Process runs continuously without exiting
- [ ] 1,813,016 profiles enriched with CBE data
- [ ] >95% success rate
- [ ] All phases (1-6) complete

### Phase 6 (Tracardi) Deploy When:
- [ ] Phase 2 complete
- [ ] Event sources ready (Teamleader, Brevo webhooks)
- [ ] Use case defined (hot lead alerts, etc.)
- [ ] Budget approved (€35/mo additional)

---

## Next Actions

### Immediate (This Week)
1. **Fix Phase 2 streaming bug** (Critical)
2. Complete CBE integration
3. Run remaining enrichment phases

### Short-term (Next 2 Weeks)
1. Deploy event webhooks (Teamleader, Brevo)
2. Build identity resolution
3. Implement scoring engine

### Medium-term (Next Month)
1. Deploy Tracardi (if needed)
2. Build workflow engine
3. Full integration testing

---

## Appendix: Current vs. Future Architecture

### Current (Simplified)
```
Sources → Event Hub → PostgreSQL → Activation
```

### Future (Full CDP)
```
Sources → Event Hub → Tracardi → PostgreSQL → Activation
                     ↓
              Intelligence Layer
```

The difference: Tracardi adds real-time processing, workflows, and intelligence between events and storage.
