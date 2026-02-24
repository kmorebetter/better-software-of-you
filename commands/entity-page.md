---
description: Generate a contact intelligence brief — everything about a person in one page
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: <contact name or id>
---

# Entity Page

Generate a contact intelligence brief for the contact specified in $ARGUMENTS. This is the flagship view — a single page that synthesizes everything the system knows about a person: profile, relationship context, company intel, email history, projects, upcoming events, and AI-generated prep.

**Reference implementation:** `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/entity-page-reference.html` — this is the gold standard. Match its layout, density, and tone.

## Step 0: Auto-Sync External Data

Before building the entity page, ensure data is fresh. Follow the auto-sync procedure in CLAUDE.md — check `gmail_last_synced` and `calendar_last_synced` in `soy_meta`, and sync if stale (>15 min) or never synced. Do this silently.

## Step 1: Read References + Resolve Entity

Read design references in parallel:
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/entity-page-reference.html`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/template-base.html`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/component-patterns.md`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/activity-feed-patterns.md`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/navigation-patterns.md`

At the same time, resolve the contact. Query `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`:

```sql
SELECT * FROM contacts WHERE name LIKE '%$ARGUMENTS%' OR id = '$ARGUMENTS';
```

If multiple matches, pick the best match or ask the user.

**Determine the contact scope:**

- If the contact's `type` is `'individual'`: scope = just this contact's ID
- If the contact's `type` is `'company'`: scope = this contact's ID + all individuals at the company:
  ```sql
  SELECT id FROM contacts WHERE company = ? AND type = 'individual' AND status = 'active';
  ```
- If the contact is an individual with a `company` value, also note the company name for context (but don't expand scope — keep it focused on the individual)

## Step 2: Check Installed Modules

```sql
SELECT name FROM modules WHERE enabled = 1;
```

Only run queries for installed modules. Skip queries for modules that aren't installed.

## Step 3: Gather Data

Run these queries. Use the resolved contact ID(s) from Step 1 wherever you see `?` or `/* scope */`. Run all queries in a single `sqlite3` heredoc call for efficiency.

### Always query:

```sql
-- Tags
SELECT t.name, t.color FROM tags t
JOIN entity_tags et ON et.tag_id = t.id
WHERE et.entity_type = 'contact' AND et.entity_id = ?;

-- Notes on this contact
SELECT content, created_at FROM notes
WHERE entity_type = 'contact' AND entity_id IN (/* scope */)
ORDER BY created_at DESC LIMIT 10;

-- Activity log entries for this contact
SELECT action, details, created_at FROM activity_log
WHERE entity_type = 'contact' AND entity_id IN (/* scope */)
ORDER BY created_at DESC LIMIT 20;
```

### If CRM module installed:

```sql
-- Interactions
SELECT ci.*, c.name as contact_name FROM contact_interactions ci
JOIN contacts c ON c.id = ci.contact_id
WHERE ci.contact_id IN (/* scope */)
ORDER BY ci.occurred_at DESC LIMIT 30;

-- Related contacts
SELECT cr.relationship_type, cr.notes,
  CASE WHEN cr.contact_id_a = ? THEN cb.name ELSE ca.name END as related_name,
  CASE WHEN cr.contact_id_a = ? THEN cb.company ELSE ca.company END as related_company,
  CASE WHEN cr.contact_id_a = ? THEN cb.role ELSE ca.role END as related_role
FROM contact_relationships cr
LEFT JOIN contacts ca ON ca.id = cr.contact_id_a
LEFT JOIN contacts cb ON cb.id = cr.contact_id_b
WHERE cr.contact_id_a = ? OR cr.contact_id_b = ?;

-- Pending follow-ups
SELECT f.*, c.name as contact_name FROM follow_ups f
JOIN contacts c ON c.id = f.contact_id
WHERE f.contact_id IN (/* scope */) AND f.status = 'pending'
ORDER BY f.due_date ASC;
```

### If Gmail module installed:

```sql
-- Individual emails (for expanded thread view)
SELECT id, thread_id, subject, snippet, from_name, from_address,
  to_addresses, direction, received_at, contact_id
FROM emails
WHERE contact_id IN (/* scope */)
ORDER BY received_at ASC;
```

### If Calendar module installed:

```sql
-- Calendar events (upcoming and recent)
SELECT * FROM calendar_events
WHERE contact_ids LIKE '%' || ? || '%'
ORDER BY start_time DESC
LIMIT 30;
```

For company-type contacts, check all member IDs against `contact_ids`.

### If Project Tracker installed:

```sql
-- Projects where this contact is the client
SELECT p.*,
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status != 'done') as open_tasks,
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status = 'done') as done_tasks,
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id) as total_tasks
FROM projects p
WHERE p.client_id IN (/* scope */)
ORDER BY p.updated_at DESC;

-- All tasks for those projects (for inline checklist)
SELECT t.*, p.name as project_name FROM tasks t
JOIN projects p ON t.project_id = p.id
WHERE p.client_id IN (/* scope */)
ORDER BY t.due_date ASC NULLS LAST;
```

### If Conversation Intelligence installed:

```sql
-- Transcripts involving this contact (including call intelligence JSON)
SELECT t.id, t.title, t.summary, t.duration_minutes, t.occurred_at,
  t.call_intelligence,
  GROUP_CONCAT(DISTINCT c.name) as participant_names
FROM transcripts t
JOIN transcript_participants tp ON tp.transcript_id = t.id
LEFT JOIN contacts c ON c.id = tp.contact_id AND tp.is_user = 0
WHERE tp.contact_id IN (/* scope */) OR (tp.is_user = 1 AND t.id IN (
  SELECT transcript_id FROM transcript_participants WHERE contact_id IN (/* scope */)
))
GROUP BY t.id
ORDER BY t.occurred_at DESC
LIMIT 20;

-- Open commitments (both directions)
SELECT com.*,
  CASE WHEN com.is_user_commitment = 1 THEN 'You' ELSE c.name END as owner_name,
  t.title as from_call, t.occurred_at as call_date
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
LEFT JOIN transcripts t ON t.id = com.transcript_id
WHERE com.status IN ('open', 'overdue')
  AND (com.owner_contact_id IN (/* scope */)
    OR com.transcript_id IN (
      SELECT transcript_id FROM transcript_participants WHERE contact_id IN (/* scope */)));

-- Latest relationship score
SELECT * FROM relationship_scores
WHERE contact_id = ?
ORDER BY score_date DESC LIMIT 1;

-- Communication insights (with evidence data)
SELECT insight_type, content, sentiment, data_points FROM communication_insights
WHERE contact_id = ? ORDER BY created_at DESC LIMIT 5;

-- Per-call metrics for dominance calculation
SELECT cm.transcript_id, cm.talk_ratio, cm.word_count,
  (SELECT COUNT(*) FROM transcript_participants WHERE transcript_id = cm.transcript_id) as participant_count,
  cm.talk_ratio / (1.0 / (SELECT COUNT(*) FROM transcript_participants WHERE transcript_id = cm.transcript_id)) as dominance_ratio,
  t.occurred_at
FROM conversation_metrics cm
JOIN transcripts t ON t.id = cm.transcript_id
WHERE cm.transcript_id IN (
  SELECT transcript_id FROM transcript_participants WHERE contact_id = ?
)
AND cm.contact_id IN (
  SELECT contact_id FROM transcript_participants tp WHERE tp.transcript_id = cm.transcript_id AND tp.is_user = 1
)
ORDER BY t.occurred_at DESC LIMIT 10;

-- Transcript detail pages (for "View full analysis" links)
SELECT entity_id, filename FROM generated_views
WHERE view_type = 'transcript_page' AND entity_type = 'transcript';
```

**Aggregate call intelligence across transcripts:**

When processing the transcript query results, if any transcripts have `call_intelligence` JSON, aggregate across all calls for this contact:

- **Cumulative pain points** — collect from all calls, deduplicate by title (keep most recent occurrence), sort most recent first
- **Known tech stack** — merge tool names from all calls, deduplicate by name
- **Unresolved concerns** — concerns where `addressed` is false, plus all concerns from the most recent call (even if addressed — shows current state)

**Per-call detail links:**

For each transcript listed in the Call Intelligence card, check if a transcript detail page exists in `generated_views` (match `view_type = 'transcript_page'` and `entity_id` = transcript ID). If so, add a "View full analysis" link after the call summary:

```html
<a href="transcript-{slug}.html" class="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 hover:underline mt-1">
  View full analysis <i data-lucide="arrow-right" class="w-3 h-3"></i>
</a>
```

Only render this link if the transcript's detail page exists in `generated_views`.

### If Notes module installed:

```sql
-- Standalone notes linked to this contact
SELECT sn.id, sn.title, substr(sn.content, 1, 150) as preview, sn.tags, sn.pinned, sn.created_at
FROM standalone_notes sn
WHERE sn.linked_contacts LIKE '%' || ? || '%'
ORDER BY sn.pinned DESC, sn.created_at DESC
LIMIT 10;
```

If notes exist, add a **Notes** card to the right column (after About, before Discovery Questions). Show each note's title, preview, tags as pills, and age. Pinned notes show a pin indicator. If no linked notes exist, skip this card entirely.

**Notes card layout:**
```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5 mb-4">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="sticky-note" class="w-5 h-5 text-zinc-400"></i>
        <h3 class="text-sm font-semibold">Notes</h3>
    </div>
    <div class="space-y-3">
        <!-- Each note -->
        <div class="pb-3 border-b border-zinc-100 last:border-0 last:pb-0">
            <div class="flex items-center gap-2 mb-1">
                <span class="text-sm font-medium text-zinc-900">Note title</span>
                <!-- pin icon if pinned -->
            </div>
            <p class="text-xs text-zinc-500 leading-relaxed">Preview text...</p>
            <div class="flex flex-wrap gap-1 mt-1.5">
                <span class="px-1.5 py-0.5 rounded text-[10px] bg-violet-50 text-violet-600">#tag</span>
            </div>
            <p class="text-[10px] text-zinc-400 mt-1">3 days ago</p>
        </div>
    </div>
</div>
```

## Step 4: Synthesize Intelligence

This is where the page goes beyond raw data. Using all gathered data, synthesize the following sections. Write in natural, narrative language — not bullet dumps.

### Relationship Context Card

Template with required data points, in this order:

1. **Depth + reasoning** (from `relationship_scores.notes`) — ALWAYS first if data exists. Display the depth level and the exact reasoning string from the notes field: e.g., "**Collaborative** — 7 meetings in 90d, dominance 1.1x, follow-through user:75% contact:68%"
2. **Trajectory + evidence** — show trajectory label with frequency comparison: "Strengthening — meeting frequency up 40% (current: 1.8/week vs previous: 1.3/week)"
3. **Follow-through both directions** — "Your follow-through: 85% · Their follow-through: 72%" — use "—" for NULL values
4. **Communication pattern** — dominance ratio + talk ratio avg: "You talk 55% of the time (dominance: 1.1x in 1:1s)" — use "—" for NULL values
5. **Next action** — from `calendar_events` or `follow_ups`, whichever is sooner. Surface prominently with amber callout if upcoming event.
6. **How you met / key moments** — from interactions and notes (keep as narrative, but AFTER the computed data above)

If no Conversation Intelligence data exists: skip items 1–4, show interaction frequency and recency instead:
- "N interactions in the last 30 days (last: X days ago)"

Pull from: relationship_scores (especially `notes` field), contact_interactions, calendar_events, follow_ups, notes, commitments, communication_insights. Never use vague language like "a sign of growing trust" — use the computed depth level and metrics.

### Company Intel Card

If the contact has a `company` value, build a company context card with defined extraction rules:

- **Key team** — always computable:
  ```sql
  SELECT name, role FROM contacts WHERE company = ? AND status = 'active' AND id != ?;
  ```
- **Project count** — always computable:
  ```sql
  SELECT COUNT(*) FROM projects WHERE client_id = ?;
  ```
- **Stats from notes** — only show if notes contain explicit numbers. Match patterns like "$X", "X employees", "X properties", "X revenue". Don't infer stats that aren't stated.
- **Description** — pull from notes if available. Don't invent a company description.
- **Website** — from contact fields or notes. Don't guess.

Pull from: contact fields, notes, other contacts with matching company, projects. Never fabricate company information.

### Email Thread Card

When emails exist, show the **full conversation expanded** — not collapsed. Each message shows:
- Sender avatar (initials), name (or "You" for outbound)
- Date/time
- One-line summary of what that message said or did

Group by thread. Show the most active/recent thread first. Use color-coded avatars: emerald for you, blue for the contact, zinc for third parties.

### Discovery Questions (gated — not always shown)

**Generate ONLY when at least one condition is true:**
- `COUNT(contact_interactions WHERE contact_id = ?) < 3` (early relationship)
- `MAX(contact_interactions.occurred_at) < date('now', '-14 days')` (stale — need to re-engage)
- Upcoming calendar event with this contact within 3 days

**If none of these conditions are met: skip the Discovery Questions card entirely.**

When generated, anchor to data:
- "Based on {contact.role} at {contact.company}, and that your last {N} conversations focused on {topics from call_intelligence}..."
- Reference specific gaps: "You haven't discussed {X} yet" or "Last call touched on {Y} — worth following up"
- 3-5 questions tailored to the contact's role, company, known concerns, and gaps in your knowledge

These should feel like a smart advisor prepped them — not generic.

## Step 5: Generate HTML

Generate a self-contained HTML file. **Match the reference implementation exactly in structure and visual quality.**

### Page Structure

```
Contact Header (full width card)
├── Avatar (initials) + Name + Role at Company
├── Email + Phone inline
└── Status + Tag badges

Two-column grid (lg:grid-cols-3)
├── Left column (lg:col-span-2)
│   ├── Relationship Context card (with amber callout for next action)
│   ├── Company Intel card (stats grid + description + key team + notable work)
│   ├── Email Thread card (expanded per-message view)
│   └── Call Intelligence card (if aggregated call_intelligence data exists)
│       ├── Card header: brain icon + "Call Intelligence" + call count badge
│       ├── Pain Points section (deduplicated across calls, severity dots: red=high, amber=medium)
│       ├── Known Tech Stack section (merged pills with category labels)
│       └── Unresolved Concerns section (unaddressed items flagged for follow-up)
└── Right column
    ├── Upcoming card (next meeting highlighted)
    ├── Project card (with inline task checklist — checkmarks for done, squares for open)
    ├── About card (background/bio from notes)
    └── Discovery Questions card (AI-generated)

Footer
```

### Design Rules

- Use the template-base.html skeleton (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- Avatar colors: `blue-100`/`blue-700` for the contact, `emerald-100`/`emerald-700` for you, `zinc-100`/`zinc-500` for others
- Callout cards: `bg-amber-50 border-amber-100` for urgent/upcoming, `bg-blue-50 border-blue-100` for informational
- Stats grid: `bg-zinc-50 rounded-lg p-3 text-center` with bold number + label
- All data static in HTML — no JavaScript data fetching
- The only JS: Lucide icon initialization (`lucide.createIcons()`)
- Responsive: sidebar stacks below on mobile via `grid-cols-1 lg:grid-cols-3`

### Rendering Principles

- **Narrative over tables.** Write relationship context as prose, not bullet lists.
- **Summarize email content.** Don't paste raw snippets — describe what each message did ("Made the intro", "Confirmed tomorrow", "Had a calendar glitch").
- **Only show cards that have data.** If no project exists, skip the project card. If no company intel, skip that card.
- **Highlight what matters now.** If there's an upcoming meeting, it should be the most prominent thing on the page.

## Step 6: Add Navigation

Include the sidebar from `navigation-patterns.md` with this contact highlighted in the People section. The People section auto-expands with this contact's `.sidebar-entity` having the `active` class.

## Step 7: Write, Register, and Open

Generate a filename slug from the contact name (lowercase, hyphens for spaces):

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/contact-{slug}.html`

**Register the view** so other pages can link to it:
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('entity_page', 'contact', ?, ?, 'contact-{slug}.html')
ON CONFLICT(filename) DO UPDATE SET
  entity_name = excluded.entity_name,
  updated_at = datetime('now');
```

Open with: `open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/contact-{slug}.html"`

Tell the user: "Contact page for **{contact name}** opened." Then briefly summarize what's on it — e.g., "Shows relationship context from Vahid's intro, 6-email thread, upcoming discovery call, and 5 prep questions."
