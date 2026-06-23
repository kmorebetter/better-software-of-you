-- 017: Slack integration — channels and messages

CREATE TABLE IF NOT EXISTS slack_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_message_id TEXT UNIQUE NOT NULL,
    channel_id TEXT NOT NULL,
    channel_name TEXT,
    sender_id TEXT,
    sender_name TEXT,
    content TEXT,
    thread_ts TEXT,
    is_thread_parent INTEGER DEFAULT 0,
    contact_id INTEGER,
    received_at TEXT NOT NULL,
    synced_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (contact_id) REFERENCES contacts(id)
);

CREATE TABLE IF NOT EXISTS slack_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_channel_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    is_dm INTEGER DEFAULT 0,
    is_monitored INTEGER DEFAULT 1,
    last_synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_slack_msg_contact ON slack_messages(contact_id);
CREATE INDEX IF NOT EXISTS idx_slack_msg_channel ON slack_messages(channel_id);
CREATE INDEX IF NOT EXISTS idx_slack_msg_received ON slack_messages(received_at);

-- Register the Slack module
INSERT OR IGNORE INTO modules (name, version, enabled, installed_at)
VALUES ('slack', '1.0.0', 1, datetime('now'));
