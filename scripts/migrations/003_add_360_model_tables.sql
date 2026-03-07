-- Migration 003: Add 360 Data Model Core Tables
-- Date: 2026-03-04
-- Purpose: Create tables for the canonical 360 Data Model domain entities

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==========================================
-- 1. Organizations Table
-- Public company and account-level data (PII stays in source systems)
-- ==========================================
CREATE TABLE IF NOT EXISTS organizations (
    organization_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL UNIQUE,
    uid_type VARCHAR(50) NOT NULL,
    kbo_number VARCHAR(20),
    vat_number VARCHAR(20),
    legal_name VARCHAR(500) NOT NULL,
    legal_form VARCHAR(100),
    nace_code VARCHAR(10),
    nace_description VARCHAR(500),
    employee_count INTEGER,
    company_size VARCHAR(50),
    annual_revenue NUMERIC(15, 2),
    website_url VARCHAR(500),
    city VARCHAR(200),
    postal_code VARCHAR(20),
    province VARCHAR(100),
    country_code VARCHAR(2) NOT NULL DEFAULT 'BE',
    geo_latitude NUMERIC(10, 8),
    geo_longitude NUMERIC(11, 8),
    source_system VARCHAR(50) NOT NULL,
    source_record_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT uq_organizations_uid UNIQUE (uid),
    CONSTRAINT uq_organizations_source UNIQUE (source_system, source_record_id)
);

-- Indexes for organizations
CREATE INDEX IF NOT EXISTS ix_organizations_uid ON organizations(uid);
CREATE INDEX IF NOT EXISTS ix_organizations_kbo ON organizations(kbo_number);
CREATE INDEX IF NOT EXISTS ix_organizations_nace ON organizations(nace_code);
CREATE INDEX IF NOT EXISTS ix_organizations_city ON organizations(city);
CREATE INDEX IF NOT EXISTS ix_organizations_source ON organizations(source_system, source_record_id);

COMMENT ON TABLE organizations IS 'Public company data - PII lives in source systems';

-- ==========================================
-- 2. Source Identity Links Table
-- UID bridge across systems without copying raw PII
-- ==========================================
CREATE TABLE IF NOT EXISTS source_identity_links (
    identity_link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL,
    subject_type VARCHAR(50) NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    source_entity_type VARCHAR(50) NOT NULL,
    source_record_id VARCHAR(100) NOT NULL,
    tracardi_profile_id VARCHAR(100),
    is_primary BOOLEAN NOT NULL DEFAULT false,
    valid_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT uq_identity_link_source UNIQUE (source_system, source_entity_type, source_record_id)
);

-- Indexes for source_identity_links
CREATE INDEX IF NOT EXISTS ix_identity_links_uid ON source_identity_links(uid);
CREATE INDEX IF NOT EXISTS ix_identity_links_tracardi ON source_identity_links(tracardi_profile_id);
CREATE INDEX IF NOT EXISTS ix_identity_links_source ON source_identity_links(source_system, source_record_id);

COMMENT ON TABLE source_identity_links IS 'UID bridge - PII stays in source systems';

-- ==========================================
-- 3. Identity Merge Events Table
-- Track identity merges and splits for reconciliation
-- ==========================================
CREATE TABLE IF NOT EXISTS identity_merge_events (
    identity_merge_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system VARCHAR(50) NOT NULL,
    source_entity_type VARCHAR(50) NOT NULL,
    losing_source_record_id VARCHAR(100) NOT NULL,
    surviving_source_record_id VARCHAR(100) NOT NULL,
    losing_uid VARCHAR(100),
    surviving_uid VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_at TIMESTAMP NOT NULL,
    reconciled_at TIMESTAMP,
    reconciliation_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    event_metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for identity_merge_events
CREATE INDEX IF NOT EXISTS ix_identity_merge_surviving_uid ON identity_merge_events(surviving_uid, event_at);
CREATE INDEX IF NOT EXISTS ix_identity_merge_losing_uid ON identity_merge_events(losing_uid, event_at);
CREATE INDEX IF NOT EXISTS ix_identity_merge_status ON identity_merge_events(reconciliation_status, created_at);

COMMENT ON TABLE identity_merge_events IS 'Identity merge/split events for reconciliation';

-- ==========================================
-- 4. Contact Roles Table
-- Business relationships and decision roles (without PII storage)
-- ==========================================
CREATE TABLE IF NOT EXISTS contact_roles (
    contact_role_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_uid VARCHAR(100) NOT NULL,
    contact_uid VARCHAR(100) NOT NULL,
    role_name VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL,
    seniority VARCHAR(100) NOT NULL,
    is_decision_maker BOOLEAN NOT NULL DEFAULT false,
    source_system VARCHAR(50) NOT NULL,
    source_record_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT uq_contact_role UNIQUE (organization_uid, contact_uid, source_system, source_record_id)
);

-- Indexes for contact_roles
CREATE INDEX IF NOT EXISTS ix_contact_roles_org ON contact_roles(organization_uid);
CREATE INDEX IF NOT EXISTS ix_contact_roles_contact ON contact_roles(contact_uid);
CREATE INDEX IF NOT EXISTS ix_contact_roles_source ON contact_roles(source_system, source_record_id);

COMMENT ON TABLE contact_roles IS 'Contact roles - PII stays in source systems';

-- ==========================================
-- 5. Segment Definitions Table
-- Canonical segment definitions stored in PostgreSQL
-- ==========================================
CREATE TABLE IF NOT EXISTS segment_definitions (
    segment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_key VARCHAR(100) NOT NULL UNIQUE,
    segment_name VARCHAR(200) NOT NULL,
    description TEXT,
    definition_type VARCHAR(50) NOT NULL,
    definition_sql TEXT,
    definition_json JSONB,
    owner VARCHAR(100),
    refresh_schedule VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for segment_definitions
CREATE INDEX IF NOT EXISTS ix_segment_definitions_key ON segment_definitions(segment_key);
CREATE INDEX IF NOT EXISTS ix_segment_definitions_active ON segment_definitions(is_active);

COMMENT ON TABLE segment_definitions IS 'Canonical segment definitions';

-- ==========================================
-- 6. Segment Memberships Table
-- Segment membership tracking with projection state
-- ==========================================
CREATE TABLE IF NOT EXISTS segment_memberships (
    segment_id UUID NOT NULL REFERENCES segment_definitions(segment_id) ON DELETE CASCADE,
    uid VARCHAR(100) NOT NULL,
    calculated_at TIMESTAMP NOT NULL,
    membership_reason JSONB,
    projected_to_tracardi BOOLEAN NOT NULL DEFAULT false,
    projected_at TIMESTAMP,
    
    PRIMARY KEY (segment_id, uid)
);

-- Indexes for segment_memberships
CREATE INDEX IF NOT EXISTS ix_segment_memberships_uid ON segment_memberships(uid, calculated_at);
CREATE INDEX IF NOT EXISTS ix_segment_memberships_projected ON segment_memberships(projected_to_tracardi, projected_at);

COMMENT ON TABLE segment_memberships IS 'Segment memberships with projection tracking';

-- ==========================================
-- 7. Consent Events Table
-- Immutable consent ledger for GDPR compliance
-- ==========================================
CREATE TABLE IF NOT EXISTS consent_events (
    consent_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL,
    consent_type VARCHAR(50) NOT NULL,
    consent_action VARCHAR(50) NOT NULL,
    consent_scope VARCHAR(100) NOT NULL,
    consent_version VARCHAR(50) NOT NULL,
    channel VARCHAR(50),
    ip_address VARCHAR(45),
    user_agent TEXT,
    proof_reference VARCHAR(200),
    expires_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for consent_events
CREATE INDEX IF NOT EXISTS ix_consent_events_uid ON consent_events(uid, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_consent_events_type ON consent_events(consent_type, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_consent_events_action ON consent_events(consent_action, created_at DESC);

COMMENT ON TABLE consent_events IS 'Immutable consent ledger for GDPR compliance';

-- ==========================================
-- 8. PII Resolution Audits Table
-- Audit trail for PII resolution events
-- ==========================================
CREATE TABLE IF NOT EXISTS pii_resolution_audits (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(100) NOT NULL,
    resolution_type VARCHAR(50) NOT NULL,
    resolution_context VARCHAR(100) NOT NULL,
    source_systems_accessed VARCHAR(200) NOT NULL,
    authorized_by VARCHAR(100) NOT NULL,
    authorized_at TIMESTAMP NOT NULL,
    resolution_duration_ms INTEGER,
    cache_hit BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for pii_resolution_audits
CREATE INDEX IF NOT EXISTS ix_pii_audit_uid ON pii_resolution_audits(uid, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_pii_audit_type ON pii_resolution_audits(resolution_type, created_at DESC);

COMMENT ON TABLE pii_resolution_audits IS 'Audit trail for PII resolution events';

-- ==========================================
-- 9. Audit Logs Table
-- General audit logging for system events
-- ==========================================
CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(100) NOT NULL,
    record_id VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    session_id VARCHAR(100),
    request_id VARCHAR(100)
);

-- Indexes for audit_logs
CREATE INDEX IF NOT EXISTS ix_audit_logs_table ON audit_logs(table_name, record_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_logs_changed_at ON audit_logs(changed_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_logs_request ON audit_logs(request_id);

COMMENT ON TABLE audit_logs IS 'General audit logging for system events';

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

-- Apply updated_at trigger to tables with updated_at column
DO $$
BEGIN
    -- organizations
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_organizations_updated_at') THEN
        CREATE TRIGGER tr_organizations_updated_at
            BEFORE UPDATE ON organizations
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    -- contact_roles
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_contact_roles_updated_at') THEN
        CREATE TRIGGER tr_contact_roles_updated_at
            BEFORE UPDATE ON contact_roles
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    -- segment_definitions
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_segment_definitions_updated_at') THEN
        CREATE TRIGGER tr_segment_definitions_updated_at
            BEFORE UPDATE ON segment_definitions
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END;
$$;

-- ==========================================
-- Migration verification query
-- ==========================================
SELECT 
    'organizations' as table_name, 
    COUNT(*) as column_count 
FROM information_schema.columns 
WHERE table_name = 'organizations'
UNION ALL
SELECT 'source_identity_links', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'source_identity_links'
UNION ALL
SELECT 'identity_merge_events', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'identity_merge_events'
UNION ALL
SELECT 'contact_roles', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'contact_roles'
UNION ALL
SELECT 'segment_definitions', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'segment_definitions'
UNION ALL
SELECT 'segment_memberships', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'segment_memberships'
UNION ALL
SELECT 'consent_events', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'consent_events'
UNION ALL
SELECT 'pii_resolution_audits', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'pii_resolution_audits'
UNION ALL
SELECT 'audit_logs', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'audit_logs';
