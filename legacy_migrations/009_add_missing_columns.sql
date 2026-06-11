-- Migration 009: Add missing columns to residents and apartments tables
-- These columns were referenced in queries but don't exist in the database
-- NOTE: This migration has already been applied manually. 
-- The columns role_other, payment_terms were added to residents
-- and additional_notes was added to apartments.
-- This file is kept for documentation purposes only.

-- Add missing columns to residents and products_services tables
ALTER TABLE residents ADD COLUMN role_other TEXT;
ALTER TABLE residents ADD COLUMN payment_terms INTEGER DEFAULT 30;
ALTER TABLE products_services ADD COLUMN additional_notes TEXT;
