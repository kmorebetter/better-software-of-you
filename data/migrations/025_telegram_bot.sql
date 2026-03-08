-- Telegram Bot Module (superseded by 027_local_telegram.sql)
-- Tracks items synced from the Telegram bot's D1 backlog into local SoY.

CREATE TABLE IF NOT EXISTS telegram_synced_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    remote_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('task', 'note')),
    local_entity_type TEXT NOT NULL,
    local_entity_id INTEGER NOT NULL,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_telegram_synced_remote ON telegram_synced_items(remote_id);

-- Register module
INSERT OR IGNORE INTO modules (name, version, enabled, installed_at)
VALUES ('telegram-bot', '1.0.0', 1, datetime('now'));
