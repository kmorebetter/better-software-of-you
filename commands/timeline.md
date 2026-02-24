---
description: Generate a Timeline view — unified chronological feed of all activity across every module with client-side filtering
allowed-tools: ["Bash", "Read", "Write"]
---

# Generate Timeline

Generate a unified timeline page showing all activity across every module in chronological order. This is the "full story" view — everything that happened, when it happened.

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

### Timeline Data Sources

Build a unified timeline from multiple tables. Each source gets queried separately, then merged and sorted by timestamp during HTML generation.

**Activity log** (always):
```sql
SELECT 'activity' as source, al.entity_type, al.entity_id, al.action, al.details, al.created_at as ts,
  CASE al.entity_type
    WHEN 'contact' THEN (SELECT name FROM contacts WHERE id = al.entity_id)
    WHEN 'project' THEN (SELECT name FROM projects WHERE id = al.entity_id)
    ELSE al.entity_type || ' #' || al.entity_id
  END as entity_name
FROM activity_log al
WHERE al.created_at >= date('now', '-30 days')
ORDER BY al.created_at DESC
LIMIT 100;
```

**Calendar events** (if Calendar installed):
```sql
SELECT 'calendar' as source, 'event' as entity_type, ce.id as entity_id,
  ce.title, ce.start_time as ts, ce.end_time, ce.location, ce.attendees
FROM calendar_events ce
WHERE date(ce.start_time) BETWEEN date('now', '-30 days') AND date('now', '+7 days')
  AND ce.status != 'cancelled'
ORDER BY ce.start_time DESC
LIMIT 50;
```

**Emails** (if Gmail installed):
```sql
SELECT 'email' as source, 'email' as entity_type, e.id as entity_id,
  e.subject as title, e.snippet, e.from_name, e.from_address, e.direction,
  e.received_at as ts, e.is_read,
  c.name as contact_name, c.id as contact_id
FROM emails e
LEFT JOIN contacts c ON e.contact_id = c.id
WHERE e.received_at >= date('now', '-30 days')
ORDER BY e.received_at DESC
LIMIT 50;
```

**Decisions** (if Decision Log installed):
```sql
SELECT 'decision' as source, 'decision' as entity_type, d.id as entity_id,
  d.title, d.status, d.decided_at as ts
FROM decisions d
WHERE d.decided_at >= date('now', '-30 days') OR d.created_at >= date('now', '-30 days')
ORDER BY COALESCE(d.decided_at, d.created_at) DESC
LIMIT 30;
```

**Journal entries** (if Journal installed):
```sql
SELECT 'journal' as source, 'journal' as entity_type, je.id as entity_id,
  je.mood, je.energy, je.content, je.entry_date as ts
FROM journal_entries je
WHERE je.entry_date >= date('now', '-30 days')
ORDER BY je.entry_date DESC
LIMIT 30;
```

**Commitments completed** (if Conversation Intelligence installed):
```sql
SELECT 'commitment' as source, 'commitment' as entity_type, com.id as entity_id,
  com.description as title, com.completed_at as ts,
  CASE WHEN com.is_user_commitment = 1 THEN 'You' ELSE c.name END as owner_name,
  c.id as owner_id
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
WHERE com.status = 'completed' AND com.completed_at >= date('now', '-30 days')
ORDER BY com.completed_at DESC
LIMIT 30;
```

**Transcripts** (if Conversation Intelligence installed):
```sql
SELECT 'transcript' as source, 'transcript' as entity_type, t.id as entity_id,
  t.title, t.duration_minutes, t.occurred_at as ts,
  GROUP_CONCAT(DISTINCT c.name) as participant_names
FROM transcripts t
LEFT JOIN transcript_participants tp ON tp.transcript_id = t.id
LEFT JOIN contacts c ON c.id = tp.contact_id AND tp.is_user = 0
WHERE t.occurred_at >= date('now', '-30 days')
GROUP BY t.id
ORDER BY t.occurred_at DESC
LIMIT 20;
```

## Step 3: Merge and Group

Merge all timeline entries by timestamp and group into date buckets:

1. **Today** — entries from today
2. **Yesterday** — entries from yesterday
3. **This Week** — entries from earlier this week (but not today/yesterday)
4. **Last Week** — entries from the previous week
5. **Earlier** — everything else (collapsed by default with `<details>`)

**Cap at 200 total entries** across all sources to keep page size reasonable. Deduplicate: if an activity_log entry references the same entity as a calendar event or email, prefer the more specific source (email/calendar) and skip the activity_log entry.

## Step 4: Generate HTML

Generate a self-contained HTML file. Follow the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font).

### Sidebar

Include the sidebar from `navigation-patterns.md` with Timeline active in the Tools section.

### Page Structure

```
Sidebar (Timeline active in Tools section)

Header card (full width)
+-- Title: "Timeline"
+-- Subtitle: "Activity across everything — last 30 days"
+-- Filter tabs (inline, right-aligned):
    [All] [People] [Email] [Calendar] [Projects] [Decisions] [Journal]

Timeline content (full width)
+-- Date bucket: "Today"
|   +-- Entry 1
|   +-- Entry 2
+-- Date bucket: "Yesterday"
|   +-- Entry 3
+-- Date bucket: "This Week"
|   +-- Entries...
+-- Date bucket: "Last Week"
|   +-- Entries...
+-- Date bucket: "Earlier" (collapsed <details>)
    +-- Entries...

Footer
```

### Filter Tabs

Client-side JavaScript to show/hide entries by `data-source` attribute. Each timeline entry gets a `data-source` attribute matching its source type.

```html
<div class="flex items-center gap-1 flex-wrap">
  <button class="filter-tab active" data-filter="all">All</button>
  <button class="filter-tab" data-filter="activity">People</button>
  <button class="filter-tab" data-filter="email">Email</button>
  <button class="filter-tab" data-filter="calendar">Calendar</button>
  <button class="filter-tab" data-filter="activity-project">Projects</button>
  <button class="filter-tab" data-filter="decision">Decisions</button>
  <button class="filter-tab" data-filter="journal">Journal</button>
</div>
```

Only show filter tabs for installed modules.

### Filter Tab CSS

```css
.filter-tab {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  color: #71717a;
  background: transparent;
  border: 1px solid #e4e4e7;
  cursor: pointer;
  transition: all 0.15s;
}
.filter-tab:hover {
  background: #f4f4f5;
  color: #18181b;
}
.filter-tab.active {
  background: #18181b;
  color: white;
  border-color: #18181b;
}
```

### Filter JavaScript (~30 lines)

```html
<script>
document.addEventListener('DOMContentLoaded', function() {
  lucide.createIcons();

  const tabs = document.querySelectorAll('.filter-tab');
  const entries = document.querySelectorAll('.timeline-entry');
  const buckets = document.querySelectorAll('.date-bucket');

  tabs.forEach(tab => {
    tab.addEventListener('click', function() {
      tabs.forEach(t => t.classList.remove('active'));
      this.classList.add('active');
      const filter = this.dataset.filter;

      entries.forEach(entry => {
        if (filter === 'all' || entry.dataset.source === filter) {
          entry.style.display = '';
        } else {
          entry.style.display = 'none';
        }
      });

      // Hide empty date buckets
      buckets.forEach(bucket => {
        const visible = bucket.querySelectorAll('.timeline-entry:not([style*="display: none"])');
        bucket.style.display = visible.length > 0 ? '' : 'none';
      });
    });
  });
});
</script>
```

### Date Bucket Headers

```html
<div class="date-bucket">
  <div class="flex items-center gap-3 mt-6 mb-4">
    <h3 class="text-xs font-semibold text-zinc-400 uppercase tracking-wider whitespace-nowrap">Today</h3>
    <div class="flex-1 h-px bg-zinc-200"></div>
    <span class="text-xs text-zinc-300">Feb 19</span>
  </div>
  <!-- entries -->
</div>
```

The "Earlier" bucket uses `<details>` for native collapse:

```html
<details class="date-bucket mt-6">
  <summary class="flex items-center gap-3 mb-4 cursor-pointer">
    <h3 class="text-xs font-semibold text-zinc-400 uppercase tracking-wider whitespace-nowrap">Earlier</h3>
    <div class="flex-1 h-px bg-zinc-200"></div>
    <span class="text-xs text-zinc-300">X entries</span>
  </summary>
  <!-- entries -->
</details>
```

### Timeline Entry Design

Each entry has a colored left border and icon matching its source type:

```html
<div class="timeline-entry bg-white rounded-lg border border-zinc-200 p-4 mb-2 border-l-4 border-l-blue-400" data-source="activity">
  <div class="flex items-start gap-3">
    <div class="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center shrink-0 mt-0.5">
      <i data-lucide="users" class="w-4 h-4 text-blue-500"></i>
    </div>
    <div class="flex-1 min-w-0">
      <div class="flex items-center justify-between gap-2">
        <p class="text-sm text-zinc-900">
          <span class="font-medium">Added interaction</span> with
          <a href="contact-sarah-chen.html" class="text-blue-600 hover:text-blue-800 hover:underline">Sarah Chen</a>
        </p>
        <span class="text-xs text-zinc-400 whitespace-nowrap">2:30 PM</span>
      </div>
      <p class="text-xs text-zinc-500 mt-1 line-clamp-2">Discovery call about Meridian project</p>
    </div>
  </div>
</div>
```

### Visual Differentiation by Source Type

| Source | Icon | Color | Border | Background |
|--------|------|-------|--------|------------|
| Contact/CRM activity | `users` | blue-500 | `border-l-blue-400` | `bg-blue-50` |
| Email | `mail` | indigo-500 | `border-l-indigo-400` | `bg-indigo-50` |
| Calendar | `calendar` | green-500 | `border-l-green-400` | `bg-green-50` |
| Project/Task activity | `folder` | purple-500 | `border-l-purple-400` | `bg-purple-50` |
| Decision | `git-branch` | amber-500 | `border-l-amber-400` | `bg-amber-50` |
| Journal | `book-open` | rose-500 | `border-l-rose-400` | `bg-rose-50` |
| Commitment | `target` | teal-500 | `border-l-teal-400` | `bg-teal-50` |
| Transcript | `message-square` | cyan-500 | `border-l-cyan-400` | `bg-cyan-50` |

### Entry Content by Source Type

**Activity log entry:**
- Title: `{action}` with `{entity_name}` (linked if entity page exists)
- Detail: `{details}` (truncated, line-clamp-2)
- Time: relative or time-of-day

**Calendar event:**
- Title: Event title
- Detail: time range + location + attendee names (linked to entity pages if they exist)
- Future events: subtle badge "upcoming"

**Email:**
- Title: Direction arrow (↗/↙) + subject
- Detail: from/to name + snippet (truncated)
- Unread: bold subject, blue dot indicator

**Decision:**
- Title: Decision title
- Detail: status badge (`decided`, `exploring`, `revisiting`)

**Journal entry:**
- Title: "Journal entry" + mood badge (if set)
- Detail: first ~100 chars of content + energy dots (if set)

**Commitment completed:**
- Title: "Completed commitment" + description
- Detail: "By {owner_name}"

**Transcript:**
- Title: Call title + duration badge
- Detail: participant names (linked)

### Contact Name Linking

Throughout all entries, check if a referenced contact has a generated entity page. If so, render as a link:
```html
<a href="contact-{slug}.html" class="text-blue-600 hover:text-blue-800 hover:underline">Name</a>
```

### Empty State

If no timeline data exists at all:

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-12 text-center">
  <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-zinc-50 mb-4">
    <i data-lucide="clock" class="w-8 h-8 text-zinc-300"></i>
  </div>
  <h3 class="text-lg font-semibold text-zinc-900 mb-1">No activity yet</h3>
  <p class="text-sm text-zinc-500">Your timeline will fill up as you add contacts, log interactions, and use the platform.</p>
</div>
```

## Design Rules (non-negotiable)

- Use the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-lg border border-zinc-200`
- Left borders on entries are 4px using the source color
- Icon containers: 32px square, rounded-lg, source-colored background with matching icon
- All timeline data is static in HTML — the JavaScript only toggles visibility of existing elements
- Maximum 200 entries across all sources
- Last 30 days by default, "Earlier" section collapsed with `<details>`
- Responsive: entries stack naturally (single column)

## Step 5: Write, Register, and Open

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/timeline.html`

**Register the view:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Timeline', 'timeline.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Open with: `open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/timeline.html"`

Tell the user: "Timeline opened." Then briefly summarize — e.g., "Showing 47 entries over the last 30 days across contacts, email, calendar, and decisions."
