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

Until that harness exists, these files are the authoritative source for how new operator eval prompts should be written.
