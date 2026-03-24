-- Track which emails have been imported as transcripts (prevents duplicates).
-- ALTERs will fail silently on re-run (column already exists) — bootstrap swallows stderr.

CREATE TABLE IF NOT EXISTS transcript_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    email_id INTEGER REFERENCES emails(id) ON DELETE SET NULL,
    doc_id TEXT,
    doc_url TEXT,
    source_type TEXT NOT NULL DEFAULT 'gemini',
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ts_email ON transcript_sources(email_id);

-- Add source columns to transcripts
ALTER TABLE transcripts ADD COLUMN source_email_id INTEGER REFERENCES emails(id);
ALTER TABLE transcripts ADD COLUMN source_calendar_event_id INTEGER REFERENCES calendar_events(id);
ALTER TABLE transcripts ADD COLUMN source_doc_id TEXT;
