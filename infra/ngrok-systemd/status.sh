#!/usr/bin/env bash
# Quick status check for ngrok CDP services

set -euo pipefail

PUBLIC_URL="https://kbocdpagent.ngrok.app"
LOCAL_URL="http://127.0.0.1:3000"

echo "=== ngrok CDP Status ==="
echo "Target URL: $PUBLIC_URL"
echo ""

# Service status
echo "--- systemd Services ---"
systemctl --user is-active ngrok-cdp.service 2>/dev/null && echo "✓ ngrok-cdp.service: active" || echo "✗ ngrok-cdp.service: inactive"
systemctl --user is-active cdp-operator-shell.service 2>/dev/null && echo "✓ cdp-operator-shell.service: active" || echo "✗ cdp-operator-shell.service: inactive"
systemctl --user is-active ngrok-cdp-watchdog.timer 2>/dev/null && echo "✓ ngrok-cdp-watchdog.timer: active" || echo "✗ ngrok-cdp-watchdog.timer: inactive"
echo ""

# Local health check
echo "--- Health Checks ---"
if curl -fsS "$LOCAL_URL" --max-time 5 >/dev/null 2>&1; then
    echo "✓ Local operator shell (port 3000): healthy"
else
    echo "✗ Local operator shell (port 3000): unhealthy"
fi

# Public health check
if curl -fsS "$PUBLIC_URL" --max-time 10 >/dev/null 2>&1; then
    echo "✓ Public URL ($PUBLIC_URL): healthy"
else
    echo "✗ Public URL ($PUBLIC_URL): unhealthy"
fi
echo ""

# Show recent logs
echo "--- Recent Logs (last 5 lines) ---"
echo "ngrok-cdp.service:"
journalctl --user -u ngrok-cdp.service --no-pager -n 5 2>/dev/null || echo "  (no logs available)"
echo ""
echo "cdp-operator-shell.service:"
journalctl --user -u cdp-operator-shell.service --no-pager -n 5 2>/dev/null || echo "  (no logs available)"
echo ""

# Show public URL info
echo "--- Public Endpoint ---"
echo "URL: $PUBLIC_URL"
echo ""
echo "Test commands:"
echo "  curl $PUBLIC_URL"
echo ""
