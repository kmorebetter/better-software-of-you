-- D1 Remote Schema for Software of You Shared Pages
-- Deployed to Cloudflare D1 during initial setup.

CREATE TABLE IF NOT EXISTS pages (
    token TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    html TEXT NOT NULL,
    owner_name TEXT,
    owner_email TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    page_token TEXT NOT NULL REFERENCES pages(token) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_started',
    priority TEXT DEFAULT 'medium',
    client_completed INTEGER NOT NULL DEFAULT 0,
    client_completed_at TEXT,
    client_completed_by TEXT,
    synced_to_soy INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_token TEXT NOT NULL REFERENCES pages(token) ON DELETE CASCADE,
    section_id TEXT NOT NULL,
    content TEXT NOT NULL,
    author_name TEXT,
    synced_to_soy INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_token TEXT NOT NULL REFERENCES pages(token) ON DELETE CASCADE,
    content TEXT NOT NULL,
    author_name TEXT,
    author_type TEXT NOT NULL DEFAULT 'client' CHECK (author_type IN ('client', 'owner')),
    synced_to_soy INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_token TEXT NOT NULL REFERENCES pages(token) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    suggested_by TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'declined')),
    synced_to_soy INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_page_token ON tasks(page_token);
CREATE INDEX IF NOT EXISTS idx_tasks_synced ON tasks(synced_to_soy);
CREATE INDEX IF NOT EXISTS idx_notes_page_token ON notes(page_token);
CREATE INDEX IF NOT EXISTS idx_notes_synced ON notes(synced_to_soy);
CREATE INDEX IF NOT EXISTS idx_comments_page_token ON comments(page_token);
CREATE INDEX IF NOT EXISTS idx_comments_synced ON comments(synced_to_soy);
CREATE INDEX IF NOT EXISTS idx_suggestions_page_token ON suggestions(page_token);
CREATE INDEX IF NOT EXISTS idx_suggestions_synced ON suggestions(synced_to_soy);

-- Access control: who can view each page (empty = public)
CREATE TABLE IF NOT EXISTS page_access (
    page_token TEXT NOT NULL REFERENCES pages(token) ON DELETE CASCADE,
    email TEXT NOT NULL,
    invited_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (page_token, email)
);

CREATE INDEX IF NOT EXISTS idx_page_access_token ON page_access(page_token);

-- Session cookies for email-gated access
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    page_token TEXT NOT NULL REFERENCES pages(token) ON DELETE CASCADE,
    email TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_page_token ON sessions(page_token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- ── Telegram Bot Module ──────────────────────────────────────────

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

CREATE TABLE IF NOT EXISTS telegram_sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_message_at TEXT NOT NULL DEFAULT (datetime('now')),
    message_count INTEGER NOT NULL DEFAULT 0,
    summary TEXT
);

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

CREATE TABLE IF NOT EXISTS telegram_context (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_telegram_messages_session ON telegram_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_telegram_messages_created ON telegram_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_telegram_backlog_synced ON telegram_backlog(synced_to_soy);
CREATE INDEX IF NOT EXISTS idx_telegram_backlog_type ON telegram_backlog(type);
