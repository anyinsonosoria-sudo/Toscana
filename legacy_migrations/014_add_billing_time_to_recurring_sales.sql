-- Migration: Add billing_time to recurring_sales
-- Date: 2026-06-10
-- Description: Add missing billing_time column to recurring_sales

ALTER TABLE recurring_sales ADD COLUMN billing_time TEXT DEFAULT '08:00';
