# Secrets Audit

**Audit Scope:** Tracked documentation and repo-level configuration hygiene  
**Last Updated:** 2026-03-02

## Purpose

This document tracks where secrets are expected to live and what still needs human review.

It must not contain raw passwords, tokens, access keys, or connection strings.

## Current Rules

- Store real secrets in Azure, local untracked env files, or other approved secret stores.
- Keep tracked files limited to templates, secret names, and rotation guidance.
- If a historical document contains raw credentials, sanitize it or move it to `docs/obsolete/`.

## Secret Inventory

| Secret Name | Purpose | Source Of Truth | Rotation Needed |
|-------------|---------|-----------------|-----------------|
| `azure-openai-key` | Azure OpenAI API authentication | Azure Portal / Key Vault / Container App secret store | If compromised |
| `azure-search-api-key` | Azure AI Search admin access | Azure Portal / Key Vault / Container App secret store | If compromised |
| `resend-api-key` | Resend API access | Resend dashboard / Container App secret store | If compromised |
| `openai-api-key` | Fallback OpenAI access | OpenAI platform / Container App secret store | If compromised |
| `tracardi-password` | Tracardi admin authentication | Tracardi deployment secret source / Container App secret store | Recommended |
| Container registry credentials | Image pull access | Azure or GitHub registry secret source | If compromised or expired |

## What Changed In The 2026-03-02 Cleanup

- Removed raw secret values from current documentation.
- Replaced tracked `.env.database` with `.env.database.example`.
- Moved unsafe prompt and handoff files out of the active root surface.
- Updated `.gitignore` for local state and download artifacts.

## Human Review Still Needed

The cleanup session found remaining hardcoded credentials or secret-like values in tracked code and utilities. Review these areas before broader automation work:

- selected scripts under `scripts/`
- selected utilities under the repo root
- legacy helpers under `functions/`
- any shell scripts that still embed live endpoints or default credentials

## Safe Recovery Guidance

If a secret must be rotated or recovered:

1. Retrieve it from the system of record, not from repo history.
2. Update the live secret store.
3. Record the rotation in `WORKLOG.md` without pasting the value.
4. Re-run only the targeted verification needed for the affected component.
