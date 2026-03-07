# TROUBLESHOOTING GUIDE — CDP_Merged

Quick reference for diagnosing and fixing common issues in the CDP_Merged deployment.

---

## 🔴 CRITICAL ISSUES

### 1. Tracardi Authentication Failure

**Symptoms:**
- Chat responds: "Sorry, I encountered an error"
- Logs show: `tracardi_auth_failed` or "Authentication error: Incorrect username or password"
- Profile search returns no results

**Diagnosis:**
```bash
# Check Container App logs
az containerapp logs show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --tail 50

# Look for authentication errors
grep -i "tracardi_auth" /path/to/logs
```

**Root Causes & Fixes:**

#### A. Wrong Username Format
**Problem:** Username is `admin@cdpmerged.local` but Tracardi expects `admin`

**Fix:**
```bash
# Update Container App environment variable
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --set-env-vars TRACARDI_USERNAME=admin
```

#### B. Wrong Password
**Problem:** Password in Container App secret doesn't match Tracardi VM

**Fix:**
```bash
# Step 1: SSH to Tracardi VM and check/reset password
ssh azureuser@52.148.232.140

# Step 2: Check Tracardi docker-compose for admin credentials
cat /opt/tracardi/docker-compose.yml | grep -A5 "ADMIN"

# Step 3: If needed, reset Tracardi admin password
docker exec -it tracardi-api python -c "
from tracardi.service.setup.setup_env import setup_default_user
setup_default_user()
"

# Step 4: Update Container App secret
az containerapp secret set \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --secrets tracardi-password=<correct-password>

# Step 5: Restart Container App
az containerapp revision restart \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast
```

#### C. Tracardi API Not Reachable
**Problem:** Network connectivity issue between Container App and Tracardi VM

**Fix:**
```bash
# Test connectivity from Container App (via Azure Console or exec)
curl -v http://52.148.232.140:8686/health

# Check NSG rules on Tracardi VM
az network nsg rule list \
  --resource-group rg-cdpmerged-prod \
  --nsg-name nsg-app-*

# Ensure port 8686 is open from Container App subnet
```

---

### 2. Container App Health Check Failures

**Symptoms:**
- Container App shows "Unhealthy" status
- Revisions failing to start
- Traffic not routing to new revisions

**Diagnosis:**
```bash
# Check revision status
az containerapp revision list \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  -o table

# Get detailed health status
az containerapp show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --query "{health:properties.runningStatus, provisioning:properties.provisioningState}"
```

**Fix:**
```bash
# Check recent logs
az containerapp logs show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --tail 100

# Common fixes:
# 1. Missing environment variable
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --set-env-vars MISSING_VAR=value

# 2. Rollback to previous revision
az containerapp ingress traffic set \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --revision-weight ca-cdpmerged-fast--0000004=100
```

---

## 🟡 COMMON ISSUES

### 3. LLM Not Responding / Timeout

**Symptoms:**
- Chat hangs indefinitely
- "Sorry, I encountered an error: LLM timeout"
- Logs show `LLMError` or timeout exceptions

**Diagnosis:**
```bash
# Check LLM provider status
curl https://aoai-cdpmerged-fast.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions \
  -H "api-key: $AZURE_OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "test"}]}'
```

**Fixes:**

#### A. Azure OpenAI Quota Exceeded
```bash
# Check quota in Azure Portal
# Navigate to: Azure OpenAI Resource -> Quotas
# If exceeded: Request quota increase or reduce usage
```

#### B. Wrong Deployment Name
```bash
# Verify deployment name
az cognitiveservices account deployment list \
  --name aoai-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast

# Update Container App if needed
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --set-env-vars AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
```

#### C. Switch to Mock Provider (Emergency)
```bash
# For testing without LLM
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --set-env-vars LLM_PROVIDER=mock
```

---

### 4. Search Returns No Results

**Symptoms:**
- "Found 0 companies matching your criteria"
- Search appears to work but returns empty

**Diagnosis:**
```bash
# Check if Tracardi has data
ssh azureuser@52.148.232.140
curl -u admin:password http://10.56.2.10:9200/_cat/indices

# Check Tracardi profiles
curl -X POST http://localhost:8686/profile/select \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"where": "id exists", "limit": 1}'
```

**Fixes:**

#### A. No Data in Elasticsearch
```bash
# Re-run KBO data ingestion (from VM or local with VPN)
poetry run python -c "
from src.ingestion.tracardi_loader import load_kbo_data
import asyncio
asyncio.run(load_kbo_data('path/to/kbo.csv'))
"
```

#### B. Wrong TQL Query Syntax
```bash
# Enable debug logging to see generated queries
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --set-env-vars LOG_LEVEL=DEBUG

# Check logs for TQL query
az containerapp logs show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --tail 100 | grep -i "tql"
```

---

### 5. Flexmail Integration Not Working

**Symptoms:**
- "Push to Flexmail" fails silently
- Contacts not appearing in Flexmail

**Diagnosis:**
```bash
# Check if Flexmail is enabled
az containerapp show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --query "properties.template.containers[0].env[?name=='FLEXMAIL_ENABLED'].value"
```

**Fix:**
```bash
# Enable and configure Flexmail
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --set-env-vars \
    FLEXMAIL_ENABLED=true \
    FLEXMAIL_API_URL=https://api.flexmail.be \
    FLEXMAIL_ACCOUNT_ID=your-account-id \
    FLEXMAIL_API_TOKEN=your-token \
    FLEXMAIL_SOURCE_ID=12345

# Set API token as secret
az containerapp secret set \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --secrets flexmail-api-token=your-token
```

---

### 6. Session / State Lost Between Messages

**Symptoms:**
- Bot forgets context from previous messages
- Multi-turn conversations don't work

**Diagnosis:**
```bash
# Check if MemorySaver is working
# Look for thread_id in logs
az containerapp logs show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --tail 50 | grep -i "thread_id"
```

**Fix:**
```bash
# This is expected behavior with MemorySaver (in-memory only)
# For production, implement Redis persistence

# Deploy Redis (if not already)
az redis create \
  --name redis-cdpmerged \
  --resource-group rg-cdpmerged-fast \
  --location westeurope \
  --sku Basic \
  --vm-size C0

# Update Container App with Redis connection
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --set-env-vars \
    REDIS_HOST=redis-cdpmerged.redis.cache.windows.net \
    REDIS_PORT=6379 \
    REDIS_PASSWORD=secretref:redis-password
```

---

## 🔧 DEBUGGING COMMANDS

### Container App Operations

```bash
# View live logs
az containerapp logs show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --follow

# Execute command in container
az containerapp exec \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --command /bin/sh

# List revisions
az containerapp revision list \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast

# Show specific revision
az containerapp revision show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --revision ca-cdpmerged-fast--0000005
```

### Tracardi VM Operations

```bash
# SSH to VM
ssh azureuser@52.148.232.140

# Check Tracardi services
docker ps

# View Tracardi logs
docker logs tracardi-api --tail 100
docker logs tracardi-gui --tail 100

# Check Elasticsearch
curl http://10.56.2.10:9200/_cluster/health

# Restart services
cd /opt/tracardi
docker compose restart

# Check disk space
df -h
docker system df
```

### Data VM Operations

```bash
# SSH via Tracardi VM (no public IP)
ssh -J azureuser@52.148.232.140 azureuser@10.56.2.10

# Check Elasticsearch
curl http://localhost:9200/_cluster/health
curl http://localhost:9200/_cat/indices

# Free up space if needed
docker system prune -f
```

### Network Testing

```bash
# Test Tracardi API from local
curl http://52.148.232.140:8686/health

# Test from Container App (exec into container)
az containerapp exec \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --command "wget -qO- http://52.148.232.140:8686/health"

# Check NSG rules
az network nsg rule list \
  --resource-group rg-cdpmerged-prod \
  --nsg-name nsg-app-cdpmerged-prod
```

---

## 📊 LOG ANALYSIS

### Key Log Patterns

| Pattern | Meaning | Action |
|---------|---------|--------|
| `tracardi_auth_failed` | Authentication error | Fix credentials |
| `query_too_long` | User query exceeded 1000 chars | Inform user |
| `nace_auto_resolved` | NACE codes found for keyword | Normal |
| `flexmail_push_complete` | Segment pushed successfully | Normal |
| `query_error` | Unhandled exception in graph | Check stack trace |

### Filtering Logs

```bash
# Get only error logs
az containerapp logs show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --tail 500 | grep -i error

# Get specific session
grep "thread_id=<session-id>" /var/log/cdp/app.log

# Get Tracardi-related logs
grep "tracardi_" /var/log/cdp/app.log
```

---

## 🆘 EMERGENCY PROCEDURES

### Complete Restart

```bash
# 1. Restart Container App
az containerapp revision restart \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast

# 2. Restart Tracardi VM services
ssh azureuser@52.148.232.140 "cd /opt/tracardi && docker compose restart"

# 3. Verify health
curl https://ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io/healthz
```

### Rollback Deployment

```bash
# List revisions
az containerapp revision list \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  -o table

# Rollback to previous revision
az containerapp ingress traffic set \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --revision-weight ca-cdpmerged-fast--0000004=100

# Verify rollback
curl https://ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io/healthz
```

### Emergency Mock Mode

If all external services are down, switch to mock mode:

```bash
az containerapp update \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --set-env-vars \
    LLM_PROVIDER=mock \
    TRACARDI_API_URL=http://localhost:8686
```

---

## 📞 ESCALATION

| Issue | Contact | When |
|-------|---------|------|
| Azure infrastructure | Azure Support | Resource failures |
| Tracardi bugs | Tracardi GitHub | API issues |
| Application code | Internal Dev | Logic errors |
| VM access | Azure VM Admin | SSH/key issues |

---

## 📝 LOG TEMPLATES

When reporting issues, include:

```markdown
**Issue:** [Brief description]
**Environment:** [prod/staging/dev]
**Time:** [When it started]
**Error Message:** [Exact error text]
**Logs:** [Relevant log snippet]
**Reproduction Steps:**
1. Step 1
2. Step 2
**Expected:** [What should happen]
**Actual:** [What actually happens]
```

---

*Last Updated: 2026-02-25*
