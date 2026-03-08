# Handoff: Browser-Capable Agent for Demo Screenshots

**Date:** 2026-03-08  
**From:** Kimi Code CLI (Headless Browser Agent)  
**To:** Browser-Capable Agent (Non-Headless for Manual Login)  
**Task:** Capture additional screenshots requiring manual login  
**Priority:** HIGH - For manager demo presentation  

---

## 🎯 Mission

The user has an extensive collection of screenshots from headless browser testing (see `SCREENSHOT_INVENTORY.md`), but **missing live dashboard screenshots** from platforms that require manual login:

1. **Resend** - Email platform dashboard, audiences, campaigns
2. **Teamleader** - CRM demo environment
3. **Exact Online** - Accounting demo environment  
4. **Tracardi GUI** - Workflow execution (optional, already have many screenshots)

You have access to **non-headless browser** and can handle **manual login flows**, **OAuth**, and **interactive sessions**.

---

## 📋 What Exists (Don't Duplicate)

### Already Have (Headless Screenshots)
- ✅ Chatbot UI flows (60+ screenshots)
- ✅ Tracardi dashboards (20+ screenshots)
- ✅ Tracardi workflows (10+ screenshots)
- ✅ Tracardi event sources (8+ screenshots)
- ✅ Analytics test results (5+ screenshots)
- ✅ Local development screenshots

### Need You To Capture (Requires Login)
- ❌ Resend dashboard with real data
- ❌ Resend audience management
- ❌ Teamleader CRM with demo data
- ❌ Exact Online with demo data
- ❌ End-to-end integration proof

---

## 🔐 Login Credentials & Access

### Resend (https://resend.com)
- **Status:** User has account
- **Login:** User will provide or you can use API key from `.env` file
- **What to capture:**
  - Dashboard overview
  - Audiences list
  - Sample audience with contacts
  - Webhook configuration
  - Campaign history

### Teamleader (https://app.teamleader.eu)
- **Status:** Demo environment available
- **Login:** OAuth flow (user may need to authorize)
- **Data already synced:** 1 company, 2 contacts, 2 deals, 2 activities
- **What to capture:**
  - Dashboard/overview
  - Companies list
  - Contacts list
  - Deals/pipeline
  - Activities
  - Integration settings

### Exact Online (https://start.exactonline.be)
- **Status:** Demo environment available
- **Login:** OAuth flow (tokens in `.env.exact`)
- **Data already synced:** 60 GL Accounts, 60 Invoices
- **What to capture:**
  - Dashboard
  - GL Accounts
  - Sales invoices
  - Integration/app settings

### Tracardi GUI (http://localhost:8787)
- **Status:** Running locally via Docker
- **Login:** Check `.env.local` for credentials or use default
- **Already have many screenshots** - only capture if new/unique views needed
- **What might be new:**
  - Live workflow execution
  - Real-time event processing
  - Profile enrichment in action

---

## 📸 Required Screenshots

### Priority 1: Resend (Critical for POC Demo)

| # | Screenshot Name | Description | URL |
|---|-----------------|-------------|-----|
| 1 | `resend_dashboard_overview.png` | Main dashboard with stats | resend.com |
| 2 | `resend_audiences_list.png` | List of audiences | resend.com/audiences |
| 3 | `resend_audience_detail.png` | Sample audience with contacts | Click into audience |
| 4 | `resend_campaigns_list.png` | Email campaigns | resend.com/campaigns |
| 5 | `resend_webhooks_config.png` | Webhook settings | resend.com/webhooks |
| 6 | `resend_api_keys.png` | API keys page (blur key) | resend.com/api-keys |

### Priority 2: Teamleader (CRM Integration Proof)

| # | Screenshot Name | Description | URL |
|---|-----------------|-------------|-----|
| 7 | `teamleader_dashboard.png` | Main dashboard | app.teamleader.eu |
| 8 | `teamleader_companies.png` | Companies list | /companies |
| 9 | `teamleader_company_detail.png` | Company with KBO match | Click company |
| 10 | `teamleader_contacts.png` | Contacts list | /contacts |
| 11 | `teamleader_deals.png` | Deals/pipeline | /deals |
| 12 | `teamleader_activities.png` | Activity timeline | /activities |
| 13 | `teamleader_integrations.png` | Integration settings | /integrations |

### Priority 3: Exact Online (Financial Integration Proof)

| # | Screenshot Name | Description | URL |
|---|-----------------|-------------|-----|
| 14 | `exact_dashboard.png` | Main dashboard | start.exactonline.be |
| 15 | `exact_gl_accounts.png` | GL Accounts list | /Financial/GLAccounts |
| 16 | `exact_sales_invoices.png` | Invoices | /SalesInvoices |
| 17 | `exact_integration_apps.png` | Connected apps | /apps |

### Priority 4: Integration Proof (The "Wow" Shots)

| # | Screenshot Name | Description | How to Capture |
|---|-----------------|-------------|----------------|
| 18 | `integration_full_architecture.png` | Diagram/overview | Use excalidraw or similar |
| 19 | `sync_teamleader_to_postgres.png` | Sync script running | Run script, capture terminal |
| 20 | `sync_exact_to_postgres.png` | Exact sync running | Run script, capture terminal |
| 21 | `data_flow_diagram.png` | Visual data flow | Create diagram |

---

## 🛠️ Technical Setup

### Prerequisites
```bash
# Ensure local stack is running
cd /home/ff/Documents/CDP_Merged
docker compose ps

# If not running:
docker compose up -d

# Verify services
curl http://localhost:8000/healthz  # Chatbot
curl http://localhost:8686/healthcheck  # Tracardi API
curl http://localhost:8787  # Tracardi GUI
```

### Environment Variables
Key files with credentials:
- `.env` - Main environment
- `.env.local` - Local overrides
- `.env.exact` - Exact Online tokens
- `.env.teamleader` - Teamleader tokens

**DO NOT COMMIT** screenshots with visible API keys or tokens!

### Browser Setup
You'll need a browser with:
- ✅ Non-headless mode (for manual login)
- ✅ Screenshot capability
- ✅ Console access (for debugging)

---

## 📝 Screenshot Naming Convention

Use this pattern:
```
{platform}_{feature}_{date}.png
```

Examples:
- `resend_dashboard_2026-03-08.png`
- `teamleader_companies_2026-03-08.png`
- `exact_gl_accounts_2026-03-08.png`

Save to: `docs/illustrated_guide/demo_screenshots/`

---

## 🎨 Screenshot Quality Guidelines

### Size
- **Minimum:** 1280x720
- **Preferred:** 1920x1080
- **Aspect Ratio:** 16:9 for consistency

### Content
- **Blur/DON'T SHOW:** API keys, passwords, tokens, personal data
- **DO SHOW:** Dashboards, lists, workflow diagrams, success states
- **Annotations:** Add red arrows/circles for key elements (if possible)

### Focus Areas
- Show **real data** from demo environments
- Show **integration points** (KBO numbers, sync status)
- Show **active states** (recent activity, processing)

---

## 🔍 Verification Checklist

Before finishing, verify:

- [ ] All screenshots are 1920x1080 or larger
- [ ] No API keys or secrets visible
- [ ] All images are clear (not blurry)
- [ ] Screenshots show real demo data (not empty states)
- [ ] File names follow convention
- [ ] Images saved to correct folder
- [ ] Inventory document updated with new screenshots

---

## 🚀 Suggested Workflow

### Step 1: Resend (Easiest, API-driven)
1. Login to resend.com
2. Navigate through each page
3. Capture screenshots 1-6
4. Save to demo_screenshots/

### Step 2: Teamleader (OAuth)
1. Go to app.teamleader.eu
2. Complete OAuth flow (user may need to authorize)
3. Navigate through CRM sections
4. Capture screenshots 7-13

### Step 3: Exact Online (OAuth)
1. Go to start.exactonline.be
2. Use existing tokens or complete OAuth
3. Navigate through accounting sections
4. Capture screenshots 14-17

### Step 4: Integration Proof
1. Run sync scripts locally
2. Capture terminal output
3. Create architecture diagram
4. Capture screenshots 18-21

### Step 5: Documentation
1. Update `SCREENSHOT_INVENTORY.md`
2. Create `MANAGER_DEMO_GUIDE.md` (slide order)
3. Handoff to user

---

## 📚 Reference Documentation

Before starting, read:

1. `AGENTS.md` - Architecture overview
2. `STATUS.md` - Current system status
3. `SCREENSHOT_INVENTORY.md` - What already exists
4. `docs/RESEND_INTEGRATION.md` - Resend setup details
5. `docs/illustrated_guide/` - This folder

---

## ❓ Questions?

If unclear on:
- **What to capture:** Reference SCREENSHOT_INVENTORY.md
- **How to login:** Check .env files for tokens/credentials
- **What's important:** Look at BACKLOG.md Milestone POC section
- **Demo flow:** Ask user for their preferred story flow

---

## 📤 Handoff Back

When complete, provide:

1. All new screenshots in `docs/illustrated_guide/demo_screenshots/`
2. Updated `SCREENSHOT_INVENTORY.md` with new entries
3. New `MANAGER_DEMO_GUIDE.md` with slide order
4. Brief notes on any issues encountered
5. Any credentials that were updated/rotated

---

## ⚠️ Important Notes

1. **Privacy:** Don't capture real customer data - use demo environments only
2. **Secrets:** Never commit screenshots with visible API keys
3. **Consistency:** Use same browser window size for all shots
4. **Timing:** Capture during active state (data loaded, not loading)
5. **Backups:** Keep originals before any editing

---

## 🎯 Success Criteria

You're successful when:

- ✅ 21 high-quality screenshots captured
- ✅ All screenshots follow naming convention
- ✅ No secrets exposed in any image
- ✅ Inventory and guide documents updated
- ✅ User can create presentation without additional screenshots

---

**Good luck! The user is very pleased with progress and these screenshots will complete the demo package.**

---

*This handoff created by Kimi Code CLI (Headless Browser Agent)*  
*Date: 2026-03-08*  
*Canonical Repo: /home/ff/Documents/CDP_Merged*
