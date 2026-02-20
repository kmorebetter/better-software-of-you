-- Software of You — Core Schema v1
-- All statements are idempotent (safe to re-run)

-- Platform metadata
CREATE TABLE IF NOT EXISTS soy_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO soy_meta (key, value) VALUES ('schema_version', '1');
INSERT OR IGNORE INTO soy_meta (key, value) VALUES ('created_at', datetime('now'));
INSERT OR IGNORE INTO soy_meta (key, value) VALUES ('platform_version', '1.0.0');

-- Contacts
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    company TEXT,
    role TEXT,
    type TEXT NOT NULL DEFAULT 'individual' CHECK (type IN ('individual', 'company')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'archived')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Tags
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT DEFAULT '#6b7280',
    category TEXT
);

-- Entity-tag associations (polymorphic)
CREATE TABLE IF NOT EXISTS entity_tags (
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entity_type, entity_id, tag_id)
);

-- Notes (polymorphic — attachable to any entity)
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Activity log (polymorphic — tracks all changes across the system)
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Installed modules registry
CREATE TABLE IF NOT EXISTS modules (
    name TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    installed_at TEXT NOT NULL DEFAULT (datetime('now')),
    enabled INTEGER NOT NULL DEFAULT 1
);

-- Generated views registry (tracks HTML pages in output/)
CREATE TABLE IF NOT EXISTS generated_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    view_type TEXT NOT NULL,          -- 'entity_page', 'dashboard', 'project_brief', etc.
    entity_type TEXT,                  -- 'contact', 'project', etc. (NULL for dashboard)
    entity_id INTEGER,                 -- linked record ID (NULL for dashboard)
    entity_name TEXT,                  -- display name for nav links
    filename TEXT NOT NULL UNIQUE,     -- relative path in output/ (e.g., 'contact-daniel-byrne.html')
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_generated_views_type ON generated_views(view_type);
CREATE INDEX IF NOT EXISTS idx_generated_views_entity ON generated_views(entity_type, entity_id);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name);
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
CREATE INDEX IF NOT EXISTS idx_entity_tags_lookup ON entity_tags(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_notes_entity ON notes(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_entity ON activity_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_date ON activity_log(created_at);
