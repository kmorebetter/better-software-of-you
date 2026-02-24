---
description: Generate an AI project brief with full context
allowed-tools: ["Bash", "Read"]
argument-hint: <project name or id>
---

# AI Project Brief

Generate a comprehensive project brief for the project specified in $ARGUMENTS.

Read the project scoring methodology before generating:
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/project-tracker/references/project-methodology.md`

## Step 1: Gather All Data

Query `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`:

```sql
-- Project details
SELECT * FROM projects WHERE name LIKE '%$ARGUMENTS%' OR id = '$ARGUMENTS';

-- Tasks
SELECT * FROM tasks WHERE project_id = ?
ORDER BY CASE status WHEN 'blocked' THEN 1 WHEN 'in_progress' THEN 2 WHEN 'todo' THEN 3 ELSE 4 END, priority DESC;

-- Milestones
SELECT * FROM milestones WHERE project_id = ? ORDER BY target_date;

-- Notes
SELECT * FROM notes WHERE entity_type = 'project' AND entity_id = ?
ORDER BY created_at DESC;

-- Activity log
SELECT * FROM activity_log WHERE entity_type = 'project' AND entity_id = ?
ORDER BY created_at DESC LIMIT 20;

-- Tags
SELECT t.name, t.color FROM tags t
JOIN entity_tags et ON et.tag_id = t.id
WHERE et.entity_type = 'project' AND et.entity_id = ?;
```

**If CRM module installed:**
```sql
-- Client details (if project has a client)
SELECT * FROM contacts WHERE id = (SELECT client_id FROM projects WHERE id = ?);

-- Recent interactions with client
SELECT * FROM contact_interactions WHERE contact_id = ?
ORDER BY occurred_at DESC LIMIT 10;
```

## Step 2: Generate the Brief

Write a project brief covering:

1. **Status Snapshot** — current status, priority, timeline (start → target), days remaining/overdue, momentum (use velocity formula from project-methodology.md), risk level (use threshold table from project-methodology.md with reasoning)
2. **Progress** — tasks done vs total, breakdown by status, milestone status
3. **Blockers & Risks** — blocked tasks, overdue items, missed milestones
4. **Client Context** (if CRM installed & project has client) — who the client is, recent interactions. Pull from `relationship_scores`: show depth, trajectory, follow-through percentages. If no conversation data, show interaction frequency (interactions/week over 30 days).
5. **Recent Activity** — what happened recently on this project
6. **Next Steps** — use the action prioritization formula from project-methodology.md. Ranked order: unblock blocked tasks → overdue tasks → approaching milestones → tasks due soon → client follow-ups. Each action must be specific and reference data.

Present as a clean, professional brief. This should feel like something you could share with a stakeholder.
