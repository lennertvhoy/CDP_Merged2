#!/usr/bin/env python3
"""ISOLATED_CHROMIUM smoke tests for critical operator paths.

WARNING: This uses generic Playwright with spawned Chromium, NOT the project's
canonical attached-Edge/CDP path. Use test_attached_edge_cdp_smoke.py for
the preferred architecture.

Uses Playwright to verify end-to-end flows:
1. Login → Chat → Response
2. Segment creation flow
3. Export functionality

Run with: pytest tests/e2e/test_isolated_chromium_smoke.py -v

Architecture: ISOLATED_PLAYWRIGHT (non-canonical)
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

# playwright import with skip if not available
try:
    from playwright.sync_api import Page, expect, sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    pytest.skip("playwright not installed", allow_module_level=True)


# Test configuration
BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:3000")
API_URL = os.environ.get("TEST_API_URL", "http://localhost:8170")
TEST_USER = os.environ.get("TEST_USER", "eval-test@cdp.local")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "EvalTest123!")


@pytest.fixture(scope="session")
def browser_context():
    """Create browser context for tests."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(browser_context):
    """Create fresh page for each test."""
    page = browser_context.new_page()
    yield page
    page.close()


class TestLoginFlow:
    """Critical path: User authentication."""
    
    def test_login_page_loads(self, page: Page):
        """Verify login page is accessible."""
        page.goto(f"{BASE_URL}/login")
        
        # Check for login form elements
        expect(page.locator("input[type='email']")).to_be_visible()
        expect(page.locator("input[type='password']")).to_be_visible()
        expect(page.locator("button[type='submit']")).to_be_visible()
    
    def test_login_with_valid_credentials(self, page: Page):
        """Verify user can log in."""
        page.goto(f"{BASE_URL}/login")
        
        # Fill credentials
        page.locator("input[type='email']").fill(TEST_USER)
        page.locator("input[type='password']").fill(TEST_PASSWORD)
        page.locator("button[type='submit']").click()
        
        # Should redirect to main app
        page.wait_for_url(f"{BASE_URL}/", timeout=10000)
        
        # Verify chat interface loads
        expect(page.locator("[data-testid='chat-input']")).to_be_visible(timeout=5000)


class TestChatFlow:
    """Critical path: Chat interaction."""
    
    @pytest.fixture
    def logged_in_page(self, page: Page):
        """Login and return authenticated page."""
        page.goto(f"{BASE_URL}/login")
        page.locator("input[type='email']").fill(TEST_USER)
        page.locator("input[type='password']").fill(TEST_PASSWORD)
        page.locator("button[type='submit']").click()
        page.wait_for_url(f"{BASE_URL}/", timeout=10000)
        yield page
    
    def test_chat_input_accepts_text(self, logged_in_page: Page):
        """Verify chat input accepts user messages."""
        chat_input = logged_in_page.locator("[data-testid='chat-input']")
        chat_input.fill("How many companies are in the database?")
        expect(chat_input).to_have_value("How many companies are in the database?")
    
    def test_chat_sends_message(self, logged_in_page: Page):
        """Verify message can be sent and appears in chat."""
        message = "How many companies in Brussels?"
        
        # Type and send
        chat_input = logged_in_page.locator("[data-testid='chat-input']")
        chat_input.fill(message)
        chat_input.press("Enter")
        
        # Verify message appears in chat history
        expect(logged_in_page.locator(".chat-message").filter(has_text=message)).to_be_visible(timeout=5000)
    
    def test_chat_receives_response(self, logged_in_page: Page):
        """Verify chat receives assistant response."""
        message = "Hello"
        
        # Send message
        chat_input = logged_in_page.locator("[data-testid='chat-input']")
        chat_input.fill(message)
        chat_input.press("Enter")
        
        # Wait for assistant response (look for assistant message)
        logged_in_page.wait_for_selector(".chat-message.assistant", timeout=30000)
        
        # Verify response is not empty
        response_text = logged_in_page.locator(".chat-message.assistant").first.inner_text()
        assert len(response_text) > 0, "Response should not be empty"


class TestResponseQuality:
    """Verify response quality characteristics."""
    
    @pytest.fixture
    def logged_in_page(self, page: Page):
        """Login and return authenticated page."""
        page.goto(f"{BASE_URL}/login")
        page.locator("input[type='email']").fill(TEST_USER)
        page.locator("input[type='password']").fill(TEST_PASSWORD)
        page.locator("button[type='submit']").click()
        page.wait_for_url(f"{BASE_URL}/", timeout=10000)
        yield page
    
    def test_response_not_numbered_steps(self, logged_in_page: Page):
        """Verify response doesn't start with numbered thinking steps."""
        message = "How many IT companies in Brussels?"
        
        chat_input = logged_in_page.locator("[data-testid='chat-input']")
        chat_input.fill(message)
        chat_input.press("Enter")
        
        # Wait for response
        logged_in_page.wait_for_selector(".chat-message.assistant", timeout=30000)
        response_text = logged_in_page.locator(".chat-message.assistant").first.inner_text()
        
        # Check no numbered steps
        assert not re.match(r'^\s*\d+\.', response_text), f"Response should not start with numbered steps: {response_text[:100]}"
    
    def test_response_no_tool_name_leakage(self, logged_in_page: Page):
        """Verify response doesn't expose tool names."""
        message = "How many IT companies in Brussels?"
        
        chat_input = logged_in_page.locator("[data-testid='chat-input']")
        chat_input.fill(message)
        chat_input.press("Enter")
        
        # Wait for response
        logged_in_page.wait_for_selector(".chat-message.assistant", timeout=30000)
        response_text = logged_in_page.locator(".chat-message.assistant").first.inner_text()
        
        # Check no tool names
        forbidden_tools = ["search_profiles", "create_segment", "export_segment", "query_unified"]
        for tool in forbidden_tools:
            assert tool not in response_text.lower(), f"Response should not contain tool name '{tool}': {response_text[:100]}"


class TestNavigation:
    """Critical path: UI navigation."""
    
    @pytest.fixture
    def logged_in_page(self, page: Page):
        """Login and return authenticated page."""
        page.goto(f"{BASE_URL}/login")
        page.locator("input[type='email']").fill(TEST_USER)
        page.locator("input[type='password']").fill(TEST_PASSWORD)
        page.locator("button[type='submit']").click()
        page.wait_for_url(f"{BASE_URL}/", timeout=10000)
        yield page
    
    def test_segment_manager_accessible(self, logged_in_page: Page):
        """Verify segment manager page loads."""
        logged_in_page.goto(f"{BASE_URL}/segments")
        expect(logged_in_page.locator("h1")).to_contain_text("Segment", ignore_case=True)
    
    def test_company_browser_accessible(self, logged_in_page: Page):
        """Verify company browser page loads."""
        logged_in_page.goto(f"{BASE_URL}/companies")
        expect(logged_in_page.locator("h1")).to_contain_text("Company", ignore_case=True)


class TestAPIHealth:
    """API health checks."""
    
    def test_api_health_endpoint(self):
        """Verify API health endpoint returns OK."""
        import requests
        
        response = requests.get(f"{API_URL}/healthz", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
    
    def test_bootstrap_endpoint(self):
        """Verify bootstrap endpoint returns config."""
        import requests
        
        response = requests.get(f"{API_URL}/api/operator/bootstrap", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "session" in data or "status" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
