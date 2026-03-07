# Handover: Tracardi Initialized - Ready for Profile Sync (Option B)

**Date:** 2026-03-01  
**Status:** Tracardi deployed, initialized, and ready for profile sync ✅  
**Next Task:** Sync 10,000 KBO profiles (East Flanders IT companies >10 employees) to Tracardi

---

## 🎯 Current State

### Tracardi Infrastructure (COMPLETE)
| Component | Status | Details |
|-----------|--------|---------|
| **Tracardi VM** | ✅ Running | Standard_B2s at 137.117.212.154 |
| **Data VM** | ✅ Running | Standard_B1ms with ES + Redis |
| **Tracardi GUI** | ✅ Initialized | Dashboard accessible and logged in |
| **PostgreSQL** | ✅ Running | 1,813,016 KBO companies |
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

## 📋 Next Task: Sync POC-Relevant Profiles to Tracardi (Option B)

### Objective
Sync **10,000 active KBO companies** that match the POC use case test criteria:
- ✅ **Status:** Active ('AC' - not dissolved/liquidated)
- ✅ **Location:** East Flanders (provincie = "Oost-Vlaanderen")
- ✅ **Industry:** IT services (relevant NACE codes)
- ✅ **Size:** >10 employees

### Why This Selection?
This matches the POC use case from the business case:
> *"Maak een segment van vennootschappen in Oost-Vlaanderen in IT-services met >10 werknemers"*

This tests:
1. NL→segment query translation
2. Segment creation in Tracardi
3. Segment push to Flexmail
4. End-to-end POC flow

---

## 🔧 Implementation Steps

### Step 1: Identify NACE Codes for IT Services
```sql
-- NACE codes for IT services (to filter in PostgreSQL)
-- 62: Computer programming, consultancy
-- 63: Information service activities
-- 582: Software publishing
-- 61: Telecommunications
```

### Step 2: Query PostgreSQL for POC-Eligible Companies

```sql
-- Query to get POC-relevant companies
SELECT 
    id,
    company_name,
    kbo_number,
    address,
    city,
    postal_code,
    province,
    nace_code,
    nace_description,
    employee_count,
    legal_form,
    status
FROM profiles
WHERE status = 'AC'
  AND province = 'Oost-Vlaanderen'
  AND employee_count > 10
  AND (nace_code LIKE '62%' 
       OR nace_code LIKE '63%' 
       OR nace_code LIKE '58.2%'
       OR nace_code LIKE '61%')
ORDER BY employee_count DESC, company_name
LIMIT 10000;
```

### Step 3: Create Sync Script

Create `scripts/sync_postgresql_to_tracardi.py`:

```python
#!/usr/bin/env python3
"""
Sync POC-relevant KBO profiles from PostgreSQL to Tracardi
- East Flanders IT companies with >10 employees
- 10,000 profiles for POC testing
"""
import asyncio
import os
import sys
import httpx
sys.path.insert(0, '/home/ff/.openclaw/workspace/repos/CDP_Merged')

from src.services.postgresql_client import PostgreSQLClient

# Configuration
TRACARDI_API_URL = os.getenv("TRACARDI_API_URL", "http://137.117.212.154:8686")
TRACARDI_USERNAME = "admin@cdpmerged.local"
TRACARDI_PASSWORD = "<redacted>"
BATCH_SIZE = 100
LIMIT = 10000

# NACE codes for IT services
IT_NACE_PREFIXES = ['62', '63', '58.2', '61']

async def get_poc_profiles(pg_client):
    """Get POC-relevant companies from PostgreSQL."""
    query = """
    SELECT 
        id,
        company_name,
        kbo_number,
        address,
        city,
        postal_code,
        province,
        nace_code,
        nace_description,
        employee_count,
        legal_form,
        status
    FROM profiles
    WHERE status = 'AC'
      AND province = 'Oost-Vlaanderen'
      AND employee_count > 10
      AND (
          nace_code LIKE '62%%' 
          OR nace_code LIKE '63%%' 
          OR nace_code LIKE '58.2%%'
          OR nace_code LIKE '61%%'
      )
    ORDER BY employee_count DESC, company_name
    LIMIT $1;
    """
    return await pg_client.fetch(query, LIMIT)

def transform_to_tracardi(profile):
    """Transform PostgreSQL profile to Tracardi format."""
    return {
        "id": str(profile["kbo_number"]),  # Use KBO as unique ID
        "traits": {
            "company_name": profile.get("company_name"),
            "kbo_number": profile.get("kbo_number"),
            "address": profile.get("address"),
            "city": profile.get("city"),
            "postal_code": profile.get("postal_code"),
            "province": profile.get("province"),
            "nace_code": profile.get("nace_code"),
            "nace_description": profile.get("nace_description"),
            "employee_count": profile.get("employee_count"),
            "legal_form": profile.get("legal_form"),
            "status": profile.get("status"),
            "data_source": "KBO",
            "segment_tags": ["poc_test", "oost_vlaanderen", "it_services"]
        },
        "metadata": {
            "system": {
                "inserted": profile.get("created_at"),
                "last_visit": profile.get("updated_at")
            }
        }
    }

async def get_tracardi_token():
    """Get authentication token from Tracardi."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TRACARDI_API_URL}/user/token",
            data={
                "username": TRACARDI_USERNAME,
                "password": TRACARDI_PASSWORD,
                "grant_type": "password"
            }
        )
        response.raise_for_status()
        return response.json()["access_token"]

async def import_profiles_to_tracardi(profiles, token):
    """Import profiles to Tracardi in batches."""
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        for i in range(0, len(profiles), BATCH_SIZE):
            batch = profiles[i:i+BATCH_SIZE]
            tracardi_profiles = [transform_to_tracardi(p) for p in batch]
            
            response = await client.post(
                f"{TRACARDI_API_URL}/profile/import",
                json={"profiles": tracardi_profiles},
                headers=headers
            )
            
            if response.status_code == 200:
                print(f"✅ Imported batch {i//BATCH_SIZE + 1}/{(len(profiles)-1)//BATCH_SIZE + 1}")
            else:
                print(f"❌ Error importing batch: {response.text}")

async def verify_sync(token):
    """Verify profiles were synced."""
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get(
            f"{TRACARDI_API_URL}/profiles/count",
            headers=headers
        )
        if response.status_code == 200:
            count = response.json().get("count", 0)
            print(f"\n📊 Total profiles in Tracardi: {count}")
            return count
        return 0

async def main():
    print("=" * 60)
    print("POC Profile Sync: East Flanders IT Companies >10 employees")
    print("=" * 60)
    
    # Connect to PostgreSQL
    pg_client = PostgreSQLClient()
    await pg_client.connect()
    
    # Get POC-relevant profiles
    print("\n🔍 Querying PostgreSQL for POC profiles...")
    profiles = await get_poc_profiles(pg_client)
    print(f"📋 Found {len(profiles)} matching profiles")
    
    await pg_client.close()
    
    if len(profiles) == 0:
        print("❌ No matching profiles found. Check query criteria.")
        return
    
    # Get Tracardi token
    print("\n🔐 Authenticating with Tracardi...")
    token = await get_tracardi_token()
    print("✅ Authenticated")
    
    # Import to Tracardi
    print(f"\n📤 Importing {len(profiles)} profiles to Tracardi...")
    await import_profiles_to_tracardi(profiles, token)
    
    # Verify
    print("\n🔍 Verifying sync...")
    count = await verify_sync(token)
    
    print("\n" + "=" * 60)
    print("SYNC COMPLETE")
    print("=" * 60)
    print(f"Expected: {len(profiles)}")
    print(f"In Tracardi: {count}")
    
    if count >= len(profiles) * 0.9:  # 90% success threshold
        print("✅ SUCCESS: Most profiles synced correctly")
    else:
        print("⚠️ WARNING: Some profiles may not have synced")

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 4: Run the Sync

```bash
cd /home/ff/.openclaw/workspace/repos/CDP_Merged

# Set environment
export TRACARDI_API_URL="http://137.117.212.154:8686"

# Run sync
poetry run python scripts/sync_postgresql_to_tracardi.py
```

---

## ✅ Completion Criteria

| Criteria | Target | Verification |
|----------|--------|--------------|
| Profiles synced | 10,000 | Script output shows count |
| Tracardi profile count | ~10,000 | API call `/profiles/count` |
| Profiles visible in GUI | Yes | Browse in Tracardi GUI |
| East Flanders filter | All | Check `province` trait |
| IT services filter | All | Check `nace_code` trait |
| >10 employees | All | Check `employee_count` trait |

### Verification Commands

```bash
# 1. Check Tracardi profile count
curl http://137.117.212.154:8686/profiles/count \
  -H "Authorization: Bearer <token>"

# 2. Query specific profile
curl "http://137.117.212.154:8686/profiles/search" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": {"traits.province": "Oost-Vlaanderen"}}'

# 3. Verify in GUI
# Open http://137.117.212.154:8787 → Profiles → Verify count and traits
```

---

## 📁 Key Files Reference

| File | Purpose |
|------|---------|
| `STATUS.md` | Current deployment status |
| `NEXT_ACTIONS.md` | Detailed next steps (Action #3) |
| `infra/tracardi/terraform.tfvars` | Infrastructure configuration |
| `logs/tracardi_redeploy_20260301T155303Z.log` | Deployment evidence |
| `scripts/sync_postgresql_to_tracardi.py` | Sync script (to be created) |

---

## 🔧 Quick Commands

```bash
# Get Tracardi password
cd infra/tracardi && terraform output -raw tracardi_admin_password

# Test Tracardi API
curl http://137.117.212.154:8686/

# Test PostgreSQL connection
poetry run python scripts/test_postgresql.py

# Query KBO data count
poetry run python -c "
import asyncio
from src.services.postgresql_client import PostgreSQLClient
async def main():
    client = PostgreSQLClient()
    await client.connect()
    # Count POC-relevant companies
    result = await client.fetch(\"\"\"
        SELECT COUNT(*) as count 
        FROM profiles 
        WHERE status = 'AC'
          AND province = 'Oost-Vlaanderen'
          AND employee_count > 10
          AND (nace_code LIKE '62%' 
               OR nace_code LIKE '63%' 
               OR nace_code LIKE '58.2%'
               OR nace_code LIKE '61%')
    \"\"\")
    print(f'POC-relevant companies: {result[0][\"count\"]}')
    await client.close()
asyncio.run(main())
"
```

---

## ⚠️ Important Notes

1. **KBO Data Only:** Only syncing public KBO data - no PII or customer data
2. **POC Scope:** This matches the "East Flanders IT >10 employees" use case
3. **Tracardi ID:** Using KBO number as unique profile ID
4. **Traits:** All KBO fields mapped to Tracardi traits for segment filtering
5. **Tags:** Added `poc_test`, `oost_vlaanderen`, `it_services` for easy filtering

---

## 🎯 Success Metrics

| Metric | Target | How to Verify |
|--------|--------|---------------|
| Sync duration | < 30 minutes | Script timer |
| Success rate | > 90% | Compare expected vs actual count |
| Trait completeness | 100% | Verify all KBO fields in Tracardi |
| GUI visibility | Yes | Manual check in Tracardi GUI |

---

## 📋 Documentation Updates Required

After completing the sync, update:

1. **STATUS.md**
   - Mark "PostgreSQL → Tracardi sync" as complete
   - Add profile count to status table

2. **NEXT_ACTIONS.md**
   - Mark Action #3 complete
   - Move to Action #4 (Flexmail Integration)

3. **CHANGELOG.md**
   - Add entry: "Synced 10,000 POC profiles to Tracardi"

4. **Evidence Log**
   - Create: `logs/profile_sync_YYYYMMDDTHHMMSS.log`

---

*Handover complete. Ready to sync POC-relevant KBO profiles to Tracardi.*
