---
description: Generate the Contacts Index — sortable, filterable, groupable CRM directory with relationship intelligence
allowed-tools: ["Bash", "Read", "Write"]
---

# Contacts Index

Generate a full CRM contacts index page — the primary working list of all contacts with search, filters, sorting, grouping, and relationship intelligence at a glance.

## Step 1 — Run bootstrap

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/bootstrap.sh"
```

## Step 2 — Query all data

Run these queries against `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`:

```sql
-- Nav counts
SELECT 'contacts' as section, COUNT(*) as count FROM contacts WHERE status = 'active'
UNION ALL SELECT 'emails', COUNT(*) FROM emails
UNION ALL SELECT 'calendar', COUNT(*) FROM calendar_events WHERE start_time > datetime('now', '-30 days')
UNION ALL SELECT 'transcripts', COUNT(*) FROM transcripts
UNION ALL SELECT 'decisions', COUNT(*) FROM decisions
UNION ALL SELECT 'journal', COUNT(*) FROM journal_entries
UNION ALL SELECT 'notes', COUNT(*) FROM standalone_notes;

-- Installed modules
SELECT name FROM modules WHERE enabled = 1;

-- All contacts with full intelligence
SELECT
  c.id, c.name, c.email, c.phone, c.company, c.role, c.type, c.status,
  c.notes, c.created_at, c.updated_at,
  -- Tags
  GROUP_CONCAT(DISTINCT t.name) as tags,
  GROUP_CONCAT(DISTINCT t.color) as tag_colors,
  -- Follow-ups
  (SELECT COUNT(*) FROM follow_ups WHERE contact_id = c.id AND status = 'pending') as followup_count,
  (SELECT COUNT(*) FROM follow_ups WHERE contact_id = c.id AND status = 'pending' AND due_date < date('now')) as overdue_followups,
  (SELECT MIN(due_date) FROM follow_ups WHERE contact_id = c.id AND status = 'pending') as next_followup_date,
  -- Last interaction (CRM)
  (SELECT MAX(occurred_at) FROM contact_interactions WHERE contact_id = c.id) as last_interaction,
  (SELECT type FROM contact_interactions WHERE contact_id = c.id ORDER BY occurred_at DESC LIMIT 1) as last_interaction_type,
  -- Interaction count
  (SELECT COUNT(*) FROM contact_interactions WHERE contact_id = c.id) as interaction_count,
  -- Email activity
  (SELECT MAX(received_at) FROM emails WHERE contact_id = c.id) as last_email,
  (SELECT COUNT(*) FROM emails WHERE contact_id = c.id) as email_count,
  -- Projects
  (SELECT COUNT(*) FROM projects WHERE client_id = c.id AND status NOT IN ('completed','cancelled')) as active_projects,
  -- Relationship score (if Conversation Intelligence installed)
  (SELECT relationship_depth FROM relationship_scores WHERE contact_id = c.id ORDER BY score_date DESC LIMIT 1) as rel_depth,
  (SELECT trajectory FROM relationship_scores WHERE contact_id = c.id ORDER BY score_date DESC LIMIT 1) as rel_trajectory,
  -- Entity page exists?
  (SELECT filename FROM generated_views WHERE entity_type = 'contact' AND entity_id = c.id LIMIT 1) as entity_page
FROM contacts c
LEFT JOIN entity_tags et ON et.entity_type = 'contact' AND et.entity_id = c.id
LEFT JOIN tags t ON t.id = et.tag_id
GROUP BY c.id
ORDER BY COALESCE(last_interaction, last_email, c.updated_at) DESC;
```

Also query for header stats:
```sql
-- Stats for header bar
SELECT
  (SELECT COUNT(*) FROM contacts WHERE status = 'active') as total_active,
  (SELECT COUNT(DISTINCT company) FROM contacts WHERE status = 'active' AND company IS NOT NULL AND company != '') as companies,
  (SELECT COUNT(DISTINCT contact_id) FROM follow_ups WHERE status = 'pending') as with_followups,
  (SELECT COUNT(*) FROM contacts WHERE status = 'active'
    AND id NOT IN (
      SELECT DISTINCT contact_id FROM contact_interactions WHERE occurred_at > datetime('now', '-30 days')
      UNION SELECT DISTINCT contact_id FROM emails WHERE received_at > datetime('now', '-30 days')
    )
  ) as going_cold;
```

## Step 3 — Generate HTML

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/contacts.html`.

Include the sidebar from `skills/dashboard-generation/references/navigation-patterns.md` with Contacts active in the People section.

### Design system
- Background: `bg-zinc-50`, cards: `bg-white border border-zinc-200 rounded-xl shadow-sm`
- Font: Inter via Google Fonts
- Icons: Lucide
- Tailwind via CDN

### Page structure

```
[Sidebar (Contacts active in People section)]

[Stats bar]  — 4 stat chips: Active contacts | Companies | With follow-ups | Going cold

[Toolbar]
  [Search input]  [Filter dropdowns: Company | Tag | Status | Relationship]  [Sort dropdown]  [View toggle: ⊞ ☰]

[Group toggle row]  — "Group by: None | Company | Tag | Relationship"

[Content area — table or card grid based on active view]

[Footer]
```

### Stats bar
Four chips in a horizontal strip:
- **N contacts** — total active
- **N companies** — distinct companies
- **N follow-ups pending** — amber if > 0
- **N going cold** — red if > 0 (no interaction in 30+ days)

### Toolbar
All filtering/sorting is **client-side JavaScript** — no page reloads.

Search input: filters by name, company, role simultaneously.

Filter dropdowns (each multi-select or single):
- **Company** — all distinct companies alphabetically
- **Tag** — all tags
- **Status** — Active / Inactive / Archived (default: Active only)
- **Relationship** — Transactional / Professional / Collaborative / Trusted (only if Conversation Intelligence installed)
- **Going cold** — toggle: show only contacts with no interaction in 30+ days

Sort dropdown:
- Last Contact (default)
- Name A→Z
- Company
- Relationship Score
- Most Interactions

View toggle: Table (default) / Cards

### Table view (default)

```html
<table class="w-full text-sm">
  <thead>
    <tr class="border-b border-zinc-100 text-xs text-zinc-400 uppercase tracking-wider">
      <th>Name</th>
      <th>Company</th>
      <th>Role</th>
      <th>Tags</th>
      <th>Last Contact</th>
      <th>Follow-up</th>
      <th>Relationship</th>
      <th></th>  <!-- arrow to entity page -->
    </tr>
  </thead>
  <tbody>
    <!-- one row per contact -->
  </tbody>
</table>
```

**Row design:**
- Name: `font-medium text-zinc-900` — linked to entity page if exists, else plain
- Company: `text-zinc-600`
- Role: `text-zinc-500 text-xs`
- Tags: small colored pill badges (max 3, then "+N more")
- Last Contact: relative time ("3 days ago", "6 weeks ago") color-coded:
  - Green (`text-emerald-600`): < 14 days
  - Amber (`text-amber-600`): 14–30 days
  - Red (`text-red-600`): > 30 days
  - Zinc (`text-zinc-400`): never / no data — show "—"
- Follow-up: if overdue → red badge "Overdue"; if pending → amber badge with date; else "—"
- Relationship: depth label pill if data exists (`text-blue-700 bg-blue-50`), else "—"
- Last column: `→` arrow link to entity page (only if page exists)
- Row hover: `hover:bg-zinc-50 cursor-pointer` — clicking anywhere on row navigates to entity page

### Card grid view

2-column grid (3 on wide screens). Each card:
```
[Avatar initials circle]  [Name — linked]  [Company · Role]
[Tags row]
[Last contact chip]  [Follow-up chip if any]
[Relationship depth pill if any]
```

### Grouping

When a group-by is active, insert a section header before each group:
```html
<div class="flex items-center gap-3 mb-3 mt-6">
  <h3 class="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Verdant Co</h3>
  <div class="flex-1 h-px bg-zinc-200"></div>
  <span class="text-xs text-zinc-400">4 contacts</span>
</div>
```

Groups are collapsible — clicking the header toggles visibility of the group's rows/cards.

### Empty states

When filters produce no results:
```html
<div class="text-center py-16 text-zinc-400">
  <i data-lucide="users" class="w-8 h-8 mx-auto mb-3 opacity-40"></i>
  <p class="text-sm">No contacts match these filters.</p>
  <button onclick="clearFilters()" class="mt-3 text-xs text-blue-600 hover:underline">Clear filters</button>
</div>
```

If "going cold" filter is on and no results: "No contacts going cold — you're on top of your relationships."

### Client-side JS requirements

All data is baked into the HTML as a JSON array in a `<script>` block. The JS handles:
- `filterContacts()` — called on any search/filter/sort change, re-renders the visible list
- `setView(type)` — toggles table/card, persists to `localStorage`
- `setGroupBy(field)` — groups the list and re-renders
- `toggleGroup(id)` — collapses/expands a group
- `toggleSidebar()` — standard sidebar toggle (from nav-patterns reference)
- `clearFilters()` — resets all filters and search

Restore last view preference from `localStorage` on page load.

**Security:** Use `document.createElement` + `textContent` for all dynamic content — never `innerHTML` with user data.

### Data baking pattern

```javascript
const CONTACTS = [
  {
    id: 1,
    name: "Daniel Byrne",
    company: "Main+Main",
    role: "Principal",
    email: "daniel@mainandmain.ca",
    status: "active",
    tags: ["client", "priority"],
    lastContact: "2024-01-15",  // ISO date or null
    lastContactType: "call",
    followupCount: 1,
    overdueFollowups: 0,
    nextFollowupDate: "2024-01-22",
    interactionCount: 7,
    activeProjects: 1,
    relDepth: "collaborative",  // or null
    relTrajectory: "strengthening",  // or null
    entityPage: "contact-daniel-byrne.html"  // or null
  },
  // ...
];
```

## Step 4 — Register and open

```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Contacts', 'contacts.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

```bash
open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/contacts.html"
```

Tell the user: "Your contacts index is ready — N contacts, sortable and filterable. Use the search bar, filter by company or tag, or group by relationship depth."
