## Handoff

**Task:** Project Organization, Cleanup, and Chainlit UI/UX Enhancement
**Status:** READY TO START
**Previous Task:** Enrichment Pipeline Monitoring (stable, autonomous)

### Context

The enrichment pipeline is running autonomously (87 chunks / 4.5% / ~30h remaining). This is an opportunity to focus on:
1. **Project organization and cleanup** - Archive legacy files, consolidate docs
2. **Chainlit UI/UX enhancement** - Transform the basic chatbot into a premium Belgian CDP AI CRM interface

---

## PART 1: PROJECT ORGANIZATION & CLEANUP

### A. File Cleanup (Low Risk)

**Target: Root Directory Screenshots**
- 18 PNG files in root directory (chatbot screenshots, Tracardi dashboards)
- **Action:** Move to `docs/screenshots/` or `docs/archive/screenshots-2026-03/`
- **Files to move:**
  ```
  chatbot_final_verification.png
  chatbot_working_2026-03-02.png
  tracardi_dashboard_*.png
  tracardi_event_sources_*.png
  tracardi_gui_profile_search_working.png
  tracardi_profiles_*.png
  tracardi_resend_webhook_detail_test.png
  tracardi_workflows_empty.png
  tracardi_login_*.png
  ```

**Target: Legacy Terraform Backups**
- `infra/tracardi/terraform.tfstate.backup`
- `infra/tracardi-minimal/terraform.tfstate.backup`
- **Action:** Move to `infra/backups/terraform/` with date stamps

**Target: Empty/Nearly Empty Directories**
- `src/search_engine/{builders}` - brace expansion artifact, likely empty
- `docs/archive/outdated_plans/` - check if empty
- `docs/archive/root_conflicts/` - check if empty
- `data/cache/cbe_extended/`, `data/test_cache/cbe_extended/` - check if needed
- **Action:** Remove if truly empty and unused

### B. Documentation Consolidation (Medium Risk)

**Duplicate/Outdated Architecture Docs:**
| Current | Status | Action |
|---------|--------|--------|
| `docs/architecture.md` (8.6KB) | Likely outdated | Archive to `docs/archive/` |
| `docs/ARCHITECTURE_AZURE.md` (25KB) | Current | Keep, update references |
| `docs/ARCHITECTURE_DECISION_RECORD.md` (17KB) | Current | Keep |

**Research/Clarification Docs (Completed Work):**
- `docs/AI_RESEARCH_AGENT_BRIEF.md`
- `docs/CDP_MERGED_RESEARCH_CLARIFICATIONS.md`
- `docs/CDP_MERGED_RESEARCH_REQUEST.md`
- **Action:** Move to `docs/archive/research-2026-02/` (historical context)

**Audit/Debug Docs (Completed):**
- `docs/AUDIT_SUMMARY.md`
- `docs/DEBUG_WORKFLOW.md`
- **Action:** Move to `docs/archive/audits/` or integrate into STATUS.md

### C. Code TODO/FIXME Review

**Files with TODOs (7 files found):**
```
scripts/webhook_gateway.py: 2 TODOs
scripts/archive/cleanup_kbo.py: 2 TODOs
scripts/data_cleanup/bulk_cleanup.py: 3 TODOs
src/services/writeback.py: 2 TODOs
src/services/cbe_extended.py: 3 TODOs
src/enrichment/phone_discovery.py: 8 TODOs
src/enrichment/cbe_integration.py: 3 TODOs
```

**Action:**
1. Review each TODO for criticality
2. Convert urgent ones to NEXT_ACTIONS.md items
3. Archive non-critical ones as known technical debt

---

## PART 2: CHAINLIT UI/UX ENHANCEMENT (Primary Focus)

### Current State Analysis

**Existing UI Elements (`src/app.py`):**
- Basic welcome message (text only)
- Simple `cl.Step` for processing indication
- Error messages with ❌ emoji
- 2 action callbacks (create_segment, push_to_resend) - placeholders only

**Current Config (`.chainlit/config.toml`):**
- Default "Assistant" name
- No custom CSS/JS
- No branding
- Basic CoT display (full)

**Goal:** Transform into a **premium Belgian CDP AI CRM chatbot** with:
- Professional branding (IT1 Group / Belgian CDP identity)
- Rich interactive elements
- Clear visual hierarchy
- Context-aware assistance
- Actionable workflows

### UI/UX Enhancement Scope

#### 1. Branding & Identity

**Config Updates (`.chainlit/config.toml`):**
```toml
[UI]
name = "CDP AI Assistant"
description = "AI-Powered Customer Data Platform for Belgian KBO Data"
# Create custom logo/favicon
custom_css = "/public/cdp-custom.css"
# Add IT1 Group or customer branding
```

**Create Files:**
- `public/cdp-custom.css` - Belgian CDP color scheme (professional blues/greys)
- `public/logo.svg` or `public/logo.png` - CDP branding
- `public/favicon.ico` - Custom favicon

**Welcome Message (`src/app.py`):**
- Convert from text to rich interactive elements
- Add quick action buttons ("Search Companies", "Create Segment", "View Analytics")
- Show system status (enrichment progress, data freshness)
- Add "What's New" section for recent features

#### 2. Rich Response Components

**Company Search Results:**
- Use `cl.Message` with markdown tables
- Add `cl.Action` buttons for each result ("Add to Segment", "View Details", "Send Email")
- Include company logos/favicons if available
- Show confidence badges (high/medium/low match)

**Segment Creation Flow:**
- Multi-step wizard using `cl.Step`
- Preview panel showing segment size and sample companies
- Confirmation dialog with "Preview First" option
- Success/failure animations

**Analytics/Charts:**
- Use `cl.Message` with embedded Plotly charts (if supported)
- Or use markdown tables with visual indicators (📊 📈 📉)
- Export options (CSV, PDF, email)

#### 3. Context-Aware UI

**Chat Profiles:**
- Add chat profiles for different user roles:
  - "Marketing Manager" - Campaign focus
  - "Sales Rep" - Lead generation focus
  - "Data Analyst" - Reporting focus
  - "Admin" - System management focus

**Settings Panel:**
- User preferences (language: Dutch/French/English)
- Default search filters (region, company size)
- Notification preferences

#### 4. Interactive Elements

**Quick Reply Buttons:**
```python
# After search results
actions = [
    cl.Action(name="save_search", value="save", label="💾 Save Search"),
    cl.Action(name="create_segment", value="segment", label="📊 Create Segment"),
    cl.Action(name="export_csv", value="export", label="📥 Export CSV"),
]
await cl.Message(content="What would you like to do?", actions=actions).send()
```

**File Upload Support:**
- Allow CSV uploads for bulk company matching
- Show progress bars for large imports

**Custom Elements:**
- Progress bars for long operations (enrichment, segment creation)
- Status indicators (🟢 enriched, 🟡 pending, 🔴 error)
- Badges for company attributes (📧 has email, 🌐 has website, etc.)

#### 5. Belgian-Specific Features

**Localization:**
- Dutch (Flemish) and French language support
- Belgian address formatting
- KBO number formatting (XXXX.XXX.XXX)
- VAT number display (BE0XXX.XXX.XXX)

**Regional Awareness:**
- Province/region filters (Vlaams-Brabant, Wallonië, etc.)
- Language-based company preferences
- NACE code explanations in Dutch/French

### Implementation Phases

**Phase 1: Foundation (2-3 hours)**
1. Update `.chainlit/config.toml` with proper branding
2. Create `public/cdp-custom.css` with Belgian CDP styling
3. Enhance welcome message with quick actions
4. Add chat profiles for different user roles

**Phase 2: Rich Responses (3-4 hours)**
1. Refactor company search results with tables + action buttons
2. Implement segment creation wizard with preview
3. Add analytics visualization (markdown-based)
4. Create status badges and indicators

**Phase 3: Interactivity (2-3 hours)**
1. Implement file upload for bulk matching
2. Add progress bars for long operations
3. Create confirmation dialogs for destructive actions
4. Add export functionality buttons

**Phase 4: Polish (2-3 hours)**
1. Dutch/French language support
2. Mobile responsiveness check
3. Accessibility improvements
4. Final branding alignment

### Design Inspiration

**Color Palette (Belgian CDP Professional):**
- Primary: Deep Blue (#1E3A5F) - Trust, professionalism
- Secondary: Golden Yellow (#F4B942) - Belgian identity
- Accent: Teal (#2A9D8F) - Tech/modern
- Background: Light Grey (#F8F9FA) - Clean, readable
- Success: Green (#28A745)
- Warning: Orange (#F4A261)
- Error: Red (#E63946)

**Typography:**
- Headings: Inter or Roboto (clean, professional)
- Body: System fonts for performance

**Icons:**
- Use emoji consistently for quick recognition
- Consider adding FontAwesome or Lucide icons via custom CSS

### Files to Create/Modify

**New Files:**
```
public/cdp-custom.css          # Custom styling
public/logo.svg                # CDP logo
public/favicon.ico             # Custom favicon
src/ui/components.py           # Reusable UI components
src/ui/actions.py              # Action callback handlers
src/ui/formatters.py           # Message formatters
```

**Files to Modify:**
```
.chainlit/config.toml          # Branding config
src/app.py                     # Enhanced UI logic
chainlit.md                    # Update welcome markdown
```

---

## PART 3: VERIFICATION CHECKLIST

After completing work, verify:

**Cleanup:**
- [ ] Root directory has no screenshot files (moved to docs/)
- [ ] Empty directories removed
- [ ] Old backups moved to infra/backups/
- [ ] Documentation consolidated in docs/archive/

**UI/UX:**
- [ ] Chatbot loads with new branding
- [ ] Welcome message shows quick actions
- [ ] Company search returns formatted table + buttons
- [ ] Segment creation has preview step
- [ ] Error messages are helpful and actionable
- [ ] Mobile view is usable
- [ ] Dutch/French terms work correctly

---

## MONITORING (Background Task)

While working on UI/UX, keep enrichment running:

```bash
# Quick check every hour
grep -c "ENRICHMENT COMPLETE" logs/enrichment/cbe_continuous_*.log

# If processes die, restart with:
bash /tmp/enrichment_loop.sh
```

Current: 87 chunks (~4.5%, ~30h remaining)

---

## PRIORITY ORDER

1. **HIGH:** Chainlit UI/UX Phase 1 (foundation + branding)
2. **MEDIUM:** Project cleanup (screenshots, empty dirs)
3. **MEDIUM:** Chainlit UI/UX Phase 2 (rich responses)
4. **LOW:** Documentation consolidation
5. **LOW:** Chainlit UI/UX Phase 3-4 (advanced features)

---

**Expected Outcome:** A professional, branded Belgian CDP AI CRM chatbot interface with rich interactions, clear visual hierarchy, and context-aware assistance, while the project file structure is cleaned and organized.
