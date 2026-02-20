---
description: Generate a visual calendar week view — your schedule with attendee context and prep links
allowed-tools: ["Bash", "Read", "Write"]
---

# Generate Calendar Week View

Generate a standalone HTML page showing the user's calendar week — the Calendar module's dedicated view page. A visual 7-day grid with event detail cards and next-week preview.

## Step 0: Auto-Sync Calendar

Before building the view, ensure calendar data is fresh. Follow the auto-sync procedure in CLAUDE.md — check `calendar_last_synced` in `soy_meta`, and sync if stale (>15 min) or never synced. Do this silently.

## Step 1: Read the Design System

Read these files first:
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/template-base.html` — HTML skeleton
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/navigation-patterns.md` — nav bar patterns

## Step 2: Gather Data

Query `${CLAUDE_PLUGIN_ROOT}/data/soy.db`:

```sql
-- This week's events (Monday through Sunday of current week)
SELECT ce.id, ce.title, ce.description, ce.location, ce.start_time, ce.end_time,
  ce.all_day, ce.status, ce.attendees, ce.contact_ids, ce.project_id
FROM calendar_events ce
WHERE date(ce.start_time) BETWEEN date('now', 'weekday 1', '-7 days') AND date('now', 'weekday 0')
  AND ce.status != 'cancelled'
ORDER BY ce.start_time ASC;

-- Next week's events (preview)
SELECT ce.id, ce.title, ce.start_time, ce.end_time, ce.attendees, ce.contact_ids
FROM calendar_events ce
WHERE date(ce.start_time) BETWEEN date('now', 'weekday 1') AND date('now', 'weekday 0', '+7 days')
  AND ce.status != 'cancelled'
ORDER BY ce.start_time ASC;

-- Week stats
SELECT
  COUNT(*) as total_events,
  SUM(CASE WHEN all_day = 1 THEN 1 ELSE 0 END) as all_day_events,
  COUNT(DISTINCT date(start_time)) as days_with_events,
  SUM(CAST((julianday(end_time) - julianday(start_time)) * 24 AS INTEGER)) as total_hours
FROM calendar_events
WHERE date(start_time) BETWEEN date('now', 'weekday 1', '-7 days') AND date('now', 'weekday 0')
  AND status != 'cancelled' AND all_day = 0;

-- Resolve contacts from event attendees
SELECT id, name, company, role FROM contacts WHERE status = 'active';

-- Projects linked to events
SELECT id, name, status FROM projects WHERE id IN (
  SELECT DISTINCT project_id FROM calendar_events WHERE project_id IS NOT NULL
);

-- Entity pages for linking
SELECT entity_id, entity_type, filename FROM generated_views
WHERE view_type = 'entity_page';
```

Also query for navigation links:
```sql
SELECT view_type, entity_name, filename, updated_at
FROM generated_views
ORDER BY updated_at DESC
LIMIT 10;
```

## Step 3: Generate HTML

Generate a self-contained HTML file following the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font).

### Nav Bar

Include the nav bar from `navigation-patterns.md`. For this page:
- Left side: Dashboard link + separator + "Week View" as current page (plain text, not a link)
- Right side: Quick links to generated entity pages (up to 5 most recent)

```html
<nav class="flex items-center justify-between mb-6 pb-4 border-b border-zinc-200">
    <div class="flex items-center gap-3">
        <a href="dashboard.html" class="flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-900 transition-colors">
            <i data-lucide="layout-dashboard" class="w-4 h-4"></i>
            <span>Dashboard</span>
        </a>
        <span class="text-zinc-300">/</span>
        <span class="text-sm font-medium text-zinc-900">Week View</span>
    </div>
    <div class="flex items-center gap-2">
        <!-- Quick links to entity pages from generated_views -->
    </div>
</nav>
```

### Layout Structure

```
Nav bar

Header card
├── Title: "This Week" + date range (e.g., "Feb 17–23, 2026")
├── Stat pills: Total events, Meeting hours, Busiest day, Days free
└── Week navigation hint: "Next week: X events"

Day columns (7 days, Mon–Sun)
┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Monday   │ Tuesday  │Wednesday │ Thursday │ Friday   │ Saturday │ Sunday   │
│ Feb 17   │ Feb 18   │ Feb 19   │ Feb 20   │ Feb 21   │ Feb 22   │ Feb 23   │
│          │          │ ★ TODAY  │          │          │          │          │
├──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ Event    │          │ Event    │ Event    │ Event    │          │          │
│ cards    │ No       │ cards    │ cards    │ cards    │ Free     │ Free     │
│ stacked  │ meetings │ stacked  │ stacked  │ stacked  │          │          │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘

Event Detail Cards (full width, for events with attendees/projects)

Next Week Preview (compact list)

Footer
```

### Header Card

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-6 mb-6">
    <div class="flex items-center justify-between">
        <div>
            <div class="flex items-center gap-2">
                <i data-lucide="calendar" class="w-5 h-5 text-zinc-700"></i>
                <h1 class="text-2xl font-bold text-zinc-900">This Week</h1>
            </div>
            <p class="text-sm text-zinc-500 mt-1">Feb 17–23, 2026</p>
        </div>
        <div class="flex items-center gap-3">
            <!-- Stat pills -->
            <span class="px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700">X events</span>
            <span class="px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700">Y hrs meetings</span>
            <span class="px-3 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700">Busiest: Day</span>
            <span class="px-3 py-1 rounded-full text-xs font-medium bg-zinc-100 text-zinc-600">Z days free</span>
        </div>
    </div>
    <p class="text-xs text-zinc-400 mt-3">Next week: X events</p>
</div>
```

### Day Columns — Week Grid

Use a responsive 7-column grid:

```html
<div class="grid grid-cols-1 md:grid-cols-7 gap-3 mb-8">
    <!-- One column per day, Monday through Sunday -->
</div>
```

**For each day column:**

```html
<!-- Regular day -->
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-3 min-h-[200px]">
    <div class="text-center mb-3 pb-2 border-b border-zinc-100">
        <div class="text-xs font-medium text-zinc-500 uppercase">Monday</div>
        <div class="text-lg font-semibold text-zinc-900">17</div>
        <div class="text-xs text-zinc-400">Feb</div>
    </div>
    <!-- Event cards stacked here -->
</div>

<!-- TODAY column — highlighted -->
<div class="bg-amber-50/50 rounded-xl shadow-sm border border-amber-200 p-3 min-h-[200px]">
    <div class="text-center mb-3 pb-2 border-b border-amber-200">
        <div class="text-xs font-medium text-amber-600 uppercase">Wednesday</div>
        <div class="text-lg font-semibold text-amber-900">19</div>
        <div class="text-xs text-amber-500">Today</div>
    </div>
    <!-- Event cards -->
</div>

<!-- Past day — dimmed -->
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-3 min-h-[200px] opacity-70">
    <!-- ... -->
</div>
```

### Event Cards Within Day Columns

Each event card inside a day column:

```html
<div class="bg-zinc-50 rounded-lg p-2 mb-2 border-l-3 border-blue-400">
    <div class="text-xs font-medium text-zinc-500">9:00 AM</div>
    <div class="text-sm font-semibold text-zinc-900 truncate">Team Standup</div>
    <div class="text-xs text-zinc-400">30 min</div>
    <!-- Attendees (first names only) -->
    <div class="text-xs text-zinc-500 mt-1">Sarah, Daniel</div>
    <!-- Location if present -->
    <div class="flex items-center gap-1 text-xs text-zinc-400 mt-0.5">
        <i data-lucide="map-pin" class="w-3 h-3"></i>
        <span>Room B</span>
    </div>
</div>
```

**Color-coded left border by type:**
- `border-blue-400` — meetings (3+ attendees or general)
- `border-emerald-400` — 1:1s (exactly 2 attendees)
- `border-amber-400` — all-day events
- `border-zinc-300` — personal / no attendees

**Duration formatting:**
- Under 60 min: "30 min", "45 min"
- Exactly 60 min: "1 hr"
- Over 60 min: "1.5 hrs", "2 hrs"

**Attendee names:** Show first names only in the day column cards. Link to entity page if exists, using the linking pattern from `navigation-patterns.md`.

**Free days:** When a day has no events, show:
```html
<div class="flex items-center justify-center h-24 text-zinc-300">
    <div class="text-center">
        <i data-lucide="sun" class="w-5 h-5 mx-auto mb-1"></i>
        <span class="text-xs">Free</span>
    </div>
</div>
```

### Event Detail Cards (below the week grid)

For each event that has attendees or a project link, show a full-width detail card:

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-4 mb-3">
    <div class="flex items-start justify-between">
        <div>
            <h3 class="font-semibold text-zinc-900">Discovery Call — Sarah Chen</h3>
            <p class="text-sm text-zinc-500">Wednesday, Feb 19 · 10:30 AM – 11:30 AM · 1 hr</p>
        </div>
        <!-- Prep link if entity page exists -->
        <a href="contact-sarah-chen.html" class="text-xs text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1">
            <span>View prep</span>
            <i data-lucide="arrow-right" class="w-3 h-3"></i>
        </a>
    </div>
    <!-- Attendees with full detail -->
    <div class="mt-3 flex flex-wrap gap-2">
        <span class="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs bg-zinc-100 text-zinc-600">
            <span class="w-5 h-5 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-medium">SC</span>
            Sarah Chen · Meridian Labs · CTO
        </span>
    </div>
    <!-- Project link if linked -->
    <div class="mt-2 flex items-center gap-1.5 text-xs text-zinc-500">
        <i data-lucide="folder" class="w-3 h-3"></i>
        <span>Project: Website Redesign</span>
    </div>
    <!-- Description if available -->
    <p class="mt-2 text-sm text-zinc-500">Discuss Q2 roadmap and resource allocation.</p>
</div>
```

Only show detail cards for events with attendees or project links. Skip simple/personal events.

### Next Week Preview

Below the detail cards, a compact preview of next week:

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5 mb-6">
    <div class="flex items-center gap-2 mb-3">
        <i data-lucide="calendar-plus" class="w-4 h-4 text-zinc-500"></i>
        <h2 class="text-sm font-semibold text-zinc-700">Next Week — X events</h2>
    </div>
    <div class="space-y-1.5">
        <div class="flex items-center gap-3 text-sm">
            <span class="text-zinc-400 w-20">Mon 24</span>
            <span class="text-zinc-500 w-16">9:00 AM</span>
            <span class="text-zinc-700">Team Standup</span>
        </div>
        <!-- More events -->
    </div>
</div>
```

If next week has no events: "No events scheduled for next week."

### Footer

```html
<footer class="mt-8 pt-4 border-t border-zinc-100 text-center">
    <p class="text-xs text-zinc-400">Generated by Software of You · DATE at TIME</p>
</footer>
```

## Design Rules (non-negotiable)

- Use the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- Today column: `bg-amber-50/50 border-amber-200`
- Past day columns: `opacity-70`
- Event cards within days: `bg-zinc-50 rounded-lg p-2 mb-2 border-l-3`
- Responsive: on mobile, day columns stack vertically (`grid-cols-1 md:grid-cols-7`)
- All data static in HTML — no JavaScript data fetching
- The only JS: `lucide.createIcons()`
- Lucide icons: `calendar` header, `map-pin` location, `sun` free day, `folder` projects, `arrow-right` links, `calendar-plus` next week, `layout-dashboard` nav
- Status color-coding: blue (meetings), emerald (1:1s), amber (all-day), zinc (personal)

### Contact Name Linking

Anywhere a contact name appears (event cards, detail cards, attendee lists), check if that contact has a generated entity page in the `generated_views` query results. If so, render the name as a clickable link:
```html
<a href="contact-sarah-chen.html" class="font-medium text-blue-600 hover:text-blue-800 hover:underline">Sarah</a>
```
If no page exists, render as plain text.

### Empty States

- No events this week: Show all 7 day columns with "Free" state. Header shows "0 events". Detail cards section hidden.
- No events next week: "No events scheduled for next week." with `calendar-off` icon.
- Calendar module not installed: Do not run this command. Tell the user: "Calendar module is not installed. Run `/google-setup` to connect your calendar."

## Step 4: Write, Register, Open

Write to `${CLAUDE_PLUGIN_ROOT}/output/week-view.html`.

**Register the view:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Week View', 'week-view.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Open: `open "${CLAUDE_PLUGIN_ROOT}/output/week-view.html"`

Tell user: "Week view opened. X events this week, Y hours of meetings."
