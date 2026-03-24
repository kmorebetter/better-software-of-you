-- Proactive Surfacing Loop
-- Dedup table to prevent repeated briefings within the same time window.
-- This is a platform feature, not a module — no module registration needed.

CREATE TABLE IF NOT EXISTS proactive_briefings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    briefing_type TEXT NOT NULL,     -- 'morning', 'pre_meeting', 'midday', 'evening'
    briefing_key TEXT NOT NULL,      -- dedup key: local date for daily, google_event_id for pre-meeting
    summary TEXT,                    -- what was surfaced (for review)
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(briefing_type, briefing_key)
);

CREATE INDEX IF NOT EXISTS idx_proactive_created ON proactive_briefings(created_at DESC);
