"""
Web Search Policy enforcement for CDP Chatbot.

Implements privacy and compliance guardrails for web search functionality:
- Domain allowlist (restricted mode)
- PII pattern blocking
- Audit logging
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


class WebSearchPolicy(Enum):
    """Web search policy modes."""

    DISABLED = "disabled"
    RESTRICTED = "restricted"  # Admin-controlled allowlist
    OPT_IN = "opt-in"  # User must explicitly enable per-query
    DEFAULT_ON = "default-on"  # Enabled with safety filters


@dataclass
class WebSearchValidation:
    """Result of validating a web search query."""

    allowed: bool
    reason: str | None = None
    blocked_patterns: list[str] | None = None
    allowed_domains: list[str] | None = None


class WebSearchPolicyEnforcer:
    """Enforces web search policies and privacy guardrails."""

    def __init__(self):
        self.policy = WebSearchPolicy(settings.WEB_SEARCH_POLICY.lower())
        self.allowed_domains = self._parse_domains(settings.WEB_SEARCH_ALLOWED_DOMAINS)
        self.blocked_patterns = self._parse_patterns(settings.WEB_SEARCH_BLOCKED_PATTERNS)
        self.audit_log = settings.WEB_SEARCH_AUDIT_LOG

    def _parse_domains(self, domains_str: str | None) -> list[str]:
        """Parse comma-separated domain list."""
        if not domains_str:
            return []
        return [d.strip().lower() for d in domains_str.split(",") if d.strip()]

    def _parse_patterns(self, patterns_str: str | None) -> list[re.Pattern]:
        """Parse comma-separated regex patterns."""
        if not patterns_str:
            # Default PII patterns
            patterns_str = r"\b\d{10}\b,\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        patterns = []
        for pattern in patterns_str.split(","):
            pattern = pattern.strip()
            if pattern:
                try:
                    patterns.append(re.compile(pattern))
                except re.error as e:
                    logger.warning("invalid_regex_pattern", pattern=pattern, error=str(e))
        return patterns

    def is_enabled(self) -> bool:
        """Check if web search is enabled."""
        return self.policy != WebSearchPolicy.DISABLED

    def validate_query(self, query: str, user_id: str | None = None) -> WebSearchValidation:
        """
        Validate a web search query against policy.

        Args:
            query: The search query to validate
            user_id: Optional user identifier for audit logging

        Returns:
            WebSearchValidation with allow/deny decision
        """
        # Check if disabled
        if self.policy == WebSearchPolicy.DISABLED:
            return WebSearchValidation(
                allowed=False, reason="Web search is disabled by administrator"
            )

        # Check for blocked PII patterns
        blocked_matches = []
        for pattern in self.blocked_patterns:
            matches = pattern.findall(query)
            blocked_matches.extend(matches)

        if blocked_matches:
            self._audit_log("BLOCKED_PII", query, user_id, blocked_patterns=blocked_matches)
            return WebSearchValidation(
                allowed=False,
                reason="Query contains potentially sensitive information (PII)",
                blocked_patterns=blocked_matches,
            )

        # For restricted mode, we don't validate domains here
        # (domains are validated against results, not queries)
        if self.policy == WebSearchPolicy.RESTRICTED:
            self._audit_log("ALLOWED_RESTRICTED", query, user_id)
            return WebSearchValidation(allowed=True, allowed_domains=self.allowed_domains)

        self._audit_log("ALLOWED", query, user_id)
        return WebSearchValidation(allowed=True)

    def validate_result_domain(self, url: str) -> bool:
        """
        Check if a search result domain is allowed.

        Args:
            url: The result URL to check

        Returns:
            True if domain is allowed
        """
        if self.policy != WebSearchPolicy.RESTRICTED:
            return True

        if not self.allowed_domains:
            return True  # No restrictions configured

        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove www. prefix for comparison
            if domain.startswith("www."):
                domain = domain[4:]

            # Check if domain matches any allowed domain
            for allowed in self.allowed_domains:
                if domain == allowed or domain.endswith(f".{allowed}"):
                    return True

            logger.debug("domain_blocked", url=url, domain=domain)
            return False

        except Exception as e:
            logger.warning("domain_validation_error", url=url, error=str(e))
            return False

    def _audit_log(self, action: str, query: str, user_id: str | None = None, **kwargs):
        """Log web search activity for audit purposes."""
        if not self.audit_log:
            return

        log_entry = {
            "action": action,
            "query_preview": query[:100] + "..." if len(query) > 100 else query,
            "user_id": user_id,
            "policy": self.policy.value,
        }
        log_entry.update(kwargs)

        logger.info("web_search_audit", **log_entry)

    def get_policy_summary(self) -> dict[str, Any]:
        """Get a summary of the current policy configuration."""
        return {
            "policy": self.policy.value,
            "enabled": self.is_enabled(),
            "allowed_domains_count": len(self.allowed_domains),
            "allowed_domains": self.allowed_domains[:5]
            if self.allowed_domains
            else [],  # Limit output
            "blocked_patterns_count": len(self.blocked_patterns),
            "audit_logging": self.audit_log,
        }


# Global enforcer instance
web_search_enforcer = WebSearchPolicyEnforcer()


def validate_web_search_query(query: str, user_id: str | None = None) -> WebSearchValidation:
    """
    Convenience function to validate a web search query.

    Args:
        query: The search query to validate
        user_id: Optional user identifier for audit logging

    Returns:
        WebSearchValidation with allow/deny decision
    """
    return web_search_enforcer.validate_query(query, user_id)


def is_web_search_enabled() -> bool:
    """Check if web search is enabled."""
    return web_search_enforcer.is_enabled()


def get_web_search_policy_summary() -> dict[str, Any]:
    """Get current web search policy summary."""
    return web_search_enforcer.get_policy_summary()
