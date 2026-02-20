---
description: Log, view, and track decisions and their outcomes
allowed-tools: ["Bash", "Read"]
argument-hint: <decision description or "list" or "revisit">
---

# Decision Tracking

Handle decision operations based on $ARGUMENTS. Database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

## Determine the Operation

Parse the arguments to figure out what the user wants:

- **"list" or "list <project>"** → List decisions, optionally filtered by project
- **"revisit"** → Show decisions needing follow-up
- **"outcome <title>"** → Record what happened after a decision
- **A title or numeric ID matching an existing decision** → View that decision
- **A natural language description of a decision made** → Log a new decision

## Log a New Decision

The user describes a decision naturally, e.g. "went with Stripe over Square for payments because better API docs and Jake recommended it."

Parse the natural language into structured fields:

- **title**: Generate a concise title (e.g., "Payment processor: Stripe over Square")
- **context**: What prompted this decision
- **options_considered**: JSON array of alternatives mentioned (e.g., `["Stripe", "Square"]`)
- **decision**: What was chosen
- **rationale**: Why it was chosen

If the user mentions a project or it's obvious from context, look up the project:

```sql
SELECT id, name FROM projects WHERE name LIKE '%keyword%';
```

If a person influenced the decision, look up the contact:

```sql
SELECT id, name FROM contacts WHERE name LIKE '%keyword%';
```

Run the insert and activity log in a single sqlite3 call:

```sql
INSERT INTO decisions (title, context, options_considered, decision, rationale, project_id, contact_id, status, decided_at, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, 'decided', datetime('now'), datetime('now'), datetime('now'));
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('decision', last_insert_rowid(), 'created', json_object('title', ?));
```

Confirm: "Logged: **Payment processor: Stripe over Square** — chose Stripe for better API docs + Jake's recommendation. Options considered: Stripe, Square."

Suggest: "Want to link this to a project or set a reminder to check the outcome?"

## List Decisions

If just "list", show recent decisions:

```sql
SELECT d.id, d.title, d.status, d.decided_at,
       p.name AS project, c.name AS influenced_by
FROM decisions d
LEFT JOIN projects p ON d.project_id = p.id
LEFT JOIN contacts c ON d.contact_id = c.id
ORDER BY d.decided_at DESC;
```

If "list <project>", filter by project name:

```sql
SELECT d.id, d.title, d.status, d.decided_at
FROM decisions d
JOIN projects p ON d.project_id = p.id
WHERE p.name LIKE '%project%'
ORDER BY d.decided_at DESC;
```

Present as a table: Title, Status, Date, Project, Influenced By.

## View a Specific Decision

Look up by LIKE match on title or by numeric ID:

```sql
SELECT d.*, p.name AS project_name, c.name AS contact_name
FROM decisions d
LEFT JOIN projects p ON d.project_id = p.id
LEFT JOIN contacts c ON d.contact_id = c.id
WHERE d.id = ? OR d.title LIKE '%query%';
```

Show full details: title, context, options considered, decision, rationale, outcome (if any), status, linked project and contact.

If no outcome recorded and the decision is older than 30 days, suggest: "This decision is X days old. Want to record how it turned out?"

## Update Outcome

The user describes what happened, e.g. "Stripe integration went smoothly, launched in 2 weeks."

Determine status from tone: positive outcomes → 'validated', negative → 'regretted'. If ambiguous, ask.

```sql
UPDATE decisions SET outcome = ?, outcome_date = datetime('now'), status = ?, updated_at = datetime('now') WHERE id = ?;
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('decision', ?, 'outcome_recorded', json_object('status', ?, 'outcome', ?));
```

Confirm the outcome and new status.

## Revisit

Show decisions marked as 'revisit' or older than 90 days with no outcome:

```sql
SELECT d.id, d.title, d.status, d.decided_at, p.name AS project
FROM decisions d
LEFT JOIN projects p ON d.project_id = p.id
WHERE d.status = 'revisit'
   OR (d.outcome IS NULL AND d.decided_at < datetime('now', '-90 days'))
ORDER BY d.decided_at ASC;
```

Present as a table. Prompt: "These decisions are worth checking in on. Want to record an outcome for any?"
