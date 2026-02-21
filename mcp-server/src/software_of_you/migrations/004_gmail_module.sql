-- Gmail Module Schema v1
-- Tracks synced emails and links them to contacts

CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_id TEXT UNIQUE,
    thread_id TEXT,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    from_address TEXT NOT NULL,
    from_name TEXT,
    to_addresses TEXT,
    subject TEXT,
    snippet TEXT,
    body_preview TEXT,
    labels TEXT,
    is_read INTEGER NOT NULL DEFAULT 0,
    is_starred INTEGER NOT NULL DEFAULT 0,
    received_at TEXT NOT NULL,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Add from_name for existing databases (safe to re-run — bootstrap swallows duplicate column errors)
ALTER TABLE emails ADD COLUMN from_name TEXT;

CREATE INDEX IF NOT EXISTS idx_emails_contact ON emails(contact_id);
CREATE INDEX IF NOT EXISTS idx_emails_thread ON emails(thread_id);
CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(received_at);
CREATE INDEX IF NOT EXISTS idx_emails_gmail_id ON emails(gmail_id);

-- Register module
INSERT OR REPLACE INTO modules (name, version) VALUES ('gmail', '1.0.0');
