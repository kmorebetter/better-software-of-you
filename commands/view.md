---
description: Generate a specialized module view or custom report
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: <contacts | projects | custom description>
---

# Generate Module View

Generate a specialized HTML view based on $ARGUMENTS. Unlike `/dashboard` (which has a fixed layout), `/view` generates flexible, purpose-built pages tailored to what the user asks for. The layout should match the data — a contact directory looks different from a project board looks different from a custom report.

## Determine View Type

- **"contacts"** → Run `/contacts` (tell user: "Generating your Contacts Index...")
- **"projects"** → Project board view
- **"emails"** or **"email"** or **"gmail"** → Run `/email-hub` (tell user: "Generating your Email Hub...")
- **"calendar"** or **"week"** or **"schedule"** → Run `/week-view`
- **"conversations"** or **"transcripts"** or **"calls"** → Run `/conversations-view`
- **"decisions"** → Run `/decision-journal-view`
- **"journal"** or **"diary"** → Run `/journal-view`
- **"notes"** → Run `/notes-view`
- **"network"** or **"map"** → Run `/network-map`
- **Custom text** → Generate a custom view based on the description

## Contact Directory View

Query `${CLAUDE_PLUGIN_ROOT}/data/soy.db`:
```sql
SELECT c.*,
  (SELECT COUNT(*) FROM notes WHERE entity_type='contact' AND entity_id=c.id) as note_count,
  (SELECT COUNT(*) FROM projects WHERE client_id=c.id) as project_count,
  GROUP_CONCAT(DISTINCT t.name) as tags
FROM contacts c
LEFT JOIN entity_tags et ON et.entity_type='contact' AND et.entity_id=c.id
LEFT JOIN tags t ON t.id=et.tag_id
WHERE c.status = 'active'
GROUP BY c.id ORDER BY c.updated_at DESC;
```

If CRM installed, also get pending follow-ups per contact.

Layout: Card grid showing each contact with name, company, email, tags, project count, and last activity date. Each contact name links to their entity page if one exists.

**Write to:** `${CLAUDE_PLUGIN_ROOT}/output/contacts.html` (always this filename — the nav bar links here)

**Register:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Contacts', 'contacts.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

## Project Board View

Query projects with tasks:
```sql
SELECT p.*, c.name as client_name,
  (SELECT COUNT(*) FROM tasks WHERE project_id=p.id AND status='todo') as todo_count,
  (SELECT COUNT(*) FROM tasks WHERE project_id=p.id AND status='in_progress') as active_count,
  (SELECT COUNT(*) FROM tasks WHERE project_id=p.id AND status='done') as done_count,
  (SELECT COUNT(*) FROM tasks WHERE project_id=p.id AND status='blocked') as blocked_count
FROM projects p LEFT JOIN contacts c ON p.client_id = c.id
WHERE p.status NOT IN ('completed', 'cancelled')
ORDER BY p.priority DESC;
```

Layout: Kanban-style columns by status (Planning, Active, Paused) or card list with task progress bars. Each project name links to its project page if one exists.

**Write to:** `${CLAUDE_PLUGIN_ROOT}/output/projects.html` (always this filename)

**Register:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Projects', 'projects.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

## Custom View

For custom descriptions, interpret what the user wants, query the relevant data, and generate an appropriate HTML layout. Use the design system from `skills/dashboard-generation/references/`.

## Navigation

**Every view must include the primary nav bar** from `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/navigation-patterns.md`. Read it before generating any HTML. The nav bar is consistent across all pages — same sections, same counts, same order.

## Output

Read template and patterns from `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/`.
Write HTML to `${CLAUDE_PLUGIN_ROOT}/output/{view-name}.html`.
Register in `generated_views`.
Open with `open <filepath>`.
