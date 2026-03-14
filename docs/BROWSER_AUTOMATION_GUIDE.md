# Browser Automation Guide for CDP_Merged

**Last Updated:** 2026-03-14  
**Default Mode:** CDP Attach (Recommended)  
**Alternative:** Extension Mode (Documented, not default)

---

## Quick Start

```bash
# 1. Launch Edge with CDP (one terminal)
chrome-for-mcp

# 2. Verify CDP is active
curl http://127.0.0.1:9223/json/version

# 3. Use the Python helper for automation
python scripts/mcp_cdp_helper.py test
python scripts/mcp_cdp_helper.py screenshot output/test.png
```

---

## Why CDP Attach is the Default

| Mode | Status | Notes |
|------|--------|-------|
| **CDP Attach** | ✅ **Default** | Controls real browser via Chrome DevTools Protocol. Playwright officially supports `connectOverCDP` for attaching to existing Chromium browsers. |
| Extension Mode | ⚙️ Available | Intended for real browser control, but reports indicate `--extension` may launch new Chrome instance instead of attaching to existing one. |
| Bundled Chromium | ⚠️ Fallback | Isolated profile, no session persistence. Not suitable for Teamleader/Exact workflows. |

**Playwright documentation:** [BrowserType.connectOverCDP](https://playwright.dev/docs/api/class-browsertype)

**Key issue with Extension mode:** [GitHub Issue #921](https://github.com/microsoft/playwright-mcp/issues/921) — `--extension` may launch new Chrome instead of attaching to existing session.

---

## CDP Mode: Complete Setup

### 1. Prerequisites

- Microsoft Edge (Flatpak) installed
- `chrome-for-mcp` helper script available
- MCP CDP wrapper configured

### 2. Launch Browser with CDP

```bash
# Using the helper script
chrome-for-mcp

# Or manually
flatpak run com.microsoft.Edge \
  --remote-debugging-port=9223 \
  --user-data-dir="$HOME/.var/app/com.microsoft.Edge/config/edge-mcp-profile" \
  --no-first-run \
  --no-default-browser-check
```

### 3. Verify CDP Endpoint

```bash
curl http://127.0.0.1:9223/json/version
```

Expected output:
```json
{
   "Browser": "Edg/146.0.3856.59",
   "Protocol-Version": "1.3",
   "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/browser/..."
}
```

### 4. MCP Configuration

`~/.kimi/mcp.json`:
```json
{
  "mcpServers": {
    "playwright": {
      "command": "/home/ff/.local/bin/playwright-mcp-cdp",
      "args": []
    }
  }
}
```

Wrapper script `~/.local/bin/playwright-mcp-cdp`:
```bash
#!/bin/bash
export PLAYWRIGHT_BROWSERS_PATH=/home/ff/.cache/ms-playwright
export PATH=/home/linuxbrew/.linuxbrew/bin:/app/bin:/usr/bin

MCP_PATH="/home/ff/.local/share/mcp-playwright/node_modules/@playwright/mcp/cli.js"
CDP_ENDPOINT="http://127.0.0.1:9223"

exec /home/linuxbrew/.linuxbrew/bin/node "$MCP_PATH" \
  --browser chromium \
  --cdp-endpoint "$CDP_ENDPOINT" \
  --allow-unrestricted-file-access "$@"
```

### 5. Test Connection

```bash
kimi mcp test playwright
```

Expected: "✓ Connected to 'playwright'" with 22 tools listed.

---

## Usage Patterns

### Pattern 1: Manual Login + Agent Continuation

**For Teamleader, Exact, or any authenticated platform:**

1. **Launch Edge with CDP:**
   ```bash
   chrome-for-mcp
   ```

2. **Log in manually:**
   - Navigate to Teamleader or Exact in the browser
   - Complete OAuth/2FA login
   - Stay logged in

3. **Hand off to agent:**
   ```bash
   python scripts/mcp_cdp_helper.py navigate "https://focus.teamleader.eu/..."
   python scripts/mcp_cdp_helper.py screenshot output/teamleader_dashboard.png
   ```

### Pattern 2: Full Agent Control (No Auth Required)

```bash
# Start browser
chrome-for-mcp

# Navigate and capture
python scripts/mcp_cdp_helper.py navigate http://localhost:3000
python scripts/mcp_cdp_helper.py snapshot
python scripts/mcp_cdp_helper.py screenshot output/capture.png
```

---

## Python Helper Script

`scripts/mcp_cdp_helper.py` provides simple commands:

```bash
# Test connection
python scripts/mcp_cdp_helper.py test

# Navigate to URL
python scripts/mcp_cdp_helper.py navigate <url>

# Get page title
python scripts/mcp_cdp_helper.py title

# Capture accessibility snapshot
python scripts/mcp_cdp_helper.py snapshot

# Take screenshot
python scripts/mcp_cdp_helper.py screenshot [filename]
```

---

## Kimi CLI Tool Invocation (Current Status)

| Aspect | Status |
|--------|--------|
| `kimi mcp test playwright` | ✅ Works |
| Python subprocess control | ✅ Works |
| Native Kimi tool calling | ❌ Blocked by upstream bug |

**Workaround:** Use `scripts/mcp_cdp_helper.py` for all browser automation until Kimi CLI fixes the session bug.

**Upstream bug symptoms:**
```
Client failed to connect: Server session was closed unexpectedly
```

This occurs when Kimi tries to invoke MCP tools directly. The MCP server itself is healthy (verified by `kimi mcp test`), but the tool invocation path has a bug in Kimi CLI 1.21.0.

---

## Extension Mode (Optional/Future)

Extension mode is available but **not the default** due to Flatpak sandboxing limitations.

### When to Use Extension Mode

- If CDP mode fails or has limitations
- If you need specific extension capabilities
- After Kimi CLI bug is fixed and native tool calling works

### Setup

1. **Build extension** (already done):
   ```bash
   # Extension built at:
   ~/.local/share/playwright-mcp-chrome-extension/
   ```

2. **Manual install** (required due to Flatpak):
   - Open Edge, go to `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked"
   - Select `~/.local/share/playwright-mcp-chrome-extension/`

3. **Switch MCP config**:
   ```json
   {
     "mcpServers": {
       "playwright": {
         "command": "/home/ff/.local/bin/playwright-mcp-extension",
         "args": []
       }
     }
   }
   ```

---

## Verification Checklist

```bash
# 1. CDP endpoint responding
curl -s http://127.0.0.1:9223/json/version | grep "Browser"

# 2. MCP test passes
kimi mcp test playwright

# 3. Python helper works
python scripts/mcp_cdp_helper.py test

# 4. Screenshot captured
ls -la output/mcp_cdp_verification.png
```

---

## Troubleshooting

### CDP Connection Refused
```bash
# Check if Edge is running
flatpak-spawn --host pgrep -a msedge

# Check port
flatpak-spawn --host ss -tlnp | grep 9223
```

### Flatpak Permission Issues
```bash
# Edge may need additional permissions
flatpak override --user com.microsoft.Edge --socket=system-bus
```

### MCP Tools Not Found
Ensure you're using `tools/call` method with correct format:
```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"browser_navigate","arguments":{"url":"..."}}}
```

---

## File Locations

| File | Purpose |
|------|---------|
| `~/.local/bin/chrome-for-mcp` | Launch Edge with CDP |
| `~/.local/bin/playwright-mcp-cdp` | MCP wrapper (CDP mode) |
| `~/.local/bin/playwright-mcp-extension` | MCP wrapper (extension mode) |
| `~/.kimi/mcp.json` | Kimi MCP configuration |
| `scripts/mcp_cdp_helper.py` | Python automation helper |
| `docs/BROWSER_AUTOMATION_GUIDE.md` | This guide |

---

## Summary

- ✅ **CDP attach is the default and working**
- ✅ **Real browser control via Edge on port 9223**
- ✅ **Manual login + agent continuation workflow ready**
- ✅ **Python helper provides automation until Kimi bug fixed**
- ⚠️ **Extension mode available but not default (Flatpak + attach issues)**
- ❌ **Kimi CLI native tool calling still blocked (upstream bug)**
