-- Add 'gemini_debrief' as a valid pm_conversations source type.
-- SQLite CHECK constraints can't be altered, so we drop and recreate the table
-- preserving all data.

-- 1. Copy data to temp table
CREATE TABLE IF NOT EXISTS _pm_conversations_backup AS SELECT * FROM pm_conversations;

-- 2. Drop original
DROP TABLE IF EXISTS pm_conversations;

-- 3. Recreate with updated CHECK
CREATE TABLE pm_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN (
        'gemini_web', 'gemini_api', 'gemini_debrief', 'chatgpt', 'claude', 'manual'
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

-- 4. Restore data
INSERT INTO pm_conversations SELECT * FROM _pm_conversations_backup;

-- 5. Clean up
DROP TABLE _pm_conversations_backup;

-- 6. Recreate indexes
CREATE INDEX IF NOT EXISTS idx_pm_conversations_project ON pm_conversations(project_id);
CREATE INDEX IF NOT EXISTS idx_pm_conversations_source ON pm_conversations(source);
