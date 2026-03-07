# CDP_Merged Operational SOP

**Document:** Operational Standard Operating Procedures  
**Version:** 1.0  
**Date:** 2026-03-01  
**Status:** Active

---

## 1. Quick Start Commands

### Default Enrichment (Fast - Skip Optional Phase 2)
```bash
# Run all enrichment except optional derived labels
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
bash run_enrichment_full.sh

# Or resume from checkpoint
bash continue_enrichment.sh
```

### With Derived Labels (Slower - Enable Phase 2)
```bash
# Only if you need human-readable industry labels
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
bash run_enrichment_full.sh --with-derived-labels
bash continue_enrichment.sh --with-derived-labels
```

---

## 2. Field Ownership Reference

| Data Field | Core Ingestion | Optional Phase 2 | Notes |
|------------|----------------|------------------|-------|
| **Enterprise Number** | ✅ | Formatting | Raw number in core, normalized format in Phase 2 |
| **Company Name** | ✅ | — | From denomination.csv |
| **Legal Form** | ✅ | — | From enterprise.csv (JuridicalForm) |
| **Status** | ✅ | — | From enterprise.csv (Status) |
| **Start Date** | ✅ | — | From enterprise.csv (StartDate) |
| **Address** | ✅ | — | From address.csv |
| **NACE Codes** | ✅ | — | From activity.csv |
| **Industry Sector Label** | ❌ | ✅ | Human-readable (e.g., "Software" from 62.01) |
| **Company Size Bucket** | ❌ | ✅ | Estimated Small/Medium/Large |

**Key Insight:** Phase 2 only adds derived labels, not core registry data. Skip it unless you specifically need human-readable industry names.

---

## 3. Enrichment Phases

### Phase 1: Contact Validation (Optional)
- **Use Case:** Profiles with email/phone
- **Cost:** €0
- **Time:** ~2 hours for 516K
- **Adds:** Contact quality scores, normalized formats

### Phase 2: CBE Derived Labels (Optional - Skip for Speed)
- **Use Case:** Only if human-readable labels needed
- **Cost:** €0
- **Time:** ~40 hours for 1.8M profiles
- **Adds:** Industry sector labels, size estimates
- **Skip If:** You can work with raw NACE codes

### Phase 3: Website Discovery (Recommended)
- **Use Case:** All profiles
- **Cost:** €0
- **Time:** ~4 hours for 516K
- **Adds:** Discovered websites from email domains

### Phase 4: AI Descriptions (Optional)
- **Use Case:** Unique NACE codes only
- **Cost:** ~€20-40
- **Time:** ~8 hours
- **Adds:** Business descriptions from NACE

### Phase 5: Geocoding (Slow)
- **Use Case:** Location-based queries
- **Cost:** €0
- **Time:** ~6 days (1 req/sec limit)
- **Adds:** Latitude/longitude coordinates

---

## 4. Decision Matrix

| Goal | Skip Phase 2 | Enable Phase 2 |
|------|--------------|----------------|
| Speed priority | ✅ Default | ❌ 40+ hours |
| Raw NACE sufficient | ✅ | ❌ |
| Human labels needed | ❌ | ✅ |
| Cost sensitive | ✅ | ✅ (both €0) |
| Storage limited | ✅ Less writes | ❌ More writes |

---

## 5. Monitoring Commands

### Check Progress
```bash
# View checkpoint
cat data/progress/streaming_last_offset_phase2_cbe_integration.json

# Check process running
pgrep -f "python.*enrich" && echo "Running" || echo "Stopped"

# View recent logs
tail -20 logs/enrichment_phase2_live.log | jq -r '[.timestamp[11:19], .event[0:60]] | @tsv'
```

### Live Monitor Script
```bash
bash monitor.sh
```

---

## 6. Troubleshooting

### Process Exited Early
1. Check exit reason in logs:
   ```bash
   grep "exit_reason" logs/enrichment_phase2_live.log | tail -5
   ```
2. If checkpoint exists, resume with:
   ```bash
   bash continue_enrichment.sh
   ```

### Need to Restart from Beginning
```bash
# Remove checkpoint
rm data/progress/streaming_last_offset_phase2_cbe_integration.json

# Restart
bash run_enrichment_full.sh [--with-derived-labels]
```

### Database Connection Issues
```bash
# Test PostgreSQL connection
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
poetry run python -c "
import asyncio
from src.services.postgresql_client import PostgreSQLClient
async def test():
    db = PostgreSQLClient()
    await db.connect()
    count = await db.get_profile_count()
    print(f'Connected: {count} profiles')
    await db.close()
asyncio.run(test())
"
```

---

## 7. Architecture Decisions

### Tracardi Remains Primary (ADR-001)
- PostgreSQL = enrichment/secondary store
- Tracardi = event hub + primary read model
- Sync job: `scripts/sync_tracardi_to_postgres.py`

### Phase 2 is Optional (2026-03-01)
- Core KBO data complete after ingestion
- Phase 2 only adds derived convenience labels
- Default scripts skip Phase 2 for speed
- Enable with `--with-derived-labels` flag

---

## 8. Cost Tracking

```bash
# View current costs
cat data/costs.json | jq

# Budget: €150/month
# Typical spend: €20-50 for full enrichment
```

---

## 9. Performance Benchmarks

| Phase | Records | Time | Rate |
|-------|---------|------|------|
| Core Ingestion | 1.8M | ~2 hours | ~250 rec/sec |
| Phase 2 (CBE) | 1.8M | ~40 hours | ~12 rec/sec |
| Website Discovery | 516K | ~4 hours | ~36 rec/sec |
| AI Descriptions | Unique NACE | ~8 hours | Varies |
| Geocoding | 516K | ~6 days | 1 rec/sec |

---

## 10. Revision History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-03-01 | 1.0 | Initial SOP, Phase 2 optional | Jarvis |

---

*For detailed architecture, see docs/ARCHITECTURE_DECISION_RECORD.md*
*For data field lineage, see docs/KBO_INGESTION.md*
