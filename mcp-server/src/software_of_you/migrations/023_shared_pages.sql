-- Shared Pages Module
-- Live interactive pages published to Cloudflare for client collaboration.
-- Clients can check tasks, leave notes, comment, and suggest new tasks.
-- Changes sync back to local SoY database.

CREATE TABLE IF NOT EXISTS shared_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_filename TEXT,
    title TEXT NOT NULL,
    published_url TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    last_published_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_synced_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS task_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shared_page_id INTEGER NOT NULL REFERENCES shared_pages(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    suggested_by TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'declined')),
    converted_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    remote_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS shared_page_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shared_page_id INTEGER NOT NULL REFERENCES shared_pages(id) ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK (direction IN ('push', 'pull')),
    items_synced INTEGER NOT NULL DEFAULT 0,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_shared_pages_token ON shared_pages(token);
CREATE INDEX IF NOT EXISTS idx_shared_pages_project ON shared_pages(project_id);
CREATE INDEX IF NOT EXISTS idx_shared_pages_status ON shared_pages(status);
CREATE INDEX IF NOT EXISTS idx_task_suggestions_page ON task_suggestions(shared_page_id);
CREATE INDEX IF NOT EXISTS idx_task_suggestions_project ON task_suggestions(project_id);
CREATE INDEX IF NOT EXISTS idx_task_suggestions_status ON task_suggestions(status);
CREATE INDEX IF NOT EXISTS idx_shared_page_sync_log_page ON shared_page_sync_log(shared_page_id);

-- Register module
INSERT OR IGNORE INTO modules (name, version, enabled, installed_at)
VALUES ('shared-pages', '1.0.0', 1, datetime('now'));
