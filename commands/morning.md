---
description: Morning routine — fresh pull of Gmail/Calendar/transcripts, regenerate dashboards, then a today briefing
allowed-tools: ["Bash", "Read", "Write", "Glob"]
argument-hint: "[full] — force a complete dashboard rebuild instead of incremental"
---

# Morning

Your once-a-day catch-up. Force a **fresh pull** of all Google data, regenerate any dashboards
that need it, then deliver a concise briefing of what actually matters today.

This command sequences pieces that already exist — it does NOT reimplement them. It adds the four
things a plain `/build-all` doesn't: a *forced* full pull (no 15-minute staleness skip), the
`soy_meta` freshness stamping the sync script omits, a transcript backlog check, and a spoken briefing.

## Step 0: Parse Arguments

Check `$ARGUMENTS` for `full`:
- Contains "full" → `FULL_REBUILD = true` (pass `force` to build-all in Step 5)
- Otherwise → `FULL_REBUILD = false` (incremental dashboard build)

## Step 1: Bootstrap

Idempotent — ensures the DB exists and migrations are current:
```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/bootstrap.sh"
```

## Step 2: Fresh Pull (forced)

Run the canonical full-sync script — Gmail + Calendar + transcripts for every active Google
account. Unlike auto-sync, run this **unconditionally** (it's the morning pull):
```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/scheduled_sync.sh"
```
It prints a JSON result and logs to `~/.local/share/software-of-you/logs/sync.log`. Parse the JSON
for per-account, per-source counts (gmail / calendar / transcripts) and note how many new items
landed.

**If the sync errors** (missing MCP venv, expired token, network failure): report it plainly,
then continue with cached data — do NOT abort the dashboards or briefing.

## Step 3: Stamp Freshness

`scheduled_sync.sh` updates `google_accounts.last_synced_at` but NOT the `soy_meta` keys that
auto-sync reads. Stamp them so downstream views/commands see fresh data (idempotent):
```sql
INSERT OR REPLACE INTO soy_meta (key,value,updated_at) VALUES ('gmail_last_synced', datetime('now'), datetime('now'));
INSERT OR REPLACE INTO soy_meta (key,value,updated_at) VALUES ('calendar_last_synced', datetime('now'), datetime('now'));
INSERT OR REPLACE INTO soy_meta (key,value,updated_at) VALUES ('transcripts_last_scanned', datetime('now'), datetime('now'));
```

## Step 4: Transcript Backlog Check

The morning pull fetches raw transcripts but does NOT analyze them. Check the backlog:
```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/sync_transcripts.py" pending
```
If the JSON `pending` count is > 0, surface it in the briefing: "N unanalyzed meeting transcripts —
run `/sync-transcripts analyze-all` to process them." Do NOT auto-analyze (each is a full
interactive pass).

## Step 5: Regenerate Dashboards

Read `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/commands/build-all.md` and follow it completely:
- Incremental by default — only rebuilds pages whose data changed, and creates pages for any
  **new** contacts/projects (that's "the dashboards required").
- Always rebuilds `dashboard.html`, `nudges.html`, `timeline.html`, `weekly-review.html`, `search.html`.
- If `FULL_REBUILD = true`, run build-all in its `force` mode (rebuild everything).

Build-all's own Step 1 auto-sync is now a no-op (we just synced and stamped fresh timestamps).

## Step 6: Open the Dashboard

```bash
open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/dashboard.html"
```

## Step 7: Morning Briefing

Deliver a tight, conversational briefing. **Every number is narrated from a computed view — never
invent or estimate.** If a section has no rows, say so briefly or skip it (no padding).

Pull from these views (use the views directly — don't re-derive):

```sql
-- Today's meetings + prep
SELECT title, start_time, time_context, minutes_until, duration_minutes, project_name
FROM v_meeting_prep
WHERE date(start_time) = date('now') OR time_context IN ('now','imminent')
ORDER BY start_time;

-- Attention radar (counts + top items)
SELECT tier, COUNT(*) FROM v_nudge_summary;            -- header counts
SELECT tier, title, context FROM v_nudge_items ORDER BY tier LIMIT 8;

-- Overdue commitments
SELECT owner_name, description, days_overdue
FROM v_commitment_status WHERE urgency = 'overdue' ORDER BY days_overdue DESC LIMIT 8;

-- Emails needing a reply
SELECT from_name, subject, days_old
FROM v_email_response_queue WHERE urgency IN ('overdue','aging') ORDER BY days_old DESC LIMIT 8;

-- At-risk relationships (gone quiet)
SELECT name, days_silent
FROM v_contact_health WHERE days_silent IS NOT NULL ORDER BY days_silent DESC LIMIT 5;
```

Structure the briefing as (omit any empty section):
1. **What changed** — one line on the fresh pull (e.g. "Pulled 12 new emails, 3 calendar updates").
2. **Today** — meetings with prep context.
3. **Needs you** — urgent nudges + overdue commitments + emails awaiting reply.
4. **Going quiet** — the relationships silent longest.

Close with the **single most useful next action** (per CLAUDE.md — one suggestion, not a list),
e.g. "Want me to draft replies to the 2 emails that have been waiting longest?"

## Notes

- This is meant to be run once at the start of the day; it's safe to run again (everything is idempotent).
- For just a data pull without rebuilding views, use `/auto-sync run`. For just dashboards, use `/build-all`.
