# CDP_Merged - Document Index

**Quick Reference:** Find the right document fast  
**Last Updated:** 2026-03-01 (Documentation Update Rules Added)

---

## 📝 MANDATORY: Update Docs After Work

**Every AI agent MUST update documentation after completing tasks.**

### Update Checklist:
- [ ] `BACKLOG.md` - Mark tasks complete, update progress
- [ ] `NEXT_ACTIONS.md` - Mark actions complete
- [ ] `PROJECT_STATUS_SUMMARY.md` - Update if milestone reached
- [ ] `GEMINI.md` - Update if quick facts changed
- [ ] Date headers - Update in all modified files
- [ ] Git commit - Descriptive message

**Failure to update docs causes confusion and wasted effort.**

---

## 🚨 START HERE (Read in Order)

If you're new to this project or an AI agent starting work, read these in order:

1. **`AGENTS.md`** - Full project context, architecture, and what went wrong
2. **`NEXT_ACTIONS.md`** - Immediate step-by-step tasks
3. **`GEMINI.md`** - Quick reference summary
4. **`BACKLOG.md`** - Current status and priorities

---

## 📋 Document Categories

### Critical Priority Documents

| Document | Purpose | When to Read |
|----------|---------|--------------|
| `AGENTS.md` | Complete project context, architecture decisions, history of confusion | **FIRST - Always** |
| `NEXT_ACTIONS.md` | Immediate step-by-step commands for Tracardi re-deployment | After AGENTS.md |
| `GEMINI.md` | Quick reference for rapid context | When you need a summary |
| `BACKLOG.md` | Current status, priorities, progress tracking | For status updates |
| `PROJECT_STATUS_SUMMARY.md` | Executive summary of current state | For overview |

### Technical Documentation

| Document | Purpose |
|----------|---------|
| `docs/ARCHITECTURE_AZURE.md` | Architecture details and diagrams |
| `docs/OPERATIONAL_SOP.md` | Enrichment field ownership and procedures |
| `docs/specs/DATABASE_SCHEMA.md` | PostgreSQL schema documentation |
| `infra/tracardi-minimal/` | Terraform code for Tracardi deployment |

### Infrastructure

| Path | Purpose |
|------|---------|
| `infra/tracardi-minimal/` | Minimal Tracardi deployment (MySQL only) |
| `infra/terraform/` | Main Azure infrastructure |
| `scripts/` | Utility scripts (sync, test, enrich) |
| `src/` | Python source code |

---

## 📁 File Organization

```
CDP_Merged/
│
├── 🚨 START HERE
│   ├── AGENTS.md                    ← Read this FIRST
│   ├── NEXT_ACTIONS.md              ← Immediate tasks
│   ├── GEMINI.md                    ← Quick reference
│   ├── BACKLOG.md                   ← Status tracking
│   └── PROJECT_STATUS_SUMMARY.md    ← Executive summary
│
├── 📄 Project Files
│   ├── README.md                    ← Updated overview
│   ├── INDEX.md                     ← This file
│   ├── CHANGELOG.md                 ← Change history
│   └── pyproject.toml               ← Python dependencies
│
├── 📁 docs/
│   ├── ARCHITECTURE_AZURE.md        ← Architecture details
│   ├── OPERATIONAL_SOP.md           ← Enrichment SOP
│   ├── ENRICHMENT.md                ← Enrichment guide
│   ├── KBO_DATA_GUIDE.md            ← KBO data documentation
│   ├── specs/
│   │   └── DATABASE_SCHEMA.md       ← Schema documentation
│   ├── archive/
│   │   ├── resolved_fixes/          ← Old bug fixes
│   │   ├── old_reports/             ← Outdated reports
│   │   └── conflicting_docs/        ← Conflicting documents
│   │       ├── MIGRATION_PLAN_v2.0.md     ⚠️ OUTDATED
│   │       ├── MIGRATION_STATUS.md        ⚠️ OUTDATED
│   │       └── STATUS_2026-02-28.md       ⚠️ OUTDATED
│   └── research/                    ← Research documents
│
├── 📁 infra/
│   ├── tracardi-minimal/            ← ⭐ Deploy Tracardi from here
│   ├── terraform/                   ← Main Azure infra
│   └── scripts/                     ← Deployment scripts
│
├── 📁 scripts/
│   ├── sync_postgresql_to_tracardi.py   ← Profile sync script
│   ├── test_postgresql.py               ← DB connection test
│   ├── enrich_profiles.py               ← Enrichment runner
│   └── import_kbo_streaming.py          ← KBO importer
│
├── 📁 src/
│   ├── services/                    ← Database clients
│   ├── enrichment/                  ← Enrichment pipeline
│   └── search_engine/               ← AI chatbot
│
└── 📁 tests/                        ← Unit tests
```

---

## 🔍 Quick Lookup

### "What should I do next?"
→ Read `NEXT_ACTIONS.md`

### "What went wrong with Tracardi?"
→ Read `AGENTS.md` section "The Confusion That Happened"

### "What's the correct architecture?"
→ Read `AGENTS.md` section "CORRECT ARCHITECTURE"

### "Why can't we skip Tracardi?"
→ Read `AGENTS.md` section "POC REQUIREMENTS"

### "How do I deploy Tracardi?"
→ Read `NEXT_ACTIONS.md` Action #1

### "What are the POC requirements?"
→ Read `AGENTS.md` section "POC REQUIREMENTS"

### "What's the current status?"
→ Read `BACKLOG.md` or `PROJECT_STATUS_SUMMARY.md`

---

## ⚠️ Documents to Avoid

These documents contain outdated or conflicting information:

| Document | Issue | Replacement |
|----------|-------|-------------|
| `MIGRATION_PLAN_v2.0.md` | Assumes "Azure-only" without Tracardi | `AGENTS.md` |
| `MIGRATION_STATUS.md` | Says Tracardi "preserved" but it's deleted | `AGENTS.md` |
| `STATUS_2026-02-28.md` | Pre-confusion, wrong priorities | `BACKLOG.md` |

**Location:** `docs/archive/conflicting_docs/`

---

## 🎯 Document Priority Hierarchy

When documents conflict, use this priority:

```
1. AGENTS.md (highest authority)
2. NEXT_ACTIONS.md
3. GEMINI.md
4. BACKLOG.md
5. PROJECT_STATUS_SUMMARY.md
6. README.md
7. Technical docs (ARCHITECTURE_AZURE, etc.)
8. Archived docs (lowest authority)
```

---

## 📊 Current Project State

| Aspect | Status |
|--------|--------|
| **Tracardi** | ❌ DELETED - Needs re-deployment |
| **PostgreSQL** | ✅ Running (1.8M companies) |
| **AI Chatbot** | ✅ Working |
| **POC Requirements** | ❌ BLOCKED (no Tracardi) |
| **Next Action** | Deploy Tracardi (see NEXT_ACTIONS.md) |

---

## 🔗 External References

- [Tracardi Documentation](https://docs.tracardi.com)
- [Flexmail API Documentation](https://api.flexmail.com)
- [Azure PostgreSQL Documentation](https://docs.microsoft.com/azure/postgresql)
- [Terraform Azure Provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)

---

## 📝 Notes for AI Agents

1. **Always read AGENTS.md first** - It contains the full context
2. **Check NEXT_ACTIONS.md** - It has the immediate steps
3. **Verify current state** - Run `terraform show` in `infra/tracardi-minimal/`
4. **Don't trust archived documents** - They may contain conflicting info
5. **When in doubt, ask** - Better to clarify than go in circles

---

*This index is current as of 2026-03-01. For the latest status, see `BACKLOG.md`.*
