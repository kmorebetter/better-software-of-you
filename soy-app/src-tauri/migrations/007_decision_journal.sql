-- Decision Journal Module Schema v1
-- Tracks decisions with context, rationale, and outcomes. Daily journaling with mood/energy tracking.

-- Decision Log
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    context TEXT,                    -- what prompted this decision
    options_considered TEXT,         -- JSON array of options that were evaluated
    decision TEXT NOT NULL,          -- what was actually decided
    rationale TEXT,                  -- why this option was chosen
    outcome TEXT,                    -- what actually happened (filled in later)
    outcome_date TEXT,              -- when the outcome was observed
    status TEXT NOT NULL DEFAULT 'decided' CHECK (status IN ('open', 'decided', 'revisit', 'validated', 'regretted')),
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    decided_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project_id);
CREATE INDEX IF NOT EXISTS idx_decisions_contact ON decisions(contact_id);
CREATE INDEX IF NOT EXISTS idx_decisions_date ON decisions(decided_at);

-- Journal
CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,           -- the main entry text
    mood TEXT,                       -- free text: "great", "rough", "energized", etc.
    energy INTEGER CHECK (energy BETWEEN 1 AND 5),  -- 1=drained, 5=fired up
    highlights TEXT,                 -- AI-extracted key moments (JSON array)
    entry_date TEXT NOT NULL,        -- the date this entry is about (YYYY-MM-DD)
    linked_contacts TEXT,            -- JSON array of contact IDs mentioned
    linked_projects TEXT,            -- JSON array of project IDs mentioned
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_journal_mood ON journal_entries(mood);

-- Register modules
INSERT OR REPLACE INTO modules (name, version) VALUES ('decision-log', '1.0.0');
INSERT OR REPLACE INTO modules (name, version) VALUES ('journal', '1.0.0');
