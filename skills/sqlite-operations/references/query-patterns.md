# Common Query Patterns

## Computed Views First

The database ships pre-computed SQL views (defined in `data/migrations/014_computed_views.sql`
and `020_slack_views.sql`) that already do the deterministic math — counts, days-silent,
overdue tiers, completion percentages. **If a view column gives you the number, read it
directly. Do not re-derive it with an ad-hoc JOIN or subquery.** Claude narrates the numbers;
it does not recompute them. This mirrors the "Computed Views" rule in the project's CLAUDE.md.

| View | What it provides | Use instead of |
|------|-----------------|----------------|
| `v_contact_health` | Per-contact: email/interaction/Slack counts, days silent, relationship depth/trajectory, open commitments, next meeting | Ad-hoc JOINs across emails + interactions + commitments + relationship_scores |
| `v_commitment_status` | All open/overdue commitments with owner name, source call, days overdue, urgency tier | Manual commitment queries with CASE statements |
| `v_nudge_items` | Unified nudge feed: all urgency tiers, all entity types, pre-computed days and context | Separate queries per nudge type (follow-ups, commitments, tasks, cold contacts, etc.) |
| `v_nudge_summary` | Count per tier (urgent/soon/awareness) | Manually summing nudge queries |
| `v_discovery_candidates` | Frequent emailers not in CRM with relevance scores | The inline discovery query with a wall of NOT LIKE filters |
| `v_meeting_prep` | Per-event: time context, minutes until, duration, project info | Ad-hoc calendar queries with time calculations |
| `v_project_health` | Per-project: task counts, completion %, overdue tasks, days to target, milestones, client name | Separate task/milestone/activity queries per project |
| `v_email_response_queue` | Inbound emails needing reply with age and urgency | Complex thread-matching subqueries |

Examples:
```sql
-- Contact health snapshot — everything in one row, no manual counting
SELECT * FROM v_contact_health WHERE id = ?;

-- Project rollups with client name and completion %
SELECT name, client_name, completion_pct, overdue_tasks FROM v_project_health;

-- What needs attention, already tiered (tier is text — order it explicitly)
SELECT * FROM v_nudge_items
ORDER BY CASE tier WHEN 'urgent' THEN 0 WHEN 'soon' THEN 1 ELSE 2 END;
```

**Ad-hoc joins below are only for data no view covers** (free-text search, activity
logging, tag lookups, raw date filtering). When a view already exposes the column, prefer it.

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

## Trivial Joins

For a plain lookup a view doesn't cover, a direct join is fine. (For per-contact or
per-project rollups, use `v_contact_health` / `v_project_health` instead — they already
carry `client_name`, counts, and days-silent.)

```sql
-- Projects with client names (simple label join — no rollups)
SELECT p.*, c.name as client_name, c.email as client_email
FROM projects p LEFT JOIN contacts c ON p.client_id = c.id;
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
