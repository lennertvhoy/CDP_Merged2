## Handoff

**Date:** 2026-03-03  
**Canonical Repo:** `/home/ff/.openclaw/workspace/repos/CDP_Merged`  
**Task:** Implement Nginx + Let's Encrypt SSL, Cost Optimization, Profile Ingestion Verification  
**Status:** PAUSED - Ready for next session  
**Priority:** P1

---

### Read First

1. `AGENTS.md` - Operating rules and IaC compliance
2. `STATUS.md` - Current system status
3. `PROJECT_STATE.yaml` - Structured live state
4. `NEXT_ACTIONS.md` - Active queue
5. This handover

---

### Non-Negotiable Rules

- Work only in `/home/ff/.openclaw/workspace/repos/CDP_Merged`
- **ALL infrastructure changes must be codified in IaC** (AGENTS.md §IaC Compliance)
- Do not restate live status in multiple docs - use `PROJECT_STATE.yaml` as source
- Use verification labels: `observed`, `reported`, `blocked`, `assumed`
- After each task, update `PROJECT_STATE.yaml` and `WORKLOG.md`

---

## Session Objectives

### Objective 1: Implement Nginx + Let's Encrypt SSL

**Status:** `assumed` - Not yet implemented  
**Cost Impact:** €0 (uses existing VM)  
**Goal:** Provide persistent HTTPS endpoint for Tracardi and Resend webhooks

**Background:**
- Current Resend webhook uses ephemeral localtunnel (`https://cuddly-bats-fail.loca.lt`)
- Tunnel expires on process restart → breaks webhook
- Nginx + Let's Encrypt provides **free, auto-renewing SSL** on the Tracardi VM

**Implementation Plan:**

1. **Install Nginx and Certbot on Tracardi VM**
   ```bash
   # SSH to Tracardi VM
   ssh azureuser@137.117.212.154
   
   # Install packages
   sudo apt update
   sudo apt install -y nginx certbot python3-certbot-nginx
   ```

2. **Configure Nginx as reverse proxy**
   - Proxy HTTP (80) and HTTPS (443) to Tracardi (8686)
   - Proxy HTTPS to Tracardi GUI (8787) if needed
   - File: `/etc/nginx/sites-available/tracardi`

3. **Obtain Let's Encrypt certificate**
   ```bash
   sudo certbot --nginx -d tracardi.yourdomain.com
   # OR use IP with DNS challenge if no domain
   ```

4. **Update Resend webhook**
   - New endpoint: `https://<vm-ip-or-domain>/tracker`
   - Update via Resend dashboard or API

5. **Codify in IaC** (CRITICAL per AGENTS.md)
   - Update `infra/tracardi/cloud-init/tracardi-vm.yaml.tftpl`
   - Add nginx install and config to cloud-init
   - Test `terraform plan` to verify no drift

**Verification Criteria:**
- [ ] HTTPS endpoint responds with valid certificate
- [ ] Resend webhook updated and receiving events
- [ ] Cloud-init template updated
- [ ] Terraform plan shows no unexpected changes

---

### Objective 2: Cost Optimization (Target: <€150/month)

**Status:** `reported` - Current estimated cost €163-218/month  
**Savings Needed:** ~€20-70/month  
**Goal:** Reduce monthly Azure spend to under €150

**Current Cost Breakdown:**

| Resource | SKU | Monthly Cost | Optimization |
|----------|-----|--------------|--------------|
| Tracardi VM | Standard_B2s | ~€35 | Keep (critical) |
| Data VM | Standard_B1ms | ~€13 | Consider B1ls (~€8) |
| Container App | Scale-to-zero | ~€5-15 | Keep (already optimized) |
| PostgreSQL | Standard_B1ms | ~€15-20 | Keep (in use) |
| **Azure AI Search** | **Basic** | **~€60** | **→ Free tier (save €60)** |
| OpenAI | S0 + gpt-4o-mini | ~€5-20 | Usage-dependent |
| Storage/Network | | ~€10-15 | Minimal |
| **Log Analytics** | **3 workspaces** | **~€20-40** | **→ Consolidate (save €20-30)** |
| **TOTAL** | | **€163-218** | **Optimized: ~€110-140** |

**Recommended Optimizations (in order of impact):**

1. **Azure AI Search: Downgrade Basic → Free** (`observed` - check index size first)
   - Free tier: 50MB limit, 3 indexes max
   - Check current usage before downgrading
   - Command: `az search service show --name cdpmerged-search --resource-group rg-cdpmerged-fast`
   - If index size < 50MB, migrate to Free tier
   - **Savings: ~€60/month**

2. **Consolidate Log Analytics Workspaces** (`reported` - 3 workspaces found)
   - Identify which workspaces are actively used
   - Migrate logs to single workspace
   - Delete unused workspaces
   - **Savings: ~€20-30/month**

3. **Data VM: Downsize B1ms → B1ls** (optional, lower impact)
   - B1ls has lower CPU/memory but may suffice for Elasticsearch
   - Test performance after change
   - **Savings: ~€5-8/month**

**IaC Compliance for Cost Changes:**
- Update `infra/terraform/variables.tf` or `terraform.tfvars`
- Document cost changes in `PROJECT_STATE.yaml`
- Update `docs/COST_OPTIMIZATION_SUMMARY.md`

**Verification Criteria:**
- [ ] Current costs documented with `az` commands
- [ ] Azure AI Search tier checked and optimized
- [ ] Log Analytics workspaces consolidated
- [ ] Monthly estimate recalculated and <€150 confirmed
- [ ] All changes codified in Terraform

---

### Objective 3: Verify Profile Ingestion

**Status:** `assumed` - Not verified in current session  
**Goal:** Confirm profiles are being ingested into Tracardi and/or PostgreSQL

**Background:**
- KBO import was running (1.94M companies)
- Tracardi has 10k profiles (from previous verification)
- PostgreSQL schema v2.2 ready but may be empty

**Verification Steps:**

1. **Check PostgreSQL company count:**
   ```bash
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM companies;"
   ```

2. **Check Tracardi profile count:**
   ```bash
   curl -u admin@admin.com:admin \
     http://137.117.212.154:8686/profiles/records
   ```

3. **Check KBO import status:**
   ```bash
   tail -f logs/kbo_import_full.log
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM companies;"
   ```

4. **Verify profile sync between systems:**
   - Are KBO companies appearing as Tracardi profiles?
   - Check Tracardi event sources and workflows
   - Tracardi GUI: http://137.117.212.154:8787

**Expected State:**
- PostgreSQL: 1.94M companies (if import completed)
- Tracardi: 10k+ profiles (from KBO sync or direct import)

**If Discrepancy Found:**
- Check if KBO import is still running
- Verify Tracardi-PostgreSQL sync is configured
- Review Tracardi workflows for profile creation

**Verification Criteria:**
- [ ] PostgreSQL company count verified
- [ ] Tracardi profile count verified
- [ ] KBO import status checked
- [ ] Any discrepancies documented in `PROJECT_STATE.yaml`
- [ ] Follow-up actions created if needed

---

## Critical: IaC Compliance Reminder

Per AGENTS.md §Infrastructure as Code (IaC) Compliance:

> **MANDATORY:** All infrastructure changes, configuration patches, and hotfixes must be codified in the IaC templates.

**For this session:**
1. Nginx changes → Update `infra/tracardi/cloud-init/tracardi-vm.yaml.tftpl`
2. Cost optimizations → Update Terraform variables
3. After SSH changes, run `terraform plan` to verify no drift
4. Document in `PROJECT_STATE.yaml` with `iac_compliance: enforced` label

**Hotfix Pattern:**
1. First apply via SSH to verify the fix
2. Immediately codify in cloud-init templates
3. Test `terraform plan`
4. Document in `PROJECT_STATE.yaml`

---

## Completion Requirements

After completing work:
1. Append session result to `WORKLOG.md`
2. Update `PROJECT_STATE.yaml` with:
   - SSL endpoint status (observed)
   - Cost optimization results (observed)
   - Profile ingestion counts (observed)
   - IaC compliance confirmation
3. Update `NEXT_ACTIONS.md` if task status changed
4. Update `STATUS.md` if summary materially changed
5. Commit changes per Git Workflow in AGENTS.md

---

## Quick Reference

| Resource | URL/Command |
|----------|-------------|
| Tracardi GUI | http://137.117.212.154:8787 |
| Tracardi API | http://137.117.212.154:8686 |
| PostgreSQL | `psql $DATABASE_URL` |
| Resend Dashboard | https://resend.com/webhooks |
| Current Tunnel | https://cuddly-bats-fail.loca.lt |
| KBO Import Log | `tail -f logs/kbo_import_full.log` |

---

## Handoff Output

**Task:** Nginx SSL + Cost Optimization + Profile Ingestion Verification  
**Status:** PAUSED - Ready for next session

### What changed
- Created handoff document with detailed implementation plan
- Documented current cost structure and optimization path
- Outlined profile ingestion verification steps

### Verification
- Current tunnel verified: `https://cuddly-bats-fail.loca.lt` (`observed`)
- Cost analysis: €163-218/month current, €110-140 target (`reported`)
- KBO import status: Running 70% at time of handoff (`reported`)

### Follow-up
1. **Implement Nginx + Let's Encrypt** on Tracardi VM (codify in cloud-init)
2. **Optimize costs**: Downgrade Azure Search, consolidate Log Analytics workspaces
3. **Verify profile ingestion**: Check PostgreSQL and Tracardi counts
4. **Update all state files** per AGENTS.md Completion Minimum
