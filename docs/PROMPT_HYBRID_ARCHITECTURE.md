# IMPLEMENTATION PROMPT: Hybrid CDP Architecture (PostgreSQL + Minimal Tracardi)

## Executive Summary
Implement Option B: Hybrid architecture where PostgreSQL remains the primary data store for 516K company profiles, and a minimal Tracardi instance handles real-time event ingestion, identity resolution, and workflow orchestration for active profiles only (target: <10K active).

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVENT SOURCES (Webhooks)                             │
├───────────────┬───────────────┬───────────────┬─────────────────────────────┤
│  Teamleader   │    Brevo      │    Website    │  Exact/Autotask/Sharepoint  │
│   (CRM)       │  (Email/SMS)  │   (GA4/GTM)   │       (ERP/PSA)             │
└───────┬───────┴───────┬───────┴───────┬───────┴─────────────┬───────────────┘
        │               │               │                     │
        └───────────────┴───────────────┴─────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MINIMAL TRACARDI (Event Hub)                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  VM: Standard_B1ms (€13/mo) - Smallest viable                       │    │
│  │                                                                     │    │
│  │  Responsibilities:                                                  │    │
│  │  1. Receive webhooks (HTTP endpoints)                               │    │
│  │  2. Event validation & deduplication                                │    │
│  │  3. Identity resolution (map to UID)                                │    │
│  │  4. Real-time scoring (engagement, lead score, churn risk)          │    │
│  │  5. Workflow triggers (if-this-then-that rules)                     │    │
│  │  6. Tag assignment (pref_contact_morning, interest_* )              │    │
│  │                                                                     │    │
│  │  Data Retention: 30 days rolling (events auto-archive to PostgreSQL)│    │
│  │  Active Profiles: Max 10K (LRU eviction)                            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└──────────────────┬──────────────────────────────────────┬───────────────────┘
                   │                                      │
                   ▼                                      ▼
┌──────────────────────────────────┐    ┌──────────────────────────────────────┐
│      POSTGRESQL (v2.0)           │    │      ACTIVATION LAYER                │
├──────────────────────────────────┤    ├──────────────────────────────────────┤
│  • 516K Company profiles         │    │  • Brevo API (send email/SMS)        │
│  • Full enrichment data (AI)     │◄───┤  • Slack webhooks (notify sales)     │
│  • Historical events (archive)   │    │  • Teamleader API (create tasks)     │
│  • Aggregated analytics          │    │  • Autotask API (create tickets)     │
│  • Event sourcing log            │    │  • Azure Queue (async processing)    │
└──────────────────────────────────┘    └──────────────────────────────────────┘
```

## Implementation Tasks

### Phase 1: Infrastructure Deployment (Terraform)

**Task 1.1: Deploy Minimal Tracardi VM**
- Create: `vm-tracardi-eventhub` (Standard_B1ms, €13/mo)
- Location: West Europe (same as PostgreSQL for low latency)
- OS: Ubuntu 22.04 LTS
- Disk: 32GB Standard SSD
- Networking: 
  - Public IP with NSG restricted to office IP (78.21.222.70/32)
  - Allow ports: 22 (SSH), 8686 (Tracardi API), 8787 (Tracardi GUI), 80/443 (webhooks)
- Tags: `environment=prod`, `component=eventhub`, `cost_center=cdp`, `temporary=false`

**Task 1.2: Configure Tracardi for Minimal Mode**
- Deploy Tracardi with Docker Compose
- Use INTERNAL MySQL (not external) - SQLite is fine for <10K profiles
- DISABLE Elasticsearch (use MySQL full-text search instead)
- Configure retention: 30 days max
- Set up daily cron job to archive old events to PostgreSQL

**Task 1.3: Secure Networking**
- NSG rules:
  - Allow 78.21.222.70/32 on 8686, 8787, 22
  - Allow Azure services (Container App subnet) on 8686
  - Deny all other inbound
- Enable Azure Monitor/Log Analytics for the VM

### Phase 2: Webhook Infrastructure

**Task 2.1: Create Webhook Endpoints**
Implement these endpoints in Tracardi:

```
POST /webhook/teamleader
  - Headers: X-Teamleader-Signature (verify)
  - Payload: { event_type, company_id, contact_id, data }
  - Actions: Create/update profile, trigger workflow

POST /webhook/brevo
  - Headers: X-Brevo-Signature (verify)
  - Payload: { event, email, campaign_id, timestamp, metadata }
  - Events: delivered, opened, clicked, bounced, unsubscribed

POST /webhook/website
  - No auth (rate limited by IP)
  - Payload: { uid, event_type, page_url, timestamp, session_data }
  - Events: page_view, form_submit, download, chat_started

POST /webhook/exact (optional)
  - Basic auth
  - Payload: { invoice_paid, subscription_status, support_ticket }
```

**Task 2.2: Webhook Security**
- Verify Teamleader signatures using shared secret
- Verify Brevo signatures
- Rate limiting: 100 req/min per IP
- IP allowlisting for Exact/Autotask (if static IPs known)

### Phase 3: Identity Resolution System

**Task 3.1: UID Mapping Logic**
Create resolution rules in Tracardi:

```python
# Priority order for identity resolution
RESOLUTION_RULES = [
    # 1. Direct UID match (Teamleader ID)
    {"source": "teamleader", "field": "company_id", "maps_to": "uid"},
    
    # 2. Email domain matching (for B2B)
    {"source": "brevo", "field": "email_domain", "maps_to": "company_domain"},
    
    # 3. KBO number (Belgian companies)
    {"source": "kbo", "field": "kbo_number", "maps_to": "kbo"},
    
    # 4. Cookie/Session ID (website anonymous)
    {"source": "website", "field": "cookie_id", "maps_to": "anonymous_id", 
     "merge_window": "24h"}  # Merge if email provided within 24h
]
```

**Task 3.2: PostgreSQL UID Sync**
- Tracardi stores: `uid`, `last_seen`, `tags`, `scores`
- Sync TO PostgreSQL every hour:
  - Update `engagement_score` in companies table
  - Update `last_interaction_at` timestamp
  - Append new tags to `segment_tags` array

### Phase 4: Real-Time Scoring Engine

**Task 4.1: Implement Scoring Rules in Tracardi**

```yaml
# scoring_rules.yml
rules:
  - name: engagement_score
    type: cumulative
    window: 30_days
    events:
      - email_opened: +2
      - email_clicked: +5
      - page_view: +1
      - form_submit: +10
      - chat_started: +15
    decay: daily_5pct  # Score decays 5% per day of inactivity

  - name: lead_temperature
    type: threshold
    conditions:
      - engagement_score > 50: "hot"
      - engagement_score > 25: "warm"
      - engagement_score > 10: "lukewarm"
      - default: "cold"

  - name: preferred_contact_time
    type: pattern
    analyze: email_opened.timestamp.hour
    buckets:
      - 6-9: "morning"
      - 9-12: "mid_morning"
      - 12-14: "lunch"
      - 14-17: "afternoon"
      - 17-20: "evening"
    winner: mode  # Most frequent bucket

  - name: interests
    type: content_analysis
    sources:
      - email.subject
      - page_view.url
      - page_view.title
    keywords:
      - "onderhoud": "interest_maintenance"
      - "prijs": "interest_pricing"
      - "support": "interest_support"
      - "training": "interest_training"
```

**Task 4.2: Sync Scores to PostgreSQL**
Create Azure Function or cron job:
```python
# Every 15 minutes
async def sync_scores():
    active_profiles = tracardi.get_profiles_with_changes(since="15m")
    for profile in active_profiles:
        await postgres.execute("""
            UPDATE companies 
            SET engagement_score = $1,
                lead_temperature = $2,
                preferred_contact_time = $3,
                segment_tags = array_append(segment_tags, $4),
                updated_at = NOW()
            WHERE kbo_number = $5 OR source_id = $6
        """, profile.score, profile.temp, profile.time, profile.new_tags, 
             profile.kbo, profile.uid)
```

### Phase 5: Workflow Engine (Tracardi Rules)

**Task 5.1: Implement Key Workflows**

```yaml
# workflows.yml
workflows:
  - name: hot_lead_alert
    trigger:
      type: score_threshold
      condition: engagement_score > 50 AND lead_temperature == "hot"
    actions:
      - type: webhook
        url: "{{SLACK_SALES_WEBHOOK}}"
        payload:
          text: "🔥 Hot lead: {{company.name}} (Score: {{engagement_score}})"
          blocks:
            - type: section
              text: "Company: {{company.name}}\nKBO: {{company.kbo_number}}\nInterest: {{interests|join(', ')}}"
            - type: button
              text: "View in Teamleader"
              url: "https://app.teamleader.eu/company/{{uid}}"
      - type: tag
        add: ["hot_lead_notified"]

  - name: morning_person_followup
    trigger:
      type: schedule
      cron: "0 7 * * 1-5"  # 7 AM weekdays
      condition: preferred_contact_time == "morning" AND days_since_contact > 7
    actions:
      - type: api_call
        service: brevo
        endpoint: /v3/smtp/email
        payload:
          to: [{"email": "{{primary_contact.email}}"}]
          templateId: 42  # Morning template
          params:
            company_name: "{{company.name}}"
            suggested_time: "08:00"

  - name: re_engagement_campaign
    trigger:
      type: inactivity
      days: 30
      condition: previous_engagement_score > 20
    actions:
      - type: tag
        add: ["re_engagement_candidate"]
      - type: webhook
        url: "{{BREVO_WEBHOOK}}"
        event: trigger_campaign
        campaign_id: "win_back_001"

  - name: churn_risk_alert
    trigger:
      type: pattern
      condition: 
        - support_tickets > 3 in 7_days
        - OR: email_engagement dropped 50% vs last_month
    actions:
      - type: tag
        add: ["churn_risk_high"]
      - type: slack
        channel: "#customer-success"
        message: "⚠️ Churn risk detected: {{company.name}}"
```

### Phase 6: PostgreSQL Integration Layer

**Task 6.1: Create Sync Tables**
```sql
-- Event archive (Tracardi → PostgreSQL)
CREATE TABLE event_archive (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL,
    source VARCHAR(50),
    event_type VARCHAR(100),
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Score history (time-series)
CREATE TABLE score_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL,
    score_type VARCHAR(50),
    score_value INTEGER,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Workflow execution log
CREATE TABLE workflow_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_name VARCHAR(100),
    uid VARCHAR(100),
    trigger_event VARCHAR(100),
    actions_taken JSONB,
    success BOOLEAN,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Task 6.2: Archive Job**
Daily cron from Tracardi VM:
```bash
#!/bin/bash
# /opt/tracardi/scripts/archive_events.sh
# Runs daily at 2 AM

curl -X POST http://localhost:8686/events/export \
  -H "Authorization: Bearer $TRACARDI_TOKEN" \
  -d '{"older_than_days": 30, "destination": "postgresql"}'

# Vacuum old events from Tracardi
curl -X DELETE http://localhost:8686/events/purge \
  -H "Authorization: Bearer $TRACARDI_TOKEN" \
  -d '{"older_than_days": 30}'
```

### Phase 7: Testing & Validation

**Task 7.1: End-to-End Test**
1. Create test company in Teamleader
2. Verify webhook received in Tracardi
3. Trigger test email from Brevo
4. Verify scoring updated
5. Verify sync to PostgreSQL
6. Check Slack notification (if applicable)

**Task 7.2: Load Testing**
- Simulate 1000 events/minute
- Verify Tracardi stays responsive
- Verify no data loss
- Check PostgreSQL sync lag < 5 minutes

**Task 7.3: Monitoring**
- Azure Monitor alerts:
  - Tracardi VM CPU > 80%
  - Tracardi API response time > 2s
  - PostgreSQL connection failures
  - Webhook delivery failures
  - Sync lag > 10 minutes

## Deliverables

1. **Terraform configs** for minimal Tracardi infrastructure
2. **Docker Compose** setup with MySQL (no ES)
3. **Webhook handler implementations** (4 endpoints)
4. **Scoring engine** configuration
5. **Workflow definitions** (YAML files)
6. **PostgreSQL sync scripts**
7. **Test suite** (pytest with mocks)
8. **Monitoring dashboard** (Azure Workbook)
9. **Runbook** for operations

## Constraints & Warnings

**CRITICAL:**
- Tracardi VM must be B1ms (€13/mo) - NO B2s (too expensive for this role)
- Event retention MAX 30 days in Tracardi
- Active profile limit: 10K (monitor with alert)
- NO Elasticsearch (use MySQL FTS instead)
- All PII stays in source systems (Teamleader, Brevo)

**Cost Target:**
- Tracardi VM: €13/mo
- PostgreSQL: €13/mo (existing)
- Bandwidth: ~€5/mo
- **Total: ~€31/mo** (vs €48/mo for full Tracardi)

## Azure Resources to Create

```bash
# You'll create:
az vm create \
  --resource-group rg-cdpmerged-fast \
  --name vm-tracardi-eventhub \
  --size Standard_B1ms \
  --image Ubuntu2204 \
  --admin-username azureuser \
  --ssh-key-values @~/.ssh/id_rsa.pub \
  --public-ip-address-allocation static \
  --nsg nsg-tracardi-eventhub

az network nsg rule create \
  --resource-group rg-cdpmerged-fast \
  --nsg-name nsg-tracardi-eventhub \
  --name allow-webhooks \
  --priority 100 \
  --source-address-prefixes '*' \
  --destination-port-ranges 80 443 8686 \
  --access Allow \
  --protocol Tcp
```

## Success Criteria

- [ ] Tracardi accessible at https://eventhub.cdpmerged.local (or IP)
- [ ] Webhooks from Teamleader/Brevo receive 200 OK
- [ ] Events appear in Tracardi within 5 seconds
- [ ] Scores sync to PostgreSQL within 15 minutes
- [ ] Slack notifications fire for hot leads
- [ ] Brevo campaigns trigger correctly
- [ ] 30-day event archive works
- [ ] VM stays under 70% CPU at 1000 events/min
- [ ] All monitors green

## Questions for Agent to Resolve

1. Should we use Azure API Management in front of webhooks for rate limiting?
2. Do we need a message queue (Azure Service Bus) between webhooks and Tracardi?
3. How to handle webhook retries on failure?
4. Should scoring happen in Tracardi or Azure Function (cheaper)?
5. Do we need GDPR deletion webhooks (right to be forgotten)?

Implement this step-by-step. Report progress after each phase.
