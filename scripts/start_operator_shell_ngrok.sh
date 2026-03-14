#!/usr/bin/env bash

set -euo pipefail

PORT="${1:-3000}"
NGROK_WEB_ADDR="${NGROK_WEB_ADDR:-127.0.0.1:4040}"
NGROK_API_URL="http://${NGROK_WEB_ADDR}/api/tunnels"
LOG_FILE="${NGROK_LOG_FILE:-/tmp/cdp-operator-shell-ngrok.log}"
STARTUP_WAIT_SECONDS="${NGROK_STARTUP_WAIT_SECONDS:-15}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  fi
}

fetch_tunnels_json() {
  curl -fsS "$NGROK_API_URL"
}

extract_url_for_port() {
  sed -n "/\"addr\":\"http:\/\/localhost:${PORT}\"/ s/.*\"public_url\":\"\\([^\"]*\\)\".*/\\1/p" | head -n 1
}

extract_any_public_url() {
  sed -n 's/.*"public_url":"\([^"]*\)".*/\1/p' | head -n 1
}

print_success() {
  local public_url="$1"

  cat <<EOF
Operator shell ngrok tunnel is live.
Public URL: ${public_url}
Port: ${PORT}
Inspect API: ${NGROK_API_URL}
Log: ${LOG_FILE}

Notes:
- Free-tier ngrok browser visits show a warning interstitial once before the private preview gate.
- After click-through, the shell login and same-origin API calls continue to work on the ngrok hostname.
- The public URL is ephemeral unless you reserve a domain.
EOF
}

require_command curl
require_command npx

if [ ! -f "${HOME}/.config/ngrok/ngrok.yml" ]; then
  printf 'ngrok auth config not found at %s/.config/ngrok/ngrok.yml\n' "${HOME}" >&2
  printf 'Configure ngrok first, then rerun this script.\n' >&2
  exit 1
fi

existing_tunnels_json=""
existing_url=""

if existing_tunnels_json="$(fetch_tunnels_json 2>/dev/null)"; then
  existing_url="$(printf '%s' "$existing_tunnels_json" | extract_url_for_port)"
  if [ -n "$existing_url" ]; then
    print_success "$existing_url"
    exit 0
  fi

  other_url="$(printf '%s' "$existing_tunnels_json" | extract_any_public_url)"
  if [ -n "$other_url" ]; then
    printf 'Another ngrok agent is already using %s.\n' "$NGROK_WEB_ADDR" >&2
    printf 'Existing public URL: %s\n' "$other_url" >&2
    printf 'Stop that tunnel or rerun with NGROK_WEB_ADDR=127.0.0.1:4041.\n' >&2
    exit 1
  fi
fi

nohup npx -y ngrok http "$PORT" --web-addr="$NGROK_WEB_ADDR" --log=stdout >"$LOG_FILE" 2>&1 &

public_url=""
for _ in $(seq 1 "$STARTUP_WAIT_SECONDS"); do
  sleep 1
  if tunnels_json="$(fetch_tunnels_json 2>/dev/null)"; then
    public_url="$(printf '%s' "$tunnels_json" | extract_url_for_port)"
    if [ -n "$public_url" ]; then
      print_success "$public_url"
      exit 0
    fi
  fi
done

printf 'ngrok did not publish a tunnel for port %s within %s seconds.\n' "$PORT" "$STARTUP_WAIT_SECONDS" >&2
printf 'Inspect %s or the log at %s.\n' "$NGROK_API_URL" "$LOG_FILE" >&2
exit 1
