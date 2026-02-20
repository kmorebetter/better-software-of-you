---
description: Generate the Search Hub — find anything across all modules with live client-side filtering
allowed-tools: ["Bash", "Read", "Write"]
---

# Generate Search Hub

Generate a search page that lets you find anything across all modules. This page embeds searchable data as a JSON blob and uses lightweight vanilla JavaScript for live filtering. This is a pragmatic exception to the "zero JS" pattern — search fundamentally requires interactivity.

## Step 0: Auto-Sync External Data

Before building, ensure data is fresh. Follow the auto-sync procedure in CLAUDE.md — check `gmail_last_synced` and `calendar_last_synced` in `soy_meta`, and sync if stale (>15 min) or never synced. Do this silently.

## Step 1: Read the Design System

Read these files first:
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/template-base.html` — HTML skeleton
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/navigation-patterns.md` — nav bar patterns

## Step 2: Check Modules & Gather Data

Query `${CLAUDE_PLUGIN_ROOT}/data/soy.db`. Run all queries in a single `sqlite3` heredoc call for efficiency.

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

### Searchable Data Queries

Gather all searchable entities. Each type has specific fields to include.

**Contacts** (always — all active):
```sql
SELECT c.id, c.name, c.company, c.role, c.email, c.phone, c.status,
  gv.filename as link
FROM contacts c
LEFT JOIN generated_views gv ON gv.entity_type = 'contact' AND gv.entity_id = c.id
WHERE c.status = 'active'
ORDER BY c.name;
```

**Emails** (if Gmail installed — last 200):
```sql
SELECT e.id, e.subject, e.from_name, e.from_address, e.snippet, e.direction,
  e.received_at as date, e.is_read
FROM emails e
ORDER BY e.received_at DESC
LIMIT 200;
```

**Projects** (if Project Tracker installed — all):
```sql
SELECT p.id, p.name, p.status, p.priority, p.description,
  c.name as client_name,
  gv.filename as link
FROM projects p
LEFT JOIN contacts c ON p.client_id = c.id
LEFT JOIN generated_views gv ON gv.entity_type = 'project' AND gv.entity_id = p.id
ORDER BY p.name;
```

**Decisions** (if Decision Log installed — all):
```sql
SELECT d.id, d.title, d.context, d.status, d.decided_at as date
FROM decisions d
ORDER BY d.decided_at DESC;
```

**Journal entries** (if Journal installed — last 90 days):
```sql
SELECT je.id, je.entry_date as date, je.mood, je.content
FROM journal_entries je
WHERE je.entry_date > date('now', '-90 days')
ORDER BY je.entry_date DESC;
```

**Commitments** (if Conversation Intelligence installed — open ones):
```sql
SELECT com.id, com.description, com.deadline_date as date, com.status,
  CASE WHEN com.is_user_commitment = 1 THEN 'You' ELSE c.name END as owner_name
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
WHERE com.status IN ('open', 'overdue')
ORDER BY com.deadline_date ASC;
```

**Transcripts** (if Conversation Intelligence installed — all):
```sql
SELECT t.id, t.title, t.occurred_at as date, t.duration_minutes,
  GROUP_CONCAT(DISTINCT c.name) as participants
FROM transcripts t
LEFT JOIN transcript_participants tp ON tp.transcript_id = t.id
LEFT JOIN contacts c ON c.id = tp.contact_id AND tp.is_user = 0
GROUP BY t.id
ORDER BY t.occurred_at DESC;
```

## Step 3: Build the JSON Data Blob

Convert query results into a JavaScript object. Truncate long text fields to keep the page size reasonable:
- `snippet`: max 120 characters
- `content` (journal): max 100 characters
- `context` (decisions): max 100 characters
- `description` (commitments): max 120 characters

Structure:

```javascript
const SOY_DATA = {
  contacts: [
    { id: 1, type: "contact", name: "Sarah Chen", company: "Acme Corp", role: "VP Engineering", email: "sarah@acme.com", phone: "555-1234", status: "active", link: "contact-sarah-chen.html" },
    ...
  ],
  emails: [
    { id: 1, type: "email", subject: "RE: Project proposal", from: "Daniel Byrne", snippet: "Looking forward to...", date: "2026-02-18", direction: "inbound", link: null },
    ...
  ],
  projects: [
    { id: 1, type: "project", name: "Meridian Rebrand", status: "active", client: "Sarah Chen", link: "project-meridian-rebrand.html" },
    ...
  ],
  decisions: [
    { id: 1, type: "decision", title: "Choose React over Vue", context: "Need a frontend framework for...", status: "decided", date: "2026-02-15", link: null },
    ...
  ],
  journal: [
    { id: 1, type: "journal", date: "2026-02-19", mood: "great", content: "Productive day, wrapped up...", link: null },
    ...
  ],
  commitments: [
    { id: 1, type: "commitment", description: "Send updated proposal", owner: "You", deadline: "2026-02-20", status: "open", link: null },
    ...
  ],
  transcripts: [
    { id: 1, type: "transcript", title: "Discovery Call", participants: "Sarah Chen, Mike Torres", date: "2026-02-17", duration: 45, link: null },
    ...
  ]
};
```

Only include categories for installed modules.

## Step 4: Generate HTML

Generate a self-contained HTML file. Follow the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font).

### Nav Bar

Use navigation-patterns.md. For this page:
- "Dashboard" nav item gets `active` class (this is a Dashboard sub-page)
- Breadcrumb: `Dashboard > Search`
- No sub-nav

### Page Structure

```
Nav bar (Dashboard active, breadcrumb: Dashboard > Search)

Search card (full width, prominent)
+-- Search input (large, with icon)
+-- Category filter tabs below input
    [All] [Contacts] [Email] [Projects] [Decisions] [Journal] [Commitments] [Calls]

Results area (full width)
+-- Results grouped by type, live-filtered
+-- Each group has a header with type icon and match count
+-- Results within each group are individual cards

Empty state (no query): Browse prompt
Empty state (no results): "No matches found"

Footer
```

### Search Input

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-6 mb-6">
  <div class="relative">
    <i data-lucide="search" class="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400 pointer-events-none"></i>
    <input type="text" id="search-input" placeholder="Search across everything..."
      class="w-full pl-12 pr-4 py-3 rounded-xl border border-zinc-200 bg-zinc-50 text-zinc-900 text-base
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent focus:bg-white
        transition-all placeholder:text-zinc-400" autocomplete="off" autofocus>
  </div>
  <div class="flex items-center gap-1 mt-3 flex-wrap" id="category-filters">
    <button class="search-filter active" data-category="all">All</button>
    <!-- Only show tabs for installed modules -->
    <button class="search-filter" data-category="contacts">Contacts</button>
    <button class="search-filter" data-category="emails">Email</button>
    <button class="search-filter" data-category="projects">Projects</button>
    <button class="search-filter" data-category="decisions">Decisions</button>
    <button class="search-filter" data-category="journal">Journal</button>
    <button class="search-filter" data-category="commitments">Commitments</button>
    <button class="search-filter" data-category="transcripts">Calls</button>
  </div>
</div>
```

### Search Filter CSS

```css
.search-filter {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  color: #71717a;
  background: transparent;
  border: 1px solid #e4e4e7;
  cursor: pointer;
  transition: all 0.15s;
}
.search-filter:hover {
  background: #f4f4f5;
  color: #18181b;
}
.search-filter.active {
  background: #18181b;
  color: white;
  border-color: #18181b;
}
```

### Result Card Templates by Type

**Contact result:**
```html
<div class="result-card bg-white rounded-lg border border-zinc-200 p-4 mb-2 hover:border-blue-200 hover:shadow-sm transition-all">
  <div class="flex items-start gap-3">
    <div class="w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-sm font-semibold shrink-0">SC</div>
    <div class="flex-1 min-w-0">
      <a href="contact-sarah-chen.html" class="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline">Sarah Chen</a>
      <p class="text-xs text-zinc-500">VP Engineering · Acme Corp</p>
      <p class="text-xs text-zinc-400 mt-1">sarah@acme.com</p>
    </div>
  </div>
</div>
```

**Email result:**
```html
<div class="result-card bg-white rounded-lg border border-zinc-200 p-4 mb-2">
  <div class="flex items-start gap-3">
    <div class="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center shrink-0">
      <i data-lucide="mail" class="w-4 h-4 text-indigo-500"></i>
    </div>
    <div class="flex-1 min-w-0">
      <p class="text-sm font-medium text-zinc-900 truncate">RE: Project proposal</p>
      <p class="text-xs text-zinc-500">From Daniel Byrne · Feb 18</p>
      <p class="text-xs text-zinc-400 mt-1 line-clamp-1">Looking forward to reviewing the updated...</p>
    </div>
  </div>
</div>
```

**Project result:**
```html
<div class="result-card bg-white rounded-lg border border-zinc-200 p-4 mb-2 hover:border-purple-200 hover:shadow-sm transition-all">
  <div class="flex items-start gap-3">
    <div class="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center shrink-0">
      <i data-lucide="folder" class="w-4 h-4 text-purple-500"></i>
    </div>
    <div class="flex-1 min-w-0">
      <a href="project-meridian.html" class="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline">Meridian Rebrand</a>
      <p class="text-xs text-zinc-500">Active · Client: Sarah Chen</p>
    </div>
  </div>
</div>
```

Use similar patterns for decisions (amber), journal (rose), commitments (teal), and transcripts (cyan).

### Result Group Headers

```html
<div class="result-group mb-4" data-group="contacts">
  <div class="flex items-center gap-2 mb-2">
    <i data-lucide="users" class="w-4 h-4 text-blue-500"></i>
    <h3 class="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Contacts</h3>
    <span class="text-xs text-zinc-400 result-count">(3 matches)</span>
  </div>
  <!-- result cards -->
</div>
```

### Icons by Category

| Category | Icon | Color |
|----------|------|-------|
| Contacts | `users` | blue-500 |
| Email | `mail` | indigo-500 |
| Projects | `folder` | purple-500 |
| Decisions | `git-branch` | amber-500 |
| Journal | `book-open` | rose-500 |
| Commitments | `target` | teal-500 |
| Calls/Transcripts | `message-square` | cyan-500 |

### JavaScript — Safe DOM Creation (~80 lines)

**Important:** Use DOM creation methods (`document.createElement`, `textContent`) instead of string concatenation with innerHTML. All text content from SOY_DATA must be set via `textContent` to prevent any XSS risk, even though the data originates from the local database.

```html
<script>
document.addEventListener('DOMContentLoaded', function() {
  lucide.createIcons();

  const input = document.getElementById('search-input');
  const resultsContainer = document.getElementById('results');
  const filterBtns = document.querySelectorAll('.search-filter');
  let activeCategory = 'all';
  let debounceTimer;

  const CONFIG = {
    contacts:    { icon: 'users',          color: 'blue',   label: 'Contacts' },
    emails:      { icon: 'mail',           color: 'indigo', label: 'Email' },
    projects:    { icon: 'folder',         color: 'purple', label: 'Projects' },
    decisions:   { icon: 'git-branch',     color: 'amber',  label: 'Decisions' },
    journal:     { icon: 'book-open',      color: 'rose',   label: 'Journal' },
    commitments: { icon: 'target',         color: 'teal',   label: 'Commitments' },
    transcripts: { icon: 'message-square', color: 'cyan',   label: 'Calls' }
  };

  filterBtns.forEach(btn => {
    btn.addEventListener('click', function() {
      filterBtns.forEach(b => b.classList.remove('active'));
      this.classList.add('active');
      activeCategory = this.dataset.category;
      doSearch(input.value);
    });
  });

  input.addEventListener('input', function() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => doSearch(this.value), 150);
  });

  function doSearch(query) {
    query = query.toLowerCase().trim();
    // Clear previous results
    while (resultsContainer.firstChild) resultsContainer.removeChild(resultsContainer.firstChild);

    if (!query) {
      showEmptyState('Type to search across all your data', 'Search contacts, emails, projects, decisions, journal entries, and more');
      return;
    }

    let totalMatches = 0;
    Object.keys(SOY_DATA).forEach(cat => {
      if (activeCategory !== 'all' && activeCategory !== cat) return;
      const matches = SOY_DATA[cat].filter(item =>
        Object.values(item).some(val => val && typeof val === 'string' && val.toLowerCase().includes(query))
      );
      if (matches.length > 0) {
        totalMatches += matches.length;
        resultsContainer.appendChild(buildGroup(cat, matches));
      }
    });

    if (totalMatches === 0) {
      showEmptyState('No matches found', 'Try a different search term or category');
    }
    lucide.createIcons();
  }

  function showEmptyState(title, subtitle) {
    const div = document.createElement('div');
    div.className = 'text-center py-12';
    const p1 = document.createElement('p');
    p1.className = 'text-sm text-zinc-500';
    p1.textContent = title;
    div.appendChild(p1);
    if (subtitle) {
      const p2 = document.createElement('p');
      p2.className = 'text-xs text-zinc-400 mt-1';
      p2.textContent = subtitle;
      div.appendChild(p2);
    }
    resultsContainer.appendChild(div);
  }

  function buildGroup(category, items) {
    const c = CONFIG[category];
    const group = document.createElement('div');
    group.className = 'result-group mb-6';

    // Header
    const header = document.createElement('div');
    header.className = 'flex items-center gap-2 mb-3';
    const icon = document.createElement('i');
    icon.setAttribute('data-lucide', c.icon);
    icon.className = 'w-4 h-4 text-' + c.color + '-500';
    header.appendChild(icon);
    const label = document.createElement('h3');
    label.className = 'text-xs font-semibold text-zinc-500 uppercase tracking-wider';
    label.textContent = c.label;
    header.appendChild(label);
    const count = document.createElement('span');
    count.className = 'text-xs text-zinc-400';
    count.textContent = '(' + items.length + (items.length === 1 ? ' match' : ' matches') + ')';
    header.appendChild(count);
    group.appendChild(header);

    items.forEach(item => group.appendChild(buildCard(category, item)));
    return group;
  }

  function buildCard(category, item) {
    const card = document.createElement('div');
    card.className = 'bg-white rounded-lg border border-zinc-200 p-3 mb-1.5 hover:shadow-sm transition-all';
    const row = document.createElement('div');
    row.className = 'flex items-start gap-3';

    // Icon/avatar
    const iconWrap = document.createElement('div');
    if (category === 'contacts') {
      iconWrap.className = 'w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-xs font-semibold shrink-0';
      iconWrap.textContent = item.name ? item.name.split(' ').map(n => n[0]).join('').substring(0, 2) : '?';
    } else {
      const c = CONFIG[category];
      iconWrap.className = 'w-7 h-7 rounded-lg bg-' + c.color + '-50 flex items-center justify-center shrink-0';
      const i = document.createElement('i');
      i.setAttribute('data-lucide', c.icon);
      i.className = 'w-3.5 h-3.5 text-' + c.color + '-500';
      iconWrap.appendChild(i);
    }
    row.appendChild(iconWrap);

    // Content
    const content = document.createElement('div');
    content.className = 'flex-1 min-w-0';

    const title = document.createElement(item.link ? 'a' : 'span');
    title.className = item.link ? 'text-sm font-medium text-blue-600 hover:text-blue-800' : 'text-sm font-medium text-zinc-900';
    if (item.link) title.href = item.link;

    switch(category) {
      case 'contacts':
        title.textContent = item.name || '';
        content.appendChild(title);
        addSubline(content, [item.role, item.company].filter(Boolean).join(' \u00b7 '));
        if (item.email) addSubline(content, item.email, 'mt-0.5');
        break;
      case 'emails':
        title.textContent = item.subject || '(no subject)';
        title.className = 'text-sm font-medium text-zinc-900 truncate block';
        content.appendChild(title);
        addSubline(content, (item.direction === 'inbound' ? 'From' : 'To') + ' ' + (item.from || '') + ' \u00b7 ' + (item.date || ''));
        if (item.snippet) addSubline(content, item.snippet, 'mt-0.5 truncate');
        break;
      case 'projects':
        title.textContent = item.name || '';
        content.appendChild(title);
        addSubline(content, item.status + (item.client ? ' \u00b7 ' + item.client : ''));
        break;
      case 'decisions':
        title.textContent = item.title || '';
        title.className = 'text-sm font-medium text-zinc-900';
        content.appendChild(title);
        addSubline(content, (item.status || '') + ' \u00b7 ' + (item.date || ''));
        if (item.context) addSubline(content, item.context, 'mt-0.5 truncate');
        break;
      case 'journal':
        title.textContent = (item.date || '') + (item.mood ? ' \u00b7 ' + item.mood : '');
        title.className = 'text-sm font-medium text-zinc-900';
        content.appendChild(title);
        if (item.content) addSubline(content, item.content, 'mt-0.5 truncate');
        break;
      case 'commitments':
        title.textContent = item.description || '';
        title.className = 'text-sm font-medium text-zinc-900 truncate block';
        content.appendChild(title);
        addSubline(content, (item.owner || '') + (item.deadline ? ' \u00b7 Due ' + item.deadline : ''));
        break;
      case 'transcripts':
        title.textContent = item.title || '';
        title.className = 'text-sm font-medium text-zinc-900';
        content.appendChild(title);
        addSubline(content, (item.date || '') + (item.duration ? ' \u00b7 ' + item.duration + ' min' : ''));
        if (item.participants) addSubline(content, item.participants);
        break;
    }

    row.appendChild(content);
    card.appendChild(row);
    return card;
  }

  function addSubline(parent, text, extraClass) {
    if (!text) return;
    const p = document.createElement('p');
    p.className = 'text-xs text-zinc-500' + (extraClass ? ' ' + extraClass : '');
    p.textContent = text;
    parent.appendChild(p);
  }

  doSearch('');
});
</script>
```

### Default State (No Query)

When the page loads with no search query, the `doSearch('')` call shows a browse prompt via the `showEmptyState` function.

## Design Rules (non-negotiable)

- Use the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- Search input: large (py-3), with search icon, autofocus, zinc-50 background
- Result cards: compact (p-3), minimal spacing (mb-1.5)
- Contact initials avatars: `w-8 h-8 rounded-full bg-blue-100 text-blue-700`
- Result groups are hidden when they have no matches
- Module-aware: only show filter tabs and include data for installed modules
- The embedded JSON data is generated at build time — the JS only filters and renders
- **Security:** All text from SOY_DATA is rendered via `textContent`, never innerHTML. DOM elements are created programmatically using `document.createElement`.

### Data Size Limits

Keep the page size manageable by limiting data:
- Contacts: all active (typically <100)
- Emails: last 200
- Projects: all (typically <20)
- Decisions: all (typically <50)
- Journal: last 90 days
- Commitments: open ones only
- Transcripts: all (typically <50)

## Step 5: Write, Register, and Open

Write to `${CLAUDE_PLUGIN_ROOT}/output/search.html`

**Register the view:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Search', 'search.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Open with: `open "${CLAUDE_PLUGIN_ROOT}/output/search.html"`

Tell the user: "Search hub opened. Indexed X contacts, Y emails, Z projects across all modules."
