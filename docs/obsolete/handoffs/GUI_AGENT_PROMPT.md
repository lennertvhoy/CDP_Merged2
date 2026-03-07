# 🚀 Tracardi GUI Agent - Action Required

**Status:** ✅ Infrastructure Ready - Proceed with Workflow Creation

---

## Quick Start

1. **Access Tracardi GUI:** http://137.117.212.154:8787
2. **Login Credentials:**
   - Username: `admin@admin.com`
   - Password: `<redacted>`

3. **Event Source:** Already created (ID: `resend-webhook`)

---

## Your Tasks

### ✅ Step 1: Event Source - ALREADY DONE
The "resend-webhook" event source has been created via API.
- Source ID: `resend-webhook`
- Type: webhook
- Status: enabled

### 🔄 Step 2: Verify Event Flow (Optional)
Test that events flow from Resend → Tracardi:
1. Send a test email via Resend API
2. Check Tracardi Data → Events for incoming events
3. Verify event structure includes: email, timestamp, event type

### 🎯 Step 3: Create Engagement Scoring Workflow (PRIORITY)
Create a workflow that processes email engagement events:

**Workflow Name:** "Email Engagement Scorer"

**Logic:**
1. When `email.opened` event received → add 10 to engagement score
2. When `email.clicked` event received → add 25 to engagement score
3. If engagement score > 50 → add tag "Highly Engaged"

**Steps:**
1. Navigate to Workflows → New Workflow
2. Set trigger: Event Type = `email.opened` OR `email.clicked`
3. Add "Update Profile" action:
   - Field: `stats.engagement_score`
   - Operation: Increment by 10 (opened) or 25 (clicked)
4. Add "If" condition: Check if `stats.engagement_score > 50`
5. Add "Add Tag" action: Tag = "Highly Engaged"
6. Save workflow

### ✅ Step 4: Test End-to-End
1. Send test email via Resend
2. Open the email (in an email client)
3. Click a link in the email
4. Check Tracardi profile for updated engagement score
5. Verify "Highly Engaged" tag appears when score > 50

---

## Reference Information

### Tracardi URLs
- **GUI:** http://137.117.212.154:8787
- **API:** http://137.117.212.154:8686

### Event Source Details
```json
{
  "id": "resend-webhook",
  "name": "Resend Webhook Source",
  "type": "webhook",
  "enabled": true,
  "transitional": true
}
```

### Webhook Endpoint
```
https://tracardi-cdpmerged.loca.lt/collect/email.event/resend-webhook
```

### Available Event Types from Resend
- `email.sent`
- `email.delivered`
- `email.opened`
- `email.clicked`
- `email.bounced`
- `email.complained`
- `email.delivery_delayed`

---

## If You Encounter Issues

### GUI Freezes / Won't Load
- Wait 10 seconds and refresh
- Check if API is responding: http://137.117.212.154:8686/info/version
- If still frozen, report to infrastructure agent

### Cannot Login
- Username: `admin@admin.com`
- Password: `<redacted>`
- If fails, API may need restart

### Workflow Not Triggering
- Verify event source is correct: `resend-webhook`
- Check event type matches (e.g., `email.opened` not `email_opened`)
- Test with manual event via API

---

## Completion Criteria

- [ ] Workflow "Email Engagement Scorer" created
- [ ] Workflow increments score on `email.opened` (+10)
- [ ] Workflow increments score on `email.clicked` (+25)
- [ ] Workflow adds "Highly Engaged" tag when score > 50
- [ ] End-to-end test successful (email sent → events → score updated)

---

**Ready to start! Access the GUI at: http://137.117.212.154:8787**
