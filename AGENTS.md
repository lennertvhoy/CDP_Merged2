# CDP_Merged - Agent Contract

**Project:** Customer Data Platform (CDP) with AI Chatbot Interface  
**Repository:** CDP_Merged  
**Infrastructure:** AZURE (VMs, Container Apps, OpenAI)  
**Last Updated:** 2026-03-07  
**Version:** 5.0 (Condensed Live Docs)

---

## Purpose

This file defines **stable operating rules** for human and AI agents.

It is **not** the live project status page.

Every session must:
- start by reading `AGENTS.md` and the required current-state docs in the prescribed order
- end with a copy-pasteable `## Handoff` block, even if the task is complete

Use these files instead:
- `STATUS.md` - human-readable current snapshot
- `PROJECT_STATE.yaml` - structured current state and verification notes
- `NEXT_ACTIONS.md` - active queue
- `BACKLOG.md` - medium-term priorities
- `WORKLOG.md` - append-only session log

---

## Canonical Working Copy

- **Work only here:** `/home/ff/Documents/CDP_Merged`
- **Do not work here:** `/home/ff/.openclaw/workspace/repos/CDP_Merged`
- If you land in the stale duplicate, stop and switch back before editing anything.

---

## Read Order Before Work

1. Confirm the current directory is `/home/ff/Documents/CDP_Merged`.
2. Read this file (`AGENTS.md`).
3. Read `STATUS.md`.
4. Read `PROJECT_STATE.yaml`.
5. Read `NEXT_ACTIONS.md`.
6. Read `BACKLOG.md` only if you need broader context.
7. If current docs conflict, resolve the contradiction against implementation and direct verification before proceeding.
8. Verify only the systems you will depend on for the task at hand.

If a verification command fails because of the local environment, record that failure in `PROJECT_STATE.yaml` or `WORKLOG.md` instead of guessing.

If multiple current docs disagree, do not pick the most convenient narrative. Check the code, deployed configuration, logs, provider state, and direct runtime behavior first. Then correct or quarantine the stale documentation before continuing.

---

## Session Start Triage

Before editing or verifying anything substantial:

1. Check `git status --short`.
2. Check `git log --oneline --decorate -n 5`.
3. Classify the task:
   - docs_or_process_only
   - verification_only
   - app_code
   - data_pipeline
   - infrastructure
4. Decide the minimum verification needed for that task before you start changing files.
5. If the worktree is dirty or `main` is moving, isolate the task scope before editing shared docs or claiming success.

The goal is to reduce accidental collisions, unnecessary doc churn, and invalid completion claims.

---

## Cost-Control Operating Mode

The target architecture remains Azure-based, but the active execution mode can be local-only.

When the user has paused Azure deployment to save costs:
- default to local runtime, local PostgreSQL, local Tracardi, and local verification work
- do not treat Azure deployment, Azure smoke tests, or cloud verification as the next automatic step
- keep Azure state in `PROJECT_STATE.yaml` and `STATUS.md` as historical context unless the user explicitly reopens that path
- local-only tasks may be considered complete after local verification plus the required doc updates; defer push, CI/CD, and Azure deployment verification until cloud work is explicitly back in scope

---

## Autonomous Continuation Protocol

High autonomy is the default operating mode for this repo.

After completing the required read order and session triage, the agent should continue work without asking the user what to do next when a safe, high-priority next step is already clear from:

- the most recent handoff
- `NEXT_ACTIONS.md`
- the current implementation state
- directly verified blockers or follow-up items

Default behavior:

1. Continue from the latest handoff first if it names a concrete unfinished task.
2. Otherwise pick the highest-priority unblocked item from `NEXT_ACTIONS.md`.
3. Choose the smallest useful unit that produces real, verifiable progress.
4. Prefer implementation, targeted verification, or contradiction cleanup over conversational check-ins.

Do not stop to ask the user "what next?" when the next safe step is already clear.

Interrupt the user only when:

- the request or goal is genuinely ambiguous
- a serious risk, destructive action, or privacy/security issue requires confirmation
- required credentials, approvals, infrastructure access, or missing dependencies make progress unsafe
- the repo presents two or more materially different valid directions and the tradeoff matters

For vague prompts such as "continue", "do something useful", or a pasted handoff, treat them as authorization to resume autonomously under this protocol.

---

## Context Budget And Session Yield

Agents must not wait until reasoning quality degrades before handing off.

If the agent estimates its remaining effective context budget is approaching roughly 20% or less:

1. Stop opening new broad context unless it is required to avoid a false claim.
2. Do not start another long verification loop, large refactor, or broad repo audit.
3. Finish the smallest safe unit of the current task.
4. Update the required docs for the work already done.
5. Produce a copy-pasteable `## Handoff` block for the next session.

Preferred behavior:

- yield early with a precise handoff rather than continue with degraded accuracy
- preserve evidence, run IDs, SHAs, blockers, and next checks
- leave the next agent a smaller, sharper starting point

When the yield is triggered mainly by context pressure, say so explicitly in the handoff.

---

## Smallest Useful Verified Increment

When resuming work from a handoff or `NEXT_ACTIONS.md`, avoid opening a broad implementation front unless it is already clearly justified.

Preferred pattern:

1. Verify the current state relevant to the chosen task.
2. Make one scoped change or complete one scoped verification target.
3. Run the smallest targeted validation that proves the step worked.
4. Update the required docs.
5. Either continue to the next scoped increment or hand off.

Avoid speculative large-scope work that has not yet been justified by repo patterns, priority, or direct evidence.

---

## Stable Architecture - AZURE INFRASTRUCTURE

**ALL REPO-MANAGED INFRASTRUCTURE IS AZURE-BASED:**

- **Azure VMs** (vm-tracardi-cdpmerged-prod, vm-data-cdpmerged-prod) - Tracardi + Elasticsearch
- **Azure Container Apps** (ca-cdpmerged-fast) - Chatbot deployment
- **Azure OpenAI** (gpt-4o-mini) - LLM provider
- **External source systems** (Teamleader, Autotask, Exact, websites, campaign tools) - PII and operational master records outside the repo-managed infrastructure boundary
- **PostgreSQL** - Canonical customer-intelligence and analytical truth layer for business/public master data, identity links, enrichment outputs, AI decision provenance, consent, canonical segments, audit-friendly facts, and the chatbot query plane
- **Tracardi** - Operational event/profile projection, workflow automation, score/tag projection, audience activation, and outbound marketing coordination
- **AI chatbot** - Natural-language operator interface that must answer authoritative data questions from PostgreSQL or a PostgreSQL-backed semantic layer, and may call Tracardi only for workflow/action execution and recent operational context

Repository-managed infrastructure runs on Azure. This is the target or managed architecture, not necessarily the active execution mode for the current session. Within the CDP stack, PostgreSQL is the customer-intelligence and analytical system of record, while Tracardi is the activation/runtime layer. PII remains owned by the source systems unless an explicit, verified architecture change says otherwise.

### Canonical Role Boundaries

- Source systems remain the PII system of record and the place where names, emails, phones, and other private contact details are resolved.
- Land canonical business data in PostgreSQL first.
- Write AI-derived tags, behavioral aggregates, and other analytically relevant facts to PostgreSQL with provenance; then project the operational slice into Tracardi.
- Project only the operational slice that workflows or campaigns need into Tracardi.
- Store authoritative segment definitions, identity mappings, consent state, audit trails, and analytics-ready facts outside Tracardi.
- Canonical segment logic lives in SQL or explicit metadata outside Tracardi. Tracardi receives projected segment state for activation.
- The chatbot must use deterministic PostgreSQL-backed tools for counts, filtering, analytics, and 360 views.
- The LLM may classify intent, extract filters, ask for clarification, and summarize results. It must not be treated as the authoritative execution engine for free-form production SQL or factual answers from Tracardi.
- Backend query execution, tool logs, audit logs, and conversation logs should use UIDs or controlled references rather than names, emails, or phones wherever feasible. Resolve PII only at an authorized presentation or activation step.
- Keep the source-identity bridge stable and reconciled. If an upstream system merges or splits records, reconcile the UID mapping in PostgreSQL first and then repair downstream projections.
- Downstream campaign or delivery tools should receive the minimum operational payload. Prefer resolving destination PII at authorized send time from the source system or a controlled service instead of treating downstream tools as permanent PII stores.
- Prefer lazy or need-based Tracardi profile creation for active UIDs unless a verified requirement justifies a broader projection.
- Do not describe Tracardi as the primary profile store, primary query plane, or source of truth in current docs unless implementation has actually changed and that change has been verified.
- Do not use the phrase "source of truth" without qualifying the layer when privacy boundaries matter:
  - source systems = PII and operational master truth
  - PostgreSQL = customer-intelligence and analytical truth
  - Tracardi = activation/runtime projection
- If the codebase temporarily diverges from this target architecture, document the gap explicitly in `PROJECT_STATE.yaml`, `STATUS.md`, and `NEXT_ACTIONS.md`.

---

## Documentation Model

| File | Role | Update when |
|------|------|-------------|
| `AGENTS.md` | Stable rules, architecture, decision guardrails | Only when the operating model changes |
| `STATUS.md` | Human-readable snapshot of current best-known state | When the summary view changes |
| `PROJECT_STATE.yaml` | Structured source for live state, confidence, verification evidence | After every meaningful verification or state change |
| `NEXT_ACTIONS.md` | Active queue, current task, paused items | When execution priority changes |
| `BACKLOG.md` | Medium-term work and milestone tracking | When priorities or milestone status changes |
| `WORKLOG.md` | Append-only record of what happened in each session | After each completed or paused task |
| `HANDOVER_TEMPLATE.md` | Standard safe handoff format for future sessions | When the handoff pattern changes |

Rules:

- Do not store the same live status in multiple places unless one file is explicitly a summary of another.
- `PROJECT_STATE.yaml` is the structured live-state source.
- `STATUS.md` must reflect `PROJECT_STATE.yaml`, not override it.
- Root-level quick-summary clones are retired; do not recreate them unless the user explicitly asks for one and the ownership cost is justified.
- Docs/process-only tasks should not rewrite live status docs unless the live understanding actually changed.
- If a current doc is known stale and cannot be fixed immediately, mark it clearly as `STALE` or `QUARANTINED` and point to the better evidence.
- Historical notes may remain historical, but current-state sections must not silently preserve false claims.
- Do not paste secrets, passwords, API keys, or install tokens into documentation or prompts.

---

## Verification Policy

Use one of these labels for operational claims:

- `observed` - verified directly in the current session
- `reported` - supported by logs or prior documentation, but not re-verified now
- `blocked` - verification attempted, but environment/tooling prevented it
- `assumed` - temporary working assumption; avoid when possible

Every live-state claim should carry:

1. a status label
2. a date
3. evidence or the command attempted

### Verification by Task Type

| Task type | Minimum verification |
|-----------|----------------------|
| Docs/process | Check links, file references, and update `WORKLOG.md` |
| App code | Run targeted tests or lint for changed areas |
| Data pipeline | Run the specific script/query affected and record sample evidence |
| Infrastructure | Prefer `terraform show`, `terraform state list`, service health checks, or provider outputs |

Do not run the full pytest, lint, and mypy suite for every documentation-only task unless that work actually changes code behavior.

When privacy boundaries are part of the claim, verify the actual data path and the actual logging path before declaring compliance.

---

## Verification Freshness Windows

Use fresh evidence for unstable operational claims. If the claim is older than the window below and has not been rechecked in the current session, downgrade it to `reported` unless there is a stronger reason not to.

| Claim Type | Freshness Window |
|-----------|------------------|
| CI/CD result for the current head SHA | same session and same SHA |
| Deployment/revision health for the current head | 24 hours |
| Service runtime health | 24 hours |
| Counts, coverage metrics, enrichment totals | 48 hours |
| Historical architectural decisions | stable unless superseded |

Additional rules:

- A green run for an older SHA is not proof that the latest SHA is green.
- A health check for an older deployed revision is not proof that the latest revision is healthy.
- If you are unsure whether evidence is still fresh enough, re-check it or label it `reported`.

---

## Task Classes And Update Scope

Use the smallest documentation footprint that still keeps current docs truthful.

| Task Class | Minimum doc updates |
|-----------|---------------------|
| docs_or_process_only | touched doc plus `WORKLOG.md`; update live-state docs only if live understanding changed |
| verification_only | `PROJECT_STATE.yaml` plus any summary doc affected, and `WORKLOG.md` |
| app_code | `WORKLOG.md`, targeted verification evidence, and live-state docs if behavior changed |
| data_pipeline | `WORKLOG.md`, `PROJECT_STATE.yaml`, and queue updates if follow-up changed |
| infrastructure | `WORKLOG.md`, `PROJECT_STATE.yaml`, queue updates, and any affected summaries |

Do not create status churn by rewriting `STATUS.md` or `NEXT_ACTIONS.md` for a docs-only edit that did not change the real system state.

---

## Repo-Fit Check Before New Patterns

Before adding a new package, ORM, framework, directory structure, service layer, persistence abstraction, or broad architectural pattern:

1. Check whether the repo already uses that pattern.
2. Check the existing dependency manager and lockfile.
3. Check how similar behavior is already implemented in code, migrations, and tests.
4. Prefer extending an existing pattern over introducing a new one.

If you still need to introduce a new pattern:

- keep the first change minimal
- explain the rationale in code comments or docs only where useful
- update the project-managed dependency files if dependencies change
- do not assume a local-only installation proves the repo now supports that pattern

Do not create broad new subsystems from a vague prompt without first proving repo fit and task priority.

---

## Environment Mutation Discipline

Do not mutate the local development environment as a substitute for making a proper repo change.

Rules:

1. Do not `pip install`, `poetry add`, `npm install -g`, or otherwise add tools or libraries ad hoc unless that change is intentionally part of the task.
2. If a new project dependency is required, add it through the repo's actual dependency-management flow and commit the resulting project files.
3. Do not rely on an uncommitted local package install as evidence that the repository change is correct.
4. If a missing tool blocks verification, prefer:
   - the project's existing tool runner
   - an already-declared dependency
   - a documented blocker
5. Only perform ephemeral environment mutation when the user explicitly wants machine-local setup work, and document that it is environment-local rather than repo-codified.

---

## Context Discipline

Do not gather broad context "just in case."

Rules:

1. Read only the files needed to complete the active task safely.
2. Do not scan the whole repository for everything you might ever need.
3. When enough context exists to act safely, stop exploring and start executing.
4. If context pressure is rising, narrow the task or hand off instead of widening the search surface.

The aim is to keep reasoning sharp and preserve performance across long sessions.

---

## Non-Interactive Execution Preference

Prefer non-interactive commands and workflows.

Rules:

1. Do not use interactive git staging or editing flows such as `git add -p`.
2. Prefer one scoped push and one verification pass over repeated blind retries.
3. Prefer explicit commands that can be reproduced in a handoff.
4. If a workflow is long-running, switch to the async handoff protocol instead of repeated sleep-and-poll loops unless a short final check is clearly worthwhile.

---

## When Plans Change

If the user changes direction mid-task:

1. Stop the current task.
2. Mark the item in `NEXT_ACTIONS.md` as `PAUSED` with a reason.
3. Add a short note to `WORKLOG.md`.
4. Update `BACKLOG.md` only if project priority actually changed.
5. Ask the user a clarifying question only if the new direction is ambiguous.

Do not silently abandon work.

---

## Dirty Worktree And Shared Branch Protocol

This repo is often worked on by multiple agents or sessions.

1. Treat any uncommitted change you did not make as user-owned or session-owned unless you can prove otherwise.
2. Do not revert, reformat, or fold unrelated local edits into your task.
3. Capture the start-of-session worktree snapshot from `git status --short` and use it to distinguish pre-existing dirty paths from paths touched in the current session.
4. If shared docs such as `PROJECT_STATE.yaml`, `STATUS.md`, `NEXT_ACTIONS.md`, or `WORKLOG.md` are already dirty, append the smallest safe change possible.
5. **CRITICAL:** If you modify any file during the session (even one that was pre-existing dirty), you must commit those specific changes before handoff. Do not leave files dirty that you touched.
6. If you cannot update a required shared doc safely because of unrelated local edits, record the blocker in `WORKLOG.md` and explain it in the handoff.
7. Do not claim the worktree is clean unless you checked it in the current session.
8. Every handoff for a dirty worktree must explicitly separate:
   - pre-existing dirty paths
   - paths touched this session
   - paths left dirty by this session
   - any path ownership that remains unclear
9. If ownership is unclear, say `ownership_unclear` instead of guessing.
10. A handoff that omits dirty-worktree ownership when the worktree is dirty is incomplete.
11. **CRITICAL:** Before writing any handoff, rerun `git status --short`.
12. Do not provide a handoff while the worktree is dirty.
13. If only session-owned changes remain, commit them before handoff.
14. If pre-existing or ownership-unclear dirty paths remain, clean the worktree first by an explicit action that preserves or resolves them (for example: user-approved commit, stash, or discard). If that cannot be done safely, escalate to the user instead of handing off over a dirty worktree.

---

## Workflow Feedback Loop

Treat recurring workflow friction as a protocol bug, not just a chat note.

Examples:
- dirty worktrees that make ownership unclear
- handoffs that are not copy-pasteable into a new session
- repeated status drift between current docs
- repeated verifier confusion about which evidence source is authoritative

When one of these appears:
1. Fix the immediate task safely.
2. Update `AGENTS.md`, `HANDOVER_TEMPLATE.md`, or another stable process doc in the same session if the fix is clear and low-risk.
3. If you cannot codify the fix immediately, record the protocol gap in `WORKLOG.md` and add a follow-up item to `NEXT_ACTIONS.md`.
4. Do not leave a recurring workflow failure only as conversational feedback.

---

## When Facts Conflict

If you find contradictory claims in the repo:

1. Stop and identify exactly which files, logs, or systems conflict.
2. Resolve the conflict by checking what is actually implemented:
   - source code
   - deployed configuration
   - provider/runtime state
   - logs
   - direct verification commands
3. Prefer implementation plus direct verification over stale narrative docs.
4. Fix current source-of-truth docs first:
   - `PROJECT_STATE.yaml`
   - `STATUS.md`
   - `NEXT_ACTIONS.md`
5. Remove, archive, or clearly label outdated guidance if it is still in a current location.
6. Only continue with new work once the contradiction is documented and the current docs are aligned.

Do not preserve a known-false current-state claim for convenience.

---

## Moving Main And Superseded Verification

If `main` or the active branch advances while you are verifying:

1. Tie every CI/CD claim to an explicit commit SHA.
2. Treat cancelled, superseded, or older-sha workflow runs as insufficient for completion.
3. Re-check the latest head before declaring success.
4. If another commit lands before your verification finishes, say so explicitly in `WORKLOG.md`, `PROJECT_STATE.yaml`, or handoff as appropriate.
5. Do not claim deployment success for the latest head from an older revision or an older successful run.

For handoffs and final updates, prefer language like:
- verified green for commit `<sha>`
- superseded by newer commit `<sha>`
- latest head not yet re-verified

---

## Async CI/CD Continuation Protocol

Long-running CI/CD must not trap the session in idle waiting.

After a push:

1. Capture the exact branch, commit SHA, and workflow run IDs.
2. Wait only long enough to confirm the relevant workflows were created and did not fail immediately.
3. Recommended maximum idle wait budget: about 2 minutes total unless the user explicitly asks you to stay and watch.
4. If CI/CD is still `queued` or `in_progress` after that budget, stop waiting and hand off the monitoring work.
5. Record the last observed status for each required workflow.
6. State clearly whether the task is:
   - `COMPLETE` because the required SHA is verified green
   - `PARTIAL` because the implementation is done but CI/CD is still pending
   - `BLOCKED` because CI/CD failed or verification could not proceed

Strict completion rule:

- A task that requires CI/CD is not `COMPLETE` until the required workflows are green for the exact SHA being handed off.
- A session does not need to remain open until that happens.

Next-agent continuation rule:

1. If the previous handoff includes pending CI/CD runs, check those runs before claiming that prior task is complete.
2. If the runs were superseded by a newer SHA, say so explicitly and re-verify on the newer SHA if that newer SHA is now the relevant target.
3. Do not treat older successful runs as completion proof for a newer commit.

---

## When New Problems Are Discovered

If you discover a new bug, regression, blocker, security issue, privacy issue, data-quality issue, operational risk, or documentation gap during any task, document it immediately instead of waiting for handoff.

Minimum protocol:

1. Classify the problem in plain language:
   - what was discovered
   - why it matters
   - what it affects
2. Record it in `PROJECT_STATE.yaml` if it changes the live understanding of the system, risk, or verification status.
3. Add or update the corresponding item in `NEXT_ACTIONS.md` if follow-up work is required.
4. Append a short entry to `WORKLOG.md` in the same session with the evidence and the action taken.
5. Update `STATUS.md` if the problem materially changes the human-readable summary of current state.
6. If the problem blocks the current task, mark the task `BLOCKED` or `PAUSED` in `NEXT_ACTIONS.md` and state the reason.

Problem record minimum fields:

```yaml
problem_identifier:
  status: observed | reported | blocked | assumed
  severity: critical | high | medium | low
  discovered_at: YYYY-MM-DD
  summary: short plain-language description
  evidence:
    - command, log, file, or runtime check
  affects:
    - code_path_or_system
  owner: agent | user | unknown
  next_action: concrete follow-up
```

If the exact YAML structure does not fit the file, preserve the same information in prose or bullets.

Documentation timing rules:

- Do it when the problem is discovered, not only at the end of the task.
- Use `observed`, `reported`, `blocked`, or `assumed` labels consistently.
- Include the command, log, file, runtime check, or other evidence that exposed the problem.
- If the problem is not yet fully understood, document the uncertainty explicitly instead of waiting for perfect information.

Do not continue under a newly discovered false assumption without first recording the issue in the current docs.

---

## Blocker Ownership

Every blocker must end the session in one of these states:

1. fixed_now
2. documented_and_paused
3. escalated_to_user

Do not leave a blocker only mentioned in passing. It must have a documented owner, evidence, and next action.

---

## Destructive Change Gate

Before deleting, replacing, or tearing down infrastructure:

1. Capture the current evidence:
   - state output, plan, endpoint checks, or screenshots
2. Record the blast radius:
   - what services, data flows, and credentials will be affected
3. Record the rollback path:
   - how to restore or redeploy
4. Get explicit user approval
5. Log the action in `WORKLOG.md`

No destructive infrastructure change should happen based on an unverified assumption.

---

## Completion Minimum

After completing work:

1. Append a short entry to `WORKLOG.md`.
2. Update `PROJECT_STATE.yaml` if any state was verified, changed, or any new problem was discovered that affects live understanding.
3. Update `NEXT_ACTIONS.md` if the active queue changed or a newly discovered problem requires follow-up, pause, or reprioritization.
4. Update `BACKLOG.md` if milestone or priority status changed.
5. Update `STATUS.md` only if its human-readable summary changed.
6. Update this file only if the workflow rules or architecture changed.
7. If the task exposed contradictory current documentation, fix or quarantine that contradiction before handoff.
8. End every session with a copy-pasteable `## Handoff` block, even for completed tasks.
9. Rerun `git status --short` immediately before preparing the handoff.
10. Clean the worktree before handoff. If that requires a user decision on pre-existing or ownership-unclear changes, stop and escalate instead of handing off a dirty tree.
11. Make the next safe step explicit in the handoff so the next session can resume autonomously.
12. If the worktree was dirty earlier in the session, include start-vs-end ownership details in the handoff and how it was cleaned.
13. If a protocol gap was discovered and fixed, log that workflow change in `WORKLOG.md`.

Git commits are recommended when the work is self-contained and the worktree allows a clean, scoped commit.

---

## Handoff Template

Use [`HANDOVER_TEMPLATE.md`](/home/ff/Documents/CDP_Merged/HANDOVER_TEMPLATE.md) as the standard safe handoff pattern.

The minimum handoff structure remains:

```markdown
## Handoff

**Date:** YYYY-MM-DD
**Task:** [brief task name]
**Type:** docs_or_process_only / verification_only / app_code / data_pipeline / infrastructure
**Status:** COMPLETE / PARTIAL / BLOCKED / PAUSED
**Canonical Repo:** `/home/ff/Documents/CDP_Merged`
**Git Head:** [sha] or `not rechecked`
**Worktree:** clean / dirty / not rechecked
**Pre-Existing Dirty Paths:** [paths] / `none` / `ownership_unclear`
**Touched This Session:** [paths] / `none`
**Left Dirty By This Session:** [paths] / `none`
**Resume From Here:** [one concrete next action]

### What changed
- [file or system change]
- [file or system change]

### Verification
- [command run or evidence reviewed]
- [result]

### Follow-up
1. [next action]
2. [next action]
```

---

## Source of Truth Hierarchy

1. `AGENTS.md` for operating rules
2. `PROJECT_STATE.yaml` for structured live state
3. `STATUS.md` for narrative live status
4. `NEXT_ACTIONS.md` for the active queue
5. `BACKLOG.md` for medium-term priorities

---

## Infrastructure as Code (IaC) Compliance

**MANDATORY:** All infrastructure changes, configuration patches, and hotfixes must be codified in the IaC templates.

### Rules

1. **No manual SSH changes** - Changes made via SSH to VMs are temporary and must be codified in:
   - Terraform configurations (`infra/tracardi/*.tf`)
   - Cloud-init templates (`infra/tracardi/cloud-init/*.tftpl`)
   - Docker Compose files (via cloud-init write_files)
   - Configuration management scripts (called from cloud-init runcmd)

2. **Hotfix Pattern** - For urgent hotfixes:
   - First apply via SSH to verify the fix
   - Immediately codify in cloud-init templates
   - Test `terraform plan` to ensure no drift
   - Document in `PROJECT_STATE.yaml` with `iac_compliance: enforced` label

3. **Verification** - After any IaC change:
   - Run `terraform plan` to verify no unexpected changes
   - Document the planned changes in `WORKLOG.md`
   - For new deployments, verify hotfixes are applied via cloud-init logs

### IaC Structure

| Component | Path | Purpose |
|-----------|------|---------|
| Terraform configs | `infra/tracardi/*.tf` | Azure resources, VMs, networking |
| Cloud-init templates | `infra/tracardi/cloud-init/*.tftpl` | VM provisioning, Docker setup, patches |
| Scripts | `infra/tracardi/scripts/` | Helper scripts for manual operations only |

---

## Git Workflow and CI/CD Compliance

**MANDATORY:** All code changes must be committed, pushed, and verified through CI/CD before being considered complete.

Temporary local-only exception:
- When the user has explicitly paused Azure deployment for cost control, local-only tasks do not require a push, GitHub Actions run, or Azure deployment verification to be considered complete.
- Resume the full push, CI/CD, and deployment protocol only when the task is intended for remote deployment or the user explicitly reopens cloud work.

### Commit and Push Protocol

1. **Stage Changes** - Add only the files relevant to the current task:
   ```bash
   git add <specific-files>
   ```
   Avoid `git add .` unless you have verified the changes comprehensively.

2. **Write Clear Commit Messages** - Follow conventional commit format:
   ```
   <type>(<scope>): <subject>
   
   <body explaining what and why>
   
   <footer: references, breaking changes>
   ```
   Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `hotfix`

3. **Commit Scope** - Keep commits atomic and focused:
   - One logical change per commit
   - Do not mix feature work with unrelated refactoring
   - Do not commit secrets, credentials, or environment-specific config

4. **Push to Origin**:
   ```bash
   git push origin <branch>
   ```

### CI/CD Verification Protocol

After pushing, you **MUST** verify CI/CD pipeline execution:

| Step | Action | Command/Method |
|------|--------|----------------|
| 1 | Check workflow status | `gh run list --limit 5` or GitHub Actions web UI |
| 2 | Wait for completion | `gh run watch <run-id>` |
| 3 | Verify success | `gh run view <run-id> --exit-status` |
| 4 | Confirm deployment | Check Azure Container App revision or VM state |

If the workflows are still running after the async wait budget, switch to the handoff flow instead of staying idle.

### CI/CD Compliance Rules

1. **No Handoff Without Green CI** - A task is not complete until:
   - All GitHub Actions workflows pass
   - Container images are successfully built and pushed
   - Deployments reach "Succeeded" state (Azure)

2. **Failed Pipeline Protocol**:
   - Immediately investigate logs: `gh run view <run-id> --log-failed`
   - Fix the root cause, not just the symptom
   - Re-push and re-verify until green
   - Document intermittent failures in `WORKLOG.md`

3. **Deployment Verification**:
   - Container Apps: Check revision status via `az containerapp revision list`
   - VMs: Verify services are healthy post-deployment
   - APIs: Run smoke tests against deployed endpoints

4. **Post-Deployment Smoke Test**:
   ```bash
   # Example: Verify deployed API is responding
   curl -sS -m 15 https://<deployed-endpoint>/health
   ```

5. **Superseded Run Rule**:
   - A successful workflow run counts only for the SHA it actually tested.
   - If a newer push cancels or supersedes the run, re-verify on the newer SHA before calling the task complete.
   - Record the verified SHA in `WORKLOG.md` or handoff when CI/CD status matters to completion.

6. **Async Monitoring Rule**:
   - Agents should not burn most of a session waiting on long GitHub Actions or deployment completion.
   - Once the run IDs, SHA, and last observed status are captured, monitoring may be handed to the next session through the required handoff.
   - The handoff must include enough detail for the next agent to resume verification without rediscovering context.

### Branch Strategy

| Branch | Purpose | Protection |
|--------|---------|------------|
| `main` | Production-ready code | Require PR reviews |
| `push-clean` | Direct push for urgent fixes | Avoid if possible |
| `feature/*` | Feature development | PR required |
| `hotfix/*` | Emergency production fixes | Fast-track PR |

### Rollback Protocol

If a deployment causes issues:

1. **Immediate**: Revert the commit: `git revert <commit-sha>`
2. **Push the revert**: `git push origin main`
3. **Verify CI/CD**: Ensure revert deploys successfully
4. **Document**: Add entry to `WORKLOG.md` with incident details

---

## Screenshot and Demo Integrity - STRICT PROHIBITION

**ABSOLUTE RULE:** Never create fake screenshots, mock interfaces, or synthetic demo content.

### What is FORBIDDEN

1. **❌ Fake Screenshots:** Creating HTML/CSS mockups that look like screenshots
2. **❌ Synthetic Data Claims:** Claiming mock data is real production data
3. **❌ Composited Images:** Combining real screenshots with fake elements
4. **❌ Staged Text Content:** Writing fake conversation transcripts as if they happened
5. **❌ Mock Interface Generators:** Scripts that generate fake UI screenshots

### What is REQUIRED

1. **✅ Real Runtime Capture:** Use browser tools to capture actual application state
2. **✅ Actual Query Results:** Run real queries against the database and show real results
3. **✅ Honest Data Attribution:** Clearly label test data vs production data
4. **✅ Real Conversations:** Capture actual chatbot interactions, not imagined ones
5. **✅ Verified Claims:** Every screenshot claim must be verifiable against the actual system

### Screenshot Verification Protocol

**Before using any screenshot in documentation:**

1. **Verify the source:**
   - Was this captured from the actual running application?
   - Can the same view be reproduced right now?
   - Are the dates/times in the screenshot recent?

2. **Verify the data:**
   - Do the numbers match actual database queries?
   - Are company names, counts, and metrics real?
   - Is there a path to reproduce this exact view?

3. **Label honestly:**
   - "Screenshot of local development instance"
   - "Test data shown - production data similar"
   - "Captured 2026-03-08 from staging environment"
   - Never imply test data is production data

### Caption-Content Alignment Protocol

**Every screenshot caption must accurately describe what is visible:**

1. **No aspirational captions:** If the screenshot shows an error, caption must say "Error" not "Success"
2. **No future-state captions:** Caption describes what IS shown, not what SHOULD BE shown
3. **Counts must match:** If caption says "1,652 companies", the screenshot must show 1,652
4. **Context must be clear:** Test data vs production data must be explicitly stated

**Pre-publication checklist:**
- [ ] Screenshot reviewed side-by-side with caption
- [ ] Numbers in caption verified against database/query results
- [ ] Error states captioned as errors, not successes
- [ ] Test data explicitly labeled
- [ ] Dates/times in screenshot are recent (within 24h for operational claims)

### Consequences of Violation

If you create fake screenshots or synthetic demo content:
1. You have compromised the trustworthiness of all documentation
2. You must immediately delete all fake content
3. You must document the violation in WORKLOG.md
4. You must re-capture all affected content using real runtime

### Correct Approach for Missing Screenshots

If a screenshot is needed but cannot be captured:

1. **Use browser tools:** Navigate to the actual application and capture
2. **Document the blocker:** "Screenshot pending - authentication required"
3. **Create a task:** Add to NEXT_ACTIONS.md for future capture
4. **Never fake it:** Leave the gap rather than create false evidence

### Source-of-Truth Documentation Standards

When documentation is designated as "source of truth" for the project:

1. **Every claim must be verified:** Run the actual query/command to verify counts
2. **Screenshots must be current:** Recapture if system state has changed
3. **Data must be realistic:** Use hyperrealistic mock data, not trivial test data (1 company → 50+ companies)
4. **End-to-end must be proven:** Show the full flow, not just component existence
5. **Contradictions must be resolved:** If two docs disagree, verify against implementation

### Illustrated Guide Directionality Rule

For `docs/ILLUSTRATED_GUIDE.md` and any derived guide assets:

1. Treat published guide claims as **delivery commitments**, not aspirational marketing copy.
2. If the guide claims a capability that the implementation or evidence does not yet support, the default action is to **fix or implement the project first**, then capture fresh evidence and screenshots.
3. Do **not** resolve the gap only by weakening or deleting the guide claim unless one of these is true:
   - the user explicitly de-scopes that claim
   - implementation is currently blocked or unsafe
   - the claim must be temporarily quarantined to avoid a false current-state statement while the implementation gap is being closed
4. If a claim is quarantined or downgraded temporarily, record the blocker and the concrete follow-up needed to make the implementation and evidence match the guide again.
5. The guide never overrides direct runtime verification for deciding what is true **now**, but guide claims do set the default expectation for what work must be completed unless the user changes scope.

**Mandatory demonstrations for CDP source-of-truth status:**
- 360° Golden Record: Single company query showing unified data from ALL sources
- Segment Activation: Actual segment push to email tool with populated audience
- Real-time Sync: Data change flowing from source → sync → chatbot within window
- CSV Export Validation: Opened file showing all claimed fields with real data
- Workflow Execution: Event triggering workflow with visible state changes

**Remember:** A missing screenshot is better than a fake screenshot.

---

## Decision Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-02-26 | Keep PostgreSQL as primary profile store | Scale, query flexibility, historical data |
| 2026-02-26 | Keep Tracardi in the target architecture | Event hub, workflow engine, and marketing integrations |
| 2026-03-02 | Separate stable rules from live status | Reduce contradictions and document drift |
| 2026-03-02 | Enforce IaC compliance via AGENTS.md | Ensure replicability, prevent configuration drift |
| 2026-03-02 | Enforce Git Workflow and CI/CD compliance | Prevent incomplete handoffs, ensure deployed code is verified |
| 2026-03-03 | Canonical production architecture is PostgreSQL-first with Tracardi as activation/workflow layer | Prevent ambiguity about source of truth, query plane, and operational roles |
| 2026-03-03 | Contradictory repo claims must be resolved against implementation before further work | Prevent stale docs from driving incorrect engineering decisions |
| 2026-03-03 | Clarify truth layers: source systems hold PII, PostgreSQL holds customer intelligence, Tracardi is a projected activation runtime | Prevent split-brain analytics and privacy-boundary confusion |
| 2026-03-03 | Newly discovered problems must be documented immediately in current docs, not deferred to handoff | Prevent silent drift, lost blockers, and false assumptions during execution |
| 2026-03-03 | Agents must classify task type, respect dirty shared worktrees, and treat superseded verification as invalid for completion | Reduce multi-agent collisions and false green claims |
| 2026-03-03 | Sessions must yield with handoff before context degradation and may hand off long-running CI/CD monitoring after initial verification | Preserve flow, reduce idle waiting, and keep handoffs reliable |
| 2026-03-03 | Agents should resume autonomously from handoff and queue, introduce new patterns only after repo-fit checks, and interrupt the user only for real uncertainty or serious issues | Maximize verified forward progress across sessions |
| 2026-03-04 | Track MCP, agent skills, GenAI observability, evals, and Responses alignment as future-value standards; keep A2A conditional and AG-UI/A2UI low-priority | Encourage modularity and future-proofing without trend-chasing |
| 2026-03-07 | When the user pauses Azure deployment to save costs, agents must switch to local-only execution and treat cloud deployment work as paused until explicitly resumed | Prevent unnecessary spend and stop stale Azure-first assumptions from driving the queue |
| 2026-03-07 | Any file modified in a session must be committed before handoff, even if pre-existing dirty | Prevent ambiguous dirty state and ensure clean handoffs |
| 2026-03-07 | Agents must clean the worktree before handoff; if pre-existing dirty paths block that, they must resolve or escalate instead of handing off a dirty tree | Prevent ambiguous ownership and stop repeated dirty-worktree handoffs |

---

*If this file starts reading like a live status page again, move that content into `STATUS.md` or `PROJECT_STATE.yaml`.*


---

## Current-vs-Historical Content Guardrail

`AGENTS.md` must stay stable. Do not store dynamic operational content here.

Keep the following out of `AGENTS.md`:
- current blockers, active incidents, or current deployment-health claims
- live enrichment percentages, current queue priorities, or current demo readiness status
- resolved-incident narratives that belong in `WORKLOG.md` or archived docs
- current automation schedules unless the schedule itself is a stable operating rule
- feature inventories and roadmap detail that belong in `BACKLOG.md`
- extra root-level quick summaries that duplicate `STATUS.md` or `PROJECT_STATE.yaml`

Put that information here instead:
- `PROJECT_STATE.yaml` for structured current state and verification evidence
- `STATUS.md` for concise human-readable current status
- `NEXT_ACTIONS.md` for active, paused, or reprioritized work
- `BACKLOG.md` for roadmap, milestones, and non-implemented inventory
- `WORKLOG.md` or `docs/archive/` for session history and resolved incidents

If `AGENTS.md` starts accumulating dynamic content:
1. Move current-state material into the appropriate state file.
2. Move historical detail into `WORKLOG.md` or an archive.
3. Keep only the stable rule, boundary, or decision that remains valid across sessions.

## Enrichment Verification Guardrail

When reporting enrichment progress or runner health:

1. Prefer canonical PostgreSQL counts as the truth source when reachable.
2. Use supervisor cursors, recent log activity, and process state as supporting evidence for progress claims.
3. Treat dashboards, `sync_status`, and stale cached docs as derived views that can lag or mislead.
4. If canonical database verification is blocked, record the failed command and downgrade the claim to `blocked` or `reported`.

Minimum evidence for a "running and making progress" claim:
- canonical SQL counts or an explicit documented blocker
- recent log or cursor advancement
- current process or supervisor state

## Task-Specific Guidance Placement

Use dedicated current-state docs instead of growing `AGENTS.md` with task-specific runbooks:
- demo readiness and current blockers -> `STATUS.md` and `NEXT_ACTIONS.md`
- live source real/mock/hybrid posture -> `PROJECT_STATE.yaml`
- medium-term capability gaps and non-implemented features -> `BACKLOG.md`
- one-off verification procedures or operational recipes -> dedicated docs under `docs/` when they need to persist

---

*End of AGENTS.md*
