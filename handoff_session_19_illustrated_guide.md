## Handoff

**Date:** 2026-03-08  
**Task:** Illustrated Guide Production - Real Screenshots & Verification  
**Type:** verification_only + app_code (if fixes needed)  
**Status:** IN PROGRESS  
**Canonical Repo:** `/home/ff/Documents/CDP_Merged`  
**Git Head:** `d040436`  
**Worktree:** clean  
**Pre-Existing Dirty Paths:** none  
**Touched This Session:** none yet  
**Left Dirty By This Session:** none yet  
**Resume From Here:** Systematic testing and screenshot capture

---

### Priority: Illustrated Guide Excellence

**Goal:** Create the best possible illustrated guide that:
1. Shows ONLY real, working functionality
2. Has every screenshot tested and verified
3. Demonstrates interesting, compelling use cases
4. Fixes any issues discovered during testing
5. Follows AGENTS.md screenshot integrity rules strictly

---

### Current State Verification

**Services Status (observed):**
| Service | Status | Port |
|---------|--------|------|
| PostgreSQL | ✅ Up 19h (healthy) | 5432 |
| Chatbot Agent | ✅ Up 3h (healthy) | 8000 |
| Elasticsearch | ✅ Up 22h (healthy) | 9200 |
| Tracardi API | ✅ Up 19h | 8686 |
| Tracardi GUI | ✅ Up 19h | 8787 |
| Redis | ✅ Up 19h | 6379 |

**Health Check (observed):**
```json
{
  "status": "ok",
  "service": "cdp-merged",
  "llm_provider": "openai"
}
```

**Database Status (from STATUS.md):**
- KBO Records: 1,940,603 (confirmed)
- Enriched Records: 36,091 with website_url
- Geocoded: 8,609 with geo_latitude

---

### Test Plan for Illustrated Guide

#### Phase 1: Chatbot Core Functionality (30 min)

**Test 1: Basic Count Query**
- [ ] Query: "How many restaurant companies are in Gent?"
- [ ] Verify: Returns actual count (expected: ~1,105 based on STATUS.md)
- [ ] Screenshot: Query + result
- [ ] Evaluation: Does it match guide description?

**Test 2: Segment Creation**
- [ ] Query: "Create a segment of software companies in Brussels"
- [ ] Verify: Segment created with member count
- [ ] Screenshot: Full conversation flow
- [ ] Evaluation: Is the flow compelling?

**Test 3: Analytics Query**
- [ ] Query: "What are the top industries in Antwerp?"
- [ ] Verify: Returns aggregated results
- [ ] Screenshot: Query + results table
- [ ] Evaluation: Is it visually interesting?

**Test 4: 360° View**
- [ ] Query: "Show me a 360 view of a company"
- [ ] Verify: Returns unified data from multiple sources
- [ ] Screenshot: Complete profile view
- [ ] Evaluation: Does it show value?

#### Phase 2: Multi-Message User Story (30 min)

**Create a realistic scenario:**
1. Initial market research query
2. Segment creation from results
3. Export segment to CSV
4. Push segment to Resend

**Each step:**
- Test functionality
- Capture screenshot
- Verify it tells a story
- Fix any issues

#### Phase 3: Backend Verification (30 min)

**Tracardi:**
- [ ] Login to GUI (localhost:8787)
- [ ] Verify event sources active
- [ ] Check workflow status
- [ ] Screenshot: Dashboard showing real data

**Database:**
- [ ] Run direct SQL query
- [ ] Verify counts match chatbot results
- [ ] Document any discrepancies

#### Phase 4: Screenshot Evaluation (30 min)

**For each screenshot:**
1. Does it show working functionality? (not errors)
2. Does it match the guide description?
3. Is it visually clear at 1440x900?
4. Does it tell part of the story?
5. Is it interesting to a manager?

**If NO to any:**
- Troubleshoot the issue
- Fix the problem
- Recapture screenshot
- Update guide text if needed

---

### Known Issues to Watch For

**From Previous Testing:**
1. Some screenshots showed "0 results" when they should show data
2. Need to verify OpenAI API key is working (not rate limited)
3. Ensure PostgreSQL queries return in <3 seconds
4. Check that segment creation actually populates members

**Blockers to Escalate:**
- If OpenAI returns 429 (rate limit)
- If database queries timeout
- If Tracardi workflows fail
- If Resend webhooks not configured

---

### Screenshot Requirements

**Technical:**
- Resolution: 1440x900 minimum
- Format: PNG
- Location: `docs/illustrated_guide/`
- Naming: `feature_description_status.png`

**Content:**
- Must show actual working system
- No mock data or fake interfaces
- Clear, readable text
- Professional appearance

**Documentation:**
- Each screenshot needs caption in guide
- Must match actual system state
- Date captured noted if relevant

---

### Definition of Done

- [ ] All screenshots captured from real system
- [ ] Each screenshot tested and verified working
- [ ] Guide text matches actual functionality
- [ ] Multi-message user story complete and tested
- [ ] No placeholder or "coming soon" content
- [ ] Manager can follow guide and understand value
- [ ] All issues found during testing are fixed
- [ ] WORKLOG.md updated with test results
- [ ] Git committed and pushed

---

### Next Actions (Priority Order)

1. **Test chatbot basic queries** - Verify core functionality works
2. **Capture working screenshots** - Replace any non-working ones
3. **Create multi-message story** - Show realistic user flow
4. **Verify backend** - Tracardi, database, integrations
5. **Evaluate all screenshots** - Ensure quality and accuracy
6. **Fix issues** - Anything broken gets repaired
7. **Update guide** - Final polished version
8. **Commit & push** - Share with manager

---

### Resources

**Running Services:**
- Chatbot: http://localhost:8000
- Tracardi GUI: http://localhost:8787
- Tracardi API: http://localhost:8686

**Documentation:**
- AGENTS.md (screenshot integrity rules)
- STATUS.md (current system state)
- ILLUSTRATED_GUIDE.md (current draft)

**Test Data:**
- 1.94M KBO records available
- Test Teamleader account connected
- Test Exact Online account connected
- Resend test account active

---

*Start with Phase 1: Test chatbot core functionality*
