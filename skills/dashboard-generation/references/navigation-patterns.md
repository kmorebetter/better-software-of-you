# Navigation Patterns

Every generated page in Software of You includes a **consistent grouped navigation system**: a primary nav bar with dropdown groups, and a breadcrumb showing where you are. This navigation is the SAME on every page — it is not dynamically assembled.

## Navigation Data Queries

Before generating ANY HTML page, run these queries to populate the nav:

```sql
-- Installed modules (determines which nav items and groups to show)
SELECT name FROM modules WHERE enabled = 1;

-- Data counts for nav badges
SELECT 'contacts' as section, COUNT(*) as count FROM contacts WHERE status = 'active'
UNION ALL SELECT 'emails', COUNT(*) FROM emails
UNION ALL SELECT 'calendar', COUNT(*) FROM calendar_events WHERE start_time > datetime('now', '-30 days')
UNION ALL SELECT 'transcripts', COUNT(*) FROM transcripts
UNION ALL SELECT 'decisions', COUNT(*) FROM decisions
UNION ALL SELECT 'journal', COUNT(*) FROM journal_entries
UNION ALL SELECT 'notes', COUNT(*) FROM standalone_notes;

-- Which module views have been generated (for linking)
SELECT entity_name, filename FROM generated_views WHERE view_type = 'module_view';

-- Entity pages (for sub-nav within sections)
SELECT entity_type, entity_id, entity_name, filename FROM generated_views
WHERE view_type = 'entity_page'
ORDER BY updated_at DESC;
```

## After Writing Any HTML Page

**Always register/update the view in the database:**

```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(filename) DO UPDATE SET
  entity_name = excluded.entity_name,
  updated_at = datetime('now');
```

### View Registration Reference

| View Type | view_type | entity_type | filename pattern |
|-----------|-----------|-------------|-----------------|
| Dashboard | `'dashboard'` | `NULL` | `dashboard.html` |
| Contact page | `'entity_page'` | `'contact'` | `contact-{slug}.html` |
| Project page | `'entity_page'` | `'project'` | `project-{slug}.html` |
| Email Hub | `'module_view'` | `'module'` | `email-hub.html` |
| Week View | `'module_view'` | `'module'` | `week-view.html` |
| Conversations | `'module_view'` | `'module'` | `conversations.html` |
| Decision Journal | `'module_view'` | `'module'` | `decision-journal.html` |
| Journal | `'module_view'` | `'module'` | `journal.html` |
| Notes | `'module_view'` | `'module'` | `notes.html` |
| Network Map | `'module_view'` | `'module'` | `network-map.html` |
| Weekly Review | `'module_view'` | `'module'` | `weekly-review.html` |
| Nudges | `'module_view'` | `'module'` | `nudges.html` |
| Timeline | `'module_view'` | `'module'` | `timeline.html` |
| Search Hub | `'module_view'` | `'module'` | `search.html` |

---

## Primary Nav Bar — Grouped Dropdowns

The primary nav uses **grouped dropdown menus** to avoid horizontal overcrowding. Three groups (People, Comms, Intelligence) plus standalone items (SoY logo, Dashboard).

### Group Definitions

| Group | Label | Items | Shows if... |
|-------|-------|-------|-------------|
| — | SoY | Home/logo link | Always |
| — | Dashboard | Dashboard link | Always |
| People | People | Contacts, Network | CRM installed |
| Comms | Comms | Email, Calendar | Gmail or Calendar installed |
| Intelligence | Intelligence | Conversations, Decisions, Journal, Notes | Any of these modules installed |

**A group only renders if at least one module within it is installed.** For example, if only Gmail is installed (not Calendar), the Comms group still shows but only contains Email.

### Structure

```html
<nav class="bg-white border-b border-zinc-200 mb-6">
  <div class="max-w-6xl mx-auto px-4">
    <!-- Primary nav -->
    <div class="flex items-center gap-1 py-3">
      <!-- Logo/home -->
      <a href="dashboard.html" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-semibold text-zinc-900 hover:bg-zinc-50 transition-colors shrink-0">
        <i data-lucide="hexagon" class="w-4 h-4"></i>
        SoY
      </a>

      <span class="w-px h-5 bg-zinc-200 mx-1"></span>

      <!-- Dashboard (standalone, always shown) -->
      <a href="dashboard.html" class="nav-item active">
        <i data-lucide="layout-dashboard" class="w-3.5 h-3.5"></i>
        Dashboard
      </a>

      <!-- People group (if CRM installed) -->
      <div class="nav-group" onclick="this.classList.toggle('open')">
        <div class="nav-group-label">
          <span>People</span>
          <i data-lucide="chevron-down" class="w-3 h-3 nav-chevron"></i>
        </div>
        <div class="nav-dropdown">
          <!-- Always (CRM is always installed if this group shows) -->
          <a href="contacts.html" class="nav-dropdown-item">
            <i data-lucide="users" class="w-3.5 h-3.5"></i>
            Contacts
            <span class="nav-badge">7</span>
          </a>
          <!-- If CRM installed and 2+ contacts -->
          <a href="network-map.html" class="nav-dropdown-item">
            <i data-lucide="share-2" class="w-3.5 h-3.5"></i>
            Network
          </a>
        </div>
      </div>

      <!-- Comms group (if Gmail or Calendar installed) -->
      <div class="nav-group" onclick="this.classList.toggle('open')">
        <div class="nav-group-label">
          <span>Comms</span>
          <i data-lucide="chevron-down" class="w-3 h-3 nav-chevron"></i>
        </div>
        <div class="nav-dropdown">
          <!-- If Gmail installed -->
          <a href="email-hub.html" class="nav-dropdown-item">
            <i data-lucide="mail" class="w-3.5 h-3.5"></i>
            Email
            <span class="nav-badge">50</span>
          </a>
          <!-- If Calendar installed -->
          <a href="week-view.html" class="nav-dropdown-item">
            <i data-lucide="calendar" class="w-3.5 h-3.5"></i>
            Calendar
            <span class="nav-badge">27</span>
          </a>
        </div>
      </div>

      <!-- Intelligence group (if any intelligence module installed) -->
      <div class="nav-group" onclick="this.classList.toggle('open')">
        <div class="nav-group-label">
          <span>Intelligence</span>
          <i data-lucide="chevron-down" class="w-3 h-3 nav-chevron"></i>
        </div>
        <div class="nav-dropdown">
          <!-- If Conversation Intelligence installed -->
          <a href="conversations.html" class="nav-dropdown-item">
            <i data-lucide="message-square" class="w-3.5 h-3.5"></i>
            Conversations
          </a>
          <!-- If Decision Log installed -->
          <a href="decision-journal.html" class="nav-dropdown-item">
            <i data-lucide="git-branch" class="w-3.5 h-3.5"></i>
            Decisions
          </a>
          <!-- If Journal installed -->
          <a href="journal.html" class="nav-dropdown-item">
            <i data-lucide="book-open" class="w-3.5 h-3.5"></i>
            Journal
          </a>
          <!-- If Notes installed -->
          <a href="notes.html" class="nav-dropdown-item">
            <i data-lucide="sticky-note" class="w-3.5 h-3.5"></i>
            Notes
          </a>
        </div>
      </div>
    </div>

    <!-- Breadcrumb + sub-nav (only on non-dashboard pages) -->
    <div class="flex items-center justify-between pb-3 -mt-1">
      <div class="flex items-center gap-1.5 text-sm">
        <a href="dashboard.html" class="text-zinc-400 hover:text-zinc-600">Dashboard</a>
        <span class="text-zinc-300">›</span>
        <a href="contacts.html" class="text-zinc-400 hover:text-zinc-600">Contacts</a>
        <span class="text-zinc-300">›</span>
        <span class="text-zinc-700 font-medium">Daniel Byrne</span>
      </div>

      <!-- Sub-nav: other pages in this section -->
      <div class="flex items-center gap-1.5">
        <a href="contact-sarah-chen.html" class="px-2 py-0.5 rounded text-xs bg-zinc-100 text-zinc-500 hover:bg-zinc-200 hover:text-zinc-700 transition-colors">Sarah Chen</a>
      </div>
    </div>
  </div>
</nav>
```

### CSS Classes (include in every page's `<style>` block)

```css
.nav-item {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.8125rem;
  color: #71717a;
  white-space: nowrap;
  transition: all 0.15s;
  text-decoration: none;
}
.nav-item:hover {
  background: #f4f4f5;
  color: #18181b;
}
.nav-item.active {
  background: #f4f4f5;
  color: #18181b;
  font-weight: 600;
}
.nav-badge {
  font-size: 0.6875rem;
  background: #e4e4e7;
  color: #52525b;
  padding: 0.0625rem 0.375rem;
  border-radius: 9999px;
  font-weight: 500;
}
.nav-item.active .nav-badge,
.nav-dropdown-item.active .nav-badge {
  background: #3b82f6;
  color: white;
}

/* Grouped dropdown nav */
.nav-group {
  position: relative;
}
.nav-group-label {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.375rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.8125rem;
  color: #71717a;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
  user-select: none;
}
.nav-group-label:hover,
.nav-group.active > .nav-group-label {
  background: #f4f4f5;
  color: #18181b;
}
.nav-group.active > .nav-group-label {
  font-weight: 600;
}
.nav-chevron {
  transition: transform 0.15s;
  opacity: 0.5;
}
.nav-group:hover .nav-chevron,
.nav-group.open .nav-chevron {
  opacity: 1;
}
.nav-group.open .nav-chevron {
  transform: rotate(180deg);
}
.nav-dropdown {
  display: none;
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 0.25rem;
  min-width: 10rem;
  background: white;
  border: 1px solid #e4e4e7;
  border-radius: 0.75rem;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1);
  padding: 0.375rem;
  z-index: 50;
}
/* Desktop: show on hover */
.nav-group:hover > .nav-dropdown {
  display: block;
}
/* Mobile: show on tap (toggle .open class) */
.nav-group.open > .nav-dropdown {
  display: block;
}
.nav-dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.625rem;
  border-radius: 0.375rem;
  font-size: 0.8125rem;
  color: #71717a;
  white-space: nowrap;
  transition: all 0.15s;
  text-decoration: none;
}
.nav-dropdown-item:hover {
  background: #f4f4f5;
  color: #18181b;
}
.nav-dropdown-item.active {
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}
```

---

## Nav Bar Variants

### On the Dashboard

- "Dashboard" nav item has the `active` class
- No group has the `active` class
- No breadcrumb row (the breadcrumb div is omitted entirely)
- No sub-nav needed

### On a Module View (e.g., Email Hub)

- The corresponding dropdown item gets `active` (e.g., "Email" dropdown item is active on email-hub.html)
- The parent group label also gets the `active` class on the `.nav-group` (e.g., the Comms group has `active`)
- "Dashboard" nav item does NOT have `active`
- Breadcrumb shows: `Dashboard › Email`
- Sub-nav is empty (no sub-pages for module views)

### On a Contact Entity Page

- "Contacts" dropdown item gets `active`
- The People group gets `active` class on the `.nav-group`
- "Dashboard" nav item does NOT have `active`
- Breadcrumb shows: `Dashboard › Contacts › Daniel Byrne`
- Sub-nav shows other contact entity pages as small pills (excluding the current contact)
- Limit sub-nav to 5 most recently updated contact pages

### On a Project Entity Page

- "Dashboard" nav item gets `active` (projects don't have their own section)
- No group has the `active` class
- Breadcrumb shows: `Dashboard › Projects › Meridian Rebrand`
- Sub-nav shows other project entity pages as pills

### On the Notes View

- "Notes" dropdown item gets `active`
- The Intelligence group gets `active` class on the `.nav-group`
- Breadcrumb shows: `Dashboard › Notes`
- No sub-nav

### On the Network Map

- "Network" dropdown item gets `active`
- The People group gets `active` class on the `.nav-group`
- Breadcrumb shows: `Dashboard › Network`
- No sub-nav

---

## Section-to-View Mapping

When a nav item is clicked, it goes to the module view page. If the view hasn't been generated yet, the link should still point to the correct filename.

| Nav Item | Group | Links to | Generated by |
|----------|-------|----------|-------------|
| Dashboard | — | `dashboard.html` | `/dashboard` |
| Contacts | People | `contacts.html` | `/view contacts` |
| Network | People | `network-map.html` | `/network-map` |
| Email | Comms | `email-hub.html` | `/email-hub` |
| Calendar | Comms | `week-view.html` | `/week-view` |
| Conversations | Intelligence | `conversations.html` | `/conversations-view` |
| Decisions | Intelligence | `decision-journal.html` | `/decision-journal-view` |
| Journal | Intelligence | `journal.html` | `/journal-view` |
| Notes | Intelligence | `notes.html` | `/notes-view` |

### Dashboard Sub-Pages

These cross-cutting views are sub-pages of Dashboard — they do NOT appear in the nav bar or any dropdown. Instead, they are accessed via the Intelligence Tools strip on the dashboard itself.

| Sub-Page | Links to | Generated by |
|----------|----------|-------------|
| Weekly Review | `weekly-review.html` | `/weekly-review` |
| Nudges | `nudges.html` | `/nudges-view` |
| Timeline | `timeline.html` | `/timeline` |
| Search | `search.html` | `/search-hub` |

On these sub-pages:
- "Dashboard" nav item gets `active` class
- No group has the `active` class
- Breadcrumb: `Dashboard > [Page Name]` (e.g., `Dashboard > Nudges`)
- No sub-nav

**Note:** "Contacts" links to `contacts.html`, which is the contact directory view generated by `/view contacts`. This is different from individual contact entity pages (`contact-{slug}.html`).

---

## Rules

1. **The primary nav is identical on every page.** Same groups, same items, same counts. The only things that change are which item has `active` and which group has `active`.
2. **Only show groups that have at least one installed module.** If no Comms modules are installed, the Comms group doesn't appear.
3. **Only show items for installed modules within each group.** If Gmail is installed but Calendar isn't, the Comms group shows only Email.
4. **Data counts are baked in at generation time.** They reflect the state when the page was built.
5. **Breadcrumb depth is max 3 levels.** Dashboard › Section › Page. Never deeper.
6. **Sub-nav only appears on entity pages.** Module views and the dashboard don't have sub-nav.
7. **Sub-nav shows sibling pages.** On a contact entity page, sub-nav shows other contacts.
8. **Limit sub-nav to 5 items.** Most recently updated first.
9. **Links use relative paths.** All pages live in `output/` together.
10. **If a view hasn't been generated, still include the nav item** — just point to the expected filename.
11. **Active state propagates upward.** When a dropdown item is active, its parent `.nav-group` also gets the `active` class.

---

## Contact Name Linking

Throughout ALL views, wherever a contact name appears (activity feeds, follow-ups, project cards, email threads, calendar events, commitment lists), check if an entity page exists:

```sql
SELECT filename FROM generated_views WHERE entity_type = 'contact' AND entity_id = ?;
```

If a page exists:
```html
<a href="contact-daniel-byrne.html" class="font-medium text-blue-600 hover:text-blue-800 hover:underline">Daniel Byrne</a>
```

If no page exists, render as plain text.

---

## Page Footer

Every page includes a footer:

```html
<footer class="mt-8 pt-4 border-t border-zinc-100 text-center">
    <p class="text-xs text-zinc-400">Generated by Software of You · February 20, 2026 at 3:45 PM</p>
</footer>
```
