-- 022_signals.sql — Signals Engine state ledger
--
-- The memory that turns proactive surfacing from a cron job into a partner.
-- One row per distinct thing worth attention, keyed by a STABLE signal_key so a
-- recurring condition (e.g. the same overdue commitment) UPDATES one row instead
-- of re-alerting every run. scripts/signals.py owns detection, scoring, dedup,
-- and auto-resolution; this file only defines storage.
--
-- Idempotent: CREATE TABLE / INDEX IF NOT EXISTS. No module row (not a module).

CREATE TABLE IF NOT EXISTS signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_key      TEXT NOT NULL UNIQUE,          -- stable dedup key: "<type>:<entity_id>[:<sub>]"
    signal_type     TEXT NOT NULL,                 -- follow_up|commitment|task|cold_contact|email_response|discovery|meeting_prep|anomaly
    signal_class    TEXT NOT NULL,                 -- commitment_followthrough|relationship_decay|time_sensitive|discovery|anomaly|retrospective
    entity_type     TEXT,                          -- contact|project|email|commitment|event|...
    entity_id       INTEGER,
    entity_name     TEXT,
    title           TEXT NOT NULL,                 -- short human label
    detail          TEXT,                          -- one-line context
    source_ref      TEXT,                          -- JSON: source rows/ids that produced it (integrity trail)

    urgency         REAL NOT NULL DEFAULT 0,       -- 0..1  time-decay component
    importance      REAL NOT NULL DEFAULT 0,       -- 0..1  relationship/project weight
    novelty         REAL NOT NULL DEFAULT 1,       -- 0..1  new vs already-surfaced
    score           REAL NOT NULL DEFAULT 0,       -- weighted blend (see signals.py)

    status          TEXT NOT NULL DEFAULT 'new',   -- new|surfaced|acted|dismissed|snoozed|resolved
    first_seen      TEXT NOT NULL DEFAULT (datetime('now')),
    last_detected   TEXT NOT NULL DEFAULT (datetime('now')),
    last_surfaced   TEXT,
    surfaced_count  INTEGER NOT NULL DEFAULT 0,
    snooze_until    TEXT,
    feedback        TEXT,
    resolved_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_score  ON signals(score DESC);
CREATE INDEX IF NOT EXISTS idx_signals_type   ON signals(signal_type);
