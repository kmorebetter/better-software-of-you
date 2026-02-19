---
description: Generate an AI relationship summary for a contact
allowed-tools: ["Bash", "Read"]
argument-hint: <contact name or id>
---

# Contact Relationship Summary

Generate an AI-powered relationship summary for the contact specified in $ARGUMENTS.

## Step 1: Gather All Data

Query `${CLAUDE_PLUGIN_ROOT}/data/soy.db` for everything about this contact:

```sql
-- Find the contact
SELECT * FROM contacts WHERE name LIKE '%$ARGUMENTS%' OR id = '$ARGUMENTS';

-- Notes
SELECT * FROM notes WHERE entity_type = 'contact' AND entity_id = ?
ORDER BY created_at DESC;

-- Tags
SELECT t.name, t.color FROM tags t
JOIN entity_tags et ON et.tag_id = t.id
WHERE et.entity_type = 'contact' AND et.entity_id = ?;
```

**If CRM module installed:**
```sql
-- Interaction history
SELECT * FROM contact_interactions WHERE contact_id = ?
ORDER BY occurred_at DESC;

-- Related contacts
SELECT cr.relationship_type, cr.notes,
  CASE WHEN cr.contact_id_a = ? THEN c_b.name ELSE c_a.name END as related_name
FROM contact_relationships cr
LEFT JOIN contacts c_a ON c_a.id = cr.contact_id_a
LEFT JOIN contacts c_b ON c_b.id = cr.contact_id_b
WHERE cr.contact_id_a = ? OR cr.contact_id_b = ?;

-- Pending follow-ups
SELECT * FROM follow_ups WHERE contact_id = ? AND status = 'pending'
ORDER BY due_date ASC;
```

**If Project Tracker installed:**
```sql
-- Projects linked to this contact
SELECT * FROM projects WHERE client_id = ? ORDER BY updated_at DESC;

-- Tasks assigned to this contact
SELECT t.*, p.name as project_name FROM tasks t
JOIN projects p ON t.project_id = p.id WHERE t.assigned_to = ?;
```

## Step 2: Generate the Summary

Write a relationship brief covering:

1. **Who they are** — name, company, role, how long in the system
2. **Relationship health** — based on interaction frequency and recency (if CRM data available)
3. **Key interactions** — summary of recent and significant interactions
4. **Projects together** (if Project Tracker installed) — active and completed work
5. **Pending items** — follow-ups due, tasks assigned
6. **Suggestions** — AI-generated ideas for strengthening the relationship

Keep it conversational and actionable. This is intelligence, not a data dump.
