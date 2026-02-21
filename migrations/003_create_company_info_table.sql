-- Migration 003: Create company_info table
-- Purpose: Store company/administrator information for invoices and documents

CREATE TABLE IF NOT EXISTS company_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    legal_id TEXT,
    address TEXT,
    city TEXT,
    country TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    bank_name TEXT,
    bank_account TEXT,
    bank_routing TEXT,
    tax_id TEXT,
    logo_path TEXT,
    notes TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_company_info_updated ON company_info(updated_at DESC);
