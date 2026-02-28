---
description: Generate a project intelligence brief — everything about a project in one page
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: <project name or id>
---

# Project Page

Generate a project intelligence brief for the project specified in $ARGUMENTS. This is the project equivalent of the entity page — a single page that synthesizes everything the system knows about a project: status, tasks, milestones, client relationship, email history, risks, and AI-generated next steps.

## Step 0: Auto-Sync External Data

Before building the project page, ensure data is fresh. Follow the auto-sync procedure in CLAUDE.md — check `gmail_last_synced` and `calendar_last_synced` in `soy_meta`, and sync if stale (>15 min) or never synced. Do this silently.

## Step 1: Read References + Resolve Project

Read design references in parallel:
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/template-base.html`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/component-patterns.md`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/navigation-patterns.md`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/delight-patterns.md` — micro-interactions and delight
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/project-tracker/references/project-methodology.md`

At the same time, resolve the project. Query `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`:

```sql
SELECT * FROM projects WHERE name LIKE '%$ARGUMENTS%' OR id = '$ARGUMENTS';
```

If multiple matches, pick the best match or ask the user.

If the project has a `client_id`, also resolve the client contact:
```sql
SELECT * FROM contacts WHERE id = ?;
```

## Step 2: Check Installed Modules

```sql
SELECT name FROM modules WHERE enabled = 1;
```

Only run queries for installed modules. Skip queries for modules that aren't installed.

## Step 3: Gather Data

Run these queries. Use the resolved project ID and client contact ID wherever you see `?`. Run all queries in a single `sqlite3` heredoc call for efficiency.

### Always query:

```sql
-- All tasks for this project
SELECT * FROM tasks WHERE project_id = ?
ORDER BY
  CASE status WHEN 'in_progress' THEN 1 WHEN 'todo' THEN 2 WHEN 'blocked' THEN 3 WHEN 'done' THEN 4 END,
  due_date ASC NULLS LAST;

-- Task status counts
SELECT status, COUNT(*) as count FROM tasks WHERE project_id = ? GROUP BY status;

-- Milestones
SELECT * FROM milestones WHERE project_id = ? ORDER BY target_date ASC NULLS LAST;

-- Notes on this project
SELECT content, created_at FROM notes
WHERE entity_type = 'project' AND entity_id = ?
ORDER BY created_at DESC LIMIT 10;

-- Activity log
SELECT action, details, created_at FROM activity_log
WHERE entity_type = 'project' AND entity_id = ?
ORDER BY created_at DESC LIMIT 20;

-- Tags
SELECT t.name, t.color FROM tags t
JOIN entity_tags et ON et.tag_id = t.id
WHERE et.entity_type = 'project' AND et.entity_id = ?;
```

### If CRM module installed (and client exists):

```sql
-- Client contact details (already fetched in Step 1)

-- Interactions with the client
SELECT ci.*, c.name as contact_name FROM contact_interactions ci
JOIN contacts c ON c.id = ci.contact_id
WHERE ci.contact_id = ?
ORDER BY ci.occurred_at DESC LIMIT 20;

-- Related contacts (people connected to the client)
SELECT cr.relationship_type, cr.notes,
  CASE WHEN cr.contact_id_a = ? THEN cb.name ELSE ca.name END as related_name,
  CASE WHEN cr.contact_id_a = ? THEN cb.company ELSE ca.company END as related_company,
  CASE WHEN cr.contact_id_a = ? THEN cb.role ELSE ca.role END as related_role
FROM contact_relationships cr
LEFT JOIN contacts ca ON ca.id = cr.contact_id_a
LEFT JOIN contacts cb ON cb.id = cr.contact_id_b
WHERE cr.contact_id_a = ? OR cr.contact_id_b = ?;

-- Pending follow-ups for the client
SELECT f.*, c.name as contact_name FROM follow_ups f
JOIN contacts c ON c.id = f.contact_id
WHERE f.contact_id = ? AND f.status = 'pending'
ORDER BY f.due_date ASC;
```

### If Gmail module installed (and client exists):

```sql
-- Emails with the client
SELECT id, thread_id, subject, snippet, from_name, from_address,
  to_addresses, direction, received_at, contact_id
FROM emails
WHERE contact_id = ?
ORDER BY received_at ASC;
```

### If Calendar module installed:

```sql
-- Events linked to this project or involving the client
SELECT * FROM calendar_events
WHERE project_id = ?
  OR (contact_ids LIKE '%' || ? || '%')
ORDER BY start_time DESC
LIMIT 20;
```

### If Conversation Intelligence installed (and client exists):

```sql
-- Transcripts with the client
SELECT t.id, t.title, t.summary, t.duration_minutes, t.occurred_at,
  GROUP_CONCAT(DISTINCT c.name) as participant_names
FROM transcripts t
JOIN transcript_participants tp ON tp.transcript_id = t.id
LEFT JOIN contacts c ON c.id = tp.contact_id AND tp.is_user = 0
WHERE tp.contact_id = ?
GROUP BY t.id
ORDER BY t.occurred_at DESC
LIMIT 15;

-- Open commitments related to this project or client
SELECT com.*,
  CASE WHEN com.is_user_commitment = 1 THEN 'You' ELSE c.name END as owner_name,
  t.title as from_call, t.occurred_at as call_date
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
LEFT JOIN transcripts t ON t.id = com.transcript_id
WHERE com.status IN ('open', 'overdue')
  AND (com.owner_contact_id = ?
    OR com.transcript_id IN (
      SELECT transcript_id FROM transcript_participants WHERE contact_id = ?));
```

## Step 4: Synthesize Intelligence

This is where the page goes beyond raw data. Using all gathered data, synthesize these sections. Write in natural, narrative language — not bullet dumps.

### Project Status Card

Tell the story of where this project stands right now:
- **Current state** — what phase is it in, what's actively being worked on
- **Blockers** — anything stalled, overdue, or waiting on someone
- **Momentum** — use the velocity formula from project-methodology.md. Display format: "Accelerating — 5 tasks completed this period vs 2 last period" (always show the numbers). If no task completions exist, show "—".
- **What just happened** — the most notable recent developments (task completions, milestone hits, client conversations)

Pull from: tasks, milestones, activity log, recent interactions, notes.

### Client Relationship Card

If a client exists, ground the relationship assessment in computed data:
- **Relationship depth + trajectory** — pull from `relationship_scores` (depth, trajectory, follow-through percentages, meeting_frequency). Display format per project-methodology.md.
- **Interaction frequency** — computed as interactions/week from contact_interactions over 30 days.
- **How the project started** — context from early interactions or notes
- **Open commitments** — list any open/overdue commitments between you and this client
- If no Conversation Intelligence data: "No conversation data — relationship based on interaction frequency only ({N}/week)"

Pull from: relationship_scores, contact_interactions, notes, commitments, follow-ups. Never use: "email tone", "current dynamic", "client satisfaction signals" — these are not computable.

### Risk Assessment

Use risk thresholds from project-methodology.md. Run the required queries and apply the first matching level:
- **High** — >=3 overdue tasks, OR >=1 missed milestone, OR no activity in 14+ days on an active project
- **Medium** — 1–2 overdue tasks, OR overdue commitments, OR target date within 14 days with open > completed tasks
- **Low** — all tasks on track, no overdue items, regular activity

Output reasoning in this format: "Medium — 2 overdue tasks, target date in 11 days with 8/12 tasks remaining"

Within the card, still name specific overdue tasks (with days overdue), missed milestones (with how much), commitment gaps, and scope concerns. The threshold determines the badge; the details provide context.

### What's Next

Use the action prioritization formula from project-methodology.md. Show 3-5 actions in ranked order:
1. Unblock blocked tasks (highest priority — blocking other work)
2. Overdue tasks (most days overdue first)
3. Approaching milestones (within 14 days)
4. Tasks due soon (within 7 days)
5. Follow-ups needed for project client

Each action must be specific and reference data:
- Not "Follow up with client" but "Send Sarah the revised timeline — she asked for it in the Feb 12 email"
- Not "Complete tasks" but "Finish the API integration task (3 days overdue) to unblock the testing milestone"

## Step 5: Generate HTML

Generate a self-contained HTML file. Match the entity-page design system in structure and visual quality.

### Page Structure

```
Project Header (full width card)
├── Project name + status badge + priority badge
├── Client name (linked to entity page if exists) + target date
└── Tag badges

Progress Bar (full width)
├── Tasks done / total with visual progress bar

Two-column grid (lg:grid-cols-3)
├── Left column (lg:col-span-2)
│   ├── Project Status card (narrative)
│   ├── Client Relationship card (if client exists)
│   ├── Task Checklist (grouped by status: in_progress first, then todo, then blocked, then done collapsed)
│   └── Email Thread card (if emails exist — expanded per-message view, same style as entity page)
└── Right column
    ├── Milestones timeline (checkmarks for completed, circles for upcoming, red for overdue)
    ├── Risk Assessment card (with risk level badge)
    ├── What's Next card (prioritized action items)
    └── Upcoming Events card (if calendar data)

Activity Timeline (full width — recent project activity with icons)

Footer
```

### Design Rules

- Use the template-base.html skeleton (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- Status badges: green (`bg-emerald-50 text-emerald-700`) for active/done, blue (`bg-blue-50 text-blue-700`) for planning/in-progress, amber (`bg-amber-50 text-amber-700`) for pending/on-hold, red (`bg-red-50 text-red-700`) for overdue/blocked, zinc (`bg-zinc-100 text-zinc-600`) for paused
- Priority badges: red for high, amber for medium, zinc for low
- Progress bar: `bg-emerald-500` fill on `bg-zinc-100` track, with percentage label
- Risk level badge: emerald for low, amber for medium, red for high
- Task checklist: checkmarks (`text-emerald-500`) for done, squares (`text-blue-500`) for in-progress, circles (`text-zinc-300`) for todo, alert triangles (`text-red-500`) for blocked
- Client name linked to entity page: check `generated_views` for the contact, link if exists
- All data static in HTML — no JavaScript data fetching
- JS: Lucide icons + delight layer from template-base.html (countups, scroll reveals, card stagger)
- Responsive: sidebar stacks below on mobile via `grid-cols-1 lg:grid-cols-3`

### Rendering Principles

- **Narrative over tables.** Write status and relationship sections as prose, not bullet lists.
- **Only show cards that have data.** If no client exists, skip client relationship card. If no emails, skip email card. If no calendar events, skip upcoming events.
- **Highlight what matters now.** Overdue tasks and missed milestones should be visually prominent with red/amber accents.
- **Tasks are scannable.** Group by status with clear visual differentiation. Done tasks can be collapsed or shown at reduced opacity.
- **Milestones tell a timeline story.** Show them vertically with a connecting line, completed ones checked off, upcoming ones open.

## Step 6: Add Navigation

Include the sidebar from `navigation-patterns.md` with this project highlighted in the Projects section. The Projects section auto-expands with this project's `.sidebar-entity` having the `active` class.

## Step 7: Write, Register, and Open

Generate a filename slug from the project name (lowercase, hyphens for spaces).

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/project-{slug}.html`

**Register the view** so other pages can link to it:
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('entity_page', 'project', ?, ?, 'project-{slug}.html')
ON CONFLICT(filename) DO UPDATE SET
  entity_name = excluded.entity_name,
  updated_at = datetime('now');
```

Open with: `open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/project-{slug}.html"`

Tell the user: "Project page for **{project name}** opened." Then briefly summarize what's on it — e.g., "Shows 12/18 tasks complete, client relationship context with Sarah, 2 overdue tasks flagged as risks, and 4 prioritized next actions."
