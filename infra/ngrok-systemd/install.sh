#!/usr/bin/env bash
# Install ngrok systemd services with fixed ngrok-branded domain

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NGROK_CONFIG="$HOME/.config/ngrok/ngrok.yml"
SYSTEMD_DIR="$HOME/.config/systemd/user"
BIN_DIR="$HOME/bin"

echo "=== ngrok Stable Tunnel Installer (Hobbyist Plan) ==="
echo "Target URL: https://kbocdpagent.ngrok.app"
echo "Local port: 3000 (operator shell)"
echo ""

# Check for ngrok binary
if [ ! -f "$HOME/Documents/CDP_Merged/ngrok" ]; then
    echo "ERROR: ngrok binary not found at ~/Documents/CDP_Merged/ngrok"
    echo "Download from: https://ngrok.com/download"
    exit 1
fi

# Check ngrok version
NGROK_VERSION=$("$HOME/Documents/CDP_Merged/ngrok" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown")
echo "Found ngrok version: $NGROK_VERSION"

# Create directories
mkdir -p "$SYSTEMD_DIR" "$BIN_DIR" "$HOME/.config/ngrok" "$HOME/.local/share"
echo "Created directories"

# Copy ngrok config
cp "$SCRIPT_DIR/ngrok.yml" "$NGROK_CONFIG"
echo "Installed ngrok config to $NGROK_CONFIG"

# Copy systemd services
cp "$SCRIPT_DIR/cdp-operator-shell.service" "$SCRIPT_DIR/ngrok-cdp.service" "$SCRIPT_DIR/ngrok-cdp-watchdog.service" "$SCRIPT_DIR/ngrok-cdp-watchdog.timer" "$SYSTEMD_DIR/"
echo "Installed systemd services to $SYSTEMD_DIR"

# Copy and make executable the watchdog script
cp "$SCRIPT_DIR/check-ngrok-cdp.sh" "$BIN_DIR/"
chmod +x "$BIN_DIR/check-ngrok-cdp.sh"
echo "Installed watchdog script to $BIN_DIR"

# Reload systemd
systemctl --user daemon-reload
echo "Reloaded systemd"

# Enable linger for user services to survive logout
if command -v loginctl &>/dev/null; then
    loginctl enable-linger "$USER" 2>/dev/null || true
    echo "Enabled linger for user $USER"
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo ""
echo "1. VERIFY DOMAIN IS RESERVED:"
echo "   https://dashboard.ngrok.com/domains"
echo "   Should show: kbocdpagent.ngrok.app"
echo ""
echo "2. START SERVICES:"
echo "   systemctl --user start cdp-operator-shell.service"
echo "   systemctl --user start ngrok-cdp.service"
echo "   systemctl --user start ngrok-cdp-watchdog.timer"
echo ""
echo "3. VERIFY:"
echo "   curl https://kbocdpagent.ngrok.app"
echo ""
echo "4. CHECK STATUS:"
echo "   ./status.sh"
echo ""
