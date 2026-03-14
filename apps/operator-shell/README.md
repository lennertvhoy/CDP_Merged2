# Operator Shell

Primary Next.js operator UI over the deprecated legacy Chainlit runtime backend.

This app is now the main user-facing shell on port `3000`. It still uses the
repo-owned operator bridge plus the existing `src.app` runtime as backend truth.
The public entry is a minimal private-preview gate. The full shell only renders
after successful access.

## Runtime split

- Recommended Node.js version: `24` (see `.nvmrc`; the workstation's `v25.8.1` produced a generic webpack failure during local verification)
- Deprecated legacy chat runtime backend: `uv run uvicorn src.app:chainlit_server_app --host 0.0.0.0 --port 8000`
- Operator bridge API: `uv run uvicorn src.operator_api:app --host 127.0.0.1 --port 8011`
- Operator shell frontend: `npm run dev`

Direct browser use of `http://localhost:8000` is deprecated and should no
longer be treated as a supported UI surface. Use `http://localhost:3000`.

## Environment

Copy `.env.example` to `.env.local`, point `OPERATOR_API_ORIGIN` at the operator bridge,
and keep `CHAT_RUNTIME_ORIGIN` pointed at the current `src.app:chainlit_server_app`
runtime backend.

For private previews behind a reverse proxy, prefer PostgreSQL-backed local
accounts instead of the legacy shared password:

```bash
printf '%s\n' 'VerySecret123!' | uv run python scripts/manage_operator_accounts.py create \
  --identifier colleague@example.com \
  --display-name "Colleague Name" \
  --password-stdin
```

Enable `CHAINLIT_LOCAL_ACCOUNT_AUTH_ENABLED=true` in `.env.local` to use those
accounts in the shell. Keep `CHAINLIT_ENABLE_AZURE_AD=false` for the current
preview gate; the OAuth path can be re-enabled later if needed.

## Online preview via ngrok

From the repo root, the repo now includes a dedicated launcher for the current
`3000 -> 8170 -> 8016` preview path:

```bash
./scripts/start_operator_shell_ngrok.sh
```

On the Bazzite workstation, the verified host path from the sandbox is:

```bash
flatpak-spawn --host sh -lc 'cd /home/ff/Documents/CDP_Merged && ./scripts/start_operator_shell_ngrok.sh'
```

This expects the shell to already be live on port `3000` and an ngrok auth token
to already be configured on the host. The script reuses an existing `3000` tunnel
when one is already running and prints the current HTTPS public URL.

Free-tier ngrok still adds its browser warning interstitial before the shell on the
first browser visit. After that click-through, the operator shell gate, local-account
sign-in, and same-origin API calls continue to work on the ngrok hostname.

## Real vs mocked

- Real now: private-preview gate, shell-owned sign-in/logout, chat send/streaming
  through the existing runtime, companies, company details, segments, segment CSV
  export, and auth-scoped thread list/detail with resume wiring in the shell
- Mocked now: sources, pipelines, activity, most settings

## Intent

The adapter boundary in `lib/adapters/` keeps real backend reads separate from mock surfaces so the shell can gain backend parity incrementally without moving truth into the frontend.
