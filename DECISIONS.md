# Architectural Decision Log

**Purpose:** Historical record of major architectural decisions.

**Note:** For still-active operating rules, see AGENTS.md. This file contains decisions that shaped the project but may no longer be active constraints.

---

## Active Decisions (Still In Effect)

| Date | Decision | Reason |
|------|----------|--------|
| 2026-03-14 | Illustrated Guide updates and PDF export are mandatory for every implementation session | Every session that changes code, tests, browser automation, UI, runtime, or user flow must update the Illustrated Guide, include evidence, and export to PDF; no session is complete without this |
| 2026-03-14 | Already-running Edge session on 127.0.0.1:9223 is mandatory for browser work | The attached Edge session preserves authenticated state and is the canonical browser path; do not spawn fresh browsers for canonical flows |
| 2026-03-14 | Tracardi is demoted from core dependency to optional activation adapter | Tracardi CE workflow execution requires Premium license; first-party event processor and PostgreSQL-backed writeback satisfy core demo/runtime needs without Tracardi |
| 2026-03-09 | Azure infrastructure deployment (Container Apps, VMs, managed PostgreSQL) is disabled to focus on local-only deployment | User directive to prioritize local development and avoid Azure infrastructure costs; CI/CD workflows disabled but preserved for reference |
| 2026-03-09 | Kubernetes is the target deployment architecture for datacenter | User confirmed ultimate deployment target is an on-prem/datacenter Kubernetes cluster (k3s/RKE2), not Azure Container Apps or docker-compose in production |
| 2026-03-08 | When browser access requires authentication to platforms (Teamleader, Exact, Resend, ngrok), prefer delegation to an AI agent with browser takeover capability over headless automation | Headless browsers cannot handle OAuth, 2FA, or active sessions; user delegation is more reliable and secure than requesting credentials |
| 2026-03-07 | When the user pauses Azure deployment to save costs, agents must switch to local-only execution and treat cloud deployment work as paused until explicitly resumed | Prevent unnecessary spend and stop stale Azure-first assumptions from driving the queue |
| 2026-03-07 | Any file modified in a session must be committed before handoff, even if pre-existing dirty | Prevent ambiguous dirty state and ensure clean handoffs |
| 2026-03-07 | Agents must clean the worktree before handoff; if pre-existing dirty paths block that, they must resolve or escalate instead of handing off a dirty tree | Prevent ambiguous ownership and stop repeated dirty-worktree handoffs |
| 2026-03-04 | Track MCP, agent skills, GenAI observability, evals, and Responses alignment as future-value standards; keep A2A conditional and AG-UI/A2UI low-priority | Encourage modularity and future-proofing without trend-chasing |
| 2026-03-03 | Agents must classify task type, respect dirty shared worktrees, and treat superseded verification as invalid for completion | Reduce multi-agent collisions and false green claims |
| 2026-03-03 | Sessions must yield with handoff before context degradation and may hand off long-running CI/CD monitoring after initial verification | Preserve flow, reduce idle waiting, and keep handoffs reliable |
| 2026-03-03 | Agents should resume autonomously from handoff and queue, introduce new patterns only after repo-fit checks, and interrupt the user only for real uncertainty or serious issues | Maximize verified forward progress across sessions |
| 2026-03-03 | Newly discovered problems must be documented immediately in current docs, not deferred to handoff | Prevent silent drift, lost blockers, and false assumptions during execution |
| 2026-03-03 | Contradictory repo claims must be resolved against implementation before further work | Prevent stale docs from driving incorrect engineering decisions |
| 2026-03-03 | Clarify truth layers: source systems hold PII, PostgreSQL holds customer intelligence, Tracardi is a projected activation runtime | Prevent split-brain analytics and privacy-boundary confusion |
| 2026-03-03 | Canonical production architecture is PostgreSQL-first with Tracardi as activation/workflow layer | Prevent ambiguity about source of truth, query plane, and operational roles |
| 2026-03-02 | Separate stable rules from live status | Reduce contradictions and document drift |
| 2026-03-02 | Enforce IaC compliance via AGENTS.md | Ensure replicability, prevent configuration drift |
| 2026-03-02 | Enforce Git Workflow and CI/CD compliance | Prevent incomplete handoffs, ensure deployed code is verified |

## Superseded Decisions

| Date | Decision | Superseded By | Reason for Change |
|------|----------|---------------|-------------------|
| 2026-02-26 | Keep Tracardi in the target architecture as core dependency | 2026-03-14: Tracardi optionalization | Tracardi CE limitations blocked core delivery; first-party alternatives proved sufficient |
| 2026-02-26 | Keep PostgreSQL as primary profile store | 2026-03-03: PostgreSQL-first canonical architecture | Refined from "primary store" to "customer-intelligence and analytical truth layer" with explicit role boundaries |

---

*For current operating rules, verification requirements, and handoff procedures, see AGENTS.md.*
