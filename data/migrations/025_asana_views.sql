-- 025: Integrate Asana into relationship health, nudges, and per-task urgency.

-- ═══════════════════════════════════════════════════════════════
-- v_asana_task_health: Per-task derived urgency and delegation status
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_asana_task_health;
CREATE VIEW IF NOT EXISTS v_asana_task_health AS
SELECT
  at.id,
  at.gid,
  at.name,
  at.notes,
  at.permalink,
  at.completed,
  at.due_on,
  at.due_at,
  at.modified_at,
  at.created_at,
  at.assignee_gid,
  at.assignee_contact_id,
  at.created_by_gid,

  -- Workspace + project context
  aw.gid AS workspace_gid,
  aw.name AS workspace_name,
  ap.gid AS project_gid,
  ap.name AS project_name,
  ap.archived AS project_archived,

  -- Assignee + creator names
  ua.name AS assignee_name,
  ua.email AS assignee_email,
  uc.name AS creator_name,
  c_assignee.name AS assignee_contact_name,

  -- Self-as-assignee / delegation flags
  CASE WHEN ua.is_self = 1 THEN 1 ELSE 0 END AS is_mine,
  CASE WHEN uc.is_self = 1 AND ua.is_self = 0 AND at.assignee_gid IS NOT NULL THEN 1 ELSE 0 END AS is_delegated_by_me,
  CASE WHEN at.assignee_gid IS NULL THEN 1 ELSE 0 END AS is_unassigned,

  -- Days until / overdue
  CASE
    WHEN at.due_on IS NULL THEN NULL
    ELSE CAST(julianday(at.due_on) - julianday('now') AS INTEGER)
  END AS days_until_due,

  CASE
    WHEN at.completed = 1 THEN 'done'
    WHEN at.due_on IS NULL THEN 'no_deadline'
    WHEN at.due_on < date('now') THEN 'overdue'
    WHEN at.due_on <= date('now', '+3 days') THEN 'soon'
    ELSE 'future'
  END AS urgency

FROM asana_tasks at
LEFT JOIN asana_projects ap ON ap.gid = at.project_gid
LEFT JOIN asana_workspaces aw ON aw.gid = at.workspace_gid
LEFT JOIN asana_users ua ON ua.gid = at.assignee_gid
LEFT JOIN asana_users uc ON uc.gid = at.created_by_gid
LEFT JOIN contacts c_assignee ON c_assignee.id = at.assignee_contact_id;


-- ═══════════════════════════════════════════════════════════════
-- v_contact_health: now also factors Asana activity
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

  (SELECT COUNT(*) FROM contact_interactions WHERE contact_id = c.id
    AND occurred_at > datetime('now', '-30 days')) AS interactions_30d,
  (SELECT COUNT(*) FROM contact_interactions WHERE contact_id = c.id) AS interactions_total,

  -- last_activity now also considers slack + asana
  (SELECT MAX(ts) FROM (
    SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
    UNION ALL
    SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
    UNION ALL
    SELECT MAX(t.occurred_at) FROM transcripts t
      JOIN transcript_participants tp ON tp.transcript_id = t.id
      WHERE tp.contact_id = c.id
    UNION ALL
    SELECT MAX(sent_at) FROM slack_messages WHERE contact_id = c.id
    UNION ALL
    SELECT MAX(modified_at) FROM asana_tasks WHERE assignee_contact_id = c.id
  )) AS last_activity,

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
      SELECT MAX(sent_at) FROM slack_messages WHERE contact_id = c.id
      UNION ALL
      SELECT MAX(modified_at) FROM asana_tasks WHERE assignee_contact_id = c.id
    ))
  ) AS INTEGER) AS days_silent,

  (SELECT COUNT(DISTINCT tp.transcript_id) FROM transcript_participants tp
    WHERE tp.contact_id = c.id) AS transcripts_total,
  (SELECT COUNT(DISTINCT tp.transcript_id) FROM transcript_participants tp
    JOIN transcripts t ON t.id = tp.transcript_id
    WHERE tp.contact_id = c.id
    AND t.occurred_at > datetime('now', '-30 days')) AS transcripts_30d,

  (SELECT COUNT(*) FROM slack_messages WHERE contact_id = c.id
    AND sent_at > datetime('now', '-30 days')) AS slack_messages_30d,
  (SELECT COUNT(*) FROM slack_messages WHERE contact_id = c.id) AS slack_messages_total,

  -- Asana stats
  (SELECT COUNT(*) FROM asana_tasks
    WHERE assignee_contact_id = c.id
    AND modified_at > datetime('now', '-30 days')) AS asana_tasks_30d,
  (SELECT COUNT(*) FROM asana_tasks
    WHERE assignee_contact_id = c.id
    AND completed = 0) AS asana_tasks_open,
  (SELECT COUNT(*) FROM asana_tasks
    WHERE assignee_contact_id = c.id
    AND completed = 0
    AND due_on IS NOT NULL
    AND due_on < date('now')) AS asana_tasks_overdue,

  (SELECT COUNT(*) FROM commitments com
    WHERE com.status IN ('open', 'overdue')
    AND com.is_user_commitment = 1
    AND com.transcript_id IN (
      SELECT transcript_id FROM transcript_participants WHERE contact_id = c.id
    )) AS your_open_commitments,

  (SELECT COUNT(*) FROM commitments com
    WHERE com.status IN ('open', 'overdue')
    AND com.is_user_commitment = 0
    AND com.owner_contact_id = c.id) AS their_open_commitments,

  (SELECT COUNT(*) FROM commitments com
    WHERE com.status IN ('open', 'overdue')
    AND com.deadline_date < date('now')
    AND (com.owner_contact_id = c.id
      OR (com.is_user_commitment = 1 AND com.transcript_id IN (
        SELECT transcript_id FROM transcript_participants WHERE contact_id = c.id
      )))) AS overdue_commitments,

  (SELECT COUNT(*) FROM follow_ups WHERE contact_id = c.id
    AND status = 'pending') AS pending_follow_ups,
  (SELECT COUNT(*) FROM follow_ups WHERE contact_id = c.id
    AND status = 'pending' AND due_date < date('now')) AS overdue_follow_ups,

  (SELECT MIN(start_time) FROM calendar_events
    WHERE contact_ids LIKE '%' || c.id || '%'
    AND start_time > datetime('now')
    AND status != 'cancelled') AS next_meeting,

  (SELECT COUNT(*) FROM projects WHERE client_id = c.id
    AND status IN ('active', 'planning')) AS active_projects,

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
-- v_nudge_items: rebuilt with 5 new Asana nudge categories.
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_nudge_summary;
DROP VIEW IF EXISTS v_nudge_items;
CREATE VIEW IF NOT EXISTS v_nudge_items AS

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

-- Asana: my overdue tasks (URGENT)
SELECT
  'asana_overdue_mine',
  ath.id,
  'urgent',
  ath.name,
  ath.assignee_contact_id,
  NULL,
  COALESCE(ath.project_name, '(no project)') ||
    CASE WHEN ath.workspace_name IS NOT NULL
         THEN ' · ' || ath.workspace_name ELSE '' END,
  ath.due_on,
  CAST(julianday('now') - julianday(ath.due_on) AS INTEGER),
  ath.workspace_name,
  'check-square'
FROM v_asana_task_health ath
WHERE ath.completed = 0
  AND ath.is_mine = 1
  AND ath.urgency = 'overdue'
  AND COALESCE(ath.project_archived, 0) = 0

UNION ALL

-- Asana: tasks I delegated that are overdue (URGENT)
SELECT
  'asana_overdue_delegated',
  ath.id,
  'urgent',
  ath.name,
  ath.assignee_contact_id,
  NULL,
  'Assigned to ' || COALESCE(ath.assignee_contact_name, ath.assignee_name, 'unknown'),
  ath.due_on,
  CAST(julianday('now') - julianday(ath.due_on) AS INTEGER),
  COALESCE(ath.project_name, ''),
  'user-x'
FROM v_asana_task_health ath
WHERE ath.completed = 0
  AND ath.is_delegated_by_me = 1
  AND ath.urgency = 'overdue'
  AND COALESCE(ath.project_archived, 0) = 0

UNION ALL

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

-- Asana: my tasks due soon (SOON — within 3 days)
SELECT
  'asana_soon_mine',
  ath.id,
  'soon',
  ath.name,
  ath.assignee_contact_id,
  NULL,
  COALESCE(ath.project_name, '(no project)'),
  ath.due_on,
  CAST(julianday(ath.due_on) - julianday('now') AS INTEGER),
  ath.workspace_name,
  'check-square'
FROM v_asana_task_health ath
WHERE ath.completed = 0
  AND ath.is_mine = 1
  AND ath.urgency = 'soon'
  AND COALESCE(ath.project_archived, 0) = 0

UNION ALL

-- Asana: tasks I delegated due soon (SOON — within 3 days)
SELECT
  'asana_soon_delegated',
  ath.id,
  'soon',
  ath.name,
  ath.assignee_contact_id,
  NULL,
  'Assigned to ' || COALESCE(ath.assignee_contact_name, ath.assignee_name, 'unknown'),
  ath.due_on,
  CAST(julianday(ath.due_on) - julianday('now') AS INTEGER),
  COALESCE(ath.project_name, ''),
  'user-check'
FROM v_asana_task_health ath
WHERE ath.completed = 0
  AND ath.is_delegated_by_me = 1
  AND ath.urgency = 'soon'
  AND COALESCE(ath.project_archived, 0) = 0

UNION ALL

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

-- Cold contacts (AWARENESS) — also counts Asana activity now
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
    UNION ALL SELECT MAX(sent_at) FROM slack_messages WHERE contact_id = c.id
    UNION ALL SELECT MAX(modified_at) FROM asana_tasks WHERE assignee_contact_id = c.id
  )),
  CAST(julianday('now') - julianday(
    (SELECT MAX(ts) FROM (
      SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
      UNION ALL SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
      UNION ALL SELECT MAX(t2.occurred_at) FROM transcripts t2
        JOIN transcript_participants tp ON tp.transcript_id = t2.id WHERE tp.contact_id = c.id
      UNION ALL SELECT MAX(sent_at) FROM slack_messages WHERE contact_id = c.id
      UNION ALL SELECT MAX(modified_at) FROM asana_tasks WHERE assignee_contact_id = c.id
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
      UNION ALL SELECT MAX(sent_at) FROM slack_messages WHERE contact_id = c.id
      UNION ALL SELECT MAX(modified_at) FROM asana_tasks WHERE assignee_contact_id = c.id
    )) < datetime('now', '-30 days')
    OR (
      (SELECT MAX(ts) FROM (
        SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
        UNION ALL SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
        UNION ALL SELECT MAX(t2.occurred_at) FROM transcripts t2
          JOIN transcript_participants tp ON tp.transcript_id = t2.id WHERE tp.contact_id = c.id
        UNION ALL SELECT MAX(sent_at) FROM slack_messages WHERE contact_id = c.id
        UNION ALL SELECT MAX(modified_at) FROM asana_tasks WHERE assignee_contact_id = c.id
      )) IS NULL
      AND julianday('now') - julianday(c.created_at) > 30
    )
  )

UNION ALL

-- Asana: unassigned tasks (AWARENESS — every task should have an owner)
SELECT
  'asana_unassigned',
  ath.id,
  'awareness',
  ath.name,
  NULL,
  NULL,
  COALESCE(ath.project_name, '(no project)') ||
    CASE WHEN ath.workspace_name IS NOT NULL
         THEN ' · ' || ath.workspace_name ELSE '' END,
  ath.modified_at,
  CAST(julianday('now') - julianday(ath.modified_at) AS INTEGER),
  'Needs an assignee',
  'user-plus'
FROM v_asana_task_health ath
WHERE ath.completed = 0
  AND ath.is_unassigned = 1
  AND COALESCE(ath.project_archived, 0) = 0

UNION ALL

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
-- v_nudge_summary: rebuild (depends on v_nudge_items)
-- ═══════════════════════════════════════════════════════════════

CREATE VIEW IF NOT EXISTS v_nudge_summary AS
SELECT
  tier,
  COUNT(*) AS count
FROM v_nudge_items
GROUP BY tier;
