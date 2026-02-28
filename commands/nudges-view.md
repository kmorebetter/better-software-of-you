---
description: Generate the Nudges view — your attention radar showing overdue, upcoming, and awareness items with urgency tiers
allowed-tools: ["Bash", "Read", "Write"]
---

# Generate Nudges View

Generate the "Attention Radar" page — a cross-module view that surfaces everything needing your attention, organized by urgency. This is the command center of the platform.

## Step 0: Auto-Sync External Data

Before building, ensure data is fresh. Follow the auto-sync procedure in CLAUDE.md — check `gmail_last_synced` and `calendar_last_synced` in `soy_meta`, and sync if stale (>15 min) or never synced. Do this silently.

## Step 1: Read the Design System

Read these files first:
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/template-base.html` — HTML skeleton
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/navigation-patterns.md` — sidebar patterns
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/delight-patterns.md` — micro-interactions and delight

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

### Nudge Data — Use Computed Views

All nudge data comes from the `v_nudge_items` view (defined in `data/migrations/014_computed_views.sql`). This view pre-computes all urgency tiers, entity names, dates, and context — Claude does NOT calculate these values.

```sql
-- All nudge items, pre-computed with urgency tiers
SELECT nudge_type, entity_id, tier, entity_name, contact_id, project_id,
  description, relevant_date, days_value, extra_context, icon
FROM v_nudge_items
ORDER BY
  CASE tier WHEN 'urgent' THEN 1 WHEN 'soon' THEN 2 WHEN 'awareness' THEN 3 END,
  days_value DESC;

-- Summary counts for header pills
SELECT tier, count FROM v_nudge_summary;

-- Emails needing response (for awareness section, separate view)
SELECT id, subject, from_name, from_address, contact_name, days_old, urgency
FROM v_email_response_queue
WHERE days_old > 3
LIMIT 5;
```

### Tier Reference

- **Urgent (red):** `tier = 'urgent'` — overdue follow-ups, overdue commitments, overdue tasks
- **Soon (amber):** `tier = 'soon'` — due within 3 days (follow-ups, commitments, tasks), projects approaching target within 7 days
- **Awareness (blue):** `tier = 'awareness'` — cold contacts (30+ days), stale projects (14+ days), decisions pending outcome (90+ days), untracked frequent contacts (5+ emails)

Also add today's meetings to the Soon section separately (these aren't in the nudge view since they're not "problems"):
```sql
SELECT title, start_time, end_time, attendees, location
FROM calendar_events
WHERE date(start_time) = date('now') AND status != 'cancelled'
ORDER BY start_time ASC;
```

## Step 3: Compute Counts

Counts come directly from the `v_nudge_summary` view — do not compute manually:

```sql
SELECT tier, count FROM v_nudge_summary;
```

This returns rows like `urgent|12`, `soon|4`, `awareness|9`. Adjust counts:
- Add the today's-meetings count to `soon_count`
- Add the `v_email_response_queue` count (WHERE `days_old > 3`) to `awareness_count`

These two sources are separate from the nudge views and must be added manually.

Determine the **most urgent single item** for the hero callout. Priority order:
1. The most overdue follow-up or commitment (whichever has more days overdue)
2. The most overdue task
3. The oldest unanswered email
4. The coldest contact

## Step 4: Generate HTML

Generate a self-contained HTML file. Follow the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font).

### Sidebar

Include the sidebar from `navigation-patterns.md` with Nudges active in the Tools section.

### Page Structure

```
Sidebar (Nudges active in Tools section)

Header card
+-- Title: "Attention Radar"
+-- Subtitle: "X items need your attention" (or "All clear" if zero)
+-- Summary pills:
    +-- Red pill: "N Urgent" (hidden if 0)
    +-- Amber pill: "N Soon" (hidden if 0)
    +-- Blue pill: "N Awareness" (hidden if 0)

Hero Callout (if any urgent items exist)
+-- Full-width card with gradient left border (red to amber)
+-- Light amber background gradient
+-- Large icon (entity-type specific)
+-- Bold title with urgency context
+-- Description and suggested action
+-- Direct link to entity page (if exists)
+-- Subtle pulse animation on icon

URGENT section (if urgent items exist)
+-- Section header: red dot + "Urgent — Needs immediate attention"
+-- Grid of red-accented cards (grid-cols-1 md:grid-cols-2 gap-3)
+-- Each card: red left border, icon, entity name, context, action link

SOON section (if soon items exist)
+-- Section header: amber dot + "Soon — Coming up in the next few days"
+-- Grid of amber-accented cards
+-- Each card: amber left border, icon, entity name, context

AWARENESS section (if awareness items exist)
+-- Section header: blue dot + "Awareness — Worth knowing about"
+-- Grid of blue-accented cards
+-- Each card: blue left border, icon, entity name, context

ALL CLEAR (if zero total items)
+-- Full-width centered card
+-- Check-circle icon (green)
+-- "Nothing needs your attention. Nice work."

Footer
```

### Hero Callout Design

The most urgent item gets a full-width hero card:

```html
<div class="nudge-hero mb-6">
  <div class="flex items-start gap-4">
    <div class="pulse-dot mt-1">
      <i data-lucide="alert-triangle" class="w-6 h-6 text-red-500"></i>
    </div>
    <div class="flex-1">
      <h3 class="text-lg font-bold text-zinc-900">Follow-up with Sarah Chen — 5 days overdue</h3>
      <p class="text-sm text-zinc-600 mt-1">You planned to discuss the proposal update. Last contact was 12 days ago.</p>
      <a href="contact-sarah-chen.html" class="inline-flex items-center gap-1 text-sm font-medium text-amber-700 hover:text-amber-900 mt-3">
        View contact <i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>
      </a>
    </div>
  </div>
</div>
```

### CSS (include in `<style>` block)

Include sidebar CSS from navigation-patterns.md, plus:

```css
.nudge-hero {
  background: linear-gradient(135deg, #fffbeb 0%, #fff7ed 100%);
  border-left: 4px solid;
  border-image: linear-gradient(to bottom, #ef4444, #f59e0b) 1;
  border-radius: 0.75rem;
  padding: 1.5rem;
}
.pulse-dot {
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

### Nudge Card Design

Each nudge card follows this pattern:

```html
<div class="bg-white rounded-lg border border-zinc-200 p-4 border-l-4 border-l-red-400">
  <div class="flex items-start gap-3">
    <i data-lucide="clock" class="w-4 h-4 text-red-500 mt-0.5 shrink-0"></i>
    <div>
      <div class="text-sm font-medium text-zinc-900">
        <a href="contact-name.html" class="text-blue-600 hover:text-blue-800 hover:underline">Contact Name</a>
        — Follow-up overdue
      </div>
      <p class="text-xs text-zinc-500 mt-1">Due 3 days ago · "Discuss proposal update"</p>
      <p class="text-xs text-zinc-400 mt-1">Schedule a follow-up</p>
    </div>
  </div>
</div>
```

Color variants:
- **Urgent**: `border-l-red-400`, icon uses `text-red-500`
- **Soon**: `border-l-amber-400`, icon uses `text-amber-500`
- **Awareness**: `border-l-blue-400`, icon uses `text-blue-500`

### Icons by Entity Type

| Entity | Lucide Icon |
|--------|-------------|
| Follow-up | `clock` |
| Commitment | `target` |
| Task | `check-square` |
| Calendar event | `calendar` |
| Contact | `users` |
| Project | `folder` |
| Decision | `git-branch` |
| Email | `mail` |

### Context Lines for Each Nudge Type

- Overdue follow-up: "Due X days ago · '{reason}'"
- Overdue commitment: "Due X days ago · '{description}'"
- Overdue task: "Due X days ago · Project: {project_name}"
- Due-soon follow-up: "Due {relative_date} · '{reason}'"
- Due-soon commitment: "Due {relative_date} · '{description}'"
- Due-soon task: "Due {relative_date} · Project: {project_name}"
- Today's meeting: "{start_time} · {location}"
- Approaching project: "{days_until} days to target · {open_tasks} open tasks"
- Cold contact: "Last contact: {days_silent} days ago · {company}"
- Stale project: "No activity in {days_stale} days"
- Pending decision: "Decided {days_ago} days ago · No outcome recorded"
- Old email: "From {from_name} · {days_old} days ago · '{subject}'"
- Untracked contact: "{from_name or email} · {email_count} emails, not tracked"

### Suggested Actions

- Follow-up: "Schedule a follow-up"
- Commitment: "Review and update"
- Task: "Update task status"
- Meeting: "Prep for this meeting"
- Project: "Review project progress"
- Cold contact: "Reach out"
- Stale project: "Check in on progress"
- Decision: "Record the outcome"
- Email: "Reply or archive"
- Untracked contact: "Run `/discover` to review"

### All Clear State

If no nudges exist at all:

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-12 text-center">
  <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-50 mb-4">
    <i data-lucide="check-circle" class="w-8 h-8 text-emerald-500"></i>
  </div>
  <h3 class="text-lg font-semibold text-zinc-900 mb-1">Nothing needs your attention</h3>
  <p class="text-sm text-zinc-500">No overdue items, no cold contacts, everything is on track. Nice work.</p>
</div>
```

### Entity Name Linking

For every contact, project, or entity name in a nudge card, check if that entity has a generated page in the `generated_views` query results. If a page exists, render the name as a link:
```html
<a href="contact-{slug}.html" class="font-medium text-blue-600 hover:text-blue-800 hover:underline">Name</a>
```
If no page exists, render as bold plain text.

### Summary Pills

```html
<div class="flex items-center gap-2 mt-3">
  <span class="px-3 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700">3 Urgent</span>
  <span class="px-3 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700">5 Soon</span>
  <span class="px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700">2 Awareness</span>
</div>
```

Only show pills for categories with items.

## Design Rules (non-negotiable)

- Use the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- The hero callout gradient and pulse animation are signature elements — always include them when urgent items exist
- Grid of nudge cards: `grid grid-cols-1 md:grid-cols-2 gap-3`
- Section headers: `text-xs font-semibold uppercase tracking-wider` with a colored dot (8px, `rounded-full`)
- All data static in HTML — no JavaScript data fetching
- JS: Lucide icons + delight layer from template-base.html (countups, scroll reveals, card stagger)
- Module-aware: only show nudges for installed modules. Skip queries entirely for uninstalled modules.

## Step 5: Write, Register, and Open

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/nudges.html`

**Register the view:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Nudges', 'nudges.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Open with: `open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/nudges.html"`

Tell the user: "Nudges view opened." Then summarize: "X urgent, Y upcoming, Z worth a look." or "All clear — nothing needs your attention."
