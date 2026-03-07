# Tracardi Workflow Setup Guide

**Date:** 2026-03-02  
**Purpose:** Manual workflow configuration for KBO data ingestion and email campaigns

---

## Overview

This guide describes how to create workflows in the Tracardi GUI for:
1. Processing KBO enterprise import events
2. Processing email engagement events (opens, clicks)
3. Processing email bounce events
4. Segment assignment based on engagement

---

## Prerequisites

- Tracardi GUI access: http://137.117.212.154:8787
- Credentials: `admin@admin.com` (get password from `terraform output -raw tracardi_admin_password`)
- Event sources created (see `scripts/setup_tracardi_kbo_and_email.py`)

---

## Event Sources Created

| Source ID | Name | Type | Purpose |
|-----------|------|------|---------|
| `kbo-batch-import` | KBO Batch Import | REST API | Batch import of KBO enterprise data |
| `kbo-realtime` | KBO Real-time Updates | Webhook | Real-time KBO publication updates |
| `resend-webhook` | Resend Email Webhook | Webhook | Email events from Resend |
| `cdp-api` | CDP API | REST API | Internal CDP API |

---

## Workflow 1: KBO Import Processor

**Purpose:** Process KBO enterprise import events and enrich profiles

### Steps:

1. **Navigate to Workflows**
   - Go to http://137.117.212.154:8787
   - Click "Flows" in the left sidebar
   - Click "Create Flow"

2. **Configure Trigger**
   - Trigger Type: `Event`
   - Event Type: `kbo.enterprise.imported`
   - Source: `kbo-batch-import`

3. **Add Actions**

   **Action 1: Set KBO Number**
   - Type: `Set Field`
   - Field: `traits.kbo_number`
   - Value: `{{event.properties.kbo_number}}`

   **Action 2: Set Company Name**
   - Type: `Set Field`
   - Field: `traits.company_name`
   - Value: `{{event.properties.enterprise_name}}`

   **Action 3: Set NACE Codes**
   - Type: `Set Field`
   - Field: `traits.nace_codes`
   - Value: `{{event.properties.nace_codes}}`

   **Action 4: Set Location**
   - Type: `Set Field`
   - Field: `traits.city`
   - Value: `{{event.properties.city}}`

   **Action 5: Add KBO Tag**
   - Type: `Add Tag`
   - Tags: `kbo_enterprise`

4. **Save Workflow**
   - Name: `KBO Import Processor`
   - Description: `Process KBO enterprise import and enrich profile`
   - Enable: Yes

---

## Workflow 2: Email Engagement Processor

**Purpose:** Process email open/click events and update engagement scores

### Steps:

1. **Create New Flow**
   - Click "Create Flow"

2. **Configure Trigger**
   - Trigger Type: `Event`
   - Event Types: `email.opened`, `email.clicked`
   - Source: `resend-webhook`

3. **Add Actions**

   **Action 1: Update Engagement Score**
   - Type: `Increment Field`
   - Field: `traits.engagement_score`
   - Value: `1`

   **Action 2: Add Engaged Tag**
   - Type: `Add Tag`
   - Tags: `email_engaged`

   **Action 3: Update Last Engagement**
   - Type: `Set Field`
   - Field: `traits.last_email_engagement`
   - Value: `{{event.timestamp}}`

4. **Save Workflow**
   - Name: `Email Engagement Processor`
   - Description: `Process email open/click events and update engagement scores`
   - Enable: Yes

---

## Workflow 3: Email Bounce Processor

**Purpose:** Process email bounce events and mark invalid emails

### Steps:

1. **Create New Flow**
   - Click "Create Flow"

2. **Configure Trigger**
   - Trigger Type: `Event`
   - Event Type: `email.bounced`
   - Source: `resend-webhook`

3. **Add Actions**

   **Action 1: Mark Invalid Email**
   - Type: `Set Field`
   - Field: `traits.email_valid`
   - Value: `false`

   **Action 2: Add Bounced Tag**
   - Type: `Add Tag`
   - Tags: `email_bounced`

   **Action 3: Record Bounce Reason**
   - Type: `Set Field`
   - Field: `traits.email_bounce_reason`
   - Value: `{{event.properties.bounce_reason}}`

4. **Save Workflow**
   - Name: `Email Bounce Processor`
   - Description: `Process email bounce events and mark invalid emails`
   - Enable: Yes

---

## Workflow 4: High Engagement Segment Assignment

**Purpose:** Assign highly engaged profiles to VIP segment

### Steps:

1. **Create New Flow**
   - Click "Create Flow"

2. **Configure Trigger**
   - Trigger Type: `Event`
   - Event Types: `email.opened`, `email.clicked`
   - Source: `resend-webhook`

3. **Add Condition**
   - Type: `If`
   - Condition: `traits.engagement_score >= 5`

4. **Add Actions (in Then branch)**

   **Action 1: Add VIP Tag**
   - Type: `Add Tag`
   - Tags: `vip`, `high_engagement`

   **Action 2: Set Engagement Tier**
   - Type: `Set Field`
   - Field: `traits.engagement_tier`
   - Value: `high`

5. **Save Workflow**
   - Name: `High Engagement Segment Assignment`
   - Description: `Assign highly engaged profiles to VIP segment`
   - Enable: Yes

---

## Resend Webhook Configuration

To receive email events from Resend:

1. **Get Tracardi Source Endpoint**
   - Source ID: `resend-webhook`
   - Endpoint: `POST http://137.117.212.154:8686/track`

2. **Configure Resend Webhook**
   ```bash
   curl -X POST https://api.resend.com/webhooks \
     -H "Authorization: Bearer $RESEND_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "http://137.117.212.154:8686/track",
       "events": ["email.sent", "email.delivered", "email.opened", "email.clicked", "email.bounced"]
     }'
   ```

3. **Or use the script:**
   ```bash
   python scripts/setup_resend_webhooks.py
   ```

---

## Testing

### Test KBO Import
```bash
TRACARDI_SOURCE_ID=kbo-batch-import python scripts/sync_kbo_to_tracardi.py
```

### Test Email Events
```bash
curl -X POST http://137.117.212.154:8686/track \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"id": "resend-webhook"},
    "events": [{
      "type": "email.opened",
      "properties": {
        "email_id": "test-123",
        "to": "test@example.com",
        "timestamp": "'$(date -Iseconds)'"
      }
    }],
    "profile": {"traits": {"email": "test@example.com"}}
  }'
```

---

## Next Steps

1. **Create workflows manually in GUI** using this guide
2. **Configure Resend webhooks** to point to Tracardi
3. **Run KBO sync** to test the full pipeline
4. **Verify event processing** in Tracardi GUI

---

## Notes

- The Tracardi workflow API requires complex node definitions that are best created through the GUI
- Event types are auto-created when first event is received
- Segments require Tracardi license (not available in current deployment)
- For segments without license, use tags (`vip`, `email_engaged`, `kbo_enterprise`) for segmentation
