#!/usr/bin/env python3
"""Deploy the PostgreSQL schema using local-only configuration."""

from __future__ import annotations

import configparser
import os
from pathlib import Path

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def load_db_config() -> dict[str, str | int]:
    """Load connection details from a local untracked file or environment."""
    env_path = Path(__file__).with_name(".env.database")
    if env_path.exists():
        config = configparser.ConfigParser()
        config.read(env_path)
        if config.has_section("database"):
            return {
                "host": config.get("database", "host"),
                "port": config.getint("database", "port", fallback=5432),
                "database": config.get("database", "database"),
                "user": config.get("database", "username"),
                "password": config.get("database", "password"),
                "sslmode": config.get("database", "ssl_mode", fallback="require"),
            }

    required = {
        "host": os.getenv("POSTGRES_HOST"),
        "database": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        joined = ", ".join(sorted(missing))
        raise RuntimeError(
            f"Missing PostgreSQL configuration: {joined}. "
            "Populate local .env.database or set POSTGRES_* environment variables."
        )

    return {
        "host": str(required["host"]),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": str(required["database"]),
        "user": str(required["user"]),
        "password": str(required["password"]),
        "sslmode": os.getenv("POSTGRES_SSLMODE", "require"),
    }


def deploy_schema() -> None:
    """Deploy the schema from schema.sql."""
    db_config = load_db_config()
    schema_path = Path(__file__).with_name("schema.sql")

    print(f"Connecting to PostgreSQL at {db_config['host']}...")
    conn = psycopg2.connect(**db_config)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    print("Reading schema file...")
    schema_sql = schema_path.read_text(encoding="utf-8")

    print("Deploying schema...")
    with conn.cursor() as cur:
        cur.execute(schema_sql)

    print("Schema deployed successfully.")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
            """
        )
        tables = cur.fetchall()
        print(f"\nTables created: {len(tables)}")
        for table in tables:
            print(f"  - {table[0]}")

    conn.close()
    print("\nDeployment complete.")


if __name__ == "__main__":
    deploy_schema()
