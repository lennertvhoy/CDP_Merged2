# Documentation Map

This directory now distinguishes clearly between current technical references, archived history, and obsolete material.

## Current

Current project state does **not** live here first. Start at the repo root:

1. `AGENTS.md`
2. `STATUS.md`
3. `PROJECT_STATE.yaml`
4. `NEXT_ACTIONS.md`
5. `BACKLOG.md`
6. `WORKLOG.md`

Use the rest of `docs/` for durable technical references such as:

- `ARCHITECTURE_AZURE.md`
- `ARCHITECTURE_DECISION_RECORD.md`
- `KBO_INGESTION.md`
- `SECRETS_AUDIT.md`
- `research/`
- `specs/`

## Archive

`docs/archive/` contains historical material that may still be useful for context:

- `status_history/` for dated status snapshots and correction notes
- `planning/` for superseded migration plans or planning copies
- `reports/` for one-off implementation or investigation reports
- `operations/` for archived operational SOPs tied to older workflows
- `roadmaps/` for superseded architecture or migration roadmaps
- `session_handoffs/` for older handoff context that is no longer current
- existing legacy archive folders preserved from earlier cleanups

Archived files are not current-state authority.

## Obsolete

`docs/obsolete/` contains materials preserved only because deleting them would hide useful audit history:

- prompt or handoff files with misleading workflow instructions
- reports that embedded credentials or other unsafe operational details
- stale navigation that pointed new agents at the wrong files

Do not use anything under `docs/obsolete/` for operational guidance.

## Secret Handling

- Keep real secrets out of tracked files.
- Use `.env.database.example` as the safe template for the local-only `.env.database`.
- If you find an old document with raw credentials, move or sanitize it instead of repeating the values elsewhere.
