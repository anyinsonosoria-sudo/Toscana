-- Migration 010: Add all missing columns required by billing/payment logic
-- Date: 2026-02-03
-- Description:
--   invoices.pending_amount  → needed by _update_invoice_status() and delete_payment route
--   invoices.recurring_sale_id → needed by create_invoice (recurring) and delete_recurring route
--   invoices.notes           → needed by edit_invoice route
--   payments.notes           → needed by _insert_payment_record()
--   suppliers.supplier_type  → needed by dashboard/supplier queries

ALTER TABLE invoices ADD COLUMN pending_amount REAL DEFAULT 0;
ALTER TABLE invoices ADD COLUMN recurring_sale_id INTEGER;
ALTER TABLE invoices ADD COLUMN notes TEXT;

ALTER TABLE payments ADD COLUMN notes TEXT;

ALTER TABLE suppliers ADD COLUMN supplier_type TEXT DEFAULT 'general';
ALTER TABLE suppliers ADD COLUMN supplier_type_other TEXT;
ALTER TABLE suppliers ADD COLUMN contact_name TEXT;
ALTER TABLE suppliers ADD COLUMN tax_id TEXT;
ALTER TABLE suppliers ADD COLUMN payment_terms INTEGER DEFAULT 30;

ALTER TABLE company_info ADD COLUMN legal_id TEXT;
ALTER TABLE company_info ADD COLUMN city TEXT;
ALTER TABLE company_info ADD COLUMN country TEXT;
ALTER TABLE company_info ADD COLUMN bank_name TEXT;
ALTER TABLE company_info ADD COLUMN bank_account TEXT;
ALTER TABLE company_info ADD COLUMN bank_routing TEXT;
ALTER TABLE company_info ADD COLUMN notes TEXT;
