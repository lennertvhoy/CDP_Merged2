-- CDP_Merged Database Schema v2.1 - Production Optimized
-- Azure Database for PostgreSQL Flexible Server
-- Optimized for 1.8M+ companies with high-throughput operations
--
-- Changes from v2.0:
-- - Additional indexes for common query patterns
-- - Partitioning for event_archive (if used)
-- - Connection pooling hints
-- - Performance monitoring tables

-- ==========================================
-- Enable required extensions
-- ==========================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- For trigram text search
CREATE EXTENSION IF NOT EXISTS "postgis";      -- For geospatial (optional)
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";  -- For query performance monitoring

-- ==========================================
-- 1. Companies Table - Core entity
-- ==========================================
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kbo_number VARCHAR(20) UNIQUE,
    vat_number VARCHAR(20),
    company_name VARCHAR(500) NOT NULL,
    legal_form VARCHAR(100),
    legal_form_code VARCHAR(10),
    juridical_situation VARCHAR(50),
    status VARCHAR(20),
    
    -- Address
    street_address TEXT,
    city VARCHAR(200),
    postal_code VARCHAR(20),
    country VARCHAR(2) DEFAULT 'BE',
    geo_latitude DECIMAL(10, 8),
    geo_longitude DECIMAL(11, 8),
    
    -- Business info
    industry_nace_code VARCHAR(10),
    industry_description VARCHAR(500),
    nace_description TEXT,
    nace_descriptions TEXT[],
    company_size VARCHAR(50),
    employee_count INTEGER,
    annual_revenue DECIMAL(15, 2),
    revenue_range VARCHAR(50),
    founded_date DATE,
    founding_year INTEGER,
    type_of_enterprise VARCHAR(20),
    
    -- Contact
    website_url VARCHAR(500),
    main_phone VARCHAR(50),
    main_fax VARCHAR(50),
    main_email VARCHAR(255),
    
    -- AI enrichment
    ai_description TEXT,
    ai_description_generated_at TIMESTAMP,
    enrichment_data JSONB,
    cbe_data JSONB,
    
    -- Source tracking
    source VARCHAR(100),
    source_system VARCHAR(50),
    source_id VARCHAR(100),
    source_created_at TIMESTAMP,
    source_updated_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(20) DEFAULT 'pending',
    all_names TEXT[],
    all_nace_codes VARCHAR(10)[],
    
    -- Engagement & scoring
    engagement_score INTEGER DEFAULT 0,
    lead_score INTEGER,
    churn_risk VARCHAR(20),
    segment_tags TEXT[] DEFAULT '{}',
    establishment_count INTEGER DEFAULT 0,
    
    -- GDPR
    data_processing_basis VARCHAR(50),
    data_retention_until DATE,
    email_bounce_count INTEGER DEFAULT 0,
    phone_validation_status VARCHAR(50),
    contact_validated BOOLEAN DEFAULT FALSE,
    contact_validated_at TIMESTAMP,
    workforce_range VARCHAR(50)
);

-- ==========================================
-- Optimized Indexes for Companies
-- ==========================================

-- Primary lookups
CREATE INDEX IF NOT EXISTS idx_companies_kbo ON companies(kbo_number);
CREATE INDEX IF NOT EXISTS idx_companies_vat ON companies(vat_number);

-- Text search (trigram for fuzzy matching)
CREATE INDEX IF NOT EXISTS idx_companies_name_trgm ON companies USING GIN(company_name gin_trgm_ops);

-- Industry and location queries
CREATE INDEX IF NOT EXISTS idx_companies_nace ON companies(industry_nace_code) 
    WHERE industry_nace_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_city ON companies(city) 
    WHERE city IS NOT NULL;

-- Composite index for chatbot city+status queries (critical for performance)
-- NOTE: status column is currently NULL for all records; data uses juridical_situation
-- This index supports the application layer which expects status='AC' for active companies
CREATE INDEX IF NOT EXISTS idx_companies_city_status_real ON companies(city, status) 
    WHERE city IS NOT NULL;

-- Covering index for aggregation queries (city + nace_code)
-- Dramatically improves "top industries in city" queries by avoiding heap access
CREATE INDEX IF NOT EXISTS idx_companies_city_nace ON companies(city, industry_nace_code) 
    WHERE city IS NOT NULL AND industry_nace_code IS NOT NULL;

-- Sync and batch processing
CREATE INDEX IF NOT EXISTS idx_companies_sync_status ON companies(sync_status) 
    WHERE sync_status IN ('pending', 'enriching', 'error');
CREATE INDEX IF NOT EXISTS idx_companies_last_sync ON companies(last_sync_at);

-- Time-based queries for incremental processing
CREATE INDEX IF NOT EXISTS idx_companies_created_at ON companies(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_companies_updated_at ON companies(updated_at DESC);

-- Composite index for enrichment pipeline (common query pattern)
CREATE INDEX IF NOT EXISTS idx_companies_enrich_ready ON companies(sync_status, updated_at) 
    WHERE sync_status IN ('pending', 'needs_enrichment');

-- Geospatial queries (if PostGIS is available)
CREATE INDEX IF NOT EXISTS idx_companies_geo ON companies(geo_latitude, geo_longitude) 
    WHERE geo_latitude IS NOT NULL AND geo_longitude IS NOT NULL;

-- Engagement scoring queries
CREATE INDEX IF NOT EXISTS idx_companies_engagement ON companies(engagement_score DESC) 
    WHERE engagement_score > 0;

-- ==========================================
-- 2. Contact Persons Table
-- ==========================================
CREATE TABLE IF NOT EXISTS contact_persons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    
    first_name VARCHAR(200),
    last_name VARCHAR(200) NOT NULL,
    job_title VARCHAR(200),
    department VARCHAR(100),
    
    email VARCHAR(255),
    phone VARCHAR(50),
    mobile VARCHAR(50),
    
    is_decision_maker BOOLEAN DEFAULT FALSE,
    decision_role VARCHAR(100),
    influence_score INTEGER CHECK (influence_score BETWEEN 1 AND 10),
    
    source_system VARCHAR(50),
    source_id VARCHAR(100),
    
    consent_email BOOLEAN DEFAULT FALSE,
    consent_phone BOOLEAN DEFAULT FALSE,
    consent_date TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Contact indexes
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contact_persons(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contact_persons(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_decision_maker ON contact_persons(is_decision_maker) WHERE is_decision_maker = TRUE;

-- ==========================================
-- 3. Interactions Table - Partitioned by month
-- ==========================================
CREATE TABLE IF NOT EXISTS interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contact_persons(id) ON DELETE SET NULL,
    
    interaction_type VARCHAR(50),  -- EMAIL, PHONE, MEETING, WEBSITE_VISIT
    direction VARCHAR(20),  -- INBOUND, OUTBOUND
    channel VARCHAR(50),
    
    subject TEXT,
    content TEXT,
    sentiment_score DECIMAL(3, 2),
    
    occurred_at TIMESTAMP NOT NULL,
    duration_seconds INTEGER,
    
    source_system VARCHAR(50),
    source_id VARCHAR(100),
    
    campaign_id VARCHAR(100),
    campaign_name VARCHAR(500),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (occurred_at);

-- Create initial partitions (adjust as needed)
CREATE TABLE IF NOT EXISTS interactions_2026_03 PARTITION OF interactions
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE IF NOT EXISTS interactions_2026_04 PARTITION OF interactions
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE IF NOT EXISTS interactions_2026_05 PARTITION OF interactions
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- Interaction indexes
CREATE INDEX IF NOT EXISTS idx_interactions_company ON interactions(company_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON interactions(interaction_type, occurred_at DESC);

-- ==========================================
-- 4. Event Archive Table - Partitioned by month
-- ==========================================
CREATE TABLE IF NOT EXISTS event_archive (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uid VARCHAR(100) NOT NULL,
    source VARCHAR(100),
    event_type VARCHAR(100) NOT NULL,
    payload JSONB,
    created_at TIMESTAMP NOT NULL
) PARTITION BY RANGE (created_at);

-- Event archive partitions
CREATE TABLE IF NOT EXISTS event_archive_2026_03 PARTITION OF event_archive
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE IF NOT EXISTS event_archive_2026_04 PARTITION OF event_archive
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

-- Event archive indexes
CREATE INDEX IF NOT EXISTS idx_event_archive_uid ON event_archive(uid);
CREATE INDEX IF NOT EXISTS idx_event_archive_type ON event_archive(event_type);
CREATE INDEX IF NOT EXISTS idx_event_archive_created ON event_archive(created_at DESC);

-- ==========================================
-- 5. Segments Table
-- ==========================================
CREATE TABLE IF NOT EXISTS segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    segment_name VARCHAR(200) NOT NULL,
    segment_description TEXT,
    
    query_definition JSONB,
    query_sql TEXT,
    
    is_dynamic BOOLEAN DEFAULT FALSE,
    last_refreshed_at TIMESTAMP,
    refresh_schedule VARCHAR(50),
    
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

CREATE INDEX IF NOT EXISTS idx_segment_members_company ON segment_members(company_id);

-- ==========================================
-- 6. Consent Records (GDPR)
-- ==========================================
CREATE TABLE IF NOT EXISTS consent_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contact_persons(id) ON DELETE CASCADE,
    
    consent_type VARCHAR(50),
    consent_given BOOLEAN,
    consent_date TIMESTAMP,
    consent_method VARCHAR(100),
    
    legal_basis VARCHAR(50),
    privacy_notice_version VARCHAR(20),
    
    withdrawn_at TIMESTAMP,
    withdrawal_method VARCHAR(100),
    
    ip_address INET,
    user_agent TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_consent_company ON consent_records(company_id, consent_type);
CREATE INDEX IF NOT EXISTS idx_consent_contact ON consent_records(contact_id, consent_type);

-- ==========================================
-- 7. Audit Log (partitioned by month)
-- ==========================================
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    event_type VARCHAR(100) NOT NULL,
    event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    actor_type VARCHAR(50),
    actor_id VARCHAR(100),
    actor_email VARCHAR(255),
    
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    
    action_type VARCHAR(50),
    action_status VARCHAR(20),
    
    request_id VARCHAR(100),
    correlation_id VARCHAR(100),
    client_ip INET,
    
    data_fields_accessed TEXT[],
    data_change JSONB,
    
    gdpr_purpose VARCHAR(100),
    encryption_status VARCHAR(50)
) PARTITION BY RANGE (event_timestamp);

CREATE TABLE IF NOT EXISTS audit_log_2026_03 PARTITION OF audit_log
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id, event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor_id, event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_correlation ON audit_log(correlation_id) WHERE correlation_id IS NOT NULL;

-- ==========================================
-- 8. Import Progress Tracking Table
-- ==========================================
CREATE TABLE IF NOT EXISTS import_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_name VARCHAR(200) NOT NULL,
    job_type VARCHAR(50),  -- 'kbo_import', 'enrichment', 'sync'
    
    total_records INTEGER,
    processed_records INTEGER DEFAULT 0,
    failed_records INTEGER DEFAULT 0,
    
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    status VARCHAR(20) DEFAULT 'running',  -- running, completed, failed, paused
    error_message TEXT,
    
    checkpoint_data JSONB,  -- For resumable imports
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_import_jobs_status ON import_jobs(status) WHERE status IN ('running', 'paused');
CREATE INDEX IF NOT EXISTS idx_import_jobs_type ON import_jobs(job_type, created_at DESC);

-- ==========================================
-- 9. Materialized Views
-- ==========================================

-- Company metrics view (refresh periodically)
CREATE MATERIALIZED VIEW IF NOT EXISTS company_metrics AS
SELECT 
    c.id as company_id,
    c.company_name,
    COUNT(DISTINCT cp.id) as contact_count,
    COUNT(DISTINCT i.id) FILTER (WHERE i.occurred_at > CURRENT_TIMESTAMP - INTERVAL '90 days') as interaction_count_90d,
    c.updated_at as last_updated
FROM companies c
LEFT JOIN contact_persons cp ON cp.company_id = c.id
LEFT JOIN interactions i ON i.company_id = c.id
GROUP BY c.id, c.company_name, c.updated_at;

CREATE UNIQUE INDEX IF NOT EXISTS idx_company_metrics_id ON company_metrics(company_id);
CREATE INDEX IF NOT EXISTS idx_company_metrics_contacts ON company_metrics(contact_count);

-- ==========================================
-- Helper Functions
-- ==========================================

-- Refresh materialized view function
CREATE OR REPLACE FUNCTION refresh_company_metrics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY company_metrics;
END;
$$ LANGUAGE plpgsql;

-- Update trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS update_companies_updated_at ON companies;
CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_contacts_updated_at ON contact_persons;
CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON contact_persons
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_segments_updated_at ON segments;
CREATE TRIGGER update_segments_updated_at BEFORE UPDATE ON segments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_import_jobs_updated_at ON import_jobs;
CREATE TRIGGER update_import_jobs_updated_at BEFORE UPDATE ON import_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function for efficient batch upsert
CREATE OR REPLACE FUNCTION upsert_companies_batch(companies_json JSONB)
RETURNS TABLE(inserted INTEGER, updated INTEGER) AS $$
DECLARE
    v_inserted INTEGER := 0;
    v_updated INTEGER := 0;
BEGIN
    -- Insert new companies
    INSERT INTO companies (
        kbo_number, company_name, street_address, city, postal_code,
        country, industry_nace_code, legal_form, founded_date,
        source_system, source_id, sync_status
    )
    SELECT 
        x.kbo_number, x.company_name, x.street_address, x.city, x.postal_code,
        x.country, x.industry_nace_code, x.legal_form, x.founded_date::DATE,
        x.source_system, x.source_id, 'pending'
    FROM jsonb_to_recordset(companies_json) AS x(
        kbo_number VARCHAR(20),
        company_name VARCHAR(500),
        street_address TEXT,
        city VARCHAR(200),
        postal_code VARCHAR(20),
        country VARCHAR(2),
        industry_nace_code VARCHAR(10),
        legal_form VARCHAR(100),
        founded_date TEXT,
        source_system VARCHAR(50),
        source_id VARCHAR(100)
    )
    ON CONFLICT (kbo_number) DO UPDATE SET
        company_name = EXCLUDED.company_name,
        street_address = EXCLUDED.street_address,
        city = EXCLUDED.city,
        postal_code = EXCLUDED.postal_code,
        legal_form = EXCLUDED.legal_form,
        updated_at = CURRENT_TIMESTAMP
    WHERE companies.source_system = EXCLUDED.source_system;
    
    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    
    RETURN QUERY SELECT v_inserted, v_updated;
END;
$$ LANGUAGE plpgsql;

-- ==========================================
-- Grants
-- ==========================================
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cdpadmin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cdpadmin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO cdpadmin;

-- Grant for pg_stat_statements
GRANT pg_read_all_stats TO cdpadmin;

-- ==========================================
-- Performance Configuration (run as superuser)
-- ==========================================
-- These settings should be applied via Azure Portal or CLI
-- but are documented here for reference:

-- Azure PostgreSQL recommended settings for 1.8M+ records:
-- shared_buffers = 2GB (25% of available memory)
-- effective_cache_size = 6GB (75% of available memory)
-- work_mem = 16MB
-- maintenance_work_mem = 512MB
-- max_connections = 200
-- max_parallel_workers_per_gather = 4
-- max_parallel_workers = 8
-- random_page_cost = 1.1 (for SSD storage)
-- effective_io_concurrency = 200
-- checkpoint_completion_target = 0.9
-- wal_buffers = 16MB
-- default_statistics_target = 100

-- ==========================================
-- Post-deployment Verification
-- ==========================================
DO $$
BEGIN
    RAISE NOTICE 'Schema v2.1 deployed successfully';
    RAISE NOTICE 'Remember to:';
    RAISE NOTICE '  1. Run ANALYZE on all tables after import';
    RAISE NOTICE '  2. Schedule regular VACUUM ANALYZE';
    RAISE NOTICE '  3. Refresh materialized views periodically';
    RAISE NOTICE '  4. Monitor pg_stat_statements for slow queries';
END $$;
