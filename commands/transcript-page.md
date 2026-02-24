---
description: Generate a per-transcript detail page — the full breakdown of a single call
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: <transcript title, contact name, or transcript id>
---

# Transcript Page

Generate a per-transcript detail page for the transcript specified in $ARGUMENTS. This is the call-level equivalent of an entity page — a single page that synthesizes everything captured from one conversation: speaker metrics, call intelligence, commitments, coaching insights, and the full transcript.

**These pages are sub-pages of Conversations** — they don't appear in the sidebar. They're accessed via "View full analysis" links from entity pages and the conversations view.

## Step 1: Read References + Resolve Transcript

Read design references in parallel:
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/template-base.html`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/component-patterns.md`
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/navigation-patterns.md`

At the same time, resolve the transcript. Query `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`:

```sql
-- Match by title, participant name, or ID
SELECT t.id, t.title, t.raw_text, t.summary, t.duration_minutes,
  t.occurred_at, t.source, t.call_intelligence
FROM transcripts t
LEFT JOIN transcript_participants tp ON tp.transcript_id = t.id
LEFT JOIN contacts c ON c.id = tp.contact_id
WHERE t.title LIKE '%$ARGUMENTS%'
   OR t.id = '$ARGUMENTS'
   OR c.name LIKE '%$ARGUMENTS%'
GROUP BY t.id
ORDER BY t.occurred_at DESC
LIMIT 5;
```

If multiple matches, pick the most recent or ask the user.

## Step 2: Gather Data

Run all queries in a single `sqlite3` heredoc call for efficiency. Use the resolved transcript ID wherever you see `?`.

```sql
-- Transcript details (already resolved above, but included for completeness)
SELECT id, title, raw_text, summary, duration_minutes, occurred_at, source, call_intelligence
FROM transcripts WHERE id = ?;

-- Participants with contact info
SELECT tp.is_user, tp.speaker_label,
  c.id as contact_id, c.name, c.role, c.company, c.email
FROM transcript_participants tp
LEFT JOIN contacts c ON c.id = tp.contact_id
WHERE tp.transcript_id = ?;

-- Per-speaker conversation metrics (join to get speaker_label from participants)
SELECT tp.speaker_label, cm.contact_id, cm.talk_ratio, cm.word_count,
  cm.question_count, cm.interruption_count, cm.longest_monologue_seconds
FROM conversation_metrics cm
LEFT JOIN transcript_participants tp
  ON tp.transcript_id = cm.transcript_id
  AND (tp.contact_id = cm.contact_id OR (tp.contact_id IS NULL AND cm.contact_id IS NULL))
WHERE cm.transcript_id = ?;

-- Commitments from this call
SELECT id, description, deadline_date, status, is_user_commitment,
  owner_contact_id, completed_at
FROM commitments
WHERE transcript_id = ?
ORDER BY is_user_commitment DESC, deadline_date ASC NULLS LAST;

-- Communication insights for this call (with evidence data)
SELECT insight_type, content, sentiment, data_points, contact_id
FROM communication_insights
WHERE transcript_id = ?
ORDER BY created_at DESC;

-- Contact entity pages (for participant linking)
SELECT entity_id, entity_name, filename FROM generated_views
WHERE view_type = 'entity_page' AND entity_type = 'contact';

-- Navigation data (for sidebar)
SELECT view_type, entity_type, entity_id, entity_name, filename
FROM generated_views ORDER BY updated_at DESC;
```

## Step 3: Process Data

1. **Participants**: Match speaker labels to contacts. For each participant with a contact_id, check if an entity page exists — if so, make their name a link.

2. **Speaker metrics**: Build per-speaker stat blocks. Calculate talk ratio bars and dominance ratios (`talk_ratio / (1.0 / participant_count)`). Use available data from conversation_metrics. If no metrics exist, note that metrics were not captured for this call. For interruption count: display the stored value. If 0, show "0 (format doesn't support detection)" rather than implying no interruptions occurred.

3. **Call intelligence**: Parse the `call_intelligence` JSON (if present). Extract:
   - **Pain points** — each with severity (high/medium/low) and description
   - **Concerns** — each with addressed (true/false) flag
   - **Tech stack** — tool names with categories
   - **Org intel** — organizational insights discovered

4. **Commitments**: Split into "Your commitments" (`is_user_commitment = 1`) and "Their commitments" (`is_user_commitment = 0`). Calculate urgency: overdue (red), due within 3 days (amber), open (zinc).

5. **Coaching insights**: Group by `insight_type`:
   - `relationship_pulse` -> heart-pulse icon, pink
   - `coach_note` -> lightbulb icon, amber
   - `pattern_alert` -> alert-triangle icon, red

## Step 4: Generate HTML

Generate a self-contained HTML file. Follow the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font).

### Page Structure

```
Sidebar (from navigation-patterns.md — "Conversations" active in Intelligence section)

Header card (full width)
├── Mic icon + title, date, duration badge
├── Participant avatars (initials circles, linked to entity pages)
├── Source badge (Gemini / Paste / Upload)
└── Stat pills: total words, talk ratio summary, questions asked, commitment count

Two-column layout: grid grid-cols-1 lg:grid-cols-3 gap-6

Left column (lg:col-span-2):

  Speaker Metrics card
  ├── Card header: bar-chart-3 icon + "Speaker Metrics"
  ├── Per-speaker rows:
  │   ├── Speaker name (or "You") + role/company if known
  │   ├── Talk ratio bar (visual percentage bar, colored per speaker)
  │   ├── Dominance ratio badge: "1.24x" (green if 0.6-1.5, amber if 1.5-2.0 or 0.4-0.6, red if >2.0 or <0.4)
  │   │   └── Computed as: talk_ratio / (1.0 / participant_count). Not stored — always calculated at display time.
  │   ├── Stats row: word count, question count, interruption count
  │   └── Longest monologue (seconds)
  └── Overall talk ratio + dominance summary

  Call Intelligence card (if call_intelligence JSON exists)
  ├── Card header: brain icon + "Call Intelligence"
  ├── Pain Points section
  │   ├── Each: severity dot (red=high, amber=medium, zinc=low) + description
  │   └── Sorted by severity (high first)
  ├── Concerns section
  │   ├── Each: check-circle (green) if addressed, alert-circle (amber) if not + description
  │   └── Unaddressed concerns highlighted with bg-amber-50
  ├── Tech Stack section
  │   └── Pills: tool name + category label (blue-50/blue-600)
  └── Org Intel section (if present)
      └── Bullet points of organizational insights

  Summary card
  ├── Card header: file-text icon + "Summary"
  └── AI-generated narrative summary (prose paragraph)

  Commitments card
  ├── Card header: circle-dot icon + "Commitments" + count badge
  ├── Section: "Your commitments" — things you said you'd do
  │   ├── Each: description, deadline (relative), status badge
  │   ├── Overdue: bg-red-50 border-l-4 border-red-400
  │   ├── Due within 3 days: bg-amber-50 border-l-4 border-amber-400
  │   └── Open: border-l-4 border-zinc-200
  ├── Section: "Their commitments" — things others committed to
  │   └── Same format, grouped by owner
  └── Empty state: "No commitments extracted from this call."

  Raw Transcript card (collapsible)
  ├── <details> element, closed by default
  ├── <summary>: "Full Transcript" + word count badge
  └── Transcript text with speaker labels
      ├── Speaker labels bold, colored per speaker
      └── Monospace or prose formatting, whichever reads better

Right column (lg:col-span-1):

  Coaching Corner card
  ├── Card header: lightbulb icon + "Coaching Corner"
  ├── Each insight:
  │   ├── Icon by type (heart-pulse / lightbulb / alert-triangle)
  │   ├── Content text
  │   ├── Evidence line (if data_points JSON exists, text-xs text-zinc-500 italic):
  │   │   ├── coach_note: "Triggered by {trigger}: {value} (threshold: {threshold})"
  │   │   ├── relationship_pulse: "{depth}, {trajectory} — {meetings_90d} meetings"
  │   │   └── pattern_alert: "Pattern: {pattern} — values: {values}"
  │   ├── Sentiment dot (green/amber/red)
  │   └── Contact context if relevant
  └── Empty state: "No coaching insights for this call."

  Participants card
  ├── Card header: users icon + "Participants"
  ├── Each participant:
  │   ├── Avatar (initials circle)
  │   ├── Name (linked to entity page if exists)
  │   ├── Role + Company
  │   └── "You" label for user participant
  └── Contact linking: check entity pages query

  Quick Stats card
  ├── Card header: hash icon + "Quick Stats"
  └── Stat grid (2x2):
      ├── Duration (minutes or "—")
      ├── Date (human-readable)
      ├── Source (Gemini / Paste / Upload)
      └── Total speakers

Footer
├── "Generated by Software of You · [date] at [time]"
```

### Design Rules

- Use the template-base.html skeleton (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200 p-5`
- Speaker colors: Use a rotating palette for talk ratio bars:
  - Speaker 1 (You): emerald-500
  - Speaker 2: blue-500
  - Speaker 3: violet-500
  - Speaker 4+: amber-500, pink-500
- Talk ratio bars: `h-3 rounded-full` with percentage width
- Pain point severity: `bg-red-500` (high), `bg-amber-500` (medium), `bg-zinc-400` (low) as `w-2 h-2 rounded-full` dots
- Concerns: `text-green-600` check-circle if addressed, `text-amber-500` alert-circle if not
- Commitment urgency: same color scheme as conversations-view (red/amber/zinc border-l-4)
- Coaching insight icons: pink for relationship_pulse, amber for coach_note, red for pattern_alert
- Contact name linking: check entity pages query — if a page exists for a contact, render their name as `<a href="contact-{slug}.html" class="font-medium text-blue-600 hover:text-blue-800 hover:underline">Name</a>`. Otherwise plain text.
- All data static in HTML — no JavaScript data fetching
- The only JS: Lucide icon initialization (`lucide.createIcons()`) + sidebar JS
- Responsive: sidebar stacks below on mobile via `grid-cols-1 lg:grid-cols-3`
- Collapsed sections use native `<details>` for zero-JS collapsing

### Empty States

Show empty states for sections with no data — never hide the card:

- No call intelligence: "No call intelligence data for this transcript." with `brain` icon
- No commitments: "No commitments extracted from this call." with `circle-dot` icon
- No coaching insights: "No coaching insights for this call." with `lightbulb` icon
- No conversation metrics: "Metrics were not captured for this call." with `bar-chart-3` icon

## Step 5: Write, Register, and Open

Generate a filename slug from the transcript title (lowercase, hyphens for spaces, strip special chars). If multiple transcripts would produce the same slug, append the transcript ID: `transcript-{slug}-{id}.html`.

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/transcript-{slug}.html`

**Register the view:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('transcript_page', 'transcript', ?, ?, 'transcript-{slug}.html')
ON CONFLICT(filename) DO UPDATE SET
  entity_name = excluded.entity_name,
  updated_at = datetime('now');
```

Open with: `open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/transcript-{slug}.html"`

Tell the user: "Transcript page for **{title}** opened." Then briefly summarize what's on it — e.g., "Shows speaker metrics (you 62%, them 38%), 3 pain points, 5 commitments, and coaching insights on question technique."
