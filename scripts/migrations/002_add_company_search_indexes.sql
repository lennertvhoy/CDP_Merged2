-- Migration: Add Performance Indexes for Company Search Queries
-- Date: 2026-03-04
-- Purpose: Speed up chatbot search queries that were taking ~30 seconds

-- ==========================================
-- Critical Indexes for Chatbot Query Performance
-- ==========================================

-- City filter (most common filter in chatbot queries)
-- Before: ~30 seconds for "companies in Gent" (29,931 results)
-- After: Expected <1 second with index
CREATE INDEX IF NOT EXISTS idx_companies_city ON companies(city) 
    WHERE city IS NOT NULL;

-- NACE code filter (industry/category searches)
CREATE INDEX IF NOT EXISTS idx_companies_nace ON companies(industry_nace_code) 
    WHERE industry_nace_code IS NOT NULL;

-- Primary KBO lookup (company detail views)
CREATE INDEX IF NOT EXISTS idx_companies_kbo ON companies(kbo_number);

-- Status filter for enrichment queries
CREATE INDEX IF NOT EXISTS idx_companies_sync_status ON companies(sync_status) 
    WHERE sync_status IN ('pending', 'enriching', 'error', 'enriched');

-- Composite index for common search patterns (city + status)
CREATE INDEX IF NOT EXISTS idx_companies_city_status ON companies(city, sync_status) 
    WHERE city IS NOT NULL;

-- Composite index for industry + location queries
CREATE INDEX IF NOT EXISTS idx_companies_nace_city ON companies(industry_nace_code, city) 
    WHERE industry_nace_code IS NOT NULL AND city IS NOT NULL;

-- Text search for company name (fuzzy matching with trigrams)
CREATE INDEX IF NOT EXISTS idx_companies_name_trgm ON companies 
    USING GIN(company_name gin_trgm_ops);

-- ==========================================
-- Verification Queries (run after migration)
-- ==========================================
-- Check index sizes:
-- SELECT schemaname, tablename, indexname, pg_size_pretty(pg_relation_size(indexrelid)) 
-- FROM pg_stat_user_indexes 
-- WHERE tablename = 'companies' 
-- ORDER BY pg_relation_size(indexrelid) DESC;

-- Test query performance:
-- EXPLAIN ANALYZE SELECT COUNT(*) FROM companies WHERE city = 'Gent';
