import asyncio
import os

import asyncpg

async def add_columns():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before running fix_schema.py")
    conn = await asyncpg.connect(database_url)
    
    # Add AI enrichment tracking columns
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS ai_description_generated_at TIMESTAMP')
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMP')
    
    # Add validation columns  
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS email_bounce_count INTEGER DEFAULT 0')
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS phone_validation_status VARCHAR(50)')
    
    # Add contact validation result columns
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS contact_validated BOOLEAN DEFAULT FALSE')
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS contact_validated_at TIMESTAMP')
    
    # CBE integration columns
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS cbe_data JSONB')
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS nace_code VARCHAR(10)')
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS nace_description TEXT')
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS workforce_range VARCHAR(50)')
    
    # Segment/analytics columns
    await conn.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS segment_tags TEXT[] DEFAULT '{}'");
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS engagement_score INTEGER')
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS lead_score INTEGER')
    await conn.execute('ALTER TABLE companies ADD COLUMN IF NOT EXISTS churn_risk VARCHAR(20)')
    
    print('All enrichment columns added!')
    await conn.close()

asyncio.run(add_columns())
