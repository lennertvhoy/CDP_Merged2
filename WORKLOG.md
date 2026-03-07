# WORKLOG

**Purpose:** Append-only session log for meaningful task updates

---

---

## 2026-03-07 (Teamleader Sync Pipeline Complete)

### Task: Build production-ready Teamleader → PostgreSQL sync pipeline

**Type:** app_code  
**Status:** COMPLETE  
**Timestamp:** 2026-03-07 21:40 CET  
**Git Commit:** `ad08be3` - feat: Teamleader → PostgreSQL sync pipeline

**Summary:**
Built and verified a production-ready sync pipeline that pulls real CRM data from Teamleader demo environment into PostgreSQL. The pipeline includes automatic KBO matching via company number/VAT, identity linking, and incremental sync capabilities.

**Components Built:**

| Component | File | Description |
|-----------|------|-------------|
| Database Schema | `scripts/migrations/004_add_crm_tables.sql` | 5 new tables: crm_companies, crm_contacts, crm_deals, crm_activities, crm_deal_phases |
| Sync Script | `scripts/sync_teamleader_to_postgres.py` | Production sync with OAuth, rate limiting, pagination |
| Teamleader Client | Inline in sync script | REST API client with automatic token refresh |

**Sync Results (Real Demo Data):**

| Entity | Count | KBO Matched |
|--------|-------|-------------|
| Companies | 1 | ✅ Yes - Linked to KBO #1020911934 |
| Contacts | 2 | N/A |
| Deals | 2 | N/A |
| Activities | 2 | N/A |

**Key Features:**
- ✅ OAuth2 authentication with automatic token refresh
- ✅ Rate limiting (per-second and per-minute)
- ✅ Incremental sync with cursor tracking
- ✅ Full sync mode available
- ✅ Automatic KBO matching via company_number/vat_number
- ✅ Identity linking to `organizations` and `source_identity_links` tables
- ✅ Configurable entity selection (companies, contacts, deals, activities)

**Usage:**
```bash
# Full sync (all entities)
poetry run python scripts/sync_teamleader_to_postgres.py --full

# Incremental sync (uses last cursor)
poetry run python scripts/sync_teamleader_to_postgres.py

# Sync specific entities only
poetry run python scripts/sync_teamleader_to_postgres.py --entities companies,contacts
```

**Environment Variables:**
```bash
TEAMLEADER_API_BASE=https://api.focus.teamleader.eu
TEAMLEADER_CLIENT_ID=your-client-id
TEAMLEADER_CLIENT_SECRET=your-client-secret
TEAMLEADER_REDIRECT_URI=http://localhost:8000/callback
TEAMLEADER_ACCESS_TOKEN=token-from-oauth-flow
TEAMLEADER_REFRESH_TOKEN=refresh-token-from-oauth-flow
TEAMLEADER_TOKEN_EXPIRES_AT=1741379426
```

**Architecture Now In Place:**
```
Teamleader API → Sync Script → PostgreSQL CRM Tables
                                    ↓
                           Automatic KBO Matching
                                    ↓
                           Unified 360° Company View
                           (KBO + CRM Data Combined)
```

**Verification:**
- ✅ Sync script runs without errors
- ✅ Companies table populated with real data
- ✅ KBO matching links to organization 1020911934
- ✅ Identity links created in source_identity_links table

---

## 2026-03-07 (Moonshot AI Provider Support Added)

### Task: Add Moonshot AI (Kimi) as LLM provider option

**Type:** app_code  
**Status:** COMPLETE  
**Timestamp:** 2026-03-07 21:06 CET  
**Git Commit:** `e23799d` - feat(llm): add Moonshot AI (Kimi) provider support

**Summary:**
Added Moonshot AI as an LLM provider option alongside OpenAI, Azure OpenAI, and Ollama. The integration uses the OpenAI-compatible API format.

**Changes:**
- `src/config.py`: Added MOONSHOT_API_KEY and MOONSHOT_BASE_URL settings
- `src/graph/nodes.py`: Added moonshot provider handling with ChatOpenAI

**Usage:**
```bash
# Add to .env.local
LLM_PROVIDER=moonshot
MOONSHOT_API_KEY=your-api-key
```

**Note:** Feature is available but not enabled by default. User can switch to Moonshot by updating .env.local.

---

## 2026-03-07 (Resend Webhook Setup Verified)

### Task: Configure and verify Resend webhook integration with Tracardi

**Type:** verification_only  
**Status:** COMPLETE (local setup)  
**Timestamp:** 2026-03-07 20:45 CET  
**Git HEAD:** Modified (scripts created, event source type fixed)

**Summary:**
Verified local Tracardi is ready to receive Resend webhook events. Fixed event source type configuration issue (webhook → REST) to enable `/track` endpoint compatibility. Created verification and fix scripts. ngrok not configured, blocking external webhook receipt from Resend servers.

**Issues Discovered and Fixed:**

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Tracker endpoint rejected events (422) | Resend event source configured with `type: ["webhook"]` | Changed to `type: ["rest"]` with REST API Bridge |

**Scripts Created:**

| Script | Purpose |
|--------|---------|
| `scripts/verify_local_resend_setup.py` | Comprehensive verification of local Resend webhook setup |
| `scripts/fix_resend_event_source.py` | Fixes event source type from webhook to REST |

**Scripts Modified:**

| Script | Change |
|--------|--------|
| `scripts/setup_tracardi_kbo_and_email.py` | Changed resend-webhook event source type from webhook to REST |

**Verification Results:**

```
✅ Tracardi Authentication: Working
✅ Resend Event Source: Type REST, Enabled
✅ Email Workflows: 5 workflows deployed
✅ Tracker Endpoint: Accepting events
✅ Event Simulation: Profile created successfully
⚠️  ngrok: Not configured (requires auth token)
```

**Local Setup Status:**
- Tracardi API: http://localhost:8686 (healthy)
- Resend event source: `resend-webhook` (type: REST, enabled)
- Workflows: All 5 email processing workflows deployed
- Test events: Successfully create profiles with engagement tracking

**External Webhook Status:**
- ngrok: Not configured (requires `./ngrok config add-authtoken <token>`)
- Resend API key: Configured in `.env`
- Next step: Configure ngrok to expose local Tracardi for external webhooks

**Reference:**
- Verification script: `python scripts/verify_local_resend_setup.py`
- Setup script (fixed): `scripts/setup_tracardi_kbo_and_email.py`

---

## 2026-03-07 (Tracardi Workflows Created via GUI)

### Task: Create 5 Resend email processing workflows in Tracardi GUI

**Type:** verification_only  
**Status:** COMPLETE  

---

## 2026-03-07 (Exact Online Sync Pipeline Implemented)

### Task: Build production-ready Exact Online → PostgreSQL sync pipeline

**Type:** app_code  
**Status:** IMPLEMENTATION COMPLETE - Pending OAuth Credentials  
**Timestamp:** 2026-03-07 21:55 CET  

**Summary:**
Built a production-ready sync pipeline for Exact Online, modeled after the successful Teamleader implementation. The pipeline can sync GL accounts, customers, sales invoices, and general ledger transactions. Ready to run once OAuth credentials are provided.

**Components Built:**

| Component | File | Description |
|-----------|------|-------------|
| Environment Template | `.env.exact` | OAuth credential configuration template |
| Exact Client Service | `src/services/exact.py` | Production OAuth2 client with auto-division discovery |
| Financial Tables Migration | `scripts/migrations/005_add_exact_financial_tables.sql` | 5 tables + 1 summary view for financial data |
| Sync Script | `scripts/sync_exact_to_postgres.py` | Production sync with incremental cursor tracking |

**Database Schema Created:**

| Table | Purpose |
|-------|---------|
| `exact_accounts` | General Ledger (chart of accounts) |
| `exact_customers` | Customer records with credit/financial info |
| `exact_sales_invoices` | Sales invoices with payment tracking |
| `exact_sales_invoice_lines` | Invoice line items |
| `exact_transactions` | General ledger transactions (journal entries) |
| `exact_customer_financial_summary` | View: Aggregated customer financial metrics |

**Key Features:**
- ✅ OAuth2 authentication with automatic token refresh
- ✅ Auto-division discovery (Exact Online company)
- ✅ Rate limiting (60 req/min to match Exact limits)
- ✅ Incremental sync with cursor tracking (Modified timestamp / EntryNumber)
- ✅ Full sync mode available
- ✅ Automatic KBO/VAT matching to existing companies
- ✅ Identity linking to organizations table
- ✅ Financial summary view (revenue YTD, outstanding, overdue, payment behavior)

**Usage:**
```bash
# 1. Configure credentials in .env.exact
#    (Get from https://apps.exactonline.com)

# 2. Run migration for financial tables
psql -d cdp -f scripts/migrations/005_add_exact_financial_tables.sql

# 3. Full sync (all entities)
poetry run python scripts/sync_exact_to_postgres.py --full

# 4. Incremental sync (uses last cursor)
poetry run python scripts/sync_exact_to_postgres.py

# 5. Sync specific entities
poetry run python scripts/sync_exact_to_postgres.py --entities customers,invoices
```

**Data Flow:**
```
Exact Online API (OData)
    ↓
ExactClient (src/services/exact.py)
    ↓ OAuth2 + Rate Limiting + Pagination
PostgreSQL Tables (exact_*)
    ↓ KBO/VAT Matching
Unified 360° View (exact_customer_financial_summary)
```

**Next Step:**
- User provides Exact Online OAuth credentials
- Run sync to populate financial data
- Enable chatbot financial 360° queries

---

