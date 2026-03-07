# CDP_Merged Demo Guide

**Purpose:** Step-by-step guide for presenting the CDP_Merged demo  
**Target Audience:** Internal stakeholders, potential customers  
**Demo Duration:** 15-20 minutes  
**Last Updated:** 2026-03-04

---

## 🎯 Demo Overview

This guide walks you through demonstrating:
1. **AI Chatbot Interface** - Natural language queries to the CDP
2. **Tracardi CDP** - 360° customer profiles, segments, workflows
3. **Resend Integration** - Email campaigns + engagement tracking
4. **Multi-System Integration Story** - Exact, Teamleader, and Autotask shown as `real`, `mock`, or `hybrid` according to the current-state docs

## Provenance Rule

The integration portion of the demo must follow [`DEMO_SOURCE_MOCK_CONTRACT.md`](DEMO_SOURCE_MOCK_CONTRACT.md).

As of 2026-03-04:

- `scripts/demo_teamleader_integration.py` now auto-detects local `.env.teamleader` credentials and runs as a live Teamleader demo slice: live `companies.list`, `contacts.list`, `deals.list`, and `events.list` reads, with mock fallback only if no company-linked events are visible on the fetched page
- `scripts/demo_exact_integration.py` is still a `mock` script unless current docs explicitly record live tenant access
- `scripts/demo_autotask_integration.py` should be treated as `mock` by default

Do not present these scripts as production integrations. Present them as a connected demo-source layer with explicit provenance.

---

## 📋 Pre-Demo Checklist

### 5 Minutes Before Demo

- [ ] Tracardi GUI accessible: http://137.117.212.154:8787
- [ ] Chatbot environment ready (local or container)
- [ ] Demo scripts tested: `python scripts/demo_all_integrations.py`
- [ ] Current source provenance checked in `STATUS.md` / `PROJECT_STATE.yaml`
- [ ] Credentials at hand (see below)
- [ ] Screenshot tool ready (for capturing impressive moments)

### Credentials

| Service | URL | Username | Password Source |
|---------|-----|----------|-----------------|
| Tracardi GUI | http://137.117.212.154:8787 | admin@admin.com | `terraform -chdir=infra/tracardi output -raw tracardi_admin_password` |
| Tracardi API | http://137.117.212.154:8686 | Same as GUI | Same as GUI |
| Chatbot Local | `chainlit run src/app.py` | N/A | N/A |

---

## 🎬 Demo Script

### Phase 1: AI Chatbot (5 minutes)

**Opening:**
> "Today I'll show you our AI-powered Customer Data Platform. Instead of complex queries or clicking through multiple systems, you simply ask questions in natural language."

#### Demo 1: Company Search

**You Say:** "Let me show you our KBO data - 2,500 real Belgian companies."

**Type:**
```
How many IT companies in Oost-Vlaanderen?
```

**Expected Response:**
- Bot shows count (47 IT companies)
- Lists some examples
- Shows search is working

**Talking Points:**
- "This is real KBO data - public but powerful when unified"
- "The AI understands 'IT companies' and maps to NACE codes automatically"
- "We can filter by location, size, industry, and more"

#### Demo 2: Natural Language Segment Creation

**You Say:** "Now watch this - I can create a marketing segment just by asking."

**Type:**
```
Create a segment of software companies in Gent with email addresses
```

**Expected Response:**
- Bot confirms segment creation
- Shows segment size
- Shows TQL query generated

**Talking Points:**
- "No SQL, no complex filters - just ask"
- "The AI translates natural language to Tracardi's TQL query language"
- "This segment is now available for campaigns"

#### Demo 3: Email Campaign via Resend

**You Say:** "Now let's send a campaign to this segment using Resend."

**Type:**
```
Send a welcome email to my Gent software segment
```

**Expected Response:**
- Bot confirms campaign sent
- Shows recipient count
- Shows message ID

**Talking Points:**
- "Resend is our email provider - modern API, great deliverability"
- "All sends are tracked - opens, clicks, bounces"
- "This integrates directly with our CDP for engagement tracking"

**Screenshot Opportunity:** Campaign confirmation message

---

### Phase 2: Tracardi CDP (5 minutes)

**Transition:**
> "Let me show you what's happening behind the scenes in our Tracardi CDP."

#### Demo 4: Profile Dashboard

**Actions:**
1. Open http://137.117.212.154:8787
2. Login with admin@admin.com
3. Navigate to Dashboard

**Show:**
- "2.50k Profiles Stored" counter
- Recent activity
- Event sources

**Talking Points:**
- "These are real profiles enriched from multiple sources"
- "Every interaction is tracked and contributes to the 360° view"
- "Tracardi is our open-source CDP - no vendor lock-in"

#### Demo 5: Individual Profile View

**Actions:**
1. Navigate to Data → Profiles
2. Click on any company profile
3. Scroll through the profile

**Show:**
- Company traits (name, address, employees)
- KBO data (NACE codes, legal form)
- Segments the profile belongs to
- Event history

**Talking Points:**
- "This is a unified profile combining data from multiple systems"
- "We track every touchpoint - website visits, email opens, support tickets"
- "All data is GDPR-compliant with proper consent management"

**Screenshot Opportunity:** Rich profile view with data

#### Demo 6: Event Sources

**Actions:**
1. Navigate to Inbound Traffic → Event Sources

**Show:**
- 4 event sources configured:
  - `kbo-batch-import` - KBO data imports
  - `kbo-realtime` - Real-time KBO updates
  - `resend-webhook` - Email events from Resend
  - `cdp-api` - Internal API events

**Talking Points:**
- "Event sources ingest data from anywhere"
- "Resend webhooks automatically track email engagement"
- "KBO data flows in via scheduled batch imports"

---

### Phase 3: Integration Demos (5 minutes)

**Transition:**
> "Now let me show you the power of connecting your existing business systems."

**Narration rule:** Unless the current-state docs explicitly say otherwise, introduce this phase as a connected demo-source layer with `mock` provenance for Exact, Teamleader, and Autotask.

#### Demo 7: Run Unified Integration Demo

**Command:**
```bash
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
source .venv/bin/activate
python scripts/demo_all_integrations.py
```

**Walk Through:**
- Press Enter to start each phase
- Read the output as it progresses
- Highlight cross-system insights at the end

**Key Moments:**
1. **Exact Online:** Financial data, invoices, payment behavior
2. **Teamleader:** CRM contacts, deals, activities
3. **Autotask:** Service tickets, contracts, assets
4. **Unified Profile:** All data merged
5. **Cross-System Insights:** Only possible with CDP

**Talking Points:**
- "Exact gives us financial health - invoices, payment behavior"
- "Teamleader shows the sales pipeline and decision makers"
- "Autotask reveals service history and technical assets"
- "Without a CDP, these are three separate silos"
- "With a CDP, we get true 360° insights"
- "Today this source layer is only as real as the current provenance matrix says it is; where access is missing, we use vendor-shaped mocks instead of pretending production connectivity exists"

**Screenshot Opportunity:** Unified profile view at the end

---

### Phase 4: Advanced Capabilities (3 minutes)

**Transition:**
> "Let me show you some advanced capabilities that become possible..."

#### Demo 8: Engagement Tracking

**You Say:**
> "When someone opens an email, that event flows back through the webhook and updates their engagement score."

**Show:**
1. In Tracardi: Data → Profiles
2. Show traits like `engagement_score`
3. Explain how this drives segmentation

**Talking Points:**
- "High engagement triggers different messaging than low engagement"
- "We can automatically segment 'hot leads' based on behavior"
- "This is all real-time - no batch processing delays"

#### Demo 9: Use Case Summary

**You Say:**
> "Here are some specific use cases this enables..."

**Show:** End of any demo script for use case list

**Key Use Cases to Highlight:**
1. **Payment-Based Segmentation** - Target fast payers for premium offers
2. **Pipeline-Based Campaigns** - Nurture deals stuck in proposal stage
3. **Proactive Support** - Reach out before customers complain
4. **Cross-Sell Intelligence** - Recommend services based on patterns
5. **Churn Prevention** - Flag at-risk customers early

---

## 🛟 Troubleshooting

### If Chatbot Won't Start

```bash
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
source .venv/bin/activate
chainlit run src/app.py
```

### If Tracardi GUI is Unreachable

1. Check VM status:
```bash
env AZURE_CONFIG_DIR=/tmp/azure-config az vm list -g rg-cdpmerged-fast -d
```

2. If needed, restart:
```bash
env AZURE_CONFIG_DIR=/tmp/azure-config az vm restart -g rg-cdpmerged-fast -n vm-tracardi-cdpmerged-prod
```

### If Profile Count is Wrong

Expected: 2,500 profiles

Check with:
```bash
curl -s http://137.117.212.154:8686/profile/select \
  -H "Authorization: Bearer $(python scripts/get_tracardi_token.py)" \
  -d '{"where": "metadata.time.create EXISTS"}'
```

If low, re-run sync:
```bash
TRACARDI_TARGET_COUNT=2500 python scripts/sync_kbo_to_tracardi.py
```

---

## 📸 Screenshot Opportunities

Capture these moments for follow-up materials:

1. **Chatbot welcome screen** - Shows AI interface
2. **Search results** - Natural language working
3. **Segment creation** - AI-generated TQL
4. **Campaign confirmation** - Resend integration
5. **Tracardi dashboard** - 2,500 profiles counter
6. **Rich profile view** - 360° customer data
7. **Unified demo end** - Cross-system insights

---

## 📝 Post-Demo Actions

### Immediately After Demo

- [ ] Export screenshots for follow-up email
- [ ] Note any questions asked
- [ ] Document any technical issues

### Follow-Up Email Template

**Subject:** CDP Demo Follow-Up - [Company Name]

```
Hi [Name],

Thanks for joining the CDP demo today. Key highlights:

✅ AI chatbot for natural language queries
✅ 2,500 Belgian companies in unified profiles  
✅ Email campaigns via Resend with engagement tracking
✅ Integration with Exact, Teamleader, Autotask
✅ 360° customer view enabling cross-system insights

Attached: Screenshots from today's demo

Next steps:
[Customize based on conversation]

Questions? Just reply to this email.

Best regards,
[Your name]
```

---

## 🎁 Bonus: Live Code Show (Optional)

If audience is technical, show the code:

```bash
# Show a demo script
cat scripts/demo_exact_integration.py | head -50

# Show the Resend integration
cat src/services/resend.py | head -50

# Show the chatbot app
cat src/app.py | head -50
```

**Talking Point:**
> "Everything is open-source and customizable. No black boxes."

---

## 📚 Additional Resources

| Resource | Location |
|----------|----------|
| Integration Demos | `scripts/demo_*_integration.py` |
| Tracardi Workflow Setup | `docs/TRACARDI_WORKFLOW_SETUP.md` |
| Architecture Overview | `AGENTS.md` |
| Current Status | `STATUS.md` |

---

**Good luck with your demo! 🚀**
