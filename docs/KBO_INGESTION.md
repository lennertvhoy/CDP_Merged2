# KBO Data Ingestion Documentation

## Overview

This document describes how to ingest KBO (Kruispuntbank Ondernemingen) data into Tracardi CDP.

Live credentials are intentionally not stored in the repo. Retrieve current values from the approved secret source before using this guide.

## Prerequisites

1. Tracardi VM running at `52.148.232.140:8686`
2. MySQL database running with Tracardi schema
3. Valid Tracardi credentials
4. Python 3.x with `requests` library

## Authentication

### Current Credentials
- **Username:** Retrieve from the approved secret source
- **Password:** Retrieve from the approved secret source
- **Token Endpoint:** `POST /user/token` (form-urlencoded)

### Resetting Password (if needed)

If authentication fails, reset the password directly in MySQL:

```bash
# SSH to VM (via Azure run-command)
az vm run-command invoke \
  --command-id RunShellScript \
  --name vm-tracardi-cdpmerged-prod \
  --resource-group RG-CDPMERGED-FAST \
  --scripts "cd /opt/tracardi && docker-compose exec -T tracardi-api python -c 'from tracardi.domain.user import User; print(User.encode_password(\"NEW_PASSWORD\"))'"

# Update MySQL with the generated hash
az vm run-command invoke \
  --command-id RunShellScript \
  --name vm-tracardi-cdpmerged-prod \
  --resource-group RG-CDPMERGED-FAST \
  --scripts "cd /opt/tracardi && docker-compose -f docker-compose.yml -f docker-compose.mysql-override.yml exec -T mysql mysql -u root -proot tracardi -e 'UPDATE user SET password=\"HASH_FROM_ABOVE\" WHERE email=\"admin@cdpmerged.local\";'"

# Update Container App secret
az containerapp secret set \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --secrets tracardi-password=NEW_PASSWORD

# Restart Container App
az containerapp revision restart \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --revision ca-cdpmerged-fast--0000011
```

## Data Structure

### Source Files

Located in `/home/ff/.openclaw/workspace/repos/CDP_Merged/data/kbo/`:

| File | Fields | Description |
|------|--------|-------------|
| `enterprise.csv` | EnterpriseNumber, Status, JuridicalForm, StartDate | Core entity data |
| `denomination.csv` | EntityNumber, Denomination | Company names |
| `address.csv` | EntityNumber, TypeOfAddress, CountryNL, StreetNL, HouseNumber, Zipcode, MunicipalityNL | Location data |
| `activity.csv` | EntityNumber, NaceCode | Business activities (1:N) |
| `contact.csv` | EntityNumber, ContactType, Value | Email/Telephone contacts |

### Tracardi Profile Mapping

```json
{
  "id": "XXXX.XXX.XXX",          // Formatted enterprise number
  "ids": ["XXXXXXXXXX"],          // Raw enterprise number
  "traits": {
    "kbo": {
      "enterpriseNumber": "...",
      "denominations": [...],
      "juridicalForm": "...",
      "status": "...",
      "startDate": "...",
      "addresses": [...],
      "activities": [...],
      "contacts": {...}
    }
  },
  "pii": {
    "name": "...",
    "email": "...",
    "telephone": "..."
  }
}
```

## Running Ingestion

### Full Ingestion

```bash
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
python3 src/ingestion/kbo_ingest.py
```

### Environment Variables

You can override defaults with environment variables:

```bash
export TRACARDI_HOST="http://52.148.232.140:8686"
export TRACARDI_USER="your-tracardi-username"
export TRACARDI_PASS="<redacted>"
python3 src/ingestion/kbo_ingest.py
```

## Verification

### Check Profile Count

```bash
curl -s http://52.148.232.140:8686/profile/count \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Query Specific Profile

```bash
curl -s "http://52.148.232.140:8686/profile/XXXX.XXX.XXX" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Search Profiles

```bash
curl -s -X POST "http://52.148.232.140:8686/profiles/select" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}'
```

## Container App Status

### Check Logs

```bash
az containerapp logs show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --tail 50
```

### Verify Configuration

```bash
az containerapp show \
  --name ca-cdpmerged-fast \
  --resource-group rg-cdpmerged-fast \
  --query "properties.template.containers[0].env"
```

## Troubleshooting

### Authentication Errors

1. Verify password hash in MySQL:
   ```bash
   az vm run-command invoke --command-id RunShellScript \
     --name vm-tracardi-cdpmerged-prod --resource-group RG-CDPMERGED-FAST \
     --scripts "cd /opt/tracardi && docker-compose -f docker-compose.yml -f docker-compose.mysql-override.yml exec -T mysql mysql -u root -proot tracardi -e 'SELECT email FROM user;'"
   ```

2. Test authentication directly:
   ```bash
   curl -s -X POST http://52.148.232.140:8686/user/token \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d 'username=YOUR_USERNAME&password=YOUR_PASSWORD'
   ```

### Data Not Appearing

1. Check if profiles exist in Elasticsearch:
   ```bash
   curl -s http://52.148.232.140:9200/_cat/indices | grep profile
   ```

2. Verify the ingestion script output for errors

3. Check Tracardi logs:
   ```bash
   az vm run-command invoke --command-id RunShellScript \
     --name vm-tracardi-cdpmerged-prod --resource-group RG-CDPMERGED-FAST \
     --scripts "cd /opt/tracardi && docker-compose logs tracardi-api --tail 50"
   ```

## Performance Notes

- Profile counts and deployment details should be re-verified against `PROJECT_STATE.yaml` before use
- Sample ingestion: 5 profiles in ~2 seconds
- Bulk import endpoint: `POST /profiles/import`
- Recommended batch size: 100-1000 profiles per request

## Field Ownership: Core Ingestion vs Optional Derived Enrichment

This table clarifies which data fields are available immediately after KBO ingestion (core) vs added by optional enrichment phases:

| Field | Source File | Available After | Phase 2 (Derived) Adds |
|-------|-------------|-----------------|------------------------|
| **Enterprise Number** | `enterprise.csv` | ✅ Core ingestion | Format normalization |
| **Company Name** | `denomination.csv` | ✅ Core ingestion | Nothing |
| **Legal Form** | `enterprise.csv` | ✅ Core ingestion | Nothing |
| **Status** | `enterprise.csv` | ✅ Core ingestion | Nothing |
| **Start Date** | `enterprise.csv` | ✅ Core ingestion | Nothing |
| **Address** | `address.csv` | ✅ Core ingestion | Nothing |
| **NACE Codes** | `activity.csv` | ✅ Core ingestion | Industry label mapping |
| **Industry Sector** | N/A | ❌ Not available | ✅ Derived from NACE |
| **Company Size Bucket** | N/A | ❌ Not available | ✅ Estimated from employees |

### Key Insight
**Phase 2 (CBE Integration) is optional.** All core registry data (NACE codes, legal form, dates) is already present after initial KBO ingestion. Phase 2 only adds:
- Human-readable industry labels (e.g., "Software" from NACE 62.01)
- Heuristic company size buckets (Small/Medium/Large estimates)
- KBO number formatting normalization

**Recommendation:** Skip Phase 2 if you need speed and can work with raw NACE codes. Enable it only when human-readable labels are required.

## Future Enhancements

1. **Data Cleanup**: Implement validation rules from `DATA_CLEANUP_ENRICHMENT_PLAN.md`
2. **Geocoding**: Add lat/long coordinates via Nominatim
3. **AI Descriptions**: Generate company descriptions via Azure OpenAI
4. **Website Discovery**: Auto-discover websites from email domains
5. **Incremental Updates**: Only process new/changed records

## VM Access

**VM Name:** `vm-tracardi-cdpmerged-prod`
**Resource Group:** `RG-CDPMERGED-FAST`
**Location:** `52.148.232.140`

### Azure Run-Command (preferred for automation)

```bash
az vm run-command invoke \
  --command-id RunShellScript \
  --name vm-tracardi-cdpmerged-prod \
  --resource-group RG-CDPMERGED-FAST \
  --scripts "YOUR_COMMAND_HERE"
```

### Docker Compose Location

```
/opt/tracardi/docker-compose.yml
/opt/tracardi/docker-compose.mysql-override.yml
```

### MySQL Access

```bash
docker-compose -f docker-compose.yml -f docker-compose.mysql-override.yml exec mysql mysql -u root -proot tracardi
```

---

*Document generated: 2026-02-25*
*Version: 1.0*
