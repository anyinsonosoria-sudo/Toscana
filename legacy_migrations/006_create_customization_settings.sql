-- Migration: Create customization_settings table
CREATE TABLE IF NOT EXISTS customization_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT NOT NULL UNIQUE,
    setting_value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Insert default accent color
INSERT OR IGNORE INTO customization_settings (setting_key, setting_value) VALUES ('accent_color', '#795547');
