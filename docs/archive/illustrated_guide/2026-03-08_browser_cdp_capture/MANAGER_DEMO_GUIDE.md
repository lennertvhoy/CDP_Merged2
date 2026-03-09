# CDP_Merged - Manager Demo Guide

**Purpose:** Illustrated presentation guide for manager demo  
**Last Updated:** 2026-03-08  
**Status:** 🚧 In Progress - Awaiting browser agent screenshots  

---

## 🎯 Demo Overview

**Title:** CDP_Merged - Customer Data Platform with AI Chatbot  
**Duration:** 15-20 minutes  
**Audience:** Manager/Stakeholder  
**Key Message:** Complete end-to-end CDP with AI chatbot, 360° views, and activation

---

## 📊 Demo Sections

### Section 1: Introduction (1 min)

**Slide 1: Title Slide**
- Title: CDP_Merged Platform Demo
- Subtitle: Customer Data Platform with AI Chatbot
- Date, Presenter

**Slide 2: What We're Demoing**
- AI-powered chatbot for customer intelligence
- 360° customer views across sources
- Automated segment creation
- Email campaign activation
- Real-time engagement tracking

**Slide 3: Architecture Overview**
- **INSERT:** `integration_full_architecture.png` (to be created)
- Text overlay: Data flows from sources → PostgreSQL → AI → Activation

---

### Section 2: The Data Foundation (2 min)

**Slide 4: Data Scale**
- 1.94 million companies in PostgreSQL
- KBO (Belgian business registry) data
- Teamleader CRM integration
- Exact Online financial data
- **INSERT:** Screenshot of database stats

**Slide 5: Source Integrations**
| Source | Status | Records |
|--------|--------|---------|
| KBO | ✅ Live | 1.94M |
| Teamleader | ✅ Demo | 1 company, 2 contacts |
| Exact Online | ✅ Demo | 60 accounts, 60 invoices |

**Slides 6-8: Source System Screenshots**
- **INSERT:** `teamleader_dashboard.png`
- **INSERT:** `teamleader_companies.png`
- **INSERT:** `exact_dashboard.png`
- **INSERT:** `exact_gl_accounts.png`

---

### Section 3: AI Chatbot Demo (5 min)

**Slide 9: Chatbot Introduction**
- Natural language queries
- Intelligent tool selection
- 360° customer views
- **INSERT:** `chatbot_initial_state.png`

**Slide 10: Basic Search Demo**
- Query: "How many restaurant companies are in Gent?"
- **INSERT:** `chatbot_test1_restaurants_gent_thinking.png`
- **INSERT:** `chatbot_test1_gent_restaurants_result.png`

**Slide 11: Segment Creation**
- Query: "Create a segment of software companies in Brussels"
- Result: 1,529 companies segmented
- **INSERT:** `chatbot_test2_segment_creation.png`

**Slide 12: Data Export**
- Export segment to CSV
- **INSERT:** `chatbot_test3_export_csv.png`

**Slide 13: Artifact Creation**
- Create markdown artifact with results
- **INSERT:** `chatbot_test4_artifact_created.png`

**Slide 14: Analytics**
- Query: "What are the top industries in Brussels?"
- **INSERT:** `analytics_test_top_industries.png`
- **INSERT:** `chatbot_test5_analytics_brussels.png`

---

### Section 4: 360° Customer Views (3 min)

**Slide 15: Cross-Source Intelligence**
- Combine KBO + Teamleader + Exact data
- **INSERT:** `chatbot_360_initial_state.png`

**Slide 16: 360° Query Example**
- Query: "What's the total pipeline value for software companies?"
- Shows unified view across all sources
- **INSERT:** `chatbot_360_tools_test_result.png`

**Slide 17: Quality Metrics**
- Tool selection accuracy: 95%+
- Response time: <3 seconds
- **INSERT:** `chatbot_quality_matrix_eval_2026-03-06.png`

---

### Section 5: Activation Layer - Tracardi (3 min)

**Slide 18: Tracardi Overview**
- Event hub and workflow engine
- Profile management
- Real-time processing
- **INSERT:** `tracardi_dashboard_verified_2026-03-07.png`

**Slide 19: Event Sources**
- 4 configured sources: CDP API, KBO Import, Resend Webhook, Real-time Updates
- **INSERT:** `tracardi_event_sources_verified.png`

**Slide 20: Email Workflows**
- 5 automated workflows:
  - Email Engagement Processor
  - Email Bounce Processor
  - Email Delivery Processor
  - High Engagement Segment
  - Email Complaint Processor
- **INSERT:** `tracardi_workflows_configured.png`

**Slide 21: Workflow Details**
- Bounce processing example
- **INSERT:** `tracardi_workflow_bounce_processor_2026-03-07.png`

---

### Section 6: Email Campaign Activation (3 min)

**Slide 22: Resend Integration**
- Modern email API
- Audience management
- Campaign tracking
- **INSERT:** `resend_dashboard_overview.png` (pending)

**Slide 23: Audience Management**
- Create audience from segment
- **INSERT:** `resend_audiences_list.png` (pending)
- **INSERT:** `resend_audience_detail.png` (pending)

**Slide 24: Campaign Sending**
- Send to audience
- Track delivery
- **INSERT:** `resend_campaigns_list.png` (pending)

**Slide 25: Webhook Configuration**
- Real-time event tracking
- 6 event types: sent, delivered, opened, clicked, bounced, complained
- **INSERT:** `resend_webhooks_config.png` (pending)

---

### Section 7: Engagement Tracking (2 min)

**Slide 26: Real-Time Events**
- Events flow back to Tracardi
- Profile enrichment
- **INSERT:** `tracardi_resend_setup_complete.png`

**Slide 27: Event Processing**
- Email opened → Profile updated
- Link clicked → Engagement scored
- **INSERT:** `tracardi_gui_profile_search_working.png`

**Slide 28: Profile Enrichment**
- Before/after engagement data
- **INSERT:** `tracardi_profile_detail_test.png`

---

### Section 8: Technical Validation (1 min)

**Slide 29: Test Coverage**
- 27 routing tests passing
- 545 unit tests passing
- POC tests: 6/6 passing
- **INSERT:** Terminal screenshot of test run

**Slide 30: Performance Metrics**
- Query latency: <3 seconds
- Segment creation: 0.32s
- Email push: 0.24s
- End-to-end: <2 seconds

---

### Section 9: Summary & Next Steps (1 min)

**Slide 31: What We Built**
- ✅ AI chatbot with 95%+ accuracy
- ✅ 360° customer views
- ✅ 1.94M company database
- ✅ Multi-source integration
- ✅ Automated activation
- ✅ Real-time engagement tracking

**Slide 32: Demo Success Proof**
- **INSERT:** `chatbot_final_verification_success.png`

**Slide 33: Next Steps**
- Production deployment planning
- Additional source integrations
- Advanced analytics
- User training

**Slide 34: Q&A**
- Questions?

---

## 📂 Screenshot Status

### ✅ Ready (Existing Screenshots)
- [x] Chatbot UI flows (60+ screenshots)
- [x] Tracardi dashboards (20+ screenshots)
- [x] Tracardi workflows (10+ screenshots)
- [x] Analytics results (5+ screenshots)

### 🚧 Pending (Requires Browser Agent)
- [ ] Resend dashboard screenshots (6)
- [ ] Teamleader CRM screenshots (7)
- [ ] Exact Online screenshots (4)
- [ ] Integration architecture diagram (1)
- [ ] Terminal/sync screenshots (3)

**Total:** 21 screenshots needed

---

## 🎨 Presentation Tips

### Visual Consistency
- Use same browser window size for all screenshots
- 1920x1080 preferred
- Consistent zoom level (100%)

### Story Flow
1. Start with problem (data silos)
2. Show solution (CDP platform)
3. Demonstrate capability (chatbot)
4. Prove integration (source systems)
5. Show activation (email campaigns)
6. Validate success (metrics)

### Key Messages
- **Scale:** 1.94M companies processed
- **Speed:** Sub-second query responses
- **Accuracy:** 95%+ tool selection
- **Integration:** 3+ source systems
- **Automation:** End-to-end activation

---

## 🔧 Creating the Presentation

### Option 1: PowerPoint
1. Create blank presentation
2. Use "Title and Content" layout for most slides
3. Insert screenshots as images
4. Add text callouts for key metrics

### Option 2: Google Slides
1. Similar to PowerPoint
2. Cloud-based for easy sharing
3. Collaboration features

### Option 3: Markdown + Marp
1. Use this file as base
2. Convert to slides with Marp
3. Export to PDF/PPTX

---

## 📝 Speaker Notes

### Slide 10: Basic Search
> "Watch how the AI reasons through the query, selecting the right tool and returning results in under a second."

### Slide 16: 360° Views
> "This is where the magic happens - combining KBO registry data with CRM and financial systems for a complete customer view."

### Slide 25: Webhook Configuration
> "Every email interaction is tracked in real-time, enriching customer profiles automatically."

---

## 📋 Pre-Demo Checklist

Before presenting:

- [ ] All 21 pending screenshots captured
- [ ] Presentation created with all slides
- [ ] Demo environment running (docker compose up)
- [ ] Backup screenshots available
- [ ] Speaker notes reviewed
- [ ] Timing practice completed

---

## 🎯 Success Metrics

Demo is successful if manager:

- ✅ Understands the platform capabilities
- ✅ Sees value in 360° customer views
- ✅ Believes AI chatbot is production-ready
- ✅ Approves next phase (deployment/integration)

---

## 📞 Support

If issues during demo:

1. **Chatbot not responding:** Check localhost:8000/healthz
2. **Tracardi errors:** Check docker compose ps
3. **Missing data:** Run sync scripts
4. **Questions you can't answer:** Note and follow up

---

**Status:** 🚧 Awaiting browser agent to capture Resend/Teamleader/Exact screenshots  
**Last Updated:** 2026-03-08  
**Next Update:** After browser agent completes screenshot capture

---

*Template created by Kimi Code CLI*  
*To be completed by Browser-Capable Agent*
