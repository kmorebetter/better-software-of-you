-- User Profile ("Soul") Schema v1
-- Stores structured user identity and derived insights about the platform owner.
-- Key-value design allows open-ended profile growth over time.

CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,          -- e.g. 'identity', 'preferences', 'patterns', 'stats'
    key TEXT NOT NULL,               -- e.g. 'name', 'role', 'communication_style'
    value TEXT,                      -- the stored value
    source TEXT NOT NULL DEFAULT 'explicit',  -- 'explicit' (user-provided) or 'derived' (computed)
    evidence TEXT,                   -- for derived values: how it was calculated
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(category, key)
);

CREATE INDEX IF NOT EXISTS idx_user_profile_category ON user_profile(category);
CREATE INDEX IF NOT EXISTS idx_user_profile_source ON user_profile(source);

-- Register the module
INSERT OR REPLACE INTO modules (name, version) VALUES ('user-profile', '1.0.0');
