-- Migration 001: Add Projection and Writeback Tables
-- Date: 2026-03-03
-- Purpose: Create tables required for PostgreSQL ↔ Tracardi projection contract

-- ==========================================
-- 1. Profile Traits Table
-- Durable analytical traits used by the chatbot and canonical segments
-- ==========================================
CREATE TABLE IF NOT EXISTS profile_traits (
    trait_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uid VARCHAR(100) NOT NULL,
    trait_name VARCHAR(100) NOT NULL,
    trait_value_text TEXT,
    trait_value_number NUMERIC,
    trait_value_boolean BOOLEAN,
    confidence DECIMAL(5, 4),
    source_system VARCHAR(50) NOT NULL,   -- intelligence_layer, tracardi_projection, batch_model
    source_reference VARCHAR(200),
    effective_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for profile_traits
CREATE INDEX IF NOT EXISTS idx_profile_traits_uid_name 
    ON profile_traits(uid, trait_name, effective_at DESC);
CREATE INDEX IF NOT EXISTS idx_profile_traits_name 
    ON profile_traits(trait_name, effective_at DESC);
CREATE INDEX IF NOT EXISTS idx_profile_traits_source 
    ON profile_traits(source_system, created_at DESC);

-- ==========================================
-- 2. Event Facts Table
-- Normalized behavioral and operational facts from Tracardi
-- ==========================================
CREATE TABLE IF NOT EXISTS event_facts (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uid VARCHAR(100) NOT NULL,
    organization_uid VARCHAR(100),
    event_type VARCHAR(100) NOT NULL,
    event_channel VARCHAR(50),
    event_source VARCHAR(50) NOT NULL,  -- website, resend, flexmail, tracardi, support, crm
    source_event_id VARCHAR(100),
    occurred_at TIMESTAMP NOT NULL,
    event_value NUMERIC,
    attributes JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for event_facts
CREATE INDEX IF NOT EXISTS idx_event_facts_uid 
    ON event_facts(uid, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_facts_org 
    ON event_facts(organization_uid, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_facts_type 
    ON event_facts(event_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_facts_source 
    ON event_facts(event_source, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_facts_occurred 
    ON event_facts(occurred_at DESC);

-- ==========================================
-- 3. AI Decisions Table
-- Explicit provenance for AI-enriched tags and recommendations
-- ==========================================
CREATE TABLE IF NOT EXISTS ai_decisions (
    ai_decision_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uid VARCHAR(100) NOT NULL,
    decision_type VARCHAR(100) NOT NULL,      -- tag_assignment, nba, classification
    decision_name VARCHAR(100) NOT NULL,      -- pref_contact_morning, interest_low_maintenance
    decision_value TEXT,
    confidence DECIMAL(5, 4),
    source_system VARCHAR(50) NOT NULL,       -- intelligence_layer, tracardi_projection
    source_content_hash VARCHAR(128),
    model_name VARCHAR(100),
    model_version VARCHAR(100),
    decided_at TIMESTAMP NOT NULL,
    explanation JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for ai_decisions
CREATE INDEX IF NOT EXISTS idx_ai_decisions_uid 
    ON ai_decisions(uid, decided_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_name 
    ON ai_decisions(decision_name, decided_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_type 
    ON ai_decisions(decision_type, decided_at DESC);

-- ==========================================
-- 4. Activation Projection State Table
-- Track what has been projected into Tracardi and other downstream systems
-- ==========================================
CREATE TABLE IF NOT EXISTS activation_projection_state (
    projection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uid VARCHAR(100) NOT NULL,
    target_system VARCHAR(50) NOT NULL,       -- tracardi, resend, flexmail
    projected_entity_type VARCHAR(50) NOT NULL, -- profile, segment, trait
    projected_entity_key VARCHAR(100) NOT NULL,
    projection_hash VARCHAR(128),
    projection_status VARCHAR(50) NOT NULL,   -- success, failed, pending
    last_error TEXT,
    projected_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (target_system, projected_entity_type, projected_entity_key)
);

-- Indexes for activation_projection_state
CREATE INDEX IF NOT EXISTS idx_projection_state_uid 
    ON activation_projection_state(uid, target_system, projected_at DESC);
CREATE INDEX IF NOT EXISTS idx_projection_state_status 
    ON activation_projection_state(projection_status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_projection_state_target 
    ON activation_projection_state(target_system, projection_status);

-- ==========================================
-- 5. Segment Definitions Table
-- Canonical segment logic lives here, not only in Tracardi
-- ==========================================
CREATE TABLE IF NOT EXISTS segment_definitions (
    segment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    segment_key VARCHAR(100) NOT NULL UNIQUE,
    segment_name VARCHAR(200) NOT NULL,
    description TEXT,
    definition_type VARCHAR(50) NOT NULL,     -- sql, metadata, rule_graph
    definition_sql TEXT,
    definition_json JSONB DEFAULT '{}'::jsonb,
    owner VARCHAR(100),
    refresh_schedule VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    member_count INTEGER DEFAULT 0,
    last_calculated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for segment_definitions
CREATE INDEX IF NOT EXISTS idx_segment_definitions_active 
    ON segment_definitions(is_active, segment_key);

-- ==========================================
-- 6. Segment Memberships Table
-- Track which UIDs belong to which segments
-- ==========================================
CREATE TABLE IF NOT EXISTS segment_memberships (
    segment_id UUID NOT NULL REFERENCES segment_definitions(segment_id) ON DELETE CASCADE,
    uid VARCHAR(100) NOT NULL,
    calculated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    membership_reason JSONB DEFAULT '{}'::jsonb,
    projected_to_tracardi BOOLEAN DEFAULT FALSE,
    projected_at TIMESTAMP,
    PRIMARY KEY (segment_id, uid)
);

-- Indexes for segment_memberships
CREATE INDEX IF NOT EXISTS idx_segment_memberships_uid 
    ON segment_memberships(uid, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_segment_memberships_projected 
    ON segment_memberships(projected_to_tracardi, projected_at) 
    WHERE projected_to_tracardi = FALSE;

-- ==========================================
-- 7. Source Identity Links Table
-- UID bridge across systems
-- ==========================================
CREATE TABLE IF NOT EXISTS source_identity_links (
    identity_link_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uid VARCHAR(100) NOT NULL,
    subject_type VARCHAR(50) NOT NULL,  -- organization, contact, household, user
    source_system VARCHAR(50) NOT NULL,
    source_entity_type VARCHAR(50) NOT NULL,  -- company, person, ticket_requester, etc.
    source_record_id VARCHAR(100) NOT NULL,
    tracardi_profile_id VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_system, source_entity_type, source_record_id)
);

-- Indexes for source_identity_links
CREATE INDEX IF NOT EXISTS idx_identity_links_uid 
    ON source_identity_links(uid, is_primary DESC);
CREATE INDEX IF NOT EXISTS idx_identity_links_tracardi 
    ON source_identity_links(tracardi_profile_id) 
    WHERE tracardi_profile_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_identity_links_source 
    ON source_identity_links(source_system, source_entity_type, source_record_id);

-- ==========================================
-- 8. Identity Merge Events Table
-- Handle merge/split reconciliation
-- ==========================================
CREATE TABLE IF NOT EXISTS identity_merge_events (
    identity_merge_event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_system VARCHAR(50) NOT NULL,
    source_entity_type VARCHAR(50) NOT NULL,
    losing_source_record_id VARCHAR(100) NOT NULL,
    surviving_source_record_id VARCHAR(100) NOT NULL,
    losing_uid VARCHAR(100),
    surviving_uid VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,         -- merge, split, remap
    event_at TIMESTAMP NOT NULL,
    reconciled_at TIMESTAMP,
    reconciliation_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for identity_merge_events
CREATE INDEX IF NOT EXISTS idx_identity_merge_events_surviving 
    ON identity_merge_events(surviving_uid, event_at DESC);
CREATE INDEX IF NOT EXISTS idx_identity_merge_events_losing 
    ON identity_merge_events(losing_uid, event_at DESC);
CREATE INDEX IF NOT EXISTS idx_identity_merge_events_status 
    ON identity_merge_events(reconciliation_status, created_at);

-- ==========================================
-- 9. Consent Events Table
-- Immutable consent and suppression events
-- ==========================================
CREATE TABLE IF NOT EXISTS consent_events (
    consent_event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uid VARCHAR(100) NOT NULL,
    purpose VARCHAR(100) NOT NULL,            -- marketing_email, tracking, sms, etc.
    status VARCHAR(50) NOT NULL,              -- granted, revoked, suppressed
    lawful_basis VARCHAR(50),
    source_system VARCHAR(50) NOT NULL,
    source_record_id VARCHAR(100),
    event_at TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for consent_events
CREATE INDEX IF NOT EXISTS idx_consent_events_uid 
    ON consent_events(uid, purpose, event_at DESC);

-- ==========================================
-- Update timestamp trigger function
-- ==========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers
DROP TRIGGER IF EXISTS update_profile_traits_updated_at ON profile_traits;
CREATE TRIGGER update_profile_traits_updated_at
    BEFORE UPDATE ON profile_traits
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_activation_projection_state_updated_at ON activation_projection_state;
CREATE TRIGGER update_activation_projection_state_updated_at
    BEFORE UPDATE ON activation_projection_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_segment_definitions_updated_at ON segment_definitions;
CREATE TRIGGER update_segment_definitions_updated_at
    BEFORE UPDATE ON segment_definitions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_source_identity_links_updated_at ON source_identity_links;
CREATE TRIGGER update_source_identity_links_updated_at
    BEFORE UPDATE ON source_identity_links
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ==========================================
-- Migration verification query
-- ==========================================
-- Run this to verify all tables were created:
-- SELECT table_name FROM information_schema.tables 
-- WHERE table_schema = 'public' 
-- AND table_name IN ('profile_traits', 'event_facts', 'ai_decisions', 
--                    'activation_projection_state', 'segment_definitions', 
--                    'segment_memberships', 'source_identity_links', 
--                    'identity_merge_events', 'consent_events')
-- ORDER BY table_name;
