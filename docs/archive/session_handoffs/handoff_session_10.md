## Handoff

**Date:** 2026-03-03  
**Canonical Repo:** `/home/ff/.openclaw/workspace/repos/CDP_Merged`  
**Task:** Deploy Projection Tables and Test Integration  
**Status:** READY

---

### Read First
1. `AGENTS.md` - Operating rules and architecture boundaries
2. `STATUS.md` - Current human-readable snapshot
3. `PROJECT_STATE.yaml` - Structured live state
4. `NEXT_ACTIONS.md` - P0 NEXT: Deploy Projection Tables and Test Integration
5. `docs/PROJECTION_CONTRACT.md` - Projection contract specification
6. This handover

---

### Current State (observed)

**Last Commit:** `e0a26a5` (style(writeback): apply ruff formatting)  
**CI/CD Status:** Green - CI run and CD run both `success` for commit `e0a26a5`  
**Worktree:** Clean - no uncommitted changes  

**Enrichment Pipeline (reported):**
- Running stably in background (PID observed in prior session)
- ~11,645 companies enriched (0.60% of 1.94M)
- ~38 hours remaining for full CBE phase
- Status check: `python scripts/enrich_monitor.py`

---

### Non-Negotiable Rules

- Work only in `/home/ff/.openclaw/workspace/repos/CDP_Merged`
- Do not work in `/home/ff/.openclaw/workspace/CDP_Merged`
- Remember the canonical architecture:
  - source systems = PII and operational master truth
  - PostgreSQL = customer-intelligence and analytical truth
  - Tracardi = event/workflow/activation runtime
  - chatbot authoritative queries = PostgreSQL-backed only

---

### Primary Objective: Deploy Projection Tables and Test Integration

**Status:** READY  
**Priority:** P0  

#### Step 1: Deploy Database Migration

**Goal:** Run the migration to create projection tables on production PostgreSQL.

**Migration File:** `scripts/migrations/001_add_projection_tables.sql`

**Tables to be created:**
- `profile_traits` - Durable analytical traits
- `event_facts` - Normalized behavioral events
- `ai_decisions` - AI decision provenance
- `activation_projection_state` - Projection state tracking
- `segment_definitions` - Canonical segment logic
- `segment_memberships` - Segment membership tracking
- `source_identity_links` - UID bridge
- `identity_merge_events` - Merge/split reconciliation
- `consent_events` - Immutable consent ledger

**Verification command (adapt as needed):**
```bash
# Verify tables created
psql -h <host> -d cdp -U <user> -c "\dt"
# Should show all 9 new tables
```

**Record in `PROJECT_STATE.yaml`:**
- deployment_status: success/failed
- tables_created: list
- any errors encountered

---

#### Step 2: Test Projection Service

**Goal:** Verify single profile projection works end-to-end.

**Test Script (create if needed):**
```python
# scripts/test_projection.py
import asyncio
from src.services.projection import ProjectionService

async def test():
    service = ProjectionService()
    await service.initialize()
    
    # Get a test company
    result = await service.project_profile("<test-uid>")
    print(f"Status: {result.status}")
    print(f"Tracardi ID: {result.tracardi_profile_id}")
    
    await service.close()

asyncio.run(test())
```

**Verification:**
- Tracardi profile created
- `activation_projection_state` record exists
- Projection hash computed

---

#### Step 3: Test Writeback Service

**Goal:** Verify webhook processing writes to PostgreSQL.

**Test Script (create if needed):**
```python
# scripts/test_writeback.py
import asyncio
from src.services.writeback import WritebackService

async def test():
    service = WritebackService()
    await service.initialize()
    
    # Simulate Tracardi webhook payload
    webhook = {
        "event": {
            "id": "test-event-1",
            "type": "tag.assigned",
            "profile": {"id": "<test-uid>"},
            "properties": {"tag_name": "test_tag"}
        }
    }
    
    result = await service.handle_webhook(webhook)
    print(f"Status: {result.status}")
    print(f"Records written: {result.records_written}")
    
    await service.close()

asyncio.run(test())
```

**Verification:**
- `event_facts` table has the event
- `profile_traits` table has the extracted trait

---

#### Step 4: Enrichment Pipeline Integration

**Goal:** Add auto-projection trigger when enrichment completes.

**Integration Point:** `src/enrichment/postgresql_pipeline.py`

Add after enrichment completion (find the `sync_status = 'enriched'` update):
```python
# After setting sync_status = 'enriched'
from src.services.projection import ProjectionService

projection_service = ProjectionService()
await projection_service.initialize()
result = await projection_service.project_profile(str(company_id))
logger.info("auto_projection_complete", uid=company_id, status=result.status)
await projection_service.close()
```

**Verification:**
- Enriched companies get auto-projected
- Projection state recorded
- No errors in enrichment logs

---

#### Step 5: Monitoring Dashboard

**Goal:** Create simple monitoring for projection health.

**Script to create:** `scripts/monitor_projection.py`
```python
import asyncio
from src.services.projection import ProjectionService
from src.services.writeback import WritebackService

async def main():
    proj = ProjectionService()
    await proj.initialize()
    metrics = await proj.get_projection_metrics()
    print("Projection Metrics:", metrics)
    await proj.close()
    
    writeback = WritebackService()
    await writeback.initialize()
    wb_metrics = await writeback.get_writeback_metrics()
    print("Writeback Metrics:", wb_metrics)
    await writeback.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### Completion Requirements

After completing the deployment and testing:

1. **Update `PROJECT_STATE.yaml`:**
   - projection_deployment.status: observed
   - projection_test_results: pass/fail with evidence
   - tables_deployed: list

2. **Append to `WORKLOG.md`:**
   - Session 10 entry
   - Deployment steps taken
   - Test results
   - Any issues discovered

3. **Update `NEXT_ACTIONS.md`:**
   - Mark "Deploy Projection Tables and Test Integration" as COMPLETE
   - Add next task based on test results

4. **Commit scope:**
   - Any test scripts created
   - Enrichment integration changes
   - Documentation updates

---

### Blockers / Risks

| Risk | Mitigation |
|------|------------|
| Database connection issues | Verify `.env.database` credentials before migration |
| Tracardi API unavailable | Check Tracardi health first; projection will retry on next run |
| Enrichment pipeline interruption | Run projection test separately first; integrate after verification |

---

### Follow-up Tasks (for after this handoff)

1. **If deployment successful:**
   - Mark P0 task complete
   - Move to P1 tasks: Define the Canonical 360 Data Model (NEXT_ACTIONS.md line 346)

2. **If issues discovered:**
   - Document in PROJECT_STATE.yaml with severity
   - Create fix tasks in NEXT_ACTIONS.md
   - Do not proceed to next P0 until resolved
