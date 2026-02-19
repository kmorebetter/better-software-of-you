---
description: View and manage commitments extracted from conversations
allowed-tools: ["Bash"]
argument-hint: [mine | theirs | overdue | <contact name> | complete <id>]
---

# Commitments

View and manage commitments from conversation transcripts. Database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

## Determine the Operation

Parse $ARGUMENTS:

- **No arguments** → Show all open commitments
- **"mine"** → Things the user owes others
- **"theirs"** → Things others owe the user
- **"overdue"** → Past deadline
- **A contact name** → Commitments involving that person
- **"complete <id>"** → Mark a commitment as done

## Queries

**All open commitments:**
```sql
SELECT c.id, c.description, c.deadline_date, c.status, c.is_user_commitment,
  CASE WHEN c.is_user_commitment = 1 THEN 'You' ELSE co.name END as owner,
  t.title as from_call, t.occurred_at as call_date
FROM commitments c
LEFT JOIN contacts co ON co.id = c.owner_contact_id
LEFT JOIN transcripts t ON t.id = c.transcript_id
WHERE c.status = 'open'
ORDER BY c.deadline_date ASC NULLS LAST;
```

**Mine / theirs:**
Add `AND c.is_user_commitment = 1` or `AND c.is_user_commitment = 0`

**Overdue:**
Add `AND c.deadline_date < date('now')`

**By contact:**
```sql
-- Commitments where contact is the owner OR from calls with that contact
AND (c.owner_contact_id = ? OR c.transcript_id IN (
  SELECT transcript_id FROM transcript_participants WHERE contact_id = ?
))
```

**Complete:**
```sql
UPDATE commitments SET status = 'completed', completed_at = datetime('now'), updated_at = datetime('now')
WHERE id = ?;
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('commitment', ?, 'completed', json_object('description', ?));
```

## Present as Narrative

Group by owner, summarize naturally:

"You have **3 open commitments**: **send the proposal** to Sarah (due Friday), **update the project timeline** from yesterday's call with Bob, and **review the design specs** — no deadline on that one.

**Others owe you 2 things**: Sarah is sending the **brand guidelines**, and Mike said he'd **confirm the budget** by end of week.

The proposal for Sarah is the most urgent — **due in 2 days**."

## Cross-Module (if Project Tracker installed)

When showing commitments, check if any match existing tasks:
```sql
SELECT id, title, project_id FROM tasks WHERE title LIKE ? AND status != 'done';
```

If a commitment doesn't have a linked task, suggest: "Want to add 'send the proposal' as a task on the **Rebrand** project?"

When completing a commitment that has a `linked_task_id`, offer to mark the task as done too.
