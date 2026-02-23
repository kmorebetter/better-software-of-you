---
description: Generate an Email Hub page — all your email threads, contacts, and response queue in one view
allowed-tools: ["Bash", "Read", "Write"]
---

# Email Hub

Generate a standalone Email Hub page — the Gmail module's dedicated view. Shows all email threads, top contacts, and a response queue for the last 30 days.

## Step 0: Auto-Sync Gmail

Check if Gmail data is stale:

```sql
SELECT value FROM soy_meta WHERE key = 'gmail_last_synced';
```

If the value is NULL or older than 15 minutes, run the Gmail sync silently before proceeding. Do not mention the sync to the user unless it fails.

## Step 1: Read Design References + Gather Data

Read these design references in parallel:
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/template-base.html` — HTML skeleton
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/navigation-patterns.md` — sidebar patterns

At the same time, gather data from `${CLAUDE_PLUGIN_ROOT}/data/soy.db`:

### All emails (last 30 days)

```sql
SELECT e.id, e.thread_id, e.subject, e.snippet, e.from_name, e.from_address,
  e.to_addresses, e.direction, e.received_at, e.is_read, e.is_starred,
  e.contact_id, c.name as contact_name, c.company as contact_company
FROM emails e
LEFT JOIN contacts c ON e.contact_id = c.id
WHERE e.received_at > datetime('now', '-30 days')
ORDER BY e.received_at DESC;
```

### Stats

```sql
SELECT COUNT(*) as total,
  SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) as unread,
  SUM(CASE WHEN is_starred = 1 THEN 1 ELSE 0 END) as starred,
  COUNT(DISTINCT thread_id) as threads,
  COUNT(DISTINCT contact_id) as contacts_emailed
FROM emails WHERE received_at > datetime('now', '-30 days');
```

### Threads needing response

```sql
SELECT e.thread_id, e.subject, e.from_name, e.received_at, c.name as contact_name, c.id as contact_id
FROM emails e
LEFT JOIN contacts c ON e.contact_id = c.id
WHERE e.direction = 'inbound'
  AND e.thread_id NOT IN (
    SELECT thread_id FROM emails WHERE direction = 'outbound' AND received_at > e.received_at
  )
  AND e.received_at > datetime('now', '-14 days')
GROUP BY e.thread_id
ORDER BY e.received_at DESC;
```

### Top contacts by email volume

```sql
SELECT c.id, c.name, c.company, COUNT(*) as email_count,
  SUM(CASE WHEN e.direction = 'inbound' THEN 1 ELSE 0 END) as inbound,
  SUM(CASE WHEN e.direction = 'outbound' THEN 1 ELSE 0 END) as outbound,
  MAX(e.received_at) as last_email
FROM emails e
JOIN contacts c ON e.contact_id = c.id
WHERE e.received_at > datetime('now', '-30 days')
GROUP BY c.id
ORDER BY email_count DESC
LIMIT 10;
```

### Generated entity pages (for linking contact names)

```sql
SELECT entity_id, filename FROM generated_views WHERE entity_type = 'contact';
```

### Sidebar navigation data

```sql
SELECT view_type, entity_name, filename, updated_at
FROM generated_views
ORDER BY updated_at DESC
LIMIT 10;
```

### Thread grouping

Group raw emails into threads by `thread_id`. For each thread, compute:
- Latest subject
- Message count
- Participants (unique from_name values)
- Latest message time (for sorting)
- Latest snippet (for preview)
- Direction of the latest message (inbound/outbound)
- Whether any message in the thread is unread
- Whether any message in the thread is starred

## Step 2: Generate HTML Page

Generate a self-contained HTML file using the template-base.html skeleton. Follow the layout below exactly.

### Sidebar

Include the sidebar from `navigation-patterns.md` with Email active in the Comms section.

### Header Card

```
Full width card
├── Left side:
│   ├── Lucide `mail` icon + Title: "Email Hub"
│   └── Subtitle: "Last 30 days"
└── Right side: Stat pills
    ├── Total threads (zinc pill)
    ├── Unread count (blue pill, only if > 0)
    ├── Starred count (amber pill, only if > 0)
    └── Contacts emailed (zinc pill)
```

Stat pill styling: `px-3 py-1 rounded-full text-xs font-medium`. Colors: blue for unread (`bg-blue-100 text-blue-700`), amber for starred (`bg-amber-100 text-amber-700`), zinc for neutral (`bg-zinc-100 text-zinc-600`).

### Needs Response Section (full width)

A full-width card with `border-l-4 border-amber-400 bg-amber-50/30` styling.

Header: Lucide `reply` icon + "Needs Response" + count badge.

Show threads where an inbound email has no outbound reply after it (from the needs-response query). Each thread row shows:
- Contact avatar: 32px circle with initials, `bg-blue-100 text-blue-700`
- Contact name (linked to entity page if one exists — use the `generated_views` query results to check), plus company in `text-zinc-400`
- Subject line
- Snippet (truncated to 100 chars, `text-zinc-500`)
- Relative time ("2h ago", "yesterday", "3 days ago")

If no threads need a response, show: "All caught up — no threads waiting for a reply" with a Lucide `check-circle` icon in emerald.

### Main Content Area (responsive two-column on large screens)

```
grid grid-cols-1 lg:grid-cols-3 gap-6
├── Left: Recent Threads (lg:col-span-2)
└── Right: Top Contacts (lg:col-span-1)
```

### Recent Threads Card (left column, `lg:col-span-2`)

Header: Lucide `inbox` icon + "Recent Threads" + total thread count.

Group threads by date:
- **Today** — threads where the latest message is from today
- **Yesterday** — threads where the latest message is from yesterday
- **This Week** — threads from the last 7 days (excluding today/yesterday)
- **Earlier** — everything else

Each date group has a subtle label: `text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2 mt-4`.

Each thread row shows:
- Contact avatar: 32px circle with initials
  - `bg-blue-100 text-blue-700` if the latest message is inbound (from them)
  - `bg-emerald-100 text-emerald-700` if the latest message is outbound (from you)
- Contact name (linked to entity page if exists) + company in `text-zinc-400`
- Subject line — bold if any message in thread is unread, normal weight otherwise
- Star icon (Lucide `star`, filled yellow `text-amber-400`) if any message is starred
- Snippet (truncated to 100 chars, `text-zinc-500 text-sm`)
- Message count badge: `bg-zinc-100 text-zinc-500 rounded-full px-1.5 py-0.5 text-xs` — only show if > 1 message
- Direction arrow: `↙` (inbound, `text-blue-500`) or `↗` (outbound, `text-emerald-500`) for the latest message
- Relative time: `text-xs text-zinc-400`

Unread thread rows get a slightly different background: `bg-blue-50/30`.

### Top Contacts Card (right column, `lg:col-span-1`)

Header: Lucide `users` icon + "Top Contacts".

Show top contacts by email volume (from the top-contacts query). Each contact shows:
- Contact name (linked to entity page if exists), bold
- Company in `text-zinc-400 text-sm`
- Email count with inbound/outbound split shown as a small horizontal bar:
  - Bar container: `h-1.5 bg-zinc-100 rounded-full overflow-hidden flex`
  - Inbound portion: `bg-blue-400`
  - Outbound portion: `bg-emerald-400`
- Small text below bar: `X inbound · Y outbound`
- Last email time: `text-xs text-zinc-400`

### Footer

```html
<footer class="mt-8 pt-4 border-t border-zinc-100 text-center">
    <p class="text-xs text-zinc-400">Generated by Software of You · {date} at {time}</p>
</footer>
```

### Design Rules (non-negotiable)

- Use the template-base.html skeleton (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200 p-6`
- Contact avatars: 32px circles with initials, `bg-blue-100 text-blue-700` for contacts, `bg-emerald-100 text-emerald-700` for you
- Unread thread rows: bold subject, `bg-blue-50/30` background
- Starred: yellow Lucide `star` icon (`text-amber-400`)
- Needs Response card: `border-l-4 border-amber-400 bg-amber-50/30`
- Responsive: main content + sidebar stack on mobile via `grid-cols-1 lg:grid-cols-3`
- All data static in HTML — no JavaScript data fetching
- The only JS: Lucide icon initialization (`lucide.createIcons()`)
- Contact name linking: check `generated_views` results — if an entity page exists for a contact, wrap the name in `<a href="filename" class="font-medium text-blue-600 hover:text-blue-800 hover:underline">`. Otherwise render as plain text.

## Step 3: Write HTML

Write the generated HTML to `${CLAUDE_PLUGIN_ROOT}/output/email-hub.html`.

## Step 4: Register and Open

Register the view in the database:

```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Email Hub', 'email-hub.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Open the file:

```
open "${CLAUDE_PLUGIN_ROOT}/output/email-hub.html"
```

Tell the user: "Email Hub opened. X threads, Y unread, Z need a response."
