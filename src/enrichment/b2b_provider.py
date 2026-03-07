"""
B2B Provider Stub - FUTURE FEATURE.

Phase 3 Enrichment placeholder.

IMPORTANT: This is a stub implementation for future B2B API integrations.
It does NOT currently perform any enrichment. The actual implementation
will integrate with services like Cognism, Lusha, or similar B2B data providers.

Planned functionality (not yet implemented):
- Contact discovery via B2B APIs
- Company enrichment with employee counts, revenue data
- Decision-maker identification
- Direct dial and email discovery
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.enrichment.base import BaseEnricher

logger = get_logger(__name__)


class B2BProviderEnricher(BaseEnricher):
    """
    Stub for B2B API integrations (e.g. Cognism, Lusha).

    This is a placeholder for future Phase 3 enrichment functionality.
    Currently always returns False for can_enrich() and performs no operations.

    To enable: Implement actual API calls to B2B data providers in enrich_profile()
    and update can_enrich() with appropriate logic.
    """

    def __init__(self, cache_dir: str | None = "./data/cache", cache_file: str = "b2b_cache.json"):
        super().__init__(cache_dir=cache_dir, cache_file=cache_file)
        logger.warning(
            "B2BProviderEnricher is a stub/future feature. "
            "No actual B2B enrichment is being performed. "
            "Implement API integrations (Cognism, Lusha, etc.) to enable this feature."
        )

    def can_enrich(self, profile: dict) -> bool:
        """
        Always returns False since it's just a stub.

        Future implementation should check if profile has sufficient
        data (company name, domain, etc.) to query B2B APIs.
        """
        return False

    async def enrich_profile(self, profile: dict) -> dict:
        """
        No-op stub method.

        Future implementation should:
        1. Query B2B APIs for contact/company data
        2. Merge results into profile
        3. Update stats appropriately
        """
        self.stats.skipped += 1
        logger.debug("B2BProviderEnricher.skipped - stub implementation, no enrichment performed")
        return profile
