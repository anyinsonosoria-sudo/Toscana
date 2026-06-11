-- Migration: Add missing columns and tables
-- Date: 2026-02-02
-- Description: Agregar columna additional_notes a apartments y tabla recurring_sales

-- Agregar columna additional_notes a apartments si no existe
ALTER TABLE apartments ADD COLUMN additional_notes TEXT;

-- Crear tabla de ventas recurrentes
CREATE TABLE IF NOT EXISTS recurring_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    service_id INTEGER,
    amount REAL NOT NULL,
    frequency TEXT NOT NULL DEFAULT 'monthly',
    billing_day INTEGER DEFAULT 1,
    start_date TEXT NOT NULL,
    end_date TEXT,
    description TEXT,
    active INTEGER DEFAULT 1,
    last_generated TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES apartments(id) ON DELETE CASCADE
);

-- Indice para ventas recurrentes activas
CREATE INDEX IF NOT EXISTS idx_recurring_sales_active ON recurring_sales(active);
CREATE INDEX IF NOT EXISTS idx_recurring_sales_unit ON recurring_sales(unit_id);
