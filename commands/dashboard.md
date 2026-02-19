---
description: Generate and open a unified HTML dashboard
allowed-tools: ["Bash", "Read", "Write"]
---

# Generate Dashboard

Generate a self-contained HTML dashboard showing a unified view across all installed modules.

## Step 1: Gather Data

Query `${CLAUDE_PLUGIN_ROOT}/data/soy.db` for all relevant data. Check which modules are installed first:
```sql
SELECT name FROM modules WHERE enabled = 1;
```

**Always query:**
```sql
-- Contact overview
SELECT COUNT(*) as total, SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active FROM contacts;

-- Recent contacts
SELECT id, name, company, email, status, updated_at FROM contacts
WHERE status = 'active' ORDER BY updated_at DESC LIMIT 8;

-- Recent activity
SELECT al.*, CASE al.entity_type
    WHEN 'contact' THEN (SELECT name FROM contacts WHERE id = al.entity_id)
    WHEN 'project' THEN (SELECT name FROM projects WHERE id = al.entity_id)
    ELSE al.entity_type || ' #' || al.entity_id
  END as entity_name
FROM activity_log al ORDER BY al.created_at DESC LIMIT 15;
```

**If CRM module installed:**
```sql
-- Upcoming follow-ups
SELECT f.*, c.name as contact_name FROM follow_ups f
JOIN contacts c ON f.contact_id = c.id
WHERE f.status = 'pending' ORDER BY f.due_date ASC LIMIT 8;
```

**If Project Tracker installed:**
```sql
-- Project summary
SELECT status, COUNT(*) as count FROM projects GROUP BY status;

-- Active projects with clients
SELECT p.id, p.name, p.status, p.priority, p.target_date, c.name as client_name
FROM projects p LEFT JOIN contacts c ON p.client_id = c.id
WHERE p.status IN ('active', 'planning') ORDER BY p.priority DESC, p.updated_at DESC;

-- Task summary
SELECT status, COUNT(*) as count FROM tasks GROUP BY status;

-- Overdue tasks
SELECT t.title, t.due_date, p.name as project_name FROM tasks t
JOIN projects p ON t.project_id = p.id
WHERE t.due_date < date('now') AND t.status NOT IN ('done');
```

## Step 2: Generate HTML

Read the base template from `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/template-base.html` and the component patterns from `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/component-patterns.md`.

Generate a self-contained HTML file following the design system. Include sections based on installed modules:

**Always:** Header with stat pills, Recent Activity timeline
**CRM:** Contacts list, Upcoming Follow-ups
**Project Tracker:** Active Projects, Task Overview, Overdue Items

Only include sections for installed modules. Adapt the grid layout to the number of sections.

Write the HTML to `${CLAUDE_PLUGIN_ROOT}/output/dashboard.html`.

## Step 3: Open

Run: `open "${CLAUDE_PLUGIN_ROOT}/output/dashboard.html"`

Tell the user the dashboard is generated and opened.
