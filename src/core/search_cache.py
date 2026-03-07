"""Search cache for persisting TQL across conversation turns.

This module provides a reliable mechanism to persist the TQL query from a search
across separate graph invocations, enabling segment creation to use the exact
same query that produced the search results.

The cache uses SQLite for persistence with conversation_id as the key,
ensuring the TQL survives even if the checkpointer state doesn't persist.

FALLBACK: If SQLite fails (read-only filesystem), falls back to in-memory cache.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)


class InMemorySearchCache:
    """In-memory fallback cache when SQLite is not available."""

    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}
        logger.info("inmemory_search_cache_initialized")

    async def store_search(
        self,
        conversation_id: str,
        tql: str,
        params: dict[str, Any] | None = None,
        ttl_seconds: int = 3600,
    ) -> None:
        """Store search in memory."""
        now = time.time()
        expires = now + ttl_seconds
        self._cache[conversation_id] = {
            "tql": tql,
            "params": params,
            "created_at": now,
            "expires_at": expires,
        }
        logger.info(
            "inmemory_cache_stored",
            conversation_id=conversation_id,
            tql_preview=tql[:50] if tql else None,
            cache_size=len(self._cache),
        )

    async def get_last_search(self, conversation_id: str) -> dict[str, Any] | None:
        """Get search from memory, cleaning expired entries."""
        now = time.time()

        # Clean up expired entries
        expired = [cid for cid, data in self._cache.items() if data.get("expires_at", 0) < now]
        for cid in expired:
            del self._cache[cid]

        # Get entry
        entry = self._cache.get(conversation_id)
        if entry:
            logger.info(
                "inmemory_cache_retrieved",
                conversation_id=conversation_id,
                tql_preview=entry["tql"][:50] if entry.get("tql") else None,
                cache_size=len(self._cache),
            )
            return {
                "tql": entry["tql"],
                "params": entry.get("params"),
                "created_at": entry.get("created_at"),
            }
        else:
            logger.info(
                "inmemory_cache_not_found",
                conversation_id=conversation_id,
                available_ids=list(self._cache.keys()),
            )
            return None

    async def clear_conversation(self, conversation_id: str) -> None:
        """Clear a conversation from memory."""
        if conversation_id in self._cache:
            del self._cache[conversation_id]
            logger.info("inmemory_cache_cleared", conversation_id=conversation_id)

    async def cleanup_expired(self) -> int:
        """Remove expired entries."""
        now = time.time()
        expired = [cid for cid, data in self._cache.items() if data.get("expires_at", 0) < now]
        for cid in expired:
            del self._cache[cid]
        return len(expired)


class SearchCache:
    """SQLite-backed cache for storing search TQL with TTL support.

    Falls back to in-memory cache if SQLite fails (e.g., read-only filesystem).
    """

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = None
        self._sqlite_available = False
        self._in_memory = InMemorySearchCache()

        # Determine database path
        if db_path is None:
            # Try several locations in order of preference
            possible_paths = [
                Path("./data/cache/search_cache.db"),  # Default
                Path(tempfile.gettempdir()) / "cdp_search_cache.db",  # Temp dir
                Path("/tmp/cdp_search_cache.db"),  # nosec B108 - Unix temp fallback
            ]
        else:
            possible_paths = [Path(db_path)]

        # Try to initialize SQLite
        for path in possible_paths:
            if self._try_init_sqlite(path):
                self.db_path = path
                self._sqlite_available = True
                logger.info(
                    "search_cache_sqlite_initialized",
                    db_path=str(path),
                )
                break

        if not self._sqlite_available:
            logger.warning(
                "search_cache_using_in_memory_fallback",
                reason="sqlite_not_available",
            )

    def _try_init_sqlite(self, db_path: Path) -> bool:
        """Try to initialize SQLite at the given path."""
        try:
            # Check if directory is writable
            db_path.parent.mkdir(parents=True, exist_ok=True)
            test_file = db_path.parent / ".write_test"
            test_file.write_text("test")
            test_file.unlink()

            # Try to create connection and table
            conn = sqlite3.connect(db_path, check_same_thread=False, timeout=5.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS search_cache (
                    conversation_id TEXT PRIMARY KEY,
                    tql TEXT NOT NULL,
                    params TEXT,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON search_cache(expires_at)")
            conn.commit()
            conn.close()
            return True

        except Exception as exc:
            logger.debug(
                "sqlite_init_failed_for_path",
                path=str(db_path),
                error=str(exc),
            )
            return False

    def _get_connection(self) -> sqlite3.Connection | None:
        """Get a database connection with proper settings."""
        if not self._sqlite_available or not self.db_path:
            return None
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=5.0)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as exc:
            logger.error("sqlite_connection_failed", error=str(exc))
            return None

    async def store_search(
        self,
        conversation_id: str,
        tql: str,
        params: dict[str, Any] | None = None,
        ttl_seconds: int = 3600,
    ) -> None:
        """Store a search TQL for a conversation."""
        # Always store in memory as backup
        await self._in_memory.store_search(conversation_id, tql, params, ttl_seconds)

        # Also try SQLite if available
        if not self._sqlite_available:
            return

        def _store():
            conn = self._get_connection()
            if not conn:
                return
            try:
                now = time.time()
                expires = now + ttl_seconds
                with conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO search_cache
                        (conversation_id, tql, params, created_at, expires_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            conversation_id,
                            tql,
                            json.dumps(params) if params else None,
                            now,
                            expires,
                        ),
                    )
                logger.info(
                    "search_cache_stored_sqlite",
                    conversation_id=conversation_id,
                    tql_preview=tql[:50] if tql else None,
                )
            except Exception as exc:
                logger.error("search_cache_sqlite_store_failed", error=str(exc))
            finally:
                conn.close()

        try:
            _store()
        except Exception as exc:
            logger.error("search_cache_store_executor_failed", error=str(exc))

    async def get_last_search(self, conversation_id: str) -> dict[str, Any] | None:
        """Retrieve the last search for a conversation."""
        # Try in-memory first (faster)
        memory_result = await self._in_memory.get_last_search(conversation_id)
        if memory_result:
            logger.info(
                "search_cache_found_in_memory",
                conversation_id=conversation_id,
            )
            return memory_result

        # Fall back to SQLite
        if not self._sqlite_available:
            logger.info(
                "search_cache_not_found",
                conversation_id=conversation_id,
                sqlite_available=False,
            )
            return None

        def _get():
            conn = self._get_connection()
            if not conn:
                return None
            try:
                now = time.time()
                with conn:
                    # Clean up expired
                    conn.execute("DELETE FROM search_cache WHERE expires_at < ?", (now,))

                    # Get entry
                    cursor = conn.execute(
                        "SELECT tql, params, created_at FROM search_cache WHERE conversation_id = ?",
                        (conversation_id,),
                    )
                    row = cursor.fetchone()

                    if row:
                        logger.info(
                            "search_cache_found_in_sqlite",
                            conversation_id=conversation_id,
                        )
                        return {
                            "tql": row["tql"],
                            "params": json.loads(row["params"]) if row["params"] else None,
                            "created_at": row["created_at"],
                        }
                    else:
                        logger.info(
                            "search_cache_not_found_in_sqlite",
                            conversation_id=conversation_id,
                        )
                        return None
            except Exception as exc:
                logger.error("search_cache_sqlite_get_failed", error=str(exc))
                return None
            finally:
                conn.close()

        try:
            return _get()
        except Exception as exc:
            logger.error("search_cache_get_executor_failed", error=str(exc))
            return None

    async def clear_conversation(self, conversation_id: str) -> None:
        """Clear the cache for a specific conversation."""
        await self._in_memory.clear_conversation(conversation_id)

        if not self._sqlite_available:
            return

        def _clear():
            conn = self._get_connection()
            if not conn:
                return
            try:
                with conn:
                    conn.execute(
                        "DELETE FROM search_cache WHERE conversation_id = ?",
                        (conversation_id,),
                    )
            finally:
                conn.close()

        try:
            _clear()
        except Exception as exc:
            logger.error("search_cache_clear_failed", error=str(exc))

    async def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        # Clean up in-memory
        memory_count = await self._in_memory.cleanup_expired()

        if not self._sqlite_available:
            return memory_count

        def _cleanup():
            conn = self._get_connection()
            if not conn:
                return 0
            try:
                now = time.time()
                with conn:
                    cursor = conn.execute(
                        "DELETE FROM search_cache WHERE expires_at < ?",
                        (now,),
                    )
                    return cursor.rowcount
            finally:
                conn.close()

        try:
            sqlite_count = _cleanup()
            return memory_count + sqlite_count
        except Exception as exc:
            logger.error("search_cache_cleanup_failed", error=str(exc))
            return memory_count


# Singleton instance for application-wide use
_search_cache_instance: SearchCache | None = None


def get_search_cache() -> SearchCache:
    """Get the singleton SearchCache instance."""
    global _search_cache_instance
    if _search_cache_instance is None:
        _search_cache_instance = SearchCache()
    return _search_cache_instance


async def store_search_tql(
    conversation_id: str,
    tql: str,
    params: dict[str, Any] | None = None,
) -> None:
    """Convenience function to store search TQL."""
    cache = get_search_cache()
    await cache.store_search(conversation_id, tql, params)


async def get_last_search_tql(conversation_id: str) -> str | None:
    """Convenience function to get last search TQL."""
    cache = get_search_cache()
    result = await cache.get_last_search(conversation_id)
    return result["tql"] if result else None


__all__ = [
    "SearchCache",
    "InMemorySearchCache",
    "get_search_cache",
    "store_search_tql",
    "get_last_search_tql",
]
