# ITERATIVE DEBUGGING WORKFLOW — CDP_Merged

A systematic approach to deploying, testing, debugging, and fixing issues in the CDP_Merged Azure deployment.

---

## 🔄 OVERVIEW

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  1. DEPLOY  │────►│  2. TEST    │────►│  3. REPORT  │────►│  4. FIX     │
│   Changes   │     │  Endpoints  │     │  Errors/    │     │   &        │
│             │     │             │     │   Logs      │     │  Redeploy   │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
       ▲                                                           │
       └───────────────────────────────────────────────────────────┘
                          (Iterate as needed)
```

---

## 1. DEPLOY CHANGES

### 1.1 Local Development Cycle

```bash
cd /home/ff/.openclaw/workspace/repos/CDP_Merged

# Ensure you're on the correct branch
git status
git log --oneline -3

# Make changes...
# Edit files...

# Run local checks
make lint
make test
make type-check

# If tests pass, commit and push
git add -A
git commit -m "fix: description of change"
git push origin main
```

### 1.2 Build and Push Container Image

```bash
# Build locally
docker build -t cdp-merged:local .

# Test locally with Docker Compose
make docker-up
curl http://localhost:8000/healthz
make docker-down

# Tag for GitHub Container Registry
export IMAGE_TAG=sha-$(git rev-parse --short HEAD)
docker build -t ghcr.io/lennertvhoy/cdp_merged:${IMAGE_TAG} .

# Push to GHCR (if credentials configured)
docker push ghcr.io/lennertvhoy/cdp_merged:${IMAGE_TAG}
```

### 1.3 Deploy to Azure Container App

```bash
# Option A: Update image only
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --image ghcr.io/lennertvhoy/cdp_merged:${IMAGE_TAG}

# Option B: Update image + environment variables
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --image ghcr.io/lennertvhoy/cdp_merged:${IMAGE_TAG} \
  --set-env-vars \
    LOG_LEVEL=DEBUG \
    NEW_FEATURE_FLAG=true

# Option C: Set secrets (for sensitive values)
az containerapp secret set \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --secrets \
    tracardi-password=newpassword \
    openai-api-key=newkey

# Wait for revision to become active
az containerapp revision list \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --query "[?properties.active].{name:name, state:properties.runningStatus, created:properties.createdTime}" \
  -o table
```

### 1.4 Verify Deployment

```bash
# Check revision status
az containerapp show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --query "{name:name, state:properties.runningStatus, provisioning:properties.provisioningState, revision:properties.latestRevisionName}"

# Output should show:
# {
#   "name": "ca-cdpmerged-fast",
#   "provisioning": "Succeeded",
#   "revision": "ca-cdpmerged-fast--0000006",
#   "state": "Running"
# }
```

---

## 2. TEST ENDPOINTS

### 2.1 Automated Health Check Script

Create `scripts/health_check.sh`:

```bash
#!/bin/bash
set -e

FQDN="ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io"
BASE_URL="https://${FQDN}"

echo "=== Health Check for ${FQDN} ==="
echo ""

# Test 1: Basic health endpoint
echo "[1/5] Testing /healthz..."
if curl -sf "${BASE_URL}/healthz" > /dev/null; then
    echo "  ✅ /healthz responding"
else
    echo "  ❌ /healthz failed"
    exit 1
fi

# Test 2: Project health endpoint
echo "[2/5] Testing /project/healthz..."
if curl -sf "${BASE_URL}/project/healthz" > /dev/null; then
    echo "  ✅ /project/healthz responding"
else
    echo "  ❌ /project/healthz failed"
    exit 1
fi

# Test 3: Main UI loads
echo "[3/5] Testing main UI..."
if curl -sf "${BASE_URL}/" | grep -q "chainlit"; then
    echo "  ✅ Chainlit UI loading"
else
    echo "  ❌ UI not loading correctly"
    exit 1
fi

# Test 4: Response time check
echo "[4/5] Testing response time..."
RESPONSE_TIME=$(curl -sf -w "%{time_total}" -o /dev/null "${BASE_URL}/healthz")
if (( $(echo "${RESPONSE_TIME} < 2.0" | bc -l) )); then
    echo "  ✅ Response time ${RESPONSE_TIME}s (acceptable)"
else
    echo "  ⚠️  Response time ${RESPONSE_TIME}s (slow)"
fi

# Test 5: LLM provider check
echo "[5/5] Checking LLM provider..."
HEALTH_OUTPUT=$(curl -sf "${BASE_URL}/healthz" 2>/dev/null || echo "{}")
LLM_PROVIDER=$(echo "${HEALTH_OUTPUT}" | grep -o '"llm_provider":"[^"]*"' | cut -d'"' -f4)
echo "  ℹ️  LLM Provider: ${LLM_PROVIDER:-unknown}"

echo ""
echo "=== All Health Checks Passed ==="
```

Run: `bash scripts/health_check.sh`

### 2.2 API Test Script

```bash
#!/bin/bash
# scripts/test_api.sh - Test Tracardi integration

FQDN="ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io"
BASE_URL="https://${FQDN}"

echo "=== API Integration Tests ==="

# Test Tracardi connectivity via health endpoint
echo "[1/2] Testing LLM configuration..."
HEALTH=$(curl -sf "${BASE_URL}/healthz" 2>/dev/null || echo "{}")
echo "Health Response: ${HEALTH}"

echo "[2/2] Manual UI test required..."
echo "  Open: ${BASE_URL}"
echo "  Send message: 'How many companies are in Gent?'"
echo "  Expected: Response with company count or error message"
```

### 2.3 Load Test (Optional)

```bash
# Using Apache Bench (if installed)
ab -n 100 -c 10 https://ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io/healthz

# Or using curl loop
for i in {1..10}; do
    time curl -sf https://ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io/healthz > /dev/null
    echo "Request $i complete"
done
```

---

## 3. REPORT ERRORS/LOGS

### 3.1 Stream Logs in Real-Time

```bash
# Watch live logs
az containerapp logs show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --follow

# In another terminal: trigger actions and watch logs
```

### 3.2 Capture Recent Logs

```bash
# Get last N lines
az containerapp logs show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --tail 200 > logs/recent.log

# Get logs from specific revision
az containerapp logs show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --revision ca-cdpmerged-fast--0000006 \
  --tail 500 > logs/revision-6.log
```

### 3.3 Log Analysis Commands

```bash
# Find all errors
grep -i error logs/recent.log > logs/errors.log

# Find Tracardi-related issues
grep -i "tracardi" logs/recent.log > logs/tracardi_issues.log

# Find authentication issues
grep -i "auth\|login\|password\|unauthorized" logs/recent.log > logs/auth_issues.log

# Count occurrences
jq -r '.error_type' logs/errors.log | sort | uniq -c | sort -rn
```

### 3.4 Structured Log Parsing

Since the app uses `structlog` with JSON output:

```bash
# Parse JSON logs with jq
az containerapp logs show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --tail 100 | jq -r 'select(.error_type) | {timestamp, level, error_type, message}'

# Extract specific fields
az containerapp logs show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --tail 100 | jq -r 'select(.event=="tracardi_auth_failed") | {time, status_code, detail}'
```

### 3.5 Error Report Template

Create `logs/error_report_$(date +%Y%m%d_%H%M%S).md`:

```markdown
# Error Report - $(date)

## Deployment Info
- Image: $(git rev-parse --short HEAD)
- Revision: ca-cdpmerged-fast--000000X
- Time: $(date)

## Errors Found
$(grep -c "error" logs/recent.log) total errors

## Top Error Types
$(jq -r '.error_type' logs/recent.log 2>/dev/null | sort | uniq -c | sort -rn | head -5)

## Tracardi Issues
$(grep "tracardi" logs/recent.log | tail -10)

## Recommendations
- [ ] Fix identified in code path
- [ ] Redeploy and re-test
```

---

## 4. FIX AND REDEPLOY

### 4.1 Quick Fixes (No Code Change)

```bash
# Fix 1: Restart Container App
az containerapp revision restart \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast

# Fix 2: Update environment variable
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --set-env-vars LOG_LEVEL=DEBUG

# Fix 3: Rollback to previous revision
az containerapp ingress traffic set \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --revision-weight ca-cdpmerged-fast--0000005=100
```

### 4.2 Code Fixes

```bash
# Step 1: Identify issue from logs
# Example: Tracardi auth failing with wrong username

# Step 2: Make code fix
# Edit src/services/tracardi.py or configuration

# Step 3: Test locally
make test

# Step 4: Commit
git add -A
git commit -m "fix: correct Tracardi username format

- Changed from email format to plain username
- Fixes authentication error in Azure deployment
- Verified with local tests"

# Step 5: Push and deploy
git push origin main
docker build -t ghcr.io/lennertvhoy/cdp_merged:fix-$(git rev-parse --short HEAD) .
docker push ghcr.io/lennertvhoy/cdp_merged:fix-$(git rev-parse --short HEAD)

az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --image ghcr.io/lennertvhoy/cdp_merged:fix-$(git rev-parse --short HEAD)

# Step 6: Verify fix
bash scripts/health_check.sh
```

### 4.3 Debugging in Container

```bash
# Execute shell in running container
az containerapp exec \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --command /bin/sh

# Inside container, check:
# - Environment variables
env | grep -E "(TRACARDI|LLM|AZURE)"

# - Test Tracardi connectivity
wget -qO- http://52.148.232.140:8686/health

# - Check file system
ls -la /app/
cat /app/src/config.py

# Exit
exit
```

### 4.4 Common Fix Patterns

#### Pattern 1: Environment Variable Fix
```bash
# Issue: Wrong value in environment variable
# Fix: Update and restart
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --set-env-vars TRACARDI_USERNAME=admin
```

#### Pattern 2: Secret Rotation
```bash
# Issue: Expired or wrong secret
# Fix: Update secret (automatically restarts revision)
az containerapp secret set \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --secrets tracardi-password=new-correct-password
```

#### Pattern 3: Feature Flag Toggle
```bash
# Issue: New feature causing problems
# Fix: Disable via feature flag
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --set-env-vars ENABLE_NEW_FEATURE=false
```

---

## 5. AUTOMATION

### 5.1 One-Command Debug Cycle

Create `scripts/debug_cycle.sh`:

```bash
#!/bin/bash
# debug_cycle.sh - Full deploy-test-report-fix cycle

set -e

RESOURCE_GROUP="rg-cdpmerged-fast"
CONTAINER_APP="ca-cdpmerged-fast"
FQDN="ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io"

echo "=== CDP_Merged Debug Cycle ==="
echo ""

# Step 1: Deploy
echo "[1/4] Deploying latest image..."
az containerapp update \
  --name ${CONTAINER_APP} \
  --resource-group ${RESOURCE_GROUP} \
  --image ghcr.io/lennertvhoy/cdp_merged:latest

# Wait for provisioning
sleep 10

# Step 2: Test
echo "[2/4] Running health checks..."
if curl -sf "https://${FQDN}/healthz" > /dev/null; then
    echo "  ✅ Health check passed"
else
    echo "  ❌ Health check failed"
    
    # Step 3: Report
    echo "[3/4] Capturing logs..."
    mkdir -p logs
    az containerapp logs show \
      --name ${CONTAINER_APP} \
      --resource-group ${RESOURCE_GROUP} \
      --tail 100 > logs/error-$(date +%Y%m%d-%H%M%S).log
    
    echo "  Logs saved to logs/"
    echo "  Last 20 lines:"
    tail -20 logs/error-$(date +%Y%m%d-%H%M%S).log
    
    exit 1
fi

# Step 4: Success
echo "[4/4] Deployment successful!"
echo "  URL: https://${FQDN}"
echo "  Revision: $(az containerapp show --name ${CONTAINER_APP} --resource-group ${RESOURCE_GROUP} --query properties.latestRevisionName -o tsv)"
```

### 5.2 Log Monitoring Alert

Create `scripts/log_watch.sh`:

```bash
#!/bin/bash
# log_watch.sh - Watch for errors and alert

RESOURCE_GROUP="rg-cdpmerged-fast"
CONTAINER_APP="ca-cdpmerged-fast"
ALERT_KEYWORDS="error|fail|exception|timeout|unauthorized"

echo "Watching logs for errors..."
az containerapp logs show \
  --name ${CONTAINER_APP} \
  --resource-group ${RESOURCE_GROUP} \
  --follow | while read line; do
    if echo "${line}" | grep -iE "${ALERT_KEYWORDS}" > /dev/null; then
        echo "🚨 ALERT: Potential error detected:"
        echo "  ${line}"
        # Could add: send notification, trigger alert, etc.
    fi
done
```

---

## 6. ERROR TRACING GUIDE

### 6.1 Azure Log → Code Line

| Log Entry | Code Location | Likely Issue |
|-----------|---------------|--------------|
| `tracardi_auth_failed` | `src/services/tracardi.py:87` | Wrong credentials |
| `query_too_long` | `src/app.py:75` | User input > 1000 chars |
| `nace_auto_resolved` | `src/ai_interface/tools.py:156` | Normal operation |
| `search_backend_failure` | `src/ai_interface/tools.py:267` | Tracardi down/slow |
| `tracardi_profile_bootstrap_failed` | `src/app.py:59` | Auth or connection issue |

### 6.2 Trace ID Tracking

The app generates trace IDs for each session. Use them to trace requests:

```bash
# Find trace ID in logs
az containerapp logs show ... | grep "trace_id"

# Trace specific session
az containerapp logs show ... | jq -r 'select(.trace_id=="your-uuid")'
```

---

## 7. TROUBLESHOOTING CHECKLIST

### Deployment Failed
- [ ] Check image tag exists in registry
- [ ] Verify Container App environment health
- [ ] Check resource quotas (CPU/memory)
- [ ] Review revision logs for startup errors

### App Unhealthy
- [ ] `/healthz` responding?
- [ ] Environment variables set correctly?
- [ ] Secrets configured?
- [ ] Network connectivity to Tracardi VM?

### Tracardi Integration Failing
- [ ] VM accessible (ping/ssh)?
- [ ] Tracardi API responding on port 8686?
- [ ] Credentials correct (try manual auth)?
- [ ] Elasticsearch running on data VM?

### LLM Not Responding
- [ ] Azure OpenAI quota available?
- [ ] Deployment name correct?
- [ ] API key valid?
- [ ] Endpoint accessible?

---

## 8. QUICK REFERENCE

### Essential Commands

```bash
# Deploy
az containerapp update -n ca-cdpmerged-fast -g rg-cdpmerged-fast --image <image>

# Logs
az containerapp logs show -n ca-cdpmerged-fast -g rg-cdpmerged-fast --follow

# Health
curl https://ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io/healthz

# Restart
az containerapp revision restart -n ca-cdpmerged-fast -g rg-cdpmerged-fast

# Rollback
az containerapp ingress traffic set -n ca-cdpmerged-fast -g rg-cdpmerged-fast --revision-weight <revision>=100

# SSH to Tracardi
ssh azureuser@52.148.232.140

# Check Tracardi logs
docker logs tracardi-api --tail 100
```

### Contact Points

| Issue | Resource |
|-------|----------|
| Azure infrastructure | Azure Portal / CLI |
| Tracardi issues | VM at 52.148.232.140 |
| Application code | GitHub repo |
| Secrets | Azure Container App secrets |

---

*Last Updated: 2026-02-25*
