---
description: Generate a Journal view — your entries with mood and energy trends, highlights, and cross-references
allowed-tools: ["Bash", "Read", "Write"]
---

# Generate Journal View

Generate a standalone HTML page for the Journal module — showing entries with mood/energy trends and linked highlights.

## Step 1: Read the Design System

Read these files first:
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/template-base.html` — HTML skeleton
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/navigation-patterns.md` — nav bar patterns

## Step 2: Check Module & Gather Data

Query `${CLAUDE_PLUGIN_ROOT}/data/soy.db`. First verify the journal module is installed:

```sql
SELECT name FROM modules WHERE name = 'journal' AND enabled = 1;
```

If the journal module is not installed, tell the user: "Journal module is not installed. Run `/add-module journal` to enable it." and stop.

### Navigation data

```sql
SELECT view_type, entity_name, filename, updated_at
FROM generated_views
ORDER BY updated_at DESC
LIMIT 10;
```

### All journal entries (last 90 days)

```sql
SELECT je.*,
  GROUP_CONCAT(DISTINCT c.name) as contact_names,
  GROUP_CONCAT(DISTINCT p.name) as project_names
FROM journal_entries je
LEFT JOIN contacts c ON je.linked_contacts LIKE '%' || c.id || '%'
LEFT JOIN projects p ON je.linked_projects LIKE '%' || p.id || '%'
WHERE je.entry_date > date('now', '-90 days')
GROUP BY je.id
ORDER BY je.entry_date DESC;
```

### Stats (last 30 days)

```sql
SELECT
  COUNT(*) as total_entries,
  COUNT(DISTINCT entry_date) as days_journaled,
  ROUND(AVG(CASE WHEN energy IS NOT NULL THEN energy END), 1) as avg_energy,
  COUNT(CASE WHEN mood IS NOT NULL THEN 1 END) as entries_with_mood
FROM journal_entries
WHERE entry_date > date('now', '-30 days');
```

### Mood frequency (last 30 days)

```sql
SELECT mood, COUNT(*) as count
FROM journal_entries
WHERE mood IS NOT NULL AND entry_date > date('now', '-30 days')
GROUP BY mood
ORDER BY count DESC;
```

### Energy over time (last 30 days, for trend visualization)

```sql
SELECT entry_date, energy, mood
FROM journal_entries
WHERE energy IS NOT NULL AND entry_date > date('now', '-30 days')
ORDER BY entry_date ASC;
```

### Most mentioned contacts (last 30 days)

```sql
SELECT c.id, c.name, COUNT(*) as mention_count
FROM journal_entries je
JOIN contacts c ON je.linked_contacts LIKE '%' || c.id || '%'
WHERE je.entry_date > date('now', '-30 days')
GROUP BY c.id
ORDER BY mention_count DESC
LIMIT 5;
```

### Most mentioned projects (last 30 days)

```sql
SELECT p.id, p.name, COUNT(*) as mention_count
FROM journal_entries je
JOIN projects p ON je.linked_projects LIKE '%' || p.id || '%'
WHERE je.entry_date > date('now', '-30 days')
GROUP BY p.id
ORDER BY mention_count DESC
LIMIT 5;
```

### Entity pages for linking

```sql
SELECT entity_id, entity_type, filename FROM generated_views WHERE view_type = 'entity_page';
```

### Calculate streak

Determine the current journaling streak — the number of consecutive days (ending today or yesterday) that have at least one entry:

```sql
SELECT DISTINCT entry_date FROM journal_entries
WHERE entry_date <= date('now')
ORDER BY entry_date DESC
LIMIT 90;
```

Walk backward from today (or yesterday, if no entry today) counting consecutive days.

## Step 3: Generate HTML

Generate a self-contained HTML file following the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font).

### Nav Bar

Include the nav bar from `navigation-patterns.md`. For this page:
- Left side: Dashboard link + separator + "Journal" as current page (plain text, not a link)
- Right side: Quick links to generated entity pages (up to 5 most recent)

```html
<nav class="flex items-center justify-between mb-6 pb-4 border-b border-zinc-200">
    <div class="flex items-center gap-3">
        <a href="dashboard.html" class="flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-900 transition-colors">
            <i data-lucide="layout-dashboard" class="w-4 h-4"></i>
            <span>Dashboard</span>
        </a>
        <span class="text-zinc-300">/</span>
        <span class="text-sm font-medium text-zinc-900">Journal</span>
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
+-- Title: "Journal"
+-- Subtitle: "X entries over Y days"
+-- Stat pills: Entries (30d), Avg energy, Days journaled, Streak

Trends card (full width)
+-- Energy trend line (left, ~70% width)
|   +-- Simple SVG line chart (inline, no external library)
|   +-- X-axis: dates, Y-axis: energy 1-5
|   +-- Dots colored by mood (if available): green=positive, amber=neutral, red=rough
|   +-- Average line shown as dashed horizontal
|   +-- If fewer than 3 data points: "Journal more to see trends. Energy tracking starts when you mention how you're feeling."
+-- Mood cloud (right, ~30% width)
    +-- Most common moods as sized text (bigger = more frequent)
    +-- Colored: positive moods in emerald, neutral in zinc, tough moods in amber

Three-column grid below trends (lg:grid-cols-3):

Left (lg:col-span-2):

  Journal Entries (main content)
  +-- Grouped by week (with week header: "This Week", "Last Week", "Feb 3-9")
  +-- Each entry card:
  |   +-- Date header: day of week + date (e.g., "Wednesday, Feb 19")
  |   +-- Mood badge (if set): colored pill
  |   +-- Energy indicator (if set): 1-5 dots, filled up to the value
  |   +-- Content: the full journal text
  |   +-- Highlights: extracted key moments as subtle badges
  |   +-- Linked contacts: name pills (linked to entity pages if they exist)
  |   +-- Linked projects: name pills (linked to project pages if they exist)
  +-- Empty state: "No journal entries yet. Just tell me how your day is going."

Right sidebar (lg:col-span-1):

  People on Your Mind card
  +-- Most mentioned contacts (last 30 days)
  +-- Name + mention count + link to entity page if exists

  Projects in Focus card
  +-- Most mentioned projects
  +-- Name + mention count + link to project page if exists

Footer
```

### Header Card

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-6 mb-6">
    <div class="flex items-center justify-between">
        <div>
            <div class="flex items-center gap-2">
                <i data-lucide="book-open" class="w-5 h-5 text-zinc-700"></i>
                <h1 class="text-2xl font-bold text-zinc-900">Journal</h1>
            </div>
            <p class="text-sm text-zinc-500 mt-1">X entries over Y days</p>
        </div>
        <div class="flex items-center gap-3">
            <span class="px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700">X entries (30d)</span>
            <span class="px-3 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700">Avg energy: X.X</span>
            <span class="px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700">Y days journaled</span>
            <span class="px-3 py-1 rounded-full text-xs font-medium bg-zinc-100 text-zinc-600">Z day streak</span>
        </div>
    </div>
</div>
```

### Trends Card (Full Width)

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-6 mb-6">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="trending-up" class="w-5 h-5 text-zinc-400"></i>
        <h2 class="text-sm font-semibold text-zinc-700">Trends — Last 30 Days</h2>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Energy trend (left, spans 2 cols) -->
        <div class="lg:col-span-2">
            <h3 class="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-3">Energy Trend</h3>
            <!-- Inline SVG chart here -->
        </div>
        <!-- Mood cloud (right) -->
        <div>
            <h3 class="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-3">Mood Cloud</h3>
            <!-- Mood words sized by frequency -->
        </div>
    </div>
</div>
```

### Energy Trend SVG

Generate a simple inline SVG for the energy trend. **No external libraries.** All data is embedded statically.

- Width: 100% of container, viewBox with aspect ratio ~4:1 (e.g., `viewBox="0 0 600 150"`)
- Height: ~120-150px
- Plot energy values (1-5) as connected dots
- Dots: 6px radius circles, stroke white (2px), fill colored by mood category
- Line: 2px stroke, `stroke: #3b82f6` (blue-500)
- Average line: 1px dashed, `stroke: #d4d4d8` (zinc-300), label "avg" on the right
- X labels: date abbreviations (e.g., "Feb 5", "Feb 10") every 5-7 days, placed at bottom
- Y labels: 1-5 on left side
- Padding: leave space for labels (left ~30px, bottom ~20px, top ~10px, right ~30px)
- If fewer than 3 data points, show this message instead of the chart:
  ```html
  <div class="flex items-center justify-center h-[120px] text-zinc-300">
      <div class="text-center">
          <i data-lucide="activity" class="w-6 h-6 mx-auto mb-2"></i>
          <p class="text-sm text-zinc-400">Journal more to see trends.</p>
          <p class="text-xs text-zinc-300">Energy tracking starts when you mention how you're feeling.</p>
      </div>
  </div>
  ```

**Coordinate math for the SVG:**
- X position: map entry index across the available width (with padding)
- Y position: map energy (1-5) to the chart height. Energy 5 = top, energy 1 = bottom
  - Formula: `y = topPadding + (5 - energy) * (chartHeight / 4)`

**Dot colors by mood category:**
- Positive ("great", "energized", "happy", "excited", "grateful", "calm", "optimistic"): `fill: #10b981` (emerald-500)
- Neutral ("fine", "okay", "steady", "focused"): `fill: #71717a` (zinc-500)
- Tough ("rough", "tired", "stressed", "anxious", "frustrated"): `fill: #f59e0b` (amber-500)
- Low ("bad", "exhausted", "overwhelmed"): `fill: #ef4444` (red-500)
- No mood data: `fill: #3b82f6` (blue-500)

### Mood Cloud

Render the most common moods (from the mood frequency query) as sized text:
- Most frequent mood: `text-2xl font-bold`
- Second most: `text-xl font-semibold`
- Third: `text-lg font-medium`
- Others: `text-base`

Colored by category:
- Positive moods: `text-emerald-600`
- Neutral moods: `text-zinc-500`
- Tough moods: `text-amber-600`
- Low moods: `text-red-500`

Arrange as a flex-wrap cluster:
```html
<div class="flex flex-wrap items-center gap-3">
    <span class="text-2xl font-bold text-emerald-600">great</span>
    <span class="text-lg font-medium text-zinc-500">focused</span>
    <span class="text-base text-amber-600">tired</span>
</div>
```

If no mood data exists:
```html
<p class="text-sm text-zinc-400">No mood data yet. Mention how you're feeling in your entries.</p>
```

### Journal Entries — Main Content

Group entries by week. Determine week boundaries and label them:
- Current week: "This Week"
- Previous week: "Last Week"
- Older weeks: date range (e.g., "Feb 3 - 9")

**Week header:**
```html
<div class="flex items-center gap-3 mt-6 mb-4">
    <h3 class="text-xs font-semibold text-zinc-400 uppercase tracking-wider">This Week</h3>
    <div class="flex-1 h-px bg-zinc-200"></div>
</div>
```

**Each entry card:**
```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5 mb-3">
    <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-3">
            <span class="text-sm font-medium text-zinc-900">Wednesday, Feb 19</span>
            <!-- Mood badge if set -->
            <span class="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">great</span>
        </div>
        <!-- Energy dots if set -->
        <div class="flex items-center gap-1" title="Energy: 4/5">
            <span class="w-2 h-2 rounded-full bg-amber-400"></span>
            <span class="w-2 h-2 rounded-full bg-amber-400"></span>
            <span class="w-2 h-2 rounded-full bg-amber-400"></span>
            <span class="w-2 h-2 rounded-full bg-amber-400"></span>
            <span class="w-2 h-2 rounded-full bg-zinc-200"></span>
        </div>
    </div>
    <!-- Content -->
    <p class="text-zinc-700 leading-relaxed text-sm">The full journal text goes here...</p>
    <!-- Highlights -->
    <div class="flex flex-wrap gap-2 mt-3">
        <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-zinc-50 text-zinc-500 border border-zinc-100">
            <i data-lucide="sparkles" class="w-3 h-3"></i>
            Great call with Sarah
        </span>
    </div>
    <!-- Linked entities -->
    <div class="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-zinc-100">
        <!-- Linked contacts -->
        <a href="contact-sarah-chen.html" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors">
            <i data-lucide="user" class="w-3 h-3"></i>
            Sarah Chen
        </a>
        <!-- Linked projects -->
        <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-zinc-100 text-zinc-600">
            <i data-lucide="folder" class="w-3 h-3"></i>
            Meridian Rebrand
        </span>
    </div>
</div>
```

**Mood badge colors:** Map common moods to the appropriate category:
- Positive ("great", "energized", "happy", "excited", "grateful", "calm", "optimistic"): `bg-emerald-100 text-emerald-700`
- Neutral ("fine", "okay", "steady", "focused"): `bg-zinc-100 text-zinc-600`
- Tough ("rough", "tired", "stressed", "anxious", "frustrated"): `bg-amber-100 text-amber-700`
- Low ("bad", "exhausted", "overwhelmed"): `bg-red-100 text-red-700`

**Energy dots:** Render 5 small circles. Filled (`bg-amber-400`) for each point of energy, empty (`bg-zinc-200`) for the rest. Add `title="Energy: X/5"` to the container.

**Highlights:** Parse the `highlights` JSON array. Render each highlight as a subtle badge with a `sparkles` icon.

**Linked contacts:** For each contact name in `contact_names`, check if that contact has a generated entity page. If yes, render as a linked pill (`<a>` tag). If no, render as a static pill.

**Linked projects:** For each project name in `project_names`, check if that project has a generated entity page. If yes, render as a linked pill. If no, render as a static pill.

**Empty state:**
```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-8 text-center">
    <i data-lucide="book-open" class="w-8 h-8 text-zinc-300 mx-auto mb-3"></i>
    <p class="text-sm text-zinc-500">No journal entries yet.</p>
    <p class="text-xs text-zinc-400 mt-1">Just tell me how your day is going.</p>
</div>
```

### Sidebar — People on Your Mind

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5 mb-4">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="users" class="w-5 h-5 text-zinc-400"></i>
        <h3 class="text-sm font-semibold">People on Your Mind</h3>
    </div>
    <div class="space-y-2.5">
        <div class="flex items-center justify-between">
            <a href="contact-sarah-chen.html" class="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline">Sarah Chen</a>
            <span class="text-xs text-zinc-400">5 mentions</span>
        </div>
        <!-- More contacts... -->
    </div>
</div>
```

If no contact mentions exist:
```html
<p class="text-xs text-zinc-400">No contacts mentioned recently.</p>
```

Contact names should link to entity pages if they exist, otherwise render as plain text.

### Sidebar — Projects in Focus

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="folder-open" class="w-5 h-5 text-zinc-400"></i>
        <h3 class="text-sm font-semibold">Projects in Focus</h3>
    </div>
    <div class="space-y-2.5">
        <div class="flex items-center justify-between">
            <span class="text-sm font-medium">Meridian Rebrand</span>
            <span class="text-xs text-zinc-400">4 mentions</span>
        </div>
        <!-- More projects... -->
    </div>
</div>
```

If no project mentions exist:
```html
<p class="text-xs text-zinc-400">No projects mentioned recently.</p>
```

Project names should link to project pages if they exist in `generated_views`, otherwise render as plain text.

### Footer

```html
<footer class="mt-8 pt-4 border-t border-zinc-100 text-center">
    <p class="text-xs text-zinc-400">Generated by Software of You · DATE at TIME</p>
</footer>
```

## Design Rules (non-negotiable)

- Use the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- Mood badge colors as specified above (emerald for positive, zinc for neutral, amber for tough, red for low)
- Energy dots: `bg-amber-400` for filled, `bg-zinc-200` for empty
- Entry content: `text-zinc-700 leading-relaxed text-sm`
- Week headers: `text-xs font-semibold text-zinc-400 uppercase tracking-wider`
- Responsive: three-column grid uses `grid-cols-1 lg:grid-cols-3`
- All data static in HTML — no JavaScript data fetching
- The only JS: `lucide.createIcons()`
- Lucide icons: `book-open` header/empty, `trending-up` trends, `sparkles` highlights, `user` contacts, `folder` projects, `users` people card, `folder-open` projects card, `layout-dashboard` nav, `activity` energy empty state

### Contact Name Linking

Anywhere a contact name appears (entry cards, sidebar), check if that contact has a generated entity page in the `generated_views` query results. If so, render the name as a clickable link:
```html
<a href="contact-sarah-chen.html" class="font-medium text-blue-600 hover:text-blue-800 hover:underline">Sarah Chen</a>
```
If no page exists, render as plain text.

### Empty States

- No entries at all: Show the empty state card in the main content area. Sidebar cards still show (with their own empty states).
- No mood data: Show message in mood cloud area.
- Not enough energy data (<3 points): Show message instead of SVG chart.
- No contact mentions: Show message in sidebar card.
- No project mentions: Show message in sidebar card.
- Journal module not installed: Do not run this command. Tell the user: "Journal module is not installed. Run `/add-module journal` to enable it."

Never hide a section because it's empty. Show the empty state instead.

## Step 4: Write, Register, Open

Write to `${CLAUDE_PLUGIN_ROOT}/output/journal.html`.

**Register the view:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Journal', 'journal.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Open: `open "${CLAUDE_PLUGIN_ROOT}/output/journal.html"`

Tell user: "Journal view opened. X entries over Y days, Z day streak." Then briefly mention trends if data exists (e.g., "Average energy 3.2, most common mood: focused.").
