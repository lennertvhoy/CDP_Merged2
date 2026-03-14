# Real Browser MCP Setup for CDP_Merged

**Date:** 2026-03-14  
**Status:** ✅ CDP Mode Working (Extension Mode Available)  
**Target:** Control actual browser (Edge/Chrome) with logged-in sessions

---

## Quick Start

```bash
# 1. Launch browser with CDP control
chrome-for-mcp cdp

# 2. Log into Teamleader, Exact, etc. in the browser window

# 3. MCP now controls THIS browser with your logged-in sessions
# Test via Python wrapper (Kimi CLI tool invocation has upstream bug):
python3 /home/ff/.local/bin/mcp-browser-navigate.py http://127.0.0.1:3000
```

---

## What Was Configured

### Browser Control Modes

| Mode | Status | Use Case |
|------|--------|----------|
| **CDP Attach** | ✅ **WORKING** | Connect to existing browser via DevTools Protocol (RECOMMENDED) |
| **Extension** | ⚙️ Available | Playwright MCP Bridge extension (requires manual install) |
| **Persistent Profile** | ⚙️ Available | Bundled Chromium with persistent state (fallback) |

### Files Created/Modified

| File | Purpose |
|------|---------|
| `~/.kimi/mcp.json` | MCP configuration (currently: CDP mode) |
| `~/.local/bin/playwright-mcp-cdp` | Wrapper for CDP attach mode |
| `~/.local/bin/playwright-mcp-extension` | Wrapper for extension mode |
| `~/.local/bin/playwright-mcp-persistent` | Wrapper for persistent profile mode |
| `~/.local/bin/chrome-for-mcp` | Helper to launch browser with MCP control |
| `~/.local/share/playwright-mcp-chrome-extension/` | Built Playwright MCP Bridge extension |
| `~/.local/share/mcp-playwright/` | Stable MCP package installation |

---

## CDP Mode (Recommended)

### How It Works

1. Launch Edge/Chrome with `--remote-debugging-port=9223`
2. MCP connects via Chrome DevTools Protocol
3. MCP controls the actual browser instance
4. You manually log in to sites
5. Agent continues in your logged-in session

### Usage

```bash
# Launch browser with CDP
chrome-for-mcp cdp

# Or manually:
flatpak run com.microsoft.Edge --remote-debugging-port=9223
# OR
flatpak run com.google.Chrome --remote-debugging-port=9223

# Verify CDP is ready
curl http://127.0.0.1:9223/json/version

# Test MCP connection
kimi mcp test playwright

# Use via Python wrapper (due to Kimi CLI bug)
python3 << 'EOF'
import subprocess, json, select

proc = subprocess.Popen(
    ['/home/ff/.local/bin/playwright-mcp-cdp'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    bufsize=0, text=True,
    env={'PLAYWRIGHT_CDP_ENDPOINT': 'http://127.0.0.1:9223'}
)

def send(msg):
    proc.stdin.write(json.dumps(msg) + '\n')
    proc.stdin.flush()

def recv():
    ready, _, _ = select.select([proc.stdout], [], [], 30)
    return json.loads(proc.stdout.readline()) if ready else None

# Initialize
send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                 "clientInfo": {"name": "test", "version": "1.0"}}})
print(recv())

# Navigate
send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
      "params": {"name": "browser_navigate",
                 "arguments": {"url": "http://127.0.0.1:3000"}}})
print(recv())

# Snapshot
send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
      "params": {"name": "browser_snapshot", "arguments": {}}})
print(recv())

proc.terminate()
EOF
```

---

## Extension Mode (Alternative)

### How It Works

1. Install Playwright MCP Bridge extension in Chrome/Edge
2. Extension generates authentication token
3. MCP connects via extension protocol
4. MCP controls the browser through the extension

### Setup

```bash
# 1. Open Chrome/Edge
flatpak run com.google.Chrome  # or com.microsoft.Edge

# 2. Go to chrome://extensions/
# 3. Enable "Developer mode"
# 4. Click "Load unpacked"
# 5. Select: /home/ff/.local/share/playwright-mcp-chrome-extension
# 6. Click the extension icon in toolbar
# 7. Copy the token shown

# 8. Export token and switch MCP config
export PLAYWRIGHT_MCP_EXTENSION_TOKEN='your-token-here'

# Edit ~/.kimi/mcp.json to use playwright-mcp-extension wrapper
```

### MCP Config for Extension Mode

```json
{
  "mcpServers": {
    "playwright": {
      "command": "/home/ff/.local/bin/playwright-mcp-extension",
      "args": [],
      "env": {
        "PLAYWRIGHT_MCP_EXTENSION_TOKEN": "your-token-here"
      }
    }
  }
}
```

---

## Known Issues

### Kimi CLI Tool Invocation Bug

**Status:** Confirmed upstream bug in Kimi CLI 1.21.0

**Symptom:**
- `kimi mcp test playwright` ✅ Works (22 tools available)
- Python subprocess test ✅ Works (full navigation/snapshot)
- Kimi native tool calls ❌ Fails with `Client failed to connect: Server session was closed unexpectedly`

**Workaround:** Use Python subprocess wrapper (see examples above)

**Tracking:** Homebrew shows 1.21.0 as latest. Check for updates:
```bash
brew update && brew info kimi-cli
```

---

## Workflow for Manual Login + Agent Control

### Step-by-Step

1. **Launch browser with CDP:**
   ```bash
   chrome-for-mcp cdp
   ```

2. **Log into sites manually:**
   - Teamleader
   - Exact Online
   - Any other required platforms

3. **Agent takes control:**
   ```bash
   # Via Python wrapper
   python3 mcp-browser-control.py
   ```

4. **Agent actions:**
   - Navigate to specific pages
   - Take screenshots
   - Extract data
   - Fill forms
   - Continue in your logged-in session

### Security Notes

- No credentials stored in code or scripts
- Login happens in your actual browser
- MCP only controls what you can see
- Session persists while browser is open
- Close browser to end MCP control

---

## Verification Commands

```bash
# Check browser CDP endpoint
curl http://127.0.0.1:9223/json/version

# Check MCP connection
PLAYWRIGHT_CDP_ENDPOINT=http://127.0.0.1:9223 kimi mcp test playwright

# Check running processes
ps aux | grep -E "msedge|chrome"

# Check listening ports
ss -tlnp | grep -E "3000|8170|9223"
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Bazzite Host                             │
│  ┌─────────────────┐    ┌──────────────────────────────┐   │
│  │  Edge/Chrome    │◄───┤  Playwright MCP Server       │   │
│  │  (Flatpak)      │CDP │  (--cdp-endpoint)            │   │
│  │                 │    │                              │   │
│  │  • Your login   │    │  • Controls real browser     │   │
│  │    sessions     │    │  • 22 tools available        │   │
│  │  • Live tabs    │    │                              │   │
│  │  • Real state   │    └──────────────┬───────────────┘   │
│  └─────────────────┘                   │                   │
│         ▲                              │                   │
│         │                              │                   │
│    You manually                        │                   │
│    log in here                         │ JSON-RPC          │
│                                        ▼                   │
│                              ┌──────────────────┐         │
│                              │   Python/App     │         │
│                              │   (workaround    │         │
│                              │    for Kimi bug) │         │
│                              └──────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### CDP Connection Refused

```bash
# Check if browser is listening
ss -tlnp | grep 9223

# If not, relaunch:
pkill -f "flatpak.*Edge"
chrome-for-mcp cdp
```

### IPv6/IPv4 Mismatch

Use explicit `127.0.0.1` instead of `localhost`:
```bash
PLAYWRIGHT_CDP_ENDPOINT=http://127.0.0.1:9223
```

### Extension Not Loading (Flatpak)

Flatpak sandboxing may prevent `--load-extension`. Use CDP mode instead.

---

## References

- Playwright MCP: https://github.com/microsoft/playwright-mcp
- CDP Documentation: https://chromedevtools.github.io/devtools-protocol/
- Extension README: `~/.local/share/playwright-mcp-extension/playwright-mcp-0.0.68/packages/extension/README.md`
