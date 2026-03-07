"""
Base classes and utilities for enrichment modules.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.core.cache import AsyncCache, SQLiteCache
from src.core.logger import get_logger
from src.core.rate_limit import AsyncRateLimiter

logger = get_logger(__name__)


@dataclass
class EnrichmentResult:
    """Result of an enrichment operation."""

    entity_id: str
    field: str
    value: Any
    success: bool
    source: str
    timestamp: str
    error: str | None = None
    metadata: dict | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class EnrichmentStats:
    """Statistics for enrichment operations."""

    source: str
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    start_time: datetime | None = None
    end_time: datetime | None = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.success / self.total) * 100

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "source": self.source,
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": round(self.success_rate, 2),
            "duration_seconds": round(self.duration_seconds, 2),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class BaseEnricher(ABC):
    """Base class for all enrichers."""

    def __init__(
        self,
        cache_dir: str | None = None,
        cache_file: str | None = None,
        max_concurrent: int = 10,
        rate_limiter: AsyncRateLimiter | None = None,
        cache: AsyncCache | None = None,
    ):
        self.stats = EnrichmentStats(source=self.__class__.__name__)
        self.max_concurrent = max_concurrent
        self.rate_limiter = rate_limiter
        self.cache: AsyncCache

        if cache is not None:
            self.cache = cache
        elif cache_file:
            db_file = cache_file.replace(".json", ".db")
            if not db_file.endswith(".db"):
                db_file += ".db"

            out_dir = Path(cache_dir) if cache_dir else Path("./data/cache")
            out_dir.mkdir(parents=True, exist_ok=True)
            db_path = out_dir / db_file

            self.cache = SQLiteCache(db_path=db_path, table_name=self.__class__.__name__.lower())
        else:
            self.cache = SQLiteCache(
                db_path=":memory:", table_name=self.__class__.__name__.lower()
            )

    def _load_cache(self):  # noqa: B027
        """Deprecated: Cache is now accessed asynchronously."""
        pass

    def _save_cache(self):  # noqa: B027
        """Deprecated: Cache is saved asynchronously on write."""
        pass

    def get_cache_key(self, **kwargs) -> str:
        """Generate a cache key from kwargs."""
        return json.dumps(kwargs, sort_keys=True)

    def start(self):
        """Start enrichment tracking."""
        self.stats.start_time = datetime.now(UTC)
        self.stats = EnrichmentStats(source=self.__class__.__name__)

    def finish(self):
        """Finish enrichment tracking."""
        self.stats.end_time = datetime.now(UTC)
        # AsyncCache doesn't require explicit save_cache, we can just optionally close it.
        # However, to be purely clean we would await cache.close(), but finish() is sync.
        pass

    @abstractmethod
    async def enrich_profile(self, profile: dict) -> dict:
        """
        Enrich a single profile.

        Args:
            profile: The profile to enrich

        Returns:
            Enriched profile
        """
        pass

    @abstractmethod
    def can_enrich(self, profile: dict) -> bool:
        """
        Check if this enricher can process the given profile.

        Args:
            profile: The profile to check

        Returns:
            bool: True if it can enrich, False otherwise
        """
        pass

    async def enrich_batch(
        self, profiles: list[dict], override_concurrent: int | None = None
    ) -> list[dict]:
        """
        Enrich a batch of profiles concurrently with rate limiting.

        Args:
            profiles: List of profiles to enrich
            override_concurrent: Override the default max_concurrent for this batch

        Returns:
            Enriched profiles
        """
        concurrency = (
            override_concurrent if override_concurrent is not None else self.max_concurrent
        )
        semaphore = asyncio.Semaphore(concurrency)

        async def _enrich_with_limit(profile: dict) -> dict:
            async with semaphore:
                if self.rate_limiter:
                    await self.rate_limiter.acquire()
                return await self.enrich_profile(profile)

        tasks = [_enrich_with_limit(p) for p in profiles]
        return await asyncio.gather(*tasks)
