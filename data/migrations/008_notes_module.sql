-- Notes Module Schema v1
-- First-class standalone notes with auto-linking to contacts and projects.
-- Separate from the polymorphic `notes` table (which attaches notes to entities).

CREATE TABLE IF NOT EXISTS standalone_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT NOT NULL,
    linked_contacts TEXT,   -- JSON array of contact IDs (auto-detected from content)
    linked_projects TEXT,   -- JSON array of project IDs (auto-detected from content)
    tags TEXT,              -- JSON array of string tags (extracted from #hashtags)
    pinned INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_standalone_notes_pinned ON standalone_notes(pinned);
CREATE INDEX IF NOT EXISTS idx_standalone_notes_created ON standalone_notes(created_at);
CREATE INDEX IF NOT EXISTS idx_standalone_notes_updated ON standalone_notes(updated_at);

-- Register the module
INSERT OR REPLACE INTO modules (name, version) VALUES ('notes', '1.0.0');
