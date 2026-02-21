-- Migration: Create residents table (for legacy compatibility)
CREATE TABLE IF NOT EXISTS residents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER,
    name TEXT,
    email TEXT,
    phone TEXT,
    role TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Add index for unit_id for performance
CREATE INDEX IF NOT EXISTS idx_residents_unit_id ON residents(unit_id);