#!/usr/bin/env python3
"""Simple PostgreSQL connectivity test."""

import asyncio
import asyncpg
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_connection():
    """Test basic PostgreSQL connectivity."""
    
    # Load connection URL from .env.database
    env_path = Path(__file__).parent.parent / ".env.database"
    connection_url = None
    
    if env_path.exists():
        import configparser
        config = configparser.ConfigParser()
        config.read(env_path)
        connection_url = config.get("connection_string", "url", fallback=None)
    
    if not connection_url:
        connection_url = None
        from os import getenv
        connection_url = getenv("DATABASE_URL")
    
    if not connection_url:
        raise RuntimeError(
            "Missing PostgreSQL connection details. Populate local .env.database "
            "or set DATABASE_URL before running this script."
        )
    
    print("=" * 60)
    print("PostgreSQL Connectivity Test")
    print("=" * 60)
    print("Host: configured via local .env.database or DATABASE_URL")
    print("Database: configured locally")
    print("User: configured locally")
    print()
    
    try:
        print("Connecting...")
        conn = await asyncpg.connect(connection_url)
        
        # Get version
        version = await conn.fetchval("SELECT version()")
        print(f"✅ Connected successfully!")
        print(f"PostgreSQL Version: {version.split()[1] if version else 'unknown'}")
        print()
        
        # Check if companies table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'companies'
            )
        """)
        
        if table_exists:
            print("✅ 'companies' table exists")
            
            # Get count
            count = await conn.fetchval("SELECT COUNT(*) FROM companies")
            print(f"   Companies count: {count}")
            
            # Get sample profile
            if count > 0:
                row = await conn.fetchrow("""
                    SELECT id, kbo_number, company_name, city, website_url, main_phone, ai_description
                    FROM companies 
                    LIMIT 1
                """)
                print(f"   Sample profile: {dict(row)}")
        else:
            print("❌ 'companies' table does NOT exist")
            print("   Schema needs to be deployed: psql -f schema.sql")
        
        # Check other tables
        for table in ["contact_persons", "interactions", "segments"]:
            exists = await conn.fetchval(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table}'
                )
            """)
            status = "✅" if exists else "❌"
            print(f"{status} '{table}' table {'exists' if exists else 'missing'}")
        
        await conn.close()
        
        print()
        print("=" * 60)
        print("Test completed successfully!")
        print("=" * 60)
        return True
        
    except asyncpg.PostgresError as e:
        print(f"❌ PostgreSQL Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
