-- Minimal local-development schema for the PostgreSQL query plane.
-- Keep this focused on what the chatbot runtime actually needs to boot and query.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "postgis";

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kbo_number VARCHAR(20) UNIQUE,
    vat_number VARCHAR(20),
    company_name VARCHAR(500) NOT NULL,
    legal_form VARCHAR(100),
    legal_form_code VARCHAR(10),
    juridical_situation VARCHAR(50),
    status VARCHAR(20),
    street_address TEXT,
    city VARCHAR(200),
    postal_code VARCHAR(20),
    country VARCHAR(2) DEFAULT 'BE',
    geo_latitude DECIMAL(10, 8),
    geo_longitude DECIMAL(11, 8),
    industry_nace_code VARCHAR(10),
    industry_description VARCHAR(500),
    nace_code VARCHAR(10),
    nace_description TEXT,
    nace_descriptions TEXT[],
    company_size VARCHAR(50),
    employee_count INTEGER,
    annual_revenue DECIMAL(15, 2),
    revenue_range VARCHAR(50),
    founded_date DATE,
    founding_year INTEGER,
    type_of_enterprise VARCHAR(20),
    website_url VARCHAR(500),
    main_phone VARCHAR(50),
    main_fax VARCHAR(50),
    main_email VARCHAR(255),
    ai_description TEXT,
    ai_description_generated_at TIMESTAMP,
    enrichment_data JSONB,
    cbe_data JSONB,
    source VARCHAR(100),
    source_system VARCHAR(50),
    source_id VARCHAR(100),
    source_created_at TIMESTAMP,
    source_updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(20) DEFAULT 'pending',
    all_names TEXT[],
    all_nace_codes VARCHAR(10)[],
    engagement_score INTEGER DEFAULT 0,
    lead_score INTEGER,
    churn_risk VARCHAR(20),
    segment_tags TEXT[] DEFAULT '{}',
    establishment_count INTEGER DEFAULT 0,
    data_processing_basis VARCHAR(50),
    data_retention_until DATE,
    email_bounce_count INTEGER DEFAULT 0,
    phone_validation_status VARCHAR(50),
    contact_validated BOOLEAN DEFAULT FALSE,
    contact_validated_at TIMESTAMP,
    workforce_range VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_companies_kbo ON companies(kbo_number);
CREATE INDEX IF NOT EXISTS idx_companies_vat ON companies(vat_number);
CREATE INDEX IF NOT EXISTS idx_companies_name_trgm
    ON companies USING GIN (company_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_companies_nace
    ON companies(industry_nace_code)
    WHERE industry_nace_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_city
    ON companies(city)
    WHERE city IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_city_status_real
    ON companies(city, status)
    WHERE city IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_city_nace
    ON companies(city, industry_nace_code)
    WHERE city IS NOT NULL AND industry_nace_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_sync_status
    ON companies(sync_status)
    WHERE sync_status IN ('pending', 'enriching', 'error', 'enriched', 'needs_enrichment');
CREATE INDEX IF NOT EXISTS idx_companies_last_sync ON companies(last_sync_at);
CREATE INDEX IF NOT EXISTS idx_companies_created_at ON companies(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_companies_updated_at ON companies(updated_at DESC);
