---
description: Generate an AI relationship summary for a contact
allowed-tools: ["Bash", "Read"]
argument-hint: <contact name or id>
---

# Contact Relationship Summary

Generate an AI-powered relationship summary for the contact specified in $ARGUMENTS.

## Step 1: Gather All Data

Query `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db` for everything about this contact:

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

**If Conversation Intelligence module installed:**
```sql
-- Relationship score (latest)
SELECT * FROM relationship_scores WHERE contact_id = ?
ORDER BY score_date DESC LIMIT 1;

-- Communication insights (recent)
SELECT insight_type, content, sentiment, data_points
FROM communication_insights WHERE contact_id = ?
ORDER BY created_at DESC LIMIT 5;

-- Conversation metrics (for dominance calculation)
SELECT cm.talk_ratio, cm.word_count, cm.question_count,
  (SELECT COUNT(*) FROM transcript_participants WHERE transcript_id = cm.transcript_id) as participant_count,
  t.occurred_at
FROM conversation_metrics cm
JOIN transcripts t ON t.id = cm.transcript_id
WHERE cm.transcript_id IN (
  SELECT transcript_id FROM transcript_participants WHERE contact_id = ?
)
AND cm.contact_id IN (
  SELECT contact_id FROM transcript_participants tp WHERE tp.transcript_id = cm.transcript_id AND tp.is_user = 1
)
ORDER BY t.occurred_at DESC;

-- Commitment follow-through (bidirectional, 90d)
SELECT
  SUM(CASE WHEN is_user_commitment = 1 AND status = 'completed' THEN 1 ELSE 0 END) as user_completed,
  SUM(CASE WHEN is_user_commitment = 1 AND status = 'overdue' THEN 1 ELSE 0 END) as user_overdue,
  SUM(CASE WHEN is_user_commitment = 0 AND status = 'completed' THEN 1 ELSE 0 END) as contact_completed,
  SUM(CASE WHEN is_user_commitment = 0 AND status = 'overdue' THEN 1 ELSE 0 END) as contact_overdue
FROM commitments
WHERE (owner_contact_id = ? OR transcript_id IN (
  SELECT transcript_id FROM transcript_participants WHERE contact_id = ?
))
AND (completed_at >= date('now', '-90 days') OR (status = 'overdue' AND updated_at >= date('now', '-90 days')));

-- Meeting count (90d)
SELECT COUNT(*) as meetings_90d
FROM transcripts t
JOIN transcript_participants tp ON tp.transcript_id = t.id
WHERE tp.contact_id = ? AND t.occurred_at >= date('now', '-90 days');
```

## Step 2: Generate the Summary

Write a relationship brief covering:

1. **Who they are** — name, company, role, how long in the system
2. **Relationship depth and trajectory** (if Conversation Intelligence installed) — use computed values from the relationship_scores table, not vague descriptions:
   - Show depth level and reasoning from `notes` field: "**Collaborative** — 7 meetings in 90d, dominance 1.1x, follow-through user:75% contact:68%"
   - Show trajectory with evidence: "**Strengthening** — frequency up 40% vs previous 45 days"
   - Show follow-through percentages for both directions
   - Show dominance ratio alongside talk ratio
   - Use "--" for any NULL values
3. **Key interactions** — summary of recent and significant interactions
4. **Projects together** (if Project Tracker installed) — active and completed work
5. **Pending items** — follow-ups due, tasks assigned, overdue commitments
6. **Coaching insight** (if Conversation Intelligence installed) — pull the latest coach_note content with its data_points evidence

Keep it conversational and actionable. Ground every claim in data — no vague "relationship health" statements without the computed depth, trajectory, and follow-through to back them up.
