---
description: Session-start pulse check — syncs data if stale, surfaces what needs attention today
allowed-tools: ["Bash", "Read"]
argument-hint: [optional: --silent to suppress output if nothing urgent]
---

# Heartbeat

Run at the start of every session (or any time you want a pulse check). This command does three things:

1. Silently syncs data if stale (>15 min)
2. Surfaces only what actually needs your attention
3. Stays quiet if everything is fine

**Do not summarize what you checked. Only surface what requires action.**

---

## Step 1: Check Sync Freshness

```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" \
  "SELECT key, value FROM soy_meta WHERE key IN ('gmail_last_synced','calendar_last_synced','transcripts_last_scanned','slack_last_synced','asana_last_synced');"
```

For each timestamp, compute minutes since last sync. If any is:
- **> 15 min** → sync Gmail, Calendar, Slack, and Asana silently (see Auto-Sync in CLAUDE.md)
- **> 60 min** → also scan for new transcripts

If `slack_last_synced` or `asana_last_synced` is missing entirely, that integration just isn't connected — skip without comment.

Run sync in background if needed. Do not mention it unless it fails.

---

## Step 2: Check Urgent Nudges

```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" \
  "SELECT tier, nudge_type, entity_name, description, days_value, extra_context
   FROM v_nudge_items
   WHERE tier = 'urgent'
   ORDER BY days_value DESC
   LIMIT 10;"
```

---

## Step 3: Check Overdue Commitments

```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" \
  "SELECT owner_name, description, days_overdue, from_call
   FROM v_commitment_status
   WHERE status = 'open' AND days_overdue > 0
   ORDER BY days_overdue DESC
   LIMIT 5;"
```

---

## Step 4: Check Email Response Queue

```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" \
  "SELECT subject, from_address, from_name, received_at,
          CAST((julianday('now') - julianday(received_at)) * 24 AS INTEGER) AS hours_waiting
   FROM v_email_response_queue
   WHERE hours_waiting > 24
   ORDER BY hours_waiting DESC
   LIMIT 5;"
```

---

## Step 5: Check Today's Calendar

```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" \
  "SELECT title, start_time, end_time
   FROM calendar_events
   WHERE date(start_time) = date('now')
     AND title NOT IN ('Busy','Home','OOO')
   ORDER BY start_time;"
```

---

## Step 6: Present Results

**If nothing is urgent** (no overdue commitments, no email >24h old, no urgent nudges):

> All clear. [X contacts, Y open commitments, next meeting at HH:MM if any today.]

**If there are urgent items**, present a scannable briefing — no more than 10 lines:

```
Heartbeat — [DATE]

URGENT
• [Commitment/nudge] — [who, what, N days overdue]
• [Email waiting reply] — [from, subject, N hours]

TODAY
• HH:MM — [meeting title]
• HH:MM — [meeting title]

NEXT ACTION: [single most important thing to do right now]
```

Group by: Urgent → Today → Nothing (omit empty sections entirely).

**One recommended next action at the end.** That's it.

---

## Dispatch Rule

If the user has >10 urgent items or asks for a full analysis, delegate to a sub-agent:

> "There's a lot in motion. Let me have a closer look — back in a moment."

Then spawn a sub-agent focused only on triage and prioritization. Present its top 5 findings.
