---
description: Generate a Conversations view — transcripts, commitments, coaching insights, and relationship patterns
allowed-tools: ["Bash", "Read", "Write"]
---

# Conversations View

Generate a standalone HTML page for the Conversation Intelligence module. This is the central hub for all conversation data — transcripts, commitments, coaching insights, and relationship health patterns.

## Step 1: Read the Design System

Read these files first:
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/template-base.html`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/navigation-patterns.md`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/activity-feed-patterns.md`

## Step 2: Gather Data

Query `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`. Run all queries in a single `sqlite3` heredoc call for efficiency.

```sql
-- All transcripts with participants and call intelligence
SELECT t.id, t.title, t.summary, t.duration_minutes, t.occurred_at, t.source,
  t.call_intelligence,
  GROUP_CONCAT(DISTINCT CASE WHEN tp.is_user = 0 THEN c.name END) as participant_names,
  GROUP_CONCAT(DISTINCT CASE WHEN tp.is_user = 0 THEN c.id END) as participant_ids
FROM transcripts t
LEFT JOIN transcript_participants tp ON tp.transcript_id = t.id
LEFT JOIN contacts c ON c.id = tp.contact_id
GROUP BY t.id
ORDER BY t.occurred_at DESC
LIMIT 30;

-- All open commitments
SELECT com.id, com.description, com.deadline_date, com.status, com.is_user_commitment,
  c.name as owner_name, c.id as owner_id,
  t.title as from_call, t.occurred_at as call_date
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
LEFT JOIN transcripts t ON t.id = com.transcript_id
WHERE com.status IN ('open', 'overdue')
ORDER BY com.deadline_date ASC NULLS LAST;

-- Completed commitments (last 30 days)
SELECT com.id, com.description, com.is_user_commitment,
  c.name as owner_name, com.completed_at
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
WHERE com.status = 'completed' AND com.completed_at > datetime('now', '-30 days')
ORDER BY com.completed_at DESC;

-- Commitment stats
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
  SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue_count,
  SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
  SUM(CASE WHEN is_user_commitment = 1 AND status IN ('open','overdue') THEN 1 ELSE 0 END) as your_open
FROM commitments;

-- Latest coaching insights
SELECT ci.insight_type, ci.content, ci.sentiment, ci.created_at,
  c.name as contact_name, t.title as from_call
FROM communication_insights ci
LEFT JOIN contacts c ON c.id = ci.contact_id
LEFT JOIN transcripts t ON t.id = ci.transcript_id
ORDER BY ci.created_at DESC
LIMIT 15;

-- Relationship scores (latest per contact)
SELECT rs.contact_id, c.name, rs.relationship_depth, rs.trajectory,
  rs.meeting_frequency, rs.talk_ratio_avg, rs.commitment_follow_through
FROM relationship_scores rs
JOIN contacts c ON c.id = rs.contact_id
INNER JOIN (
  SELECT contact_id, MAX(score_date) as latest FROM relationship_scores GROUP BY contact_id
) l ON rs.contact_id = l.contact_id AND rs.score_date = l.latest
ORDER BY rs.trajectory DESC;

-- Entity pages for linking
SELECT entity_id, filename FROM generated_views WHERE entity_type = 'contact';

-- Transcript detail pages (for "View full analysis" links)
SELECT entity_id, filename FROM generated_views
WHERE view_type = 'transcript_page' AND entity_type = 'transcript';
```

Also query for navigation:
```sql
SELECT view_type, entity_name, filename, updated_at
FROM generated_views
ORDER BY updated_at DESC
LIMIT 10;
```

## Step 3: Prepare Data

Process the query results:

1. **Transcripts**: Parse participant names/IDs. For each participant, check if an entity page exists — if so, make the name a link.
2. **Commitments**: Split into "Your commitments" (`is_user_commitment = 1`) and "Their commitments" (`is_user_commitment = 0`). Group "Their commitments" by `owner_name`. Calculate days overdue (`deadline_date` vs today) or days until due.
3. **Coaching insights**: Map `insight_type` to Lucide icons: `relationship_pulse` -> `heart-pulse`, `coach_note` -> `lightbulb`, `pattern_alert` -> `alert-triangle`.
4. **Relationship scores**: Map `trajectory` to display: `strengthening` -> green up arrow, `stable` -> zinc right arrow, `cooling` -> amber down-right arrow, `at_risk` -> red down arrow. Map `relationship_depth` to badge colors.
5. **Commitment stats**: Use for header stat pills.
6. **Call intelligence badges**: For each transcript, if `call_intelligence` JSON exists, parse it and prepare inline badges:
   - Pain point count → `"X pain points"` badge (red-50/red-600 if any severity=high, else amber-50/amber-600)
   - Concern count → `"X concerns"` badge (amber-50/amber-600 if any unaddressed, else zinc-100/zinc-600)
   - Tech stack pills → show up to 3 tool names as compact pills (blue-50/blue-600), "+N more" if additional

## Step 4: Generate HTML

Generate a self-contained HTML file. Follow the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font).

### Page Structure

```
Sidebar (from navigation-patterns.md — Conversations active in the Intelligence section)

Header card (full width)
├── Title: "Conversations"
├── Subtitle: "X transcripts, Y open commitments"
└── Stat pills (right side):
    ├── Transcripts count (with mic icon)
    ├── Your open commitments (with circle-dot icon)
    ├── Their open commitments (with users icon)
    └── Overdue count (with alert-circle icon, red if > 0)

Two-column layout: grid grid-cols-1 lg:grid-cols-3 gap-6

Left column (lg:col-span-2):

  Commitment Tracker card
  ├── Card header: circle-dot icon + "Commitment Tracker"
  ├── Section: "Your commitments" — things you said you'd do
  │   ├── Each commitment row:
  │   │   ├── Description text
  │   │   ├── "from [call title]" link context
  │   │   ├── Deadline date (relative: "due in 3 days", "due tomorrow")
  │   │   └── Status badge
  │   ├── Overdue items: bg-red-50 border-l-4 border-red-400, days overdue in red
  │   ├── Due within 3 days: bg-amber-50 border-l-4 border-amber-400
  │   └── Open (not urgent): border-l-4 border-zinc-200
  ├── Section: "Their commitments" — things others committed to
  │   ├── Grouped by contact name (subheadings)
  │   └── Same format as your commitments
  └── Recently completed (collapsed <details>, last 30 days, dimmed text)
      └── Each: description + who completed + when (relative date)

  Transcript Timeline card
  ├── Card header: mic icon + "Transcript Timeline"
  ├── Transcripts listed chronologically (newest first)
  ├── Each transcript entry:
  │   ├── Title (linked to transcript detail page if it exists in generated_views, otherwise bold text) + date (relative) + duration badge ("32 min")
  │   ├── Participants (linked to entity pages if they exist)
  │   ├── Call intelligence badges (if call_intelligence JSON exists):
  │   │   ├── Pain point count badge (red/amber pill)
  │   │   ├── Concern count badge (amber/zinc pill)
  │   │   └── Tech stack pills (up to 3, blue pills, "+N more")
  │   ├── Summary text (2-3 sentences, line-clamp-3)
  │   ├── Commitments from this call (inline pills: amber for open, red for overdue, green for completed)
  │   └── "View full analysis →" link (if transcript detail page exists in generated_views)
  └── Empty state: "No conversations imported yet. Use /import-call to get started." with mic-off icon

Right column:

  Coaching Corner card
  ├── Card header: lightbulb icon + "Coaching Corner"
  ├── Each insight:
  │   ├── Icon by type:
  │   │   ├── relationship_pulse → heart-pulse (pink-50/pink-600)
  │   │   ├── coach_note → lightbulb (amber-50/amber-600)
  │   │   └── pattern_alert → alert-triangle (red-50/red-600)
  │   ├── Content text (text-sm)
  │   ├── Sentiment indicator dot:
  │   │   ├── positive → bg-green-400 (green dot)
  │   │   ├── neutral → bg-amber-400 (amber dot)
  │   │   └── needs_attention → bg-red-400 (red dot)
  │   └── Source line: "From call with [contact name]" (text-xs text-zinc-400)
  └── Empty state: "No coaching insights yet. Import a call transcript to get started."

  Relationship Health card
  ├── Card header: heart-pulse icon + "Relationship Health"
  ├── Each contact with a relationship score:
  │   ├── Contact name (linked to entity page if exists)
  │   ├── Depth badge (rounded-full pill):
  │   │   ├── transactional → bg-zinc-100 text-zinc-600
  │   │   ├── professional → bg-blue-50 text-blue-700
  │   │   ├── collaborative → bg-purple-50 text-purple-700
  │   │   └── trusted → bg-green-50 text-green-700
  │   ├── Trajectory indicator:
  │   │   ├── strengthening → trending-up icon, text-green-600
  │   │   ├── stable → minus icon, text-zinc-400
  │   │   ├── cooling → trending-down icon, text-amber-500
  │   │   └── at_risk → alert-triangle icon, text-red-500
  │   ├── Follow-through percentage (if available)
  │   └── Meeting frequency (text-xs)
  └── Empty state: "No relationship data yet. Scores build as you import conversations."

Footer
├── "Generated by Software of You · [date] at [time]"
```

### Design Rules (non-negotiable)

- Use the template-base.html skeleton (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200 p-5` (or `p-6`)
- Overdue commitments: `bg-red-50 border-l-4 border-red-400`
- Due soon (within 3 days): `bg-amber-50 border-l-4 border-amber-400`
- Open commitments (not urgent): `border-l-4 border-zinc-200`
- Coaching insight sentiment: inline dot (`w-2 h-2 rounded-full`) — green=positive, amber=neutral, red=needs_attention
- Relationship trajectory: color-coded Lucide icons with matching text color
- Relationship depth: colored pill badges
- Contact name linking: check entity pages query — if a page exists for a contact, render their name as `<a href="contact-{slug}.html" class="font-medium text-blue-600 hover:text-blue-800 hover:underline">Name</a>`. Otherwise plain text.
- Transcript title linking: check transcript detail pages query — if a detail page exists for a transcript, wrap the title in `<a href="transcript-{slug}.html" class="font-medium text-blue-600 hover:text-blue-800 hover:underline">Title</a>`. Otherwise render as bold text. If a detail page exists, also add after the transcript entry:
  ```html
  <a href="transcript-{slug}.html" class="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 hover:underline mt-1">
    View full analysis <i data-lucide="arrow-right" class="w-3 h-3"></i>
  </a>
  ```
  Only render these links if the transcript's detail page exists in `generated_views`.
- All data static in HTML — no JavaScript data fetching
- The only JS: Lucide icon initialization (`lucide.createIcons()`)
- Responsive: sidebar stacks below on mobile via `grid-cols-1 lg:grid-cols-3`
- Collapsed sections use native `<details>` for zero-JS collapsing

### Empty States

If no data exists for a section, show the empty state — never hide the card. Empty states tell the user the feature is available.

- No transcripts: "No conversations imported yet. Use `/import-call` to get started." with `mic-off` icon
- No commitments: "No commitments tracked yet. They'll appear here after importing call transcripts." with `circle-dot` icon
- No coaching insights: "No coaching insights yet. Import a call transcript to get started." with `lightbulb` icon
- No relationship scores: "No relationship data yet. Scores build as you import conversations." with `heart-pulse` icon

## Step 5: Write, Register, and Open

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/conversations.html`

**Register the view:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Conversations', 'conversations.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Open with: `open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/conversations.html"`

Tell the user: "Conversations view opened." Then briefly summarize what's on it — e.g., "Shows 5 transcripts, 3 open commitments (2 yours), and relationship health for 4 contacts."
