-- Migration 007: Add Autotask to Unified 360 Views
-- Date: 2026-03-08
-- Purpose: Extend the unified 360 model with Autotask support/ticket data linked by KBO

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==========================================
-- 1. Autotask schema alignment
-- ==========================================
ALTER TABLE IF EXISTS autotask_companies
    ADD COLUMN IF NOT EXISTS vat_number VARCHAR(20),
    ADD COLUMN IF NOT EXISTS kbo_number VARCHAR(20),
    ADD COLUMN IF NOT EXISTS organization_uid VARCHAR(100),
    ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS raw_data JSONB;

CREATE INDEX IF NOT EXISTS idx_autotask_companies_vat_number
    ON autotask_companies(vat_number)
    WHERE vat_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_autotask_companies_kbo_number
    ON autotask_companies(kbo_number)
    WHERE kbo_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_autotask_companies_org_uid
    ON autotask_companies(organization_uid)
    WHERE organization_uid IS NOT NULL;

UPDATE autotask_companies
SET
    vat_number = COALESCE(
        vat_number,
        CASE
            WHEN upper(tax_id) LIKE 'BE%' THEN regexp_replace(upper(tax_id), '[^A-Z0-9]', '', 'g')
            ELSE NULL
        END
    ),
    kbo_number = COALESCE(
        kbo_number,
        CASE
            WHEN upper(tax_id) LIKE 'BE%'
                 AND length(regexp_replace(upper(tax_id), '[^0-9]', '', 'g')) = 10
            THEN regexp_replace(upper(tax_id), '[^0-9]', '', 'g')
            ELSE NULL
        END
    )
WHERE tax_id IS NOT NULL;

UPDATE autotask_companies ac
SET organization_uid = c.id::text
FROM companies c
WHERE ac.organization_uid IS NULL
  AND ac.kbo_number = c.kbo_number;

INSERT INTO source_identity_links (
    uid,
    subject_type,
    source_system,
    source_entity_type,
    source_record_id,
    is_primary
)
SELECT
    COALESCE(ac.organization_uid, c.id::text) AS uid,
    'company' AS subject_type,
    'autotask' AS source_system,
    'company' AS source_entity_type,
    ac.id AS source_record_id,
    false AS is_primary
FROM autotask_companies ac
JOIN companies c ON c.kbo_number = ac.kbo_number
WHERE ac.kbo_number IS NOT NULL
ON CONFLICT (source_system, source_entity_type, source_record_id)
DO UPDATE SET
    uid = EXCLUDED.uid;

-- ==========================================
-- 2. Autotask support summary helper view
-- ==========================================
CREATE OR REPLACE VIEW autotask_company_support_summary AS
WITH ticket_summary AS (
    SELECT
        company_id,
        COUNT(*) AS total_tickets,
        COUNT(*) FILTER (
            WHERE lower(COALESCE(status, '')) NOT IN ('completed', 'closed', 'resolved', 'cancelled')
        ) AS open_tickets,
        MAX(COALESCE(last_modified_date, create_date)) AS last_ticket_at
    FROM autotask_tickets
    GROUP BY company_id
),
contract_summary AS (
    SELECT
        company_id,
        COUNT(*) AS total_contracts,
        COUNT(*) FILTER (
            WHERE lower(COALESCE(status, '')) = 'active'
        ) AS active_contracts,
        COALESCE(SUM(contract_value), 0) AS total_contract_value,
        MAX(start_date) AS last_contract_start
    FROM autotask_contracts
    GROUP BY company_id
)
SELECT
    ac.id AS autotask_company_id,
    ac.kbo_number,
    ac.name AS autotask_company_name,
    ac.company_type AS autotask_company_type,
    ac.phone AS autotask_phone,
    ac.web_address AS autotask_website,
    ac.city AS autotask_city,
    COALESCE(ts.total_tickets, 0) AS autotask_total_tickets,
    COALESCE(ts.open_tickets, 0) AS autotask_open_tickets,
    ts.last_ticket_at AS autotask_last_ticket_at,
    COALESCE(cs.total_contracts, 0) AS autotask_total_contracts,
    COALESCE(cs.active_contracts, 0) AS autotask_active_contracts,
    COALESCE(cs.total_contract_value, 0) AS autotask_total_contract_value,
    cs.last_contract_start AS autotask_last_contract_start,
    ac.last_sync_at AS autotask_last_sync_at
FROM autotask_companies ac
LEFT JOIN ticket_summary ts ON ts.company_id = ac.id
LEFT JOIN contract_summary cs ON cs.company_id = ac.id
WHERE ac.kbo_number IS NOT NULL;

COMMENT ON VIEW autotask_company_support_summary IS 'Autotask ticket and contract summary by KBO-linked company';

-- ==========================================
-- 3. Unified company 360 view with Autotask
-- ==========================================
CREATE OR REPLACE VIEW unified_company_360 AS
SELECT
    -- KBO/Base identity (from companies table)
    c.id::text AS company_uid,
    c.kbo_number,
    c.vat_number,
    c.company_name AS kbo_company_name,
    c.legal_form,
    c.industry_nace_code AS nace_code,
    c.nace_description,
    c.status AS kbo_status,
    c.juridical_situation,
    c.city AS kbo_city,
    c.postal_code AS kbo_postal_code,
    c.street_address AS kbo_street,
    c.country AS country_code,
    c.company_size,
    c.employee_count,
    c.establishment_count,
    c.founded_date,
    c.website_url,
    CASE
        WHEN c.main_email IS NOT NULL AND c.main_email LIKE '%@%'
        THEN split_part(c.main_email, '@', 2)
        ELSE NULL
    END AS email_domain,
    c.geo_latitude,
    c.geo_longitude,

    -- Teamleader CRM data (if linked)
    tl.id::text AS tl_company_id,
    tl.source_record_id AS tl_source_id,
    tl.company_name AS tl_company_name,
    tl.crm_status AS tl_status,
    tl.customer_type AS tl_customer_type,
    tl.main_email AS tl_email,
    tl.main_phone AS tl_phone,
    tl.city AS tl_city,
    tl.lead_source AS tl_lead_source,
    tl.last_sync_at AS tl_last_sync,

    -- Exact Online data (if linked)
    ex.id::text AS exact_customer_id,
    ex.source_record_id AS exact_source_id,
    ex.company_name AS exact_company_name,
    ex.status AS exact_status,
    ex.credit_line AS exact_credit_line,
    ex.payment_terms_days AS exact_payment_terms,
    ex.is_blocked AS exact_is_blocked,
    ex.account_manager AS exact_account_manager,
    ex.main_email AS exact_email,
    ex.city AS exact_city,
    ex.last_sync_at AS exact_last_sync,

    -- Identity linking status
    CASE
        WHEN tl.id IS NOT NULL AND ex.id IS NOT NULL AND at.autotask_company_id IS NOT NULL THEN 'linked_all'
        WHEN tl.id IS NOT NULL AND ex.id IS NOT NULL THEN 'linked_both'
        WHEN tl.id IS NOT NULL AND at.autotask_company_id IS NOT NULL THEN 'linked_teamleader_autotask'
        WHEN ex.id IS NOT NULL AND at.autotask_company_id IS NOT NULL THEN 'linked_exact_autotask'
        WHEN tl.id IS NOT NULL THEN 'linked_teamleader'
        WHEN ex.id IS NOT NULL THEN 'linked_exact'
        WHEN at.autotask_company_id IS NOT NULL THEN 'linked_autotask'
        ELSE 'kbo_only'
    END AS identity_link_status,

    -- Last update tracking
    GREATEST(
        c.updated_at,
        COALESCE(tl.last_sync_at, '1970-01-01'::timestamp),
        COALESCE(ex.last_sync_at, '1970-01-01'::timestamp),
        COALESCE(at.autotask_last_sync_at, '1970-01-01'::timestamp)
    ) AS last_updated_at,

    -- Autotask support data
    at.autotask_company_id,
    at.autotask_company_name,
    at.autotask_company_type,
    at.autotask_phone,
    at.autotask_website,
    at.autotask_city,
    at.autotask_total_tickets,
    at.autotask_open_tickets,
    at.autotask_last_ticket_at,
    at.autotask_total_contracts,
    at.autotask_active_contracts,
    at.autotask_total_contract_value,
    at.autotask_last_contract_start,

    -- Source coverage flags
    CASE WHEN tl.id IS NOT NULL THEN true ELSE false END AS has_teamleader,
    CASE WHEN ex.id IS NOT NULL THEN true ELSE false END AS has_exact,
    CASE WHEN at.autotask_company_id IS NOT NULL THEN true ELSE false END AS has_autotask,
    1
        + CASE WHEN tl.id IS NOT NULL THEN 1 ELSE 0 END
        + CASE WHEN ex.id IS NOT NULL THEN 1 ELSE 0 END
        + CASE WHEN at.autotask_company_id IS NOT NULL THEN 1 ELSE 0 END
        AS total_source_count

FROM companies c
LEFT JOIN crm_companies tl
    ON tl.kbo_number = c.kbo_number
   AND tl.source_system = 'teamleader'
LEFT JOIN exact_customers ex
    ON ex.kbo_number = c.kbo_number
   AND ex.source_system = 'exact'
LEFT JOIN autotask_company_support_summary at
    ON at.kbo_number = c.kbo_number
WHERE c.kbo_number IS NOT NULL;

COMMENT ON VIEW unified_company_360 IS 'Unified 360° view combining KBO, Teamleader, Exact, and Autotask data by KBO number';

-- ==========================================
-- 4. Company activity timeline with Autotask
-- ==========================================
CREATE OR REPLACE VIEW company_activity_timeline AS

-- KBO events (enrichment, etc.)
SELECT
    c.kbo_number,
    c.id::text AS company_uid,
    c.company_name,
    'kbo_enrichment' AS source_system,
    'data_update' AS activity_type,
    'Company data enriched' AS activity_description,
    c.updated_at AS activity_date,
    jsonb_build_object(
        'website_url', c.website_url,
        'geo_latitude', c.geo_latitude,
        'ai_description', c.ai_description
    ) AS activity_data
FROM companies c
WHERE c.kbo_number IS NOT NULL
  AND c.updated_at > c.created_at + INTERVAL '1 day'

UNION ALL

-- Teamleader activities
SELECT
    tl.kbo_number,
    c.id::text AS company_uid,
    c.company_name,
    'teamleader' AS source_system,
    a.activity_type,
    COALESCE(a.activity_subject, a.activity_description) AS activity_description,
    a.activity_date,
    jsonb_build_object(
        'activity_id', a.source_record_id,
        'completed', a.completed,
        'outcome', a.outcome
    ) AS activity_data
FROM crm_activities a
JOIN crm_companies tl
    ON tl.id = a.crm_company_id
   AND tl.source_system = 'teamleader'
LEFT JOIN companies c ON c.kbo_number = tl.kbo_number
WHERE tl.kbo_number IS NOT NULL

UNION ALL

-- Teamleader deals
SELECT
    tl.kbo_number,
    c.id::text AS company_uid,
    c.company_name,
    'teamleader' AS source_system,
    'deal_' || d.deal_status AS activity_type,
    d.deal_title || ' (' || d.deal_value || ' ' || d.deal_currency || ')' AS activity_description,
    COALESCE(d.actual_close_date, d.expected_close_date)::timestamp AS activity_date,
    jsonb_build_object(
        'deal_id', d.source_record_id,
        'deal_value', d.deal_value,
        'deal_phase', d.deal_phase,
        'probability', d.probability
    ) AS activity_data
FROM crm_deals d
JOIN crm_companies tl
    ON tl.id = d.crm_company_id
   AND tl.source_system = 'teamleader'
LEFT JOIN companies c ON c.kbo_number = tl.kbo_number
WHERE tl.kbo_number IS NOT NULL

UNION ALL

-- Exact invoices
SELECT
    ex.kbo_number,
    c.id::text AS company_uid,
    c.company_name,
    'exact' AS source_system,
    'invoice_' || i.invoice_status AS activity_type,
    'Invoice ' || i.invoice_number || ' (' || i.total_amount_incl || ' ' || i.currency || ')' AS activity_description,
    i.invoice_date::timestamp AS activity_date,
    jsonb_build_object(
        'invoice_id', i.source_record_id,
        'invoice_number', i.invoice_number,
        'amount', i.total_amount_incl,
        'status', i.invoice_status,
        'days_overdue', i.days_overdue
    ) AS activity_data
FROM exact_sales_invoices i
JOIN exact_customers ex
    ON ex.id = i.crm_company_id
    OR ex.source_record_id = i.exact_customer_id
LEFT JOIN companies c ON c.kbo_number = ex.kbo_number
WHERE ex.kbo_number IS NOT NULL

UNION ALL

-- Autotask tickets
SELECT
    ac.kbo_number,
    c.id::text AS company_uid,
    c.company_name,
    'autotask' AS source_system,
    'ticket_' || lower(COALESCE(t.status, 'unknown')) AS activity_type,
    t.title AS activity_description,
    COALESCE(t.last_modified_date, t.create_date) AS activity_date,
    jsonb_build_object(
        'ticket_id', t.id,
        'priority', t.priority,
        'status', t.status,
        'queue_id', t.queue_id
    ) AS activity_data
FROM autotask_tickets t
JOIN autotask_companies ac ON ac.id = t.company_id
LEFT JOIN companies c ON c.kbo_number = ac.kbo_number
WHERE ac.kbo_number IS NOT NULL

UNION ALL

-- Autotask contracts
SELECT
    ac.kbo_number,
    c.id::text AS company_uid,
    c.company_name,
    'autotask' AS source_system,
    'contract_' || lower(COALESCE(ct.status, 'unknown')) AS activity_type,
    ct.contract_name || ' (' || ct.contract_value || ' EUR)' AS activity_description,
    COALESCE(ct.start_date, ct.end_date) AS activity_date,
    jsonb_build_object(
        'contract_id', ct.id,
        'status', ct.status,
        'contract_value', ct.contract_value,
        'contract_type', ct.contract_type
    ) AS activity_data
FROM autotask_contracts ct
JOIN autotask_companies ac ON ac.id = ct.company_id
LEFT JOIN companies c ON c.kbo_number = ac.kbo_number
WHERE ac.kbo_number IS NOT NULL

ORDER BY activity_date DESC;

COMMENT ON VIEW company_activity_timeline IS 'Chronological activity feed across KBO, Teamleader, Exact, and Autotask';

-- ==========================================
-- 5. Identity link quality including Autotask
-- ==========================================
CREATE OR REPLACE VIEW identity_link_quality AS
SELECT
    'teamleader' AS source_system,
    COUNT(*) AS total_records,
    COUNT(kbo_number) AS with_kbo_number,
    COUNT(organization_uid) AS with_org_uid,
    COUNT(*) FILTER (WHERE kbo_number IS NOT NULL) AS matched_by_kbo,
    COUNT(*) FILTER (WHERE kbo_number IS NULL AND organization_uid IS NULL) AS unmatched,
    ROUND(100.0 * COUNT(kbo_number) / NULLIF(COUNT(*), 0), 2) AS match_rate_pct,
    MIN(last_sync_at) AS oldest_sync,
    MAX(last_sync_at) AS newest_sync
FROM crm_companies
WHERE source_system = 'teamleader'

UNION ALL

SELECT
    'exact' AS source_system,
    COUNT(*) AS total_records,
    COUNT(kbo_number) AS with_kbo_number,
    COUNT(organization_uid) AS with_org_uid,
    COUNT(*) FILTER (WHERE kbo_number IS NOT NULL) AS matched_by_kbo,
    COUNT(*) FILTER (WHERE kbo_number IS NULL AND organization_uid IS NULL) AS unmatched,
    ROUND(100.0 * COUNT(kbo_number) / NULLIF(COUNT(*), 0), 2) AS match_rate_pct,
    MIN(last_sync_at) AS oldest_sync,
    MAX(last_sync_at) AS newest_sync
FROM exact_customers
WHERE source_system = 'exact'

UNION ALL

SELECT
    'autotask' AS source_system,
    COUNT(*) AS total_records,
    COUNT(kbo_number) AS with_kbo_number,
    COUNT(organization_uid) AS with_org_uid,
    COUNT(*) FILTER (WHERE kbo_number IS NOT NULL) AS matched_by_kbo,
    COUNT(*) FILTER (WHERE kbo_number IS NULL AND organization_uid IS NULL) AS unmatched,
    ROUND(100.0 * COUNT(kbo_number) / NULLIF(COUNT(*), 0), 2) AS match_rate_pct,
    MIN(last_sync_at) AS oldest_sync,
    MAX(last_sync_at) AS newest_sync
FROM autotask_companies;

COMMENT ON VIEW identity_link_quality IS 'Monitor Teamleader, Exact, and Autotask identity matching coverage and quality';

-- ==========================================
-- Migration verification
-- ==========================================
SELECT
    schemaname,
    viewname,
    viewowner
FROM pg_views
WHERE schemaname = 'public'
  AND viewname IN (
      'autotask_company_support_summary',
      'unified_company_360',
      'company_activity_timeline',
      'identity_link_quality'
  )
ORDER BY viewname;
