# Navigation Patterns

Every generated page in Software of You includes a **consistent two-tier navigation system**: a primary nav bar showing all sections with data counts, and a breadcrumb showing where you are. This navigation is the SAME on every page — it is not dynamically assembled from random pills.

## Navigation Data Queries

Before generating ANY HTML page, run these queries to populate the nav:

```sql
-- Installed modules (determines which nav items to show)
SELECT name FROM modules WHERE enabled = 1;

-- Data counts for nav badges
SELECT 'contacts' as section, COUNT(*) as count FROM contacts WHERE status = 'active'
UNION ALL SELECT 'emails', COUNT(*) FROM emails
UNION ALL SELECT 'calendar', COUNT(*) FROM calendar_events WHERE start_time > datetime('now', '-30 days')
UNION ALL SELECT 'transcripts', COUNT(*) FROM transcripts
UNION ALL SELECT 'decisions', COUNT(*) FROM decisions
UNION ALL SELECT 'journal', COUNT(*) FROM journal_entries;

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
| Network Map | `'module_view'` | `'module'` | `network-map.html` |

---

## Primary Nav Bar

The primary nav is a **horizontal bar at the top of every page**. It shows the major sections of the system, each with a data count badge. Only sections whose modules are installed appear.

### Structure

```html
<nav class="bg-white border-b border-zinc-200 mb-6">
  <div class="max-w-6xl mx-auto px-4">
    <!-- Primary nav -->
    <div class="flex items-center gap-1 py-3 overflow-x-auto">
      <!-- Logo/home -->
      <a href="dashboard.html" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-semibold text-zinc-900 hover:bg-zinc-50 transition-colors shrink-0">
        <i data-lucide="hexagon" class="w-4 h-4"></i>
        SoY
      </a>

      <span class="w-px h-5 bg-zinc-200 mx-1"></span>

      <!-- Section links — only show installed modules -->

      <!-- Always -->
      <a href="dashboard.html" class="nav-item active">
        <i data-lucide="layout-dashboard" class="w-3.5 h-3.5"></i>
        Dashboard
      </a>

      <!-- Always (CRM is always installed) -->
      <a href="contacts.html" class="nav-item">
        <i data-lucide="users" class="w-3.5 h-3.5"></i>
        Contacts
        <span class="nav-badge">2</span>
      </a>

      <!-- If Gmail installed -->
      <a href="email-hub.html" class="nav-item">
        <i data-lucide="mail" class="w-3.5 h-3.5"></i>
        Email
        <span class="nav-badge">50</span>
      </a>

      <!-- If Calendar installed -->
      <a href="week-view.html" class="nav-item">
        <i data-lucide="calendar" class="w-3.5 h-3.5"></i>
        Calendar
        <span class="nav-badge">27</span>
      </a>

      <!-- If Conversation Intelligence installed -->
      <a href="conversations.html" class="nav-item">
        <i data-lucide="message-square" class="w-3.5 h-3.5"></i>
        Conversations
      </a>

      <!-- If Decision Log installed -->
      <a href="decision-journal.html" class="nav-item">
        <i data-lucide="git-branch" class="w-3.5 h-3.5"></i>
        Decisions
      </a>

      <!-- If Journal installed -->
      <a href="journal.html" class="nav-item">
        <i data-lucide="book-open" class="w-3.5 h-3.5"></i>
        Journal
      </a>

      <!-- If CRM installed and 2+ contacts -->
      <a href="network-map.html" class="nav-item">
        <i data-lucide="share-2" class="w-3.5 h-3.5"></i>
        Network
      </a>
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
.nav-item.active .nav-badge {
  background: #3b82f6;
  color: white;
}
```

---

## Nav Bar Variants

### On the Dashboard

- "Dashboard" nav item has the `active` class
- No breadcrumb row (the breadcrumb div is omitted entirely)
- No sub-nav needed

### On a Module View (e.g., Email Hub)

- The corresponding nav item gets `active` (e.g., "Email" is active on email-hub.html)
- Breadcrumb shows: `Dashboard › Email`
- Sub-nav is empty (no sub-pages for module views)

### On a Contact Entity Page

- "Contacts" nav item gets `active`
- Breadcrumb shows: `Dashboard › Contacts › Daniel Byrne`
- Sub-nav shows other contact entity pages as small pills (excluding the current contact)
- Limit sub-nav to 5 most recently updated contact pages

### On a Project Entity Page

- "Dashboard" nav item gets `active` (projects don't have their own section — they're on the dashboard)
- Breadcrumb shows: `Dashboard › Projects › Meridian Rebrand`
- Sub-nav shows other project entity pages as pills

### On the Network Map

- "Network" nav item gets `active`
- Breadcrumb shows: `Dashboard › Network`
- No sub-nav

---

## Section-to-View Mapping

When a nav item is clicked, it goes to the module view page. If the view hasn't been generated yet, the link should still point to the correct filename — when the user clicks it and gets a 404, they'll know to generate it.

| Nav Item | Links to | Generated by |
|----------|----------|-------------|
| Dashboard | `dashboard.html` | `/dashboard` |
| Contacts | `contacts.html` | `/view contacts` |
| Email | `email-hub.html` | `/email-hub` |
| Calendar | `week-view.html` | `/week-view` |
| Conversations | `conversations.html` | `/conversations-view` |
| Decisions | `decision-journal.html` | `/decision-journal-view` |
| Journal | `journal.html` | `/journal-view` |
| Network | `network-map.html` | `/network-map` |

**Note:** "Contacts" links to `contacts.html`, which is the contact directory view generated by `/view contacts`. This is different from individual contact entity pages (`contact-{slug}.html`).

---

## Rules

1. **The primary nav is identical on every page.** Same sections, same counts, same order. The only thing that changes is which item has the `active` class.
2. **Only show sections for installed modules.** If Gmail isn't installed, the "Email" nav item doesn't appear.
3. **Data counts are baked in at generation time.** They reflect the state when the page was built. This is fine — they're indicators, not live counters.
4. **Breadcrumb depth is max 3 levels.** Dashboard › Section › Page. Never deeper.
5. **Sub-nav only appears on entity pages.** Module views and the dashboard don't have sub-nav.
6. **Sub-nav shows sibling pages.** On a contact entity page, sub-nav shows other contacts. On a project page, other projects.
7. **Limit sub-nav to 5 items.** Most recently updated first.
8. **Links use relative paths.** All pages live in `output/` together.
9. **If a view hasn't been generated, still include the nav item** — just point to the expected filename. Users can generate it when they need it.

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
    <p class="text-xs text-zinc-400">Generated by Software of You · February 19, 2026 at 3:45 PM</p>
</footer>
```
