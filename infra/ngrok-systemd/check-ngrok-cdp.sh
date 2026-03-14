#!/usr/bin/env bash
# Watchdog: Health check for operator shell and public ngrok tunnel

set -euo pipefail

LOCAL_URL="http://127.0.0.1:3000"
PUBLIC_URL="https://kbocdpagent.ngrok.app"
LOG_FILE="$HOME/.local/share/ngrok-cdp-watchdog.log"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

# Check if local operator shell is healthy
if ! curl -fsS "$LOCAL_URL" --max-time 10 >/dev/null 2>&1; then
    log "WARN: Local operator shell (port 3000) unhealthy, restarting cdp-operator-shell.service"
    systemctl --user restart cdp-operator-shell.service 2>/dev/null || true
    # Give app time to start before checking public URL
    sleep 5
fi

# Check if public tunnel is healthy
if ! curl -fsS "$PUBLIC_URL" --max-time 15 >/dev/null 2>&1; then
    log "WARN: Public tunnel unhealthy, restarting ngrok-cdp.service"
    systemctl --user restart ngrok-cdp.service
fi

log "INFO: Health check passed"
