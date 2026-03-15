# CDP_Merged - Agent Contract

**Project:** Customer Data Platform (CDP) with AI Chatbot Interface  
**Repository:** CDP_Merged  
**Infrastructure:** AZURE (target) / Local-only (current)  
**Version:** 6.0 (Compact Governance)  
**Last Updated:** 2026-03-14

---

## Executive Summary

This file defines **stable operating rules** for human and AI agents. It is NOT the live project status page.

**Start every session by reading:**
1. This file (`AGENTS.md`)
2. `STATUS.md` - human-readable current snapshot
3. `PROJECT_STATE.yaml` - structured current state
4. `NEXT_ACTIONS.md` - active queue (max 10 items)

**End every session with:**
1. Copy-pasteable `## Handoff` block
2. Clean worktree (`git status --short` empty)
3. Updated live-state files if state changed
4. End-of-session hygiene (see below)

---

## File Contract Summary

| File | Purpose | Max Size | Contains | Must NOT Contain |
|------|---------|----------|----------|------------------|
| `AGENTS.md` | Stable rules | 1000 lines | Operating rules, verification policy, handoff template | Session timelines, current counts, blockers |
| `STATUS.md` | Current snapshot | 120 lines | Execution mode, URL status, active blockers, 5-7 headline bullets | Detailed history, old observations |
| `PROJECT_STATE.yaml` | Structured state | 900 lines | Current counts (with `as_of`), component states, active problems | Historical logs, resolved problems >48h |
| `NEXT_ACTIONS.md` | Active queue | 180 lines | ACTIVE/BLOCKED/PAUSED items only, max 10 | COMPLETE/REMOVED items, history |
| `BACKLOG.md` | Roadmap | 250 lines | NOW/NEXT/LATER/WATCHLIST, exit criteria | Detailed execution state |
| `WORKLOG.md` | History | unlimited | Session details, evidence, completed work | — |

---

## Canonical Terminology

Use these exact terms consistently:

| Concept | Canonical Term | Forbidden Synonyms |
|---------|----------------|-------------------|
| Azure state | "Azure deployment disabled for cost control" | paused, paused_not_disabled, disabled_not_paused |
| Tracardi role | `optional_activation_adapter_non_authoritative` | core_dependency, required |
| Execution mode | `local_only` | hybrid, cloud_first |
| Operator shell | Port 3000 | — |
| Operator API | Port 8170 | — |

---

## Bazzite / Host Runtime Rules (Critical)

This project runs on **Bazzite**. Execution context matters:

### Host vs Sandbox
- **Host reality** for: ports, processes, systemd, ngrok, Node, npm, Linuxbrew, Podman
- **Always use:** `flatpak-spawn --host ...` for host-side checks
- **Never trust** sandbox `ss`, `ps`, `systemctl --user` for host state

### Fast Sanity Check
```bash
flatpak-spawn --host bash -lc 'export PATH="/home/linuxbrew/.linuxbrew/bin:$PATH"; which node; node -v'
flatpak-spawn --host bash -lc 'ss -ltnp "( sport = :3000 or sport = :8170 )"'
flatpak-spawn --host bash -lc 'systemctl --user status cdp-operator-api.service'
```

### Port Roles
| Port | Role |
|------|------|
| 3000 | **Primary operator shell UI** |
| 8170 | **Operator API / shell bridge** |
| 8000 | Legacy (Chainlit deprecated) |

---

## Verification Policy

Use these labels for operational claims:
- `observed` - verified directly in current session
- `reported` - supported by prior evidence, not re-verified
- `blocked` - verification attempted but prevented
- `assumed` - temporary working assumption

Every live-state claim must have:
1. Status label
2. Date/timestamp
3. Evidence or attempted command

---

## Handoff Template

Every session must end with:

```markdown
## Handoff

**Date:** YYYY-MM-DD
**Task:** [brief name]
**Type:** docs_or_process_only / verification_only / app_code / data_pipeline / infrastructure
**Status:** COMPLETE / PARTIAL / BLOCKED / PAUSED
**Git Head:** [sha]
**Worktree:** clean / dirty

### What changed
- [change]

### Verification
- [command] → [result]

### Follow-up
1. [next action]
```

---

## End-of-Session Hygiene (Mandatory)

Before any handoff or "session complete" message, you **must**:

1. **Move completed narrative to WORKLOG.md**
   - All detailed implementation history
   - Verification evidence
   - Screenshot references

2. **Trim STATUS.md to current truth only**
   - Max 7 headline bullets
   - Remove old observations
   - Update `Updated At` timestamp

3. **Remove completed items from NEXT_ACTIONS.md**
   - Max 10 active items
   - No COMPLETE/REMOVED statuses
   - Move history to WORKLOG.md

4. **Verify duplicated counts against PROJECT_STATE.yaml**
   - STATUS.md counts must reference PROJECT_STATE.yaml
   - BACKLOG.md counts must include `as_of` date

5. **Verify canonical terminology**
   - Azure status uses canonical form
   - Tracardi role is correct
   - No forbidden synonyms

6. **Update freshness timestamps**
   - Every mutable metric gets `as_of` or `verified_at`
   - Old timestamps (>48h) are `reported`, not `observed`

7. **Run docs hygiene check**
   ```bash
   python scripts/check_state_docs.py
   ```

---

## Read Order Before Work

1. Confirm current directory is `/home/ff/Documents/CDP_Merged`
2. Read this file (`AGENTS.md`)
3. Read `STATUS.md`
4. Read `PROJECT_STATE.yaml`
5. Read `NEXT_ACTIONS.md`
6. Verify only systems you will depend on

If verification fails, record failure in `PROJECT_STATE.yaml` or `WORKLOG.md`.

---

## Canonical Browser Session (Mandatory)

**Use the already-running attached Edge session on `127.0.0.1:9223` for browser work.**

This session is already logged into required platforms and preserves authenticated state.

### Prohibited
- NEVER spawn fresh browsers for canonical flows
- NEVER use `browser_navigate` or isolated Chromium
- NEVER replace the live session with Playwright-isolated browsers

### How to Connect
```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9223')
    context = browser.contexts[0]
    page = context.pages[0]
```

### Before Browser Work
1. Verify Edge CDP: `curl -s http://127.0.0.1:9223/json/list`
2. Connect to EXISTING page(s)
3. Screenshots MUST show authenticated state

---

## Illustrated Guide Compliance

**No session is complete unless the Illustrated Guide is updated and re-exported to PDF.**

See full requirements in `docs/ILLUSTRATED_GUIDE_COMPLIANCE.md`.

Quick checklist:
- [ ] `docs/ILLUSTRATED_GUIDE.md` updated
- [ ] Screenshots/artifacts referenced
- [ ] PDF exported to `reports/illustrated_guide/ILLUSTRATED_GUIDE_latest.pdf`
- [ ] PDF path included in report

---

## Context Budget and Yield

If remaining effective context budget is ~20% or less:
1. Stop opening new broad context
2. Finish smallest safe unit of current task
3. Update required docs
4. Produce copy-pasteable Handoff block

Yield early with precise handoff rather than continue with degraded accuracy.

---

## Autonomous Continuation Protocol

After completing required read order:
1. Continue from latest handoff if unfinished task named
2. Otherwise pick highest-priority unblocked item from NEXT_ACTIONS.md
3. Choose smallest useful unit
4. Prefer implementation over conversational check-ins

Interrupt user only when:
- Request is genuinely ambiguous
- Serious risk/destructive action requires confirmation
- Credentials/approvals/access missing
- Two+ materially different valid directions exist

---

## Dirty Worktree Protocol

1. Treat any uncommitted change you did not make as user-owned
2. Capture start-of-session snapshot from `git status --short`
3. If shared docs are dirty, append smallest safe change
4. **Critical:** If you modify a file, commit those changes before handoff
5. Do not claim worktree is clean without current-session check
6. Rerun `git status --short` immediately before preparing handoff
7. Do not provide handoff while worktree is dirty

---

## When Facts Conflict

1. Stop and identify conflicting files/systems
2. Resolve by checking implementation:
   - source code
   - deployed configuration
   - provider/runtime state
   - logs
   - direct verification
3. Prefer implementation + verification over stale docs
4. Fix current source-of-truth docs first
5. Continue only after contradiction documented

---

## Cost-Control Operating Mode

When Azure deployment disabled:
- Default to local runtime, local PostgreSQL
- Do not treat Azure deployment as automatic next step
- Keep Azure state as historical context
- Local-only tasks complete after local verification

---

## Background Monitoring Discipline

For long-running jobs (enrichers, CI runs):
1. Verify once: is it alive, is it making progress
2. If blocker is time-based, demote to background monitoring
3. Do NOT keep spending session on repeated snapshots
4. Switch to other unblocked tasks
5. Leave precise recheck trigger in NEXT_ACTIONS.md

---

## Source of Truth Hierarchy

1. `AGENTS.md` - operating rules (this file)
2. `PROJECT_STATE.yaml` - structured live state
3. `STATUS.md` - narrative live status
4. `NEXT_ACTIONS.md` - active queue
5. `BACKLOG.md` - roadmap
6. `WORKLOG.md` - history

---

## Anti-Regression Checks

Run before claiming docs cleanup complete:

```bash
python scripts/check_state_docs.py
```

This enforces:
- STATUS.md ≤ 120 lines
- NEXT_ACTIONS.md ≤ 180 lines, no COMPLETE/REMOVED
- PROJECT_STATE.yaml ≤ 900 lines
- AGENTS.md ≤ 1000 lines
- Canonical terminology used
- Mutable counts have freshness dates

---

## Decision Log

For full decision history, see `DECISIONS.md`.

Key active decisions:
| Date | Decision |
|------|----------|
| 2026-03-14 | Tracardi demoted to optional activation adapter |
| 2026-03-14 | Illustrated Guide updates mandatory per session |
| 2026-03-14 | Edge session on 127.0.0.1:9223 mandatory for browser work |
| 2026-03-09 | Azure infrastructure deployment disabled (cost control) |
| 2026-03-09 | Kubernetes is target deployment architecture |
| 2026-03-03 | PostgreSQL-first canonical architecture |
| 2026-03-03 | Truth layers: sources=PII, PostgreSQL=intelligence, Tracardi=activation |

---

*End of AGENTS.md*
