---
description: Log, view, and track decisions and their outcomes
allowed-tools: ["Bash", "Read"]
argument-hint: <decision description or "list" or "revisit" or "review <id>" or "outcome <title>">
---

# Decision Tracking

Handle decision operations based on $ARGUMENTS. Database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

## Determine the Operation

Parse the arguments to figure out what the user wants:

- **"list" or "list <project>"** → List decisions, optionally filtered by project
- **"revisit"** → Show decisions with scheduled reviews due
- **"review <id or title>"** → Run a structured review for a specific decision
- **"outcome <title>"** → Record what happened after a decision (quick update)
- **A title or numeric ID matching an existing decision** → View that decision
- **A natural language description of a decision made** → Log a new decision

---

## Log a New Decision

The user describes a decision naturally, e.g. "went with Stripe over Square for payments because better API docs and Jake recommended it."

Parse the natural language into structured fields:

- **title**: Generate a concise title (e.g., "Payment processor: Stripe over Square")
- **context**: What prompted this decision
- **options_considered**: JSON array of alternatives mentioned (e.g., `["Stripe", "Square"]`)
- **decision**: What was chosen
- **rationale**: Why it was chosen

**Ask for confidence level:** "On a scale of 1–10, how certain were you when you made this call? (1 = significant doubt, 10 = very confident)" — if the user is in a hurry or it's obvious from context, default to NULL and skip asking.

If the user mentions a project or it's obvious from context, look up the project:

```sql
SELECT id, name FROM projects WHERE name LIKE '%keyword%';
```

If a person influenced the decision, look up the contact:

```sql
SELECT id, name FROM contacts WHERE name LIKE '%keyword%';
```

**Set review schedule automatically** — calculate from `datetime('now')`:
- `review_30_date` = decided_at + 30 days
- `review_90_date` = decided_at + 90 days
- `review_180_date` = decided_at + 180 days

Run the insert and activity log in a single sqlite3 call:

```sql
INSERT INTO decisions (
  title, context, options_considered, decision, rationale,
  confidence_level, review_30_date, review_90_date, review_180_date,
  project_id, contact_id, status, decided_at, created_at, updated_at
)
VALUES (
  ?, ?, ?, ?, ?,
  ?,
  date('now', '+30 days'), date('now', '+90 days'), date('now', '+180 days'),
  ?, ?, 'decided', datetime('now'), datetime('now'), datetime('now')
);
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('decision', last_insert_rowid(), 'created', json_object('title', ?));
```

Confirm: "Logged: **Payment processor: Stripe over Square** — chose Stripe for better API docs + Jake's recommendation. Options considered: Stripe, Square."

If confidence was captured: "Confidence at decision time: 8/10."

Add: "I've scheduled check-ins at 30, 90, and 180 days. Nudges will surface them when due."

---

## List Decisions

If just "list", show recent decisions:

```sql
SELECT d.id, d.title, d.status, d.confidence_level, d.decided_at,
       p.name AS project, c.name AS influenced_by,
       d.review_30_date, d.review_90_date, d.review_180_date,
       d.process_quality, d.outcome_quality
FROM decisions d
LEFT JOIN projects p ON d.project_id = p.id
LEFT JOIN contacts c ON d.contact_id = c.id
ORDER BY d.decided_at DESC;
```

If "list <project>", filter by project name:

```sql
SELECT d.id, d.title, d.status, d.confidence_level, d.decided_at
FROM decisions d
JOIN projects p ON d.project_id = p.id
WHERE p.name LIKE '%project%'
ORDER BY d.decided_at DESC;
```

Present as a table: Title, Status, Confidence, Date, Project.

Note any decisions with reviews coming up in the next 14 days.

---

## View a Specific Decision

Look up by LIKE match on title or by numeric ID:

```sql
SELECT d.*, p.name AS project_name, c.name AS contact_name
FROM decisions d
LEFT JOIN projects p ON d.project_id = p.id
LEFT JOIN contacts c ON d.contact_id = c.id
WHERE d.id = ? OR d.title LIKE '%query%';
```

Show full details: title, context, options considered, decision, rationale, confidence level, outcome (if any), process quality, outcome quality, external factors, what they'd do differently, status, linked project and contact.

If process_quality and outcome_quality are both set, show the quadrant label:
- process 4-5 + outcome 4-5 → **Skilled** — good process, good result
- process 4-5 + outcome 1-2 → **Unlucky** — good process, bad result (don't change the process)
- process 1-2 + outcome 4-5 → **Lucky** — bad process, good result (the process still needs work)
- process 1-2 + outcome 1-2 → **Expected** — bad process, bad result

If no outcome recorded and a review date has passed, suggest: "Your 30-day check-in for this decision was due on [date]. Want to run a structured review?"

---

## Structured Review

Triggered by "review <id or title>" or when the user wants to check in on a specific decision.

This is the structured process/outcome separation — the core of grounded decision tracking.

**Step 1:** Look up the decision.

**Step 2:** Determine which review stage is appropriate:
- If `review_30_date` has passed but `process_quality` is NULL → 30-day check-in (too early for outcome, focus on process)
- If `review_90_date` has passed but `outcome_quality` is NULL → 90-day review (assess both)
- If `review_180_date` has passed → full retrospective

**Step 3:** Ask structured questions in sequence. Present one at a time, not as a form dump.

### 30-Day Check-In (early signals, focus on process)

"It's been about 30 days since you decided to [decision]. A few questions:"

1. "Any early signals on how this is playing out?" → `outcome` field (preliminary notes)
2. "Looking back at the *process* — did you consider the right options and have enough information? Rate 1–5." → `process_quality`
3. "What was in your control vs. what wasn't?" → `within_control`, `external_factors`

Don't ask for `outcome_quality` at 30 days — it's too early to know. Say explicitly: "We won't rate the outcome yet — it's too early. We're just checking the process."

### 90-Day Review (assess the outcome)

"It's been about 3 months. Time to check in on [decision]."

1. "What actually happened?" → `outcome` (update or confirm)
2. "How did it turn out? Rate the outcome 1–5 (1=very bad, 5=very good)." → `outcome_quality`
3. "Now that you can see the outcome — how good was your *process*? Rate 1–5." → `process_quality`
   Note: "Separate the two: a bad outcome doesn't automatically mean a bad process."
4. "What would you do differently about how you *made* this decision?" → `would_do_differently`

Set `status` based on outcome_quality: 4-5 → 'validated', 1-2 → 'regretted', 3 → 'revisit'.

### 180-Day Retrospective (full picture)

Same as 90-day but also ask:
- "Has your view of the process quality changed now that more time has passed?"
- "What pattern do you notice across similar decisions?"

**Step 4:** Save all fields in a single sqlite3 call. For 30-day check-ins, do NOT update `status` (leave it as 'decided') — it's too early to assess the outcome. Only set `status` during 90-day and 180-day reviews based on `outcome_quality`.

```sql
UPDATE decisions SET
  outcome = ?,
  outcome_date = datetime('now'),
  process_quality = ?,
  outcome_quality = ?,
  within_control = ?,
  external_factors = ?,
  would_do_differently = ?,
  status = ?,
  updated_at = datetime('now')
WHERE id = ?;
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('decision', ?, 'reviewed', json_object(
  'process_quality', ?,
  'outcome_quality', ?,
  'status', ?
));
```

**Step 5:** After saving, show the quadrant label and one sentence of interpretation:
- **Skilled**: "Good process, good outcome — this is the zone you want to operate in."
- **Unlucky**: "Your process was sound. The outcome was bad luck, not a bad decision — don't overcorrect."
- **Lucky**: "The outcome was good, but the process had gaps. Worth examining before you make similar calls."
- **Expected**: "Both the process and outcome were poor. What would you change first?"

---

## Quick Outcome Update

The user describes what happened without wanting the full structured review, e.g. "Stripe integration went smoothly, launched in 2 weeks."

Capture the outcome text and ask just one clarifying question: "Quick rating — how did it turn out? (1=very bad, 5=very good)" to get `outcome_quality`.

Derive `status` from outcome_quality: 4-5 → 'validated', 1-2 → 'regretted', 3 → keep as 'decided'.

```sql
UPDATE decisions SET
  outcome = ?,
  outcome_date = datetime('now'),
  outcome_quality = ?,
  status = ?,
  updated_at = datetime('now')
WHERE id = ?;
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('decision', ?, 'outcome_recorded', json_object('status', ?, 'outcome', ?));
```

Confirm the outcome and suggest: "Want to do a full process review? That's where the real learning is."

---

## Revisit — Reviews Due

Show decisions with scheduled reviews that have passed and haven't been completed:

```sql
SELECT d.id, d.title, d.decided_at, d.status,
  d.review_30_date, d.review_90_date, d.review_180_date,
  d.process_quality, d.outcome_quality,
  CASE
    WHEN d.review_180_date <= date('now') AND (d.outcome_quality IS NULL OR d.process_quality IS NULL) THEN '180-day'
    WHEN d.review_90_date <= date('now') AND (d.outcome_quality IS NULL OR d.process_quality IS NULL) THEN '90-day'
    WHEN d.review_30_date <= date('now') AND d.process_quality IS NULL THEN '30-day'
    WHEN d.review_30_date IS NULL AND d.outcome IS NULL AND julianday('now') - julianday(d.decided_at) > 90 THEN '90-day'
  END as review_due,
  CAST(julianday('now') - julianday(d.decided_at) AS INTEGER) as days_ago
FROM decisions d
WHERE
  (d.review_30_date <= date('now') AND d.process_quality IS NULL)
  OR (d.review_90_date <= date('now') AND d.outcome_quality IS NULL)
  OR (d.review_180_date <= date('now') AND (d.outcome_quality IS NULL OR d.would_do_differently IS NULL))
  OR (d.review_30_date IS NULL AND d.outcome IS NULL AND julianday('now') - julianday(d.decided_at) > 90)
ORDER BY d.decided_at ASC;
```

Present as a table with the review type due. Prompt: "Run `/decision review <title>` to check in on any of these."
