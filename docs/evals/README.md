# Operator Eval Assets

This folder holds the new self-contained operator-eval foundation for the chatbot.

## Purpose

These assets are meant to close the gap between:

- the existing retrieval/grounding harness in `tests/integration/`
- the newer product-quality concerns surfaced during screenshot review and prompt rewrites

The goal is to make chatbot evaluation reproducible even when conversation history is empty.

## Files

- `OPERATOR_EVAL_STANDARD.md` - canonical prompt format, scoring dimensions, and fail rules
- `operator_eval_cases.v1.json` - machine-readable starter bank of self-contained eval prompts
- `operator_eval_scorecard_template.csv` - reusable scoring sheet for manual or semi-manual reviews
- `../../scripts/prepare_operator_eval_run.py` - CLI that prepares timestamped review bundles
- `../../src/evals/operator_eval_run_prep.py` - reusable run-prep module behind the CLI

## Current Repo Path

Prepare a review bundle with:

```bash
poetry run python scripts/prepare_operator_eval_run.py \
  --output-dir output/operator_eval_runs \
  --model-provider openai \
  --model-name gpt-5
```

Each run emits:

- `manifest.json` with run metadata and selected case ids
- `cases.json` with the selected machine-readable prompts
- `scorecard.csv` with prefilled run/case metadata for review
- `prompts.md` with a reviewer-friendly prompt packet

## Current Scope

The starter bank focuses on the main operator workflows already visible in the current demo and review material:

- segment search
- 360 account summaries
- export UX
- copy/troubleshooting UX
- Belgian publication parsing
- cross-source mismatch analysis
- account disambiguation
- account prioritization

## Not Yet Done

- automatic execution of these cases against the live chatbot
- automated grading of answer-first behavior, tool leakage, and UX failures
- full migration of every historical scenario into this format

These files plus the run-prep harness are the authoritative source for how new operator eval prompts should be written and reviewed.
