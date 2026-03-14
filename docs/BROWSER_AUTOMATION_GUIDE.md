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

### Pattern 1: Manual Login + Agent Continuation (Recommended for Authenticated Sites)

**Complete workflow for Teamleader, Exact, or any platform requiring login:**

#### Step 1: Launch Browser with CDP
```bash
chrome-for-mcp
```

#### Step 2: Log in Manually (You Do This)
In the Edge browser window that opened:
1. Navigate to your target site (e.g., `https://focus.teamleader.eu`)
2. Complete the login flow (email/password, OAuth, 2FA)
3. Navigate to the page you want automated
4. **Leave the browser open** — this is now your logged-in session

#### Step 3: Hand Off to Agent (Agent Does This)
Once you're logged in and on the desired page:

```bash
# Verify current state
python scripts/mcp_cdp_helper.py url
python scripts/mcp_cdp_helper.py title

# Capture current page
python scripts/mcp_cdp_helper.py screenshot output/browser_automation/step1_logged_in.png

# Navigate within the same session (cookies/auth preserved)
python scripts/mcp_cdp_helper.py navigate "https://focus.teamleader.eu/your-target-page"

# Capture results
python scripts/mcp_cdp_helper.py snapshot
python scripts/mcp_cdp_helper.py screenshot output/browser_automation/step2_result.png
```

#### Key Point
The agent controls **the same browser window** you logged into. Cookies, session tokens, and authentication state are preserved. This is why CDP attach mode is superior to isolated browser automation for authenticated workflows.

---

### Example: Teamleader Manual-Login Continuation

**Prerequisites:** Edge running with CDP (`chrome-for-mcp`)

```bash
# 1. Agent navigates to login page (prepares for your login)
python scripts/mcp_cdp_helper.py navigate "https://focus.teamleader.eu"

# 2. [YOU] Log in manually in the Edge browser window
#    - Enter email/password or use Google/Apple/Microsoft sign-in
#    - Complete 2FA if required
#    - Navigate to desired section (e.g., Contacts, Companies)
#    - Stay on that page

# 3. [AGENT] Continue from your logged-in session
python scripts/mcp_cdp_helper.py url
# → https://focus.teamleader.eu/your-logged-in-path

python scripts/mcp_cdp_helper.py title
# → Teamleader Focus - Your Section

python scripts/mcp_cdp_helper.py screenshot output/browser_automation/teamleader_dashboard.png

# Navigate within the same authenticated session
python scripts/mcp_cdp_helper.py navigate "https://focus.teamleader.eu/your-target-page"
python scripts/mcp_cdp_helper.py snapshot
```

---

### Example: Exact Online Manual-Login Continuation

**Prerequisites:** Edge running with CDP (`chrome-for-mcp`)

```bash
# 1. Agent navigates to login page (prepares for your login)
python scripts/mcp_cdp_helper.py navigate "https://start.exactonline.be"

# 2. [YOU] Log in manually in the Edge browser window
#    - Enter email address or username
#    - Click Continue
#    - Enter password
#    - Complete 2FA if required
#    - Navigate to desired section (e.g., Financial, CRM)
#    - Stay on that page

# 3. [AGENT] Continue from your logged-in session
python scripts/mcp_cdp_helper.py url
# → https://start.exactonline.be/ui/... (logged-in URL)

python scripts/mcp_cdp_helper.py title
# → Exact Online - Your Section

python scripts/mcp_cdp_helper.py screenshot output/browser_automation/exact_dashboard.png

# List all tabs to see your session state
python scripts/mcp_cdp_helper.py tabs

# Navigate within the same authenticated session
python scripts/mcp_cdp_helper.py navigate "https://start.exactonline.be/ui/your-target"
python scripts/mcp_cdp_helper.py snapshot
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

`scripts/mcp_cdp_helper.py` provides simple CLI commands for controlling the attached browser:

| Command | Usage | Description |
|---------|-------|-------------|
| `test` | `python scripts/mcp_cdp_helper.py test` | Quick connectivity test |
| `navigate` | `python scripts/mcp_cdp_helper.py navigate <url>` | Navigate to URL |
| `title` | `python scripts/mcp_cdp_helper.py title` | Get current page title |
| `url` | `python scripts/mcp_cdp_helper.py url` | Get current page URL |
| `snapshot` | `python scripts/mcp_cdp_helper.py snapshot` | Capture accessibility snapshot |
| `screenshot` | `python scripts/mcp_cdp_helper.py screenshot [filename]` | Take screenshot |
| `tabs` | `python scripts/mcp_cdp_helper.py tabs` | List all browser tabs/pages |

### Examples

```bash
# Quick test
python scripts/mcp_cdp_helper.py test

# Navigate and capture
python scripts/mcp_cdp_helper.py navigate http://localhost:3000
python scripts/mcp_cdp_helper.py title
python scripts/mcp_cdp_helper.py url
python scripts/mcp_cdp_helper.py snapshot
python scripts/mcp_cdp_helper.py screenshot output/browser_automation/my_capture.png
```

### Error Handling

If the CDP browser is not running:
```
ERROR: CDP browser not responding on port 9223

To fix:
  1. Launch browser: chrome-for-mcp
  2. Or manually: flatpak run com.microsoft.Edge --remote-debugging-port=9223
  3. Verify: curl http://127.0.0.1:9223/json/version
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
