---
description: Quick status report for a project
allowed-tools: ["Bash"]
argument-hint: <project name or id>
---

# Quick Project Status

Generate a concise status update for the project specified in $ARGUMENTS.

Query `${CLAUDE_PLUGIN_ROOT}/data/soy.db`:

```sql
-- Project overview
SELECT p.*, c.name as client_name
FROM projects p LEFT JOIN contacts c ON p.client_id = c.id
WHERE p.name LIKE '%$ARGUMENTS%' OR p.id = '$ARGUMENTS';

-- Task breakdown
SELECT status, COUNT(*) as count FROM tasks WHERE project_id = ? GROUP BY status;

-- Overdue tasks
SELECT title, due_date FROM tasks
WHERE project_id = ? AND due_date < date('now') AND status NOT IN ('done');

-- Next milestone
SELECT * FROM milestones WHERE project_id = ? AND status = 'pending'
ORDER BY target_date ASC LIMIT 1;

-- Last 5 activities
SELECT action, details, created_at FROM activity_log
WHERE entity_type = 'project' AND entity_id = ?
ORDER BY created_at DESC LIMIT 5;
```

Present as a quick, scannable status:
- One-line summary (status + progress percentage)
- Task breakdown (todo/in-progress/done/blocked)
- Overdue items (if any)
- Next milestone (if any)
- Last few activities

Keep it short — this is for a quick check-in, not a full brief. Suggest `/project-brief <name>` for the full version.
