---
description: Generate a HubSpot-style entity page with unified activity timeline
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: <contact name or id>
---

# Entity Page

Generate a unified entity page for the contact specified in $ARGUMENTS. This page shows everything about a contact (or company) in one place: profile, action items, and an intelligently grouped activity timeline.

## Step 1: Read Design System + Resolve Entity

Read all three design files in parallel (these define the HTML patterns used to render the page):
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/template-base.html`
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/component-patterns.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/activity-feed-patterns.md`

At the same time, resolve the contact. Query `${CLAUDE_PLUGIN_ROOT}/data/soy.db`:

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

## Step 3: Check Installed Modules

```sql
SELECT name FROM modules WHERE enabled = 1;
```

Only run queries for installed modules. Skip queries for modules that aren't installed.

## Step 4: Gather Data

Run these queries. Use the resolved contact ID(s) from Step 2 wherever you see `?` or `/* scope */`. Run all queries in a single `sqlite3` heredoc call for efficiency.

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
-- Emails collapsed by thread
SELECT
  thread_id,
  COUNT(*) as message_count,
  MAX(received_at) as latest_date,
  MIN(received_at) as first_date,
  GROUP_CONCAT(DISTINCT direction) as directions,
  (SELECT subject FROM emails e2 WHERE e2.thread_id = emails.thread_id ORDER BY received_at DESC LIMIT 1) as subject,
  (SELECT snippet FROM emails e3 WHERE e3.thread_id = emails.thread_id ORDER BY received_at DESC LIMIT 1) as latest_snippet,
  GROUP_CONCAT(DISTINCT from_address) as from_addresses
FROM emails
WHERE contact_id IN (/* scope */)
GROUP BY thread_id
ORDER BY latest_date DESC
LIMIT 50;
```

### If Calendar module installed:

```sql
-- Calendar events (upcoming and recent)
-- Note: contact_ids is comma-separated, so use LIKE matching
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

-- Tasks assigned to this contact
SELECT t.*, p.name as project_name FROM tasks t
JOIN projects p ON t.project_id = p.id
WHERE t.assigned_to IN (/* scope */) AND t.status != 'done'
ORDER BY t.due_date ASC NULLS LAST;
```

### If Conversation Intelligence installed:

```sql
-- Transcripts involving this contact
SELECT t.id, t.title, t.summary, t.duration_minutes, t.occurred_at,
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

-- Communication insights
SELECT insight_type, content, sentiment FROM communication_insights
WHERE contact_id = ? ORDER BY created_at DESC LIMIT 5;
```

## Step 5: Compute Quick Stats

From the query results, calculate:
- **Total emails**: sum of all `message_count` from thread-collapsed emails
- **Total meetings**: count of calendar events + transcripts (deduplicated)
- **Last activity**: most recent date across all data sources — present as relative ("2 days ago")

## Step 6: Build Activity Items

Normalize every query result into activity items. Each item has:
- **type**: email_thread, colleague_email, meeting_upcoming, meeting_past, transcript, interaction, note, commitment_open, commitment_overdue, follow_up_due, follow_up_overdue
- **date**: the canonical date for sorting (received_at, occurred_at, start_time, created_at, due_date)
- **render data**: whatever the HTML pattern needs

### Grouping rules:

**Email thread collapsing** is already done in the SQL (GROUP BY thread_id). Each thread = one activity item showing subject + count + latest snippet + date range.

**Meeting + transcript merging**: If a transcript's `occurred_at` falls on the same day as a calendar event's `start_time`, AND they share at least one participant, merge them into a single "meeting + transcript" item. Use the transcript's summary and commitment count. Use the calendar event's attendees and time.

**Deduplication**:
- If an email exists in the `emails` table AND as a `contact_interaction` with type='email' on the same day with matching subject → keep only the `emails` version (it has thread collapsing)
- If a calendar event AND a `contact_interaction` with type='meeting' on the same day → keep only the calendar event (it has attendees)

### Temporal bucketing:

Sort all activity items by date descending, then assign to sections:

| Section | Rule |
|---------|------|
| **Upcoming** | date > now (future events, future follow-up due dates) |
| **This Week** | date >= start of this week AND date <= now |
| **Earlier This Month** | date >= start of this month AND date < start of this week |
| **Last Month** | date >= start of last month AND date < start of this month |
| **Older** | everything else |

Only render sections that have items. Skip empty sections entirely.

**Rendering caps per section** (to keep page manageable):
- Upcoming: show all (typically small)
- This Week: up to 15 items
- Earlier This Month: up to 10 items
- Last Month: up to 10 items
- Older: up to 20 items, wrapped in `<details>` for collapse

If a section hits its cap, add a note like "and 5 more items" at the end of that section.

## Step 7: Detect Enrichment Signals

Check for actionable signals to surface in the Action Items card:

**Overdue commitments**: Any commitment with `status = 'overdue'` or `deadline_date < date('now')` and `status = 'open'`

**Follow-ups due/overdue**: Any follow-up with `status = 'pending'` and `due_date <= date('now', '+3 days')` (show upcoming ones too)

**Staleness**: Calculate the most recent activity date across ALL sources. If > 30 days ago AND the contact is active, flag it.

**Missing data**: Check if 2 or more of these are NULL/empty: email, phone, company, role. If so, show a subtle "Missing: X, Y" hint below the contact details card (not in the action items card).

Only render the Action Items card if there are overdue commitments, due/overdue follow-ups, or staleness warnings. If everything is clean, skip the card entirely.

## Step 8: Generate HTML

Generate a self-contained HTML file using the template-base.html structure with these modifications:

### Title
Change the page `<title>` to the contact's name. Change the header to show the entity page header pattern (avatar initials + name + company/role + tags + quick stats).

### Layout

```html
<!-- Header (full width) -->
<!-- entity page header pattern from activity-feed-patterns.md -->

<!-- Two-column grid -->
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">

    <!-- Left column (2/3 width) -->
    <div class="lg:col-span-2 space-y-0">
        <!-- Action Items card (only if items exist) -->
        <!-- Activity Timeline with temporal sections -->
    </div>

    <!-- Right column (1/3 width) — sidebar -->
    <div class="space-y-6">
        <!-- Contact Details card -->
        <!-- Related Contacts card (if CRM installed and relationships exist) -->
        <!-- Active Projects card (if Project Tracker installed and projects exist) -->
        <!-- Relationship Health card (if ConvIntel installed and score exists) -->
    </div>
</div>
```

### Design Rules

- Use the template-base.html skeleton (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- Use activity feed patterns from `activity-feed-patterns.md` for all timeline items
- Use base patterns from `component-patterns.md` for status badges, empty states
- All data static in HTML — no JavaScript data fetching
- The only JS: Lucide icon initialization (`lucide.createIcons()`)
- The `<details>` element for the Older section is native HTML, not JS
- Responsive: sidebar stacks below on mobile via `grid-cols-1 lg:grid-cols-3`

### Empty States

- If no activity at all: show empty state with "No recorded activity yet. Interactions, emails, and meetings will appear here as data is added."
- If a sidebar card would be empty (no projects, no relationships, no relationship score): don't render that card at all
- If no action items: don't render the action items card

## Step 9: Write and Open

Generate a filename slug from the contact name (lowercase, hyphens for spaces):

Write to `${CLAUDE_PLUGIN_ROOT}/output/{contact-slug}.html`

Open with: `open "${CLAUDE_PLUGIN_ROOT}/output/{contact-slug}.html"`

Tell the user: "Entity page for **{contact name}** opened." Then briefly mention what's on it — e.g., "Shows 12 email threads, 4 meetings, and 2 overdue commitments."
