# Operator Eval Standard

## Why This Exists

The chatbot already has deterministic retrieval coverage, but operator-quality failures still slip through when tests depend on hidden thread memory or only score factual correctness.

This standard makes each evaluation prompt self-contained and scoreable on user-facing quality, not just backend correctness.

## Required Prompt Structure

Every reusable operator eval should include all of the following:

1. `Role/Context`
   State who the chatbot is, what product it is inside, and what data/tools are in scope.
2. `Goal`
   State the exact user task.
3. `Constraints`
   Include geography, exclusions, allowed sources, privacy limits, required fields, or anti-hallucination rules.
4. `Workflow Expectation`
   State whether the bot should preview, clarify, confirm, or execute immediately.
5. `Desired Output`
   State the required output shape such as bullets, a table, a segment preview, a CSV action, or a change card.
6. `Success Criteria`
   State what a good answer must contain so scoring is reproducible.

## Core Rule

Every prompt must still be valid if all previous conversation turns are removed.

That means the prompt itself must carry:

- the task state
- the business context
- the execution expectation
- the evaluation target

## Default Scoring Dimensions

Use these five dimensions for operator-quality scoring:

| Dimension | What it measures |
|-----------|------------------|
| `intent` | Whether the chatbot understood the actual user task |
| `autonomy` | Whether it solved the task without avoidable back-and-forth or debug leakage |
| `trust` | Whether it stayed honest, source-disciplined, and explicit about uncertainty |
| `actionability` | Whether a real operator could immediately use the answer |
| `ux_product_polish` | Whether the answer feels like a product, not a debug console |

Score each dimension on `0-10`.

## Default Weighted Total

When a single rolled-up score is useful, use this weighting:

- `intent`: `20%`
- `autonomy`: `30%`
- `trust`: `30%`
- `actionability`: `20%`

Keep `ux_product_polish` visible as its own separate dimension so strong analysis does not hide weak product behavior.

## Mandatory Failure Checks

Flag these explicitly in every review:

- `tool_leakage`
  User-facing answer exposes internal tool names or planning traces such as `I will use...`, `search_profiles`, or `query_unified_360`.
- `answer_first_failure`
  Answer starts with internal process, blockers, or system narration instead of user-facing output.
- `hallucinated_missing_data`
  Missing information is invented instead of marked as absent or uncertain.
- `copy_ux_failure`
  Copy flows fail without graceful fallback when `ClipboardItem` or equivalent browser capability is missing.
- `export_ux_failure`
  Export flows return an internal path, opaque backend state, or a non-downloadable artifact without a clear user-facing limitation message.

## Output Pattern Expectations

These response patterns should be favored by default:

- answer first, internals second
- interpret implications, not just raw fields
- separate `facts`, `inference`, and `to validate`
- preview before mutation when the request changes segments, exports, or records

## Initial Coverage Targets

The eval bank should prioritize these product areas:

1. search and segment creation
2. segment interpretation and contact-coverage meaning
3. 360 account views with explicit inconsistencies and uncertainties
4. Belgian Staatsblad/KBO parsing and operations actions
5. export and copy UX regressions
6. ambiguity/disambiguation
7. prioritization and next-best-action style reasoning

## Repo Execution Path

For now:

- the canonical reusable prompts live in `docs/evals/operator_eval_cases.v1.json`
- the reusable manual scoring sheet lives in `docs/evals/operator_eval_scorecard_template.csv`
- the validation guard lives in `tests/unit/test_operator_eval_assets.py`

Later:

- wire these cases into an automated or semi-automated local eval harness
- store run artifacts and scorecards per model/app revision
