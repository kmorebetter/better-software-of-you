# Navigation Patterns

Every generated page in Software of You includes a **persistent left sidebar** that lists all pages — module views and individual entity pages — so every page is one click away. The sidebar is the SAME on every page; only the active state changes.

## Navigation Data Queries

Before generating ANY HTML page, run these queries to populate the sidebar:

```sql
-- Installed modules (determines which sections to show)
SELECT name FROM modules WHERE enabled = 1;

-- Data counts for sidebar badges
SELECT 'contacts' as section, COUNT(*) as count FROM contacts WHERE status = 'active'
UNION ALL SELECT 'emails', COUNT(*) FROM emails
UNION ALL SELECT 'calendar', COUNT(*) FROM calendar_events WHERE start_time > datetime('now', '-30 days')
UNION ALL SELECT 'transcripts', COUNT(*) FROM transcripts
UNION ALL SELECT 'decisions', COUNT(*) FROM decisions
UNION ALL SELECT 'journal', COUNT(*) FROM journal_entries
UNION ALL SELECT 'notes', COUNT(*) FROM standalone_notes;

-- Which module views have been generated (for linking)
SELECT entity_name, filename FROM generated_views WHERE view_type = 'module_view';

-- Contact entity pages for sidebar (alphabetical)
SELECT entity_id, entity_name, filename FROM generated_views
WHERE view_type = 'entity_page' AND entity_type = 'contact'
ORDER BY entity_name ASC;

-- Project entity pages for sidebar (alphabetical)
SELECT entity_id, entity_name, filename FROM generated_views
WHERE view_type = 'entity_page' AND entity_type = 'project'
ORDER BY entity_name ASC;

-- Nudge count for Tools section badge
SELECT
  (SELECT COUNT(*) FROM follow_ups WHERE status = 'pending' AND due_date < date('now'))
  + (SELECT COUNT(*) FROM commitments WHERE status IN ('open','overdue') AND deadline_date < date('now'))
  + (SELECT COUNT(*) FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.status NOT IN ('done') AND t.due_date < date('now'))
  as urgent_count;
```

### Ungenerated Page Fallback

Sidebar items must never link to pages that don't exist yet. Before rendering each item, check whether its target file appears in the `generated_views` results above.

**If the page has been generated** → render as a normal `<a>` tag linking to the file.

**If the page has NOT been generated yet** → render as a `<span>` with a tooltip. Example:

```html
<!-- Generated — normal link -->
<a href="contacts.html" class="sidebar-item">
  <i data-lucide="users" class="w-4 h-4"></i>
  Contacts
  <span class="sidebar-badge">7</span>
</a>

<!-- Not yet generated — greyed out, non-clickable -->
<span class="sidebar-item sidebar-item-disabled" title="Run /contacts to generate this view">
  <i data-lucide="users" class="w-4 h-4"></i>
  Contacts
</span>
```

Apply this same pattern to entity page links in the sidebar.

**Module view filenames to check against `generated_views`:**

| Nav Item | Expected filename |
|----------|------------------|
| Contacts | `contacts.html` |
| Network Map | `network-map.html` |
| Email | `email-hub.html` |
| Calendar | `week-view.html` |
| Conversations | `conversations.html` |
| Decisions | `decision-journal.html` |
| Journal | `journal.html` |
| Notes | `notes.html` |
| Weekly Review | `weekly-review.html` |
| Nudges | `nudges.html` |
| Timeline | `timeline.html` |
| Search | `search.html` |

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
| Contacts Index | `'module_view'` | `'module'` | `contacts.html` |
| Network Map | `'module_view'` | `'module'` | `network-map.html` |
| Weekly Review | `'module_view'` | `'module'` | `weekly-review.html` |
| Nudges | `'module_view'` | `'module'` | `nudges.html` |
| Timeline | `'module_view'` | `'module'` | `timeline.html` |
| Search Hub | `'module_view'` | `'module'` | `search.html` |
| Transcript Page | `'transcript_page'` | `'transcript'` | `transcript-{slug}.html` |

---

## Sidebar Structure

The sidebar is a fixed-position `<aside>` on the left side of the viewport. It contains all navigation organized into collapsible sections, with entity pages listed directly by name.

```
┌─────────────────────┐
│ ⬡ Software of You   │  ← header (links to dashboard)
├─────────────────────┤
│ ▫ Dashboard          │  ← always present
│                      │
│ ▸ People             │  ← collapsible, if CRM installed
│   Contacts (9)       │
│   Network Map        │
│   ─────────          │
│   Daniel Byrne       │  ← entity pages listed directly
│   Sarah Chen         │
│   Marcus Webb        │
│   ...                │
│   Show all (24)      │  ← if >10 contacts
│                      │
│ ▸ Projects           │  ← if Project Tracker installed
│   Meridian Rebrand   │  ← project entity pages
│   AI for Main+Main   │
│                      │
│ ▸ Comms              │  ← if Gmail or Calendar installed
│   Email (12)         │
│   Calendar (5)       │
│                      │
│ ▸ Intelligence       │  ← if any intel module installed
│   Conversations      │
│   Decisions          │
│   Journal            │
│   Notes              │
│                      │
│ ▸ Tools              │  ← always present
│   Weekly Review      │
│   Nudges (3!)        │
│   Timeline           │
│   Search             │
├─────────────────────┤
│ TIP                  │  ← contextual card
│ Use /follow-up to    │
│ set a reminder.      │
└─────────────────────┘
```

### HTML Structure

```html
<!-- Sidebar -->
<aside id="sidebar" class="sidebar">
  <!-- Header -->
  <div class="sidebar-header">
    <a href="dashboard.html" class="sidebar-logo">
      <i data-lucide="hexagon" class="w-4 h-4"></i>
      <span>Software of You</span>
    </a>
  </div>

  <!-- Scrollable nav area -->
  <nav class="sidebar-nav">
    <!-- Dashboard (always present) -->
    <a href="dashboard.html" class="sidebar-item active">
      <i data-lucide="layout-dashboard" class="w-4 h-4"></i>
      Dashboard
    </a>

    <!-- People section (if CRM installed) -->
    <div class="sidebar-section open" id="section-people">
      <button class="sidebar-section-label" onclick="toggleSection('section-people')">
        <span>People</span>
        <i data-lucide="chevron-right" class="w-3.5 h-3.5 sidebar-chevron"></i>
      </button>
      <div class="sidebar-section-content">
        <!-- Module views -->
        <a href="contacts.html" class="sidebar-item">
          <i data-lucide="users" class="w-4 h-4"></i>
          Contacts
          <span class="sidebar-badge">9</span>
        </a>
        <a href="network-map.html" class="sidebar-item">
          <i data-lucide="share-2" class="w-4 h-4"></i>
          Network Map
        </a>
        <!-- Divider before entity pages -->
        <div class="sidebar-divider"></div>
        <!-- Contact entity pages (alphabetical, capped at 10) -->
        <a href="contact-daniel-byrne.html" class="sidebar-entity active">Daniel Byrne</a>
        <a href="contact-sarah-chen.html" class="sidebar-entity">Sarah Chen</a>
        <a href="contact-marcus-webb.html" class="sidebar-entity">Marcus Webb</a>
        <!-- ... more contacts ... -->
        <!-- Show if >10 contact entity pages exist -->
        <button class="sidebar-show-all" onclick="showAllEntities('section-people')">Show all (24)</button>
      </div>
    </div>

    <!-- Projects section (if Project Tracker installed) -->
    <div class="sidebar-section" id="section-projects">
      <button class="sidebar-section-label" onclick="toggleSection('section-projects')">
        <span>Projects</span>
        <i data-lucide="chevron-right" class="w-3.5 h-3.5 sidebar-chevron"></i>
      </button>
      <div class="sidebar-section-content">
        <!-- Project entity pages (alphabetical) -->
        <a href="project-meridian-rebrand.html" class="sidebar-entity">Meridian Rebrand</a>
        <a href="project-ai-for-mainmain.html" class="sidebar-entity">AI for Main+Main</a>
      </div>
    </div>

    <!-- Comms section (if Gmail or Calendar installed) -->
    <div class="sidebar-section" id="section-comms">
      <button class="sidebar-section-label" onclick="toggleSection('section-comms')">
        <span>Comms</span>
        <i data-lucide="chevron-right" class="w-3.5 h-3.5 sidebar-chevron"></i>
      </button>
      <div class="sidebar-section-content">
        <!-- If Gmail installed -->
        <a href="email-hub.html" class="sidebar-item">
          <i data-lucide="mail" class="w-4 h-4"></i>
          Email
          <span class="sidebar-badge">50</span>
        </a>
        <!-- If Calendar installed -->
        <a href="week-view.html" class="sidebar-item">
          <i data-lucide="calendar" class="w-4 h-4"></i>
          Calendar
          <span class="sidebar-badge">27</span>
        </a>
      </div>
    </div>

    <!-- Intelligence section (if any intelligence module installed) -->
    <div class="sidebar-section" id="section-intelligence">
      <button class="sidebar-section-label" onclick="toggleSection('section-intelligence')">
        <span>Intelligence</span>
        <i data-lucide="chevron-right" class="w-3.5 h-3.5 sidebar-chevron"></i>
      </button>
      <div class="sidebar-section-content">
        <!-- If Conversation Intelligence installed -->
        <a href="conversations.html" class="sidebar-item">
          <i data-lucide="message-square" class="w-4 h-4"></i>
          Conversations
        </a>
        <!-- If Decision Log installed -->
        <a href="decision-journal.html" class="sidebar-item">
          <i data-lucide="git-branch" class="w-4 h-4"></i>
          Decisions
        </a>
        <!-- If Journal installed -->
        <a href="journal.html" class="sidebar-item">
          <i data-lucide="book-open" class="w-4 h-4"></i>
          Journal
        </a>
        <!-- If Notes installed -->
        <a href="notes.html" class="sidebar-item">
          <i data-lucide="sticky-note" class="w-4 h-4"></i>
          Notes
        </a>
      </div>
    </div>

    <!-- Tools section (always present) -->
    <div class="sidebar-section" id="section-tools">
      <button class="sidebar-section-label" onclick="toggleSection('section-tools')">
        <span>Tools</span>
        <i data-lucide="chevron-right" class="w-3.5 h-3.5 sidebar-chevron"></i>
      </button>
      <div class="sidebar-section-content">
        <a href="weekly-review.html" class="sidebar-item">
          <i data-lucide="clipboard-list" class="w-4 h-4"></i>
          Weekly Review
        </a>
        <a href="nudges.html" class="sidebar-item">
          <i data-lucide="bell" class="w-4 h-4"></i>
          Nudges
          <span class="sidebar-badge sidebar-badge-alert">3</span>
        </a>
        <a href="timeline.html" class="sidebar-item">
          <i data-lucide="clock" class="w-4 h-4"></i>
          Timeline
        </a>
        <a href="search.html" class="sidebar-item">
          <i data-lucide="search" class="w-4 h-4"></i>
          Search
        </a>
      </div>
    </div>
  </nav>

  <!-- Tip card (bottom zone) -->
  <div class="sidebar-tip-zone">
    <div class="sidebar-tip">
      <p class="sidebar-tip-label">Tip</p>
      <p class="sidebar-tip-text">Use /follow-up to set a reminder for any contact.</p>
    </div>
  </div>
</aside>

<!-- Mobile hamburger toggle -->
<button id="sidebar-toggle" class="sidebar-mobile-toggle" onclick="toggleSidebar()">
  <i data-lucide="menu" class="w-5 h-5"></i>
</button>

<!-- Mobile backdrop -->
<div id="sidebar-backdrop" class="sidebar-backdrop" onclick="toggleSidebar()"></div>

<!-- Main content wrapper -->
<main class="lg:ml-60">
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Page content goes here -->
  </div>
</main>
```

### CSS Classes (include in every page's `<style>` block)

```css
/* ── SIDEBAR ── */
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  width: 15rem; /* 240px */
  background: white;
  border-right: 1px solid #e4e4e7;
  display: flex;
  flex-direction: column;
  z-index: 40;
  transform: translateX(-100%);
  transition: transform 0.2s ease;
}
@media (min-width: 1024px) {
  .sidebar { transform: translateX(0); }
}
.sidebar.open { transform: translateX(0); }

.sidebar-header {
  padding: 1rem 1rem;
  border-bottom: 1px solid #f4f4f5;
  flex-shrink: 0;
}
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #18181b;
  text-decoration: none;
}
.sidebar-logo:hover { color: #3b82f6; }

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 0.5rem;
}

/* Sidebar items (module views + dashboard) */
.sidebar-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.8125rem;
  color: #71717a;
  text-decoration: none;
  transition: all 0.15s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sidebar-item:hover {
  background: #f4f4f5;
  color: #18181b;
}
.sidebar-item.active {
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}
.sidebar-item-disabled {
  opacity: 0.4;
  cursor: default;
  pointer-events: none;
}

/* Sidebar badges */
.sidebar-badge {
  margin-left: auto;
  font-size: 0.6875rem;
  background: #e4e4e7;
  color: #52525b;
  padding: 0.0625rem 0.375rem;
  border-radius: 9999px;
  font-weight: 500;
  flex-shrink: 0;
}
.sidebar-item.active .sidebar-badge {
  background: #3b82f6;
  color: white;
}
.sidebar-badge-alert {
  background: #fecaca;
  color: #dc2626;
}
.sidebar-item.active .sidebar-badge-alert {
  background: #dc2626;
  color: white;
}

/* Sidebar sections (collapsible groups) */
.sidebar-section {
  margin-top: 0.5rem;
}
.sidebar-section-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0.375rem 0.75rem;
  font-size: 0.6875rem;
  font-weight: 600;
  color: #a1a1aa;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  cursor: pointer;
  background: none;
  border: none;
  font-family: inherit;
  transition: color 0.15s;
}
.sidebar-section-label:hover {
  color: #71717a;
}
.sidebar-chevron {
  transition: transform 0.15s;
  flex-shrink: 0;
}
.sidebar-section.open > .sidebar-section-label .sidebar-chevron {
  transform: rotate(90deg);
}
.sidebar-section-content {
  display: none;
  padding-top: 0.125rem;
}
.sidebar-section.open > .sidebar-section-content {
  display: block;
}

/* Entity page links (contacts, projects listed by name) */
.sidebar-entity {
  display: block;
  padding: 0.25rem 0.75rem 0.25rem 1.75rem;
  font-size: 0.8125rem;
  color: #71717a;
  text-decoration: none;
  transition: all 0.15s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sidebar-entity:hover {
  background: #f4f4f5;
  color: #18181b;
  border-radius: 0.375rem;
}
.sidebar-entity.active {
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
  border-radius: 0.375rem;
}
.sidebar-entity-disabled {
  opacity: 0.4;
  cursor: default;
  pointer-events: none;
}

/* Divider between module views and entity pages */
.sidebar-divider {
  height: 1px;
  background: #f4f4f5;
  margin: 0.375rem 0.75rem;
}

/* "Show all" button for overflow entity lists */
.sidebar-show-all {
  display: block;
  width: 100%;
  padding: 0.25rem 0.75rem 0.25rem 1.75rem;
  font-size: 0.75rem;
  color: #3b82f6;
  text-align: left;
  cursor: pointer;
  background: none;
  border: none;
  font-family: inherit;
  transition: color 0.15s;
}
.sidebar-show-all:hover { color: #1d4ed8; }

/* Hidden entity pages (shown when "Show all" is clicked) */
.sidebar-entity-overflow {
  display: none;
}
.sidebar-section.show-all .sidebar-entity-overflow {
  display: block;
}
.sidebar-section.show-all .sidebar-show-all {
  display: none;
}

/* Tip card zone (bottom of sidebar) */
.sidebar-tip-zone {
  padding: 0.75rem;
  border-top: 1px solid #f4f4f5;
  flex-shrink: 0;
}
.sidebar-tip {
  background: #fafafa;
  border-radius: 0.5rem;
  padding: 0.75rem;
}
.sidebar-tip-label {
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #a1a1aa;
  font-weight: 600;
  margin-bottom: 0.25rem;
}
.sidebar-tip-text {
  font-size: 0.75rem;
  color: #71717a;
  line-height: 1.4;
}

/* Mobile toggle button */
.sidebar-mobile-toggle {
  position: fixed;
  top: 1rem;
  left: 1rem;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border: 1px solid #e4e4e7;
  border-radius: 0.5rem;
  padding: 0.5rem;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  cursor: pointer;
  color: #52525b;
}
@media (min-width: 1024px) {
  .sidebar-mobile-toggle { display: none; }
}

/* Mobile backdrop */
.sidebar-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.3);
  z-index: 30;
  display: none;
}
.sidebar-backdrop.visible {
  display: block;
}
@media (min-width: 1024px) {
  .sidebar-backdrop { display: none !important; }
}
```

---

## Sidebar Variants (Active States)

### On the Dashboard

- "Dashboard" sidebar item has the `active` class
- No entity or section item is active
- All sections collapsed by default (except Tools, which auto-expands)

### On a Module View (e.g., Email Hub)

- The corresponding sidebar item gets `active` (e.g., "Email" is active on email-hub.html)
- The parent section auto-expands (e.g., Comms section has `open` class)
- "Dashboard" does NOT have `active`

### On a Contact Entity Page

- The contact's name in the People section gets `active` on the `.sidebar-entity`
- The People section auto-expands
- "Contacts" module view item does NOT get `active` — only the specific entity
- "Dashboard" does NOT have `active`

### On a Project Entity Page

- The project's name in the Projects section gets `active` on the `.sidebar-entity`
- The Projects section auto-expands
- "Dashboard" does NOT have `active`

### On a Tools Sub-Page (Weekly Review, Nudges, Timeline, Search)

- The corresponding item in the Tools section gets `active`
- The Tools section auto-expands
- "Dashboard" does NOT have `active`

### On the Notes View

- "Notes" sidebar item gets `active`
- The Intelligence section auto-expands
- "Dashboard" does NOT have `active`

### On a Transcript Detail Page

- "Conversations" sidebar item in the Intelligence section gets `active`
- The Intelligence section auto-expands
- "Dashboard" does NOT have `active`
- Transcript pages do NOT appear in the sidebar — they are sub-pages accessed via links

### On the Network Map

- "Network Map" sidebar item gets `active`
- The People section auto-expands
- "Dashboard" does NOT have `active`

---

## Section-to-View Mapping

| Nav Item | Section | Links to | Generated by |
|----------|---------|----------|-------------|
| Dashboard | — | `dashboard.html` | `/dashboard` |
| Contacts | People | `contacts.html` | `/contacts` |
| Network Map | People | `network-map.html` | `/network-map` |
| Email | Comms | `email-hub.html` | `/email-hub` |
| Calendar | Comms | `week-view.html` | `/week-view` |
| Conversations | Intelligence | `conversations.html` | `/conversations-view` |
| Decisions | Intelligence | `decision-journal.html` | `/decision-journal-view` |
| Journal | Intelligence | `journal.html` | `/journal-view` |
| Notes | Intelligence | `notes.html` | `/notes-view` |
| Weekly Review | Tools | `weekly-review.html` | `/weekly-review` |
| Nudges | Tools | `nudges.html` | `/nudges-view` |
| Timeline | Tools | `timeline.html` | `/timeline` |
| Search | Tools | `search.html` | `/search-hub` |

**Note:** "Contacts" links to `contacts.html`, which is the contact directory view generated by `/contacts`. This is different from individual contact entity pages (`contact-{slug}.html`).

**Note:** Transcript detail pages (`transcript-{slug}.html`) do **not** appear in the sidebar. They are sub-pages accessed via "View full analysis" links from entity pages and the Conversations view. On transcript pages, "Conversations" in the Intelligence section is the active sidebar item.

---

## Entity Page Listing Rules

Contact and project entity pages are listed directly in the sidebar by name, making every person and project one click away.

1. **Contacts appear in the People section**, below the module views (Contacts, Network Map), separated by a `.sidebar-divider`.
2. **Projects appear in the Projects section**, listed directly. A project index view does not exist yet. Projects section lists entity pages only.
3. **Alphabetical order** by entity name.
4. **Cap at 10 visible** by default. If more than 10 exist, the first 10 render normally and the rest get `class="sidebar-entity sidebar-entity-overflow"`. A "Show all (N)" button appears at the bottom.
5. **Ungenerated entity pages** render as `<span class="sidebar-entity sidebar-entity-disabled">` — same greyed-out pattern as module views.

---

## Rules

1. **The sidebar is identical on every page.** Same sections, same items, same counts. The only things that change are which item has `active` and which section has `open`.
2. **Only show sections that have at least one installed module** (except Dashboard and Tools, which always show).
3. **Only show items for installed modules within each section.** If Gmail is installed but Calendar isn't, the Comms section shows only Email.
4. **Data counts are baked in at generation time.** They reflect the state when the page was built.
5. **Links use relative paths.** All pages live in `output/` together.
6. **If a view hasn't been generated, render the sidebar item as a greyed-out `<span>` (non-clickable) instead of an `<a>` tag.** Check the `generated_views` query results. Never link to a file that hasn't been generated.
7. **Active state determines which section is auto-expanded.** The section containing the active page gets the `open` class on load. Other sections are collapsed.
8. **Entity pages capped at 10 visible.** Overflow uses "Show all" expander.
9. **Sections use `<button>` not `<div>` for labels.** Ensures keyboard accessibility.
10. **Each section needs a unique `id`** (`section-people`, `section-projects`, `section-comms`, `section-intelligence`, `section-tools`) for the JS functions.
11. **No breadcrumbs.** The sidebar provides full hierarchy at all times.
12. **No sub-nav pills.** Entity pages are listed directly in the sidebar.

---

## Required JavaScript (include in every page's `<script>` block)

Every generated page **must** include this sidebar JS. It handles section toggle, mobile sidebar, and "show all" entity expansion.

```javascript
// ── SIDEBAR SECTION TOGGLE ──
function toggleSection(id) {
  var section = document.getElementById(id);
  if (section) section.classList.toggle('open');
}

// ── SHOW ALL ENTITIES ──
function showAllEntities(sectionId) {
  var section = document.getElementById(sectionId);
  if (section) section.classList.add('show-all');
}

// ── MOBILE SIDEBAR TOGGLE ──
function toggleSidebar() {
  var sidebar = document.getElementById('sidebar');
  var backdrop = document.getElementById('sidebar-backdrop');
  var isOpen = sidebar.classList.contains('open');
  if (isOpen) {
    sidebar.classList.remove('open');
    backdrop.classList.remove('visible');
  } else {
    sidebar.classList.add('open');
    backdrop.classList.add('visible');
  }
}

// Close sidebar on Escape key (mobile)
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    var sidebar = document.getElementById('sidebar');
    var backdrop = document.getElementById('sidebar-backdrop');
    if (sidebar) sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('visible');
  }
});
```

---

## Tip Card Content

The tip card at the bottom of the sidebar shows contextual hints. Rotate through these based on the current page:

| Current Page | Tip Text |
|-------------|----------|
| Dashboard | "Use /contact to add someone new." |
| Contact Entity | "Use /follow-up to set a reminder for this person." |
| Project Entity | "Use /project status to get a quick update." |
| Email Hub | "Use /email to compose a message." |
| Calendar | "Use /calendar to create an event." |
| Conversations | "Use /import-call to analyze a transcript." |
| Transcript Detail | "Use /import-call to analyze another transcript." |
| Decisions | "Use /decision to log a new decision." |
| Journal | "Use /journal to write today's entry." |
| Notes | "Use /note to capture a thought." |
| Default | "Use /help-soy to see all available commands." |

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

## Page Layout Wrapper

Every page uses this layout structure (sidebar + main content):

```html
<body class="bg-zinc-50 text-zinc-900 font-sans antialiased">
  <!-- Sidebar (from above) -->
  <!-- Mobile toggle + backdrop (from above) -->

  <main class="lg:ml-60">
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Page content here -->
    </div>

    <footer class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 mt-8 pb-8">
      <div class="pt-4 border-t border-zinc-100 text-center">
        <p class="text-xs text-zinc-400">Generated by Software of You · February 23, 2026 at 3:45 PM</p>
      </div>
    </footer>
  </main>

  <script>
    // Sidebar JS (from above)
    lucide.createIcons();
  </script>
</body>
```

**Key dimensions:**
- Sidebar: `w-60` (240px), fixed left
- Content: `lg:ml-60` pushes content right on desktop, full width on mobile
- Content max-width: `max-w-5xl` (1024px) centered in remaining space
- At 1280px viewport: 240px sidebar + 1040px content area → `max-w-5xl` fits comfortably

---

## Pre-Computed Sidebar Data (Build Context)

During `/build-all`, sidebar queries run **once** in Step 2 and the results are reused for every page generated in that build. This avoids re-querying the same modules, contacts, projects, badges, and nudge counts for each of the 20+ pages.

**How it works:**
- Step 2 of `/build-all` runs all sidebar queries (modules, contacts, projects, generated_views, badge counts, nudge count) in a single batch
- Results are held in context as "build context"
- When generating each page, the sidebar HTML is constructed from this pre-computed data rather than re-querying
- The sidebar structure, CSS, JS, and active-state logic are unchanged — only the data source is optimized

**When standalone commands run** (e.g., `/entity-page Daniel` outside of `/build-all`), sidebar queries still run fresh per the "Navigation Data Queries" section above. The pre-computation is purely a `/build-all` optimization.

**No changes to sidebar HTML structure.** The sidebar output is identical whether data comes from fresh queries or pre-computed build context.

---

## Page Footer

Every page includes a footer inside the `<main>` wrapper:

```html
<footer class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 mt-8 pb-8">
    <div class="pt-4 border-t border-zinc-100 text-center">
        <p class="text-xs text-zinc-400">Generated by Software of You · February 23, 2026 at 3:45 PM</p>
    </div>
</footer>
```
