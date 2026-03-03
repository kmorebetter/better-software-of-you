-- PM Conversations Module
-- Tracks project management conversations from Gemini, ChatGPT, Claude, etc.
-- Extracts decisions, action items, Claude prompts, and architecture notes.

CREATE TABLE IF NOT EXISTS pm_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN (
        'gemini_web', 'gemini_api', 'chatgpt', 'claude', 'manual'
    )),
    raw_text TEXT,
    message_count INTEGER DEFAULT 0,
    summary TEXT,
    intelligence JSON,
    occurred_at TEXT,
    processed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pm_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES pm_conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'model')),
    content TEXT,
    sequence_num INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pm_conversations_project ON pm_conversations(project_id);
CREATE INDEX IF NOT EXISTS idx_pm_conversations_source ON pm_conversations(source);
CREATE INDEX IF NOT EXISTS idx_pm_messages_conversation ON pm_messages(conversation_id);

-- Register module
INSERT OR REPLACE INTO modules (name, version, enabled, installed_at)
VALUES ('pm-intelligence', '1.0.0', 1, datetime('now'));
