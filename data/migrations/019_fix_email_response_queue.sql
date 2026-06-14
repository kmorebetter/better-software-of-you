-- Migration 019: Filter automated senders from v_email_response_queue
-- Removes QuickBooks notifications, AP system emails, and other automated senders
-- that don't require a human reply.

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
  -- Must not have been replied to in this thread
  AND e.thread_id NOT IN (
    SELECT thread_id FROM emails
    WHERE direction = 'outbound' AND received_at > e.received_at
  )
  -- Filter automated/notification senders
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
  -- Filter automated subject patterns
  AND e.subject NOT LIKE 'Request Created%'
  AND e.subject NOT LIKE '%Invoice - %[0-9]%'
ORDER BY e.received_at ASC;
