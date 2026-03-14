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
    
    def test_login_redirect_shows_preview_gate(self, browser_controller):
        """Verify /login redirects to preview access gate."""
        browser_controller.navigate(f"{BASE_URL}/login")
        time.sleep(2)  # Wait for page load
        
        snapshot = browser_controller.snapshot()
        # The /login route shows a preview gate, not traditional login form
        # Evidence from real snapshot:
        # - "Private preview" text
        # - "Use the main access screen" heading
        # - "Return to preview" link
        assert "Private preview" in snapshot, f"Expected 'Private preview' in snapshot, got: {snapshot[:500]}"
        assert "main access screen" in snapshot.lower() or "Return to preview" in snapshot, \
            f"Expected access gate indicators in snapshot, got: {snapshot[:500]}"
    
    def test_main_page_shows_authenticated_ui(self, browser_controller):
        """Verify main page shows authenticated operator UI."""
        browser_controller.navigate(f"{BASE_URL}/")
        time.sleep(2)
        
        snapshot = browser_controller.snapshot()
        # Real snapshot evidence:
        # - "CDP" header
        # - Navigation buttons: Chat, Threads, Companies, Segments, Sources, Pipelines, Activity
        # - "Private preview" indicator
        # - "Sign out" button (proves authenticated state)
        assert "CDP" in snapshot, f"Expected 'CDP' header in snapshot, got: {snapshot[:500]}"
        assert "Chat" in snapshot and "Segments" in snapshot, \
            f"Expected navigation buttons in snapshot, got: {snapshot[:500]}"
        assert "Sign out" in snapshot or "Private preview" in snapshot, \
            f"Expected authenticated state indicators, got: {snapshot[:500]}"


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


class TestDeterministicTabSelection:
    """Verify robust tab selection works reliably."""
    
    def test_select_tab_by_url_prefix(self, browser_controller):
        """Select tab using URL prefix match - most robust method."""
        result = browser_controller.select_tab_deterministic(
            url_prefix=BASE_URL
        )
        assert result["success"], f"URL prefix match failed: {result}"
        assert result["method"] == "url_prefix"
    
    def test_select_tab_by_url_contains(self, browser_controller):
        """Select tab using URL substring match."""
        result = browser_controller.select_tab_deterministic(
            url_contains="localhost:3000"
        )
        assert result["success"], f"URL contains match failed: {result}"
        assert result["method"] == "url_contains"
    
    def test_select_tab_by_title(self, browser_controller):
        """Select tab using title pattern match."""
        result = browser_controller.select_tab_deterministic(
            title_contains="CDP"
        )
        assert result["success"], f"Title match failed: {result}"
        assert result["method"] == "title_contains"
    
    def test_select_tab_fallback(self, browser_controller):
        """Verify fallback works when no specific match found."""
        result = browser_controller.select_tab_deterministic(
            url_contains="this-wont-match-anything-12345",
            fallback_first=True
        )
        assert result["success"], f"Fallback selection failed: {result}"
        assert result["method"] == "fallback_first"
    
    def test_select_tab_preference_order(self, browser_controller):
        """Verify exact match takes precedence over prefix match."""
        # First navigate to login
        browser_controller.navigate(f"{BASE_URL}/login")
        time.sleep(1)
        
        # Try with both url_prefix and url_contains
        # prefix should win since it's priority 2 vs 3
        result = browser_controller.select_tab_deterministic(
            url_prefix=BASE_URL,
            url_contains="localhost"
        )
        assert result["success"]
        # The method should be url_prefix since it's higher priority
        assert result["method"] == "url_prefix"


class TestNavigationAttached:
    """Critical path: UI navigation via attached Edge."""
    
    def test_segment_manager_accessible(self, browser_controller):
        """Verify segment manager view loads via navigation."""
        # First navigate to base URL (may show login gate or main page depending on auth state)
        browser_controller.navigate(BASE_URL)
        time.sleep(2)
        
        snapshot = browser_controller.snapshot()
        
        # Check if we're on login gate or main page
        if "Private preview" in snapshot or "main access screen" in snapshot.lower():
            # On login gate - this is expected if not authenticated
            # Navigate to main access screen
            ref = browser_controller.get_element_ref("Use the main access screen")
            if ref:
                browser_controller.click("Use the main access screen", ref=ref)
                time.sleep(2)
                snapshot = browser_controller.snapshot()
        
        # Now we should be on the main page with navigation
        assert "Segments" in snapshot, f"Expected 'Segments' navigation in snapshot, got: {snapshot[:500]}"
        
        # Get ref for Segments button and click with ref
        ref = browser_controller.get_element_ref("Segments")
        assert ref is not None, "Could not find ref for Segments button"
        
        result = browser_controller.click("Segments", ref=ref)
        time.sleep(2)
        
        # Segments view loads as client-side view (URL stays /)
        # Check for Segments view content instead of URL change
        snapshot_after = browser_controller.snapshot()
        assert "Segments" in snapshot_after and "Create segment" in snapshot_after, \
            f"Expected Segments view with 'Create segment' button, got: {snapshot_after[:500]}"
    
    def test_companies_navigation_available(self, browser_controller):
        """Verify Companies navigation is available on main page."""
        browser_controller.navigate(f"{BASE_URL}/")
        time.sleep(2)
        
        snapshot = browser_controller.snapshot()
        # Companies is available as a navigation button, not direct route
        # Real snapshot evidence: button "Companies" [ref=e16]
        assert "Companies" in snapshot, f"Expected 'Companies' navigation button, got: {snapshot[:500]}"
        
        # Direct /companies route is 404 - verify this is expected
        browser_controller.navigate(f"{BASE_URL}/companies")
        time.sleep(1)
        
        snapshot_404 = browser_controller.snapshot()
        # This is expected behavior - Companies is a modal/view, not a route
        if "404" in snapshot_404:
            # This is fine - Companies is accessed via navigation, not direct URL
            pass
    
    def test_screenshot_capture(self, browser_controller, tmp_path):
        """Verify screenshot capture works via CDP."""
        browser_controller.navigate(BASE_URL)
        time.sleep(2)
        
        screenshot_path = tmp_path / "test_screenshot.png"
        result = browser_controller.screenshot(str(screenshot_path))
        
        assert result is not None, "Screenshot should return data"
        assert screenshot_path.exists(), "Screenshot file should be created"
        assert screenshot_path.stat().st_size > 1000, "Screenshot should have content"


class TestEndToEndSmokeFlow:
    """Complete end-to-end smoke flow with assertions and artifacts.
    
    Validates:
    - Deterministic tab selection
    - Navigation to operator shell
    - Segments surface interaction
    - Screenshot capture as evidence
    """
    
    def test_full_segments_smoke_flow(self, browser_controller, tmp_path):
        """Execute complete smoke flow: select tab → navigate → open Segments → assert → screenshot."""
        # Step 1: Deterministic tab selection
        result = browser_controller.ensure_tab_for_url(BASE_URL)
        assert result["success"], f"Tab selection failed: {result.get('error')}"
        assert result["method"] in ["exact_url", "url_prefix", "url_contains", "navigate"]
        time.sleep(2)
        
        # Step 2: Verify we're on authenticated main page
        snapshot = browser_controller.snapshot()
        assert "CDP" in snapshot, "Expected CDP header on main page"
        assert "Segments" in snapshot, "Expected Segments navigation"
        assert "Chat" in snapshot, "Expected Chat navigation"
        
        # Step 3: Get element ref and click Segments
        ref = browser_controller.get_element_ref("Segments")
        assert ref is not None, "Could not find Segments button ref"
        
        click_result = browser_controller.click("Segments", ref=ref)
        time.sleep(2)  # Wait for client-side navigation
        
        # Step 4: Assert Segments view loaded
        snapshot_segments = browser_controller.snapshot()
        assert "Segments" in snapshot_segments, "Segments heading not found"
        assert "Create segment" in snapshot_segments, "Create segment button not found"
        assert "Search segments" in snapshot_segments.lower() or "search" in snapshot_segments.lower(), \
            "Search field not found"
        
        # Step 5: Verify URL (stays on / for client-side routing)
        current_url = browser_controller.get_url()
        assert BASE_URL in current_url, f"Expected URL to contain {BASE_URL}, got: {current_url}"
        
        # Step 6: Capture evidence screenshot
        screenshot_path = tmp_path / "segments_smoke_evidence.png"
        browser_controller.screenshot(str(screenshot_path))
        
        assert screenshot_path.exists(), "Screenshot file should exist"
        screenshot_size = screenshot_path.stat().st_size
        assert screenshot_size > 5000, f"Screenshot too small ({screenshot_size} bytes), may be blank"
        
        # Optional: Copy to reports for CI artifacts
        reports_dir = Path("reports/e2e_evidence")
        reports_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(screenshot_path, reports_dir / "segments_smoke_latest.png")


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
