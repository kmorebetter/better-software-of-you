-- Episodic Memory & Learning Layer v1
-- Compressed retrievable memories, extracted knowledge, pattern detection, and learned rules.
-- All statements are idempotent (safe to re-run).

-- ═══════════════════════════════════════════════════════════════
-- EPISODES — Compressed, retrievable memories of significant interactions.
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    significance TEXT,
    source_type TEXT NOT NULL CHECK (source_type IN ('transcript', 'email_thread', 'calendar_event', 'manual')),
    source_id INTEGER,
    source_ref TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    occurred_at TEXT NOT NULL,
    salience REAL DEFAULT 0.5,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_episodes_occurred ON episodes(occurred_at);
CREATE INDEX IF NOT EXISTS idx_episodes_source ON episodes(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_episodes_project ON episodes(project_id);
CREATE INDEX IF NOT EXISTS idx_episodes_salience ON episodes(salience DESC);

-- ═══════════════════════════════════════════════════════════════
-- EPISODE_CONTACTS — Which contacts appear in each episode.
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS episode_contacts (
    episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'participant' CHECK (role IN ('participant', 'mentioned', 'subject')),
    PRIMARY KEY (episode_id, contact_id)
);

CREATE INDEX IF NOT EXISTS idx_episode_contacts_contact ON episode_contacts(contact_id);

-- ═══════════════════════════════════════════════════════════════
-- FACTS — Extracted knowledge about entities that persists and updates.
-- Bitemporal: learned_at vs last_confirmed_at tracks freshness.
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type TEXT NOT NULL CHECK (subject_type IN ('contact', 'company', 'project')),
    subject_id INTEGER NOT NULL,
    subject_name TEXT,
    category TEXT NOT NULL CHECK (category IN (
        'preference', 'org_intel', 'personal', 'business', 'technical', 'relationship', 'other'
    )),
    content TEXT NOT NULL,
    confidence REAL DEFAULT 0.8,
    source_episode_id INTEGER REFERENCES episodes(id) ON DELETE SET NULL,
    learned_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_confirmed_at TEXT NOT NULL DEFAULT (datetime('now')),
    superseded_at TEXT,
    superseded_by_id INTEGER REFERENCES facts(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
CREATE INDEX IF NOT EXISTS idx_facts_confirmed ON facts(last_confirmed_at);
CREATE INDEX IF NOT EXISTS idx_facts_episode ON facts(source_episode_id);

-- ═══════════════════════════════════════════════════════════════
-- PATTERNS — Detected across multiple episodes.
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    pattern_type TEXT NOT NULL CHECK (pattern_type IN (
        'recurring_topic', 'behavioral', 'scheduling', 'communication', 'outcome', 'other'
    )),
    subject_type TEXT CHECK (subject_type IN ('contact', 'project', 'user', 'company')),
    subject_id INTEGER,
    strength REAL NOT NULL DEFAULT 0.5,
    occurrence_count INTEGER NOT NULL DEFAULT 2,
    first_observed_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_observed_at TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'dismissed', 'promoted')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_patterns_subject ON patterns(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_status ON patterns(status);

-- ═══════════════════════════════════════════════════════════════
-- PATTERN_EPISODES — Evidence chain linking patterns to episodes.
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS pattern_episodes (
    pattern_id INTEGER NOT NULL REFERENCES patterns(id) ON DELETE CASCADE,
    episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    relevance TEXT,
    PRIMARY KEY (pattern_id, episode_id)
);

CREATE INDEX IF NOT EXISTS idx_pattern_episodes_episode ON pattern_episodes(episode_id);

-- ═══════════════════════════════════════════════════════════════
-- LEARNED_RULES — Operational rules promoted from patterns or corrections.
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS learned_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    action TEXT NOT NULL,
    origin TEXT NOT NULL CHECK (origin IN ('pattern_promotion', 'user_correction')),
    source_pattern_id INTEGER REFERENCES patterns(id) ON DELETE SET NULL,
    source_episode_id INTEGER REFERENCES episodes(id) ON DELETE SET NULL,
    target_contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    target_project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    priority INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'retired')),
    times_applied INTEGER NOT NULL DEFAULT 0,
    last_applied_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_learned_rules_status ON learned_rules(status);
CREATE INDEX IF NOT EXISTS idx_learned_rules_contact ON learned_rules(target_contact_id);
CREATE INDEX IF NOT EXISTS idx_learned_rules_project ON learned_rules(target_project_id);

-- ═══════════════════════════════════════════════════════════════
-- COMPUTED VIEWS
-- ═══════════════════════════════════════════════════════════════

-- v_episode_recall: Episodes for a contact, ranked by recency × salience.
-- Used by: /prep, /entity-page
DROP VIEW IF EXISTS v_episode_recall;
CREATE VIEW IF NOT EXISTS v_episode_recall AS
SELECT
    e.id AS episode_id,
    e.title,
    e.summary,
    e.significance,
    e.source_type,
    e.occurred_at,
    e.salience,
    e.project_id,
    (SELECT name FROM projects WHERE id = e.project_id) AS project_name,
    ec.contact_id,
    ec.role AS contact_role,
    (SELECT name FROM contacts WHERE id = ec.contact_id) AS contact_name,
    CAST(julianday('now') - julianday(e.occurred_at) AS INTEGER) AS days_ago,
    e.salience * (1.0 / (1.0 + CAST(julianday('now') - julianday(e.occurred_at) AS REAL) / 30.0)) AS recall_score
FROM episodes e
JOIN episode_contacts ec ON ec.episode_id = e.id
ORDER BY recall_score DESC;

-- v_stale_facts: Current facts not confirmed in 90+ days.
-- Used by: /nudges, /entity-page
DROP VIEW IF EXISTS v_stale_facts;
CREATE VIEW IF NOT EXISTS v_stale_facts AS
SELECT
    f.id,
    f.subject_type,
    f.subject_id,
    f.subject_name,
    f.category,
    f.content,
    f.confidence,
    f.learned_at,
    f.last_confirmed_at,
    CAST(julianday('now') - julianday(f.last_confirmed_at) AS INTEGER) AS days_since_confirmed,
    (SELECT title FROM episodes WHERE id = f.source_episode_id) AS source_episode_title
FROM facts f
WHERE f.superseded_at IS NULL
  AND julianday('now') - julianday(f.last_confirmed_at) > 90
ORDER BY days_since_confirmed DESC;

-- Register module
INSERT OR REPLACE INTO modules (name, version, enabled, installed_at)
VALUES ('episodic-memory', '1.0.0', 1, datetime('now'));
