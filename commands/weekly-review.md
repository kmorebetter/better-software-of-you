---
description: Generate a Weekly Review — your week at a glance with relationship pulse, meetings, email activity, project progress, and look-ahead
allowed-tools: ["Bash", "Read", "Write"]
---

# Generate Weekly Review

Generate the weekly intelligence brief — a cross-module summary of your week with a look-ahead. This synthesizes data from all installed modules into one page.

## Step 0: Auto-Sync External Data

Before building, ensure data is fresh. Follow the auto-sync procedure in CLAUDE.md — check `gmail_last_synced` and `calendar_last_synced` in `soy_meta`, and sync if stale (>15 min) or never synced. Do this silently.

## Step 1: Read the Design System

Read these files first:
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/template-base.html` — HTML skeleton
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/navigation-patterns.md` — sidebar patterns

## Step 2: Check Modules & Gather Data

Query `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`. Run all queries in a single `sqlite3` heredoc call for efficiency.

```sql
-- Installed modules
SELECT name FROM modules WHERE enabled = 1;

-- Navigation data
SELECT view_type, entity_type, entity_name, filename FROM generated_views ORDER BY updated_at DESC;

-- Nav badge counts
SELECT 'contacts' as section, COUNT(*) as count FROM contacts WHERE status = 'active'
UNION ALL SELECT 'emails', COUNT(*) FROM emails
UNION ALL SELECT 'calendar', COUNT(*) FROM calendar_events WHERE start_time > datetime('now', '-30 days')
UNION ALL SELECT 'transcripts', COUNT(*) FROM transcripts
UNION ALL SELECT 'decisions', COUNT(*) FROM decisions
UNION ALL SELECT 'journal', COUNT(*) FROM journal_entries;

-- Entity pages for linking
SELECT entity_type, entity_id, entity_name, filename FROM generated_views WHERE view_type = 'entity_page';
```

### Week boundaries

Calculate the current week (Monday–Sunday or start of today's week):
- Week start: `date('now', 'weekday 1', '-7 days')` (last Monday)
- Week end: `date('now', 'weekday 0')` (this Sunday)

### This Week Data

**Activity summary** (grouped by entity type):
```sql
SELECT entity_type, COUNT(*) as count
FROM activity_log
WHERE created_at >= date('now', '-7 days')
GROUP BY entity_type;
```

**Contacts touched this week** (relationship pulse):
```sql
SELECT DISTINCT c.id, c.name, c.company, MAX(al.created_at) as last_touch,
  COUNT(al.id) as touch_count
FROM activity_log al
JOIN contacts c ON al.entity_type = 'contact' AND al.entity_id = c.id
WHERE al.created_at >= date('now', '-7 days')
GROUP BY c.id
ORDER BY touch_count DESC
LIMIT 10;
```

**Contacts going cold** (no activity in 14+ days among active contacts):
```sql
SELECT c.id, c.name, c.company,
  MAX(al.created_at) as last_activity,
  CAST(julianday('now') - julianday(MAX(al.created_at)) AS INTEGER) as days_silent
FROM contacts c
LEFT JOIN activity_log al ON al.entity_type = 'contact' AND al.entity_id = c.id
WHERE c.status = 'active'
GROUP BY c.id
HAVING days_silent > 14 OR last_activity IS NULL
ORDER BY days_silent DESC
LIMIT 5;
```

**Meetings attended** (if Calendar installed):
```sql
SELECT id, title, start_time, end_time, attendees, location
FROM calendar_events
WHERE date(start_time) BETWEEN date('now', '-7 days') AND date('now')
  AND status != 'cancelled'
ORDER BY start_time ASC;
```

**Email activity** (if Gmail installed):
```sql
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN direction = 'inbound' THEN 1 ELSE 0 END) as received,
  SUM(CASE WHEN direction = 'outbound' THEN 1 ELSE 0 END) as sent,
  SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) as unread
FROM emails
WHERE received_at >= date('now', '-7 days');
```

**Threads needing response** (if Gmail installed):
```sql
SELECT e.thread_id, e.subject, e.from_name, e.received_at, c.name as contact_name
FROM emails e
LEFT JOIN contacts c ON e.contact_id = c.id
WHERE e.direction = 'inbound'
  AND e.thread_id NOT IN (
    SELECT thread_id FROM emails WHERE direction = 'outbound' AND received_at > e.received_at
  )
  AND e.received_at >= date('now', '-7 days')
GROUP BY e.thread_id
ORDER BY e.received_at DESC
LIMIT 5;
```

**Tasks completed** (if Project Tracker installed):
```sql
SELECT t.title, p.name as project_name
FROM tasks t
JOIN projects p ON p.id = t.project_id
WHERE t.status = 'done' AND t.updated_at >= date('now', '-7 days')
ORDER BY t.updated_at DESC;
```

**Milestones hit** (if Project Tracker installed):
```sql
SELECT m.title, p.name as project_name
FROM milestones m
JOIN projects p ON p.id = m.project_id
WHERE m.status = 'completed' AND m.updated_at >= date('now', '-7 days')
ORDER BY m.updated_at DESC;
```

**Decisions made** (if Decision Log installed):
```sql
SELECT id, title, status, decided_at
FROM decisions
WHERE decided_at >= date('now', '-7 days')
ORDER BY decided_at DESC;
```

**Journal insights** (if Journal installed):
```sql
SELECT entry_date, mood, energy
FROM journal_entries
WHERE entry_date >= date('now', '-7 days')
ORDER BY entry_date ASC;
```

**Commitments completed this week** (if Conversation Intelligence installed):
```sql
SELECT com.description, com.is_user_commitment, c.name as owner_name
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
WHERE com.completed_at >= date('now', '-7 days')
ORDER BY com.completed_at DESC;
```

**New commitments this week** (if Conversation Intelligence installed):
```sql
SELECT com.description, com.is_user_commitment, c.name as owner_name, com.deadline_date
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
WHERE com.created_at >= date('now', '-7 days') AND com.status = 'open'
ORDER BY com.deadline_date ASC;
```

### Looking Ahead Data

**Next week's calendar** (if Calendar installed):
```sql
SELECT id, title, start_time, end_time, attendees, location
FROM calendar_events
WHERE date(start_time) BETWEEN date('now', '+1 day') AND date('now', '+8 days')
  AND status != 'cancelled'
ORDER BY start_time ASC;
```

**Follow-ups due soon** (if CRM installed):
```sql
SELECT f.reason, f.due_date, c.name as contact_name, c.id as contact_id
FROM follow_ups f
JOIN contacts c ON c.id = f.contact_id
WHERE f.status = 'pending' AND f.due_date <= date('now', '+7 days')
ORDER BY f.due_date ASC;
```

**Commitment deadlines** (if Conversation Intelligence installed):
```sql
SELECT com.description, com.deadline_date,
  CASE WHEN com.is_user_commitment = 1 THEN 'You' ELSE c.name END as owner
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
WHERE com.status = 'open' AND com.deadline_date <= date('now', '+7 days')
ORDER BY com.deadline_date ASC;
```

**Task due dates** (if Project Tracker installed):
```sql
SELECT t.title, t.due_date, p.name as project_name
FROM tasks t
JOIN projects p ON p.id = t.project_id
WHERE t.status NOT IN ('done') AND t.due_date <= date('now', '+7 days')
ORDER BY t.due_date ASC;
```

**Approaching project dates** (if Project Tracker installed):
```sql
SELECT p.name, p.target_date,
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status != 'done') as open_tasks
FROM projects p
WHERE p.status = 'active' AND p.target_date BETWEEN date('now') AND date('now', '+14 days');
```

## Step 3: Generate HTML

Generate a self-contained HTML file. Follow the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font).

### Sidebar

Include the sidebar from `navigation-patterns.md` with Weekly Review active in the Tools section.

### Page Structure

```
Sidebar (Weekly Review active in Tools section)

Header card (full width)
+-- Title: "Week of Feb 16-22, 2026" (calculate actual dates)
+-- Subtitle: "Your weekly intelligence brief"
+-- Stats row: summary counts as pills
    +-- Meetings (if Calendar): "X meetings"
    +-- Emails (if Gmail): "X emails"
    +-- Tasks done (if Project Tracker): "X tasks done"
    +-- Decisions (if Decision Log): "X decisions"
    +-- Journal entries (if Journal): "X entries"

Two-column layout: grid grid-cols-1 lg:grid-cols-5 gap-6

Left column (lg:col-span-3): THIS WEEK
+-- Relationship Pulse card
    +-- Contacts touched (list with touch count)
    +-- Contacts going cold (warning items)
+-- Meetings Attended card (if Calendar installed)
    +-- Count + list of meetings with key details
+-- Email Activity card (if Gmail installed)
    +-- Sent/received counts
    +-- Threads needing response list
+-- Project Progress card (if Project Tracker installed)
    +-- Tasks completed list
    +-- Milestones hit
+-- Decisions Made card (if Decision Log installed)
    +-- List of this week's decisions
+-- Journal Insights card (if Journal installed)
    +-- Mood/energy mini-sparkline
    +-- Summary of patterns
+-- Commitments card (if Conversation Intelligence installed)
    +-- Completed commitments
    +-- New commitments

Right column (lg:col-span-2): LOOKING AHEAD
+-- Next Week Calendar card (if Calendar installed)
    +-- Upcoming meetings listed by day
+-- Due Soon card
    +-- Follow-ups due (if CRM)
    +-- Commitment deadlines (if Conversation Intelligence)
    +-- Task due dates (if Project Tracker)
+-- Approaching Dates card
    +-- Project target dates (if Project Tracker)

Footer
```

### Section Card Design

Each section uses a consistent card pattern:

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5 mb-4">
  <div class="flex items-center gap-2 mb-4">
    <i data-lucide="ICON" class="w-4 h-4 text-zinc-400"></i>
    <h3 class="text-sm font-semibold text-zinc-700">Section Title</h3>
    <span class="text-xs text-zinc-400 ml-auto">Count or context</span>
  </div>
  <!-- Section content -->
</div>
```

### Section Icons

| Section | Icon |
|---------|------|
| Relationship Pulse | `heart-pulse` |
| Meetings | `calendar` |
| Email Activity | `mail` |
| Project Progress | `folder` |
| Decisions | `git-branch` |
| Journal Insights | `book-open` |
| Commitments | `target` |
| Next Week | `calendar-days` |
| Due Soon | `alert-circle` |
| Approaching Dates | `clock` |

### Journal Insights — Mini Sparkline

If the Journal module is installed and there are 3+ entries with energy data this week, render a mini inline SVG sparkline:

```html
<svg viewBox="0 0 120 30" class="w-full h-8">
  <polyline points="..." fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round"/>
  <circle cx="..." cy="..." r="3" fill="#10b981"/>
  <!-- dots colored by mood category -->
</svg>
```

Map energy values (1-5) to Y coordinates (1=bottom, 5=top). If fewer than 3 entries, show "Not enough data for trends this week."

### Module-Aware Sections

Each section only renders if its module is installed. If a module is installed but has no data for the week, show a subtle message rather than hiding:

```html
<p class="text-sm text-zinc-400 italic">No meetings this week.</p>
```

### Column Headers

```html
<!-- Left column -->
<div class="lg:col-span-3">
  <div class="flex items-center gap-2 mb-4">
    <h2 class="text-xs font-semibold text-zinc-400 uppercase tracking-wider">This Week</h2>
    <div class="flex-1 h-px bg-zinc-200"></div>
  </div>
  <!-- section cards -->
</div>

<!-- Right column -->
<div class="lg:col-span-2">
  <div class="flex items-center gap-2 mb-4">
    <h2 class="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Looking Ahead</h2>
    <div class="flex-1 h-px bg-zinc-200"></div>
  </div>
  <!-- section cards -->
</div>
```

### Contact Name Linking

Anywhere a contact name appears (relationship pulse, meeting attendees, email threads, commitments), check if that contact has a generated entity page. If a page exists, link the name:
```html
<a href="contact-{slug}.html" class="font-medium text-blue-600 hover:text-blue-800 hover:underline">Name</a>
```
If no page exists, render as bold plain text.

### Empty States

- No activity this week at all: Show a centered message "Quiet week — no recorded activity." with a `coffee` icon. Still show the Looking Ahead column.
- Individual empty sections: "No [data type] this week." in italic zinc-400 text. Do not hide the card.
- Module not installed: Do not show the card at all.

## Design Rules (non-negotiable)

- Use the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- Stats pills in header: use module-specific colors (blue for meetings, indigo for emails, purple for tasks, amber for decisions, rose for journal)
- Cold contacts: `bg-amber-50 border-l-4 border-amber-400` warning style
- Due soon items: `bg-amber-50 border-l-4 border-amber-400` if due within 3 days, `bg-red-50 border-l-4 border-red-400` if overdue
- All data static in HTML — no JavaScript data fetching
- The only JS: Lucide icon initialization (`lucide.createIcons()`)
- Responsive: `grid grid-cols-1 lg:grid-cols-5 gap-6`

## Step 4: Write, Register, and Open

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/weekly-review.html`

**Register the view:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Weekly Review', 'weekly-review.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Open with: `open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/weekly-review.html"`

Tell the user: "Weekly review opened." Then briefly summarize highlights — e.g., "Touched 5 contacts, attended 3 meetings, completed 4 tasks. 2 follow-ups due next week."
