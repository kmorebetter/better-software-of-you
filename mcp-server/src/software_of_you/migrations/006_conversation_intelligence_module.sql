-- Conversation Intelligence Module Schema v1
-- Imports meeting transcripts, extracts commitments, provides communication coaching.

CREATE TABLE IF NOT EXISTS transcripts (
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
);

CREATE TABLE IF NOT EXISTS transcript_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    speaker_label TEXT NOT NULL,
    is_user INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS commitments (
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

CREATE TABLE IF NOT EXISTS conversation_metrics (
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

CREATE TABLE IF NOT EXISTS communication_insights (
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

CREATE TABLE IF NOT EXISTS relationship_scores (
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
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_transcripts_occurred ON transcripts(occurred_at);
CREATE INDEX IF NOT EXISTS idx_tp_transcript ON transcript_participants(transcript_id);
CREATE INDEX IF NOT EXISTS idx_tp_contact ON transcript_participants(contact_id);
CREATE INDEX IF NOT EXISTS idx_commitments_transcript ON commitments(transcript_id);
CREATE INDEX IF NOT EXISTS idx_commitments_owner ON commitments(owner_contact_id);
CREATE INDEX IF NOT EXISTS idx_commitments_status ON commitments(status);
CREATE INDEX IF NOT EXISTS idx_cm_transcript ON conversation_metrics(transcript_id);
CREATE INDEX IF NOT EXISTS idx_cm_contact ON conversation_metrics(contact_id);
CREATE INDEX IF NOT EXISTS idx_ci_transcript ON communication_insights(transcript_id);
CREATE INDEX IF NOT EXISTS idx_ci_contact ON communication_insights(contact_id);
CREATE INDEX IF NOT EXISTS idx_ci_type ON communication_insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_rs_contact ON relationship_scores(contact_id);
CREATE INDEX IF NOT EXISTS idx_rs_date ON relationship_scores(score_date);

-- Register module
INSERT OR REPLACE INTO modules (name, version) VALUES ('conversation-intelligence', '1.0.0');
