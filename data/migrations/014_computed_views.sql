-- Computed Views — Deterministic Calculation Layer
-- These views pre-compute all metrics that commands currently derive ad-hoc.
-- Claude reads from these views and narrates the results — it does not compute them.
-- All statements are idempotent (DROP VIEW IF EXISTS + CREATE VIEW IF NOT EXISTS).

-- ═══════════════════════════════════════════════════════════════
-- v_contact_health: Per-contact activity stats and relationship pulse
-- Used by: /entity-page, /prep, /nudges, /contacts, /dashboard
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

  -- Last activity (most recent across interactions, emails, transcripts)
  (SELECT MAX(ts) FROM (
    SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
    UNION ALL
    SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
    UNION ALL
    SELECT MAX(t.occurred_at) FROM transcripts t
      JOIN transcript_participants tp ON tp.transcript_id = t.id
      WHERE tp.contact_id = c.id
  )) AS last_activity,

  -- Days since last activity (NULL if no activity)
  CAST(julianday('now') - julianday(
    (SELECT MAX(ts) FROM (
      SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
      UNION ALL
      SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
      UNION ALL
      SELECT MAX(t.occurred_at) FROM transcripts t
        JOIN transcript_participants tp ON tp.transcript_id = t.id
        WHERE tp.contact_id = c.id
    ))
  ) AS INTEGER) AS days_silent,

  -- Transcript/call stats
  (SELECT COUNT(DISTINCT tp.transcript_id) FROM transcript_participants tp
    WHERE tp.contact_id = c.id) AS transcripts_total,
  (SELECT COUNT(DISTINCT tp.transcript_id) FROM transcript_participants tp
    JOIN transcripts t ON t.id = tp.transcript_id
    WHERE tp.contact_id = c.id
    AND t.occurred_at > datetime('now', '-30 days')) AS transcripts_30d,

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
-- v_commitment_status: All open/overdue commitments with context
-- Used by: /prep, /nudges, /entity-page, /commitments
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_commitment_status;
CREATE VIEW IF NOT EXISTS v_commitment_status AS
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
    THEN CAST(julianday('now') - julianday(com.deadline_date) AS INTEGER)
    ELSE NULL
  END AS days_overdue,

  -- Days until deadline (NULL if no deadline, negative if past)
  CASE
    WHEN com.deadline_date IS NOT NULL
    THEN CAST(julianday(com.deadline_date) - julianday('now') AS INTEGER)
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


-- ═══════════════════════════════════════════════════════════════
-- v_nudge_items: Unified nudge feed with urgency tiers
-- Used by: /nudges, /nudges-view, /dashboard
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
    -- Either last activity was 30+ days ago
    (SELECT MAX(ts) FROM (
      SELECT MAX(occurred_at) AS ts FROM contact_interactions WHERE contact_id = c.id
      UNION ALL SELECT MAX(received_at) FROM emails WHERE contact_id = c.id
      UNION ALL SELECT MAX(t2.occurred_at) FROM transcripts t2
        JOIN transcript_participants tp ON tp.transcript_id = t2.id WHERE tp.contact_id = c.id
    )) < datetime('now', '-30 days')
    -- Or contact has zero activity and was added 30+ days ago
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


-- ═══════════════════════════════════════════════════════════════
-- v_nudge_summary: Counts by tier for dashboard/header pills
-- Used by: /nudges-view, /dashboard
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_nudge_summary;
CREATE VIEW IF NOT EXISTS v_nudge_summary AS
SELECT
  tier,
  COUNT(*) AS count
FROM v_nudge_items
GROUP BY tier;


-- ═══════════════════════════════════════════════════════════════
-- v_discovery_candidates: Frequent emailers not in CRM
-- Used by: /discover
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_discovery_candidates;
CREATE VIEW IF NOT EXISTS v_discovery_candidates AS
SELECT
  e.from_address,
  e.from_name,
  COUNT(*) AS email_count,
  COUNT(DISTINCT e.thread_id) AS thread_count,
  MAX(e.received_at) AS last_email,
  MIN(e.received_at) AS first_email,
  CAST(julianday('now') - julianday(MAX(e.received_at)) AS INTEGER) AS days_since_last,

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
GROUP BY e.from_address
HAVING email_count >= 2
ORDER BY relevance_score DESC, last_email DESC;


-- ═══════════════════════════════════════════════════════════════
-- v_meeting_prep: Per-event prep data for upcoming meetings
-- Used by: /prep, /week-view
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_meeting_prep;
CREATE VIEW IF NOT EXISTS v_meeting_prep AS
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


-- ═══════════════════════════════════════════════════════════════
-- v_project_health: Per-project progress and risk indicators
-- Used by: /project-page, /dashboard, /nudges
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_project_health;
CREATE VIEW IF NOT EXISTS v_project_health AS
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
    THEN CAST(julianday(p.target_date) - julianday('now') AS INTEGER)
    ELSE NULL
  END AS days_to_target,

  -- Last activity
  (SELECT MAX(created_at) FROM activity_log
    WHERE entity_type = 'project' AND entity_id = p.id) AS last_activity,
  CAST(julianday('now') - julianday(COALESCE(
    (SELECT MAX(created_at) FROM activity_log WHERE entity_type = 'project' AND entity_id = p.id),
    p.created_at
  )) AS INTEGER) AS days_since_activity,

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


-- ═══════════════════════════════════════════════════════════════
-- v_email_response_queue: Inbound emails needing a reply
-- Used by: /email-hub, /nudges, /dashboard
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_email_response_queue;
CREATE VIEW IF NOT EXISTS v_email_response_queue AS
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
  CAST(julianday('now') - julianday(e.received_at) AS INTEGER) AS days_old,
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
