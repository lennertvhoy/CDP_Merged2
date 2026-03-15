# Illustrated Guide Compliance Requirements

**Purpose:** Mandatory documentation standards for all implementation sessions.

**Rule:** No session is complete unless the Illustrated Guide is updated and re-exported to PDF with new evidence included.

---

## Scope Trigger

For every session where you make a real change to:
- code
- tests/evals
- browser automation
- UI behavior
- runtime behavior
- user flow coverage

You **must** do all of the following before handoff:

1. Update `docs/ILLUSTRATED_GUIDE.md`
2. Add the new screenshot(s) or artifact reference(s) that prove the change
3. Describe the exact change that occurred
4. Describe what was verified directly in this session
5. Export the updated Illustrated Guide to PDF
6. Include the PDF file path in the report
7. Keep the worktree clean at the end

---

## Content Requirements

For each real implementation step completed in a session, update the guide with:

- date/session section
- short title of the change
- problem before
- change made
- verification performed
- result
- remaining gap
- screenshot(s) or artifact path(s)
- category label:
  - `ATTACHED_EDGE_CDP`
  - `ISOLATED_PLAYWRIGHT`
  - `API/backend`
  - `UI/runtime`
  - `eval/test`

If a screenshot exists, the guide must reference it explicitly by file path.

---

## Example Section Style

```markdown
### 2026-03-14 — Deterministic attached-Edge segments smoke
- Problem before: first-tab selection was fragile and 2 attached-Edge assertions failed.
- Change made: deterministic tab selection + corrected Segments smoke assertions.
- Verified directly: 17/17 attached-Edge tests passed.
- Artifacts:
  - `reports/e2e_evidence/segments_smoke_deterministic.png`
  - `reports/e2e_evidence/segments_smoke_latest.png`
- Status: canonical ATTACHED_EDGE_CDP path improved.
- Remaining gap: no chat-send smoke yet.
```

---

## PDF Export Requirements

After updating `docs/ILLUSTRATED_GUIDE.md`, export it to PDF every time:

- PDF must be regenerated from the latest guide content
- PDF must be committed if the guide changed meaningfully in that session
- Report must include:
  - exact PDF path
  - exact source markdown path
  - confirmation that PDF reflects the latest screenshots/changes

**Stable output path:** `reports/illustrated_guide/ILLUSTRATED_GUIDE_latest.pdf`

Optional timestamped history (additionally): `reports/illustrated_guide/ILLUSTRATED_GUIDE_YYYY-MM-DD_HHMM.pdf`

---

## Screenshot / Evidence Rule

If you claim a UI, browser, or flow change:
- capture at least one screenshot artifact
- reference it in the guide
- ensure the exported PDF reflects that new screenshot/evidence section

**No invisible evidence.**

---

## Handoff Extension for Illustrated Guide

A handoff is not complete unless all of the following are true:
- `git status --short` is empty
- intended changes are committed
- `docs/ILLUSTRATED_GUIDE.md` is updated if the session changed system behavior or coverage
- the Illustrated Guide PDF was exported from the current guide version
- the report includes the exact PDF path

---

## What is NOT Acceptable

- "Guide will be updated later"
- "Screenshots exist but not yet documented"
- "PDF export skipped this time"
- "Docs-only update without evidence"
- "Evidence captured but not included in guide"

---

## Required Report Sections

Append to every completion report:

15. Exact Illustrated Guide update made
16. Exact screenshots/artifacts added to the guide
17. Exact PDF export path
18. Exact export command(s) used
19. Exact proof the PDF reflects the latest session change

---

*Referenced from AGENTS.md. See canonical browser session rules in AGENTS.md section "Canonical Browser Session".*
