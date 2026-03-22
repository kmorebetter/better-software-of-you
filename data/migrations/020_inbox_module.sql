-- Inbox Module
-- Quick capture inbox — write first, route later.
-- Adds inbox table, registers module, rebuilds v_nudge_items with unrouted inbox nudges.

-- ═══════════════════════════════════════════════════════════════
-- Part 1: Inbox table
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    routed_to TEXT,              -- NULL = unrouted. Values: 'contact', 'project', 'decision', 'journal', 'note', 'interaction', 'commitment', 'dismissed'
    routed_entity_id INTEGER,   -- FK to destination table row (after routing)
    routed_at TEXT,              -- ISO timestamp when routed
    tags TEXT DEFAULT '[]',     -- JSON array, extracted from #hashtags in content
    matched_contacts TEXT DEFAULT '[]',  -- JSON array of {id, name} objects for matched contacts
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_inbox_unrouted ON inbox(created_at DESC) WHERE routed_to IS NULL;
CREATE INDEX IF NOT EXISTS idx_inbox_routed ON inbox(routed_to) WHERE routed_to IS NOT NULL;


-- ═══════════════════════════════════════════════════════════════
-- Part 2: Module registration
-- ═══════════════════════════════════════════════════════════════

INSERT OR REPLACE INTO modules (name, version) VALUES ('inbox', '1.0.0');


-- ═══════════════════════════════════════════════════════════════
-- Part 3: Rebuild v_nudge_items with inbox UNION ALL added
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_nudge_items;
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
  CAST(julianday('now') - julianday(f.due_date) AS INTEGER) AS days_value,
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
  CAST(julianday('now') - julianday(com.deadline_date) AS INTEGER),
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
  CAST(julianday('now') - julianday(tk.due_date) AS INTEGER),
  p.name,
  'check-square'
FROM tasks tk
JOIN projects p ON p.id = tk.project_id
WHERE tk.status NOT IN ('done') AND tk.due_date < date('now')

UNION ALL

-- Benjis business opportunities (URGENT/SOON/AWARENESS by age)
SELECT
  'opportunity',
  opp.id,
  opp.tier,
  COALESCE(opp.from_name, opp.from_address),
  opp.contact_id,
  NULL,
  opp.match_reason || ': ' || COALESCE(opp.subject, ''),
  opp.received_at,
  opp.days_old,
  opp.from_address,
  'dollar-sign'
FROM v_email_opportunities opp

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
  CAST(julianday(f.due_date) - julianday('now') AS INTEGER),
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
  CAST(julianday(com.deadline_date) - julianday('now') AS INTEGER),
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
  CAST(julianday(tk.due_date) - julianday('now') AS INTEGER),
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
  CAST(julianday(p.target_date) - julianday('now') AS INTEGER),
  NULL,
  'folder'
FROM projects p
WHERE p.status = 'active'
  AND p.target_date BETWEEN date('now') AND date('now', '+7 days')

UNION ALL

-- Contacts going cold (AWARENESS — 30+ days silent)
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
  )),
  CAST(julianday('now') - julianday(
    (SELECT MAX(ts) FROM (
      SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
      UNION ALL SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
      UNION ALL SELECT MAX(t2.occurred_at) FROM transcripts t2
        JOIN transcript_participants tp ON tp.transcript_id = t2.id WHERE tp.contact_id = c.id
    ))
  ) AS INTEGER),
  c.email,
  'users'
FROM contacts c
WHERE c.status = 'active'
  AND (
    (SELECT MAX(ts) FROM (
      SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
      UNION ALL SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
      UNION ALL SELECT MAX(t2.occurred_at) FROM transcripts t2
        JOIN transcript_participants tp ON tp.transcript_id = t2.id WHERE tp.contact_id = c.id
    )) < datetime('now', '-30 days')
    OR (
      (SELECT MAX(ts) FROM (
        SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
        UNION ALL SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
        UNION ALL SELECT MAX(t2.occurred_at) FROM transcripts t2
          JOIN transcript_participants tp ON tp.transcript_id = t2.id WHERE tp.contact_id = c.id
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
  CAST(julianday('now') - julianday(COALESCE(MAX(al.created_at), p.created_at)) AS INTEGER),
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
  CAST(julianday('now') - julianday(d.decided_at) AS INTEGER),
  NULL,
  'git-branch'
FROM decisions d
WHERE d.status = 'decided' AND d.outcome IS NULL
  AND julianday('now') - julianday(d.decided_at) > 90

UNION ALL

-- Unrouted inbox items (AWARENESS / SOON — never urgent)
-- Items older than 1 day surface here; >3 days escalates to 'soon'
SELECT
    'unrouted_inbox',
    i.id,
    CASE
        WHEN julianday('now') - julianday(i.created_at) > 3 THEN 'soon'
        ELSE 'awareness'
    END,
    substr(i.content, 1, 60),
    NULL,
    NULL,
    'Inbox item captured ' || CAST(ROUND(julianday('now') - julianday(i.created_at)) AS INTEGER) || ' days ago — needs routing',
    i.created_at,
    CAST(ROUND(julianday('now') - julianday(i.created_at)) AS INTEGER),
    i.matched_contacts,
    'inbox'
FROM inbox i
WHERE i.routed_to IS NULL
    AND julianday('now') - julianday(i.created_at) > 1

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
  AND e.from_address NOT IN (
    SELECT email FROM google_accounts WHERE status = 'active'
  )
GROUP BY e.from_address
HAVING COUNT(*) >= 5;


-- ═══════════════════════════════════════════════════════════════
-- Part 4: Rebuild v_nudge_summary (depends on v_nudge_items)
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_nudge_summary;
CREATE VIEW IF NOT EXISTS v_nudge_summary AS
SELECT tier, COUNT(*) AS count FROM v_nudge_items GROUP BY tier;
