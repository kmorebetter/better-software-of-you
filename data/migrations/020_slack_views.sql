-- 018: Update computed views to include Slack messages in activity calculations
-- After Slack integration, v_contact_health and v_nudge_items must factor in
-- slack_messages so contacts with active Slack threads don't appear "silent."

-- ═══════════════════════════════════════════════════════════════
-- v_contact_health: Add slack_messages to last_activity / days_silent
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_contact_health;
CREATE VIEW IF NOT EXISTS v_contact_health AS
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
  ) AS INTEGER) AS days_silent,

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


-- ═══════════════════════════════════════════════════════════════
-- v_nudge_items: Update cold_contact detection to include Slack
-- The full view must be recreated since we're changing the cold_contact UNION member
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_nudge_items;
CREATE VIEW IF NOT EXISTS v_nudge_items AS

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
  ) AS INTEGER),
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
