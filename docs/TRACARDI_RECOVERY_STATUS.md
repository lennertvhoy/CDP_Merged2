# Tracardi Recovery Status - 2026-03-03

## ✅ RECOVERY SUCCESSFUL

**Status**: RESOLVED - Tracardi API and GUI fully operational
**Recovery Time**: ~30 minutes
**Resolution**: Data VM restart + Elasticsearch auto-start + Tracardi API restart

---

## Summary

| Component | Status | Details |
|-----------|--------|---------|
| KBO Import | ✅ COMPLETE | 1,940,603 companies imported to PostgreSQL |
| PostgreSQL | ✅ RUNNING | Azure Flexible Server (cdp-postgres-661) |
| Tracardi API | ✅ RUNNING | http://137.117.212.154:8686 |
| Tracardi GUI | ✅ RUNNING | http://137.117.212.154:8787 |
| Elasticsearch | ✅ RUNNING | vm-data-cdpmerged-prod (10.57.3.10) |
| Profiles | ✅ INTACT | 2,509 profiles preserved |

---

## Issue Timeline

### Initial Problem (Reported 2026-03-03 11:45)
- Tracardi API unresponsive (connection timeout)
- GUI stuck on loading spinner
- Root cause: Elasticsearch on data VM not responding

### Recovery Actions
1. **11:45-12:00**: Investigated and identified Elasticsearch failure
2. **12:00**: Restarted data VM via Azure CLI
3. **12:05**: ES connection changed from timeout → refused (VM up, ES starting)
4. **12:08**: Elasticsearch fully operational
5. **12:09**: Restarted Tracardi API container
6. **12:10**: Tracardi API verified working

### Verification
```bash
# API Health Check
curl http://137.117.212.154:8686/
# Result: {"version":"1.0.x",...,"installed":{"schema":true,"users":true,"form":true}}

# Authentication
curl -X POST http://137.117.212.154:8686/user/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@admin.com&password=<terraform-output>"
# Result: {"access_token":"...","token_type":"bearer","roles":["admin","maintainer"]}

# Profile Count
curl http://137.117.212.154:8686/profile/select \
  -H "Authorization: Bearer <token>" \
  -d '{"where":"metadata.time.create EXISTS","limit":0}'
# Result: {"total":2509,"result":[]}
```

---

## Access Information

### Tracardi GUI
- **URL**: http://137.117.212.154:8787
- **Username**: admin@admin.com
- **Password**: Get via `terraform -chdir=infra/tracardi output -raw tracardi_admin_password`

### Tracardi API
- **URL**: http://137.117.212.154:8686
- **Docs**: http://137.117.212.154:8686/docs

### Event Sources (Previously Created)
1. kbo-batch-import
2. kbo-realtime
3. resend-webhook
4. cdp-api

---

## Remaining Tasks

### 1. Create Tracardi Workflows (Manual GUI)
Workflow creation via API returned 404. Workflows need to be created manually:

**Via GUI** (http://137.117.212.154:8787):
1. Go to **Automation → Automation Workflows**
2. Create these 4 workflows:
   - **KBO Import Processor**: Handle KBO batch import events
   - **Email Engagement Processor**: Process email.opened/clicked events
   - **Email Bounce Processor**: Handle email.bounced events
   - **High Engagement Segment Assignment**: Auto-tag high engagers

### 2. Resend Webhook Configuration
Configure Resend to send events to Tracardi:
```bash
curl -X POST https://api.resend.com/webhooks \
  -H "Authorization: Bearer $RESEND_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://137.117.212.154:8686/track",
    "events": ["email.sent","email.delivered","email.opened","email.clicked","email.bounced"]
  }'
```

### 3. Verify KBO Import Completion
```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM companies;"
# Expected: 1940603
```

---

## KBO Import - SUCCESS ✅

**Status**: COMPLETED at 2026-03-03 11:59:12

```
Final PostgreSQL count: 1,940,603
Total time: 0.6 hours
Average rate: 882.5 records/second
```

---

## Commands Reference

```bash
# Check Tracardi API
curl -sS http://137.117.212.154:8686/

# Check Elasticsearch
ssh azureuser@137.117.212.154 "curl -sS http://10.57.3.10:9200/"

# Restart Tracardi API (if needed)
ssh azureuser@137.117.212.154 "sudo docker restart tracardi_api"

# View API logs
ssh azureuser@137.117.212.154 "sudo docker logs -f tracardi_api"

# Get Tracardi password
terraform -chdir=infra/tracardi output -raw tracardi_admin_password
```

---

## Files Created/Modified

1. `docs/TRACARDI_RECOVERY_STATUS.md` - This file
2. `scripts/setup_tracardi_workflows.py` - Workflow automation script (API 404)
3. `NEXT_ACTIONS.md` - Updated with recovery status
4. `PROJECT_STATE.yaml` - Updated with verification notes
5. `WORKLOG.md` - Session log

---

## Lessons Learned

1. **Root Cause**: Elasticsearch failure causes Tracardi API to hang at startup
2. **Recovery Pattern**: 
   - VM restart → Wait for cloud-init → ES auto-starts → Restart Tracardi API
3. **Connection refused > timeout**: Indicates VM is up but service not ready
4. **Azure run-command**: Can get stuck; SSH direct preferred when available

---

**Last Updated**: 2026-03-03 12:10
**Status**: ✅ RECOVERED - All systems operational
