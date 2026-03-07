import json
import sqlite3
from pathlib import Path
from typing import Any, Protocol

import redis.asyncio as aioredis

from src.core.logger import get_logger

logger = get_logger(__name__)


class AsyncCache(Protocol):
    """Protocol for async caching mechanisms."""

    async def get(self, key: str, default: Any = None) -> Any: ...
    async def set(self, key: str, value: Any) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def clear(self) -> None: ...
    async def close(self) -> None: ...


class SQLiteCache(AsyncCache):
    """
    SQLite-backed async cache.
    Uses small synchronous statements because executor handoff can deadlock with
    sqlite3 in this runtime.
    """

    def __init__(self, db_path: str | Path, table_name: str = "cache"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.table_name = table_name
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        # SQLite needs check_same_thread=False if shared, but we create fresh ones
        # per task/thread or use a connection pool to be safe in async context.
        return sqlite3.connect(self.db_path, check_same_thread=False, timeout=60.0)

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    async def get(self, key: str, default: Any = None) -> Any:
        def _get():
            with self._get_connection() as conn:
                cursor = conn.execute(f"SELECT value FROM {self.table_name} WHERE key = ?", (key,))  # nosec B608
                row = cursor.fetchone()
                if row:
                    try:
                        return json.loads(row[0])
                    except json.JSONDecodeError:
                        return default
                return default

        return _get()

    async def set(self, key: str, value: Any) -> None:
        def _set():
            serialized = json.dumps(value)
            with self._get_connection() as conn:
                conn.execute(
                    f"INSERT OR REPLACE INTO {self.table_name} (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (key, serialized),
                )

        _set()

    async def delete(self, key: str) -> None:
        def _delete():
            with self._get_connection() as conn:
                conn.execute(f"DELETE FROM {self.table_name} WHERE key = ?", (key,))  # nosec B608

        _delete()

    async def clear(self) -> None:
        def _clear():
            with self._get_connection() as conn:
                conn.execute(f"DELETE FROM {self.table_name}")  # nosec B608

        _clear()

    async def close(self) -> None:
        # SQLite connection handles its own closure here since we create short-lived connections
        pass


class RedisCache(AsyncCache):
    """Redis-backed async cache."""

    def __init__(
        self, url: str = "redis://localhost:6379/0", prefix: str = "cdp:", ttl: int = 86400
    ):
        self.redis = aioredis.from_url(url, decode_responses=True)
        self.prefix = prefix
        self.ttl = ttl

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    async def get(self, key: str, default: Any = None) -> Any:
        value = await self.redis.get(self._key(key))
        if value is None:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    async def set(self, key: str, value: Any) -> None:
        serialized = json.dumps(value)
        await self.redis.set(self._key(key), serialized, ex=self.ttl)

    async def delete(self, key: str) -> None:
        await self.redis.delete(self._key(key))

    async def clear(self) -> None:
        keys = await self.redis.keys(f"{self.prefix}*")
        if keys:
            await self.redis.delete(*keys)

    async def close(self) -> None:
        await self.redis.aclose()


class MultiTierCache(AsyncCache):
    """
    Multi-tier cache using L1 (e.g. Memory/SQLite) and L2 (e.g. Redis).
    Reads try L1, then L2 (populating L1).
    Writes go to both L1 and L2.
    """

    def __init__(self, l1: AsyncCache, l2: AsyncCache):
        self.l1 = l1
        self.l2 = l2

    async def get(self, key: str, default: Any = None) -> Any:
        # Try L1
        val = await self.l1.get(key, default=None)
        if val is not None:
            return val

        # Try L2
        val = await self.l2.get(key, default=None)
        if val is not None:
            # Populate L1
            await self.l1.set(key, val)
            return val

        return default

    async def set(self, key: str, value: Any) -> None:
        await self.l1.set(key, value)
        await self.l2.set(key, value)

    async def delete(self, key: str) -> None:
        await self.l1.delete(key)
        await self.l2.delete(key)

    async def clear(self) -> None:
        await self.l1.clear()
        await self.l2.clear()

    async def close(self) -> None:
        await self.l1.close()
        await self.l2.close()
