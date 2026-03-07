# CDP_MERGED Research Request - Clarifications & Specifications
**Date:** 2026-02-26  
**For:** AI Research Agent

---

## Deliverable Format

**Preferred:** Single consolidated report with **10 distinct sections** (one per research request), plus:
- Executive summary with top 10 prioritized recommendations
- Implementation roadmap (phased approach)
- ROI projection matrix

**Structure per research area:**
```
1. Research Request Title
   1.1 Current State Analysis
   1.2 Research Findings
   1.3 Recommendations (prioritized)
   1.4 Implementation Complexity (Low/Medium/High)
   1.5 Expected ROI/Timeline
```

---

## Specific Competitors to Analyze (Request 5)

**Primary Competitors:**
1. **Apollo.io** - Leading B2B data platform (main benchmark)
2. **ZoomInfo** - Enterprise B2B contact database
3. **Lusha** - Contact finder extension
4. **Cognism** - EMEA-focused B2B data (closest competitor)
5. **Hunter.io** - Email finder specialist

**Secondary:**
- Clearbit (now HubSpot)
- LeadIQ
- UpLead
- RocketReach

**Belgian/EU-specific:**
- Local lead gen tools in Belgium/Netherlands
- Data brokers serving EU market

---

## Implementation Cost Estimates & Timelines

**YES, include these for each recommendation:**

**Cost Categories:**
- Development hours (assume €75-100/hour rate)
- External API costs (monthly/usage-based)
- Infrastructure costs (hosting, databases)
- Legal/compliance costs

**Timeline Categories:**
- **Quick Wins:** 1-2 weeks
- **Short-term:** 1-2 months
- **Medium-term:** 3-6 months
- **Long-term:** 6+ months

**Example format:**
| Recommendation | Dev Cost | API Cost/mo | Timeline | Impact |
|----------------|----------|-------------|----------|--------|
| Cache common queries | €1,500 | €0 | 1 week | +30% speed |
| Add ZeroBounce validation | €500 | €200 | 2 weeks | +15% accuracy |

---

## Preferred Data Sources & Tools

### Email Validation
- **Primary:** ZeroBounce (GDPR compliant, EU servers)
- **Alternative:** Hunter.io (has free tier)
- **Avoid:** Services that store/leak data

### Social Media APIs
- **LinkedIn:** Official API only (NO scraping)
- **Twitter/X:** API v2 (academic/basic tier)
- **News:** Google News API, NewsAPI.org

### Technographic Data
- **BuiltWith** (has API)
- **Wappalyzer** (open source)
- **BuiltWith alternatives:** SimilarTech, WhatCMS

### Financial Data (Belgian companies)
- **National Bank of Belgium** open data
- **KBO** (we already have this)
- **Graydon** (if affordable)
- **Bisnode** (Dun & Bradstreet alternative)

### B2B Data Enrichment
- **Cognism** (EU-focused, compliant)
- **Lusha** (API available)
- **Clearbit** (now HubSpot, pricing?)
- **Avoid:** Non-GDPR compliant brokers

### Geocoding
- **OpenStreetMap/Nominatim** (already using, FREE)
- **Google Maps Geocoding** (if needed, paid)

---

## Priority Focus Areas

**Highest Priority (do these first):**
1. Data Quality Optimization (Request 1)
2. Query Latency Optimization (Request 3)
3. Competitive Analysis (Request 5) - for positioning

**Medium Priority:**
4. Chatbot Intelligence/Profit Features (Request 2)
5. Integration Ecosystem (Request 8)

**Lower Priority (future roadmap):**
6. Multi-modal data (Request 4)
7. Voice interface (Request 7)

---

## Success Metrics to Track

**Data Quality:**
- Email coverage: 1.9% → 30%+
- Phone coverage: 1.9% → 40%+
- Website coverage: 0.02% → 50%+
- Data freshness score (re-verification frequency)

**Performance:**
- Simple query latency: ~1s → <500ms
- Complex query latency: 3s → <2s
- Cache hit rate target: 60%+

**User Value:**
- Lead conversion rate (user-reported)
- Segment export frequency
- Email campaign ROI (from Resend integration)

---

## Budget Context

**Current monthly costs:**
- Azure Container App: ~€50-100
- Azure OpenAI: ~€20-40 (current usage)
- Tracardi hosting: Included in Azure VM
- Google Places: $200 free tier

**Available budget for improvements:**
- One-time development: €2,000-5,000
- Monthly API/services budget: €200-500

**Prioritize free/low-cost solutions where possible.**

---

## Legal Compliance Requirements

**Must verify for EVERY data source:**
- ✅ GDPR Article 6 legal basis (legitimate interest for B2B)
- ✅ Article 13/14 transparency (privacy notices updated)
- ✅ Data Processing Agreement (DPA) with vendor
- ✅ No cross-border transfer issues (EU servers preferred)
- ✅ No schijnzelfstandigheid risk (for user's tax status)

**Avoid:**
- Scraping personal emails (first.lastname@)
- Bypassing rate limits
- Using gray-market data brokers

---

## Report Length Guidelines

**Total length:** 10,000-15,000 words
- Executive Summary: 500 words
- Per research area: 800-1,200 words
- Implementation roadmap: 1,000 words
- ROI projections: 500 words

**Format:** Markdown with tables, bullet lists, clear headings

---

## Questions for Research Agent

If you encounter ambiguities while researching:

1. **Email preferences:** Lenny prefers short emails. Use bullet points, avoid walls of text.

2. **Decision style:** Lenny likes having options but wants clear recommendations with trade-offs explained.

3. **Technical depth:** Assume intermediate technical knowledge (can read code, understands APIs).

4. **Business focus:** Always tie recommendations back to user profit/ROI. "Better data" is less compelling than "30% more leads = €X more revenue."

5. **Urgency:** No hard deadline, but faster is better. Prioritize Quick Wins in first deliverable.

---

## Start Immediately

**You have all context needed to begin.**

**First task:** Research Request #1 (Data Quality Optimization) - specifically:
1. What legal B2B data sources exist for Belgian companies?
2. What's the optimal enrichment order for maximum coverage?
3. Which email validation service offers best ROI for our scale?

Expected timeline for complete report: 1-2 weeks  
Checkpoint: Send draft of Request #1 within 3 days for feedback

---

*Contact: lennertvhoy@gmail.com for clarifications*  
*Workspace: /home/ff/.openclaw/workspace/repos/CDP_Merged*
