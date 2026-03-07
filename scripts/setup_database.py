#!/usr/bin/env python3
"""
CDP_Merged Database Schema Setup Script
Run this after PostgreSQL is provisioned to create all tables and indexes.
"""

import os
import sys

# Database connection - UPDATE THESE VALUES
DB_HOST = "cdp-postgres-prod.postgres.database.azure.com"
DB_NAME = "cdp_merged"
DB_USER = "cdpadmin"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

if not DB_PASSWORD:
    raise RuntimeError("DB_PASSWORD must be set before running setup_database.py")

# SQL Schema
SCHEMA_SQL = """
-- Create database (run manually if needed)
-- CREATE DATABASE cdp_merged;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================
-- 1. COMPANIES TABLE (Core entity)
-- ============================================
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kbo_number VARCHAR(20) UNIQUE,
    vat_number VARCHAR(20),
    company_name VARCHAR(500) NOT NULL,
    legal_form VARCHAR(100),
    
    -- Address (denormalized for search)
    street_address TEXT,
    city VARCHAR(200),
    postal_code VARCHAR(20),
    country VARCHAR(2) DEFAULT 'BE',
    geo_latitude DECIMAL(10, 8),
    geo_longitude DECIMAL(11, 8),
    
    -- Business info
    industry_nace_code VARCHAR(10),
    industry_description VARCHAR(500),
    company_size VARCHAR(50),
    employee_count INTEGER,
    annual_revenue DECIMAL(15, 2),
    founded_date DATE,
    
    -- Contact info
    website_url VARCHAR(500),
    main_phone VARCHAR(50),
    main_email VARCHAR(255),
    
    -- AI enrichment
    ai_description TEXT,
    ai_description_generated_at TIMESTAMP,
    
    -- Source tracking
    source_system VARCHAR(50),
    source_id VARCHAR(100),
    source_created_at TIMESTAMP,
    source_updated_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(20) DEFAULT 'pending',
    
    -- GDPR
    data_processing_basis VARCHAR(50),
    data_retention_until DATE
);

-- Companies indexes
CREATE INDEX IF NOT EXISTS idx_companies_kbo ON companies(kbo_number);
CREATE INDEX IF NOT EXISTS idx_companies_vat ON companies(vat_number);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies USING GIN(company_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_companies_city ON companies(city);
CREATE INDEX IF NOT EXISTS idx_companies_updated ON companies(updated_at DESC);

-- ============================================
-- 2. CONTACT PERSONS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS contact_persons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Personal info
    first_name VARCHAR(200),
    last_name VARCHAR(200) NOT NULL,
    job_title VARCHAR(200),
    department VARCHAR(100),
    
    -- Contact
    email VARCHAR(255),
    phone VARCHAR(50),
    mobile VARCHAR(50),
    
    -- Decision making
    is_decision_maker BOOLEAN DEFAULT FALSE,
    decision_role VARCHAR(100),
    influence_score INTEGER CHECK (influence_score BETWEEN 1 AND 10),
    
    -- Source tracking
    source_system VARCHAR(50),
    source_id VARCHAR(100),
    
    -- GDPR
    consent_email BOOLEAN DEFAULT FALSE,
    consent_phone BOOLEAN DEFAULT FALSE,
    consent_date TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Contact indexes
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contact_persons(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contact_persons(email);

-- ============================================
-- 3. INTERACTIONS TABLE (Partitioned by month)
-- ============================================
CREATE TABLE IF NOT EXISTS interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contact_persons(id) ON DELETE SET NULL,
    
    -- Interaction details
    interaction_type VARCHAR(50),
    direction VARCHAR(20),
    channel VARCHAR(50),
    
    -- Content
    subject TEXT,
    content TEXT,
    sentiment_score DECIMAL(3, 2),
    
    -- Metadata
    occurred_at TIMESTAMP NOT NULL,
    duration_seconds INTEGER,
    
    -- Source
    source_system VARCHAR(50),
    source_id VARCHAR(100),
    
    -- Campaign attribution
    campaign_id VARCHAR(100),
    campaign_name VARCHAR(500),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (occurred_at);

-- Create initial partitions
CREATE TABLE IF NOT EXISTS interactions_2026_01 PARTITION OF interactions
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE IF NOT EXISTS interactions_2026_02 PARTITION OF interactions
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE IF NOT EXISTS interactions_2026_03 PARTITION OF interactions
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

-- Interactions indexes
CREATE INDEX IF NOT EXISTS idx_interactions_company ON interactions(company_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON interactions(interaction_type, occurred_at DESC);

-- ============================================
-- 4. SEGMENTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    segment_name VARCHAR(200) NOT NULL,
    segment_description TEXT,
    
    -- Query definition
    query_definition JSONB,
    query_sql TEXT,
    
    -- Auto-refresh
    is_dynamic BOOLEAN DEFAULT FALSE,
    last_refreshed_at TIMESTAMP,
    refresh_schedule VARCHAR(50),
    
    -- Metrics
    member_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Segment members (many-to-many)
CREATE TABLE IF NOT EXISTS segment_members (
    segment_id UUID REFERENCES segments(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_reason VARCHAR(200),
    PRIMARY KEY (segment_id, company_id)
);

-- ============================================
-- 5. CONSENT RECORDS (GDPR)
-- ============================================
CREATE TABLE IF NOT EXISTS consent_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contact_persons(id) ON DELETE CASCADE,
    
    -- Consent details
    consent_type VARCHAR(50),
    consent_given BOOLEAN,
    consent_date TIMESTAMP,
    consent_method VARCHAR(100),
    
    -- Legal basis
    legal_basis VARCHAR(50),
    privacy_notice_version VARCHAR(20),
    
    -- Withdrawal
    withdrawn_at TIMESTAMP,
    withdrawal_method VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 6. AUDIT LOG (Partitioned by month)
-- ============================================
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Event
    event_type VARCHAR(100) NOT NULL,
    event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Actor
    actor_type VARCHAR(50),
    actor_id VARCHAR(100),
    actor_email VARCHAR(255),
    
    -- Resource
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    
    -- Action
    action_type VARCHAR(50),
    action_status VARCHAR(20),
    
    -- Details
    request_id VARCHAR(100),
    correlation_id VARCHAR(100),
    client_ip INET,
    
    -- Data accessed
    data_fields_accessed TEXT[],
    data_change JSONB,
    
    -- Compliance
    gdpr_purpose VARCHAR(100),
    encryption_status VARCHAR(50)
) PARTITION BY RANGE (event_timestamp);

-- Create initial partitions
CREATE TABLE IF NOT EXISTS audit_log_2026_01 PARTITION OF audit_log
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE IF NOT EXISTS audit_log_2026_02 PARTITION OF audit_log
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

-- ============================================
-- 7. MIGRATION TRACKING
-- ============================================
CREATE TABLE IF NOT EXISTS migration_status (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_system VARCHAR(50) NOT NULL,
    source_count INTEGER,
    migrated_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    last_migrated_id VARCHAR(100),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'running'
);

-- ============================================
-- 8. MATERIALIZED VIEW: Company Metrics
-- ============================================
CREATE MATERIALIZED VIEW IF NOT EXISTS company_metrics AS
SELECT 
    c.id as company_id,
    c.company_name,
    COUNT(DISTINCT cp.id) as contact_count,
    COUNT(DISTINCT i.id) as interaction_count_90d,
    MAX(i.occurred_at) as last_interaction_at
FROM companies c
LEFT JOIN contact_persons cp ON cp.company_id = c.id
LEFT JOIN interactions i ON i.company_id = c.id 
    AND i.occurred_at > NOW() - INTERVAL '90 days'
GROUP BY c.id, c.company_name;

CREATE UNIQUE INDEX IF NOT EXISTS idx_company_metrics_id ON company_metrics(company_id);

-- ============================================
-- SCHEMA COMPLETE
-- ============================================
SELECT 'Schema created successfully!' as status;
"""

def main():
    """Execute schema creation."""
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError:
        print("Error: psycopg2 not installed.")
        print("Install with: pip install psycopg2-binary")
        sys.exit(1)
    
    print(f"Connecting to {DB_HOST}...")
    
    try:
        # Connect to postgres database first to create cdp_merged
        conn = psycopg2.connect(
            host=DB_HOST,
            database="postgres",
            user=DB_USER,
            password=DB_PASSWORD,
            sslmode="require"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Create database if not exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname='cdp_merged'")
        if not cursor.fetchone():
            cursor.execute("CREATE DATABASE cdp_merged")
            print("✓ Database 'cdp_merged' created")
        else:
            print("✓ Database 'cdp_merged' already exists")
        
        cursor.close()
        conn.close()
        
        # Connect to cdp_merged database
        conn = psycopg2.connect(
            host=DB_HOST,
            database="cdp_merged",
            user=DB_USER,
            password=DB_PASSWORD,
            sslmode="require"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Execute schema
        print("Creating schema...")
        cursor.execute(SCHEMA_SQL)
        
        # Print results
        for notice in conn.notices:
            print(notice.strip())
        
        cursor.close()
        conn.close()
        
        print("\n✅ Schema setup complete!")
        print(f"\nDatabase: cdp_merged")
        print(f"Host: {DB_HOST}")
        print(f"Tables created: companies, contact_persons, interactions, segments, consent_records, audit_log")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
