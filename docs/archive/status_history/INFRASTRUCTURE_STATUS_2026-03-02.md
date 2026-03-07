# Infrastructure Status Report - 2026-03-02

## 🔴 CRITICAL ISSUE: Intermittent Tracardi API Failures

### Root Cause
**Elasticsearch on data VM (vm-data-cdpmerged-prod) is unstable.** 

The data VM has a stuck Azure Run Command extension that prevents proper diagnostics and management. Elasticsearch starts but becomes unresponsive, causing the Tracardi API to timeout on database-dependent operations.

### Current Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                     Tracardi App VM                              │
│  (vm-tracardi-cdpmerged-prod - 137.117.212.154)                 │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  GUI (:8787) │  │  API (:8686) │  │  MySQL       │           │
│  │     ✅       │  │    ⚠️        │  │     ✅       │           │
│  └──────────────┘  └──────┬───────┘  └──────────────┘           │
│                           │                                      │
│                           │ Connects to                          │
│                           ▼                                      │
└─────────────────────────────────────────────────────────────────┘
                           │
                           │ (Internal Network)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Data VM                                      │
│  (vm-data-cdpmerged-prod - 10.57.3.10)                          │
│                                                                  │
│  ┌────────────────────┐  ┌────────────────────┐                 │
│  │ Elasticsearch      │  │ Redis              │                 │
│  │ (:9200)   🔴       │  │ (:6379)   ✅       │                 │
│  │ Unresponsive       │  │ Working            │                 │
│  └────────────────────┘  └────────────────────┘                 │
│                                                                  │
│  ⚠️ Azure Run Command Extension STUCK                           │
│     - Cannot execute diagnostics commands                        │
│     - Cannot retrieve logs                                       │
│     - VM requires recreation for full fix                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✅ What's Working

| Component | Status | Details |
|-----------|--------|---------|
| Tracardi GUI | ✅ | HTTP 200, loads static content |
| Tracardi API (basic) | ✅ | /info/version responds |
| MySQL | ✅ | Healthy, connected |
| Redis | ✅ | Connected on data VM |
| Tunnel | ✅ | https://pink-pumas-report.loca.lt |
| Resend Webhook | ✅ | Configured and ready |

## 🔴 What's Broken

| Component | Status | Impact |
|-----------|--------|--------|
| Elasticsearch | 🔴 Unresponsive | API calls timeout, GUI freezes |
| Data VM Management | 🔴 Stuck Extension | Cannot run diagnostics/commands |
| API Database Calls | 🔴 Timeout | Cannot login, create sources, etc. |

---

## 🔧 ACTIONS TAKEN

1. ✅ Restarted both VMs (app and data)
2. ✅ Confirmed containers are running
3. ❌ Elasticsearch still unresponsive
4. ❌ Azure Run Command extension stuck on data VM

---

## 🎯 OPTIONS TO PROCEED

### Option 1: Recreate Data VM (RECOMMENDED - Permanent Fix)
**Estimated Time:** 20-30 minutes
**Steps:**
1. Delete vm-data-cdpmerged-prod
2. Recreate with same network config (10.57.3.10)
3. Deploy Elasticsearch + Redis via Docker Compose
4. Verify Elasticsearch responds on :9200
5. Restart Tracardi API container

**Terraform Location:** `infra/tracardi/` or `infra/terraform/`

### Option 2: Use Alternative Tunnel Directly to GUI
**Workaround Only - Events Still Won't Flow**
Since the GUI loads but API calls fail, this won't allow workflow creation.

### Option 3: Bypass Tracardi for POC
**Immediate Workaround**
1. Keep Resend webhooks for data collection
2. Store events in PostgreSQL directly
3. Skip Tracardi workflow automation for now
4. Complete POC with manual event tracking

---

## 📝 CURRENT CONFIGURATION

### Environment Files Updated:
- `.env.webhook` - Tunnel: `https://pink-pumas-report.loca.lt`
- `.env.tracardi` - Credentials valid

### Resend Webhook:
```json
{
  "id": "5f3c93ca-d60f-427f-9c91-ec5a462c3540",
  "endpoint": "https://pink-pumas-report.loca.lt/collect/email.event/resend-webhook",
  "status": "enabled"
}
```

### VM Status:
```
vm-tracardi-cdpmerged-prod: VM running ✅
vm-data-cdpmerged-prod:     VM running ✅ (but ES unresponsive)
```

---

## 🚀 RECOMMENDATION

**For Immediate POC Completion:**
1. Accept that Tracardi workflow automation is blocked
2. Store webhook events directly in PostgreSQL
3. Use PostgreSQL for engagement scoring (SQL queries)
4. Complete remaining POC requirements without Tracardi workflows

**For Full Solution:**
1. Recreate data VM via Terraform
2. Redeploy Elasticsearch with proper resource allocation
3. Reconfigure Tracardi API to use new ES instance
4. Complete workflow setup

---

## 📞 NEXT STEPS

**GUI Agent:** PAUSE Tracardi workflow creation - infrastructure blocked.

**Options:**
1. **Recreate data VM** (I can do this via Terraform)
2. **Bypass Tracardi** for POC and use PostgreSQL directly
3. **Wait** for manual ES fix (may take hours)

**What would you like to do?**
