# CDP_Merged

AI-assisted customer data platform built around PostgreSQL, Tracardi, and an operator chatbot.

**Last Updated:** 2026-03-06  
**Canonical Repo:** `/home/ff/Documents/CDP_Merged`

## Start Here

Read these files in order:

1. `AGENTS.md`
2. `STATUS.md`
3. `PROJECT_STATE.yaml`
4. `NEXT_ACTIONS.md`
5. `BACKLOG.md`
6. `WORKLOG.md`

## Repo Orientation

- `AGENTS.md` is the stable operating contract for agents.
- `PROJECT_STATE.yaml` is the structured live-state source.
- `STATUS.md` is the short human-readable current snapshot.
- `NEXT_ACTIONS.md` is the active and paused queue only.
- `BACKLOG.md` holds roadmap and medium-term planning.
- `WORKLOG.md` is the append-only session history.

Do not use `README.md` as a live status page. If a claim matters operationally, verify it in `PROJECT_STATE.yaml` or `STATUS.md`.

## Documentation Layout

### Current

Active, maintained documents stay at the repo root:

- `AGENTS.md`
- `STATUS.md`
- `PROJECT_STATE.yaml`
- `NEXT_ACTIONS.md`
- `BACKLOG.md`
- `WORKLOG.md`
- `HANDOVER_TEMPLATE.md`
- `CHANGELOG.md`

### Archived

Historical material that may still be useful for context lives under `docs/archive/`:

- `docs/archive/status_history/`
- `docs/archive/planning/`
- `docs/archive/reports/`
- `docs/archive/session_handoffs/`
- existing legacy archive folders already under `docs/archive/`

### Obsolete

Unsafe or misleading historical prompts and reports live under `docs/obsolete/`. Do not use them for live operations.

## Repository Map

- `src/`: application code
- `scripts/`: operational and utility scripts
- `ops/`: archived operational tooling moved out of the repo root
- `config/examples/`: safe example env/config fragments
- `infra/`: infrastructure code and deployment helpers
- `docs/`: durable technical documentation, archives, and obsolete material
- `tests/`: unit and integration coverage
- `logs/`: session and operational logs

## Safety Notes

- Real secrets must not live in the repo. Use `.env.database.example` as a template and keep the real `.env.database` local-only.
- Do not treat `docs/archive/` or `docs/obsolete/` as sources of current status.
- If a status claim matters operationally, prefer `PROJECT_STATE.yaml` over older summaries.
