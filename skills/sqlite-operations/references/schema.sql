-- Software of You — Schema Reference
--
-- GENERATED FROM THE LIVE DATABASE. This is a read-only reference snapshot,
-- not the source of truth. The authoritative schema lives in the ordered
-- migrations under data/migrations/ (applied by shared/bootstrap.sh).
--
-- Regenerate with:
--   sqlite3 ~/.local/share/software-of-you/soy.db .schema > schema.sql
--   (then re-add this header and the module section comments)
--
-- Covers all 34 user tables and all 8 computed views. The sqlite-internal
-- sqlite_sequence table is intentionally omitted.

-- === CORE (always present) ===

CREATE TABLE soy_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    company TEXT,
    role TEXT,
    type TEXT NOT NULL DEFAULT 'individual' CHECK (type IN ('individual', 'company')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'archived')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_contacts_name ON contacts(name);
CREATE INDEX idx_contacts_company ON contacts(company);
CREATE INDEX idx_contacts_status ON contacts(status);

CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT DEFAULT '#6b7280',
    category TEXT
);

CREATE TABLE entity_tags (
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entity_type, entity_id, tag_id)
);
CREATE INDEX idx_entity_tags_lookup ON entity_tags(entity_type, entity_id);

CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_notes_entity ON notes(entity_type, entity_id);

CREATE TABLE activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_activity_log_entity ON activity_log(entity_type, entity_id);
CREATE INDEX idx_activity_log_date ON activity_log(created_at);

CREATE TABLE modules (
    name TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    installed_at TEXT NOT NULL DEFAULT (datetime('now')),
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE generated_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    view_type TEXT NOT NULL,          -- 'entity_page', 'dashboard', 'project_brief', etc.
    entity_type TEXT,                  -- 'contact', 'project', etc. (NULL for dashboard)
    entity_id INTEGER,                 -- linked record ID (NULL for dashboard)
    entity_name TEXT,                  -- display name for nav links
    filename TEXT NOT NULL UNIQUE,     -- relative path in output/ (e.g., 'contact-daniel-byrne.html')
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_generated_views_type ON generated_views(view_type);
CREATE INDEX idx_generated_views_entity ON generated_views(entity_type, entity_id);

CREATE TABLE user_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,          -- e.g. 'identity', 'preferences', 'patterns', 'stats'
    key TEXT NOT NULL,               -- e.g. 'name', 'role', 'communication_style'
    value TEXT,                      -- the stored value
    source TEXT NOT NULL DEFAULT 'explicit',  -- 'explicit' (user-provided) or 'derived' (computed)
    evidence TEXT,                   -- for derived values: how it was calculated
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(category, key)
);
CREATE INDEX idx_user_profile_category ON user_profile(category);
CREATE INDEX idx_user_profile_source ON user_profile(source);

CREATE TABLE schema_migrations (filename TEXT PRIMARY KEY, checksum TEXT, applied_at TEXT);

-- === CRM MODULE ===

CREATE TABLE contact_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('email', 'call', 'meeting', 'message', 'other')),
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    subject TEXT,
    summary TEXT,
    occurred_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_interactions_contact ON contact_interactions(contact_id);
CREATE INDEX idx_interactions_date ON contact_interactions(occurred_at);
CREATE INDEX idx_interactions_type ON contact_interactions(type);

CREATE TABLE contact_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id_a INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    contact_id_b INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    notes TEXT,
    CHECK (contact_id_a < contact_id_b)
);

CREATE TABLE follow_ups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    due_date TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'skipped')),
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_follow_ups_due ON follow_ups(due_date);
CREATE INDEX idx_follow_ups_status ON follow_ups(status);

-- === PROJECT TRACKER MODULE ===

CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    client_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('idea', 'planning', 'active', 'paused', 'completed', 'cancelled')),
    priority TEXT DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    start_date TEXT,
    target_date TEXT,
    completed_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_client ON projects(client_id);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'done', 'blocked')),
    priority TEXT DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    assigned_to INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    due_date TEXT,
    completed_at TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_status ON tasks(status);

CREATE TABLE milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    target_date TEXT,
    completed_date TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'missed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_milestones_project ON milestones(project_id);

-- === GMAIL MODULE ===

CREATE TABLE google_accounts (
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

CREATE TABLE emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_id TEXT UNIQUE,
    thread_id TEXT,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    from_address TEXT NOT NULL,
    to_addresses TEXT,
    subject TEXT,
    snippet TEXT,
    body_preview TEXT,
    labels TEXT,
    is_read INTEGER NOT NULL DEFAULT 0,
    is_starred INTEGER NOT NULL DEFAULT 0,
    received_at TEXT NOT NULL,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
, from_name TEXT, account_id INTEGER REFERENCES google_accounts(id));
CREATE INDEX idx_emails_contact ON emails(contact_id);
CREATE INDEX idx_emails_thread ON emails(thread_id);
CREATE INDEX idx_emails_date ON emails(received_at);
CREATE INDEX idx_emails_gmail_id ON emails(gmail_id);
CREATE INDEX idx_emails_from ON emails(from_address);
CREATE INDEX idx_emails_account ON emails(account_id);

-- === CALENDAR MODULE ===

CREATE TABLE calendar_events (
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
, account_id INTEGER REFERENCES google_accounts(id));
CREATE INDEX idx_events_start ON calendar_events(start_time);
CREATE INDEX idx_events_google_id ON calendar_events(google_event_id);
CREATE INDEX idx_events_project ON calendar_events(project_id);
CREATE INDEX idx_calendar_events_account ON calendar_events(account_id);

-- === CONVERSATION INTELLIGENCE MODULE ===

CREATE TABLE transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    source TEXT DEFAULT 'paste',
    raw_text TEXT NOT NULL,
    summary TEXT,
    duration_minutes INTEGER,
    occurred_at TEXT NOT NULL,
    processed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
, call_intelligence TEXT, source_email_id INTEGER REFERENCES emails(id), source_calendar_event_id INTEGER REFERENCES calendar_events(id), source_doc_id TEXT);
CREATE INDEX idx_transcripts_occurred ON transcripts(occurred_at);

CREATE TABLE transcript_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    speaker_label TEXT NOT NULL,
    is_user INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_tp_transcript ON transcript_participants(transcript_id);
CREATE INDEX idx_tp_contact ON transcript_participants(contact_id);

CREATE TABLE transcript_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    email_id INTEGER REFERENCES emails(id) ON DELETE SET NULL,
    doc_id TEXT,
    doc_url TEXT,
    source_type TEXT NOT NULL DEFAULT 'gemini',
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX idx_ts_email ON transcript_sources(email_id);

CREATE TABLE commitments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    owner_contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    is_user_commitment INTEGER DEFAULT 0,
    description TEXT NOT NULL,
    deadline_mentioned TEXT,
    deadline_date TEXT,
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'completed', 'overdue', 'cancelled')),
    linked_task_id INTEGER,
    linked_project_id INTEGER,
    completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_commitments_transcript ON commitments(transcript_id);
CREATE INDEX idx_commitments_owner ON commitments(owner_contact_id);
CREATE INDEX idx_commitments_status ON commitments(status);
CREATE INDEX idx_commitments_task ON commitments(linked_task_id);
CREATE INDEX idx_commitments_project ON commitments(linked_project_id);

CREATE TABLE conversation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    talk_ratio REAL,
    word_count INTEGER,
    question_count INTEGER,
    interruption_count INTEGER,
    longest_monologue_seconds INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_cm_transcript ON conversation_metrics(transcript_id);
CREATE INDEX idx_cm_contact ON conversation_metrics(contact_id);

CREATE TABLE communication_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    insight_type TEXT NOT NULL CHECK(insight_type IN (
        'relationship_pulse', 'coach_note', 'pattern_alert'
    )),
    content TEXT NOT NULL,
    data_points TEXT,
    sentiment TEXT CHECK(sentiment IN ('positive', 'neutral', 'needs_attention')),
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_ci_transcript ON communication_insights(transcript_id);
CREATE INDEX idx_ci_contact ON communication_insights(contact_id);
CREATE INDEX idx_ci_type ON communication_insights(insight_type);

CREATE TABLE relationship_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    score_date TEXT NOT NULL,
    meeting_frequency REAL,
    talk_ratio_avg REAL,
    commitment_follow_through REAL,
    topic_diversity REAL,
    relationship_depth TEXT CHECK(relationship_depth IN (
        'transactional', 'professional', 'collaborative', 'trusted'
    )),
    trajectory TEXT CHECK(trajectory IN (
        'strengthening', 'stable', 'cooling', 'at_risk'
    )),
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
, commitment_follow_through_inbound REAL);
CREATE INDEX idx_rs_contact ON relationship_scores(contact_id);
CREATE INDEX idx_rs_date ON relationship_scores(score_date);

-- === DECISION LOG MODULE ===

CREATE TABLE decisions (
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
, confidence_level INTEGER CHECK (confidence_level BETWEEN 1 AND 10), review_30_date TEXT, review_90_date TEXT, review_180_date TEXT, process_quality INTEGER CHECK (process_quality BETWEEN 1 AND 5), outcome_quality INTEGER CHECK (outcome_quality BETWEEN 1 AND 5), within_control TEXT, external_factors TEXT, would_do_differently TEXT);
CREATE INDEX idx_decisions_status ON decisions(status);
CREATE INDEX idx_decisions_project ON decisions(project_id);
CREATE INDEX idx_decisions_contact ON decisions(contact_id);
CREATE INDEX idx_decisions_date ON decisions(decided_at);

-- === JOURNAL MODULE ===

CREATE TABLE journal_entries (
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
CREATE INDEX idx_journal_date ON journal_entries(entry_date);
CREATE INDEX idx_journal_mood ON journal_entries(mood);

-- === NOTES MODULE ===

CREATE TABLE standalone_notes (
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
CREATE INDEX idx_standalone_notes_pinned ON standalone_notes(pinned);
CREATE INDEX idx_standalone_notes_created ON standalone_notes(created_at);
CREATE INDEX idx_standalone_notes_updated ON standalone_notes(updated_at);

-- === SLACK MODULE ===

CREATE TABLE slack_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_channel_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    is_dm INTEGER DEFAULT 0,
    is_monitored INTEGER DEFAULT 1,
    last_synced_at TEXT
);

CREATE TABLE slack_messages (
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
CREATE INDEX idx_slack_msg_contact ON slack_messages(contact_id);
CREATE INDEX idx_slack_msg_channel ON slack_messages(channel_id);
CREATE INDEX idx_slack_msg_received ON slack_messages(received_at);

-- === PIPELINE + HEALTH (infrastructure) ===

CREATE TABLE pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running', 'completed', 'failed', 'partial')),
    trigger TEXT DEFAULT 'manual',
    duration_seconds REAL,
    summary TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);

CREATE TABLE pipeline_phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES pipeline_runs(id),
    phase TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    started_at TEXT,
    completed_at TEXT,
    duration_seconds REAL,
    result TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_pipeline_phases_run ON pipeline_phases(run_id);

CREATE TABLE health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ok', 'warning', 'repaired', 'failed')),
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_health_checks_type ON health_checks(check_type);
CREATE INDEX idx_health_checks_created ON health_checks(created_at);

-- === COMPUTED VIEWS (data/migrations/014, 020) — see CLAUDE.md 'Computed Views' ===

CREATE VIEW v_contact_health AS
SELECT
  c.id,
  c.name,
  c.email,
  c.company,
  c.role,
  c.status,

  -- Email stats (last 30 days)
  (SELECT COUNT(*) FROM emails WHERE contact_id = c.id
    AND received_at > datetime('now', '-30 days')) AS emails_30d,
  (SELECT COUNT(*) FROM emails WHERE contact_id = c.id
    AND direction = 'inbound'
    AND received_at > datetime('now', '-30 days')) AS emails_inbound_30d,
  (SELECT COUNT(*) FROM emails WHERE contact_id = c.id
    AND direction = 'outbound'
    AND received_at > datetime('now', '-30 days')) AS emails_outbound_30d,
  (SELECT COUNT(DISTINCT thread_id) FROM emails WHERE contact_id = c.id
    AND received_at > datetime('now', '-30 days')) AS threads_30d,
  (SELECT COUNT(*) FROM emails WHERE contact_id = c.id) AS emails_total,

  -- Interaction stats
  (SELECT COUNT(*) FROM contact_interactions WHERE contact_id = c.id
    AND occurred_at > datetime('now', '-30 days')) AS interactions_30d,
  (SELECT COUNT(*) FROM contact_interactions WHERE contact_id = c.id) AS interactions_total,

  -- Last activity (most recent across interactions, emails, transcripts, AND SLACK)
  (SELECT MAX(ts) FROM (
    SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
    UNION ALL
    SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
    UNION ALL
    SELECT MAX(t.occurred_at) FROM transcripts t
      JOIN transcript_participants tp ON tp.transcript_id = t.id
      WHERE tp.contact_id = c.id
    UNION ALL
    SELECT MAX(received_at) FROM slack_messages WHERE contact_id = c.id
  )) AS last_activity,

  -- Days since last activity (NULL if no activity) — now includes Slack
  CAST(julianday('now') - julianday(
    (SELECT MAX(ts) FROM (
      SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
      UNION ALL
      SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
      UNION ALL
      SELECT MAX(t.occurred_at) FROM transcripts t
        JOIN transcript_participants tp ON tp.transcript_id = t.id
        WHERE tp.contact_id = c.id
      UNION ALL
      SELECT MAX(received_at) FROM slack_messages WHERE contact_id = c.id
    ))
  ) + 0.5 AS INTEGER) AS days_silent,

  -- Transcript/call stats
  (SELECT COUNT(DISTINCT tp.transcript_id) FROM transcript_participants tp
    WHERE tp.contact_id = c.id) AS transcripts_total,
  (SELECT COUNT(DISTINCT tp.transcript_id) FROM transcript_participants tp
    JOIN transcripts t ON t.id = tp.transcript_id
    WHERE tp.contact_id = c.id
    AND t.occurred_at > datetime('now', '-30 days')) AS transcripts_30d,

  -- Slack stats (last 30 days)
  (SELECT COUNT(*) FROM slack_messages WHERE contact_id = c.id
    AND received_at > datetime('now', '-30 days')) AS slack_messages_30d,
  (SELECT COUNT(*) FROM slack_messages WHERE contact_id = c.id) AS slack_messages_total,

  -- Open commitments (you owe them)
  (SELECT COUNT(*) FROM commitments com
    WHERE com.status IN ('open', 'overdue')
    AND com.is_user_commitment = 1
    AND com.transcript_id IN (
      SELECT transcript_id FROM transcript_participants WHERE contact_id = c.id
    )) AS your_open_commitments,

  -- Open commitments (they owe you)
  (SELECT COUNT(*) FROM commitments com
    WHERE com.status IN ('open', 'overdue')
    AND com.is_user_commitment = 0
    AND com.owner_contact_id = c.id) AS their_open_commitments,

  -- Overdue commitments (either direction)
  (SELECT COUNT(*) FROM commitments com
    WHERE com.status IN ('open', 'overdue')
    AND com.deadline_date < date('now')
    AND (com.owner_contact_id = c.id
      OR (com.is_user_commitment = 1 AND com.transcript_id IN (
        SELECT transcript_id FROM transcript_participants WHERE contact_id = c.id
      )))) AS overdue_commitments,

  -- Pending follow-ups
  (SELECT COUNT(*) FROM follow_ups WHERE contact_id = c.id
    AND status = 'pending') AS pending_follow_ups,
  (SELECT COUNT(*) FROM follow_ups WHERE contact_id = c.id
    AND status = 'pending' AND due_date < date('now')) AS overdue_follow_ups,

  -- Next upcoming event with this contact
  (SELECT MIN(start_time) FROM calendar_events
    WHERE contact_ids LIKE '%' || c.id || '%'
    AND start_time > datetime('now')
    AND status != 'cancelled') AS next_meeting,

  -- Active projects where this contact is the client
  (SELECT COUNT(*) FROM projects WHERE client_id = c.id
    AND status IN ('active', 'planning')) AS active_projects,

  -- Latest relationship score
  (SELECT relationship_depth FROM relationship_scores
    WHERE contact_id = c.id ORDER BY score_date DESC LIMIT 1) AS relationship_depth,
  (SELECT trajectory FROM relationship_scores
    WHERE contact_id = c.id ORDER BY score_date DESC LIMIT 1) AS trajectory,
  (SELECT commitment_follow_through FROM relationship_scores
    WHERE contact_id = c.id ORDER BY score_date DESC LIMIT 1) AS follow_through,
  (SELECT talk_ratio_avg FROM relationship_scores
    WHERE contact_id = c.id ORDER BY score_date DESC LIMIT 1) AS talk_ratio_avg,
  (SELECT notes FROM relationship_scores
    WHERE contact_id = c.id ORDER BY score_date DESC LIMIT 1) AS relationship_notes

FROM contacts c
WHERE c.status = 'active';

CREATE VIEW v_commitment_status AS
SELECT
  com.id,
  com.description,
  com.status,
  com.is_user_commitment,
  com.deadline_date,
  com.deadline_mentioned,
  com.owner_contact_id,
  com.transcript_id,
  com.linked_task_id,
  com.linked_project_id,
  com.created_at,

  -- Owner display name
  CASE WHEN com.is_user_commitment = 1 THEN 'You'
       ELSE COALESCE(c.name, 'Unknown') END AS owner_name,

  -- Source call info
  t.title AS from_call,
  t.occurred_at AS call_date,

  -- Days overdue (NULL if not overdue, positive if overdue)
  CASE
    WHEN com.deadline_date IS NOT NULL AND com.deadline_date < date('now')
    THEN CAST(julianday('now') - julianday(com.deadline_date) + 0.5 AS INTEGER)
    ELSE NULL
  END AS days_overdue,

  -- Days until deadline (NULL if no deadline, negative if past)
  CASE
    WHEN com.deadline_date IS NOT NULL
    THEN CAST(julianday(com.deadline_date) - julianday('now') + 0.5 AS INTEGER)
    ELSE NULL
  END AS days_until_deadline,

  -- Urgency tier
  CASE
    WHEN com.deadline_date IS NOT NULL AND com.deadline_date < date('now') THEN 'overdue'
    WHEN com.deadline_date IS NOT NULL AND com.deadline_date <= date('now', '+3 days') THEN 'soon'
    ELSE 'open'
  END AS urgency,

  -- Contact involved (the other party — not the owner)
  COALESCE(
    (SELECT GROUP_CONCAT(DISTINCT c2.name) FROM transcript_participants tp2
      JOIN contacts c2 ON c2.id = tp2.contact_id
      WHERE tp2.transcript_id = com.transcript_id
      AND tp2.contact_id != com.owner_contact_id
      AND tp2.is_user = 0),
    c.name
  ) AS involved_contact_name

FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
LEFT JOIN transcripts t ON t.id = com.transcript_id
WHERE com.status IN ('open', 'overdue');

CREATE VIEW v_nudge_items AS

-- Overdue follow-ups (URGENT)
SELECT
  'follow_up' AS nudge_type,
  f.id AS entity_id,
  'urgent' AS tier,
  c.name AS entity_name,
  c.id AS contact_id,
  NULL AS project_id,
  f.reason AS description,
  f.due_date AS relevant_date,
  CAST(julianday('now') - julianday(f.due_date) + 0.5 AS INTEGER) AS days_value,
  c.company AS extra_context,
  'clock' AS icon
FROM follow_ups f
JOIN contacts c ON c.id = f.contact_id
WHERE f.status = 'pending' AND f.due_date < date('now')

UNION ALL

-- Overdue commitments (URGENT)
SELECT
  'commitment',
  com.id,
  'urgent',
  CASE WHEN com.is_user_commitment = 1 THEN 'You' ELSE COALESCE(c.name, 'Unknown') END,
  com.owner_contact_id,
  NULL,
  com.description,
  com.deadline_date,
  CAST(julianday('now') - julianday(com.deadline_date) + 0.5 AS INTEGER),
  t.title,
  'target'
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
LEFT JOIN transcripts t ON t.id = com.transcript_id
WHERE com.status IN ('open', 'overdue') AND com.deadline_date < date('now')

UNION ALL

-- Overdue tasks (URGENT)
SELECT
  'task',
  tk.id,
  'urgent',
  tk.title,
  NULL,
  tk.project_id,
  p.name,
  tk.due_date,
  CAST(julianday('now') - julianday(tk.due_date) + 0.5 AS INTEGER),
  p.name,
  'check-square'
FROM tasks tk
JOIN projects p ON p.id = tk.project_id
WHERE tk.status NOT IN ('done') AND tk.due_date < date('now')

UNION ALL

-- Follow-ups due soon (SOON — within 3 days)
SELECT
  'follow_up',
  f.id,
  'soon',
  c.name,
  c.id,
  NULL,
  f.reason,
  f.due_date,
  CAST(julianday(f.due_date) - julianday('now') + 0.5 AS INTEGER),
  c.company,
  'clock'
FROM follow_ups f
JOIN contacts c ON c.id = f.contact_id
WHERE f.status = 'pending'
  AND f.due_date BETWEEN date('now') AND date('now', '+3 days')

UNION ALL

-- Commitments due soon (SOON — within 3 days)
SELECT
  'commitment',
  com.id,
  'soon',
  CASE WHEN com.is_user_commitment = 1 THEN 'You' ELSE COALESCE(c.name, 'Unknown') END,
  com.owner_contact_id,
  NULL,
  com.description,
  com.deadline_date,
  CAST(julianday(com.deadline_date) - julianday('now') + 0.5 AS INTEGER),
  t.title,
  'target'
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
LEFT JOIN transcripts t ON t.id = com.transcript_id
WHERE com.status = 'open'
  AND com.deadline_date BETWEEN date('now') AND date('now', '+3 days')

UNION ALL

-- Tasks due soon (SOON — within 3 days)
SELECT
  'task',
  tk.id,
  'soon',
  tk.title,
  NULL,
  tk.project_id,
  p.name,
  tk.due_date,
  CAST(julianday(tk.due_date) - julianday('now') + 0.5 AS INTEGER),
  p.name,
  'check-square'
FROM tasks tk
JOIN projects p ON p.id = tk.project_id
WHERE tk.status NOT IN ('done')
  AND tk.due_date BETWEEN date('now') AND date('now', '+3 days')

UNION ALL

-- Projects approaching target date (SOON — within 7 days)
SELECT
  'project',
  p.id,
  'soon',
  p.name,
  NULL,
  p.id,
  CAST((SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status != 'done') AS TEXT) || ' open tasks',
  p.target_date,
  CAST(julianday(p.target_date) - julianday('now') + 0.5 AS INTEGER),
  NULL,
  'folder'
FROM projects p
WHERE p.status = 'active'
  AND p.target_date BETWEEN date('now') AND date('now', '+7 days')

UNION ALL

-- Contacts going cold (AWARENESS — 30+ days silent) — NOW INCLUDES SLACK
SELECT
  'cold_contact',
  c.id,
  'awareness',
  c.name,
  c.id,
  NULL,
  c.company,
  (SELECT MAX(ts) FROM (
    SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
    UNION ALL SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
    UNION ALL SELECT MAX(t2.occurred_at) FROM transcripts t2
      JOIN transcript_participants tp ON tp.transcript_id = t2.id WHERE tp.contact_id = c.id
    UNION ALL SELECT MAX(received_at) FROM slack_messages WHERE contact_id = c.id
  )),
  CAST(julianday('now') - julianday(
    (SELECT MAX(ts) FROM (
      SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
      UNION ALL SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
      UNION ALL SELECT MAX(t2.occurred_at) FROM transcripts t2
        JOIN transcript_participants tp ON tp.transcript_id = t2.id WHERE tp.contact_id = c.id
      UNION ALL SELECT MAX(received_at) FROM slack_messages WHERE contact_id = c.id
    ))
  ) + 0.5 AS INTEGER),
  c.email,
  'users'
FROM contacts c
WHERE c.status = 'active'
  AND (
    -- Either last activity was 30+ days ago
    (SELECT MAX(ts) FROM (
      SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
      UNION ALL SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
      UNION ALL SELECT MAX(t2.occurred_at) FROM transcripts t2
        JOIN transcript_participants tp ON tp.transcript_id = t2.id WHERE tp.contact_id = c.id
      UNION ALL SELECT MAX(received_at) FROM slack_messages WHERE contact_id = c.id
    )) < datetime('now', '-30 days')
    -- Or contact has zero activity and was added 30+ days ago
    OR (
      (SELECT MAX(ts) FROM (
        SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
        UNION ALL SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
        UNION ALL SELECT MAX(t2.occurred_at) FROM transcripts t2
          JOIN transcript_participants tp ON tp.transcript_id = t2.id WHERE tp.contact_id = c.id
        UNION ALL SELECT MAX(received_at) FROM slack_messages WHERE contact_id = c.id
      )) IS NULL
      AND julianday('now') - julianday(c.created_at) > 30
    )
  )

UNION ALL

-- Stale projects (AWARENESS — 14+ days no activity)
SELECT
  'stale_project',
  p.id,
  'awareness',
  p.name,
  NULL,
  p.id,
  p.status,
  MAX(al.created_at),
  CAST(julianday('now') - julianday(COALESCE(MAX(al.created_at), p.created_at)) + 0.5 AS INTEGER),
  p.target_date,
  'folder'
FROM projects p
LEFT JOIN activity_log al ON al.entity_type = 'project' AND al.entity_id = p.id
WHERE p.status IN ('active', 'planning')
GROUP BY p.id
HAVING CAST(julianday('now') - julianday(COALESCE(MAX(al.created_at), p.created_at)) AS INTEGER) > 14

UNION ALL

-- Decisions pending outcome (AWARENESS — 90+ days old)
SELECT
  'decision',
  d.id,
  'awareness',
  d.title,
  d.contact_id,
  d.project_id,
  'No outcome recorded',
  d.decided_at,
  CAST(julianday('now') - julianday(d.decided_at) + 0.5 AS INTEGER),
  NULL,
  'git-branch'
FROM decisions d
WHERE d.status = 'decided' AND d.outcome IS NULL
  AND julianday('now') - julianday(d.decided_at) > 90

UNION ALL

-- Untracked frequent contacts (AWARENESS — 5+ emails, not in CRM)
SELECT
  'untracked_contact',
  NULL,
  'awareness',
  COALESCE(e.from_name, e.from_address),
  NULL,
  NULL,
  e.from_address,
  MAX(e.received_at),
  COUNT(*),
  CAST(COUNT(DISTINCT e.thread_id) AS TEXT) || ' threads',
  'user-plus'
FROM emails e
WHERE e.direction = 'inbound'
  AND e.contact_id IS NULL
  AND e.from_address NOT LIKE '%noreply%'
  AND e.from_address NOT LIKE '%no-reply%'
  AND e.from_address NOT LIKE '%do-not-reply%'
  AND e.from_address NOT LIKE '%notifications%'
  AND e.from_address NOT LIKE '%newsletter%'
  AND e.from_address NOT LIKE '%digest%'
  AND e.from_address NOT LIKE '%automated%'
  AND e.from_address NOT LIKE '%mailer-daemon%'
  AND e.from_address NOT LIKE '%@calendar.google.com'
  AND e.from_address NOT LIKE '%@docs.google.com'
  AND e.from_address NOT LIKE '%@github.com'
  AND e.from_address NOT LIKE '%@linkedin.com'
  AND e.from_address NOT LIKE '%@slack.com'
  AND e.from_address NOT IN (
    SELECT email FROM contacts WHERE email IS NOT NULL AND email != ''
  )
GROUP BY e.from_address
HAVING COUNT(*) >= 5;

CREATE VIEW v_nudge_summary AS
SELECT
  tier,
  COUNT(*) AS count
FROM v_nudge_items
GROUP BY tier;

CREATE VIEW v_discovery_candidates AS
SELECT
  e.from_address,
  e.from_name,
  COUNT(*) AS email_count,
  COUNT(DISTINCT e.thread_id) AS thread_count,
  MAX(e.received_at) AS last_email,
  MIN(e.received_at) AS first_email,
  CAST(julianday('now') - julianday(MAX(e.received_at)) + 0.5 AS INTEGER) AS days_since_last,

  -- Relevance score components
  MIN(COUNT(*), 10) AS volume_score,
  MIN(COUNT(DISTINCT e.thread_id) * 2, 10) AS thread_score,
  CASE
    WHEN CAST(julianday('now') - julianday(MAX(e.received_at)) AS INTEGER) <= 7 THEN 5
    WHEN CAST(julianday('now') - julianday(MAX(e.received_at)) AS INTEGER) <= 14 THEN 3
    WHEN CAST(julianday('now') - julianday(MAX(e.received_at)) AS INTEGER) <= 30 THEN 1
    ELSE 0
  END AS recency_score,

  -- Total relevance score
  MIN(COUNT(*), 10)
    + MIN(COUNT(DISTINCT e.thread_id) * 2, 10)
    + CASE
        WHEN CAST(julianday('now') - julianday(MAX(e.received_at)) AS INTEGER) <= 7 THEN 5
        WHEN CAST(julianday('now') - julianday(MAX(e.received_at)) AS INTEGER) <= 14 THEN 3
        WHEN CAST(julianday('now') - julianday(MAX(e.received_at)) AS INTEGER) <= 30 THEN 1
        ELSE 0
      END AS relevance_score

FROM emails e
WHERE e.direction = 'inbound'
  AND e.contact_id IS NULL
  AND e.from_address NOT LIKE '%noreply%'
  AND e.from_address NOT LIKE '%no-reply%'
  AND e.from_address NOT LIKE '%do-not-reply%'
  AND e.from_address NOT LIKE '%notifications%'
  AND e.from_address NOT LIKE '%newsletter%'
  AND e.from_address NOT LIKE '%digest%'
  AND e.from_address NOT LIKE '%automated%'
  AND e.from_address NOT LIKE '%mailer-daemon%'
  AND e.from_address NOT LIKE '%calendar-notification%'
  AND e.from_address NOT LIKE '%@calendar.google.com'
  AND e.from_address NOT LIKE '%@docs.google.com'
  AND e.from_address NOT LIKE '%@github.com'
  AND e.from_address NOT LIKE '%@linkedin.com'
  AND e.from_address NOT LIKE '%@slack.com'
  AND e.from_address NOT IN (
    SELECT email FROM contacts WHERE email IS NOT NULL AND email != ''
  )
  AND e.from_address NOT IN (
    SELECT email FROM google_accounts WHERE status = 'active'
  )
GROUP BY e.from_address
HAVING email_count >= 2
ORDER BY relevance_score DESC, last_email DESC;

CREATE VIEW v_meeting_prep AS
SELECT
  ce.id AS event_id,
  ce.title,
  ce.description,
  ce.location,
  ce.start_time,
  ce.end_time,
  ce.all_day,
  ce.status,
  ce.attendees,
  ce.contact_ids,
  ce.project_id,

  -- Time context
  CASE
    WHEN ce.start_time <= datetime('now') AND ce.end_time > datetime('now') THEN 'now'
    WHEN CAST((julianday(ce.start_time) - julianday('now')) * 24 * 60 AS INTEGER) <= 120 THEN 'imminent'
    WHEN date(ce.start_time) = date('now') THEN 'today'
    WHEN date(ce.start_time) = date('now', '+1 day') THEN 'tomorrow'
    ELSE 'upcoming'
  END AS time_context,

  -- Minutes until start (negative if in progress)
  CAST((julianday(ce.start_time) - julianday('now')) * 24 * 60 AS INTEGER) AS minutes_until,

  -- Duration in minutes
  CAST((julianday(ce.end_time) - julianday(ce.start_time)) * 24 * 60 AS INTEGER) AS duration_minutes,

  -- Project name (if linked)
  (SELECT name FROM projects WHERE id = ce.project_id) AS project_name,
  (SELECT status FROM projects WHERE id = ce.project_id) AS project_status

FROM calendar_events ce
WHERE ce.status != 'cancelled'
  AND (ce.start_time > datetime('now', '-1 day')
    OR (ce.start_time <= datetime('now') AND ce.end_time > datetime('now')));

CREATE VIEW v_project_health AS
SELECT
  p.id,
  p.name,
  p.status,
  p.priority,
  p.start_date,
  p.target_date,
  p.client_id,

  -- Client name
  (SELECT name FROM contacts WHERE id = p.client_id) AS client_name,

  -- Task counts
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id) AS total_tasks,
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status = 'todo') AS todo_tasks,
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status = 'in_progress') AS active_tasks,
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status = 'done') AS done_tasks,
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status = 'blocked') AS blocked_tasks,

  -- Completion percentage (0-100, integer)
  CASE
    WHEN (SELECT COUNT(*) FROM tasks WHERE project_id = p.id) = 0 THEN 0
    ELSE CAST(
      (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status = 'done') * 100.0
      / (SELECT COUNT(*) FROM tasks WHERE project_id = p.id)
    AS INTEGER)
  END AS completion_pct,

  -- Overdue tasks
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id
    AND status NOT IN ('done') AND due_date < date('now')) AS overdue_tasks,

  -- Days to target (negative if past)
  CASE
    WHEN p.target_date IS NOT NULL
    THEN CAST(julianday(p.target_date) - julianday('now') + 0.5 AS INTEGER)
    ELSE NULL
  END AS days_to_target,

  -- Last activity
  (SELECT MAX(created_at) FROM activity_log
    WHERE entity_type = 'project' AND entity_id = p.id) AS last_activity,
  CAST(julianday('now') - julianday(COALESCE(
    (SELECT MAX(created_at) FROM activity_log WHERE entity_type = 'project' AND entity_id = p.id),
    p.created_at
  )) + 0.5 AS INTEGER) AS days_since_activity,

  -- Milestone progress
  (SELECT COUNT(*) FROM milestones WHERE project_id = p.id) AS total_milestones,
  (SELECT COUNT(*) FROM milestones WHERE project_id = p.id AND status = 'completed') AS completed_milestones,
  (SELECT MIN(target_date) FROM milestones WHERE project_id = p.id
    AND status = 'pending' AND target_date >= date('now')) AS next_milestone_date,
  (SELECT name FROM milestones WHERE project_id = p.id
    AND status = 'pending' AND target_date >= date('now')
    ORDER BY target_date ASC LIMIT 1) AS next_milestone_name,

  -- Open commitments related to this project's client
  (SELECT COUNT(*) FROM commitments WHERE status IN ('open', 'overdue')
    AND (linked_project_id = p.id
      OR owner_contact_id = p.client_id)) AS open_commitments

FROM projects p
WHERE p.status NOT IN ('completed', 'cancelled');

CREATE VIEW v_email_response_queue AS
SELECT
  e.id,
  e.thread_id,
  e.subject,
  e.from_name,
  e.from_address,
  e.snippet,
  e.received_at,
  e.contact_id,
  c.name AS contact_name,
  CAST(julianday('now') - julianday(e.received_at) + 0.5 AS INTEGER) AS days_old,
  CASE
    WHEN CAST(julianday('now') - julianday(e.received_at) AS INTEGER) > 3 THEN 'overdue'
    WHEN CAST(julianday('now') - julianday(e.received_at) AS INTEGER) > 1 THEN 'aging'
    ELSE 'fresh'
  END AS urgency
FROM emails e
LEFT JOIN contacts c ON e.contact_id = c.id
WHERE e.direction = 'inbound'
  AND e.is_read = 0
  AND e.thread_id NOT IN (
    SELECT thread_id FROM emails
    WHERE direction = 'outbound' AND received_at > e.received_at
  )
ORDER BY e.received_at ASC;

