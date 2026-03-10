"""Tests for web search policy enforcement."""

import re
from unittest.mock import patch

import pytest

from src.services.web_search_policy import (
    WebSearchPolicy,
    WebSearchPolicyEnforcer,
    validate_web_search_query,
)


class TestWebSearchPolicyEnforcer:
    """Test web search policy enforcement."""

    def test_disabled_policy_blocks_all(self):
        """Test that disabled policy blocks all queries."""
        with patch.object(WebSearchPolicyEnforcer, '_parse_domains', return_value=[]):
            with patch.object(WebSearchPolicyEnforcer, '_parse_patterns', return_value=[]):
                enforcer = WebSearchPolicyEnforcer()
                enforcer.policy = WebSearchPolicy.DISABLED
                
                result = enforcer.validate_query("python tutorial")
                assert result.allowed is False
                assert "disabled" in result.reason.lower()

    def test_pii_pattern_blocking_email(self):
        """Test that email addresses are blocked."""
        enforcer = WebSearchPolicyEnforcer()
        enforcer.policy = WebSearchPolicy.RESTRICTED
        enforcer.blocked_patterns = [re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}")]
        
        result = enforcer.validate_query("Contact john.doe@company.com for help")
        assert result.allowed is False
        assert result.blocked_patterns is not None
        assert "john.doe@company.com" in result.blocked_patterns

    def test_pii_pattern_blocking_phone(self):
        """Test that phone numbers are blocked."""
        enforcer = WebSearchPolicyEnforcer()
        enforcer.policy = WebSearchPolicy.RESTRICTED
        enforcer.blocked_patterns = [re.compile(r"\b\d{10}\b")]
        
        result = enforcer.validate_query("Call 0123456789 for support")
        assert result.allowed is False
        assert result.blocked_patterns is not None
        assert "0123456789" in result.blocked_patterns

    def test_allowed_query_passes(self):
        """Test that clean queries are allowed."""
        enforcer = WebSearchPolicyEnforcer()
        enforcer.policy = WebSearchPolicy.RESTRICTED
        enforcer.blocked_patterns = []
        
        result = enforcer.validate_query("python programming tutorial")
        assert result.allowed is True

    def test_domain_validation_allowed(self):
        """Test that allowed domains pass validation."""
        enforcer = WebSearchPolicyEnforcer()
        enforcer.policy = WebSearchPolicy.RESTRICTED
        enforcer.allowed_domains = ["microsoft.com", "github.com"]
        
        assert enforcer.validate_result_domain("https://docs.microsoft.com/python") is True
        assert enforcer.validate_result_domain("https://github.com/user/repo") is True

    def test_domain_validation_blocked(self):
        """Test that non-allowed domains are blocked."""
        enforcer = WebSearchPolicyEnforcer()
        enforcer.policy = WebSearchPolicy.RESTRICTED
        enforcer.allowed_domains = ["microsoft.com"]
        
        assert enforcer.validate_result_domain("https://suspicious-site.com") is False
        assert enforcer.validate_result_domain("https://phishing-example.com") is False

    def test_domain_validation_www_subdomain(self):
        """Test that www subdomains are handled correctly."""
        enforcer = WebSearchPolicyEnforcer()
        enforcer.policy = WebSearchPolicy.RESTRICTED
        enforcer.allowed_domains = ["microsoft.com"]
        
        assert enforcer.validate_result_domain("https://www.microsoft.com") is True
        assert enforcer.validate_result_domain("https://subdomain.microsoft.com") is True

    def test_is_enabled_disabled(self):
        """Test is_enabled returns False for disabled policy."""
        enforcer = WebSearchPolicyEnforcer()
        enforcer.policy = WebSearchPolicy.DISABLED
        assert enforcer.is_enabled() is False

    def test_is_enabled_restricted(self):
        """Test is_enabled returns True for restricted policy."""
        enforcer = WebSearchPolicyEnforcer()
        enforcer.policy = WebSearchPolicy.RESTRICTED
        assert enforcer.is_enabled() is True

    def test_policy_summary(self):
        """Test policy summary generation."""
        enforcer = WebSearchPolicyEnforcer()
        enforcer.policy = WebSearchPolicy.RESTRICTED
        enforcer.allowed_domains = ["microsoft.com", "github.com"]
        
        summary = enforcer.get_policy_summary()
        assert summary["policy"] == "restricted"
        assert summary["enabled"] is True
        assert summary["allowed_domains_count"] == 2

    def test_parse_domains_empty(self):
        """Test parsing empty domain string."""
        enforcer = WebSearchPolicyEnforcer()
        domains = enforcer._parse_domains(None)
        assert domains == []
        
        domains = enforcer._parse_domains("")
        assert domains == []

    def test_parse_domains_valid(self):
        """Test parsing valid domain string."""
        enforcer = WebSearchPolicyEnforcer()
        domains = enforcer._parse_domains("microsoft.com, github.com, python.org")
        assert domains == ["microsoft.com", "github.com", "python.org"]

    def test_parse_patterns_invalid_regex(self):
        """Test that invalid regex patterns are handled gracefully."""
        enforcer = WebSearchPolicyEnforcer()
        # Invalid regex pattern
        patterns = enforcer._parse_patterns("[invalid(.")
        assert patterns == []  # Should return empty list, not crash


class TestValidateWebSearchQuery:
    """Test the convenience function."""

    @patch('src.services.web_search_policy.web_search_enforcer')
    def test_convenience_function(self, mock_enforcer):
        """Test that convenience function delegates to enforcer."""
        mock_enforcer.validate_query.return_value.allowed = True
        
        result = validate_web_search_query("test query", user_id="user123")
        mock_enforcer.validate_query.assert_called_once_with("test query", "user123")
