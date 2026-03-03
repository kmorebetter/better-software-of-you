-- Shared Page Access Control
-- Track who has been granted access to each shared page.

CREATE TABLE IF NOT EXISTS shared_page_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shared_page_id INTEGER NOT NULL REFERENCES shared_pages(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    invitation_sent_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_shared_page_access_unique
    ON shared_page_access(shared_page_id, email);
CREATE INDEX IF NOT EXISTS idx_shared_page_access_page
    ON shared_page_access(shared_page_id);
