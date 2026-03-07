#!/usr/bin/env python3
"""
Database Migration Script v2.2

Adds extended columns for full KBO import:
- enrichment_data (JSONB)
- all_names (TEXT[])
- all_nace_codes (VARCHAR[])
- nace_descriptions (TEXT[])
- legal_form_code
- status
- juridical_situation
- type_of_enterprise
- main_fax
- establishment_count

Usage:
    python scripts/migrate_schema_v2.2.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import get_logger

logger = get_logger(__name__)

# Migration SQL
MIGRATION_SQL = """
-- Migration v2.2: Extended KBO columns
DO $$
BEGIN
    -- Add enrichment_data JSONB column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'companies' AND column_name = 'enrichment_data'
    ) THEN
        ALTER TABLE companies ADD COLUMN enrichment_data JSONB;
        RAISE NOTICE 'Added column: enrichment_data';
    END IF;

    -- Add all_names array
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'companies' AND column_name = 'all_names'
    ) THEN
        ALTER TABLE companies ADD COLUMN all_names TEXT[];
        RAISE NOTICE 'Added column: all_names';
    END IF;

    -- Add all_nace_codes array
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'companies' AND column_name = 'all_nace_codes'
    ) THEN
        ALTER TABLE companies ADD COLUMN all_nace_codes VARCHAR(10)[];
        RAISE NOTICE 'Added column: all_nace_codes';
    END IF;

    -- Add nace_descriptions array
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'companies' AND column_name = 'nace_descriptions'
    ) THEN
        ALTER TABLE companies ADD COLUMN nace_descriptions TEXT[];
        RAISE NOTICE 'Added column: nace_descriptions';
    END IF;

    -- Add legal_form_code
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'companies' AND column_name = 'legal_form_code'
    ) THEN
        ALTER TABLE companies ADD COLUMN legal_form_code VARCHAR(10);
        RAISE NOTICE 'Added column: legal_form_code';
    END IF;

    -- Add status
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'companies' AND column_name = 'status'
    ) THEN
        ALTER TABLE companies ADD COLUMN status VARCHAR(20);
        RAISE NOTICE 'Added column: status';
    END IF;

    -- Add juridical_situation
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'companies' AND column_name = 'juridical_situation'
    ) THEN
        ALTER TABLE companies ADD COLUMN juridical_situation VARCHAR(50);
        RAISE NOTICE 'Added column: juridical_situation';
    END IF;

    -- Add type_of_enterprise
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'companies' AND column_name = 'type_of_enterprise'
    ) THEN
        ALTER TABLE companies ADD COLUMN type_of_enterprise VARCHAR(20);
        RAISE NOTICE 'Added column: type_of_enterprise';
    END IF;

    -- Add main_fax
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'companies' AND column_name = 'main_fax'
    ) THEN
        ALTER TABLE companies ADD COLUMN main_fax VARCHAR(50);
        RAISE NOTICE 'Added column: main_fax';
    END IF;

    -- Add establishment_count
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'companies' AND column_name = 'establishment_count'
    ) THEN
        ALTER TABLE companies ADD COLUMN establishment_count INTEGER DEFAULT 0;
        RAISE NOTICE 'Added column: establishment_count';
    END IF;
END $$;

-- Add indexes for new columns
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status) WHERE status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_legal_form_code ON companies(legal_form_code) WHERE legal_form_code IS NOT NULL;

-- Update version comment
COMMENT ON TABLE companies IS 'Companies table v2.2 - Extended KBO support';

-- Verification
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns 
    WHERE table_name = 'companies';
    
    RAISE NOTICE 'Migration complete. Total columns in companies table: %', col_count;
END $$;
"""


async def run_migration():
    """Run the database migration."""
    try:
        import asyncpg
    except ImportError:
        logger.error("asyncpg not installed. Run: pip install asyncpg")
        raise
    
    # Get connection URL
    conn_url = os.environ.get("DATABASE_URL")
    if not conn_url:
        env_path = Path(__file__).parent.parent / ".env.database"
        if env_path.exists():
            import configparser
            config = configparser.ConfigParser()
            config.read(env_path)
            conn_url = config.get("connection_string", "url", fallback=None)
    
    if not conn_url:
        raise RuntimeError("DATABASE_URL or .env.database connection string required")
    
    logger.info("Connecting to database...")
    conn = await asyncpg.connect(conn_url)
    
    try:
        logger.info("Running migration v2.2...")
        await conn.execute(MIGRATION_SQL)
        logger.info("Migration completed successfully")
        
        # Verify
        count = await conn.fetchval("SELECT COUNT(*) FROM companies")
        logger.info(f"Current companies in database: {count:,}")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    import asyncio
    
    try:
        asyncio.run(run_migration())
        sys.exit(0)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
