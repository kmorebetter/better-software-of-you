---
description: Generate a Decision Journal view — your decisions over time with outcomes, patterns, and revisit prompts
allowed-tools: ["Bash", "Read", "Write"]
---

# Decision Journal View

Generate a standalone HTML page showing the Decision Journal — all tracked decisions over time with outcomes, patterns, and revisit prompts.

## Step 1: Read the Design System

Read these files first:
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/template-base.html` — HTML skeleton
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/navigation-patterns.md` — nav bar patterns

## Step 2: Gather Data

Query `${CLAUDE_PLUGIN_ROOT}/data/soy.db`. Run all queries in a single `sqlite3` heredoc call for efficiency.

```sql
-- All decisions with linked project/contact
SELECT d.*, p.name as project_name, c.name as contact_name
FROM decisions d
LEFT JOIN projects p ON d.project_id = p.id
LEFT JOIN contacts c ON d.contact_id = c.id
ORDER BY d.decided_at DESC;

-- Stats
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN status = 'decided' THEN 1 ELSE 0 END) as decided,
  SUM(CASE WHEN status = 'validated' THEN 1 ELSE 0 END) as validated,
  SUM(CASE WHEN status = 'regretted' THEN 1 ELSE 0 END) as regretted,
  SUM(CASE WHEN status = 'revisit' THEN 1 ELSE 0 END) as revisit,
  SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
  SUM(CASE WHEN outcome IS NULL AND julianday('now') - julianday(decided_at) > 90 THEN 1 ELSE 0 END) as needs_outcome
FROM decisions;

-- Entity pages for linking
SELECT entity_id, entity_type, filename FROM generated_views WHERE view_type = 'entity_page';

-- Navigation: other generated views
SELECT view_type, entity_name, filename, updated_at
FROM generated_views
ORDER BY updated_at DESC
LIMIT 10;
```

## Step 3: Generate HTML

Generate a self-contained HTML file using the template-base.html skeleton (Tailwind CDN, Lucide CDN, Inter font). Use `max-w-5xl` container.

### Nav Bar

Include a nav bar following `navigation-patterns.md`. Use the Dashboard-style nav pattern with "Dashboard" link on the left, breadcrumb separator, then "Decision Journal" as current page (plain text, not a link). On the right, show pills linking to other generated entity pages (from the `generated_views` query, limit 5 most recent, excluding the current page).

### Header Card

Full-width card: `bg-white rounded-xl shadow-sm border border-zinc-200 p-6`

```
Header card (full width)
├── Left side:
│   ├── Lucide `scale` icon + Title: "Decision Journal" (text-2xl font-bold)
│   └── Subtitle: "X decisions tracked" (text-sm text-zinc-500)
└── Right side: Stat pills
    ├── Total: zinc pill (bg-zinc-100 text-zinc-700)
    ├── Validated: green pill (bg-green-100 text-green-700) — count + "Validated"
    ├── Regretted: red pill (bg-red-100 text-red-700) — count + "Regretted"
    └── Needs Review: amber pill (bg-amber-100 text-amber-700) — needs_outcome count
```

Only show stat pills that have non-zero counts.

### Decision Score Card (full width, show only if there are at least 3 decisions with outcomes)

`bg-white rounded-xl shadow-sm border border-zinc-200 p-6`

- A visual progress bar showing: validated % (green), regretted % (red), pending % (zinc) — use `rounded-full h-3 overflow-hidden flex` with colored segments
- Below the bar: "X% of your tracked decisions had positive outcomes" (if any validated exist)
- Show the raw numbers: "X validated, Y regretted, Z pending outcome"

### Needs Attention Card (show only if `needs_outcome` > 0)

`bg-amber-50 rounded-xl border border-amber-200 p-6`

Header: Lucide `alert-circle` icon + "Worth Revisiting" (text-lg font-semibold text-amber-900)
Subheading: "These decisions are over 90 days old with no recorded outcome" (text-sm text-amber-700)

List each decision needing outcome:
- Title (font-medium text-amber-900)
- Decided date in relative format ("3 months ago")
- Prompt text: "How did this turn out?" (text-sm text-amber-600)
- Action hint: "Run `/decision outcome <title>` to record what happened" (text-xs text-amber-500 font-mono)

### Decision Timeline (full width)

Group decisions by month. Each month gets a header:
- `text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3 mt-6` — format: "FEBRUARY 2026"

Each decision card within a month:

`bg-white rounded-xl shadow-sm border border-zinc-200 p-5 mb-3` with a **left border** indicating status:
- `border-l-4 border-green-500` for validated
- `border-l-4 border-red-500` for regretted
- `border-l-4 border-amber-400` for revisit
- `border-l-4 border-blue-500` for decided (recent, <90 days old)
- `border-l-4 border-zinc-300` for open

Card content layout:

```
┌────────────────────────────────────────────────────────────────────┐
│ ▌ Payment processor: Stripe over Square          Status Badge     │
│ ▌ Decided 3 months ago                                            │
│ ▌                                                                 │
│ ▌ Context: Needed to choose a payment system for the app launch   │
│ ▌ Decision: Went with Stripe                                      │
│ ▌ Options: [Stripe] [Square] [PayPal]                             │
│ ▌ Rationale: Better API docs, Jake recommended it                 │
│ ▌ Project: SaaS Platform  ·  Influenced by: Jake Morrison        │
│ ▌                                                                 │
│ ▌ ┌─ Outcome (bg-green-50 for validated / bg-red-50 for regret) ─┐│
│ ▌ │ Validated ✓ — Integration went smoothly, launched in 2 weeks  ││
│ ▌ │ Recorded: January 15, 2026                                    ││
│ ▌ └──────────────────────────────────────────────────────────────┘│
│ ▌                                                                 │
│ ▌ ┌─ OR if no outcome and >90 days old (bg-amber-50) ───────────┐│
│ ▌ │ ⚠ Worth revisiting — this decision is X days old             ││
│ ▌ └──────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────┘
```

Detail rendering rules:
- **Title**: `text-lg font-semibold text-zinc-900`
- **Status badge** (top right): pill with icon
  - Validated: `bg-green-100 text-green-700` + checkmark
  - Regretted: `bg-red-100 text-red-700` + x-circle
  - Revisit: `bg-amber-100 text-amber-700` + refresh-cw
  - Decided: `bg-blue-100 text-blue-700` + check
  - Open: `bg-zinc-100 text-zinc-600` + circle
- **Date**: relative format ("3 months ago", "2 weeks ago") in `text-sm text-zinc-500`
- **Context**: `text-sm text-zinc-600` — the context field, 1-2 lines max
- **Decision**: `text-sm text-zinc-700 font-medium` — what was chosen
- **Options considered**: pill badges — `bg-zinc-100 text-zinc-600 rounded-full px-2 py-0.5 text-xs inline-block mr-1`
- **Rationale**: `text-sm text-zinc-600 italic` — brief text
- **Linked project/contact**: `text-sm text-zinc-500` — project name linked to project entity page if one exists in `generated_views`; contact name linked to contact entity page if one exists. Use `text-blue-600 hover:text-blue-800 hover:underline` for links.
- **Outcome section** (if outcome recorded):
  - Validated: `bg-green-50 rounded-lg p-3 mt-3` with "Validated" in green + checkmark + outcome text
  - Regretted: `bg-red-50 rounded-lg p-3 mt-3` with "Regretted" in red + x-circle + outcome text
  - Outcome date in `text-xs text-zinc-400`
- **Worth revisiting callout** (if no outcome and >90 days old):
  - `bg-amber-50 rounded-lg p-3 mt-3` with amber alert-circle icon + "Worth revisiting — this decision is X days old"

Only show fields that have values. If context is empty, skip it. If no options_considered, skip the pills. If no linked project/contact, skip that line.

### Footer

```html
<footer class="mt-8 pt-4 border-t border-zinc-100 text-center">
    <p class="text-xs text-zinc-400">Generated by Software of You · [current date and time]</p>
</footer>
```

### Empty State

If there are no decisions at all, show a single centered card:
- Lucide `scale` icon (large, `w-12 h-12 text-zinc-300`)
- "No decisions tracked yet" (text-lg font-medium text-zinc-500)
- "Start your decision journal — just tell me about a choice you've made." (text-sm text-zinc-400)
- "Try: `/decision went with React over Vue for the frontend because...`" (text-xs text-zinc-400 font-mono)

## Step 4: Design Rules (non-negotiable)

- Use the template-base.html structure (Tailwind CDN, Lucide CDN, Inter font)
- Background: `bg-zinc-50`, cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- Status colors: green = validated, red = regretted, amber = revisit or open (>90 days), blue = decided (recent), zinc = open
- Options considered pills: `bg-zinc-100 text-zinc-600 rounded-full px-2 py-0.5 text-xs`
- Outcome sections: `bg-green-50` for validated, `bg-red-50` for regretted
- Month group headers: `text-sm font-medium text-zinc-400 uppercase tracking-wider`
- All data static in HTML — no JavaScript data fetching
- The only JS: Lucide icon initialization (`lucide.createIcons()`)
- Parse `options_considered` as JSON — it's stored as a JSON array in the database

### Contact & Project Name Linking

Anywhere a project or contact name appears, check if an entity page exists for it in the `generated_views` query results. If so, render as a clickable link (`text-blue-600 hover:text-blue-800 hover:underline`). If not, render as plain text.

## Step 5: Write, Register, and Open

Write to `${CLAUDE_PLUGIN_ROOT}/output/decision-journal.html`.

**Register the view:**
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'Decision Journal', 'decision-journal.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Open with: `open "${CLAUDE_PLUGIN_ROOT}/output/decision-journal.html"`

Tell the user: "Decision Journal opened." Then briefly summarize what's shown — e.g., "Shows 12 decisions: 5 validated, 2 regretted, 3 need review. Grouped by month from February 2026 back to October 2025."
