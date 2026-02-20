---
description: Generate all HTML views — dashboard, entity pages for every contact, project pages, and all module views
allowed-tools: ["Bash", "Read", "Write"]
---

# Build All Views

Generate every HTML view in the system. This is the "build everything" command — it produces the full, detailed version of every page, using each command's complete spec. No shortcuts, no light versions.

## Step 0: Auto-Sync External Data

Before building anything, ensure data is fresh. Follow the auto-sync procedure in CLAUDE.md — check `gmail_last_synced` and `calendar_last_synced` in `soy_meta`, and sync if stale (>15 min) or never synced. Do this silently.

## Step 1: Inventory

Query `${CLAUDE_PLUGIN_ROOT}/data/soy.db`:

```sql
-- What modules are installed
SELECT name FROM modules WHERE enabled = 1;

-- All active contacts (these each get an entity page)
SELECT id, name FROM contacts WHERE status = 'active';

-- All active/planning projects (these each get a project page)
SELECT id, name FROM projects WHERE status IN ('active', 'planning');

-- What views already exist (to report what's new vs. updated)
SELECT filename, updated_at FROM generated_views;
```

## Step 2: Generate Everything

Run each command's FULL specification. Do NOT generate lightweight summaries — use the complete command file for each page. Generate in this order:

### Entity Pages (one per active contact)

For EACH active contact, run the complete `/entity-page` workflow:
- Read the reference implementation (`entity-page-reference.html`)
- Read all design references
- Gather ALL data for that contact (interactions, emails, calendar, transcripts, commitments, relationships, notes, tags, projects)
- Synthesize intelligence (relationship context narrative, company intel, expanded email threads, discovery questions)
- Generate the full HTML with navigation
- Register in `generated_views`

**This is the most important step.** Each entity page must be the rich, researched version — not a card with name and email. Read `${CLAUDE_PLUGIN_ROOT}/commands/entity-page.md` and follow it completely for each contact.

### Project Pages (one per active/planning project)

For EACH active or planning project, run the complete `/project-page` workflow:
- Read `${CLAUDE_PLUGIN_ROOT}/commands/project-page.md` and follow it completely
- Full data gathering, intelligence synthesis, risk assessment, task checklist
- Register in `generated_views`

### Module Views (one per installed module)

Generate each module's dedicated view if the module is installed:

| Module | Command spec to follow | Output file |
|--------|----------------------|-------------|
| Gmail | `commands/email-hub.md` | `email-hub.html` |
| Calendar | `commands/week-view.md` | `week-view.html` |
| Conversation Intelligence | `commands/conversations-view.md` | `conversations.html` |
| Decision Log | `commands/decision-journal-view.md` | `decision-journal.html` |
| Journal | `commands/journal-view.md` | `journal.html` |

For each: read the full command file and follow it completely.

### Network Map

If CRM module is installed and there are 2+ contacts:
- Follow `commands/network-map.md` completely
- Generate the D3.js interactive visualization

### Dashboard (LAST)

Generate the dashboard LAST so it can link to all the entity pages and module views that now exist:
- Follow `commands/dashboard.md` completely
- The nav bar will populate with all the pages generated above
- Contact names throughout will link to entity pages

## Step 3: Open Dashboard

After everything is generated, open the dashboard:
```
open "${CLAUDE_PLUGIN_ROOT}/output/dashboard.html"
```

## Step 4: Report

Tell the user what was built:

"**Built X pages:**
- **Y entity pages**: [list contact names]
- **Z project pages**: [list project names]
- **N module views**: [list which ones]
- Dashboard with links to everything

All pages are in `output/` and linked via the nav bar."

## Important

- **Do NOT skip the intelligence synthesis steps.** Entity pages must include relationship context narratives, company intel, email thread summaries, and discovery questions — not just raw data.
- **Do NOT generate lightweight card versions.** Every page uses its full command specification.
- **Generate entity pages BEFORE the dashboard** so the dashboard can link to them.
- If there are many contacts (10+), this will take a while. That's fine — quality over speed.
