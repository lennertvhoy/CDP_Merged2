# 🚀 Handover Prompt - Next AI Agent

**Date:** 2026-03-02  
**Previous Session:** Infrastructure Recovery & Workflow Integration  
**Your Priority:** Action #8 - Create Email Engagement Workflow

---

## ⚡ TL;DR - Start Here

**System Status:** ✅ Tracardi fully operational  
**Next Task:** Create "Email Engagement Scorer" workflow in Tracardi GUI  
**Time Estimate:** 30-45 minutes  
**Difficulty:** Medium (GUI-based workflow creation)

**Quick Start:**
1. Read `handover_2026-03-02.md` for full context
2. Access Tracardi: http://137.117.212.154:8787
3. Login: admin@admin.com / <redacted>
4. Create workflow (see details below)
5. Update documentation when done

---

## 📋 BEFORE YOU START - MANDATORY

### 1. Read These Files (In Order)
- [ ] `handover_2026-03-02.md` - Complete handover context
- [ ] `AGENTS.md` - Agent instructions (especially "WHEN PLANS CHANGE" section)
- [ ] `NEXT_ACTIONS.md` - Action #8 details
- [ ] `GUI_AGENT_PROMPT.md` - GUI-specific instructions

### 2. Verify Current State
```bash
cd /home/ff/.openclaw/workspace/repos/CDP_Merged

# Check Tracardi API
curl http://137.117.212.154:8686/info/version
# Expected: "1.0.x"

# Check authentication
curl -X POST http://137.117.212.154:8686/user/token \
  -d "username=admin@admin.com" \
  -d "password=<redacted>"
# Expected: access_token in response
```

### 3. Understand the Task
Create a Tracardi workflow that:
- Processes email engagement events from Resend
- Updates profile engagement scores
- Tags highly engaged users

---

## 🎯 YOUR TASK: Action #8

### Create Email Engagement Workflow

**Access:**
- URL: http://137.117.212.154:8787
- Username: admin@admin.com
- Password: <redacted>

**Workflow Specification:**

| Property | Value |
|----------|-------|
| **Name** | Email Engagement Scorer |
| **Trigger Events** | `email.opened`, `email.clicked` |
| **Event Source** | `resend-webhook` (already created) |

**Logic:**
```
IF event = email.opened THEN
    profile.stats.engagement_score += 10
    
IF event = email.clicked THEN
    profile.stats.engagement_score += 25
    
IF profile.stats.engagement_score > 50 THEN
    ADD TAG "Highly Engaged"
```

**Step-by-Step Instructions:**

1. **Login to GUI**
   - Open http://137.117.212.154:8787
   - Enter credentials
   - Select server: http://137.117.212.154:8686

2. **Create New Workflow**
   - Navigate to Workflows
   - Click "New Workflow"
   - Name: "Email Engagement Scorer"

3. **Configure Trigger**
   - Trigger type: Event
   - Event types: `email.opened`, `email.clicked`
   - Source: `resend-webhook`

4. **Add Update Profile Action**
   - Action: Update Profile
   - Field: `stats.engagement_score`
   - Operation: Increment
   - Value: Use conditional - 10 for opened, 25 for clicked
   - OR create two separate branches

5. **Add Conditional Branch**
   - Condition: `stats.engagement_score > 50`

6. **Add Tag Action**
   - In the "true" branch of condition
   - Action: Add Tag
   - Tag: "Highly Engaged"

7. **Save and Activate**
   - Save workflow
   - Activate it
   - Note the workflow ID

**Testing the Workflow:**

1. Send test email via Resend:
   ```bash
   curl -X POST https://api.resend.com/emails \
     -H "Authorization: Bearer <redacted>" \
     -H "Content-Type: application/json" \
     -d '{
       "from": "onboarding@resend.dev",
       "to": "your-email@example.com",
       "subject": "Test Email for Tracardi",
       "html": "<p>Click <a href='https://example.com'>this link</a></p>"
     }'
   ```

2. Open the email in your email client
3. Wait 2-3 minutes
4. Click the link in the email
5. Check Tracardi:
   - Go to Data → Events
   - Verify events received
   - Go to Profiles
   - Check profile engagement_score
   - Verify "Highly Engaged" tag if score > 50

---

## ⚠️ CRITICAL RULES

### If User Changes Plans
1. **STOP** - Don't continue current work
2. **DOCUMENT** - Add to NEXT_ACTIONS.md: `⏸️ Action #8 PAUSED - [reason]`
3. **UPDATE** - Update BACKLOG.md with new priority
4. **CONFIRM** - Ask user before proceeding with new work
5. **NEVER** abandon without documenting why

See AGENTS.md "WHEN USER CHANGES PLANS" section for full procedure.

### After Completing Work (MANDATORY)
Update ALL of these before saying you're done:

1. [ ] **BACKLOG.md** - Mark workflow task complete
2. [ ] **NEXT_ACTIONS.md** - Mark Action #8 ✅ complete
3. [ ] **AGENTS.md** - Update if workflow architecture changed
4. [ ] **PROJECT_STATUS_SUMMARY.md** - Update workflow status
5. [ ] **handover_2026-03-02.md** - Mark Action #8 complete
6. [ ] **Date headers** - Update in all modified files
7. [ ] **This file** - Mark your completion

---

## 🧪 Verification Checklist

Before finishing, verify:

- [ ] Workflow "Email Engagement Scorer" exists and is active
- [ ] Trigger configured for email.opened and email.clicked
- [ ] Update Profile action increments score correctly
- [ ] Conditional branch checks score > 50
- [ ] Add Tag action adds "Highly Engaged" tag
- [ ] Test email sent and events received in Tracardi
- [ ] Profile engagement_score updated correctly
- [ ] Tag appears when score exceeds 50
- [ ] No errors in Tracardi logs

---

## 📊 Success Criteria

The task is complete when:
1. ✅ Workflow created and saved
2. ✅ Events trigger workflow correctly
3. ✅ Engagement scores update accurately (+10 open, +25 click)
4. ✅ "Highly Engaged" tag applies when score > 50
5. ✅ End-to-end test successful (email → events → score → tag)
6. ✅ All documentation updated

---

## 🆘 Troubleshooting

### GUI Won't Load
```bash
# Check if API is responding
curl http://137.117.212.154:8686/info/version

# If not responding, restart API
az vm run-command invoke -g rg-cdpmerged-fast -n vm-tracardi-cdpmerged-prod \
  --command-id RunShellScript --scripts "docker restart tracardi_api"
```

### Can't Login
- Username: admin@admin.com
- Password: <redacted>
- If fails, check API logs:
```bash
az vm run-command invoke -g rg-cdpmerged-fast -n vm-tracardi-cdpmerged-prod \
  --command-id RunShellScript --scripts "docker logs tracardi_api --tail 50"
```

### Events Not Received
1. Check tunnel is running: `pgrep -f localtunnel`
2. If not running, restart:
   ```bash
   nohup npx localtunnel --port 8686 --subdomain tracardi-cdpmerged > /tmp/tunnel.log 2>&1 &
   ```
3. Update Resend webhook endpoint if tunnel URL changed

### Workflow Not Triggering
- Verify event source is correct: `resend-webhook`
- Check event type matches exactly: `email.opened` (not `email_opened`)
- Ensure workflow is activated (not just saved)

---

## 📁 Key Files Reference

| File | Purpose |
|------|---------|
| `handover_2026-03-02.md` | Full handover context |
| `AGENTS.md` | Agent instructions & workflow template |
| `NEXT_ACTIONS.md` | Action #8 details |
| `GUI_AGENT_PROMPT.md` | GUI-specific instructions |
| `BACKLOG.md` | Project status |
| `.env.webhook` | Webhook configuration |

---

## 📝 Task Completion Report Template

Copy this and fill out when done:

```markdown
## Task Completion Report

**Date:** 2026-03-02
**Task:** Action #8 - Create Email Engagement Workflow
**Status:** ✅ Complete

### Documentation Updated:
- [ ] BACKLOG.md - Task status updated
- [ ] NEXT_ACTIONS.md - Action #8 marked complete
- [ ] AGENTS.md - Architecture/decisions updated (if needed)
- [ ] PROJECT_STATUS_SUMMARY.md - Status updated
- [ ] handover_2026-03-02.md - Action #8 marked complete
- [ ] Date headers updated in all modified files

### Verification:
- [ ] Workflow "Email Engagement Scorer" created
- [ ] Trigger configured for email.opened and email.clicked
- [ ] Update Profile action increments score correctly
- [ ] Conditional branch checks score > 50
- [ ] Add Tag action adds "Highly Engaged" tag
- [ ] Test email sent
- [ ] Events received in Tracardi
- [ ] Profile scores updated correctly
- [ ] Tag appears when appropriate
- [ ] No errors in logs

### What Was Accomplished:
1. Created "Email Engagement Scorer" workflow in Tracardi
2. Configured trigger for email.opened and email.clicked events
3. Set up profile score increment (+10 open, +25 click)
4. Added conditional logic for "Highly Engaged" tag
5. Tested end-to-end flow with test email

### Issues Encountered:
- [List any issues and how they were resolved]

### Next Steps:
- [Any follow-up actions needed]
```

---

## 🎯 Remember

1. **Read first** - Don't skip the documentation
2. **Verify state** - Check Tracardi is operational
3. **Follow procedure** - Use the workflow template in AGENTS.md if needed
4. **Update docs** - This is MANDATORY, not optional
5. **Ask if unclear** - Better to confirm than guess

---

**Ready to start?** Access Tracardi at http://137.117.212.154:8787

Good luck! 🚀
