---
description: Add, edit, list, or find projects and tasks
allowed-tools: ["Bash", "Read"]
argument-hint: <project name> [--client <name>] [--status <status>] or "list" or "task <project> <task title>"
---

# Project Management

Handle project and task operations based on $ARGUMENTS. Database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

## Determine the Operation

- **No arguments or "list"** → List active projects
- **"task <project> <title>"** → Add a task to a project
- **Project name with flags** → Create a new project
- **References existing project + changes** → Edit that project

## Add a Project

Parse project name and optional flags (--client, --status, --priority, --target).

If --client is specified, look up the contact:
```sql
SELECT id FROM contacts WHERE name LIKE '%client_name%';
```

Run both statements in a single sqlite3 call (so `last_insert_rowid()` works correctly):

```sql
INSERT INTO projects (name, description, client_id, status, priority, start_date, target_date)
VALUES (?, ?, ?, ?, ?, date('now'), ?);
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('project', last_insert_rowid(), 'created', json_object('name', ?));
```

Confirm with project details. If client was linked, mention the connection.

## List Projects

```sql
SELECT p.id, p.name, p.status, p.priority, p.target_date, c.name as client
FROM projects p LEFT JOIN contacts c ON p.client_id = c.id
WHERE p.status NOT IN ('completed', 'cancelled')
ORDER BY
  CASE p.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
  p.updated_at DESC;
```

Include task counts per project:
```sql
SELECT project_id, status, COUNT(*) as count FROM tasks GROUP BY project_id, status;
```

## Add a Task

```sql
INSERT INTO tasks (project_id, title, status, priority)
VALUES (?, ?, 'todo', ?);
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('project', ?, 'task_added', json_object('task', ?));
```

## Edit a Project

Update specified fields, set `updated_at = datetime('now')`, log the change.

## Update Task Status

```sql
UPDATE tasks SET status = ?, updated_at = datetime('now'),
  completed_at = CASE WHEN ? = 'done' THEN datetime('now') ELSE NULL END
WHERE id = ?;
```
