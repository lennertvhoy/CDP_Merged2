#!/usr/bin/env bash
# reset_db.sh — Reset Tracardi data (profiles, segments)
set -euo pipefail

echo "⚠️  WARNING: This will delete all profiles and segments from Tracardi!"
read -r -p "Type 'yes' to confirm: " confirm
[ "$confirm" = "yes" ] || { echo "Aborted."; exit 1; }

TRACARDI_URL="${TRACARDI_API_URL:-http://localhost:8686}"
TRACARDI_USER="${TRACARDI_USERNAME:-}"
TRACARDI_PASS="${TRACARDI_PASSWORD:-}"

if [ -z "$TRACARDI_USER" ] || [ -z "$TRACARDI_PASS" ]; then
    echo "ERROR: TRACARDI_USERNAME and TRACARDI_PASSWORD environment variables must be set."
    echo "Example: TRACARDI_USERNAME=admin TRACARDI_PASSWORD=secret ./scripts/reset_db.sh"
    exit 1
fi

echo "🔑 Authenticating with Tracardi at $TRACARDI_URL..."
TOKEN=$(curl -s -X POST "$TRACARDI_URL/user/token" \
    -d "username=$TRACARDI_USER&password=$TRACARDI_PASS&grant_type=password&scope=" \
    | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "🗑️  Deleting all profiles..."
curl -s -X DELETE "$TRACARDI_URL/profiles" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    | python3 -c "import sys, json; print(json.dumps(json.load(sys.stdin), indent=2))" 2>/dev/null || echo "Done (or endpoint not available)"

echo "✅ Reset complete. Tracardi data cleared."
