---
description: Generate and open a unified HTML dashboard
allowed-tools: ["Bash", "Read", "Write"]
---

# Generate Dashboard

Generate the Software of You home dashboard. This is a **fixed-layout** dashboard — the same sections appear in the same order every time. You fill in the data, but do NOT change the structure.

**The dashboard adapts to what's installed.** If Google is connected, email and calendar are primary content, not afterthoughts. The layout shifts to put the most actionable data first.

## Step 0: Auto-Sync External Data

Before building the dashboard, ensure data is fresh. Follow the auto-sync procedure in CLAUDE.md — check `gmail_last_synced` and `calendar_last_synced` in `soy_meta`, and sync if stale (>15 min) or never synced. Do this silently.

## Step 1: Read the Design System

Read these files first:
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/template-base.html` — HTML skeleton
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/component-patterns.md` — component snippets
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/navigation-patterns.md` — sidebar patterns

## Step 2: Gather Data

Query `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`. Check installed modules first:
```sql
SELECT name FROM modules WHERE enabled = 1;
```

**Query generated views** (for navigation and contact linking):
```sql
SELECT entity_name, entity_id, filename, updated_at FROM generated_views
WHERE view_type = 'entity_page' ORDER BY updated_at DESC LIMIT 10;
```

**Always query:**
```sql
-- Contact stats
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
SELECT f.*, c.name as contact_name FROM follow_ups f
JOIN contacts c ON f.contact_id = c.id
WHERE f.status = 'pending' ORDER BY f.due_date ASC LIMIT 8;
```

**If Project Tracker installed:**
```sql
SELECT status, COUNT(*) as count FROM projects GROUP BY status;

SELECT p.id, p.name, p.status, p.priority, p.target_date, c.name as client_name
FROM projects p LEFT JOIN contacts c ON p.client_id = c.id
WHERE p.status IN ('active', 'planning') ORDER BY p.priority DESC, p.updated_at DESC;

SELECT status, COUNT(*) as count FROM tasks GROUP BY status;

SELECT t.title, t.due_date, p.name as project_name FROM tasks t
JOIN projects p ON t.project_id = p.id
WHERE t.due_date < date('now') AND t.status NOT IN ('done');
```

**If Calendar module installed (REQUIRED — not optional):**
```sql
-- Today's events (the hero data)
SELECT ce.id, ce.title, ce.start_time, ce.end_time, ce.location,
  ce.description, ce.attendees, ce.contact_ids, ce.status
FROM calendar_events ce
WHERE date(ce.start_time) = date('now') AND ce.status != 'cancelled'
ORDER BY ce.start_time ASC;

-- Tomorrow's events
SELECT ce.id, ce.title, ce.start_time, ce.end_time, ce.location,
  ce.attendees, ce.contact_ids
FROM calendar_events ce
WHERE date(ce.start_time) = date('now', '+1 day') AND ce.status != 'cancelled'
ORDER BY ce.start_time ASC;

-- Rest of the week (next 5 days, excluding today and tomorrow)
SELECT ce.id, ce.title, ce.start_time, ce.end_time, ce.location,
  ce.attendees, ce.contact_ids
FROM calendar_events ce
WHERE date(ce.start_time) BETWEEN date('now', '+2 days') AND date('now', '+6 days')
  AND ce.status != 'cancelled'
ORDER BY ce.start_time ASC;

-- Week stats
SELECT COUNT(*) as total_events,
  SUM(CASE WHEN date(start_time) = date('now') THEN 1 ELSE 0 END) as today_count
FROM calendar_events
WHERE start_time BETWEEN datetime('now') AND datetime('now', '+7 days')
  AND status != 'cancelled';
```

For each event with `contact_ids`, resolve contact names:
```sql
SELECT id, name, company FROM contacts WHERE id IN (/* contact_ids from events */);
```

**If Gmail module installed (REQUIRED — not optional):**
```sql
-- Active threads (last 14 days, with full context)
SELECT e.thread_id, e.subject, e.snippet, e.from_name, e.from_address,
  e.to_addresses, e.direction, e.received_at, e.is_read, e.is_starred,
  c.name as contact_name, c.company as contact_company, c.id as contact_id
FROM emails e
LEFT JOIN contacts c ON e.contact_id = c.id
WHERE e.received_at > datetime('now', '-14 days')
ORDER BY e.received_at DESC;

-- Unread count
SELECT COUNT(*) as unread FROM emails WHERE is_read = 0;

-- Starred/important
SELECT COUNT(*) as starred FROM emails WHERE is_starred = 1 AND is_read = 0;

-- Threads needing response (inbound emails with no outbound reply in same thread)
SELECT e.thread_id, e.subject, e.from_name, e.received_at, c.name as contact_name
FROM emails e
LEFT JOIN contacts c ON e.contact_id = c.id
WHERE e.direction = 'inbound'
  AND e.thread_id NOT IN (
    SELECT thread_id FROM emails
    WHERE direction = 'outbound' AND received_at > e.received_at
  )
  AND e.received_at > datetime('now', '-7 days')
GROUP BY e.thread_id
ORDER BY e.received_at DESC
LIMIT 5;
```

Group raw email results into threads: group by `thread_id`, show the latest message per thread, count messages per thread.

## Step 3: Generate HTML

Generate a self-contained HTML file. Follow this **exact layout structure**:

### Sidebar (always)
Include the sidebar from `navigation-patterns.md` with Dashboard active.

### Header (always)
- Title: "Software of You"
- Subtitle: today's date in human format (e.g., "Wednesday, February 19, 2026")
- Stat pills (right side): Contact count, Project count (if installed), Unread emails (if Gmail), Today's events (if Calendar)

---

### Intelligence Tools Strip (always, after header)

A 4-card grid linking to cross-cutting views. Place this between the header and Today's Agenda. Always include this section — it's the gateway to the platform's intelligence features.

**Query nudge count for the badge:**
```sql
-- Count urgent nudges (overdue follow-ups + overdue commitments + overdue tasks)
SELECT
  (SELECT COUNT(*) FROM follow_ups WHERE status = 'pending' AND due_date < date('now'))
  + (SELECT COUNT(*) FROM commitments WHERE status IN ('open','overdue') AND deadline_date < date('now'))
  + (SELECT COUNT(*) FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.status NOT IN ('done') AND t.due_date < date('now'))
  as urgent_count;
```

**HTML:**
```html
<!-- Intelligence Tools Strip -->
<div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
  <a href="weekly-review.html" class="bg-white rounded-xl border border-zinc-200 p-4 hover:border-blue-300 hover:shadow-sm transition-all group">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center">
        <i data-lucide="clipboard-list" class="w-4.5 h-4.5 text-blue-600"></i>
      </div>
      <div>
        <div class="text-sm font-semibold text-zinc-900 group-hover:text-blue-700">Weekly Review</div>
        <div class="text-xs text-zinc-500">Your week at a glance</div>
      </div>
    </div>
  </a>
  <a href="nudges.html" class="bg-white rounded-xl border border-zinc-200 p-4 hover:border-amber-300 hover:shadow-sm transition-all group">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center relative">
        <i data-lucide="bell" class="w-4.5 h-4.5 text-amber-600"></i>
        <!-- Show red dot badge if urgent_count > 0. Hide this span entirely if urgent_count is 0. -->
        <span class="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-[10px] text-white flex items-center justify-center font-bold">N</span>
      </div>
      <div>
        <div class="text-sm font-semibold text-zinc-900 group-hover:text-amber-700">Nudges</div>
        <div class="text-xs text-zinc-500">Items need attention</div>
      </div>
    </div>
  </a>
  <a href="timeline.html" class="bg-white rounded-xl border border-zinc-200 p-4 hover:border-purple-300 hover:shadow-sm transition-all group">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-lg bg-purple-50 flex items-center justify-center">
        <i data-lucide="clock" class="w-4.5 h-4.5 text-purple-600"></i>
      </div>
      <div>
        <div class="text-sm font-semibold text-zinc-900 group-hover:text-purple-700">Timeline</div>
        <div class="text-xs text-zinc-500">Activity across everything</div>
      </div>
    </div>
  </a>
  <a href="search.html" class="bg-white rounded-xl border border-zinc-200 p-4 hover:border-emerald-300 hover:shadow-sm transition-all group">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center">
        <i data-lucide="search" class="w-4.5 h-4.5 text-emerald-600"></i>
      </div>
      <div>
        <div class="text-sm font-semibold text-zinc-900 group-hover:text-emerald-700">Search</div>
        <div class="text-xs text-zinc-500">Find anything</div>
      </div>
    </div>
  </a>
</div>
```

Replace `N` in the Nudges badge with the actual `urgent_count` value. If `urgent_count` is 0, omit the red badge `<span>` entirely.

---

### TODAY'S AGENDA — Hero Card (if Calendar installed)

**This is the most prominent card on the dashboard.** Full width, top of the page, visually distinct.

Card styling: `bg-white rounded-xl shadow-sm border border-zinc-200 p-6`
Header: Lucide `calendar` icon + "Today" + day of week + date + event count pill

**Render each event as a row:**
```
┌─────────────────────────────────────────────────────────────┐
│  9:00 AM   Team Standup                          30 min    │
│            Daily sync with engineering team                 │
│                                                             │
│  10:30 AM  Sarah Chen — Discovery Call    ← amber if next  │
│            Meridian Labs · Google Meet                      │
│            [View prep →]  (link to entity page if exists)   │
│                                                             │
│  2:00 PM   Project Review with Daniel                      │
│            Byrne Properties · Conference Room B             │
└─────────────────────────────────────────────────────────────┘
```

For each event:
- **Time**: formatted as `h:mm AM/PM` in bold, with duration on the right
- **Title**: event title, bold
- **Context line**: attendee names (resolved from contacts), location, meeting link
- **Highlight the NEXT upcoming event** with `bg-amber-50 border-l-4 border-amber-400` and a "Next up" badge
- **Past events today**: slightly dimmed (`opacity-60`), with a subtle checkmark
- If an attendee has an entity page, link their name: `[Sarah Chen →]` opens entity page

If today has no events: show "No meetings today" with a subtle `calendar-off` icon. Still show the card.

**Tomorrow preview**: Below today's events, a subtle divider line, then "Tomorrow" with a compact list (just times and titles, no full details). This gives a look-ahead without cluttering.

---

### EMAIL INBOX — Primary Card (if Gmail installed)

**This card shows what needs attention.** Not a data dump — curated, prioritized.

Card styling: same white card. Header: Lucide `mail` icon + "Inbox" + unread count badge (`bg-blue-100 text-blue-700 rounded-full px-2 py-0.5 text-xs font-medium`)

**Section 1: Needs Response** (threads where you received an email but haven't replied)
- Show up to 5 threads
- Each shows: contact name (or sender name), subject, snippet (truncated to ~80 chars), time received (relative: "2 hours ago", "yesterday")
- Contact avatar (initials circle, `bg-blue-100 text-blue-700`)
- If the contact has an entity page, name is a link
- Styling: `border-l-4 border-amber-400` to signal "action needed"

**Section 2: Recent Threads** (latest email activity, excluding the above)
- Show up to 8 threads, grouped by thread_id
- Each shows: contact name/avatar, subject, message count badge, last activity time, direction arrow (↗ outbound, ↙ inbound for the latest message)
- Starred threads get a `star` icon in yellow
- Unread threads have bold subject text

**Empty state**: "Inbox clear — no unread emails." with a `mail-check` icon.

---

### Row 1: Two-column grid

- **Left: Active Projects** (if Project Tracker installed) — table with project name, client (linked to entity page if exists), status badge, target date. If no projects, show "Contacts" card instead.
- **Right: Task Overview** (if Project Tracker installed) — 4 stat boxes showing todo/in-progress/done/blocked counts. Below: overdue task warning if any exist (red text, task name + project name + days overdue). If no Project Tracker, show "Contacts" card.

### Row 2: Two-column grid

- **Left: Contacts** — list of recent contacts with name, company/role, email. Each contact name links to entity page if one exists. If already shown in Row 1, show "Tags" or skip.
- **Right: Upcoming Follow-ups** (if CRM installed) — list with contact name, reason, due date. Overdue items: `bg-red-50 border-l-4 border-red-400 text-red-700`. Due today: `bg-amber-50 border-l-4 border-amber-400`. If no CRM, skip this card.

### Row 3: Full-width

- **Activity Timeline** — full-width card with recent activity entries. Each entry shows: Lucide icon (by type), action description, entity name (linked if entity page exists), and relative timestamp. Group entries that happened on the same day under a date header.

### Footer
- "Generated by Software of You" with installed module names and count.

---

## Layout Priority Rules

The dashboard must adapt intelligently based on installed modules:

**Calendar + Gmail both installed (full experience):**
1. Today's Agenda (hero, full width)
2. Email Inbox (full width)
3. Projects + Tasks (two-column)
4. Contacts + Follow-ups (two-column)
5. Activity Timeline (full width)

**Calendar only (no Gmail):**
1. Today's Agenda (hero, full width)
2. Projects + Tasks OR Contacts (two-column)
3. Follow-ups + Contacts (two-column)
4. Activity Timeline (full width)

**Gmail only (no Calendar):**
1. Email Inbox (full width)
2. Projects + Tasks (two-column)
3. Contacts + Follow-ups (two-column)
4. Activity Timeline (full width)

**No Google connected:**
1. Projects + Tasks (two-column)
2. Contacts + Follow-ups (two-column)
3. Activity Timeline (full width)
4. Add a callout card: `bg-blue-50 border border-blue-100 rounded-xl p-4` — "Connect Google to see your email and calendar here. Run `/google-setup`."

---

## Design Rules (non-negotiable)

- Use the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200 p-6`
- Status badges: green (active/done), blue (planning/in-progress), amber (pending/next), red (overdue/blocked), zinc (paused/inactive)
- Lucide icons: `users` contacts, `folder`/`folder-open` projects, `check-square` tasks, `clock` follow-ups, `activity` timeline, `calendar` events, `mail` emails, `arrow-up-right` outbound, `arrow-down-left` inbound, `star` starred, `alert-circle` overdue
- All data static in HTML — no JavaScript data fetching
- Responsive: `grid grid-cols-1 lg:grid-cols-2 gap-6`
- The only JS: Lucide icon initialization (`lucide.createIcons()`)

### Contact Name Linking

Anywhere a contact name appears (activity feed, follow-ups, project cards, email threads, calendar events), check if that contact has a generated entity page in the `generated_views` query results. If so, render the name as a clickable link to that page. If not, render as plain text. Follow the pattern in `navigation-patterns.md`.

### Empty States

If a section has no data, show a subtle empty state:
- No events today: "No meetings today" with `calendar-off` icon
- No unread email: "Inbox clear" with `mail-check` icon
- No projects: "No active projects — try `/project <name>` to start one"
- No contacts: "Add your first contact — just tell me about someone"

Never hide a section because it's empty if the module is installed. Show the empty state instead — it tells the user the feature is available.

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/dashboard.html`.

## Step 4: Register, Open

**Register the dashboard view:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('dashboard', NULL, NULL, 'Dashboard', 'dashboard.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Run: `open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/dashboard.html"`

Tell the user: "Dashboard updated and opened."
