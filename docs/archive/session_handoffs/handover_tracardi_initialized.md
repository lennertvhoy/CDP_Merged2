# Handover: Tracardi Initialized - Ready for Profile Sync

**Date:** 2026-03-01  
**Status:** Tracardi deployed and initialized ✅  
**Next Task:** PostgreSQL → Tracardi profile sync

---

## 🎯 Current State

### Tracardi Infrastructure (COMPLETE)
| Component | Status | Details |
|-----------|--------|---------|
| **Tracardi VM** | ✅ Running | Standard_B2s at 137.117.212.154 |
| **Data VM** | ✅ Running | Standard_B1ms with ES + Redis |
| **Tracardi GUI** | ✅ Initialized | Dashboard accessible and logged in |
| **PostgreSQL** | ✅ Running | 1,813,016 companies |
| **Container App** | ✅ Aligned | Auth configured correctly |

### Tracardi Admin Credentials (VERIFIED)
| Field | Value |
|-------|-------|
| **Email** | `admin@cdpmerged.local` |
| **Password** | `<redacted>` |
| **Installation Token** | `<redacted>` |

### Endpoints
| Service | URL |
|---------|-----|
| Tracardi API | http://137.117.212.154:8686 |
| Tracardi GUI | http://137.117.212.154:8787 |
| Elasticsearch | http://10.57.3.10:9200 (private) |

---

## 📋 Next Task: PostgreSQL → Tracardi Sync (Action #3)

**Objective:** Sync 10,000 most active profiles from PostgreSQL to Tracardi

**Why:** Tracardi needs profile data to enable segment creation and Flexmail integration

**Reference:** See `NEXT_ACTIONS.md` Action #3 for detailed script

### Quick Start Commands

```bash
# 1. Set environment variables
export TRACARDI_API_URL="http://137.117.212.154:8686"
export TRACARDI_TOKEN="<get from Tracardi GUI or terraform output>"

# 2. Create and run sync script
# (See NEXT_ACTIONS.md for full script)
poetry run python scripts/sync_postgresql_to_tracardi.py
```

### Success Criteria
- [ ] 10,000 profiles imported to Tracardi
- [ ] Profiles visible in Tracardi GUI
- [ ] Profile count endpoint returns ~10,000

---

## 📁 Key Files Reference

| File | Purpose |
|------|---------|
| `STATUS.md` | Current deployment status |
| `NEXT_ACTIONS.md` | Detailed next steps (Action #3) |
| `infra/tracardi/terraform.tfvars` | Infrastructure configuration |
| `logs/tracardi_redeploy_20260301T155303Z.log` | Deployment evidence |

---

## 🔧 Quick Commands

```bash
# Get Tracardi credentials
cd infra/tracardi && terraform output -raw tracardi_admin_password

# Test Tracardi API
curl http://137.117.212.154:8686/

# SSH to Tracardi VM
ssh azureuser@137.117.212.154

# Check Docker containers (from VM)
docker ps

# Test PostgreSQL connection
poetry run python scripts/test_postgresql.py
```

---

## ⚠️ Important Notes

1. **Username Format:** Use `admin@cdpmerged.local` (not just `admin`)
2. **Password:** Available via `terraform output -raw tracardi_admin_password`
3. **Installation Token:** Available via `terraform output -raw tracardi_installation_token`
4. **GUI Access:** http://137.117.212.154:8787 (from office IP 78.21.222.70/32)

---

## 🎯 Success Metrics for Next Session

| Metric | Target |
|--------|--------|
| Profiles synced | 10,000 |
| Sync duration | < 30 minutes |
| Tracardi profile count | ~10,000 |

---

*Handover complete. Tracardi ready for profile sync.*
