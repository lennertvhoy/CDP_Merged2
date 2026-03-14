-- Migration 008: Privacy Boundary Fix
-- Date: 2026-03-14
-- Purpose: Migrate existing company_engagement data to use email_hash instead of raw email
--          and sanitize event_data JSONB to remove PII

-- ==========================================
-- Step 1: Add email_hash column if it doesn't exist
-- ==========================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'company_engagement' 
        AND column_name = 'email_hash'
    ) THEN
        ALTER TABLE company_engagement ADD COLUMN email_hash VARCHAR(64);
    END IF;
END $$;

-- ==========================================
-- Step 2: Migrate existing email data to hashed version
-- Only hash emails that look valid (contain @)
-- ==========================================
UPDATE company_engagement
SET email_hash = encode(digest(lower(trim(email)), 'sha256'), 'hex')
WHERE email IS NOT NULL 
  AND email != ''
  AND email LIKE '%@%'
  AND (email_hash IS NULL OR email_hash = '');

-- ==========================================
-- Step 3: Create index on email_hash for lookups
-- ==========================================
CREATE INDEX IF NOT EXISTS idx_company_engagement_email_hash 
ON company_engagement(email_hash) 
WHERE email_hash IS NOT NULL;

-- ==========================================
-- Step 4: Sanitize existing event_data
-- This removes raw emails and subjects from JSONB while preserving hashes and metadata
-- ==========================================

-- Update event_data to remove raw emails but keep hashed versions
UPDATE company_engagement
SET event_data = jsonb_strip_nulls(jsonb_build_object(
    'email_id', event_data->>'email_id',
    'recipient_hash', encode(digest(lower(trim(event_data->>'to')), 'sha256'), 'hex'),
    'recipient_domain', split_part(lower(trim(event_data->>'to')), '@', 2),
    'sender_domain', split_part(lower(trim(event_data->>'from')), '@', 2),
    'subject_hash', encode(digest(lower(trim(event_data->>'subject')), 'sha256'), 'hex'),
    'timestamp', COALESCE(event_data->>'created_at', event_data->>'timestamp'),
    'click_domain', CASE 
        WHEN event_data->'click'->>'link' IS NOT NULL 
        THEN split_part(split_part(event_data->'click'->>'link', '://', 2), '/', 1)
        WHEN event_data->>'click' IS NOT NULL 
        THEN split_part(split_part(event_data->>'click', '://', 2), '/', 1)
        ELSE NULL 
    END,
    'user_agent', event_data->>'user_agent',
    'kbo_number', event_data->>'kbo_number',
    'metadata', event_data->'metadata'
))
WHERE event_data IS NOT NULL
  AND (event_data->>'to' IS NOT NULL OR event_data->>'from' IS NOT NULL);

-- ==========================================
-- Step 5: Drop the old email column (after migration is verified)
-- Uncomment after confirming migration works correctly
-- ==========================================
-- ALTER TABLE company_engagement DROP COLUMN IF EXISTS email;

-- ==========================================
-- Migration verification query
-- ==========================================
-- Run these to verify the migration:

-- Check that email_hash is populated for rows that had emails:
-- SELECT 
--     COUNT(*) as total_rows,
--     COUNT(email_hash) as with_hash,
--     COUNT(email) as with_raw_email
-- FROM company_engagement;

-- Verify no raw emails in event_data:
-- SELECT COUNT(*) 
-- FROM company_engagement 
-- WHERE event_data::text LIKE '%@%.%'  -- Simple check for email patterns
--   AND event_data->>'recipient_domain' IS NULL;  -- Excludes already-sanitized

-- Sample of sanitized event_data:
-- SELECT event_data 
-- FROM company_engagement 
-- WHERE event_data IS NOT NULL 
-- LIMIT 5;
