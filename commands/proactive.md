---
description: Proactive intelligence loop — run via /loop 15m /proactive
allowed-tools: ["Bash", "Read", "Write"]
---

# Proactive Intelligence Loop

Time-aware proactive surfacing. Designed to run via `/loop 15m /proactive`. Most invocations will be silent — only surface information when it's timely and hasn't been shown before.

## Step 1: Get Current Context

```sql
-- Current local hour and today's local date
SELECT
    CAST(strftime('%H', 'now', 'localtime') AS INTEGER) AS hour,
    date('now', 'localtime') AS today;

-- Already-sent briefings today
SELECT briefing_type, briefing_key FROM proactive_briefings
WHERE created_at > datetime('now', '-24 hours');

-- Imminent meetings (within 30 min)
SELECT * FROM v_meeting_prep WHERE minutes_until BETWEEN 0 AND 30;
```

All time comparisons MUST use the `'localtime'` modifier to respect the user's timezone.

## Step 2: Route to Appropriate Briefing

### Morning (6am–9am, not yet briefed today)

**Skip if:** `SELECT 1 FROM proactive_briefings WHERE briefing_type = 'morning' AND briefing_key = date('now', 'localtime')`

**Query:**
- `SELECT * FROM v_nudge_summary` — counts by tier
- `SELECT * FROM v_nudge_items WHERE tier = 'urgent' ORDER BY days_value DESC LIMIT 3`
- `SELECT * FROM v_meeting_prep WHERE time_context IN ('today', 'imminent')`
- `SELECT * FROM v_email_response_queue WHERE urgency = 'overdue' LIMIT 3`
- `SELECT COUNT(*) FROM inbox WHERE routed_to IS NULL` — if inbox module installed

**Present:**
"Good morning. You have [X] urgent items, [Y] meetings today.
Top priority: [most urgent nudge]. First meeting: [next meeting] in [time]."
If unrouted inbox items: "Also, [N] captures sitting in your inbox."

**Log:**
```sql
INSERT OR IGNORE INTO proactive_briefings (briefing_type, briefing_key, summary, created_at)
VALUES ('morning', date('now', 'localtime'), '<brief summary>', datetime('now'));
```

### Pre-Meeting (meeting within 30 minutes, any time of day)

Triggers regardless of time of day. **Skip if:** already briefed for this event's `google_event_id`.

**Query:**
- `v_meeting_prep WHERE minutes_until BETWEEN 0 AND 30`
- For each imminent meeting's attendees, check `v_contact_health` for matched contacts
- `v_commitment_status WHERE owner_contact_id IN (attendee_ids) AND status IN ('open','overdue')`

**Present:**
"Meeting with [name] in [X] minutes.
Context: [relationship depth/trajectory]. Last interaction: [days ago].
Open items: [commitments between you].
[If declining trajectory: 'Heads up — this relationship has been cooling.']"

**Log:**
```sql
INSERT OR IGNORE INTO proactive_briefings (briefing_type, briefing_key, summary, created_at)
VALUES ('pre_meeting', '<google_event_id>', '<brief summary>', datetime('now'));
```

### Midday (11am–1pm, not yet briefed today)

**Skip if:** already briefed for midday today.

**Query:**
- `v_nudge_items WHERE tier = 'urgent'` — compare against morning briefing to find NEW items
- `SELECT COUNT(*) FROM inbox WHERE routed_to IS NULL`
- `v_email_response_queue WHERE urgency IN ('overdue', 'aging') LIMIT 3`

**Present:** Brief status check. Only surface NEW urgent items since morning. If nothing new: **say nothing** (no "all clear" spam).

**Log only if something was surfaced.**

### Evening (5pm–7pm, not yet briefed today)

**Skip if:** already briefed for evening today.

**Query:**
- `SELECT action, COUNT(*) FROM activity_log WHERE created_at > date('now', 'localtime', 'start of day') GROUP BY action`
- `v_nudge_items WHERE tier = 'urgent'` — remaining unresolved

**Present:**
"Today you [logged X interactions, completed Y tasks, captured Z notes].
Still open: [remaining urgent items]. [If 0 urgent: 'Clean slate for tomorrow.']"

**Log:**
```sql
INSERT OR IGNORE INTO proactive_briefings (briefing_type, briefing_key, summary, created_at)
VALUES ('evening', date('now', 'localtime'), '<brief summary>', datetime('now'));
```

### Default (any other time)

Only surface if:
- A meeting is within 30 minutes (pre-meeting briefing)
- A new urgent nudge appeared since last briefing

Otherwise: **do nothing. Don't spam.** Silent exit is the expected outcome for most invocations.

## Edge Cases

- **No Google calendar connected:** Skip pre-meeting and meeting-related morning items. Still show nudges/email.
- **No data at all (new user):** Do nothing. Don't surface empty briefings.
- **User runs `/proactive` manually:** Works fine — same logic, just triggered manually instead of via `/loop`.
- **Timezone changes (travel):** `'localtime'` follows system clock. Briefings may shift — acceptable for v1.
