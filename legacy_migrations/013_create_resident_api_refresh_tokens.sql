CREATE TABLE IF NOT EXISTS resident_api_refresh_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    jti TEXT NOT NULL UNIQUE,
    expires_at INTEGER NOT NULL,
    issued_at INTEGER NOT NULL,
    revoked_at INTEGER,
    replaced_by_jti TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_resident_api_refresh_tokens_user_id
    ON resident_api_refresh_tokens(user_id);

CREATE INDEX IF NOT EXISTS idx_resident_api_refresh_tokens_revoked_at
    ON resident_api_refresh_tokens(revoked_at);