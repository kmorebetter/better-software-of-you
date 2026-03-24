-- Multi-Google-Account Support
-- Adds a registry of connected Google accounts and links emails/calendar
-- events to specific accounts via account_id.

-- Account registry
CREATE TABLE IF NOT EXISTS google_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    display_name TEXT,
    token_file TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    connected_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_synced_at TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disconnected', 'error'))
);

-- Add account_id to emails (nullable — NULL means pre-multi-account)
ALTER TABLE emails ADD COLUMN account_id INTEGER REFERENCES google_accounts(id);

-- Add account_id to calendar_events (nullable — NULL means pre-multi-account)
ALTER TABLE calendar_events ADD COLUMN account_id INTEGER REFERENCES google_accounts(id);

-- Indexes for filtering by account
CREATE INDEX IF NOT EXISTS idx_emails_account ON emails(account_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_account ON calendar_events(account_id);
