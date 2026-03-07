# Handover Template v3

**Purpose:** Standard safe handoff for future sessions  
**Last Updated:** 2026-03-06

---

## Usage

Use this template when handing work to a new session or another agent.

Rules:
- Do not restate live status if it already belongs in `PROJECT_STATE.yaml` or `STATUS.md`.
- Mark operational claims as `observed`, `reported`, `blocked`, or `assumed`.
- Record exact SHAs and run IDs when CI/CD affects completion.
- If `main` moved or a workflow run was superseded, say so explicitly.
- Every session ends with a handoff block, even when the task is complete.
- The handoff must be copy-pasteable into a new session without extra explanation from the user.
- The handoff should give the next agent one concrete place to resume.
- If the worktree was dirty, separate pre-existing dirty paths from paths touched in the current session.
- If path ownership is unclear, say `ownership_unclear` instead of guessing.
- If you mention enrichment progress, lead with canonical PostgreSQL evidence when reachable; use logs/process state as supporting evidence, not a dashboard-only claim.

---

## Template

~~~md
## Handoff

**Date:** YYYY-MM-DD
**Task:** [brief task name]
**Type:** docs_or_process_only / verification_only / app_code / data_pipeline / infrastructure
**Status:** COMPLETE / PARTIAL / BLOCKED / PAUSED
**Handoff Reason:** normal_completion / pending_ci_cd / context_budget / blocked / user_stop
**Canonical Repo:** `/home/ff/Documents/CDP_Merged`
**Branch:** [branch] or `not rechecked`
**Git Head:** [sha] or `not rechecked`
**Worktree:** clean / dirty / not rechecked
**Pre-Existing Dirty Paths:** [paths] / `none` / `ownership_unclear`
**Touched This Session:** [paths] / `none`
**Left Dirty By This Session:** [paths] / `none`
**Ownership Notes:** [short clarification] / `none`
**Verified SHA:** [sha] / `not applicable` / `not re-verified`
**Pending CI/CD Runs:** [run ids or `none`]
**Last Observed:** success / in_progress / queued / failure / cancelled / not_checked
**Resume From Here:** [one concrete next action]
**Interrupt Only If:** [ambiguity / serious risk / destructive approval / missing access / `none`]

### Read First
1. `AGENTS.md`
2. `STATUS.md`
3. `PROJECT_STATE.yaml`
4. `NEXT_ACTIONS.md`
5. This handoff

### What changed
- [file, system, or decision updated]
- [file, system, or decision updated]

### Verification
- `[command, query, or method]`
- [result]

### Open Issues
- [remaining blocker, uncertainty, or dependency]

### Follow-up
1. [next action]
2. [next action]
~~~

---

## Notes

- Keep live-state detail in `PROJECT_STATE.yaml` and `STATUS.md`; summarize here, do not duplicate.
- If a task depends on CI/CD, include the exact SHA and run IDs checked.
- If a task depends on enrichment progress, include the canonical SQL query or the explicit blocker that prevented it.
- If the worktree is dirty, the handoff is incomplete unless it distinguishes pre-existing dirt from this-session changes.
- Use a narrower task-specific handoff only when it removes ambiguity without reintroducing duplicated status.
