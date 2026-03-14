#!/usr/bin/env python3
"""Setup minimal database schema for smoke tests."""
import asyncio
import os
import sys

import asyncpg


async def setup() -> None:
    """Create minimal tables for smoke tests."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is required", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(database_url)

    # Create minimal tables for smoke tests
    await conn.execute(
        """
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

        CREATE TABLE IF NOT EXISTS app_chat_users (
            user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            identifier TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS app_chat_threads (
            thread_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS app_auth_local_accounts (
            account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            identifier TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    print("Database schema created successfully")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(setup())
