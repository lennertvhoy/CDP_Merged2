#!/usr/bin/env python3
"""ATTACHED_EDGE_CDP smoke tests for critical operator paths.

Uses the project's canonical browser automation path:
- Attached Edge via CDP on 127.0.0.1:9223
- Preserves cookies/session/auth
- Reuses existing browser instance

Run with: pytest tests/e2e/test_attached_edge_cdp_smoke.py -v

Architecture: ATTACHED_EDGE_CDP (canonical)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import the canonical CDP helper
sys.path.insert(0, str(project_root / "scripts"))
from mcp_cdp_helper import MCPBrowserController, check_cdp_endpoint

# Test configuration
BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:3000")
API_URL = os.environ.get("TEST_API_URL", "http://localhost:8170")
CDP_ENDPOINT = os.environ.get("TEST_CDP_ENDPOINT", "http://127.0.0.1:9223")
TEST_USER = os.environ.get("TEST_USER", "eval-test@cdp.local")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "EvalTest123!")


@pytest.fixture(scope="session")
def cdp_available():
    """Verify CDP endpoint is available before running tests."""
    if not check_cdp_endpoint(CDP_ENDPOINT):
        pytest.skip(f"CDP endpoint not available at {CDP_ENDPOINT}")
    return True


@pytest.fixture
def browser_controller(cdp_available):
    """Create CDP-attached browser controller for each test."""
    controller = MCPBrowserController(CDP_ENDPOINT)
    if not controller.start():
        pytest.fail("Failed to start MCP CDP controller")
    
    yield controller
    
    controller.close()


class TestCDPConnection:
    """Verify CDP infrastructure."""
    
    def test_cdp_endpoint_responsive(self, cdp_available):
        """CDP endpoint returns version info."""
        import urllib.request
        with urllib.request.urlopen(f"{CDP_ENDPOINT}/json/version", timeout=5) as response:
            data = json.loads(response.read().decode())
            assert "Browser" in data
            assert "Edg" in data["Browser"] or "Chrome" in data["Browser"]
    
    def test_cdp_lists_targets(self, cdp_available):
        """CDP endpoint lists browser targets/pages."""
        import urllib.request
        with urllib.request.urlopen(f"{CDP_ENDPOINT}/json/list", timeout=5) as response:
            tabs = json.loads(response.read().decode())
            assert isinstance(tabs, list)
            # Should have at least one tab
            assert len(tabs) >= 1


class TestLoginFlowAttached:
    """Critical path: User authentication via attached Edge."""
    
    def test_login_page_loads(self, browser_controller):
        """Verify login page is accessible."""
        browser_controller.navigate(f"{BASE_URL}/login")
        time.sleep(2)  # Wait for page load
        
        snapshot = browser_controller.snapshot()
        assert "Private Access" in snapshot or "login" in snapshot.lower() or "email" in snapshot.lower()
    
    def test_login_form_elements_present(self, browser_controller):
        """Verify login form elements exist."""
        browser_controller.navigate(f"{BASE_URL}/login")
        time.sleep(2)
        
        snapshot = browser_controller.snapshot()
        # Check for email and password fields
        assert "email" in snapshot.lower() or "@" in snapshot
        assert "password" in snapshot.lower() or any(indicator in snapshot.lower() for indicator in ["password", "continue", "sign in"])


class TestChatFlowAttached:
    """Critical path: Chat interaction via attached Edge."""
    
    def test_chat_page_navigable(self, browser_controller):
        """Verify chat page loads after auth."""
        # Navigate to main page
        browser_controller.navigate(BASE_URL)
        time.sleep(2)
        
        title = browser_controller.get_title()
        assert "CDP" in title or "Merged" in title or "Private Preview" in title
    
    def test_chat_interface_elements(self, browser_controller):
        """Verify chat input is present."""
        browser_controller.navigate(BASE_URL)
        time.sleep(2)
        
        snapshot = browser_controller.snapshot()
        # Look for chat-related elements
        chat_indicators = ["ask", "message", "chat", "send", "input"]
        assert any(indicator in snapshot.lower() for indicator in chat_indicators), \
            f"No chat indicators found in: {snapshot[:500]}"


class TestNavigationAttached:
    """Critical path: UI navigation via attached Edge."""
    
    def test_segment_manager_accessible(self, browser_controller):
        """Verify segment manager page loads."""
        browser_controller.navigate(f"{BASE_URL}/segments")
        time.sleep(2)
        
        snapshot = browser_controller.snapshot()
        assert "segment" in snapshot.lower() or "audience" in snapshot.lower()
    
    def test_company_browser_accessible(self, browser_controller):
        """Verify company browser page loads."""
        browser_controller.navigate(f"{BASE_URL}/companies")
        time.sleep(2)
        
        snapshot = browser_controller.snapshot()
        assert "company" in snapshot.lower() or "business" in snapshot.lower()
    
    def test_screenshot_capture(self, browser_controller, tmp_path):
        """Verify screenshot capture works via CDP."""
        browser_controller.navigate(BASE_URL)
        time.sleep(2)
        
        screenshot_path = tmp_path / "test_screenshot.png"
        result = browser_controller.screenshot(str(screenshot_path))
        
        assert result is not None, "Screenshot should return data"
        assert screenshot_path.exists(), "Screenshot file should be created"
        assert screenshot_path.stat().st_size > 1000, "Screenshot should have content"


class TestAPIHealth:
    """API health checks (HTTP, not browser)."""
    
    def test_api_health_endpoint(self):
        """Verify API health endpoint returns OK."""
        import urllib.request
        
        with urllib.request.urlopen(f"{API_URL}/healthz", timeout=10) as response:
            assert response.status == 200
            data = json.loads(response.read().decode())
            assert data.get("status") == "ok"
    
    def test_bootstrap_endpoint(self):
        """Verify bootstrap endpoint returns config."""
        import urllib.request
        
        with urllib.request.urlopen(f"{API_URL}/api/operator/bootstrap", timeout=10) as response:
            assert response.status == 200
            data = json.loads(response.read().decode())
            assert "session" in data or "status" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
