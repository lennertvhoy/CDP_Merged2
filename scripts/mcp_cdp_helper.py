#!/usr/bin/env python3
"""
MCP CDP Helper for CDP_Merged
Real browser control via Chrome DevTools Protocol (CDP)

CANONICAL BROWSER PATH: Attached Edge/CDP
This is the project's preferred browser automation architecture.
Reuses existing Edge instance on 127.0.0.1:9223, preserving session/auth.

Usage:
    # Ensure Edge is running with CDP first:
    chrome-for-mcp
    
    # Then use this helper:
    python scripts/mcp_cdp_helper.py navigate http://localhost:3000
    python scripts/mcp_cdp_helper.py snapshot
    python scripts/mcp_cdp_helper.py screenshot output/test.png
    python scripts/mcp_cdp_helper.py title
    python scripts/mcp_cdp_helper.py url
    python scripts/mcp_cdp_helper.py tabs

Architecture: ATTACHED_EDGE_CDP (canonical)
"""

import subprocess
import json
import sys
import select
import time
from pathlib import Path

# Configuration
MCP_CDP_BINARY = "/home/ff/.local/bin/playwright-mcp-cdp"
DEFAULT_CDP_ENDPOINT = "http://127.0.0.1:9223"


class MCPBrowserController:
    """Simple controller for MCP CDP browser automation."""
    
    def __init__(self, cdp_endpoint: str = DEFAULT_CDP_ENDPOINT):
        self.cdp_endpoint = cdp_endpoint
        self.proc = None
        self.message_id = 0
        
    def start(self):
        """Start the MCP CDP subprocess."""
        env = {
            **dict(subprocess.os.environ),
            "PLAYWRIGHT_CDP_ENDPOINT": self.cdp_endpoint,
        }
        self.proc = subprocess.Popen(
            [MCP_CDP_BINARY],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            text=True,
            env=env,
        )
        # Give it a moment to initialize
        time.sleep(0.5)
        return self.proc.poll() is None
        
    def send(self, method: str, params: dict = None) -> dict:
        """Send a JSON-RPC request to MCP."""
        self.message_id += 1
        message = {
            "jsonrpc": "2.0",
            "id": self.message_id,
            "method": "tools/call",
            "params": {
                "name": method,
                "arguments": params or {}
            }
        }
        
        msg_str = json.dumps(message) + "\n"
        self.proc.stdin.write(msg_str)
        self.proc.stdin.flush()
        
        # Read response with timeout
        response = self._read_response(timeout=10.0)
        return response
        
    def _read_response(self, timeout: float = 10.0) -> dict:
        """Read a JSON-RPC response from stdout."""
        start_time = time.time()
        buffer = ""
        
        while time.time() - start_time < timeout:
            # Check if data is available
            if select.select([self.proc.stdout], [], [], 0.1)[0]:
                line = self.proc.stdout.readline()
                if line:
                    try:
                        return json.loads(line.strip())
                    except json.JSONDecodeError:
                        buffer += line
                        # Try to extract JSON from buffer
                        try:
                            # Look for complete JSON objects
                            start = buffer.find('{')
                            end = buffer.rfind('}')
                            if start >= 0 and end > start:
                                return json.loads(buffer[start:end+1])
                        except:
                            pass
                        continue
            time.sleep(0.05)
            
        return {"error": "Timeout waiting for response", "raw": buffer}
        
    def navigate(self, url: str) -> dict:
        """Navigate to a URL."""
        return self.send("browser_navigate", {"url": url})
        
    def get_title(self) -> str:
        """Get the current page title from snapshot response."""
        result = self.send("browser_snapshot", {})
        if "result" in result:
            content = result["result"].get("content", [])
            for item in content:
                if item.get("type") == "text":
                    text = item.get("text", "")
                    # Extract title from snapshot text
                    for line in text.split("\n"):
                        if "Page Title:" in line:
                            return line.split("Page Title:")[1].strip()
        return "N/A"
        
    def get_url(self) -> str:
        """Get the current page URL from snapshot response."""
        result = self.send("browser_snapshot", {})
        if "result" in result:
            content = result["result"].get("content", [])
            for item in content:
                if item.get("type") == "text":
                    text = item.get("text", "")
                    # Extract URL from snapshot text
                    for line in text.split("\n"):
                        if "Page URL:" in line:
                            return line.split("Page URL:")[1].strip()
        return "N/A"
        
    def snapshot(self) -> str:
        """Get accessibility snapshot of the page."""
        result = self.send("browser_snapshot", {})
        if "result" in result:
            content = result["result"].get("content", [])
            for item in content:
                if item.get("type") == "text":
                    return item.get("text", "N/A")
        return json.dumps(result, indent=2)
        
    def screenshot(self, filename: str = None) -> bytes:
        """Take a screenshot. Returns base64 data."""
        result = self.send("browser_take_screenshot", {})
        if "result" in result:
            content = result["result"].get("content", [])
            for item in content:
                if item.get("type") == "image":
                    data = item.get("data", "")
                    if filename and data:
                        import base64
                        img_data = base64.b64decode(data)
                        Path(filename).parent.mkdir(parents=True, exist_ok=True)
                        with open(filename, "wb") as f:
                            f.write(img_data)
                        print(f"Screenshot saved to: {filename}")
                    return data
        return None
        
    def click(self, element_description: str, ref: str = None) -> dict:
        """Click an element by description or ref."""
        params = {"element": element_description}
        if ref:
            params["ref"] = ref
        return self.send("browser_click", params)
        
    def fill(self, element_description: str, text: str, ref: str = None) -> dict:
        """Fill an input field with text."""
        params = {
            "element": element_description,
            "text": text
        }
        if ref:
            params["ref"] = ref
        return self.send("browser_type", params)
        
    def wait_for_text(self, text: str, timeout_sec: int = 10) -> bool:
        """Wait for specific text to appear on page."""
        start = time.time()
        while time.time() - start < timeout_sec:
            snapshot = self.snapshot()
            if text in snapshot:
                return True
            time.sleep(0.5)
        return False
        
    def get_element_ref(self, element_description: str) -> str:
        """Get ref for an element from snapshot by description."""
        result = self.send("browser_snapshot", {})
        if "result" in result:
            content = result["result"].get("content", [])
            for item in content:
                if item.get("type") == "text":
                    text = item.get("text", "")
                    # Look for element with matching description
                    lines = text.split("\n")
                    for line in lines:
                        if element_description.lower() in line.lower() and "[" in line:
                            # Extract ref from line like "- button 'Search' [ref=s23e45]"
                            import re
                            match = re.search(r'\[ref=([^\]]+)\]', line)
                            if match:
                                return match.group(1)
        return None
        
    def close(self):
        """Close the MCP subprocess."""
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except:
                self.proc.kill()


def check_cdp_endpoint(endpoint: str = DEFAULT_CDP_ENDPOINT) -> bool:
    """Check if CDP endpoint is responding."""
    import urllib.request
    try:
        urllib.request.urlopen(endpoint, timeout=2)
        return True
    except:
        return False


def list_tabs(endpoint: str = DEFAULT_CDP_ENDPOINT) -> list:
    """List all browser tabs via CDP HTTP endpoint."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{endpoint}/json/list", timeout=5) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return [{"error": str(e)}]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
        
    command = sys.argv[1]
    
    # Pre-flight check: is CDP browser running?
    if not check_cdp_endpoint():
        print("ERROR: CDP browser not responding on port 9223", file=sys.stderr)
        print("", file=sys.stderr)
        print("To fix:", file=sys.stderr)
        print("  1. Launch browser: chrome-for-mcp", file=sys.stderr)
        print("  2. Or manually: flatpak run com.microsoft.Edge --remote-debugging-port=9223", file=sys.stderr)
        print("  3. Verify: curl http://127.0.0.1:9223/json/version", file=sys.stderr)
        sys.exit(1)
    
    controller = MCPBrowserController()
    
    try:
        print(f"Starting MCP CDP controller...")
        if not controller.start():
            print("ERROR: Failed to start MCP process", file=sys.stderr)
            sys.exit(1)
        print(f"Connected to CDP endpoint: {DEFAULT_CDP_ENDPOINT}")
        
        if command == "navigate":
            if len(sys.argv) < 3:
                print("Usage: python mcp_cdp_helper.py navigate <url>")
                sys.exit(1)
            url = sys.argv[2]
            print(f"Navigating to: {url}")
            result = controller.navigate(url)
            print(f"Result: {json.dumps(result, indent=2)}")
            # Wait a moment for page load
            time.sleep(2)
            title = controller.get_title()
            print(f"Page title: {title}")
            
        elif command == "snapshot":
            print("Capturing page snapshot...")
            snapshot = controller.snapshot()
            print(snapshot[:2000] if len(snapshot) > 2000 else snapshot)
            if len(snapshot) > 2000:
                print(f"\n... (truncated, total length: {len(snapshot)} chars)")
                
        elif command == "title":
            title = controller.get_title()
            print(f"Page title: {title}")
            
        elif command == "url":
            url = controller.get_url()
            print(f"Page URL: {url}")
            
        elif command == "screenshot":
            filename = sys.argv[2] if len(sys.argv) > 2 else "output/mcp_screenshot.png"
            print(f"Taking screenshot...")
            controller.screenshot(filename)
            
        elif command == "test":
            print("Testing MCP CDP connection...")
            # Navigate to operator shell
            controller.navigate("http://localhost:3000")
            time.sleep(2)
            title = controller.get_title()
            print(f"✓ Navigation successful")
            print(f"✓ Page title: {title}")
            snapshot = controller.snapshot()
            print(f"✓ Snapshot captured ({len(snapshot)} chars)")
            if "CDP_Merged" in snapshot or "Private Preview" in snapshot:
                print("✓ Verified: CDP_Merged operator shell is accessible")
                
        elif command == "tabs":
            print("Listing browser tabs...")
            tabs = list_tabs()
            print(f"\nTotal tabs: {len(tabs)}\n")
            for i, tab in enumerate(tabs[:10], 1):  # Limit to first 10
                if "error" in tab:
                    print(f"{i}. Error: {tab['error']}")
                else:
                    title = tab.get('title', 'N/A')[:50]
                    url = tab.get('url', 'N/A')[:60]
                    print(f"{i}. {title}... ({url})")
                    
        elif command == "click":
            if len(sys.argv) < 3:
                print("Usage: python mcp_cdp_helper.py click '<element description>'")
                sys.exit(1)
            element = sys.argv[2]
            print(f"Clicking: {element}")
            result = controller.click(element)
            print(f"Result: {json.dumps(result, indent=2)}")
            
        elif command == "fill":
            if len(sys.argv) < 4:
                print("Usage: python mcp_cdp_helper.py fill '<element description>' '<text>'")
                sys.exit(1)
            element = sys.argv[2]
            text = sys.argv[3]
            print(f"Filling '{element}' with: {text}")
            result = controller.fill(element, text)
            print(f"Result: {json.dumps(result, indent=2)}")
            
        elif command == "wait-for":
            if len(sys.argv) < 3:
                print("Usage: python mcp_cdp_helper.py wait-for '<text>' [timeout_seconds]")
                sys.exit(1)
            text = sys.argv[2]
            timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 10
            print(f"Waiting for text: '{text}' (timeout: {timeout}s)")
            found = controller.wait_for_text(text, timeout)
            print(f"Result: {'Found' if found else 'Not found'}")
            
        else:
            print(f"Unknown command: {command}")
            print(__doc__)
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        controller.close()
        print("Controller closed")


if __name__ == "__main__":
    main()
