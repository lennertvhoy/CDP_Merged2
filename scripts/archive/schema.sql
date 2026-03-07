-- CDP_Merged Database Schema v2.0
-- Azure Database for PostgreSQL Flexible Server (B1ms)
-- Run this to initialize the database

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For trigram text search
CREATE EXTENSION IF NOT EXISTS "postgis";  -- For geospatial (optional, remove if not needed)

-- 1. Companies Table
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kbo_number VARCHAR(20) UNIQUE,
    vat_number VARCHAR(20),
    company_name VARCHAR(500) NOT NULL,
    legal_form VARCHAR(100),
    
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
    company_size VARCHAR(50),
    employee_count INTEGER,
    annual_revenue DECIMAL(15, 2),
    founded_date DATE,
    
    -- Contact
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

-- Indexes for companies
CREATE INDEX IF NOT EXISTS idx_companies_kbo ON companies(kbo_number);
CREATE INDEX IF NOT EXISTS idx_companies_vat ON companies(vat_number);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies USING GIN(company_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_companies_nace ON companies(industry_nace_code);
CREATE INDEX IF NOT EXISTS idx_companies_city ON companies(city);
CREATE INDEX IF NOT EXISTS idx_companies_updated ON companies(updated_at DESC);

-- 2. Contact Persons Table
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

CREATE INDEX IF NOT EXISTS idx_contacts_company ON contact_persons(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contact_persons(email);

-- 3. Interactions Table (partitioned by month)
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

-- Create initial partitions
CREATE TABLE IF NOT EXISTS interactions_2026_03 PARTITION OF interactions
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE IF NOT EXISTS interactions_2026_04 PARTITION OF interactions
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE INDEX IF NOT EXISTS idx_interactions_company ON interactions(company_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON interactions(interaction_type, occurred_at DESC);

-- 4. Segments Table
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

-- 5. Consent Records (GDPR)
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

-- 6. Audit Log (partitioned by month)
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

-- 7. Materialized View: Company Metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS company_metrics AS
SELECT 
    c.id as company_id,
    c.company_name,
    COUNT(DISTINCT cp.id) as contact_count,
    0 as interaction_count_90d,  -- Will be updated with actual data
    c.updated_at as last_updated
FROM companies c
LEFT JOIN contact_persons cp ON cp.company_id = c.id
GROUP BY c.id, c.company_name, c.updated_at;

CREATE UNIQUE INDEX IF NOT EXISTS idx_company_metrics_id ON company_metrics(company_id);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cdpadmin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cdpadmin;

-- Refresh materialized view function
CREATE OR REPLACE FUNCTION refresh_company_metrics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY company_metrics;
END;
$$ LANGUAGE plpgsql;

-- Update trigger for companies
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON contact_persons
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_segments_updated_at BEFORE UPDATE ON segments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
