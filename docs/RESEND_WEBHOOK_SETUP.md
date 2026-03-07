# Resend Webhook Configuration Guide

This guide explains how to set up Resend webhooks to track email events (delivered, opened, clicked, bounced, etc.) in your CDP.

## Architecture Overview

```
┌─────────────┐     Send Email      ┌─────────────┐
│   Resend    │ ──────────────────► │  Recipient  │
│   (SMTP)    │                     │   Inbox     │
└──────┬──────┘                     └─────────────┘
       │
       │ Email Events (webhooks)
       │ sent, delivered, opened, clicked, bounced
       ▼
┌─────────────┐     Forward       ┌─────────────┐
│    CDP      │ ─────────────────►│  Tracardi   │
│   Webhook   │                   │  (Events)   │
│   Gateway   │ ─────────────────►│  PostgreSQL │
│             │    Store Events   │  (Profiles) │
└─────────────┘                   └─────────────┘
```

## Supported Email Events

| Event | Description | Use Case |
|-------|-------------|----------|
| `email.sent` | Email dispatched from Resend | Track sending volume |
| `email.delivered` | Successfully delivered to inbox | Confirm delivery |
| `email.delivery_delayed` | Temporary delivery failure | Monitor delivery issues |
| `email.bounced` | Permanent delivery failure | Clean email lists |
| `email.complained` | Recipient marked as spam | Reputation management |
| `email.opened` | Recipient opened email | Engagement tracking |
| `email.clicked` | Recipient clicked link | Conversion tracking |

## Quick Setup

### 1. Configure Environment Variables

Add to your `.env` file:

```bash
# Resend API (already configured)
RESEND_API_KEY=re_aKqPRjtf_PZd7KR9PRokt38eivFvhBoHq
RESEND_FROM_EMAIL=onboarding@resend.dev

# Webhook Configuration
RESEND_WEBHOOK_URL=https://your-domain.com/webhook/resend
TRACARDI_TRACKER_URL=http://137.117.212.154:8686/tracker
```

### 2. Create the Webhook

**Option A: Interactive Setup**
```bash
python scripts/setup_resend_webhooks.py
```

**Option B: Automated Setup**
```bash
# Create engagement tracking webhook (opened, clicked, bounced)
python scripts/setup_resend_webhooks_auto.py --engagement

# Or create full tracking webhook (all events)
python scripts/setup_resend_webhooks_auto.py --full
```

### 3. Save the Webhook Secret

After creating the webhook, you'll receive a secret token. Add it to your `.env`:

```bash
RESEND_WEBHOOK_SECRET=whsec_your_webhook_secret_here
```

### 4. Verify Configuration

```bash
# List existing webhooks
python scripts/setup_resend_webhooks_auto.py --list
```

## Webhook Security

The webhook gateway includes multiple security layers:

### 1. Svix Signature Verification
Resend uses Svix for webhook signing. The signature is verified using HMAC-SHA256:

```
Signature Format: v1,<timestamp>,<signature>
Verification: HMACSHA256(secret, timestamp + "." + payload)
```

### 2. Replay Protection
- Timestamp validation (5-minute window)
- Nonce tracking to prevent duplicate processing
- Redis-backed distributed storage (with memory fallback)

### 3. Rate Limiting
- Configurable requests per window (default: 100/minute)
- Per-client IP tracking
- Automatic blocking of abusive clients

### 4. IP Allowlisting (Optional)
```bash
# Add to .env to restrict webhook sources
WEBHOOK_IP_ALLOWLIST=44.228.172.0/24,44.228.173.0/24
```

## Webhook Payload Format

### Example: Email Opened Event

```json
{
  "type": "email.opened",
  "created_at": "2024-03-07T14:30:00.000Z",
  "data": {
    "created_at": "2024-03-07T14:25:00.000Z",
    "email_id": "a12b34c5-d6e7-890f-1234-567890abcdef",
    "from": "onboarding@resend.dev",
    "to": "customer@example.com",
    "subject": "Welcome to Our Platform!",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    "ip_address": "192.168.1.1"
  }
}
```

### Example: Link Clicked Event

```json
{
  "type": "email.clicked",
  "created_at": "2024-03-07T14:31:00.000Z",
  "data": {
    "created_at": "2024-03-07T14:25:00.000Z",
    "email_id": "a12b34c5-d6e7-890f-1234-567890abcdef",
    "from": "onboarding@resend.dev",
    "to": "customer@example.com",
    "subject": "Welcome to Our Platform!",
    "click": {
      "link": "https://yourapp.com/get-started",
      "timestamp": "2024-03-07T14:31:00.000Z"
    },
    "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0...",
    "ip_address": "192.168.1.1"
  }
}
```

## Processing Events in Tracardi

### Event Mapping

Incoming webhooks are transformed to Tracardi events:

| Resend Event | Tracardi Event Type | Properties |
|-------------|---------------------|------------|
| `email.sent` | `email.sent` | email_id, from, to, subject |
| `email.delivered` | `email.delivered` | email_id, timestamp |
| `email.opened` | `email.opened` | email_id, user_agent, ip |
| `email.clicked` | `email.clicked` | email_id, link, user_agent |
| `email.bounced` | `email.bounced` | email_id, bounce_type |
| `email.complained` | `email.complained` | email_id, timestamp |

### Creating Workflows

To process email events in Tracardi:

1. **Go to Tracardi Dashboard** → Workflows
2. **Create a new workflow** for email engagement
3. **Add Event Source** for Resend webhooks
4. **Add nodes** for:
   - Profile enrichment (update last_email_opened)
   - Scoring (add engagement points)
   - Segmentation (mark as engaged)

### Example: Engagement Scoring Workflow

```yaml
# Workflow: Email Engagement Scoring
triggers:
  - event: email.opened
    source: resend

nodes:
  - id: add_score
    type: AddScoreNode
    config:
      score_name: email_engagement
      value: 5
      
  - id: update_profile
    type: UpdateProfileNode
    config:
      traits:
        last_email_opened: "{{event.timestamp}}"
        email_engagement_score: "{{profile.traits.email_engagement_score + 5}}"
```

## Testing Webhooks

### Method 1: Using the Setup Script
```bash
python scripts/setup_resend_webhooks.py
# Select option 4: Test webhook with test email
```

### Method 2: Manual Test
```python
from src.services.resend import ResendClient
import asyncio

async def test():
    client = ResendClient()
    result = await client.send_email(
        to="your-email@example.com",
        subject="🧪 Webhook Test",
        html="<h1>Test</h1><p>Open and click <a href='https://example.com'>this link</a></p>",
    )
    print(f"Email sent: {result['id']}")

asyncio.run(test())
```

### Method 3: Using Resend Dashboard
1. Go to Resend Dashboard → Logs
2. Find a sent email
3. Check if events are being received

## Troubleshooting

### Webhook Not Receiving Events

**Check 1: Verify webhook is created**
```bash
python scripts/setup_resend_webhooks_auto.py --list
```

**Check 2: Test endpoint accessibility**
```bash
curl -X POST https://your-domain.com/webhook/resend \
  -H "Content-Type: application/json" \
  -d '{"type":"test"}'
```

**Check 3: Check webhook secret**
- Ensure `RESEND_WEBHOOK_SECRET` matches the secret from Resend dashboard
- Secret is shown only once when creating the webhook

### Signature Verification Failed

**Problem:** `resend_signature_verification_failed`

**Solutions:**
1. Verify `RESEND_WEBHOOK_SECRET` is set correctly in `.env`
2. Check for trailing spaces in the secret
3. Regenerate webhook if secret was lost:
   ```bash
   python scripts/setup_resend_webhooks_auto.py --delete-all
   python scripts/setup_resend_webhooks_auto.py --engagement
   ```

### Events Not Showing in Tracardi

**Check 1: Verify Tracardi tracker URL**
```bash
curl http://137.117.212.154:8686/tracker
# Should return 400 (missing payload) not 404
```

**Check 2: Check Tracardi event source**
- Ensure event source exists for Resend
- Verify source ID matches configuration

**Check 3: Review logs**
```bash
# Check webhook gateway logs
python scripts/webhook_gateway.py

# Check Tracardi logs
docker logs tracardi-api
```

## Monitoring

### Health Check Endpoint

```bash
curl https://your-domain.com/health
```

Response:
```json
{
  "status": "ok",
  "timestamp": "2024-03-07T14:30:00Z",
  "security": {
    "resend_signature_verification": true,
    "replay_protection": {"enabled": true, "window_seconds": 300},
    "rate_limiting": {"enabled": true, "requests_per_window": 100}
  }
}
```

### Key Metrics to Monitor

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Webhook delivery rate | >99% | 95-99% | <95% |
| Event processing latency | <1s | 1-5s | >5s |
| Bounce rate | <2% | 2-5% | >5% |
| Spam complaint rate | <0.1% | 0.1-0.3% | >0.3% |

## Best Practices

1. **Use Engagement Events for Scoring**
   - Focus on `email.opened` and `email.clicked` for engagement metrics
   - Use `email.bounced` for list hygiene

2. **Implement Retry Logic**
   - Webhooks may occasionally fail
   - Resend retries automatically for 24 hours
   - Ensure your endpoint returns 200 quickly

3. **Process Events Asynchronously**
   - Return 200 response immediately
   - Process events in background (Event Hub → Workers)

4. **Secure Your Endpoint**
   - Always use HTTPS in production
   - Enable signature verification
   - Use IP allowlisting if possible

5. **Monitor and Alert**
   - Set up alerts for high bounce rates
   - Monitor delivery rates
   - Track engagement trends

## Reference

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RESEND_API_KEY` | Yes | Resend API key |
| `RESEND_WEBHOOK_URL` | Yes | Your webhook endpoint URL |
| `RESEND_WEBHOOK_SECRET` | Yes | Webhook signing secret |
| `TRACARDI_TRACKER_URL` | No | Tracardi tracker endpoint |
| `WEBHOOK_IP_ALLOWLIST` | No | Comma-separated IP ranges |
| `REDIS_URL` | No | Redis for distributed rate limiting |

### Scripts

| Script | Purpose |
|--------|---------|
| `setup_resend_webhooks.py` | Interactive setup wizard |
| `setup_resend_webhooks_auto.py` | Automated setup for CI/CD |
| `webhook_gateway.py` | Webhook receiver service |

---

*Last updated: 2026-03-07*
