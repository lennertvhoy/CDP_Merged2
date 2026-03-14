# Acceptance Criteria Appendix

**Purpose:** Reviewer-facing proof package for CDP_Merged POC verification  
**Audience:** Technical auditors, QA reviewers, stakeholder sign-off  
**Last Updated:** 2026-03-14  
**Version:** 1.0 (Aligned with Illustrated Guide v3.3)

---

## How to Use This Document

This appendix provides **executable verification steps** for each major claim in the business case. Reviewers can:

1. Run the commands/checks listed in each section
2. Compare results against the expected outcomes
3. Sign off on individual criteria

**Prerequisites:**
- Local Docker Compose stack running (`docker compose up -d`)
- PostgreSQL accessible on `localhost:5432`
- `.env.local` populated with valid credentials

---

## AC-1: 360° Golden Record

### Claim
The system provides a unified customer view combining KBO + Teamleader + Exact + Autotask data.

### Verification

**Step 1: Check linked company count**
```sql
SELECT identity_link_status, COUNT(*) 
FROM unified_company_360 
GROUP BY identity_link_status;
```

**Expected Result:**
| identity_link_status | count |
|---------------------|-------|
| kbo_only | ~1,940,588 |
| linked_exact | 8 |
| linked_teamleader | 6 |
| linked_kbo_teamleader_exact | 0 |
| linked_kbo_exact_autotask | 0 |
| linked_all | 1 |

**Step 2: Verify the primary demonstration case**
```sql
SELECT kbo_number, kbo_company_name, 
       tl_company_name, exact_company_name, autotask_company_name,
       autotask_open_tickets, autotask_total_contracts,
       total_source_count, identity_link_status
FROM unified_company_360
WHERE kbo_number = '0438437723';
```

**Expected Result:**
```
kbo_number: 0438437723
kbo_company_name: B.B.S. ENTREPRISE
tl_company_name: B.B.S. Entreprise
exact_company_name: Entreprise BCE sprl
autotask_company_name: B.B.S. Entreprise
autotask_open_tickets: 1
autotask_total_contracts: 1
total_source_count: 4
identity_link_status: linked_all
```

**Acceptance:** Pass if `linked_all` count ≥ 1 and B.B.S. Entreprise shows 4 sources.

---

## AC-2: Natural Language Segmentation

### Claim
Business users can create segments by asking questions in natural language.

### Verification

**Step 1: Start the chatbot locally**
```bash
cd /home/ff/Documents/CDP_Merged
docker compose up -d
```

**Step 2: Access the chatbot UI**
- Open browser to `http://localhost:8000`
- Authenticate (dev password mode if `CHAINLIT_ENABLE_AZURE_AD=false`)

**Step 3: Execute test prompts**

| Prompt | Expected Result |
|--------|-----------------|
| "Create a segment of IT services companies in Brussels" | Segment created with ~190 companies |
| "Show me software companies with email addresses" | Filtered list with email coverage shown |
| "How many restaurants are in Gent?" | Count returned (~1,105) |

**Step 4: Verify segment persistence**
```sql
SELECT name, description, 
       filter_criteria->>'nace_codes' as nace_codes,
       filter_criteria->>'city' as city
FROM segment_definitions
ORDER BY created_at DESC
LIMIT 3;
```

**Acceptance:** Pass if all 3 test prompts return accurate results.

---

## AC-3: Segment Activation

### Claim
Segments flow to activation platforms in <60 seconds.

### Verification

**Step 1: Verify Resend API connectivity**
```bash
curl -H "Authorization: Bearer $RESEND_API_KEY" \
  https://api.resend.com/audiences
```

**Expected:** HTTP 200 with audience list.

**Step 2: Execute activation flow**
```bash
# Via chatbot or direct API
# POST /segments/{id}/activate
# Body: {"platform": "resend", "audience_name": "Test Segment"}
```

**Step 3: Verify timing**
| Metric | Target | Measured |
|--------|--------|----------|
| NL → Segment | <5s | 0.32s ✅ |
| Segment → Resend | <10s | 0.24s ✅ |
| Total activation | <60s | <3s ✅ |

**Step 4: Verify Resend audience population**
- Check Resend dashboard at `https://resend.com/audiences`
- Verify audience shows contacts populated

**Acceptance:** Pass if total latency <60s and audience shows >100 contacts.

---

## AC-4: Engagement Tracking

### Claim
Email engagement events are tracked and generate Next Best Action recommendations.

### Verification

**Step 1: Verify event processor health**
```bash
curl http://localhost:5001/health
```

**Expected:** `{"status": "healthy", "postgres": "connected"}`

**Step 2: Check scoring model**
```bash
curl http://localhost:5001/api/scoring-model | jq .
```

**Expected:** Valid JSON with `event_weights`, `engagement_thresholds`, `recommendation_rules`.

**Step 3: Get Next Best Action for test company**
```bash
curl http://localhost:5001/api/next-best-action/0438437723 | jq .
```

**Expected Result Structure:**
```json
{
  "status": "success",
  "kbo_number": "0438437723",
  "engagement_score": <number>,
  "engagement_level": "low|medium|high",
  "recommendations": [
    {
      "type": "support_expansion|re_activation|cross_sell|sales_opportunity",
      "action": "<descriptive text>",
      "reason": "<explanation>"
    }
  ]
}
```

**Step 4: Verify engagement leads endpoint**
```bash
curl "http://localhost:5001/api/engagement/leads?min_score=5" | jq .
```

**Expected:** Array of leads with `kbo_number`, `engagement_score`, `email_opens`, `email_clicks`.

**Acceptance:** Pass if both endpoints return valid recommendations.

---

## AC-5: Privacy Boundary

### Claim
The CDP contains no direct PII; operates on UID-first design.

### Verification

**Step 1: Verify PostgreSQL core has no PII**
```sql
-- Check companies table columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'companies' 
AND column_name IN ('name', 'email', 'phone', 'contact');
```

**Expected:** 0 rows (no PII columns in core table).

**Step 2: Verify Tracardi profiles are anonymous**
```bash
curl -H "Authorization: Bearer $TRACARDI_TOKEN" \
  http://localhost:8686/profile/select | jq '.results[0]'
```

**Expected:** Profile has `id` (UID) but no `name`, `email`, or `phone` in traits.

**Step 3: Verify gateway sanitization**
```bash
cd /home/ff/Documents/CDP_Merged
uv run python -c "from scripts.webhook_gateway import sanitize_resend_event_data; \
  print(sanitize_resend_event_data({'email': 'test@example.com', 'subject': 'Test'}))"
```

**Expected:** Email hashed (SHA256), subject hashed, domain preserved.

**Step 4: Run gateway tests**
```bash
cd /home/ff/Documents/CDP_Merged
pytest tests/unit/test_webhook_gateway.py -v
```

**Expected:** 48 tests pass.

**Acceptance:** Pass if all privacy checks pass (noting documented divergence in event metadata).

---

## AC-6: Data Scale

### Claim
The system handles the full 1.94M KBO dataset.

### Verification

**Step 1: Verify company count**
```sql
SELECT COUNT(*) FROM companies;
```

**Expected:** 1,940,603

**Step 2: Verify query performance**
```sql
EXPLAIN ANALYZE 
SELECT * FROM companies 
WHERE main_city ILIKE 'Brussels' 
AND industry_nace_code LIKE '62%';
```

**Expected:** Execution time <3 seconds.

**Step 3: Check enrichment coverage**
```sql
SELECT 
  COUNT(*) as total,
  COUNT(website_url) as with_website,
  COUNT(geo_latitude) as with_geocode,
  COUNT(ai_description) as with_description
FROM companies;
```

**Expected Results (as of 2026-03-09):**
| Metric | Expected |
|--------|----------|
| total | 1,940,603 |
| with_website | ~70,922 |
| with_geocode | ~63,979 |
| with_description | ~31,033 |

**Acceptance:** Pass if total count = 1,940,603 and queries complete <3s.

---

## AC-7: Source System Sync

### Claim
Data from Teamleader, Exact, and Autotask syncs to PostgreSQL.

### Verification

**Step 1: Check Teamleader sync status**
```sql
SELECT COUNT(*) FROM teamleader_companies;
SELECT last_synced_at FROM teamleader_companies LIMIT 1;
```

**Step 2: Check Exact Online sync status**
```sql
SELECT COUNT(*) FROM exact_accounts;
SELECT COUNT(*) FROM exact_invoices;
```

**Step 3: Check Autotask sync status**
```sql
SELECT COUNT(*) FROM autotask_companies;
SELECT COUNT(*) FROM autotask_tickets;
SELECT COUNT(*) FROM autotask_contracts;
```

**Expected:**
| Table | Expected Count |
|-------|---------------|
| teamleader_companies | 1 |
| exact_accounts | 9 |
| exact_invoices | 78 |
| autotask_companies | 5 |
| autotask_tickets | 5 |
| autotask_contracts | 3 |

**Step 4: Verify sync timestamps are recent**
```sql
SELECT MAX(last_synced_at) as latest_sync FROM teamleader_companies
UNION ALL
SELECT MAX(synced_at) FROM exact_accounts;
```

**Expected:** Timestamps within last 7 days.

**Acceptance:** Pass if all tables have records and sync timestamps are recent.

---

## AC-8: Event Writeback

### Claim
Engagement events from email platform write back to CDP.

### Verification

**Step 1: Check event_facts table**
```sql
SELECT event_type, COUNT(*) 
FROM event_facts 
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY event_type;
```

**Expected:** Rows with `email.opened`, `email.clicked`, `page.view`, etc.

**Step 2: Verify webhook gateway accepts events**
```bash
curl -X POST http://localhost:8000/webhook/resend \
  -H "Content-Type: application/json" \
  -H "Resend-Signature: <valid-signature>" \
  -d '{
    "type": "email.opened",
    "data": {
      "email_id": "test@example.com",
      "timestamp": "2026-03-14T10:00:00Z"
    }
  }'
```

**Expected:** HTTP 200 with `{"status": "processed"}`.

**Acceptance:** Pass if event_facts has recent rows and webhook returns 200.

---

## Sign-Off Matrix

| ID | Criterion | Verifier | Date | Status |
|----|-----------|----------|------|--------|
| AC-1 | 360° Golden Record | | | ⬜ |
| AC-2 | NL Segmentation | | | ⬜ |
| AC-3 | Segment Activation | | | ⬜ |
| AC-4 | Engagement Tracking | | | ⬜ |
| AC-5 | Privacy Boundary | | | ⬜ |
| AC-6 | Data Scale | | | ⬜ |
| AC-7 | Source System Sync | | | ⬜ |
| AC-8 | Event Writeback | | | ⬜ |

**Overall Acceptance:** ⬜ PASS / ⬜ FAIL / ⬜ PARTIAL

**Notes:**
- Partial acceptance requires documenting specific gaps
- All "Partial" or "Fail" results must reference open backlog items

---

## Automated Verification

For CI/CD integration, run the comprehensive verification script:

```bash
cd /home/ff/Documents/CDP_Merged
uv run python scripts/verify_acceptance_criteria.py
```

**Expected Output:**
```
✅ AC-1: 360° Golden Record - PASS (1 linked_all company)
✅ AC-2: NL Segmentation - PASS (routing guard active)
✅ AC-3: Segment Activation - PASS (avg latency 0.28s)
✅ AC-4: Engagement Tracking - PASS (event processor healthy)
⚠️  AC-5: Privacy Boundary - PARTIAL (raw email in metadata)
✅ AC-6: Data Scale - PASS (1,940,603 records)
✅ AC-7: Source System Sync - PASS (all sources active)
✅ AC-8: Event Writeback - PASS (webhook gateway operational)

Overall: 7 PASS, 1 PARTIAL, 0 FAIL
```

---

*For business context, see `docs/BUSINESS_CONFORMITY_MATRIX.md`. For evidence screenshots, see `docs/ILLUSTRATED_GUIDE.md`.*
