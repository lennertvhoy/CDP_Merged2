## Handoff

**Date:** 2026-03-02
**Task:** Tracardi Profile Search API Fix - Wildcard and Range Endpoint
**Status:** COMPLETE
**Canonical Repo:** `/home/ff/.openclaw/workspace/repos/CDP_Merged`

---

### Read First
1. `AGENTS.md` - Stable operating rules
2. `STATUS.md` - Current snapshot (profile search now marked as fixed)
3. `PROJECT_STATE.yaml` - Structured evidence (updated with fix details)
4. `NEXT_ACTIONS.md` - Active queue (profile search task completed)
5. This handover

---

### What Changed

#### Code/Infrastructure Changes
- **Applied hotfix to Tracardi API container** (`observed` on 2026-03-02)
  - Script: `infra/tracardi/scripts/hotfix_profile_search_vm.sh`
  - Patched `/app/app/api/generic_endpoint.py` inside the tracardi_api container
  - Three functions modified to handle wildcard `*` queries:
    1. `query_by_sql` - Converts `*` to empty string before Elasticsearch query
    2. `time_range_with_sql` - Same wildcard handling for range queries
    3. `histogram_with_sql` - Same wildcard handling for histogram queries
  - Container restarted after patching

- **Backfilled profile timestamps** (`observed` on 2026-03-02)
  - Script: `infra/tracardi/scripts/backfill_profile_update_time_vm.sh`
  - Updated `metadata.time.update` field for profiles missing it
  - Used `_update_by_query` with Painless script to copy from `metadata.time.create` or `metadata.time.insert`

- **Created verification script**
  - File: `scripts/verify_profile_range_endpoint.py`
  - Validates both `/profile/select` and `/profile/select/range/page/0` endpoints
  - Demonstrates correct `DatetimeRangePayload` format

#### Documentation Updates
- `PROJECT_STATE.yaml` - Added `tracardi_profile_search_verification` (status: `observed`) and `tracardi_profile_search_fix` entries
- `STATUS.md` - Updated "Immediate Focus" section; profile search marked as complete
- `NEXT_ACTIONS.md` - Updated task status; profile search no longer blocked
- `PROJECT_STATUS_SUMMARY.md` - Added profile search fix to current state
- `GEMINI.md` - Updated quick reference
- `WORKLOG.md` - Appended detailed session log with root cause analysis

---

### Verification

#### API Endpoints Working
```bash
# Get password from terraform
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
TRACARDI_PASSWORD=$(terraform -chdir=infra/tracardi output -raw tracardi_admin_password)

# Run verification script
python3 scripts/verify_profile_range_endpoint.py
```

**Results:**
- `/profile/select` with `where="*"` → 2500 profiles ✓
- `/profile/select/range/page/0` → 2500 profiles ✓

#### Payload Format for Range Endpoint
The range endpoint requires a specific `DatetimeRangePayload` format:

```json
{
  "where": "",
  "limit": 25,
  "start": 0,
  "minDate": {
    "absolute": {
      "year": 2026, "month": 3, "date": 1,
      "hour": 0, "minute": 0, "second": 0,
      "meridiem": "AM", "timeZone": 0
    }
  },
  "maxDate": {
    "absolute": {
      "year": 2026, "month": 3, "date": 31,
      "hour": 11, "minute": 59, "second": 59,
      "meridiem": "PM", "timeZone": 0
    }
  }
}
```

**Note:** The endpoint expects `minDate.absolute` and `maxDate.absolute` with datetime components, NOT simple timestamps or ISO strings.

---

### Root Cause Summary

The profile search had two issues:

1. **Wildcard 500 Error**: `*` was being passed directly to Elasticsearch SQL parser, which couldn't parse it as a valid query. Fixed by converting `*` to empty string in three API functions.

2. **Range Endpoint Format Mismatch**: Previous testing used incorrect payload format (timestamps/ISO strings). The Tracardi API requires a specific nested structure with `year`, `month`, `date`, `hour`, `minute`, `second`, `meridiem`, and `timeZone` fields.

---

### Follow-up

1. **Apply GUI date range hotfix** - GUI profile search needs additional patch for default date ranges
   - Script: `infra/tracardi/scripts/hotfix_profile_search_gui_dates.sh`
   - Issue: GUI sends requests without `minDate`/`maxDate`, causing "Incorrect time range" error
2. **Create event sources** - None exist after VM redeploy/reinitialization
3. **Create workflows** - None exist; needed for outbound email campaigns
4. **Review hardcoded credentials** - Still pending human review
5. **Consider Tracardi license** - Segments/Audiences feature requires license

---

## GUI Date Range Issue (Additional Finding)

During verification, discovered that the GUI profile search still shows "Query error" because:

1. GUI sends `/profile/select/range/page/0` without `minDate`/`maxDate` fields
2. API defaults both from/to dates to current timestamp
3. Validation fails: "Incorrect time range. From date is earlier than or equal to to date."

**Solution:** Created additional hotfix script (`hotfix_profile_search_gui_dates.sh`) that adds default date ranges (1970-2100) when dates are not provided.

**API vs GUI Status:**
| Endpoint | API Status | GUI Status |
|----------|-----------|------------|
| `/profile/select` | ✅ Working with `*` | N/A |
| `/profile/select/range` | ✅ Working with dates | ⚠️ Needs date fix |
| `/profile/select/histogram` | ✅ Working with dates | ⚠️ Needs date fix |

---

### Git State

Uncommitted changes present:
- Modified: `BACKLOG.md`, `GEMINI.md`, `NEXT_ACTIONS.md`, `PROJECT_STATE.yaml`, `PROJECT_STATUS_SUMMARY.md`, `STATUS.md`, `WORKLOG.md`, `scripts/sync_kbo_to_tracardi.py`
- New files: `docs/HANDOFF_*.md` files, `infra/tracardi/scripts/*.sh` files, `scripts/verify_profile_range_endpoint.py`, screenshots

**Recommendation:** Review and commit the profile search fix scripts and documentation updates as a scoped commit.

---

### Important Credentials (for reference only - not stored in docs)

- **Tracardi GUI/API:** http://137.117.212.154:8787 / http://137.117.212.154:8686
- **Admin account:** `admin@admin.com` (password via `terraform -chdir=infra/tracardi output -raw tracardi_admin_password`)
- **Primary operator:** `l.vanhoyweghen@it1.be` (credentials noted in PROJECT_STATE.yaml, needs re-verification)
