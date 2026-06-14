-- Migration 021: Add source_inbox labeling to email response queue
-- Emails forwarded from daniel@benjis.com are clearly tagged so they
-- never get mixed in with Kerry's normal email.

DROP VIEW IF EXISTS v_email_response_queue;
CREATE VIEW IF NOT EXISTS v_email_response_queue AS
SELECT
  e.id,
  e.thread_id,
  e.subject,
  e.from_name,
  e.from_address,
  e.to_addresses,
  e.snippet,
  e.received_at,
  e.contact_id,
  c.name AS contact_name,
  CAST(julianday('now') - julianday(e.received_at) AS INTEGER) AS days_old,
  CASE
    WHEN CAST(julianday('now') - julianday(e.received_at) AS INTEGER) > 3 THEN 'overdue'
    WHEN CAST(julianday('now') - julianday(e.received_at) AS INTEGER) > 1 THEN 'aging'
    ELSE 'fresh'
  END AS urgency,
  CASE
    WHEN e.to_addresses LIKE '%daniel@benjis.com%' THEN 'daniel_inbox'
    WHEN e.account_id = (SELECT id FROM google_accounts WHERE email = 'kerry@benjis.com') THEN 'benjis'
    ELSE 'betterstory'
  END AS source_inbox
FROM emails e
LEFT JOIN contacts c ON e.contact_id = c.id
WHERE e.direction = 'inbound'
  AND e.is_read = 0
  AND e.thread_id NOT IN (
    SELECT thread_id FROM emails
    WHERE direction = 'outbound' AND received_at > e.received_at
  )
  AND e.from_address NOT LIKE '%noreply%'
  AND e.from_address NOT LIKE '%no-reply%'
  AND e.from_address NOT LIKE '%donotreply%'
  AND e.from_address NOT LIKE '%notification%'
  AND e.from_address NOT LIKE '%notifications%'
  AND e.from_address NOT LIKE '%SupplierAP%'
  AND e.from_address NOT LIKE '%quickbooks%'
  AND e.from_address NOT LIKE '%intuit.com%'
  AND e.from_address NOT LIKE '%automated%'
  AND e.from_address NOT LIKE '%gemini-notes%'
  AND e.from_address NOT LIKE '%hello@benjis%'
  AND e.subject NOT LIKE 'Request Created%'
  AND e.subject NOT LIKE '%Invoice - %[0-9]%'
ORDER BY e.received_at ASC;
