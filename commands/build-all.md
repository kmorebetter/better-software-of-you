---
description: Rebuild all HTML views — deterministic renderer for structure, Claude only for narrative synthesis
allowed-tools: ["Bash", "Read", "Write", "Glob"]
---

# Build All Views

Regenerate every HTML view. The whole site is now built by a **deterministic renderer**
(`scripts/render.py`) in ~1–2 seconds — dashboard, all module views, and every contact entity page,
straight from the computed views. Claude is used **only** where genuine synthesis is required:
per-contact relationship narratives (and only when that contact's data changed) and transcript pages.

This replaces the old token-by-token generation. Do NOT hand-write structural HTML — call the renderer.

## Step 0: Parse Arguments

`$ARGUMENTS` may contain `force`. The deterministic renderer always rebuilds every structural page
(it's cheap), so `force` only affects **narratives**: with `force`, refresh every data-rich contact's
narrative; without it, refresh only the ones the renderer reports as stale.

## Step 1: Auto-Sync External Data

Ensure data is fresh first. Follow the auto-sync procedure in CLAUDE.md — check `gmail_last_synced` /
`calendar_last_synced` in `soy_meta` and sync if stale (>15 min); check `transcripts_last_scanned`
and scan if >1 hour stale. Do this silently.

## Step 2: Deterministic Render (structure — no Claude)

Run the renderer under the MCP venv Python (it has jinja2):

```bash
"${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/.venv/bin/python3" \
  "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/scripts/render.py" all
```

This builds `dashboard.html`, the module views (`contacts`, `nudges`, `week-view`, `email-hub`,
`timeline`, `conversations`, `weekly-review`, `network-map`, `search`), and a `contact-<slug>.html`
for every active contact — each with the stored narrative slotted in — and registers them all in
`generated_views`. It prints a JSON summary (`built`, `count`, `ms`). Report those numbers.

## Step 3: Narrative Refresh (Claude — only where judgment changed)

Ask the renderer which contacts need a narrative rewrite (data-rich contacts whose underlying data
changed since their narrative was written, or who have none):

```bash
"${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/.venv/bin/python3" \
  "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/scripts/render.py" stale-narratives
```

For `force`, treat ALL data-rich contacts as stale.

For EACH stale contact, produce the narrative sections (the ONLY model-authored parts of an entity
page) following the synthesis guidance in `commands/entity-page.md` and
`skills/conversation-intelligence/`:
- `relationship_context` — grounded prose; cite specifics (emails, calls, commitments). No invention.
- `company_intel` — what's known about their company from the data. NULL/omit if nothing is known.
- `discovery_questions` — a JSON array of specific open questions worth asking them next.
- `next_action` — one concrete, specific next step.

Then persist it (the renderer computes the freshness fingerprint and re-renders that page):

```bash
echo '{"contact_id": <id>, "relationship_context": "...", "company_intel": "...",
       "discovery_questions": ["...","..."], "next_action": "..."}' \
| "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/.venv/bin/python3" \
    "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/scripts/render.py" save-narrative
```

Ground every claim in data. If a contact has too little data to characterize, write a short honest
narrative ("Limited data — 2 emails, no calls yet") rather than inventing one.

## Step 4: Transcript Pages (Claude — one per analyzed transcript, if missing/stale)

The renderer does not build transcript detail pages. For each analyzed transcript
(`summary IS NOT NULL OR call_intelligence IS NOT NULL`) that has no current `transcript-*.html` in
`generated_views`, follow `commands/transcript-page.md` completely. Generate these before/independent
of the dashboard; they're already linked by filename.

## Step 5: Project Pages (Claude — if any active/planning projects)

If `SELECT COUNT(*) FROM projects WHERE status IN ('active','planning')` > 0, follow
`commands/project-page.md` for each. (None today → skip.)

## Step 6: Open + Report

```bash
open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/dashboard.html"
```

Report concisely:
```
Rebuilt the site in <ms> ms (deterministic): dashboard + 9 module views + N entity pages.
Refreshed narratives for: [names]  (or "none — all current")
Transcript pages built: [titles]  (or "none new")
```

## Important

- **Structure is deterministic** — never hand-write dashboard/module/entity HTML; the renderer owns it.
- **Claude only writes narratives + transcript/project pages**, and narratives only when stale — this
  is where tokens are spent, nowhere else.
- **Never fabricate.** Every narrative claim traces to data; NULL over fiction (renderer shows "—").
- The renderer freezes each contact's `slug`, so renames never orphan a page or its inbound links.
