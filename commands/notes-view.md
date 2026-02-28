---
description: Generate a Notes view — your standalone notes with tags, linked entities, and pinned highlights
allowed-tools: ["Bash", "Read", "Write"]
---

# Generate Notes View

Generate a standalone HTML page for the Notes module — showing all notes with tags, cross-references, pinned items, and sidebar stats.

## Step 1: Read the Design System

Read these files first:
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/template-base.html` — HTML skeleton
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/navigation-patterns.md` — sidebar patterns
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/delight-patterns.md` — micro-interactions and delight

## Step 2: Check Module & Gather Data

Query `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`. First verify the notes module is installed:

```sql
SELECT name FROM modules WHERE name = 'notes' AND enabled = 1;
```

If the notes module is not installed, tell the user: "Notes module is not installed. Run `/add-module notes` to enable it." and stop.

### Navigation data

```sql
SELECT view_type, entity_name, filename, updated_at
FROM generated_views
ORDER BY updated_at DESC
LIMIT 10;
```

### Stats

```sql
SELECT
  COUNT(*) as total_notes,
  COUNT(CASE WHEN pinned = 1 THEN 1 END) as pinned_count,
  COUNT(CASE WHEN created_at > datetime('now', '-7 days') THEN 1 END) as this_week
FROM standalone_notes;
```

### Pinned notes

```sql
SELECT sn.*,
  (SELECT json_group_array(c.name) FROM contacts c WHERE sn.linked_contacts LIKE '%' || c.id || '%') as contact_names,
  (SELECT json_group_array(p.name) FROM projects p WHERE sn.linked_projects LIKE '%' || p.id || '%') as project_names
FROM standalone_notes sn
WHERE sn.pinned = 1
ORDER BY sn.updated_at DESC;
```

### All notes (last 90 days)

```sql
SELECT sn.*,
  (SELECT json_group_array(c.name) FROM contacts c WHERE sn.linked_contacts LIKE '%' || c.id || '%') as contact_names,
  (SELECT json_group_array(p.name) FROM projects p WHERE sn.linked_projects LIKE '%' || p.id || '%') as project_names
FROM standalone_notes sn
WHERE sn.created_at > datetime('now', '-90 days')
ORDER BY sn.created_at DESC;
```

### Most referenced contacts (last 30 days)

```sql
SELECT c.id, c.name, COUNT(*) as mention_count
FROM standalone_notes sn
JOIN contacts c ON sn.linked_contacts LIKE '%' || c.id || '%'
WHERE sn.created_at > datetime('now', '-30 days')
GROUP BY c.id
ORDER BY mention_count DESC
LIMIT 5;
```

### Most referenced projects (last 30 days)

```sql
SELECT p.id, p.name, COUNT(*) as mention_count
FROM standalone_notes sn
JOIN projects p ON sn.linked_projects LIKE '%' || p.id || '%'
WHERE sn.created_at > datetime('now', '-30 days')
GROUP BY p.id
ORDER BY mention_count DESC
LIMIT 5;
```

### Most used tags (all time)

```sql
SELECT value as tag, COUNT(*) as count
FROM standalone_notes, json_each(standalone_notes.tags)
WHERE tags IS NOT NULL
GROUP BY value
ORDER BY count DESC
LIMIT 10;
```

### Entity pages for linking

```sql
SELECT entity_id, entity_type, filename FROM generated_views WHERE view_type = 'entity_page';
```

## Step 3: Generate HTML

Generate a self-contained HTML file following the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font).

### Sidebar

Include the sidebar from `navigation-patterns.md` with Notes active in the Intelligence section.

### Layout Structure

```
Sidebar

Header card
+-- Title: "Notes"
+-- Subtitle: "X notes captured"
+-- Stat pills: Total notes, Pinned, This week

Pinned notes section (only if pinned notes exist)
+-- 2-column grid of pinned note cards
+-- Each card: pin icon, title, preview, tags, linked entities, timestamp

All Notes section (reverse-chronological, grouped by week)
+-- Week headers: "This Week", "Last Week", "Feb 3-9"
+-- Each card: title, content preview, tags as colored pills, linked contacts/projects as pills, timestamp

Three-column grid below:
Left (lg:col-span-2): All Notes section
Right (lg:col-span-1): Sidebar

Sidebar:
  Most Referenced card (contacts)
  +-- Name + mention count + link to entity page if exists

  Most Referenced card (projects)
  +-- Name + mention count + link to project page if exists

  Popular Tags card
  +-- Tag pills with counts

Footer
```

### Header Card

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-6 mb-6">
    <div class="flex items-center justify-between">
        <div>
            <div class="flex items-center gap-2">
                <i data-lucide="sticky-note" class="w-5 h-5 text-zinc-700"></i>
                <h1 class="text-2xl font-bold text-zinc-900">Notes</h1>
            </div>
            <p class="text-sm text-zinc-500 mt-1">X notes captured</p>
        </div>
        <div class="flex items-center gap-3">
            <span class="px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700">X total</span>
            <span class="px-3 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700">Y pinned</span>
            <span class="px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700">Z this week</span>
        </div>
    </div>
</div>
```

### Pinned Notes Section

Only render this section if pinned notes exist. Show as a 2-column grid with a subtle amber pin indicator.

```html
<div class="mb-6">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="pin" class="w-4 h-4 text-amber-500"></i>
        <h2 class="text-sm font-semibold text-zinc-700">Pinned</h2>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Pinned note cards -->
        <div class="bg-white rounded-xl shadow-sm border border-amber-200 p-5">
            <div class="flex items-start justify-between mb-2">
                <h3 class="text-sm font-semibold text-zinc-900">Note Title</h3>
                <i data-lucide="pin" class="w-3.5 h-3.5 text-amber-400 shrink-0"></i>
            </div>
            <p class="text-sm text-zinc-600 leading-relaxed mb-3">Content preview...</p>
            <!-- Tags -->
            <div class="flex flex-wrap gap-1.5 mb-3">
                <span class="px-2 py-0.5 rounded-full text-xs bg-violet-50 text-violet-600">#research</span>
            </div>
            <!-- Linked entities -->
            <div class="flex flex-wrap items-center gap-1.5 pt-3 border-t border-zinc-100">
                <a href="contact-sarah-chen.html" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors">
                    <i data-lucide="user" class="w-3 h-3"></i>
                    Sarah Chen
                </a>
            </div>
            <p class="text-xs text-zinc-400 mt-2">2 days ago</p>
        </div>
    </div>
</div>
```

### All Notes — Main Content

Group notes by week. Determine week boundaries and label them:
- Current week: "This Week"
- Previous week: "Last Week"
- Older weeks: date range (e.g., "Feb 3 - 9")

Exclude pinned notes from this section to avoid duplication (they're shown in the Pinned section above).

**Week header:**
```html
<div class="flex items-center gap-3 mt-6 mb-4">
    <h3 class="text-xs font-semibold text-zinc-400 uppercase tracking-wider">This Week</h3>
    <div class="flex-1 h-px bg-zinc-200"></div>
</div>
```

**Each note card:**
```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5 mb-3">
    <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-semibold text-zinc-900">Note Title</h3>
        <span class="text-xs text-zinc-400">Feb 19</span>
    </div>
    <p class="text-zinc-700 leading-relaxed text-sm">Full note content or preview (truncate at ~200 chars for long notes)...</p>
    <!-- Tags -->
    <div class="flex flex-wrap gap-1.5 mt-3">
        <span class="px-2 py-0.5 rounded-full text-xs bg-violet-50 text-violet-600">#research</span>
        <span class="px-2 py-0.5 rounded-full text-xs bg-violet-50 text-violet-600">#ideas</span>
    </div>
    <!-- Linked entities -->
    <div class="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-zinc-100">
        <a href="contact-sarah-chen.html" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors">
            <i data-lucide="user" class="w-3 h-3"></i>
            Sarah Chen
        </a>
        <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-zinc-100 text-zinc-600">
            <i data-lucide="folder" class="w-3 h-3"></i>
            Meridian Rebrand
        </span>
    </div>
</div>
```

**Tag pill colors:** All tags use `bg-violet-50 text-violet-600` for consistency.

**Linked contacts:** Check if an entity page exists for the contact. If yes, render as a linked pill (`<a>` tag). If no, render as a static pill.

**Linked projects:** Check if a project page exists in `generated_views`. If yes, render as a linked pill. If no, render as a static pill.

**Empty state:**
```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-8 text-center">
    <i data-lucide="sticky-note" class="w-8 h-8 text-zinc-300 mx-auto mb-3"></i>
    <p class="text-sm text-zinc-500">No notes yet.</p>
    <p class="text-xs text-zinc-400 mt-1">Capture a thought with /note — it'll auto-link to your contacts and projects.</p>
</div>
```

### Sidebar — Most Referenced Contacts

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5 mb-4">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="users" class="w-5 h-5 text-zinc-400"></i>
        <h3 class="text-sm font-semibold">Most Referenced</h3>
    </div>
    <div class="space-y-2.5">
        <div class="flex items-center justify-between">
            <a href="contact-sarah-chen.html" class="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline">Sarah Chen</a>
            <span class="text-xs text-zinc-400">5 notes</span>
        </div>
    </div>
</div>
```

Contact names should link to entity pages if they exist, otherwise render as plain text.

If no contact references: `<p class="text-xs text-zinc-400">No contacts referenced yet.</p>`

### Sidebar — Most Referenced Projects

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5 mb-4">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="folder-open" class="w-5 h-5 text-zinc-400"></i>
        <h3 class="text-sm font-semibold">Projects Referenced</h3>
    </div>
    <div class="space-y-2.5">
        <div class="flex items-center justify-between">
            <span class="text-sm font-medium">Meridian Rebrand</span>
            <span class="text-xs text-zinc-400">4 notes</span>
        </div>
    </div>
</div>
```

Project names should link to project pages if they exist in `generated_views`, otherwise render as plain text.

If no project references: `<p class="text-xs text-zinc-400">No projects referenced yet.</p>`

### Sidebar — Popular Tags

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="hash" class="w-5 h-5 text-zinc-400"></i>
        <h3 class="text-sm font-semibold">Popular Tags</h3>
    </div>
    <div class="flex flex-wrap gap-2">
        <span class="px-2.5 py-1 rounded-full text-xs bg-violet-50 text-violet-600 font-medium">research <span class="text-violet-400">5</span></span>
        <span class="px-2.5 py-1 rounded-full text-xs bg-violet-50 text-violet-600 font-medium">ideas <span class="text-violet-400">3</span></span>
    </div>
</div>
```

If no tags: `<p class="text-xs text-zinc-400">No tags used yet. Add #hashtags to your notes.</p>`

### Footer

```html
<footer class="mt-8 pt-4 border-t border-zinc-100 text-center">
    <p class="text-xs text-zinc-400">Generated by Software of You · DATE at TIME</p>
</footer>
```

## Design Rules (non-negotiable)

- Use the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- Pinned cards: `border-amber-200` instead of `border-zinc-200`
- Tag pills: `bg-violet-50 text-violet-600` (all tags same color for consistency)
- Contact pills: `bg-blue-50 text-blue-600`
- Project pills: `bg-zinc-100 text-zinc-600`
- Note content: `text-zinc-700 leading-relaxed text-sm`
- Week headers: `text-xs font-semibold text-zinc-400 uppercase tracking-wider`
- Responsive: three-column grid uses `grid-cols-1 lg:grid-cols-3`
- All data static in HTML — no JavaScript data fetching
- The only JS: `lucide.createIcons()`
- Lucide icons: `sticky-note` header/empty, `pin` pinned items, `user` contacts, `folder` projects, `users` sidebar contacts, `folder-open` sidebar projects, `hash` tags card, `layout-dashboard` nav

### Contact Name Linking

Anywhere a contact name appears (note cards, sidebar), check if that contact has a generated entity page in the `generated_views` query results. If so, render as a clickable link. If no page exists, render as plain text.

### Empty States

- No notes at all: Show the empty state card in the main content area. Sidebar cards still show (with their own empty states).
- No pinned notes: Omit the Pinned section entirely.
- No contact references: Show message in sidebar card.
- No project references: Show message in sidebar card.
- No tags: Show message in sidebar card.
- Notes module not installed: Do not run this command. Tell the user: "Notes module is not installed. Run `/add-module notes` to enable it."

Never hide a section because it's empty (except Pinned, which is only shown when pinned notes exist). Show the empty state instead.

## Step 4: Write, Register, Open

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/notes.html`.

**Register the view:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Notes', 'notes.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Open: `open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/notes.html"`

Tell user: "Notes view opened. X notes total, Y pinned." Then briefly mention top tags or most referenced contacts if data exists.
