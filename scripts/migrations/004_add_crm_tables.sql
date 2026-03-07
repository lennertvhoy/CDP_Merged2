-- Migration 004: Add CRM Tables for Source System Integration
-- Date: 2026-03-07
-- Purpose: Store CRM data from Teamleader (and later Exact, Autotask)
-- Note: PII (names, emails, phones) is stored for operational needs but should be minimized

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==========================================
-- 1. CRM Companies Table
-- Company data from CRM systems (Teamleader, Exact, etc.)
-- ==========================================
CREATE TABLE IF NOT EXISTS crm_companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Source identification
    source_system VARCHAR(50) NOT NULL DEFAULT 'teamleader',
    source_record_id VARCHAR(100) NOT NULL,
    
    -- Identity linking (to KBO/organizations)
    kbo_number VARCHAR(20),
    vat_number VARCHAR(20),
    organization_uid VARCHAR(100),
    
    -- Company info
    company_name VARCHAR(500) NOT NULL,
    legal_name VARCHAR(500),
    business_type VARCHAR(100),
    status VARCHAR(50),
    
    -- Address
    street_address TEXT,
    city VARCHAR(200),
    postal_code VARCHAR(20),
    country VARCHAR(2) DEFAULT 'BE',
    
    -- Contact info (minimal PII for matching)
    main_email VARCHAR(255),
    email_domain VARCHAR(100),
    main_phone VARCHAR(50),
    website_url VARCHAR(500),
    
    -- CRM-specific data
    crm_status VARCHAR(50),
    customer_type VARCHAR(100),
    lead_source VARCHAR(200),
    
    -- Sync tracking
    source_created_at TIMESTAMP,
    source_updated_at TIMESTAMP,
    last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_version INTEGER DEFAULT 1,
    
    -- Raw data for debugging
    raw_data JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(source_system, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_crm_companies_source ON crm_companies(source_system, source_record_id);
CREATE INDEX IF NOT EXISTS idx_crm_companies_kbo ON crm_companies(kbo_number) WHERE kbo_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_crm_companies_vat ON crm_companies(vat_number) WHERE vat_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_crm_companies_org_uid ON crm_companies(organization_uid) WHERE organization_uid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_crm_companies_name ON crm_companies USING GIN (company_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_crm_companies_city ON crm_companies(city) WHERE city IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_crm_companies_sync ON crm_companies(last_sync_at);
CREATE INDEX IF NOT EXISTS idx_crm_companies_email_domain ON crm_companies(email_domain) WHERE email_domain IS NOT NULL;

COMMENT ON TABLE crm_companies IS 'CRM company data from source systems (Teamleader, Exact, Autotask)';

-- ==========================================
-- 2. CRM Contacts Table
-- Contact data from CRM systems
-- PII minimized - only store what's needed for identity linking
-- ==========================================
CREATE TABLE IF NOT EXISTS crm_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Source identification
    source_system VARCHAR(50) NOT NULL DEFAULT 'teamleader',
    source_record_id VARCHAR(100) NOT NULL,
    
    -- Link to company
    crm_company_id UUID REFERENCES crm_companies(id) ON DELETE CASCADE,
    source_company_id VARCHAR(100),
    
    -- Identity linking
    contact_uid VARCHAR(100),
    
    -- Minimal PII for identity (hashed where possible)
    first_name VARCHAR(200),
    last_name VARCHAR(200),
    full_name VARCHAR(400),
    
    -- Contact info
    email VARCHAR(255),
    email_hash VARCHAR(64), -- SHA-256 hash for matching without storing email
    phone VARCHAR(50),
    mobile VARCHAR(50),
    
    -- Professional info (not PII)
    job_title VARCHAR(200),
    department VARCHAR(100),
    seniority VARCHAR(50),
    is_decision_maker BOOLEAN DEFAULT FALSE,
    
    -- CRM-specific
    contact_status VARCHAR(50),
    lead_score INTEGER,
    
    -- Sync tracking
    source_created_at TIMESTAMP,
    source_updated_at TIMESTAMP,
    last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_version INTEGER DEFAULT 1,
    
    -- Raw data (for debugging, should be purged regularly)
    raw_data JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(source_system, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_crm_contacts_source ON crm_contacts(source_system, source_record_id);
CREATE INDEX IF NOT EXISTS idx_crm_contacts_company ON crm_contacts(crm_company_id);
CREATE INDEX IF NOT EXISTS idx_crm_contacts_email_hash ON crm_contacts(email_hash) WHERE email_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_crm_contacts_name ON crm_contacts USING GIN (full_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_crm_contacts_sync ON crm_contacts(last_sync_at);

COMMENT ON TABLE crm_contacts IS 'CRM contact data - PII stored only for operational identity linking';

-- ==========================================
-- 3. CRM Deals Table
-- Pipeline/deal data from CRM systems
-- ==========================================
CREATE TABLE IF NOT EXISTS crm_deals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Source identification
    source_system VARCHAR(50) NOT NULL DEFAULT 'teamleader',
    source_record_id VARCHAR(100) NOT NULL,
    
    -- Link to company
    crm_company_id UUID REFERENCES crm_companies(id) ON DELETE CASCADE,
    source_company_id VARCHAR(100),
    
    -- Deal info
    deal_title VARCHAR(500) NOT NULL,
    deal_description TEXT,
    
    -- Financial
    deal_value DECIMAL(15, 2),
    deal_currency VARCHAR(3) DEFAULT 'EUR',
    
    -- Pipeline status
    deal_status VARCHAR(50), -- open, won, lost
    deal_phase VARCHAR(200),
    probability INTEGER, -- 0-100
    
    -- Dates
    expected_close_date DATE,
    actual_close_date DATE,
    
    -- Source tracking
    source_created_at TIMESTAMP,
    source_updated_at TIMESTAMP,
    last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_version INTEGER DEFAULT 1,
    
    -- Raw data
    raw_data JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(source_system, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_crm_deals_source ON crm_deals(source_system, source_record_id);
CREATE INDEX IF NOT EXISTS idx_crm_deals_company ON crm_deals(crm_company_id);
CREATE INDEX IF NOT EXISTS idx_crm_deals_status ON crm_deals(deal_status);
CREATE INDEX IF NOT EXISTS idx_crm_deals_phase ON crm_deals(deal_phase);
CREATE INDEX IF NOT EXISTS idx_crm_deals_expected_close ON crm_deals(expected_close_date);
CREATE INDEX IF NOT EXISTS idx_crm_deals_sync ON crm_deals(last_sync_at);

COMMENT ON TABLE crm_deals IS 'CRM deal/pipeline data from source systems';

-- ==========================================
-- 4. CRM Activities Table
-- Activities/events from CRM systems
-- ==========================================
CREATE TABLE IF NOT EXISTS crm_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Source identification
    source_system VARCHAR(50) NOT NULL DEFAULT 'teamleader',
    source_record_id VARCHAR(100) NOT NULL,
    
    -- Link to related entities
    crm_company_id UUID REFERENCES crm_companies(id) ON DELETE CASCADE,
    crm_contact_id UUID REFERENCES crm_contacts(id) ON DELETE CASCADE,
    crm_deal_id UUID REFERENCES crm_deals(id) ON DELETE CASCADE,
    source_company_id VARCHAR(100),
    source_contact_id VARCHAR(100),
    
    -- Activity info
    activity_type VARCHAR(50), -- call, meeting, email, note, task
    activity_subject VARCHAR(500),
    activity_description TEXT,
    
    -- Participants (stored as JSON array of source IDs, not PII)
    participant_source_ids JSONB DEFAULT '[]',
    
    -- Timing
    activity_date TIMESTAMP,
    activity_end_date TIMESTAMP,
    duration_minutes INTEGER,
    
    -- Outcome
    outcome VARCHAR(200),
    outcome_notes TEXT,
    completed BOOLEAN DEFAULT FALSE,
    
    -- Source tracking
    source_created_at TIMESTAMP,
    source_updated_at TIMESTAMP,
    last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_version INTEGER DEFAULT 1,
    
    -- Raw data
    raw_data JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(source_system, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_crm_activities_source ON crm_activities(source_system, source_record_id);
CREATE INDEX IF NOT EXISTS idx_crm_activities_company ON crm_activities(crm_company_id);
CREATE INDEX IF NOT EXISTS idx_crm_activities_contact ON crm_activities(crm_contact_id);
CREATE INDEX IF NOT EXISTS idx_crm_activities_deal ON crm_activities(crm_deal_id);
CREATE INDEX IF NOT EXISTS idx_crm_activities_type ON crm_activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_crm_activities_date ON crm_activities(activity_date);
CREATE INDEX IF NOT EXISTS idx_crm_activities_sync ON crm_activities(last_sync_at);

COMMENT ON TABLE crm_activities IS 'CRM activity/event data from source systems';

-- ==========================================
-- 5. Sync State Table
-- Track incremental sync cursors for each source
-- ==========================================
CREATE TABLE IF NOT EXISTS sync_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL, -- companies, contacts, deals, activities
    cursor_value VARCHAR(500), -- last synced ID or timestamp
    cursor_type VARCHAR(50), -- id, timestamp, page
    records_synced INTEGER DEFAULT 0,
    last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_status VARCHAR(50) DEFAULT 'idle', -- idle, running, error
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(source_system, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_sync_state_source ON sync_state(source_system, entity_type);
CREATE INDEX IF NOT EXISTS idx_sync_state_status ON sync_state(sync_status);

COMMENT ON TABLE sync_state IS 'Incremental sync cursor tracking for source systems';

-- ==========================================
-- Triggers for updated_at timestamps
-- ==========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_crm_companies_updated_at') THEN
        CREATE TRIGGER tr_crm_companies_updated_at
            BEFORE UPDATE ON crm_companies
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_crm_contacts_updated_at') THEN
        CREATE TRIGGER tr_crm_contacts_updated_at
            BEFORE UPDATE ON crm_contacts
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_crm_deals_updated_at') THEN
        CREATE TRIGGER tr_crm_deals_updated_at
            BEFORE UPDATE ON crm_deals
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_crm_activities_updated_at') THEN
        CREATE TRIGGER tr_crm_activities_updated_at
            BEFORE UPDATE ON crm_activities
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_sync_state_updated_at') THEN
        CREATE TRIGGER tr_sync_state_updated_at
            BEFORE UPDATE ON sync_state
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END;
$$;

-- ==========================================
-- Migration verification
-- ==========================================
SELECT 
    'crm_companies' as table_name, 
    COUNT(*) as column_count 
FROM information_schema.columns 
WHERE table_name = 'crm_companies'
UNION ALL
SELECT 'crm_contacts', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'crm_contacts'
UNION ALL
SELECT 'crm_deals', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'crm_deals'
UNION ALL
SELECT 'crm_activities', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'crm_activities'
UNION ALL
SELECT 'sync_state', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'sync_state';
