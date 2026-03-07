-- Migration 005: Add Exact Online Financial Tables
-- Date: 2026-03-07
-- Purpose: Store financial data from Exact Online (accounts, GL accounts, invoices, transactions)
-- Note: Financial data enables 360° customer view with revenue, payment behavior, and credit insights

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==========================================
-- 1. Exact Accounts Table (Chart of Accounts)
-- General ledger accounts from Exact
-- ==========================================
CREATE TABLE IF NOT EXISTS exact_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source identification
    source_system VARCHAR(50) NOT NULL DEFAULT 'exact',
    source_record_id VARCHAR(100) NOT NULL, -- Exact GL Account ID (guid)
    
    -- Account info
    account_code VARCHAR(50) NOT NULL, -- Account number/code (e.g., "1300")
    account_name VARCHAR(500) NOT NULL,
    account_type VARCHAR(100), -- Assets, Liabilities, Equity, Income, Expenses
    account_classification VARCHAR(100), -- Detailed classification
    
    -- Financial properties
    is_active BOOLEAN DEFAULT TRUE,
    is_tax_relevant BOOLEAN DEFAULT FALSE,
    tax_code VARCHAR(50),
    
    -- Reporting
    reporting_code VARCHAR(100),
    reporting_description TEXT,
    
    -- Parent/child hierarchy
    parent_account_id VARCHAR(100),
    
    -- Sync tracking
    source_created_at TIMESTAMP,
    source_updated_at TIMESTAMP,
    last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_version INTEGER DEFAULT 1,
    
    -- Raw data
    raw_data JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(source_system, source_record_id),
    UNIQUE(source_system, account_code)
);

CREATE INDEX IF NOT EXISTS idx_exact_accounts_source ON exact_accounts(source_system, source_record_id);
CREATE INDEX IF NOT EXISTS idx_exact_accounts_code ON exact_accounts(account_code);
CREATE INDEX IF NOT EXISTS idx_exact_accounts_type ON exact_accounts(account_type);
CREATE INDEX IF NOT EXISTS idx_exact_accounts_active ON exact_accounts(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_exact_accounts_sync ON exact_accounts(last_sync_at);

COMMENT ON TABLE exact_accounts IS 'Exact Online general ledger (GL) accounts - chart of accounts';

-- ==========================================
-- 2. Exact Customers Table
-- Customer records from Exact (linked to GL accounts)
-- ==========================================
CREATE TABLE IF NOT EXISTS exact_customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source identification
    source_system VARCHAR(50) NOT NULL DEFAULT 'exact',
    source_record_id VARCHAR(100) NOT NULL, -- Exact Account ID (guid)
    
    -- Identity linking (to KBO/organizations)
    kbo_number VARCHAR(20),
    vat_number VARCHAR(20),
    organization_uid VARCHAR(100),
    
    -- Link to GL account
    exact_gl_account_id VARCHAR(100) REFERENCES exact_accounts(source_record_id),
    
    -- Company info
    company_name VARCHAR(500) NOT NULL,
    legal_name VARCHAR(500),
    
    -- Address
    street_address TEXT,
    city VARCHAR(200),
    postal_code VARCHAR(20),
    country VARCHAR(2) DEFAULT 'BE',
    
    -- Contact info
    main_email VARCHAR(255),
    email_domain VARCHAR(100),
    main_phone VARCHAR(50),
    website_url VARCHAR(500),
    
    -- Financial status
    credit_line DECIMAL(15, 2),
    discount_percentage DECIMAL(5, 2),
    
    -- Payment terms
    payment_terms_days INTEGER,
    payment_terms_type VARCHAR(50), -- AfterInvoice, AfterDelivery, etc.
    
    -- Tax
    vat_number_exact VARCHAR(50),
    vat_liable VARCHAR(50),
    
    -- Status
    status VARCHAR(50) DEFAULT 'C', -- C = Customer, S = Supplier, A = Both
    is_blocked BOOLEAN DEFAULT FALSE,
    block_reason VARCHAR(200),
    
    -- CRM-specific
    customer_type VARCHAR(100),
    lead_source VARCHAR(200),
    account_manager VARCHAR(200),
    
    -- Sync tracking
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

CREATE INDEX IF NOT EXISTS idx_exact_customers_source ON exact_customers(source_system, source_record_id);
CREATE INDEX IF NOT EXISTS idx_exact_customers_kbo ON exact_customers(kbo_number) WHERE kbo_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_exact_customers_vat ON exact_customers(vat_number) WHERE vat_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_exact_customers_org_uid ON exact_customers(organization_uid) WHERE organization_uid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_exact_customers_name ON exact_customers USING GIN (company_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_exact_customers_city ON exact_customers(city) WHERE city IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_exact_customers_sync ON exact_customers(last_sync_at);
CREATE INDEX IF NOT EXISTS idx_exact_customers_gl_account ON exact_customers(exact_gl_account_id);

COMMENT ON TABLE exact_customers IS 'Exact Online customer accounts with financial and credit information';

-- ==========================================
-- 3. Exact Sales Invoices Table
-- Invoice data from Exact Online
-- ==========================================
CREATE TABLE IF NOT EXISTS exact_sales_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source identification
    source_system VARCHAR(50) NOT NULL DEFAULT 'exact',
    source_record_id VARCHAR(100) NOT NULL, -- Exact Invoice ID (guid)
    invoice_number VARCHAR(100) NOT NULL, -- Human-readable invoice number
    
    -- Link to customer
    exact_customer_id VARCHAR(100),
    crm_company_id UUID REFERENCES crm_companies(id),
    
    -- Invoice info
    invoice_type VARCHAR(50), -- Normal, CreditNote, etc.
    invoice_description TEXT,
    
    -- Financial
    total_amount_excl DECIMAL(15, 2) NOT NULL,
    total_vat_amount DECIMAL(15, 2) NOT NULL,
    total_amount_incl DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'EUR',
    exchange_rate DECIMAL(10, 6) DEFAULT 1.0,
    
    -- Dates
    invoice_date DATE NOT NULL,
    due_date DATE,
    delivery_date DATE,
    payment_date DATE,
    
    -- Status
    invoice_status VARCHAR(50), -- Open, Paid, PartiallyPaid, etc.
    payment_status VARCHAR(50),
    
    -- Payment tracking
    amount_paid DECIMAL(15, 2) DEFAULT 0,
    amount_open DECIMAL(15, 2),
    days_overdue INTEGER,
    
    -- Payment method
    payment_condition VARCHAR(100),
    payment_method VARCHAR(50),
    
    -- Sales info
    sales_order_number VARCHAR(100),
    delivery_number VARCHAR(100),
    
    -- Document references
    document_number VARCHAR(100),
    journal_code VARCHAR(50),
    
    -- Sync tracking
    source_created_at TIMESTAMP,
    source_updated_at TIMESTAMP,
    last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_version INTEGER DEFAULT 1,
    
    -- Raw data
    raw_data JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(source_system, source_record_id),
    UNIQUE(source_system, invoice_number)
);

CREATE INDEX IF NOT EXISTS idx_exact_invoices_source ON exact_sales_invoices(source_system, source_record_id);
CREATE INDEX IF NOT EXISTS idx_exact_invoices_number ON exact_sales_invoices(invoice_number);
CREATE INDEX IF NOT EXISTS idx_exact_invoices_customer ON exact_sales_invoices(exact_customer_id);
CREATE INDEX IF NOT EXISTS idx_exact_invoices_crm_company ON exact_sales_invoices(crm_company_id);
CREATE INDEX IF NOT EXISTS idx_exact_invoices_date ON exact_sales_invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_exact_invoices_due_date ON exact_sales_invoices(due_date);
CREATE INDEX IF NOT EXISTS idx_exact_invoices_status ON exact_sales_invoices(invoice_status);
CREATE INDEX IF NOT EXISTS idx_exact_invoices_payment ON exact_sales_invoices(payment_status);
CREATE INDEX IF NOT EXISTS idx_exact_invoices_overdue ON exact_sales_invoices(days_overdue) WHERE days_overdue > 0;
CREATE INDEX IF NOT EXISTS idx_exact_invoices_sync ON exact_sales_invoices(last_sync_at);

COMMENT ON TABLE exact_sales_invoices IS 'Exact Online sales invoices with payment tracking';

-- ==========================================
-- 4. Exact Sales Invoice Lines Table
-- Line items for each invoice
-- ==========================================
CREATE TABLE IF NOT EXISTS exact_sales_invoice_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source identification
    source_system VARCHAR(50) NOT NULL DEFAULT 'exact',
    source_record_id VARCHAR(100) NOT NULL, -- Exact Line ID (guid)
    
    -- Link to invoice
    exact_invoice_id VARCHAR(100),
    sales_invoice_id UUID REFERENCES exact_sales_invoices(id) ON DELETE CASCADE,
    line_number INTEGER,
    
    -- Product info
    item_code VARCHAR(100),
    item_description TEXT,
    
    -- Quantities
    quantity DECIMAL(15, 4),
    unit_code VARCHAR(50),
    
    -- Pricing
    unit_price DECIMAL(15, 4),
    discount_percentage DECIMAL(5, 2),
    line_amount_excl DECIMAL(15, 2),
    vat_amount DECIMAL(15, 2),
    line_amount_incl DECIMAL(15, 2),
    
    -- GL account
    exact_gl_account_id VARCHAR(100),
    cost_center VARCHAR(100),
    cost_unit VARCHAR(100),
    
    -- Sync tracking
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

CREATE INDEX IF NOT EXISTS idx_exact_invoice_lines_source ON exact_sales_invoice_lines(source_system, source_record_id);
CREATE INDEX IF NOT EXISTS idx_exact_invoice_lines_invoice ON exact_sales_invoice_lines(sales_invoice_id);
CREATE INDEX IF NOT EXISTS idx_exact_invoice_lines_item ON exact_sales_invoice_lines(item_code);
CREATE INDEX IF NOT EXISTS idx_exact_invoice_lines_gl ON exact_sales_invoice_lines(exact_gl_account_id);
CREATE INDEX IF NOT EXISTS idx_exact_invoice_lines_sync ON exact_sales_invoice_lines(last_sync_at);

COMMENT ON TABLE exact_sales_invoice_lines IS 'Exact Online sales invoice line items';

-- ==========================================
-- 5. Exact Transactions Table
-- General ledger transactions (journal entries)
-- ==========================================
CREATE TABLE IF NOT EXISTS exact_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source identification
    source_system VARCHAR(50) NOT NULL DEFAULT 'exact',
    source_record_id VARCHAR(100) NOT NULL, -- Exact Transaction ID (guid)
    entry_number INTEGER,
    
    -- Date
    transaction_date DATE NOT NULL,
    financial_year INTEGER,
    financial_period INTEGER,
    
    -- GL accounts
    exact_gl_account_id VARCHAR(100) REFERENCES exact_accounts(source_record_id),
    exact_gl_account_code VARCHAR(50),
    
    -- Customer/entity
    exact_customer_id VARCHAR(100),
    crm_company_id UUID REFERENCES crm_companies(id),
    
    -- Transaction details
    transaction_type VARCHAR(50), -- Sales, Purchase, Bank, etc.
    transaction_description TEXT,
    document_number VARCHAR(100),
    
    -- Amounts
    amount DECIMAL(15, 2) NOT NULL,
    amount_dc DECIMAL(15, 2), -- Debit/Credit amount
    currency VARCHAR(3) DEFAULT 'EUR',
    
    -- Reference info
    reference_number VARCHAR(100),
    invoice_number VARCHAR(100),
    
    -- Journal info
    journal_code VARCHAR(50),
    journal_description VARCHAR(200),
    
    -- Cost tracking
    cost_center VARCHAR(100),
    cost_unit VARCHAR(100),
    project_code VARCHAR(100),
    
    -- Sync tracking
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

CREATE INDEX IF NOT EXISTS idx_exact_transactions_source ON exact_transactions(source_system, source_record_id);
CREATE INDEX IF NOT EXISTS idx_exact_transactions_date ON exact_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_exact_transactions_gl ON exact_transactions(exact_gl_account_id);
CREATE INDEX IF NOT EXISTS idx_exact_transactions_customer ON exact_transactions(exact_customer_id);
CREATE INDEX IF NOT EXISTS idx_exact_transactions_crm_company ON exact_transactions(crm_company_id);
CREATE INDEX IF NOT EXISTS idx_exact_transactions_type ON exact_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_exact_transactions_year_period ON exact_transactions(financial_year, financial_period);
CREATE INDEX IF NOT EXISTS idx_exact_transactions_invoice ON exact_transactions(invoice_number);
CREATE INDEX IF NOT EXISTS idx_exact_transactions_sync ON exact_transactions(last_sync_at);

COMMENT ON TABLE exact_transactions IS 'Exact Online general ledger transactions (journal entries)';

-- ==========================================
-- 6. Exact Financial Summary View
-- Aggregated customer financial metrics
-- ==========================================
CREATE OR REPLACE VIEW exact_customer_financial_summary AS
SELECT 
    c.id as customer_id,
    c.exact_customer_id,
    c.source_record_id,
    c.company_name,
    c.kbo_number,
    c.vat_number,
    c.organization_uid,
    
    -- Revenue metrics
    COALESCE(SUM(CASE 
        WHEN i.invoice_date >= DATE_TRUNC('year', CURRENT_DATE) 
        THEN i.total_amount_incl 
        ELSE 0 
    END), 0) as revenue_ytd,
    
    COALESCE(SUM(CASE 
        WHEN i.invoice_date >= DATE_TRUNC('month', CURRENT_DATE) 
        THEN i.total_amount_incl 
        ELSE 0 
    END), 0) as revenue_this_month,
    
    COALESCE(SUM(i.total_amount_incl), 0) as revenue_total,
    
    -- Outstanding amounts
    COALESCE(SUM(CASE 
        WHEN i.invoice_status IN ('Open', 'PartiallyPaid') 
        THEN i.amount_open 
        ELSE 0 
    END), 0) as outstanding_amount,
    
    COALESCE(SUM(CASE 
        WHEN i.invoice_status IN ('Open', 'PartiallyPaid') AND i.due_date < CURRENT_DATE
        THEN i.amount_open 
        ELSE 0 
    END), 0) as overdue_amount,
    
    -- Invoice counts
    COUNT(i.id) as total_invoices,
    COUNT(CASE WHEN i.invoice_status = 'Paid' THEN 1 END) as paid_invoices,
    COUNT(CASE WHEN i.invoice_status IN ('Open', 'PartiallyPaid') THEN 1 END) as open_invoices,
    COUNT(CASE WHEN i.days_overdue > 0 THEN 1 END) as overdue_invoices,
    
    -- Payment behavior
    CASE 
        WHEN COUNT(CASE WHEN i.payment_date IS NOT NULL AND i.due_date IS NOT NULL THEN 1 END) > 0
        THEN AVG(CASE 
            WHEN i.payment_date IS NOT NULL AND i.due_date IS NOT NULL 
            THEN GREATEST(i.payment_date - i.due_date, 0)
            ELSE NULL 
        END)
        ELSE NULL 
    END as avg_days_overdue,
    
    -- Last activity
    MAX(i.invoice_date) as last_invoice_date,
    MAX(i.payment_date) as last_payment_date

FROM exact_customers c
LEFT JOIN exact_sales_invoices i ON c.id = i.crm_company_id OR c.source_record_id = i.exact_customer_id
WHERE c.source_system = 'exact'
GROUP BY c.id, c.exact_customer_id, c.source_record_id, c.company_name, c.kbo_number, c.vat_number, c.organization_uid;

COMMENT ON VIEW exact_customer_financial_summary IS 'Aggregated financial metrics per Exact Online customer';

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
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_exact_accounts_updated_at') THEN
        CREATE TRIGGER tr_exact_accounts_updated_at
            BEFORE UPDATE ON exact_accounts
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_exact_customers_updated_at') THEN
        CREATE TRIGGER tr_exact_customers_updated_at
            BEFORE UPDATE ON exact_customers
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_exact_sales_invoices_updated_at') THEN
        CREATE TRIGGER tr_exact_sales_invoices_updated_at
            BEFORE UPDATE ON exact_sales_invoices
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_exact_sales_invoice_lines_updated_at') THEN
        CREATE TRIGGER tr_exact_sales_invoice_lines_updated_at
            BEFORE UPDATE ON exact_sales_invoice_lines
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'tr_exact_transactions_updated_at') THEN
        CREATE TRIGGER tr_exact_transactions_updated_at
            BEFORE UPDATE ON exact_transactions
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END;
$$;

-- ==========================================
-- Migration verification
-- ==========================================
SELECT 
    'exact_accounts' as table_name, 
    COUNT(*) as column_count 
FROM information_schema.columns 
WHERE table_name = 'exact_accounts'
UNION ALL
SELECT 'exact_customers', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'exact_customers'
UNION ALL
SELECT 'exact_sales_invoices', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'exact_sales_invoices'
UNION ALL
SELECT 'exact_sales_invoice_lines', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'exact_sales_invoice_lines'
UNION ALL
SELECT 'exact_transactions', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'exact_transactions'
UNION ALL
SELECT 'exact_customer_financial_summary', COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'exact_customer_financial_summary';
