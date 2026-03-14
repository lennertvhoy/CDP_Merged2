CREATE TABLE IF NOT EXISTS profile_traits (
    trait_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uid VARCHAR(100) NOT NULL,
    trait_name VARCHAR(100) NOT NULL,
    trait_value_text TEXT,
    trait_value_number NUMERIC,
    trait_value_boolean BOOLEAN,
    confidence DECIMAL(5, 4),
    source_system VARCHAR(50) NOT NULL,
    source_reference VARCHAR(200),
    effective_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_profile_traits_uid_name
    ON profile_traits(uid, trait_name, effective_at DESC);
CREATE INDEX IF NOT EXISTS idx_profile_traits_name
    ON profile_traits(trait_name, effective_at DESC);
CREATE INDEX IF NOT EXISTS idx_profile_traits_source
    ON profile_traits(source_system, created_at DESC);

CREATE TABLE IF NOT EXISTS event_facts (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uid VARCHAR(100) NOT NULL,
    organization_uid VARCHAR(100),
    event_type VARCHAR(100) NOT NULL,
    event_channel VARCHAR(50),
    event_source VARCHAR(50) NOT NULL,
    source_event_id VARCHAR(100),
    occurred_at TIMESTAMP NOT NULL,
    event_value NUMERIC,
    attributes JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS ai_decisions (
    ai_decision_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uid VARCHAR(100) NOT NULL,
    decision_type VARCHAR(100) NOT NULL,
    decision_name VARCHAR(100) NOT NULL,
    decision_value TEXT,
    confidence DECIMAL(5, 4),
    source_system VARCHAR(50) NOT NULL,
    source_content_hash VARCHAR(128),
    model_name VARCHAR(100),
    model_version VARCHAR(100),
    decided_at TIMESTAMP NOT NULL,
    explanation JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_decisions_uid
    ON ai_decisions(uid, decided_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_name
    ON ai_decisions(decision_name, decided_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_type
    ON ai_decisions(decision_type, decided_at DESC);
