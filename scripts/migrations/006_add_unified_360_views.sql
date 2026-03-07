-- Migration 006: Add Unified 360° Views for Cross-Source Identity
-- Date: 2026-03-07
-- Purpose: Create unified views combining KBO + Teamleader + Exact data for 360° customer insights
-- Note: These views enable queries like "What is the total pipeline value for software companies in Brussels?"

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ==========================================
-- 1. Unified Company 360° View
-- Combines KBO base data with CRM and Financial data
-- ==========================================
CREATE OR REPLACE VIEW unified_company_360 AS
SELECT 
    -- KBO/Base identity (from companies table)
    c.id::text as company_uid,
    c.kbo_number,
    c.vat_number,
    c.company_name as kbo_company_name,
    c.legal_form,
    c.industry_nace_code as nace_code,
    c.nace_description,
    c.status as kbo_status,
    c.juridical_situation,
    c.city as kbo_city,
    c.postal_code as kbo_postal_code,
    c.street_address as kbo_street,
    c.country_code,
    c.company_size,
    c.employee_count,
    c.establishment_count,
    c.founded_date,
    c.website_url,
    c.email_domain,
    c.geo_latitude,
    c.geo_longitude,
    
    -- Teamleader CRM data (if linked)
    tl.id::text as tl_company_id,
    tl.source_record_id as tl_source_id,
    tl.company_name as tl_company_name,
    tl.crm_status as tl_status,
    tl.customer_type as tl_customer_type,
    tl.main_email as tl_email,
    tl.main_phone as tl_phone,
    tl.city as tl_city,
    tl.lead_source as tl_lead_source,
    tl.last_sync_at as tl_last_sync,
    
    -- Exact Online data (if linked)
    ex.id::text as exact_customer_id,
    ex.source_record_id as exact_source_id,
    ex.company_name as exact_company_name,
    ex.status as exact_status,
    ex.credit_line as exact_credit_line,
    ex.payment_terms_days as exact_payment_terms,
    ex.is_blocked as exact_is_blocked,
    ex.account_manager as exact_account_manager,
    ex.main_email as exact_email,
    ex.city as exact_city,
    ex.last_sync_at as exact_last_sync,
    
    -- Identity linking status
    CASE 
        WHEN tl.id IS NOT NULL AND ex.id IS NOT NULL THEN 'linked_both'
        WHEN tl.id IS NOT NULL THEN 'linked_teamleader'
        WHEN ex.id IS NOT NULL THEN 'linked_exact'
        ELSE 'kbo_only'
    END as identity_link_status,
    
    -- Last update tracking
    GREATEST(
        c.updated_at,
        COALESCE(tl.last_sync_at, '1970-01-01'::timestamp),
        COALESCE(ex.last_sync_at, '1970-01-01'::timestamp)
    ) as last_updated_at

FROM companies c
LEFT JOIN crm_companies tl ON tl.kbo_number = c.kbo_number AND tl.source_system = 'teamleader'
LEFT JOIN exact_customers ex ON ex.kbo_number = c.kbo_number AND ex.source_system = 'exact'
WHERE c.kbo_number IS NOT NULL;

COMMENT ON VIEW unified_company_360 IS 'Unified 360° view combining KBO, Teamleader, and Exact data by KBO number';

-- Index on the view's key columns (via underlying tables)
CREATE INDEX IF NOT EXISTS idx_companies_kbo_lookup ON companies(kbo_number) WHERE kbo_number IS NOT NULL;

-- ==========================================
-- 2. Unified Pipeline & Revenue View
-- Combines CRM deals with Exact financial data
-- ==========================================
CREATE OR REPLACE VIEW unified_pipeline_revenue AS
SELECT 
    uc360.company_uid,
    uc360.kbo_number,
    uc360.kbo_company_name,
    uc360.nace_code,
    uc360.nace_description,
    uc360.kbo_city,
    uc360.kbo_status,
    
    -- Teamleader Pipeline
    COALESCE(tl_pipeline.open_deals_count, 0) as tl_open_deals,
    COALESCE(tl_pipeline.open_deals_value, 0) as tl_pipeline_value,
    COALESCE(tl_pipeline.won_deals_ytd, 0) as tl_won_deals_ytd,
    COALESCE(tl_pipeline.won_value_ytd, 0) as tl_won_value_ytd,
    
    -- Exact Financials
    COALESCE(ex_fin.revenue_ytd, 0) as exact_revenue_ytd,
    COALESCE(ex_fin.revenue_total, 0) as exact_revenue_total,
    COALESCE(ex_fin.outstanding_amount, 0) as exact_outstanding,
    COALESCE(ex_fin.overdue_amount, 0) as exact_overdue,
    COALESCE(ex_fin.open_invoices, 0) as exact_open_invoices,
    
    -- Combined metrics
    COALESCE(tl_pipeline.open_deals_value, 0) + COALESCE(ex_fin.outstanding_amount, 0) as total_exposure,
    CASE 
        WHEN COALESCE(ex_fin.revenue_ytd, 0) > 0 
        THEN ROUND((COALESCE(tl_pipeline.won_value_ytd, 0) / ex_fin.revenue_ytd) * 100, 2)
        ELSE NULL 
    END as crm_to_revenue_ratio,
    
    -- Data quality indicators
    CASE WHEN tl_pipeline.company_id IS NOT NULL THEN true ELSE false END as has_crm_data,
    CASE WHEN ex_fin.customer_id IS NOT NULL THEN true ELSE false END as has_financial_data

FROM unified_company_360 uc360
LEFT JOIN (
    -- Teamleader pipeline aggregation
    SELECT 
        tl.kbo_number,
        tl.id::text as company_id,
        COUNT(CASE WHEN d.deal_status = 'open' THEN 1 END) as open_deals_count,
        SUM(CASE WHEN d.deal_status = 'open' THEN d.deal_value ELSE 0 END) as open_deals_value,
        COUNT(CASE WHEN d.deal_status = 'won' AND d.actual_close_date >= DATE_TRUNC('year', CURRENT_DATE) THEN 1 END) as won_deals_ytd,
        SUM(CASE WHEN d.deal_status = 'won' AND d.actual_close_date >= DATE_TRUNC('year', CURRENT_DATE) THEN d.deal_value ELSE 0 END) as won_value_ytd
    FROM crm_companies tl
    LEFT JOIN crm_deals d ON d.crm_company_id = tl.id
    WHERE tl.source_system = 'teamleader'
    GROUP BY tl.kbo_number, tl.id
) tl_pipeline ON tl_pipeline.kbo_number = uc360.kbo_number
LEFT JOIN (
    -- Exact financial aggregation
    SELECT 
        ex.kbo_number,
        ex.id::text as customer_id,
        fs.revenue_ytd,
        fs.revenue_total,
        fs.outstanding_amount,
        fs.overdue_amount,
        fs.open_invoices
    FROM exact_customers ex
    LEFT JOIN exact_customer_financial_summary fs ON fs.customer_id = ex.id
    WHERE ex.source_system = 'exact'
) ex_fin ON ex_fin.kbo_number = uc360.kbo_number
WHERE uc360.kbo_number IS NOT NULL;

COMMENT ON VIEW unified_pipeline_revenue IS 'Combined pipeline and revenue view for sales analysis';

-- ==========================================
-- 3. Industry Pipeline Summary View
-- Answer: "What is the total pipeline value for software companies in Brussels?"
-- ==========================================
CREATE OR REPLACE VIEW industry_pipeline_summary AS
SELECT 
    CASE 
        WHEN nace_code LIKE '62%' THEN 'Software/IT Services'
        WHEN nace_code LIKE '63%' THEN 'Data Processing/Web'
        WHEN nace_code LIKE '56%' THEN 'Food & Beverage'
        WHEN nace_code LIKE '47%' THEN 'Retail'
        WHEN nace_code LIKE '41%' OR nace_code LIKE '42%' OR nace_code LIKE '43%' THEN 'Construction'
        WHEN nace_code LIKE '69%' THEN 'Legal/Accounting'
        WHEN nace_code LIKE '70%' THEN 'Headquarters/Management'
        WHEN nace_code LIKE '71%' THEN 'Architecture/Engineering'
        WHEN nace_code LIKE '72%' THEN 'R&D/Scientific'
        WHEN nace_code LIKE '73%' THEN 'Advertising/Market Research'
        WHEN nace_code LIKE '74%' THEN 'Other Professional Services'
        WHEN nace_code LIKE '86%' THEN 'Healthcare'
        ELSE 'Other'
    END as industry_category,
    nace_code,
    nace_description,
    kbo_city,
    
    COUNT(DISTINCT kbo_number) as company_count,
    SUM(tl_open_deals) as total_open_deals,
    SUM(tl_pipeline_value) as total_pipeline_value,
    SUM(tl_won_deals_ytd) as total_won_deals_ytd,
    SUM(tl_won_value_ytd) as total_won_value_ytd,
    SUM(exact_revenue_ytd) as total_revenue_ytd,
    SUM(exact_outstanding) as total_outstanding,
    SUM(exact_overdue) as total_overdue,
    SUM(total_exposure) as total_exposure

FROM unified_pipeline_revenue
WHERE kbo_number IS NOT NULL
GROUP BY 
    CASE 
        WHEN nace_code LIKE '62%' THEN 'Software/IT Services'
        WHEN nace_code LIKE '63%' THEN 'Data Processing/Web'
        WHEN nace_code LIKE '56%' THEN 'Food & Beverage'
        WHEN nace_code LIKE '47%' THEN 'Retail'
        WHEN nace_code LIKE '41%' OR nace_code LIKE '42%' OR nace_code LIKE '43%' THEN 'Construction'
        WHEN nace_code LIKE '69%' THEN 'Legal/Accounting'
        WHEN nace_code LIKE '70%' THEN 'Headquarters/Management'
        WHEN nace_code LIKE '71%' THEN 'Architecture/Engineering'
        WHEN nace_code LIKE '72%' THEN 'R&D/Scientific'
        WHEN nace_code LIKE '73%' THEN 'Advertising/Market Research'
        WHEN nace_code LIKE '74%' THEN 'Other Professional Services'
        WHEN nace_code LIKE '86%' THEN 'Healthcare'
        ELSE 'Other'
    END,
    nace_code,
    nace_description,
    kbo_city;

COMMENT ON VIEW industry_pipeline_summary IS 'Industry-level pipeline and revenue summary by city';

-- ==========================================
-- 4. Company Activity Timeline View
-- All activities across systems in chronological order
-- ==========================================
CREATE OR REPLACE VIEW company_activity_timeline AS

-- KBO events (enrichment, etc.)
SELECT 
    c.kbo_number,
    c.id::text as company_uid,
    c.company_name,
    'kbo_enrichment' as source_system,
    'data_update' as activity_type,
    'Company data enriched' as activity_description,
    c.updated_at as activity_date,
    jsonb_build_object(
        'website_url', c.website_url,
        'geo_latitude', c.geo_latitude,
        'ai_description', c.ai_description
    ) as activity_data
FROM companies c
WHERE c.kbo_number IS NOT NULL
  AND c.updated_at > c.created_at + INTERVAL '1 day'

UNION ALL

-- Teamleader activities
SELECT 
    tl.kbo_number,
    c.id::text as company_uid,
    c.company_name,
    'teamleader' as source_system,
    a.activity_type,
    COALESCE(a.activity_subject, a.activity_description) as activity_description,
    a.activity_date,
    jsonb_build_object(
        'activity_id', a.source_record_id,
        'completed', a.completed,
        'outcome', a.outcome
    ) as activity_data
FROM crm_activities a
JOIN crm_companies tl ON tl.id = a.crm_company_id AND tl.source_system = 'teamleader'
LEFT JOIN companies c ON c.kbo_number = tl.kbo_number
WHERE tl.kbo_number IS NOT NULL

UNION ALL

-- Teamleader deals
SELECT 
    tl.kbo_number,
    c.id::text as company_uid,
    c.company_name,
    'teamleader' as source_system,
    'deal_' || d.deal_status as activity_type,
    d.deal_title || ' (' || d.deal_value || ' ' || d.deal_currency || ')' as activity_description,
    COALESCE(d.actual_close_date, d.expected_close_date)::timestamp as activity_date,
    jsonb_build_object(
        'deal_id', d.source_record_id,
        'deal_value', d.deal_value,
        'deal_phase', d.deal_phase,
        'probability', d.probability
    ) as activity_data
FROM crm_deals d
JOIN crm_companies tl ON tl.id = d.crm_company_id AND tl.source_system = 'teamleader'
LEFT JOIN companies c ON c.kbo_number = tl.kbo_number
WHERE tl.kbo_number IS NOT NULL

UNION ALL

-- Exact invoices
SELECT 
    ex.kbo_number,
    c.id::text as company_uid,
    c.company_name,
    'exact' as source_system,
    'invoice_' || i.invoice_status as activity_type,
    'Invoice ' || i.invoice_number || ' (' || i.total_amount_incl || ' ' || i.currency || ')' as activity_description,
    i.invoice_date::timestamp as activity_date,
    jsonb_build_object(
        'invoice_id', i.source_record_id,
        'invoice_number', i.invoice_number,
        'amount', i.total_amount_incl,
        'status', i.invoice_status,
        'days_overdue', i.days_overdue
    ) as activity_data
FROM exact_sales_invoices i
JOIN exact_customers ex ON ex.id = i.crm_company_id OR ex.source_record_id = i.exact_customer_id
LEFT JOIN companies c ON c.kbo_number = ex.kbo_number
WHERE ex.kbo_number IS NOT NULL

ORDER BY activity_date DESC;

COMMENT ON VIEW company_activity_timeline IS 'Chronological activity feed across all systems';

-- ==========================================
-- 5. Identity Link Quality View
-- Monitor KBO matching accuracy and coverage
-- ==========================================
CREATE OR REPLACE VIEW identity_link_quality AS
SELECT 
    'teamleader' as source_system,
    COUNT(*) as total_records,
    COUNT(kbo_number) as with_kbo_number,
    COUNT(organization_uid) as with_org_uid,
    COUNT(*) FILTER (WHERE kbo_number IS NOT NULL) as matched_by_kbo,
    COUNT(*) FILTER (WHERE kbo_number IS NULL AND organization_uid IS NULL) as unmatched,
    ROUND(100.0 * COUNT(kbo_number) / NULLIF(COUNT(*), 0), 2) as match_rate_pct,
    MIN(last_sync_at) as oldest_sync,
    MAX(last_sync_at) as newest_sync
FROM crm_companies
WHERE source_system = 'teamleader'

UNION ALL

SELECT 
    'exact' as source_system,
    COUNT(*) as total_records,
    COUNT(kbo_number) as with_kbo_number,
    COUNT(organization_uid) as with_org_uid,
    COUNT(*) FILTER (WHERE kbo_number IS NOT NULL) as matched_by_kbo,
    COUNT(*) FILTER (WHERE kbo_number IS NULL AND organization_uid IS NULL) as unmatched,
    ROUND(100.0 * COUNT(kbo_number) / NULLIF(COUNT(*), 0), 2) as match_rate_pct,
    MIN(last_sync_at) as oldest_sync,
    MAX(last_sync_at) as newest_sync
FROM exact_customers
WHERE source_system = 'exact';

COMMENT ON VIEW identity_link_quality IS 'Monitor identity matching coverage and quality';

-- ==========================================
-- 6. High-Value Account View
-- Identify accounts with significant exposure/opportunity
-- ==========================================
CREATE OR REPLACE VIEW high_value_accounts AS
SELECT 
    upr.*,
    uc360.tl_customer_type,
    uc360.tl_lead_source,
    uc360.exact_credit_line,
    uc360.exact_payment_terms,
    uc360.exact_account_manager,
    uc360.identity_link_status,
    
    -- Risk/Value scoring
    CASE 
        WHEN exact_overdue > 10000 THEN 'high_risk'
        WHEN exact_overdue > 0 THEN 'medium_risk'
        WHEN tl_pipeline_value > 50000 THEN 'high_opportunity'
        WHEN tl_pipeline_value > 10000 THEN 'medium_opportunity'
        WHEN exact_revenue_ytd > 100000 THEN 'high_value'
        ELSE 'standard'
    END as account_priority,
    
    -- Data completeness score
    (
        CASE WHEN uc360.tl_company_name IS NOT NULL THEN 25 ELSE 0 END +
        CASE WHEN uc360.exact_company_name IS NOT NULL THEN 25 ELSE 0 END +
        CASE WHEN uc360.kbo_city IS NOT NULL THEN 25 ELSE 0 END +
        CASE WHEN uc360.website_url IS NOT NULL THEN 25 ELSE 0 END
    ) as data_completeness_score

FROM unified_pipeline_revenue upr
JOIN unified_company_360 uc360 ON uc360.kbo_number = upr.kbo_number
WHERE 
    -- Filter for companies with meaningful data
    (upr.tl_pipeline_value > 0 OR upr.exact_revenue_ytd > 0 OR upr.exact_outstanding > 0)
    OR upr.has_crm_data = true 
    OR upr.has_financial_data = true
ORDER BY 
    upr.total_exposure DESC,
    upr.exact_revenue_ytd DESC NULLS LAST;

COMMENT ON VIEW high_value_accounts IS 'Prioritized accounts with revenue, pipeline, or risk indicators';

-- ==========================================
-- 7. Geographic Revenue Distribution View
-- Revenue and pipeline by location
-- ==========================================
CREATE OR REPLACE VIEW geographic_revenue_distribution AS
SELECT 
    COALESCE(kbo_city, 'Unknown') as city,
    COALESCE(province, 'Unknown') as province,
    
    COUNT(DISTINCT kbo_number) as total_companies,
    COUNT(DISTINCT CASE WHEN has_crm_data THEN kbo_number END) as companies_with_crm,
    COUNT(DISTINCT CASE WHEN has_financial_data THEN kbo_number END) as companies_with_financials,
    
    SUM(tl_pipeline_value) as total_pipeline,
    SUM(tl_won_value_ytd) as total_closed_won_ytd,
    SUM(exact_revenue_ytd) as total_revenue_ytd,
    SUM(exact_outstanding) as total_outstanding,
    SUM(exact_overdue) as total_overdue,
    
    -- Average metrics
    ROUND(AVG(tl_pipeline_value) FILTER (WHERE tl_pipeline_value > 0), 2) as avg_pipeline_value,
    ROUND(AVG(exact_revenue_ytd) FILTER (WHERE exact_revenue_ytd > 0), 2) as avg_revenue_ytd,
    
    -- Market penetration indicator
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN has_crm_data OR has_financial_data THEN kbo_number END) / 
        NULLIF(COUNT(DISTINCT kbo_number), 0), 2) as market_penetration_pct

FROM unified_pipeline_revenue upr
LEFT JOIN companies c ON c.kbo_number = upr.kbo_number
GROUP BY COALESCE(kbo_city, 'Unknown'), COALESCE(province, 'Unknown')
ORDER BY total_revenue_ytd DESC NULLS LAST, total_pipeline DESC NULLS LAST;

COMMENT ON VIEW geographic_revenue_distribution IS 'Revenue and pipeline distribution by geography';

-- ==========================================
-- Sample Queries Documentation
-- ==========================================
COMMENT ON VIEW unified_company_360 IS 
'Sample queries:
-- Find all software companies in Brussels with deals over 10k:
SELECT * FROM unified_company_360 
WHERE nace_code LIKE ''62%'' AND kbo_city ILIKE ''brussel%''
AND company_uid IN (SELECT company_uid FROM unified_pipeline_revenue WHERE tl_pipeline_value > 10000);

-- Show 360° view for a specific company:
SELECT * FROM unified_company_360 WHERE kbo_number = ''0123.456.789'';
';

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
    'unified_company_360',
    'unified_pipeline_revenue',
    'industry_pipeline_summary',
    'company_activity_timeline',
    'identity_link_quality',
    'high_value_accounts',
    'geographic_revenue_distribution',
    'exact_customer_financial_summary'
)
ORDER BY viewname;
