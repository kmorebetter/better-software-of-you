# Common Query Patterns

## Text Search
```sql
-- Search contacts by name or company
SELECT * FROM contacts WHERE name LIKE '%term%' OR company LIKE '%term%';

-- Search across multiple entity types
SELECT 'contact' as type, id, name as title FROM contacts WHERE name LIKE '%term%'
UNION ALL
SELECT 'project' as type, id, name as title FROM projects WHERE name LIKE '%term%'
UNION ALL
SELECT 'note' as type, id, substr(content, 1, 80) as title FROM notes WHERE content LIKE '%term%';
```

## Cross-Module Joins
```sql
-- Projects with client names
SELECT p.*, c.name as client_name, c.email as client_email
FROM projects p LEFT JOIN contacts c ON p.client_id = c.id;

-- All data for a contact (use contact_id = ?)
SELECT c.*,
  (SELECT COUNT(*) FROM notes WHERE entity_type='contact' AND entity_id=c.id) as note_count,
  (SELECT COUNT(*) FROM projects WHERE client_id=c.id) as project_count,
  (SELECT COUNT(*) FROM follow_ups WHERE contact_id=c.id AND status='pending') as pending_followups
FROM contacts c WHERE c.id = ?;
```

## Activity Logging

**Important:** When using `last_insert_rowid()`, the INSERT and the activity_log INSERT must be in the same `sqlite3` call. Use a heredoc to send both statements together.

```sql
-- Always log after data changes (run together with the INSERT)
INSERT INTO contacts (name, email) VALUES ('Jane', 'jane@example.com');
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('contact', last_insert_rowid(), 'created', json_object('name', 'Jane'));

-- Readable activity timeline
SELECT al.created_at, al.action, al.details,
  CASE al.entity_type
    WHEN 'contact' THEN (SELECT name FROM contacts WHERE id = al.entity_id)
    WHEN 'project' THEN (SELECT name FROM projects WHERE id = al.entity_id)
  END as entity_name
FROM activity_log al ORDER BY al.created_at DESC LIMIT 20;
```

## Date Filtering
```sql
-- Today
WHERE created_at >= date('now')
-- Last 7 days
WHERE created_at >= date('now', '-7 days')
-- Overdue items
WHERE due_date < date('now') AND status NOT IN ('completed', 'done')
-- Next 7 days
WHERE due_date BETWEEN date('now') AND date('now', '+7 days')
```

## Tags
```sql
-- Get tags for an entity
SELECT t.name, t.color FROM tags t
JOIN entity_tags et ON et.tag_id = t.id
WHERE et.entity_type = ? AND et.entity_id = ?;

-- Find entities with a specific tag
SELECT et.entity_type, et.entity_id FROM entity_tags et
JOIN tags t ON t.id = et.tag_id WHERE t.name = ?;
```
