-- Local Telegram bot tables (replaces D1/Cloudflare architecture)
-- Conversations and sessions are stored locally since the bot runs on this machine.

-- Conversation history for claude -p context
CREATE TABLE IF NOT EXISTS telegram_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    telegram_message_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tg_conv_session ON telegram_conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_tg_conv_created ON telegram_conversations(created_at);

-- Bot sessions (group messages by time proximity)
CREATE TABLE IF NOT EXISTS telegram_bot_sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_message_at TEXT NOT NULL DEFAULT (datetime('now')),
    message_count INTEGER NOT NULL DEFAULT 0
);

-- Error log for debugging
CREATE TABLE IF NOT EXISTS telegram_bot_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    error_message TEXT NOT NULL,
    error_stack TEXT,
    user_message_preview TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tg_errors_created ON telegram_bot_errors(created_at);

-- Update module version
INSERT OR REPLACE INTO modules (name, version, enabled, installed_at)
VALUES ('telegram-bot', '2.0.0', 1, datetime('now'));
