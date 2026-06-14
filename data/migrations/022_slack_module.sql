-- Slack Module Schema v1
-- Mirrors Slack DMs and allowlisted channels into the local DB.
-- Auto-links Slack users to contacts by email; messages inherit that link.

CREATE TABLE IF NOT EXISTS slack_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_user_id TEXT UNIQUE NOT NULL,
    name TEXT,
    real_name TEXT,
    display_name TEXT,
    email TEXT,
    title TEXT,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    is_bot INTEGER NOT NULL DEFAULT 0,
    is_self INTEGER NOT NULL DEFAULT 0,
    profile_image TEXT,
    tz TEXT,
    deleted INTEGER NOT NULL DEFAULT 0,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_slack_users_contact ON slack_users(contact_id);
CREATE INDEX IF NOT EXISTS idx_slack_users_email ON slack_users(email);

CREATE TABLE IF NOT EXISTS slack_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_channel_id TEXT UNIQUE NOT NULL,
    name TEXT,
    channel_type TEXT NOT NULL CHECK (channel_type IN ('im', 'mpim', 'public_channel', 'private_channel')),
    is_allowlisted INTEGER NOT NULL DEFAULT 0,
    allowlisted_at TEXT,
    last_synced_ts TEXT,
    dm_user_id TEXT,
    member_count INTEGER,
    is_archived INTEGER NOT NULL DEFAULT 0,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_slack_channels_allowlisted ON slack_channels(is_allowlisted);
CREATE INDEX IF NOT EXISTS idx_slack_channels_dm_user ON slack_channels(dm_user_id);

CREATE TABLE IF NOT EXISTS slack_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_ts TEXT NOT NULL,
    channel_id INTEGER NOT NULL REFERENCES slack_channels(id) ON DELETE CASCADE,
    slack_user_id TEXT,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    direction TEXT CHECK (direction IN ('inbound', 'outbound')),
    text TEXT,
    thread_ts TEXT,
    has_link INTEGER NOT NULL DEFAULT 0,
    has_file INTEGER NOT NULL DEFAULT 0,
    reactions TEXT,
    permalink TEXT,
    sent_at TEXT NOT NULL,
    synced_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(channel_id, slack_ts)
);

CREATE INDEX IF NOT EXISTS idx_slack_messages_contact ON slack_messages(contact_id);
CREATE INDEX IF NOT EXISTS idx_slack_messages_channel ON slack_messages(channel_id);
CREATE INDEX IF NOT EXISTS idx_slack_messages_sent ON slack_messages(sent_at);
CREATE INDEX IF NOT EXISTS idx_slack_messages_user ON slack_messages(slack_user_id);
CREATE INDEX IF NOT EXISTS idx_slack_messages_thread ON slack_messages(thread_ts);

-- Per-DM relationship pulse: last contact, days silent, message volume
CREATE VIEW IF NOT EXISTS v_slack_thread_health AS
SELECT
    su.id AS slack_user_pk,
    su.slack_user_id,
    su.real_name,
    su.email,
    su.contact_id,
    c.name AS contact_name,
    sc.id AS channel_pk,
    sc.slack_channel_id,
    COUNT(sm.id) AS message_count_30d,
    SUM(CASE WHEN sm.direction = 'inbound' THEN 1 ELSE 0 END) AS inbound_30d,
    SUM(CASE WHEN sm.direction = 'outbound' THEN 1 ELSE 0 END) AS outbound_30d,
    MAX(sm.sent_at) AS last_message_at,
    CAST(julianday('now') - julianday(MAX(sm.sent_at)) AS INTEGER) AS days_silent
FROM slack_users su
JOIN slack_channels sc
    ON sc.channel_type = 'im'
    AND sc.dm_user_id = su.slack_user_id
LEFT JOIN slack_messages sm
    ON sm.channel_id = sc.id
    AND sm.sent_at >= datetime('now', '-30 days')
WHERE su.is_self = 0 AND su.is_bot = 0
GROUP BY su.id, sc.id;

-- Register module
INSERT OR REPLACE INTO modules (name, version) VALUES ('slack', '1.0.0');
