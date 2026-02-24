---
description: Draft a follow-up message or manage follow-up reminders
allowed-tools: ["Bash", "Read"]
argument-hint: <contact name> [context or "list" or "complete <id>"]
---

# Follow-Up Management

Handle follow-up operations based on $ARGUMENTS. Database at `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`.

## Determine the Operation

- **"list"** → Show pending follow-ups
- **"complete <id>"** → Mark a follow-up as done
- **Contact name** → Draft a follow-up message for that person
- **Contact name + context** → Draft a follow-up with specific context

## List Pending Follow-Ups

```sql
SELECT f.id, f.due_date, f.reason, f.status, c.name as contact_name
FROM follow_ups f JOIN contacts c ON f.contact_id = c.id
WHERE f.status = 'pending'
ORDER BY f.due_date ASC;
```

Highlight overdue items (due_date < today).

## Complete a Follow-Up

```sql
UPDATE follow_ups SET status = 'completed', completed_at = datetime('now') WHERE id = ?;
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('contact', (SELECT contact_id FROM follow_ups WHERE id = ?), 'follow_up_completed', json_object('follow_up_id', ?));
```

## Draft a Follow-Up Message

1. Look up the contact and gather recent context:
   - Contact details
   - Recent interactions (if CRM installed)
   - Recent notes
   - Active projects together (if Project Tracker installed)
   - Latest relationship score (if Conversation Intelligence installed):
     ```sql
     SELECT relationship_depth, trajectory FROM relationship_scores
     WHERE contact_id = ? ORDER BY score_date DESC LIMIT 1;
     ```

2. Draft using this template structure:
   1. **Greeting + reference to last interaction:** "Following up on our {interaction_type} {days_ago} days ago about {topic}."
   2. **Purpose statement:** one sentence on why you're reaching out
   3. **Relevant context:** mention active project or pending commitment if applicable
   4. **Clear ask or next step**
   5. **Sign-off**

3. Tone — match the relationship depth from `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/conversation-intelligence/references/scoring-methodology.md`:
   - **Trusted / Collaborative:** casual, first-name, brief. Skip formalities.
   - **Professional:** standard business, slightly more formal.
   - **Transactional** (or no score): concise, action-focused. Get to the point.

4. Ask if the user wants to:
   - Refine the message
   - Schedule a follow-up reminder
   - Log this as an interaction

## Schedule a Follow-Up Reminder

```sql
INSERT INTO follow_ups (contact_id, due_date, reason) VALUES (?, ?, ?);
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('contact', ?, 'follow_up_scheduled', json_object('due_date', ?, 'reason', ?));
```
