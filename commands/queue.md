---
description: Show everything pending, prioritized — your visible agenda across commitments, nudges, emails, and in-flight jobs
allowed-tools: ["Bash"]
argument-hint: [optional: urgent | soon | all | in-flight]
---

# Queue

Show the full picture of what's pending, organized by priority tier. Unlike `/nudges` (which is a conversational briefing), this is your raw agenda — everything that's waiting, in one place.

Filter via `$ARGUMENTS`:
- `urgent` → urgent tier only
- `soon` → soon + urgent
- `in-flight` → active pipeline jobs only
- (no argument) → all tiers

---

## Step 1: Nudge Items by Tier

```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" <<'SQL'
SELECT
  tier,
  nudge_type,
  entity_name,
  description,
  COALESCE(days_value, 0) AS days_value,
  extra_context
FROM v_nudge_items
ORDER BY
  CASE tier WHEN 'urgent' THEN 1 WHEN 'soon' THEN 2 ELSE 3 END,
  days_value DESC;
SQL
```

---

## Step 2: Open Commitments

```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" <<'SQL'
SELECT
  owner_name,
  description,
  COALESCE(days_overdue, 0) AS days_overdue,
  urgency,
  from_call
FROM v_commitment_status
WHERE status = 'open'
ORDER BY days_overdue DESC
LIMIT 20;
SQL
```

---

## Step 3: Email Response Queue

```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" <<'SQL'
SELECT
  subject,
  from_name,
  from_address,
  received_at,
  CAST((julianday('now') - julianday(received_at)) * 24 AS INTEGER) AS hours_waiting
FROM v_email_response_queue
ORDER BY hours_waiting DESC
LIMIT 10;
SQL
```

---

## Step 4: In-Flight Pipeline Jobs

```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" <<'SQL'
SELECT
  trigger,
  status,
  started_at,
  CAST((julianday('now') - julianday(started_at)) * 60 AS INTEGER) AS minutes_running,
  duration_seconds,
  summary
FROM pipeline_runs
WHERE status IN ('running','pending','failed')
ORDER BY started_at DESC
LIMIT 10;
SQL
```

---

## Step 5: Present the Queue

Format as a structured agenda. Omit any section with no items.

```
QUEUE — [DATE TIME]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 URGENT ([N] items)
• [entity_name] — [nudge_reason] — [N days overdue]
• [owner_name] committed to "[commitment_text]" — [N days overdue]
• Reply to [from_name] re: "[subject]" — waiting [N]h

🟡 SOON ([N] items)
• [entity_name] — [nudge_reason]
• ...

⚪ AWARENESS ([N] items)
• [entity_name] — [nudge_reason]
• ...

⚙️ IN FLIGHT
• [pipeline_name] — [status] — [N] min — [records_processed] records

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[N] urgent · [N] soon · [N] awareness · [N] in-flight
```

Rules:
- Use real names, not entity IDs
- Show days/hours overdue, not timestamps
- Commitments belong in URGENT if days_overdue > 0, SOON if due within 7 days
- If in-flight jobs show `failed`, flag clearly: "⚠️ [pipeline_name] failed — [error_message]"
- If a section is empty, omit it entirely
- Keep each line to one line — no multi-line items

**If `$ARGUMENTS` is `urgent`:** Show only the 🔴 URGENT section.
**If `$ARGUMENTS` is `soon`:** Show 🔴 and 🟡 sections.
**If `$ARGUMENTS` is `in-flight`:** Show only the ⚙️ IN FLIGHT section.

After the queue, offer one follow-up: "Want to act on any of these?" — don't list options, just wait.
