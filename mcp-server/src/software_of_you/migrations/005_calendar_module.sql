-- Calendar Module Schema v1
-- Tracks synced calendar events and links them to contacts/projects

CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    google_event_id TEXT UNIQUE,
    calendar_id TEXT DEFAULT 'primary',
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    all_day INTEGER NOT NULL DEFAULT 0,
    status TEXT DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'tentative', 'cancelled')),
    attendees TEXT,
    contact_ids TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_start ON calendar_events(start_time);
CREATE INDEX IF NOT EXISTS idx_events_google_id ON calendar_events(google_event_id);
CREATE INDEX IF NOT EXISTS idx_events_project ON calendar_events(project_id);

-- Register module
INSERT OR REPLACE INTO modules (name, version) VALUES ('calendar', '1.0.0');
