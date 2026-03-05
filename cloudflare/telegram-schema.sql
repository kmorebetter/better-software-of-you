-- D1 Schema for Telegram Bot Module
-- Applied during /telegram-setup via D1 API.

-- Conversation messages for history/continuity
CREATE TABLE IF NOT EXISTS telegram_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    tool_calls TEXT,
    tool_results TEXT,
    telegram_message_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Sessions (auto-expire after 4hr inactivity)
CREATE TABLE IF NOT EXISTS telegram_sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_message_at TEXT NOT NULL DEFAULT (datetime('now')),
    message_count INTEGER NOT NULL DEFAULT 0,
    summary TEXT
);

-- Backlog: items to sync to local SoY
CREATE TABLE IF NOT EXISTS telegram_backlog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK (type IN ('task', 'note')),
    project_name TEXT,
    project_id INTEGER,
    title TEXT NOT NULL,
    content TEXT,
    tags TEXT,
    priority TEXT DEFAULT 'medium',
    source_message_id INTEGER,
    synced_to_soy INTEGER NOT NULL DEFAULT 0,
    synced_at TEXT,
    local_entity_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Context cache: SoY data snapshots for Claude's system prompt
CREATE TABLE IF NOT EXISTS telegram_context (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_telegram_messages_session ON telegram_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_telegram_messages_created ON telegram_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_telegram_backlog_synced ON telegram_backlog(synced_to_soy);
CREATE INDEX IF NOT EXISTS idx_telegram_backlog_type ON telegram_backlog(type);
