CREATE TABLE IF NOT EXISTS resident_user_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    unit_id INTEGER NOT NULL,
    resident_id INTEGER,
    is_primary INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('invited', 'active', 'revoked')),
    invitation_code TEXT,
    invited_at TEXT,
    activated_at TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(unit_id) REFERENCES apartments(id) ON DELETE CASCADE,
    FOREIGN KEY(resident_id) REFERENCES residents(id) ON DELETE SET NULL,
    FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(user_id, unit_id)
);

CREATE INDEX IF NOT EXISTS idx_resident_user_units_user_id ON resident_user_units(user_id);
CREATE INDEX IF NOT EXISTS idx_resident_user_units_unit_id ON resident_user_units(unit_id);
CREATE INDEX IF NOT EXISTS idx_resident_user_units_status ON resident_user_units(status);