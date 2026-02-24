---
description: Generate the Nudges view — your attention radar showing overdue, upcoming, and awareness items with urgency tiers
allowed-tools: ["Bash", "Read", "Write"]
---

# Generate Nudges View

Generate the "Attention Radar" page — a cross-module view that surfaces everything needing your attention, organized by urgency. This is the command center of the platform.

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

### Urgent (Red) — Needs immediate attention

**Overdue follow-ups** (if CRM installed):
```sql
SELECT f.id, f.reason, f.due_date, c.name as contact_name, c.id as contact_id,
  CAST(julianday('now') - julianday(f.due_date) AS INTEGER) as days_overdue
FROM follow_ups f
JOIN contacts c ON c.id = f.contact_id
WHERE f.status = 'pending' AND f.due_date < date('now')
ORDER BY f.due_date ASC;
```

**Overdue commitments** (if Conversation Intelligence installed):
```sql
SELECT com.id, com.description, com.deadline_date,
  CASE WHEN com.is_user_commitment = 1 THEN 'You' ELSE c.name END as owner,
  c.id as owner_id,
  CAST(julianday('now') - julianday(com.deadline_date) AS INTEGER) as days_overdue
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
WHERE com.status IN ('open', 'overdue') AND com.deadline_date < date('now')
ORDER BY com.deadline_date ASC;
```

**Overdue tasks** (if Project Tracker installed):
```sql
SELECT t.id, t.title, t.due_date, p.name as project_name, p.id as project_id,
  CAST(julianday('now') - julianday(t.due_date) AS INTEGER) as days_overdue
FROM tasks t
JOIN projects p ON p.id = t.project_id
WHERE t.status NOT IN ('done') AND t.due_date < date('now')
ORDER BY t.due_date ASC;
```

### Soon (Amber) — Coming up in the next few days

**Follow-ups due within 3 days** (if CRM installed):
```sql
SELECT f.id, f.reason, f.due_date, c.name as contact_name, c.id as contact_id
FROM follow_ups f
JOIN contacts c ON c.id = f.contact_id
WHERE f.status = 'pending' AND f.due_date BETWEEN date('now') AND date('now', '+3 days')
ORDER BY f.due_date ASC;
```

**Commitments due within 3 days** (if Conversation Intelligence installed):
```sql
SELECT com.id, com.description, com.deadline_date,
  CASE WHEN com.is_user_commitment = 1 THEN 'You' ELSE c.name END as owner,
  c.id as owner_id
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
WHERE com.status = 'open' AND com.deadline_date BETWEEN date('now') AND date('now', '+3 days')
ORDER BY com.deadline_date ASC;
```

**Tasks due within 3 days** (if Project Tracker installed):
```sql
SELECT t.id, t.title, t.due_date, p.name as project_name, p.id as project_id
FROM tasks t
JOIN projects p ON p.id = t.project_id
WHERE t.status NOT IN ('done') AND t.due_date BETWEEN date('now') AND date('now', '+3 days')
ORDER BY t.due_date ASC;
```

**Today's meetings** (if Calendar installed):
```sql
SELECT title, start_time, end_time, attendees, location
FROM calendar_events
WHERE date(start_time) = date('now') AND status != 'cancelled'
ORDER BY start_time ASC;
```

**Projects approaching target date** (if Project Tracker installed):
```sql
SELECT p.name, p.id, p.target_date,
  CAST(julianday(p.target_date) - julianday('now') AS INTEGER) as days_until,
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status != 'done') as open_tasks
FROM projects p
WHERE p.status = 'active' AND p.target_date BETWEEN date('now') AND date('now', '+7 days');
```

### Awareness (Blue) — Worth knowing about

**Contacts going cold** (30+ days no activity):
```sql
SELECT c.id, c.name, c.company, c.email,
  MAX(al.created_at) as last_activity,
  CAST(julianday('now') - julianday(MAX(al.created_at)) AS INTEGER) as days_silent
FROM contacts c
JOIN activity_log al ON al.entity_type = 'contact' AND al.entity_id = c.id
WHERE c.status = 'active'
GROUP BY c.id
HAVING days_silent > 30
ORDER BY days_silent DESC
LIMIT 5;
```

**Stale projects** (14+ days no activity, if Project Tracker installed):
```sql
SELECT p.id, p.name, p.status, p.target_date,
  MAX(al.created_at) as last_activity,
  CAST(julianday('now') - julianday(MAX(al.created_at)) AS INTEGER) as days_stale
FROM projects p
LEFT JOIN activity_log al ON al.entity_type = 'project' AND al.entity_id = p.id
WHERE p.status IN ('active', 'planning')
GROUP BY p.id
HAVING days_stale > 14 OR last_activity IS NULL
ORDER BY days_stale DESC;
```

**Decisions pending outcome** (90+ days old, if Decision Log installed):
```sql
SELECT d.id, d.title, d.decided_at,
  CAST(julianday('now') - julianday(d.decided_at) AS INTEGER) as days_ago
FROM decisions d
WHERE d.status = 'decided' AND d.outcome IS NULL
  AND julianday('now') - julianday(d.decided_at) > 90
ORDER BY d.decided_at ASC;
```

**Emails needing response** (inbound, unread, 3+ days old, if Gmail installed):
```sql
SELECT e.id, e.subject, e.from_name, e.from_address, e.received_at,
  c.name as contact_name, c.id as contact_id,
  CAST(julianday('now') - julianday(e.received_at) AS INTEGER) as days_old
FROM emails e
LEFT JOIN contacts c ON e.contact_id = c.id
WHERE e.direction = 'inbound' AND e.is_read = 0
  AND julianday('now') - julianday(e.received_at) > 3
  AND e.thread_id NOT IN (
    SELECT thread_id FROM emails WHERE direction = 'outbound' AND received_at > e.received_at
  )
ORDER BY e.received_at ASC
LIMIT 5;
```

## Step 3: Compute Counts

After gathering data, compute:
- `urgent_count`: total overdue follow-ups + overdue commitments + overdue tasks
- `soon_count`: total due-soon follow-ups + due-soon commitments + due-soon tasks + today's meetings + approaching projects
- `awareness_count`: cold contacts + stale projects + pending decisions + old unread emails
- `total_count`: urgent_count + soon_count + awareness_count

Determine the **most urgent single item** for the hero callout. Priority order:
1. The most overdue follow-up or commitment (whichever has more days overdue)
2. The most overdue task
3. The oldest unanswered email
4. The coldest contact

## Step 4: Generate HTML

Generate a self-contained HTML file. Follow the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font).

### Sidebar

Include the sidebar from `navigation-patterns.md` with Nudges active in the Tools section.

### Page Structure

```
Sidebar (Nudges active in Tools section)

Header card
+-- Title: "Attention Radar"
+-- Subtitle: "X items need your attention" (or "All clear" if zero)
+-- Summary pills:
    +-- Red pill: "N Urgent" (hidden if 0)
    +-- Amber pill: "N Soon" (hidden if 0)
    +-- Blue pill: "N Awareness" (hidden if 0)

Hero Callout (if any urgent items exist)
+-- Full-width card with gradient left border (red to amber)
+-- Light amber background gradient
+-- Large icon (entity-type specific)
+-- Bold title with urgency context
+-- Description and suggested action
+-- Direct link to entity page (if exists)
+-- Subtle pulse animation on icon

URGENT section (if urgent items exist)
+-- Section header: red dot + "Urgent — Needs immediate attention"
+-- Grid of red-accented cards (grid-cols-1 md:grid-cols-2 gap-3)
+-- Each card: red left border, icon, entity name, context, action link

SOON section (if soon items exist)
+-- Section header: amber dot + "Soon — Coming up in the next few days"
+-- Grid of amber-accented cards
+-- Each card: amber left border, icon, entity name, context

AWARENESS section (if awareness items exist)
+-- Section header: blue dot + "Awareness — Worth knowing about"
+-- Grid of blue-accented cards
+-- Each card: blue left border, icon, entity name, context

ALL CLEAR (if zero total items)
+-- Full-width centered card
+-- Check-circle icon (green)
+-- "Nothing needs your attention. Nice work."

Footer
```

### Hero Callout Design

The most urgent item gets a full-width hero card:

```html
<div class="nudge-hero mb-6">
  <div class="flex items-start gap-4">
    <div class="pulse-dot mt-1">
      <i data-lucide="alert-triangle" class="w-6 h-6 text-red-500"></i>
    </div>
    <div class="flex-1">
      <h3 class="text-lg font-bold text-zinc-900">Follow-up with Sarah Chen — 5 days overdue</h3>
      <p class="text-sm text-zinc-600 mt-1">You planned to discuss the proposal update. Last contact was 12 days ago.</p>
      <a href="contact-sarah-chen.html" class="inline-flex items-center gap-1 text-sm font-medium text-amber-700 hover:text-amber-900 mt-3">
        View contact <i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>
      </a>
    </div>
  </div>
</div>
```

### CSS (include in `<style>` block)

Include sidebar CSS from navigation-patterns.md, plus:

```css
.nudge-hero {
  background: linear-gradient(135deg, #fffbeb 0%, #fff7ed 100%);
  border-left: 4px solid;
  border-image: linear-gradient(to bottom, #ef4444, #f59e0b) 1;
  border-radius: 0.75rem;
  padding: 1.5rem;
}
.pulse-dot {
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

### Nudge Card Design

Each nudge card follows this pattern:

```html
<div class="bg-white rounded-lg border border-zinc-200 p-4 border-l-4 border-l-red-400">
  <div class="flex items-start gap-3">
    <i data-lucide="clock" class="w-4 h-4 text-red-500 mt-0.5 shrink-0"></i>
    <div>
      <div class="text-sm font-medium text-zinc-900">
        <a href="contact-name.html" class="text-blue-600 hover:text-blue-800 hover:underline">Contact Name</a>
        — Follow-up overdue
      </div>
      <p class="text-xs text-zinc-500 mt-1">Due 3 days ago · "Discuss proposal update"</p>
      <p class="text-xs text-zinc-400 mt-1">Schedule a follow-up</p>
    </div>
  </div>
</div>
```

Color variants:
- **Urgent**: `border-l-red-400`, icon uses `text-red-500`
- **Soon**: `border-l-amber-400`, icon uses `text-amber-500`
- **Awareness**: `border-l-blue-400`, icon uses `text-blue-500`

### Icons by Entity Type

| Entity | Lucide Icon |
|--------|-------------|
| Follow-up | `clock` |
| Commitment | `target` |
| Task | `check-square` |
| Calendar event | `calendar` |
| Contact | `users` |
| Project | `folder` |
| Decision | `git-branch` |
| Email | `mail` |

### Context Lines for Each Nudge Type

- Overdue follow-up: "Due X days ago · '{reason}'"
- Overdue commitment: "Due X days ago · '{description}'"
- Overdue task: "Due X days ago · Project: {project_name}"
- Due-soon follow-up: "Due {relative_date} · '{reason}'"
- Due-soon commitment: "Due {relative_date} · '{description}'"
- Due-soon task: "Due {relative_date} · Project: {project_name}"
- Today's meeting: "{start_time} · {location}"
- Approaching project: "{days_until} days to target · {open_tasks} open tasks"
- Cold contact: "Last contact: {days_silent} days ago · {company}"
- Stale project: "No activity in {days_stale} days"
- Pending decision: "Decided {days_ago} days ago · No outcome recorded"
- Old email: "From {from_name} · {days_old} days ago · '{subject}'"

### Suggested Actions

- Follow-up: "Schedule a follow-up"
- Commitment: "Review and update"
- Task: "Update task status"
- Meeting: "Prep for this meeting"
- Project: "Review project progress"
- Cold contact: "Reach out"
- Stale project: "Check in on progress"
- Decision: "Record the outcome"
- Email: "Reply or archive"

### All Clear State

If no nudges exist at all:

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-12 text-center">
  <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-50 mb-4">
    <i data-lucide="check-circle" class="w-8 h-8 text-emerald-500"></i>
  </div>
  <h3 class="text-lg font-semibold text-zinc-900 mb-1">Nothing needs your attention</h3>
  <p class="text-sm text-zinc-500">No overdue items, no cold contacts, everything is on track. Nice work.</p>
</div>
```

### Entity Name Linking

For every contact, project, or entity name in a nudge card, check if that entity has a generated page in the `generated_views` query results. If a page exists, render the name as a link:
```html
<a href="contact-{slug}.html" class="font-medium text-blue-600 hover:text-blue-800 hover:underline">Name</a>
```
If no page exists, render as bold plain text.

### Summary Pills

```html
<div class="flex items-center gap-2 mt-3">
  <span class="px-3 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700">3 Urgent</span>
  <span class="px-3 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700">5 Soon</span>
  <span class="px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700">2 Awareness</span>
</div>
```

Only show pills for categories with items.

## Design Rules (non-negotiable)

- Use the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- The hero callout gradient and pulse animation are signature elements — always include them when urgent items exist
- Grid of nudge cards: `grid grid-cols-1 md:grid-cols-2 gap-3`
- Section headers: `text-xs font-semibold uppercase tracking-wider` with a colored dot (8px, `rounded-full`)
- All data static in HTML — no JavaScript data fetching
- The only JS: Lucide icon initialization (`lucide.createIcons()`)
- Module-aware: only show nudges for installed modules. Skip queries entirely for uninstalled modules.

## Step 5: Write, Register, and Open

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/nudges.html`

**Register the view:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Nudges', 'nudges.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Open with: `open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/nudges.html"`

Tell the user: "Nudges view opened." Then summarize: "X urgent, Y upcoming, Z worth a look." or "All clear — nothing needs your attention."
