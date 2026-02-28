---
description: Generate a meeting prep brief — everything you need to know before an upcoming meeting, in one page
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: <contact name, event title, or blank for next meeting>
---

# Meeting Prep Brief

Generate a meeting prep brief for the event or contact specified in $ARGUMENTS. If no argument given, prep for the next upcoming meeting. This is the pre-meeting power page — synthesizing relationship context, open items, recent conversations, email threads, and AI-generated talking points into a single scannable brief.

## Step 0: Auto-Sync External Data

Before building, ensure data is fresh. Follow the auto-sync procedure in CLAUDE.md — check `gmail_last_synced` and `calendar_last_synced` in `soy_meta`, and sync if stale (>15 min) or never synced. Do this silently.

## Step 1: Read References + Resolve Meeting

Read design references in parallel:
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/template-base.html`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/component-patterns.md`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/navigation-patterns.md`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/delight-patterns.md`

At the same time, resolve the meeting. Query `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`:

### Path A: No argument (next upcoming meeting)

```sql
SELECT id, title, description, location, start_time, end_time, all_day, status,
  attendees, contact_ids, project_id
FROM calendar_events
WHERE (start_time > datetime('now') OR (start_time <= datetime('now') AND end_time > datetime('now')))
  AND status != 'cancelled'
  AND all_day = 0
ORDER BY start_time ASC
LIMIT 1;
```

If nothing found, expand to include all-day events in the next 7 days. If still nothing: tell the user "No upcoming meetings found. Connect your calendar with `/google-setup`, or specify a contact name: `/prep Sarah` for a general prep brief."

**Special: meeting happening now.** If the next event's `start_time` is in the past but `end_time` is in the future, it's currently happening. Still generate the brief, but use the "Happening now" countdown style (green accent).

### Path B: Contact name argument

```sql
SELECT id, name, email FROM contacts WHERE name LIKE '%$ARGUMENTS%' AND status = 'active';
```

Then find the next meeting with that contact:

```sql
SELECT ce.* FROM calendar_events ce
WHERE ce.start_time > datetime('now')
  AND ce.status != 'cancelled'
  AND (
    ce.contact_ids LIKE '%' || ? || '%'
    OR ce.attendees LIKE '%' || ? || '%'
  )
ORDER BY ce.start_time ASC
LIMIT 1;
```

Where `?` is the resolved contact ID (for `contact_ids`) and the contact's email (for `attendees`).

**Fallback: no meeting found.** If no upcoming meeting exists with this contact, generate a **contact-only prep brief** — same data enrichment without the meeting header card. Replace the meeting header with a simpler header: "Prep Brief: {Contact Name}". Tell the user: "No upcoming meeting found with {name}, but here's a prep brief based on your history."

### Path C: Event title argument

```sql
SELECT * FROM calendar_events
WHERE title LIKE '%$ARGUMENTS%'
  AND start_time > datetime('now', '-1 day')
  AND status != 'cancelled'
ORDER BY start_time ASC
LIMIT 1;
```

If multiple matches, list them and ask the user to pick.

## Step 2: Check Installed Modules

```sql
SELECT name FROM modules WHERE enabled = 1;
```

Only run queries for installed modules. Skip queries for modules that aren't installed.

## Step 3: Resolve Attendees

Parse attendees from two sources on the resolved event:

1. **`contact_ids`** — comma-separated contact IDs matched during calendar sync
2. **`attendees`** — may contain email addresses (JSON or comma-separated text)

Build the attendee roster:

```sql
-- Known contacts from contact_ids
SELECT c.id, c.name, c.email, c.company, c.role, c.type, c.status, c.notes
FROM contacts c
WHERE c.id IN (/* parsed contact_ids */)
  AND c.status = 'active';

-- Also match attendee emails not already found
SELECT c.id, c.name, c.email, c.company, c.role
FROM contacts c
WHERE c.email IN (/* emails from attendees field not already matched */)
  AND c.status = 'active';
```

Exclude the user's own email (from `user_profile`).

Classify each attendee:
- **Known contact with data** — full enrichment (has interactions, transcripts, or relationship scores)
- **Known contact, sparse data** — basic card with name/role/company + "Limited data" note
- **Unknown attendee** — email only, dashed-border card, suggest adding as contact

**Cap detailed enrichment at 5 attendees.** If more than 5 known contacts, enrich the 5 with the most data. Show the rest as a compact "Also attending: {names}" list.

## Step 4: Gather Enrichment Data

For each known attendee, run enrichment queries. Use a single `sqlite3` heredoc call for efficiency. Adapt these from the entity-page patterns but focus on actionable prep data.

### If CRM module installed:

```sql
-- Recent interactions (last 30 days)
SELECT type, direction, subject, summary, occurred_at
FROM contact_interactions
WHERE contact_id = ?
ORDER BY occurred_at DESC LIMIT 10;

-- Pending follow-ups
SELECT f.*, c.name as contact_name FROM follow_ups f
JOIN contacts c ON c.id = f.contact_id
WHERE f.contact_id = ? AND f.status = 'pending'
ORDER BY f.due_date ASC;
```

### If Conversation Intelligence installed:

```sql
-- Latest relationship score
SELECT * FROM relationship_scores
WHERE contact_id = ? ORDER BY score_date DESC LIMIT 1;

-- Communication insights
SELECT insight_type, content, sentiment, data_points
FROM communication_insights
WHERE contact_id = ? ORDER BY created_at DESC LIMIT 5;

-- Open commitments (both directions)
SELECT com.*,
  CASE WHEN com.is_user_commitment = 1 THEN 'You' ELSE c.name END as owner_name,
  t.title as from_call, t.occurred_at as call_date
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
LEFT JOIN transcripts t ON t.id = com.transcript_id
WHERE com.status IN ('open', 'overdue')
  AND (com.owner_contact_id = ?
    OR com.transcript_id IN (
      SELECT transcript_id FROM transcript_participants WHERE contact_id = ?));

-- Recent transcripts (last 3 calls with this person)
SELECT t.id, t.title, t.summary, t.duration_minutes, t.occurred_at,
  t.call_intelligence
FROM transcripts t
JOIN transcript_participants tp ON tp.transcript_id = t.id
WHERE tp.contact_id = ?
ORDER BY t.occurred_at DESC LIMIT 3;

-- Transcript detail pages (for linking)
SELECT entity_id, filename FROM generated_views
WHERE view_type = 'transcript_page' AND entity_type = 'transcript';
```

### If Gmail module installed:

```sql
-- Recent emails with this attendee (last 14 days)
SELECT id, thread_id, subject, snippet, from_name, from_address,
  to_addresses, direction, received_at
FROM emails
WHERE contact_id = ?
ORDER BY received_at DESC LIMIT 15;
```

### If Project Tracker installed:

```sql
-- Active projects where this person is the client
SELECT p.id, p.name, p.status, p.priority, p.target_date,
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status != 'done') as open_tasks,
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status = 'done') as done_tasks
FROM projects p
WHERE p.client_id = ? AND p.status IN ('active', 'planning');

-- Also check if the event itself is linked to a project
SELECT p.id, p.name, p.status, p.priority, p.target_date
FROM projects p
WHERE p.id = ?;
```

### Cross-meeting data:

```sql
-- Entity pages for attendees (for linking)
SELECT entity_id, entity_name, filename FROM generated_views
WHERE view_type = 'entity_page' AND entity_type = 'contact'
  AND entity_id IN (/* attendee contact IDs */);

-- Project pages (for linking)
SELECT entity_id, entity_name, filename FROM generated_views
WHERE view_type = 'entity_page' AND entity_type = 'project';

-- User name for greeting
SELECT value FROM user_profile WHERE category = 'identity' AND key = 'name';
```

## Step 5: Synthesize the Prep Brief

This is the intelligence layer. Using all gathered data, synthesize:

### Per-attendee relationship context

Use `relationship_scores` (depth, trajectory), `communication_insights`, and recent interaction patterns. Write in narrative prose, grounded in data. Example: "**Collaborative** — 7 meetings in 90d, dominance 1.1x. Follow-through: you 85%, Sarah 72%."

If no Conversation Intelligence data exists for an attendee, use interaction frequency and recency instead.

### Open items audit

Aggregate all commitments and follow-ups across ALL attendees. Split into:
- **Things you owe them** — your commitments + your pending follow-ups
- **Things they owe you** — their commitments

Flag anything overdue with urgency. This is the most actionable section.

### Conversation highlights

From the most recent 1-3 transcripts per attendee, extract: key topics discussed, unresolved concerns, pain points from `call_intelligence` JSON. Link to transcript detail pages where available.

### Email context

Summarize recent email threads with attendees. Focus on: what was the last thing discussed, any unanswered threads (latest is inbound with no reply).

### Suggested talking points

Synthesize from ALL of the above into 3-7 concrete, data-grounded talking points. Each must cite its source:
- "Follow up on the API integration timeline — Sarah asked about this in your Feb 12 call, and you committed to an update"
- "Address the unanswered email from Daniel (Feb 25) about the budget proposal"
- "Check on their Q1 headcount decision — mentioned as pending in your last call"

**Never generate generic talking points like "Discuss project updates" or "Establish meeting objectives."** Every point must trace to a specific piece of data. If there isn't enough data for 3 grounded points, generate fewer — quality over quantity.

## Step 6: Generate HTML

Generate a self-contained HTML file using the template-base.html skeleton (Tailwind CDN, Lucide CDN, Inter font). Include all delight layer CSS/JS from template-base.html.

### Page Structure

```
Meeting Header (full width card, prominent)
├── Calendar-clock icon + Event title
├── Date · Time range · Duration
├── Location / Video link (if present)
├── Stat pills: N attendees · N open items · Last spoke X days ago
└── Countdown callout (color-coded by urgency)

Attendee Strip (horizontal scroll)
├── Per attendee: initials avatar, name (linked to entity page if exists),
│   role at company, depth badge, trajectory indicator
└── Unknown attendees: dashed border, email only, "Not in your contacts"

Two-column grid (lg:grid-cols-3)
├── Left column (lg:col-span-2)
│   ├── Open Items card (MOST IMPORTANT — top position)
│   │   ├── "You owe them" section
│   │   │   ├── Overdue: bg-red-50 border-l-4 border-red-400
│   │   │   ├── Due soon: bg-amber-50 border-l-4 border-amber-400
│   │   │   └── Open: border-l-4 border-zinc-200
│   │   ├── "They owe you" section
│   │   └── Empty: "All clear" celebration pattern
│   ├── Recent Conversations card
│   │   ├── Per-transcript: title + date + duration + 2-3 line summary
│   │   ├── Key topics / pain points from call_intelligence
│   │   └── "View full analysis →" link if transcript page exists
│   ├── Email Context card
│   │   ├── Threads grouped, most recent first
│   │   ├── Last message: who, when, one-line summary
│   │   └── Unanswered flag if latest inbound has no reply
│   └── Project Context card (only if event linked to project OR attendees are project clients)
│       ├── Project name + status badge + progress bar
│       └── Open tasks count, next milestone
└── Right column
    ├── Talking Points card (PREMIUM — special blue gradient treatment)
    │   ├── bg-gradient-to-b from-blue-50 to-white, border-blue-100
    │   ├── Numbered list with blue number circles
    │   └── Each: bold action + text-xs context citing source
    ├── Relationship Context card (per attendee, stacked)
    │   ├── Depth + trajectory with evidence
    │   ├── Communication style
    │   └── Follow-through rates
    └── Quick Actions card
        ├── Links to entity pages for each known attendee
        ├── Link to project page if relevant
        └── Link to week view

Footer
├── "Generated by Software of You · DATE at TIME"
```

### Meeting Header Countdown Styles

```html
<!-- Starts in <2 hours — amber urgency -->
<div class="bg-amber-50 border border-amber-200 rounded-lg p-3 mt-4">
  <div class="flex items-center gap-2">
    <i data-lucide="clock" class="w-4 h-4 text-amber-600"></i>
    <span class="text-sm font-semibold text-amber-800">Starts in 47 minutes</span>
  </div>
</div>

<!-- Starts in >2 hours — blue calm -->
<div class="bg-blue-50 border border-blue-100 rounded-lg p-3 mt-4">
  <div class="flex items-center gap-2">
    <i data-lucide="calendar-clock" class="w-4 h-4 text-blue-600"></i>
    <span class="text-sm font-semibold text-blue-800">Tomorrow at 10:30 AM</span>
  </div>
</div>

<!-- Happening now — green -->
<div class="bg-emerald-50 border border-emerald-200 rounded-lg p-3 mt-4">
  <div class="flex items-center gap-2">
    <i data-lucide="radio" class="w-4 h-4 text-emerald-600"></i>
    <span class="text-sm font-semibold text-emerald-800">Happening now — 23 minutes remaining</span>
  </div>
</div>
```

### Attendee Card Styles

```html
<!-- Known contact with data -->
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-4 min-w-[220px] flex-shrink-0 delight-card">
  <div class="flex items-center gap-3 mb-3">
    <span class="w-10 h-10 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-semibold">SC</span>
    <div>
      <a href="contact-sarah-chen.html" class="text-sm font-semibold text-zinc-900 hover:text-blue-600 delight-link">Sarah Chen</a>
      <p class="text-xs text-zinc-500">CTO · Meridian Labs</p>
    </div>
  </div>
  <div class="flex items-center gap-2">
    <span class="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">Collaborative</span>
    <span class="text-xs text-emerald-600 flex items-center gap-0.5">
      <i data-lucide="trending-up" class="w-3 h-3"></i>
      Rising
    </span>
  </div>
</div>

<!-- Unknown attendee -->
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 border-dashed p-4 min-w-[220px] flex-shrink-0 delight-card">
  <div class="flex items-center gap-3 mb-3">
    <span class="w-10 h-10 rounded-full bg-zinc-100 text-zinc-400 flex items-center justify-center text-sm">
      <i data-lucide="user" class="w-5 h-5"></i>
    </span>
    <div>
      <p class="text-sm font-medium text-zinc-600">alex@external.com</p>
      <p class="text-xs text-zinc-400">Not in your contacts</p>
    </div>
  </div>
</div>
```

### Talking Points Card (Premium Treatment)

This card gets special visual treatment — it's the "magic" of the feature:

```html
<div class="bg-gradient-to-b from-blue-50 to-white rounded-xl shadow-sm border border-blue-100 p-5 mb-4">
  <div class="flex items-center gap-2 mb-4">
    <div class="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
      <i data-lucide="lightbulb" class="w-4 h-4 text-blue-600"></i>
    </div>
    <h3 class="text-sm font-semibold text-zinc-900">Talking Points</h3>
  </div>
  <ol class="space-y-3">
    <li class="flex gap-3">
      <span class="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">1</span>
      <div>
        <p class="text-sm font-medium text-zinc-900">Follow up on the API integration timeline</p>
        <p class="text-xs text-zinc-500 mt-0.5">Sarah asked about this in your Feb 12 call — you committed to providing an update</p>
      </div>
    </li>
  </ol>
</div>
```

### Design Rules

- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- Avatar color palette (rotating per attendee): blue, emerald, violet, amber, pink
- Callout cards: `bg-amber-50 border-amber-100` for urgent, `bg-blue-50 border-blue-100` for info
- Open item urgency: red border-l for overdue, amber for due soon, zinc for open
- All data static in HTML — no JavaScript data fetching
- JS: Lucide icons + delight layer (countups, scroll reveals, card stagger)
- Responsive: `grid-cols-1 lg:grid-cols-3` for main grid, attendee strip scrolls horizontally on mobile

### Rendering Principles

- **Narrative over tables.** Relationship context as prose.
- **Only show cards that have data.** No email card if no emails. No project card if no project link.
- **Empty state for open items = "All clear" celebration** (green circle + animated checkmark from delight-patterns.md).
- **Never fabricate data.** If you can't ground a talking point in specific data, don't generate it.
- **Distinguish inference from fact.** "Based on your last 3 calls, topics have shifted from logistics to strategy" — flag the basis.

## Step 7: Add Navigation

Include the sidebar from `navigation-patterns.md`. Prep pages are **sub-pages** (like transcript pages) — they do NOT appear in the sidebar themselves. Set the active state to **Calendar** in the Comms section (the section auto-expands).

Tip card text for prep pages: "Use /prep before any meeting to get a full brief."

## Step 8: Write, Register, and Open

Generate a filename slug from the event title (lowercase, hyphens for spaces, strip special characters). If the event title is generic (e.g., "Meeting"), include the primary attendee name: `prep-meeting-sarah-chen.html`. For contact-only prep (no meeting found), use `prep-{contact-slug}.html`.

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/prep-{slug}.html`

**Register the view:**

For event-based prep:
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('prep_page', 'calendar_event', ?, ?, 'prep-{slug}.html')
ON CONFLICT(filename) DO UPDATE SET
  entity_name = excluded.entity_name,
  updated_at = datetime('now');
```

For contact-only prep:
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('prep_page', 'contact', ?, ?, 'prep-{slug}.html')
ON CONFLICT(filename) DO UPDATE SET
  entity_name = excluded.entity_name,
  updated_at = datetime('now');
```

**Log the activity:**
```sql
INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
VALUES ('calendar_event', ?, 'prep_generated', 'Generated meeting prep brief for: {event title}', datetime('now'));
```

Open with: `open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/prep-{slug}.html"`

Tell the user: "Prep brief for **{event title}** opened." Then briefly summarize what's on it — e.g., "Shows 2 attendees, 3 open commitments, talking points from your last call, and an unanswered email thread."
