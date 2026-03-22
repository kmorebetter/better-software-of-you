-- Email Opportunity Detection
-- Surfaces inbound Benjis emails that look like new business opportunities.
-- Adds a standalone v_email_opportunities view and integrates into v_nudge_items.

-- ═══════════════════════════════════════════════════════════════
-- v_email_opportunities: Inbound Benjis emails matching opportunity signals
-- Used by: /nudges, /nudges-view, /dashboard, /morning
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_email_opportunities;
CREATE VIEW IF NOT EXISTS v_email_opportunities AS
SELECT
  raw.id,
  raw.gmail_id,
  raw.thread_id,
  raw.subject,
  raw.from_name,
  raw.from_address,
  raw.snippet,
  raw.received_at,
  raw.contact_id,
  raw.account_id,
  raw.days_old,
  raw.tier,
  raw.match_reason
FROM (
  SELECT
    e.id,
    e.gmail_id,
    e.thread_id,
    e.subject,
    e.from_name,
    e.from_address,
    e.snippet,
    e.received_at,
    e.contact_id,
    e.account_id,

    -- Age in days
    CAST(julianday('now') - julianday(e.received_at) AS INTEGER) AS days_old,

    -- Urgency tier based on age
    CASE
      WHEN CAST(julianday('now') - julianday(e.received_at) AS INTEGER) < 2 THEN 'urgent'
      WHEN CAST(julianday('now') - julianday(e.received_at) AS INTEGER) <= 5 THEN 'soon'
      ELSE 'awareness'
    END AS tier,

    -- Which keyword(s) matched (for transparency)
    CASE
      WHEN e.subject LIKE '%Registration Form%' THEN 'website inquiry'
      WHEN LOWER(e.subject) LIKE '%rfp%' OR LOWER(e.snippet) LIKE '%rfp%' THEN 'RFP'
      WHEN LOWER(e.subject) LIKE '%rfq%' OR LOWER(e.snippet) LIKE '%rfq%' THEN 'RFQ'
      WHEN LOWER(e.subject) LIKE '%quote%' OR LOWER(e.snippet) LIKE '%quote%' THEN 'quote request'
      WHEN LOWER(e.subject) LIKE '%proposal%' OR LOWER(e.snippet) LIKE '%proposal%' THEN 'proposal'
      WHEN LOWER(e.subject) LIKE '%pricing%' OR LOWER(e.snippet) LIKE '%pricing%' THEN 'pricing inquiry'
      WHEN LOWER(e.subject) LIKE '%plants for%' OR LOWER(e.snippet) LIKE '%plants for%' THEN 'plants request'
      WHEN LOWER(e.subject) LIKE '%interior plant%' OR LOWER(e.snippet) LIKE '%interior plant%' THEN 'interior plants'
      WHEN LOWER(e.subject) LIKE '%planting%' OR LOWER(e.snippet) LIKE '%planting%' THEN 'planting project'
      WHEN LOWER(e.subject) LIKE '%biophilic%' OR LOWER(e.snippet) LIKE '%biophilic%' THEN 'biophilic design'
      WHEN LOWER(e.subject) LIKE '%new office%' OR LOWER(e.snippet) LIKE '%new office%' THEN 'new office'
      WHEN LOWER(e.subject) LIKE '%renovation%' OR LOWER(e.snippet) LIKE '%renovation%' THEN 'renovation'
      WHEN LOWER(e.subject) LIKE '%interested in%your%serv%' OR LOWER(e.snippet) LIKE '%interested in%your%serv%' THEN 'service inquiry'
      WHEN LOWER(e.subject) LIKE '%consultation%' OR LOWER(e.snippet) LIKE '%consultation%' THEN 'consultation'
      WHEN LOWER(e.subject) LIKE '%inquiry%' OR LOWER(e.snippet) LIKE '%inquiry%' THEN 'general inquiry'
      WHEN LOWER(e.subject) LIKE '%plant maintenance%' OR LOWER(e.snippet) LIKE '%plant maintenance%' THEN 'maintenance inquiry'
      WHEN LOWER(e.subject) LIKE '%plant program%' OR LOWER(e.snippet) LIKE '%plant program%' THEN 'plant program'
      ELSE 'opportunity signal'
    END AS match_reason,

    -- Row number per thread — keep only the latest email per conversation
    ROW_NUMBER() OVER (PARTITION BY e.thread_id ORDER BY e.received_at DESC) AS rn

  FROM emails e
  WHERE e.account_id = 2  -- Benjis account only
    AND e.direction = 'inbound'

  -- Must match at least one opportunity keyword
  AND (
    -- Website form submissions
    e.subject LIKE '%Registration Form%'
    -- Quote / proposal / pricing
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%quote%'
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%proposal%'
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%pricing%'
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%rfp%'
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%rfq%'
    -- Plant-specific signals
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%plants for%'
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%interior plant%'
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%planting%'
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%biophilic%'
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%plant maintenance%'
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%plant program%'
    -- Space / project signals
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%new office%'
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%renovation%'
    -- General inquiry language
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%consultation%'
    OR LOWER(e.subject || ' ' || COALESCE(e.snippet, '')) LIKE '%inquiry%'
  )

  -- Exclude noise (use %domain% pattern to handle "Name <email>" format)
  -- Allow hello@benjis.com through (website form submissions)
  AND (e.from_address LIKE '%hello@benjis.com%' OR e.from_address NOT LIKE '%@benjis.com%')
  AND e.from_address NOT LIKE '%quickbooks%'            -- invoicing
  AND e.from_address NOT LIKE '%intuit%'                -- invoicing
  AND e.from_address NOT LIKE '%noreply%'               -- automated
  AND e.from_address NOT LIKE '%no-reply%'              -- automated
  AND e.from_address NOT LIKE '%notifications%'         -- automated
  AND e.from_address NOT LIKE '%@calendar.google.com%'  -- calendar
  AND e.from_address NOT LIKE '%gemini-notes%'          -- meeting notes
  AND e.from_address NOT LIKE '%@google.com%'           -- Google notifications
  AND e.from_address NOT LIKE '%@ramp.com%'             -- expense mgmt
  AND e.from_address NOT LIKE '%@rogers.com%'           -- telecom
  AND e.from_address NOT LIKE '%corrigopro%'            -- work order system
  AND e.from_address NOT LIKE '%corrigo%'               -- work order system
  AND e.from_address NOT LIKE '%newsletter%'
  AND e.from_address NOT LIKE '%digest%'
  AND e.from_address NOT LIKE '%automated%'
  AND e.from_address NOT LIKE '%mailer-daemon%'
  AND e.from_address NOT LIKE '%@yardi.com%'            -- vendor management
  AND e.from_address NOT LIKE '%@attio.com%'            -- CRM marketing

  -- Exclude subjects that are clearly not opportunities
  AND e.subject NOT LIKE '%Invoice%'                    -- AR/AP noise
  AND e.subject NOT LIKE '%invoice%'
  AND e.subject NOT LIKE '%work order%'                 -- maintenance tickets
  AND e.subject NOT LIKE '%Timesheet%'
  AND e.subject NOT LIKE '%[Case:%'                     -- support tickets
  AND e.subject NOT LIKE '%Apprenticeship%'             -- job inquiries
  AND e.subject NOT LIKE '%Job%Application%'            -- job inquiries
  AND e.subject NOT LIKE '%Resume%'                     -- job inquiries

  ORDER BY e.received_at DESC
) raw
WHERE raw.rn = 1
ORDER BY raw.received_at DESC;


-- ═══════════════════════════════════════════════════════════════
-- v_nudge_items: Rebuild with opportunity detection added
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

-- ★ Benjis business opportunities (URGENT/SOON/AWARENESS by age)
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
-- v_nudge_summary: Rebuild (depends on v_nudge_items)
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_nudge_summary;
CREATE VIEW IF NOT EXISTS v_nudge_summary AS
SELECT
  tier,
  COUNT(*) AS count
FROM v_nudge_items
GROUP BY tier;
