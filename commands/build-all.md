---
description: Generate all HTML views — dashboard, entity pages for every contact, project pages, and all module views
allowed-tools: ["Bash", "Read", "Write", "Glob"]
---

# Build All Views

Generate every HTML view in the system. Uses **incremental builds** — only regenerates pages whose underlying data has changed since the last build. Use `/build-all force` to bypass staleness checks and rebuild everything.

## Step 0: Parse Arguments

Check `$ARGUMENTS` for the `force` flag:
- If arguments contain "force" → set `FORCE_REBUILD = true` — skip all staleness checks, rebuild everything
- Otherwise → `FORCE_REBUILD = false` — use incremental build

## Step 1: Auto-Sync External Data

Before building anything, ensure data is fresh. Follow the auto-sync procedure in CLAUDE.md — check `gmail_last_synced` and `calendar_last_synced` in `soy_meta`, and sync if stale (>15 min) or never synced. Also check `transcripts_last_scanned` and scan if >1 hour stale. Do this silently.

## Step 2: Pre-Compute Build Context

Run ALL inventory and sidebar queries in a **single step** so results can be reused across all page generations. Do NOT re-run these queries per page.

```sql
-- What modules are installed
SELECT name FROM modules WHERE enabled = 1;

-- All active contacts (these each get an entity page)
SELECT id, name FROM contacts WHERE status = 'active' ORDER BY name;

-- All active/planning projects (these each get a project page)
SELECT id, name FROM projects WHERE status IN ('active', 'planning') ORDER BY name;

-- All analyzed transcripts (these each get a transcript detail page)
SELECT id, title FROM transcripts
WHERE summary IS NOT NULL
   OR call_intelligence IS NOT NULL
   OR id IN (SELECT DISTINCT transcript_id FROM conversation_metrics)
ORDER BY title;

-- What views already exist (filenames + timestamps for staleness comparison)
SELECT view_type, entity_type, entity_id, entity_name, filename, updated_at FROM generated_views;

-- Sidebar badge counts
SELECT 'contacts' as section, COUNT(*) as count FROM contacts WHERE status = 'active'
UNION ALL SELECT 'emails', COUNT(*) FROM emails
UNION ALL SELECT 'calendar', COUNT(*) FROM calendar_events WHERE start_time > datetime('now', '-30 days')
UNION ALL SELECT 'transcripts', COUNT(*) FROM transcripts
UNION ALL SELECT 'decisions', COUNT(*) FROM decisions
UNION ALL SELECT 'journal', COUNT(*) FROM journal_entries
UNION ALL SELECT 'notes', COUNT(*) FROM standalone_notes;

-- Nudge count for Tools section badge
SELECT
  (SELECT COUNT(*) FROM follow_ups WHERE status = 'pending' AND due_date < date('now'))
  + (SELECT COUNT(*) FROM commitments WHERE status IN ('open','overdue') AND deadline_date < date('now'))
  + (SELECT COUNT(*) FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.status NOT IN ('done') AND t.due_date < date('now'))
  as urgent_count;
```

Hold ALL of these results in context as **"build context"** — refer back to them when generating each page's sidebar instead of re-querying.

## Step 3: Staleness Check

**If `FORCE_REBUILD = true`, skip this step entirely — mark all pages for rebuild.**

Read `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/staleness-queries.md` for the full query reference.

### 3a. Sidebar staleness (global)

```sql
SELECT
  (SELECT COUNT(*) FROM contacts WHERE status = 'active') as active_contacts,
  (SELECT COUNT(*) FROM generated_views WHERE view_type = 'entity_page' AND entity_type = 'contact') as contact_pages,
  (SELECT COUNT(*) FROM projects WHERE status IN ('active','planning')) as active_projects,
  (SELECT COUNT(*) FROM generated_views WHERE view_type = 'entity_page' AND entity_type = 'project') as project_pages;
```

If `active_contacts != contact_pages` OR `active_projects != project_pages` → **sidebar is stale, mark ALL pages for rebuild.** (A new entity means every page's sidebar needs updating.)

### 3b. Entity page staleness (batch)

Run the batch entity page staleness query from `staleness-queries.md` to check all contacts at once. A contact's page is stale if:
- No row in `generated_views` for it (never built)
- File missing from `output/` directory
- `latest_data_change > page_updated_at`

### 3c. Project page staleness

For each active/planning project, run the project staleness query. Same logic as entity pages.

### 3d. Transcript page staleness

For each analyzed transcript, run the transcript staleness query. Same logic.

### 3e. Module view staleness

For each installed module view, run its staleness query from `staleness-queries.md`:

| View | Stale check |
|------|-------------|
| `contacts.html` | Contacts index query |
| `network-map.html` | Network map query |
| `email-hub.html` | Email hub query |
| `week-view.html` | Week view query |
| `conversations.html` | Conversations query |
| `decision-journal.html` | Decision journal query |
| `journal.html` | Journal query |
| `notes.html` | Notes query |

### 3f. Always-rebuild views

These are always marked for rebuild regardless of data changes:
- `dashboard.html` — aggregates everything
- `nudges.html` — urgency-sensitive, date-relative
- `timeline.html` — cross-module chronological
- `weekly-review.html` — aggregated weekly lens
- `search.html` — embeds all data as JSON

## Step 4: Report Build Plan

**Before generating anything**, tell the user what will happen:

```
Build plan:
- 3 of 9 entity pages need rebuilding: Daniel Byrne, Sarah Chen, Marcus Webb
- 6 entity pages unchanged — skipping
- 1 of 2 project pages need rebuilding: Meridian Rebrand
- 2 module views rebuilding: Email Hub, Conversations
- 4 module views unchanged — skipping
- Dashboard + 4 cross-cutting views always rebuild
- Total: 12 pages to build, 10 to skip

Use `/build-all force` to rebuild everything.
```

If `FORCE_REBUILD = true`, say:
```
Force rebuild: regenerating all X pages (staleness checks bypassed).
```

If nothing is stale (except always-rebuild views):
```
Build plan: All pages are up to date. Rebuilding 5 always-refresh views (dashboard + cross-cutting).
```

## Step 5: Generate Stale Pages Only

Run each command's FULL specification for pages marked as stale. **SKIP pages not in the rebuild list.** Generate in this order:

### Transcript Pages (one per analyzed transcript — if stale)

For EACH stale transcript, run the complete `/transcript-page` workflow:
- Read `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/commands/transcript-page.md` and follow it completely
- Full data gathering: transcript details, participants, metrics, commitments, coaching insights
- Generate the full HTML with navigation (use pre-computed sidebar data from Step 2)
- Register in `generated_views`

**Generate transcript pages FIRST** so that entity pages and conversations-view can link to them.

### Entity Pages (one per active contact — if stale)

For EACH stale contact, run the complete `/entity-page` workflow:
- Read the reference implementation (`entity-page-reference.html`)
- Read all design references
- Gather ALL data for that contact
- Synthesize intelligence (relationship context narrative, company intel, expanded email threads, discovery questions)
- Generate the full HTML with navigation (use pre-computed sidebar data from Step 2)
- Register in `generated_views`

**This is the most important step.** Each entity page must be the rich, researched version. Read `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/commands/entity-page.md` and follow it completely for each contact.

### Project Pages (one per active/planning project — if stale)

For EACH stale project, run the complete `/project-page` workflow:
- Read `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/commands/project-page.md` and follow it completely
- Full data gathering, intelligence synthesis, risk assessment, task checklist
- Use pre-computed sidebar data from Step 2
- Register in `generated_views`

### Contacts Index (if stale or never built)

If stale or force mode:
- Follow `commands/contacts.md` completely
- If 0 contacts: show empty state ("No contacts yet — try `/contact add` to get started")
- Output: `contacts.html`

### Module Views (if stale)

Generate each STALE installed module's view. **Skip modules whose views are up to date.**

| Module | Command spec to follow | Output file | Empty state message |
|--------|----------------------|-------------|-------------------|
| Gmail | `commands/email-hub.md` | `email-hub.html` | "No emails synced yet — try `/google-setup` to connect Gmail" |
| Calendar | `commands/week-view.md` | `week-view.html` | "No calendar events — connect Google Calendar via `/google-setup`" |
| Conversation Intelligence | `commands/conversations-view.md` | `conversations.html` | "No transcripts yet — try `/import-call` to import a meeting" |
| Decision Log | `commands/decision-journal-view.md` | `decision-journal.html` | "No decisions logged yet — try `/decision` to record one" |
| Journal | `commands/journal-view.md` | `journal.html` | "No journal entries yet — try `/journal` to write today's entry" |
| Notes | `commands/notes-view.md` | `notes.html` | "No notes yet — try `/note` to create one" |

For each stale view: read the full command file and follow it completely. Use pre-computed sidebar data.

Even if skipping a module view due to freshness, ensure the file exists on disk. If the row exists in `generated_views` but the file is missing, rebuild it.

### Network Map (if stale)

If stale or force mode and CRM module is installed:
- If 2+ contacts: follow `commands/network-map.md` completely
- If 0–1 contacts: generate with empty state

### Cross-Cutting Views (always rebuild)

Generate these four views AFTER all entity/module pages, since they link to those pages:

| View | Command spec to follow | Output file |
|------|----------------------|-------------|
| Nudges | `commands/nudges-view.md` | `nudges.html` |
| Timeline | `commands/timeline.md` | `timeline.html` |
| Weekly Review | `commands/weekly-review.md` | `weekly-review.html` |
| Search Hub | `commands/search-hub.md` | `search.html` |

For each: read the full command file and follow it completely. Generate in order listed. Use pre-computed sidebar data.

### Dashboard (LAST — always rebuild)

Generate the dashboard LAST so it can link to all the pages generated above:
- Follow `commands/dashboard.md` completely
- The sidebar will populate from pre-computed build context
- Contact names throughout will link to entity pages
- The Intelligence Tools strip will link to the four cross-cutting views

## Step 6: Open Dashboard

After everything is generated, open the dashboard:
```
open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/dashboard.html"
```

## Step 7: Report

Tell the user what was built and what was skipped:

```
Built X pages, skipped Y (unchanged):

**Built:**
- T transcript pages: [list titles]
- E entity pages: [list names]
- P project pages: [list names]
- M module views: [list which ones]
- Dashboard + 4 cross-cutting views

**Skipped (up to date):**
- S entity pages: [list names]
- N module views: [list which ones]

All pages are in `output/` and linked via the sidebar.
```

If force mode, report all as built with no skipped section.

## Important

- **Do NOT skip the intelligence synthesis steps.** Entity pages must include relationship context narratives, company intel, email thread summaries, and discovery questions — not just raw data.
- **Do NOT generate lightweight card versions.** Every page uses its full command specification.
- **Generate entity pages BEFORE the dashboard** so the dashboard can link to them.
- **Use pre-computed sidebar data** from Step 2 for all pages — do NOT re-query sidebar data per page.
- **Check file existence on disk**, not just `generated_views` rows. A row without a file means the page needs rebuilding.
- If there are many contacts (10+), this will take a while. That's fine — quality over speed. But incremental builds mean most runs will be fast when only a few things changed.
