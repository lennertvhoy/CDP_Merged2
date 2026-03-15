"""PostgreSQL client for CDP_Merged - Direct database access for enrichment pipeline."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from src.core.logger import get_logger

logger = get_logger(__name__)


class PostgreSQLClient:
    """Async PostgreSQL client for profile operations."""

    def __init__(self, connection_url: str | None = None) -> None:
        """
        Initialize PostgreSQL client.

        Args:
            connection_url: PostgreSQL connection URL. If None, loads from .env.database
        """
        self.connection_url = connection_url or self._load_connection_url()
        self.pool: asyncpg.Pool | None = None

    def _load_connection_url(self) -> str:
        """Load connection URL from .env.database file."""
        from pathlib import Path

        env_path = Path(__file__).parent.parent.parent / ".env.database"
        if env_path.exists():
            import configparser

            config = configparser.ConfigParser()
            config.read(env_path)
            connection_url = config.get("connection_string", "url", fallback=None)
            if connection_url:
                return connection_url

        # Fallback to environment variable
        import os

        connection_url = os.environ.get("DATABASE_URL")
        if connection_url:
            return connection_url

        raise RuntimeError(
            "DATABASE_URL or local .env.database [connection_string] url is required."
        )

    async def connect(self) -> None:
        """Create connection pool."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.connection_url,
                min_size=1,
                max_size=10,
                command_timeout=60,
            )
            logger.info("postgresql_connected")

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("postgresql_disconnected")

    async def ensure_connected(self) -> None:
        """Ensure connection pool is established."""
        if self.pool is None:
            await self.connect()

    @asynccontextmanager
    async def transaction(self):
        """Async context manager for transactions."""
        await self.ensure_connected()
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def get_profile_count(self) -> int:
        """
        Get total number of profiles (companies).

        Returns:
            Total count of companies
        """
        await self.ensure_connected()
        assert self.pool is not None

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) FROM companies")
            return row[0] if row else 0

    async def get_profiles(
        self,
        limit: int = 100,
        offset: int = 0,
        where_clause: str | None = None,
        order_by: str = "id",
    ) -> list[dict[str, Any]]:
        """
        Fetch profiles from PostgreSQL.

        Args:
            limit: Maximum number of profiles to fetch
            offset: Number of profiles to skip
            where_clause: Optional WHERE clause (e.g., "city = 'Brussels'")
            order_by: Column to order by

        Returns:
            List of profile dictionaries
        """
        await self.ensure_connected()

        query = f"""  # nosec
            SELECT
                id,
                kbo_number,
                vat_number,
                company_name,
                legal_form,
                street_address,
                city,
                postal_code,
                country,
                geo_latitude,
                geo_longitude,
                industry_nace_code,
                nace_description,
                company_size,
                employee_count,
                revenue_range,
                founded_date,
                website_url,
                main_phone,
                main_email,
                ai_description,

                source_system,
                source_id,


                created_at,
                updated_at,
                last_sync_at,
                sync_status
            FROM companies
            {f"WHERE {where_clause}" if where_clause else ""}  # nosec
            ORDER BY {order_by}  # nosec
            LIMIT $1 OFFSET $2
        """

        assert self.pool is not None
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, limit, offset)
            return [dict(row) for row in rows]

    async def get_profile_by_id(self, profile_id: str) -> dict[str, Any] | None:
        """
        Fetch a single profile by ID.

        Args:
            profile_id: Profile UUID

        Returns:
            Profile dictionary or None if not found
        """
        await self.ensure_connected()

        query = """
            SELECT
                id,
                kbo_number,
                vat_number,
                company_name,
                legal_form,
                street_address,
                city,
                postal_code,
                country,
                geo_latitude,
                geo_longitude,
                industry_nace_code,
                nace_description,
                company_size,
                employee_count,
                revenue_range,
                founded_date,
                website_url,
                main_phone,
                main_email,
                ai_description,

                source_system,
                source_id,


                created_at,
                updated_at,
                last_sync_at,
                sync_status
            FROM companies
            WHERE id = $1
        """

        assert self.pool is not None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, profile_id)
            return dict(row) if row else None

    async def get_profile_by_kbo(self, kbo_number: str) -> dict[str, Any] | None:
        """
        Fetch a profile by KBO number.

        Args:
            kbo_number: KBO/enterprise number

        Returns:
            Profile dictionary or None if not found
        """
        await self.ensure_connected()

        query = """
            SELECT
                id,
                kbo_number,
                vat_number,
                company_name,
                legal_form,
                street_address,
                city,
                postal_code,
                country,
                geo_latitude,
                geo_longitude,
                industry_nace_code,
                nace_description,
                company_size,
                employee_count,
                revenue_range,
                founded_date,
                website_url,
                main_phone,
                main_email,
                ai_description,

                source_system,
                source_id,


                created_at,
                updated_at,
                last_sync_at,
                sync_status
            FROM companies
            WHERE kbo_number = $1
        """

        assert self.pool is not None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, kbo_number)
            return dict(row) if row else None

    async def update_profile(
        self,
        profile_id: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Update a profile with enriched data.

        Args:
            profile_id: Profile UUID
            data: Dictionary of fields to update

        Returns:
            True if update was successful
        """
        await self.ensure_connected()

        if not data:
            return True

        # Build dynamic UPDATE query
        allowed_fields = {
            "company_name",
            "legal_form",
            "street_address",
            "city",
            "postal_code",
            "country",
            "geo_latitude",
            "geo_longitude",
            "industry_nace_code",
            "nace_description",
            "company_size",
            "employee_count",
            "revenue_range",
            "founded_date",
            "website_url",
            "main_phone",
            "main_email",
            "ai_description",
            "ai_description_generated_at",
            "source_system",
            "source_id",
            "source_created_at",
            "source_updated_at",
            "last_sync_at",
            "sync_status",
        }

        # Filter to allowed fields only
        update_data = {k: v for k, v in data.items() if k in allowed_fields}

        if not update_data:
            logger.warning("postgresql_update_no_valid_fields", profile_id=profile_id)
            return False

        # Build SET clause
        set_clauses = []
        values: list[Any] = []
        for i, (key, value) in enumerate(update_data.items(), start=2):
            set_clauses.append(f"{key} = ${i}")
            values.append(value)

        query = f"""  # nosec
            UPDATE companies  # nosec
            SET {", ".join(set_clauses)}, updated_at = CURRENT_TIMESTAMP  # nosec
            WHERE id = $1
        """

        assert self.pool is not None
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, profile_id, *values)
            # Result is like "UPDATE 1" or "UPDATE 0"
            return "UPDATE 1" in result

    async def update_profiles_batch(
        self,
        updates: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, int]:
        """
        Update multiple profiles in a batch.

        Args:
            updates: List of (profile_id, data) tuples

        Returns:
            Dict with success and failed counts
        """
        await self.ensure_connected()

        success_count = 0
        failed_count = 0

        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for profile_id, data in updates:
                    if not data:
                        continue

                    allowed_fields = {
                        "company_name",
                        "legal_form",
                        "street_address",
                        "city",
                        "postal_code",
                        "country",
                        "geo_latitude",
                        "geo_longitude",
                        "industry_nace_code",
                        "nace_description",
                        "company_size",
                        "employee_count",
                        "revenue_range",
                        "founded_date",
                        "website_url",
                        "main_phone",
                        "main_email",
                        "ai_description",
                        "ai_description_generated_at",
                        "source_system",
                        "source_id",
                        "source_created_at",
                        "source_updated_at",
                        "last_sync_at",
                        "sync_status",
                    }

                    update_data = {k: v for k, v in data.items() if k in allowed_fields}

                    if not update_data:
                        continue

                    set_clauses = []
                    values: list[Any] = []
                    for key, value in update_data.items():
                        set_clauses.append(f"{key} = ${len(values) + 2}")
                        values.append(value)

                    query = f"""  # nosec
                        UPDATE companies  # nosec
                        SET {", ".join(set_clauses)}, updated_at = CURRENT_TIMESTAMP  # nosec
                        WHERE id = $1
                    """

                    try:
                        result = await conn.execute(query, profile_id, *values)
                        if "UPDATE 1" in result:
                            success_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(
                            "postgresql_batch_update_error", profile_id=profile_id, error=str(e)
                        )
                        failed_count += 1

        return {"success": success_count, "failed": failed_count}

    async def search_profiles(
        self,
        query: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Search profiles using simple query matching.

        This is a simplified search - for production, use the search_engine module.

        Args:
            query: Search query string
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Dict with total count and results list
        """
        await self.ensure_connected()

        # Simple search on company_name using trigram similarity
        search_query = """
            SELECT
                id,
                kbo_number,
                vat_number,
                company_name,
                legal_form,
                street_address,
                city,
                postal_code,
                website_url,
                main_phone,
                main_email,
                industry_nace_code,
                created_at,
                updated_at
            FROM companies
            WHERE
                company_name ILIKE $1
                OR kbo_number ILIKE $1
                OR city ILIKE $1
            ORDER BY company_name
            LIMIT $2 OFFSET $3
        """

        count_query = """
            SELECT COUNT(*) FROM companies
            WHERE
                company_name ILIKE $1
                OR kbo_number ILIKE $1
                OR city ILIKE $1
        """

        search_pattern = f"%{query}%"

        assert self.pool is not None
        async with self.pool.acquire() as conn:
            total_row = await conn.fetchrow(count_query, search_pattern)
            total = total_row[0] if total_row else 0

            rows = await conn.fetch(search_query, search_pattern, limit, offset)
            results = [dict(row) for row in rows]

            return {
                "total": total,
                "result": results,
                "limit": limit,
                "offset": offset,
            }

    async def health_check(self) -> dict[str, Any]:
        """
        Check database connectivity and return stats.

        Returns:
            Health status dict
        """
        try:
            await self.ensure_connected()
            assert self.pool is not None

            async with self.pool.acquire() as conn:
                # Check connection
                version = await conn.fetchval("SELECT version()")

                # Get counts
                company_count = await conn.fetchval("SELECT COUNT(*) FROM companies")
                contact_count = await conn.fetchval("SELECT COUNT(*) FROM contact_persons")

                return {
                    "status": "healthy",
                    "connected": True,
                    "version": version.split()[1] if version else "unknown",
                    "tables": {
                        "companies": company_count,
                        "contact_persons": contact_count,
                    },
                }
        except Exception as e:
            logger.error("postgresql_health_check_failed", error=str(e))
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
            }


# Singleton instance
_postgresql_client: PostgreSQLClient | None = None


def get_postgresql_client(connection_url: str | None = None) -> PostgreSQLClient:
    """Get or create singleton PostgreSQL client instance."""
    global _postgresql_client
    if _postgresql_client is None:
        _postgresql_client = PostgreSQLClient(connection_url)
    return _postgresql_client
