# Tracardi Data Cleanup - Deliverables Summary

## Overview
This package contains a comprehensive data cleanup and enrichment strategy for 516K+ existing Tracardi profiles containing Belgian company (KBO) data.

## Files Delivered

### 1. Documentation
| File | Description |
|------|-------------|
| `docs/DATA_CLEANUP_IMPLEMENTATION.md` | Complete 30,000+ word implementation plan with strategies, code samples, risk assessment, and cost analysis |

### 2. Python Scripts
| File | Purpose |
|------|---------|
| `scripts/data_cleanup/profile_analyzer.py` | Phase 1: Analyze current data quality, field population, duplicates |
| `scripts/data_cleanup/bulk_cleanup.py` | Phase 2: Bulk validation and normalization |
| `scripts/data_cleanup/deduplicate.py` | Phase 3: Merge duplicate profiles by KBO |
| `scripts/data_cleanup/backup_and_rollback.sh` | Backup, restore, and progress monitoring utilities |

## Quick Start

### Step 1: Data Analysis
```bash
cd /home/ff/.openclaw/workspace/CDP_Merged/scripts/data_cleanup
python3 profile_analyzer.py
```

### Step 2: Test Cleanup (100 profiles)
```bash
# First, update TOKEN in bulk_cleanup.py
python3 bulk_cleanup.py --test
```

### Step 3: Preview Duplicates
```bash
python3 deduplicate.py --preview
```

### Step 4: Create Backup
```bash
./backup_and_rollback.sh backup
```

### Step 5: Full Cleanup
```bash
python3 bulk_cleanup.py
```

### Step 6: Deduplication (Dry Run First)
```bash
python3 deduplicate.py        # Dry run
python3 deduplicate.py --live # Execute
```

## Key Findings from API Analysis

### Profile Structure
```
Profile
├── id (primary key)
├── data
│   ├── identifier.id         # KBO number stored here
│   ├── contact
│   │   ├── email.main        # Primary email
│   │   ├── email.business    # Business email
│   │   ├── phone.main        # Primary phone
│   │   ├── phone.business    # Business phone
│   │   └── address.*         # street, postcode, town, country
│   └── job.company
│       ├── name              # Company name
│       ├── size              # Company size
│       └── country
└── traits                    # Custom fields for enrichment
```

### Authentication Issue
**Note:** The provided credentials (`admin@cdpmerged.local` / `<redacted>`) did not authenticate successfully during testing. You may need to:
1. Verify the correct username format
2. Check if the password has changed
3. Generate a new token via the Tracardi UI

Once you have working credentials, update the `TOKEN` variable in the Python scripts.

### Alternative: Direct Elasticsearch Access
If Tracardi API authentication continues to fail, you can run the scripts directly on the Tracardi server:
```bash
ssh user@52.148.232.140
cd /path/to/scripts
export ES_HOST=http://localhost:9200
python3 profile_analyzer.py
```

## Implementation Timeline

| Phase | Duration | Activity |
|-------|----------|----------|
| 1 | 2-4 hours | Data profiling and analysis |
| 2 | 1 hour | Test on 100 profiles |
| 3 | 3-4 hours | Full cleanup (516K profiles) |
| 4 | 2-3 hours | Deduplication |
| 5 | 1 hour | Validation and verification |
| **Total** | **~12 hours** | With monitoring and safety checks |

## Cost Analysis

| Item | Cost |
|------|------|
| Compute | €0 (use existing server) |
| Storage | €0 (local backup) |
| APIs | €0 (open source tools) |
| **Total** | **€0** |

Well within the €150 budget.

## Risk Summary

| Risk | Mitigation |
|------|------------|
| Data loss | Full ES snapshot before any changes |
| Auth issues | Fallback to direct ES access |
| Merge conflicts | Dry-run mode, manual review queue |
| Performance | Batch processing with progress tracking |
| Validation errors | Reject invalid data, log for review |

## Next Steps

1. ✅ **Review this documentation** - Understand the approach
2. ⏳ **Verify Tracardi credentials** - Get working API token
3. ⏳ **Run Phase 1 analysis** - Get actual data quality metrics
4. ⏳ **Execute test batch** - Validate on 100 profiles
5. ⏳ **Full production cleanup** - Process all 516K profiles
6. ⏳ **Deduplication** - Merge duplicate KBO records
7. ⏳ **Phase 2 enrichment** - Geocoding, AI descriptions, website discovery

## Support

For questions or issues:
1. Check the detailed implementation guide in `docs/DATA_CLEANUP_IMPLEMENTATION.md`
2. Review the troubleshooting section in the appendix
3. Check logs: `cleanup.log`, `deduplication.log`

---

*Delivered: 2026-02-25*  
*Status: Ready for Phase 1 execution*
