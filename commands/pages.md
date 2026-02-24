---
description: List and open generated HTML pages (dashboards, entity pages, project briefs)
allowed-tools: ["Bash", "Read"]
argument-hint: [page name to open]
---

# List & Open Generated Pages

If **$ARGUMENTS is provided**, find and open a matching page.

Search for a match:
```sql
SELECT filename, entity_name, view_type, updated_at
FROM generated_views
WHERE entity_name LIKE '%$ARGUMENTS%' OR filename LIKE '%$ARGUMENTS%'
ORDER BY updated_at DESC LIMIT 1;
```

- If found, open it: `open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/{filename}"`
- If not found, say "No page found matching '$ARGUMENTS'." and show all available pages (fall through to the no-arguments flow below).

If **no arguments**, list all available pages.

Query all generated views:
```sql
SELECT view_type, entity_type, entity_name, filename, updated_at
FROM generated_views ORDER BY updated_at DESC;
```

Also check for HTML files in output/ that aren't registered:
```bash
ls "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/"*.html 2>/dev/null
```

Present results as a table with columns: **Page Name**, **Type**, **Last Updated** (human-readable, e.g. "2 days ago").

If there are unregistered HTML files in output/ not found in generated_views, list them separately as "Unregistered pages."

Tell the user: "Run `/pages <name>` to open any page, or `/dashboard` to regenerate the dashboard."
