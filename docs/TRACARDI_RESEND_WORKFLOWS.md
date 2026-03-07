# Tracardi Workflows for Resend Email Events

Complete guide for setting up Tracardi workflows to process Resend email events (sent, delivered, opened, clicked, bounced, complained).

## Architecture

```
┌─────────────┐     Webhook      ┌─────────────┐     Workflow     ┌─────────────┐
│   Resend    │ ───────────────► │   Tracardi  │ ───────────────► │   Profile   │
│   Events    │                  │   Ingestion │                  │   Update    │
└─────────────┘                  └──────┬──────┘                  └─────────────┘
                                        │
                                        ▼
                              ┌───────────────────┐
                              │  Event Processing │
                              │  - Engagement     │
                              │  - Bounce         │
                              │  - Delivery       │
                              │  - Complaint      │
                              └───────────────────┘
```

## Quick Start

### 1. Run the Setup Script

```bash
python scripts/setup_tracardi_resend_complete.py
```

This creates:
- ✅ Event Source: `resend-webhook`
- ✅ Event Types: `email.sent`, `email.delivered`, `email.opened`, `email.clicked`, `email.bounced`, `email.complained`
- ✅ Workflows: Engagement, Bounce, Delivery, Complaint, Segmentation

### 2. Configure Resend Webhook

```bash
python scripts/setup_resend_webhooks.py
# Or automated:
python scripts/setup_resend_webhooks_auto.py --engagement
```

Set webhook URL to: `http://137.117.212.154:8686/track`

### 3. Test the Integration

```bash
# Send a test email
python -c "
import asyncio
from src.services.resend import ResendClient

async def test():
    client = ResendClient()
    result = await client.send_email(
        to='your-email@example.com',
        subject='🧪 Tracardi Workflow Test',
        html='<h1>Test</h1><p>Open and click <a href=\"https://example.com\">this link</a></p>',
    )
    print(f'Email sent: {result[\"id\"]}')

asyncio.run(test())
"
```

## Workflow Details

### 1. Email Engagement Processor

**Triggers:** `email.opened`, `email.clicked`

**Actions:**
1. Increment `traits.engagement_score` by 1
2. Add tag `email_engaged`
3. Update `traits.last_email_engagement` timestamp
4. Record `traits.last_email_id` and `traits.last_email_subject`

**Purpose:** Track email engagement and build engagement scores for segmentation.

### 2. Email Bounce Processor

**Triggers:** `email.bounced`

**Actions:**
1. Set `traits.email_valid` to `false`
2. Set `traits.email_bounced_at` timestamp
3. Add tag `email_bounced`
4. Record `traits.email_bounce_type` and `traits.email_bounce_reason`

**Purpose:** Mark invalid emails and maintain list hygiene.

### 3. Email Delivery Processor

**Triggers:** `email.sent`, `email.delivered`

**Actions:**
1. Update `traits.last_email_sent_at` timestamp
2. Set `traits.email_valid` to `true`
3. Increment `traits.total_emails_sent` counter

**Purpose:** Track email delivery and maintain email validity status.

### 4. High Engagement Segment Assignment

**Triggers:** `email.opened`, `email.clicked`

**Condition:** `traits.engagement_score >= 5`

**Actions:**
1. Add tags `vip` and `high_engagement`
2. Set `traits.engagement_tier` to `high`

**Purpose:** Automatically segment highly engaged users for targeted campaigns.

### 5. Email Complaint Processor

**Triggers:** `email.complained`

**Actions:**
1. Set `traits.email_suppressed` to `true`
2. Set `traits.email_suppression_reason` to `spam_complaint`
3. Set `traits.email_suppressed_at` timestamp
4. Add tags `email_complaint` and `do_not_email`

**Purpose:** Handle spam complaints and suppress profiles to protect sender reputation.

## Event Type Reference

| Event Type | Properties | Workflow |
|------------|-----------|----------|
| `email.sent` | email_id, to, from, subject, timestamp | Email Delivery Processor |
| `email.delivered` | email_id, to, timestamp | Email Delivery Processor |
| `email.delivery_delayed` | email_id, to, reason, timestamp | - |
| `email.opened` | email_id, to, timestamp, user_agent, ip_address | Engagement Processor + Segment Assignment |
| `email.clicked` | email_id, to, link, timestamp, user_agent, ip_address | Engagement Processor + Segment Assignment |
| `email.bounced` | email_id, to, bounce_type, bounce_reason, timestamp | Bounce Processor |
| `email.complained` | email_id, to, timestamp | Complaint Processor |

## Profile Traits Updated

| Trait | Type | Description |
|-------|------|-------------|
| `engagement_score` | number | Cumulative email engagement score |
| `last_email_engagement` | datetime | Timestamp of last open/click |
| `last_email_event` | string | Type of last email event |
| `last_email_id` | string | ID of last email interacted with |
| `last_email_subject` | string | Subject of last email |
| `last_email_sent_at` | datetime | Timestamp of last sent email |
| `total_emails_sent` | number | Total emails sent to profile |
| `email_valid` | boolean | Whether email is valid (false if bounced) |
| `email_bounced_at` | datetime | When email bounced |
| `email_bounce_type` | string | Type of bounce (hard_bounce, soft_bounce) |
| `email_bounce_reason` | string | Bounce reason description |
| `email_suppressed` | boolean | Whether email is suppressed |
| `email_suppression_reason` | string | Reason for suppression |
| `email_suppressed_at` | datetime | When email was suppressed |
| `engagement_tier` | string | Engagement tier (high, medium, low) |

## Tags Applied

| Tag | When Applied |
|-----|-------------|
| `email_engaged` | On email open or click |
| `email_bounced` | On email bounce |
| `email_complaint` | On spam complaint |
| `do_not_email` | On spam complaint |
| `vip` | When engagement_score >= 5 |
| `high_engagement` | When engagement_score >= 5 |

## Testing Workflows

### Test 1: Engagement Tracking

```bash
curl -X POST http://137.117.212.154:8686/track \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"id": "resend-webhook"},
    "profile": {"traits": {"email": "test@example.com"}},
    "events": [{
      "type": "email.opened",
      "properties": {
        "email_id": "test-123",
        "to": "test@example.com",
        "subject": "Test Email",
        "timestamp": "'$(date -Iseconds)'"
      }
    }]
  }'
```

**Expected:** Profile engagement_score incremented, `email_engaged` tag added.

### Test 2: Bounce Handling

```bash
curl -X POST http://137.117.212.154:8686/track \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"id": "resend-webhook"},
    "profile": {"traits": {"email": "bounce@example.com"}},
    "events": [{
      "type": "email.bounced",
      "properties": {
        "email_id": "test-456",
        "to": "bounce@example.com",
        "bounce_type": "hard_bounce",
        "bounce_reason": "Mailbox does not exist"
      }
    }]
  }'
```

**Expected:** Profile `email_valid` set to false, `email_bounced` tag added.

### Test 3: VIP Segmentation

Send 5+ open events for the same profile and verify:
- `engagement_score` >= 5
- `vip` tag added
- `engagement_tier` set to `high`

## Monitoring & Debugging

### Check Workflow Execution

1. Go to Tracardi GUI: `http://137.117.212.154:8787`
2. Navigate to "Flows"
3. Click on workflow name to see execution logs

### View Profile Updates

1. Go to "Profiles" in Tracardi GUI
2. Search by email
3. View "Traits" section for updated fields

### Check Events

1. Go to "Events" in Tracardi GUI
2. Filter by event type (e.g., `email.opened`)
3. Verify events are being received

### Log Analysis

```bash
# Check Tracardi API logs
docker logs tracardi-api 2>&1 | grep -i "event\|workflow"

# Check webhook gateway logs
python scripts/webhook_gateway.py
```

## Customization

### Adjust Engagement Score Value

Edit `scripts/setup_tracardi_resend_complete.py`:

```python
{
    "id": "increment_engagement_score",
    "type": "increment",
    "config": {
        "field": "traits.engagement_score",
        "value": 5  # Change from 1 to 5
    }
}
```

### Change VIP Threshold

Edit the condition in `create_high_engagement_segment_workflow()`:

```python
"config": {
    "condition": "{{profile.traits.engagement_score >= 10}}"  # Change from 5
}
```

### Add Custom Traits

Add to any workflow node:

```python
{
    "id": "custom_trait",
    "type": "trait",
    "config": {
        "traits": {
            "custom_field": "{{event.properties.custom_value}}"
        }
    }
}
```

## Troubleshooting

### Events Not Processing

**Check 1:** Verify event source exists
```bash
curl http://137.117.212.154:8686/event-sources \
  -H "Authorization: Bearer $TOKEN"
```

**Check 2:** Test event tracking directly
```bash
curl -X POST http://137.117.212.154:8686/track \
  -H "Content-Type: application/json" \
  -d '{"source": {"id": "resend-webhook"}, "events": [{"type": "email.opened"}]}'
```

**Check 3:** Verify workflow is enabled
- Go to Tracardi GUI → Flows
- Check that workflow toggle is ON

### Workflows Not Triggering

**Problem:** Workflow not executing on events

**Solution:**
1. Check workflow trigger event types match incoming events
2. Verify workflow is deployed (not in draft state)
3. Check Tracardi API logs for errors

### Engagement Score Not Updating

**Problem:** Score stays at 0

**Solution:**
1. Verify profile exists before event
2. Check `traits.engagement_score` field is accessible
3. Verify increment action is configured correctly

## Best Practices

1. **Test in Staging First**
   - Use test email addresses
   - Verify workflows before production

2. **Monitor Engagement Trends**
   - Track average engagement scores
   - Identify highly engaged segments

3. **Maintain List Hygiene**
   - Regularly review bounced emails
   - Suppress complainers immediately

4. **Segment Based on Engagement**
   - Use `engagement_tier` for targeting
   - Create campaigns for `vip` segment

5. **Review Workflow Performance**
   - Check execution logs regularly
   - Optimize slow workflows

## Reference

### Scripts

| Script | Purpose |
|--------|---------|
| `setup_tracardi_resend_complete.py` | Full setup (sources, types, workflows) |
| `setup_resend_webhooks.py` | Interactive webhook configuration |
| `setup_resend_webhooks_auto.py` | Automated webhook setup |

### API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /track` | Ingest events from Resend |
| `GET /flows` | List workflows |
| `GET /event-sources` | List event sources |
| `GET /profiles` | View profiles |

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TRACARDI_API_URL` | Yes | Tracardi API endpoint |
| `TRACARDI_USERNAME` | Yes | Tracardi username |
| `TRACARDI_PASSWORD` | Yes | Tracardi password |
| `RESEND_API_KEY` | Yes | Resend API key |
| `RESEND_WEBHOOK_SECRET` | No | Webhook signing secret |

---

*Last updated: 2026-03-07*
