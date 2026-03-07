# TASK: Align CDP_Merged Documentation with Hybrid Architecture

## Objective
Update all documentation, specs, and backlog to reflect the **Hybrid Architecture** (PostgreSQL + Minimal Tracardi) that replaces the original Tracardi-only design.

## Architecture Summary (The "New Truth")

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVENT SOURCES (Webhooks)                             │
│  Teamleader │ Brevo │ Website │ Exact/Autotask/Sharepoint                     │
└───────┬───────┴───────┬───────┴─────────────┬───────────────────────────────┘
        │               │                     │
        └───────────────┴─────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              MINIMAL TRACARDI (Event Hub - Max 10K active profiles)          │
│  • Event ingestion & validation                                              │
│  • Identity resolution (UID mapping)                                         │
│  • Real-time scoring (engagement, lead temp, churn risk)                     │
│  • Workflow triggers (if-this-then-that)                                     │
│  • 30-day event retention (auto-archive to PostgreSQL)                       │
│  VM: Standard_B1ms (€13/mo) - MySQL only, NO Elasticsearch                   │
└──────────────────┬──────────────────────────────┬───────────────────────────┘
                   │                              │
                   ▼                              ▼
┌──────────────────────────────────┐    ┌──────────────────────────────────────┐
│   POSTGRESQL (Source of Truth)   │    │      ACTIVATION LAYER                │
│  • 516K Company profiles (KBO)   │    │  • Brevo API (email/SMS)             │
│  • Full enrichment data (AI)     │◄───┤  • Slack webhooks (sales alerts)     │
│  • Historical events (archive)   │    │  • Teamleader API (tasks)            │
│  • Aggregated analytics          │    │  • Autotask API (tickets)            │
│  • Event sourcing log            │    │  • Azure Queue (async)               │
└──────────────────────────────────┘    └──────────────────────────────────────┘
                   ▲
                   │
┌──────────────────┴───────────────────────────────────────────────────────────┐
│                           AI CHATBOT INTERFACE                                │
│  • Natural language → SQL queries on PostgreSQL                               │
│  • Real-time scores from Tracardi (engagement, lead temperature)              │
│  • Recommendations based on combined data                                     │
└───────────────────────────────────────────────────────────────────────────────┘
```

## Files to Update

### 1. Architecture Documentation
**File:** `docs/ARCHITECTURE_AZURE.md`
**Changes:**
- [ ] Update diagram to show Hybrid architecture
- [ ] Clarify PostgreSQL = primary data store (516K profiles)
- [ ] Clarify Tracardi = event hub only (10K active)
- [ ] Add data flow: Source → Tracardi (events) → PostgreSQL (profiles) → Activation
- [ ] Update cost estimate: €26/mo (€13 PostgreSQL + €13 Tracardi B1ms)

### 2. Technical Briefing Alignment
**File:** `docs/PROMPT_HYBRID_ARCHITECTURE.md` (already created)
**New File:** `docs/ARCHITECTURE_DECISION_RECORD.md`
**Content:**
- [ ] ADR-001: Why we moved from Tracardi-only to Hybrid
- [ ] ADR-002: Why PostgreSQL over Elasticsearch for 516K profiles
- [ ] ADR-003: Tracardi role redefinition (event hub vs profile store)

### 3. Database Schema Documentation
**File:** `docs/specs/DATABASE_SCHEMA.md`
**Changes:**
- [ ] Document all tables: companies, contact_persons, interactions, event_archive
- [ ] Document enrichment columns: engagement_score, lead_temperature, etc.
- [ ] Document sync tables for Tracardi integration
- [ ] Add ERD diagram

### 4. API Specifications
**File:** `docs/specs/API_SPEC.md` (create if missing)
**Content:**
- [ ] Tracardi webhook endpoints (4 endpoints)
- [ ] PostgreSQL query API (for chatbot)
- [ ] Activation API (Brevo, Slack connectors)

### 5. BACKLOG.md Update
**File:** `BACKLOG.md`
**Structure:**

#### Phase 1: Infrastructure ✅ (In Progress)
- [x] Deploy PostgreSQL (Azure Database)
- [x] Create PostgreSQL schema with enrichment columns
- [x] Deploy minimal Tracardi VM (Standard_B1ms)
- [x] Configure Tracardi with MySQL (no ES)
- [x] Configure NSG for webhook endpoints
- [ ] Verify health checks for both systems

#### Phase 2: Data Layer (Next)
- [ ] Import KBO data (516K profiles) to PostgreSQL
- [ ] Run enrichment pipeline on all profiles
- [ ] Create event_archive table for Tracardi sync
- [ ] Test PostgreSQL → Tracardi connectivity

#### Phase 3: Event Ingestion (Priority: High)
- [ ] Implement `/webhook/teamleader` endpoint
- [ ] Implement `/webhook/brevo` endpoint  
- [ ] Implement `/webhook/website` endpoint
- [ ] Implement identity resolution logic
- [ ] Test webhook security (signatures, rate limiting)

#### Phase 4: Intelligence Layer (Priority: High)
- [ ] Build scoring engine (engagement_score, lead_temperature)
- [ ] Implement "preferred_contact_time" analysis
- [ ] Implement "interests" keyword extraction
- [ ] Create sync job: Tracardi → PostgreSQL (every 15 min)
- [ ] Test scoring accuracy

#### Phase 5: Workflow Engine (Priority: Medium)
- [ ] Implement "hot_lead_alert" workflow
- [ ] Implement "morning_person_followup" workflow
- [ ] Implement "re_engagement_campaign" workflow
- [ ] Implement "churn_risk_alert" workflow
- [ ] Test Slack/Brevo integrations

#### Phase 6: Chatbot Integration (Priority: Medium)
- [ ] Update chatbot to query PostgreSQL directly
- [ ] Add real-time scores from Tracardi
- [ ] Implement combined 360° profile view
- [ ] Test NL→SQL accuracy

#### Phase 7: Testing & Validation (Priority: High)
- [ ] End-to-end test: Teamleader → Tracardi → PostgreSQL → Brevo
- [ ] Load test: 1000 events/minute
- [ ] Failover test: Tracardi restart, data integrity
- [ ] GDPR compliance audit

#### Phase 8: Monitoring & Ops (Priority: Medium)
- [ ] Azure Monitor dashboards
- [ ] Alerting rules (CPU, latency, sync lag)
- [ ] Runbook for common issues
- [ ] Documentation for team

### 6. Deployment Guide
**File:** `docs/deployment.md`
**Changes:**
- [ ] Separate sections: PostgreSQL deployment, Tracardi deployment
- [ ] Add Terraform configs for both
- [ ] Add environment variables (.env, .env.database)
- [ ] Add troubleshooting section

### 7. Cost Analysis
**File:** `docs/COST_OPTIMIZATION_SUMMARY.md`
**Update:**
- [ ] Original cost: €48/mo (Tracardi B2s + data VM) - CRASHED
- [ ] New cost: €26/mo (PostgreSQL B1ms + Tracardi B1ms)
- [ ] Savings: €22/mo (46% reduction)
- [ ] Scalability: Handles 516K+ profiles vs 10K limit

### 8. README.md
**File:** `README.md`
**Changes:**
- [ ] Update project description to mention Hybrid Architecture
- [ ] Add quickstart for both PostgreSQL and Tracardi
- [ ] Update architecture diagram
- [ ] Add "Why Hybrid?" section

## Key Messages to Convey

1. **Scalability Fix:** PostgreSQL handles 516K profiles; Tracardi handles real-time events
2. **Cost Reduction:** 46% cheaper than original design
3. **Same Capabilities:** All original use cases still work (360° profile, automation, AI chatbot)
4. **Better Architecture:** Separation of concerns (data storage vs event processing)
5. **Privacy Preserved:** UID-based, no PII in CDP, same privacy-by-design

## Deliverables Checklist

- [ ] All documentation updated with Hybrid Architecture
- [ ] Backlog organized by phase with clear priorities
- [ ] Architecture Decision Records (ADRs) created
- [ ] Cost comparison documented
- [ ] Migration notes (from old to new architecture)
- [ ] Team onboarding guide updated

## Success Criteria

- [ ] New team member can understand architecture from docs alone
- [ ] Backlog clearly shows what's done vs todo
- [ ] All files reference the same architecture (no contradictions)
- [ ] Original POC requirements still met (KBO import, AI chatbot, Flexmail integration)

## Notes

- Keep original business case documents as "historical reference"
- Add "Last Updated: 2026-02-28" to all modified files
- Ensure all docs are in `/home/ff/.openclaw/workspace/repos/CDP_Merged/docs/`
- Backlog is at `/home/ff/.openclaw/workspace/repos/CDP_Merged/BACKLOG.md`
