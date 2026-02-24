---
description: View the activity timeline
allowed-tools: ["Bash"]
argument-hint: [today | week | all] [contact/project name]
---

# Activity Log

Show the activity timeline from `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`.

Default: last 7 days. Parse $ARGUMENTS for time range and optional entity filter.

First, check which modules are installed:
```sql
SELECT name FROM modules WHERE enabled = 1;
```

Then query the activity log. Build the entity_name CASE statement based on installed modules:
- Always include: `WHEN 'contact' THEN (SELECT name FROM contacts WHERE id = al.entity_id)`
- If project-tracker installed, add: `WHEN 'project' THEN (SELECT name FROM projects WHERE id = al.entity_id)`
- Fallback: `ELSE al.entity_type || ' #' || al.entity_id`

```sql
SELECT al.created_at, al.entity_type, al.entity_id, al.action, al.details,
  CASE al.entity_type
    WHEN 'contact' THEN (SELECT name FROM contacts WHERE id = al.entity_id)
    -- include project CASE only if project-tracker module is installed
    ELSE al.entity_type || ' #' || al.entity_id
  END as entity_name
FROM activity_log al
WHERE al.created_at >= date('now', '-7 days')
ORDER BY al.created_at DESC;
```

Adjust the WHERE clause based on arguments:
- "today" → `date('now')`
- "week" → `date('now', '-7 days')`
- "all" → no date filter
- A name → filter to that entity

Present as a clean timeline grouped by date. Use human-readable timestamps ("2 hours ago", "yesterday").
