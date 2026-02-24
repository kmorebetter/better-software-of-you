---
description: Your communication review — patterns, metrics, and coaching across conversations
allowed-tools: ["Bash", "Read"]
argument-hint: [week | month | <contact name>]
---

# Communication Review

Provide a communication assessment based on conversation data. Database at `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`.

## Determine the Scope

- **No arguments or "week"** → This week's review
- **"month"** → Monthly trends
- **A contact name** → Review for a specific relationship

## Gather Data

**Transcripts in the period:**
```sql
SELECT t.*, GROUP_CONCAT(DISTINCT CASE WHEN tp.is_user = 0 THEN c.name END) as participants
FROM transcripts t
LEFT JOIN transcript_participants tp ON tp.transcript_id = t.id
LEFT JOIN contacts c ON c.id = tp.contact_id
WHERE t.occurred_at >= date('now', '-7 days')
GROUP BY t.id ORDER BY t.occurred_at DESC;
```

**Aggregate metrics:**
```sql
SELECT
  COUNT(DISTINCT cm.transcript_id) as call_count,
  SUM(CASE WHEN tp.is_user = 1 THEN cm.word_count ELSE 0 END) as user_words,
  SUM(cm.word_count) as total_words,
  AVG(CASE WHEN tp.is_user = 1 THEN cm.talk_ratio END) as avg_talk_ratio,
  SUM(CASE WHEN tp.is_user = 1 THEN cm.question_count ELSE 0 END) as user_questions
FROM conversation_metrics cm
JOIN transcript_participants tp ON tp.transcript_id = cm.transcript_id AND tp.contact_id = cm.contact_id
JOIN transcripts t ON t.id = cm.transcript_id
WHERE t.occurred_at >= date('now', '-7 days');
```

```sql
-- Per-call dominance ratios (for trend analysis)
SELECT cm.transcript_id, cm.talk_ratio,
  (SELECT COUNT(*) FROM transcript_participants WHERE transcript_id = cm.transcript_id) as participant_count,
  cm.talk_ratio / (1.0 / (SELECT COUNT(*) FROM transcript_participants WHERE transcript_id = cm.transcript_id)) as dominance_ratio,
  t.occurred_at
FROM conversation_metrics cm
JOIN transcript_participants tp ON tp.transcript_id = cm.transcript_id AND tp.is_user = 1
JOIN transcripts t ON t.id = cm.transcript_id
WHERE t.occurred_at >= date('now', '-7 days')
  AND cm.contact_id = tp.contact_id;
```

**Commitment follow-through:**
```sql
-- Follow-through rate: completed / (completed + overdue). Open-not-yet-due excluded.
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
  SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue,
  CAST(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS REAL)
    / NULLIF(SUM(CASE WHEN status IN ('completed', 'overdue') THEN 1 ELSE 0 END), 0) as follow_through_rate
FROM commitments WHERE created_at >= date('now', '-30 days');
```

**Recent insights:**
```sql
SELECT ci.*, c.name as contact_name FROM communication_insights ci
LEFT JOIN contacts c ON c.id = ci.contact_id
WHERE ci.created_at >= date('now', '-7 days')
ORDER BY ci.created_at DESC;
```

**Relationship trajectories:**
```sql
SELECT rs.*, c.name as contact_name FROM relationship_scores rs
JOIN contacts c ON c.id = rs.contact_id
WHERE rs.score_date = (SELECT MAX(score_date) FROM relationship_scores WHERE contact_id = rs.contact_id)
AND rs.trajectory IN ('cooling', 'at_risk')
ORDER BY rs.trajectory ASC;
```

## Present as Narrative

Ground every number in computed values. Use dominance ratios (not "a bit high"), follow-through percentages (not "could be better"), and exact meeting counts.

"This week you had **4 calls** totalling about **2 hours 15 minutes**. Your average talk ratio was **58%** with an average dominance ratio of **1.16x** — balanced overall, though your call with **Mike** hit **1.72x** (dominant in a 1:1).

You asked **12 questions** across those calls, mostly in your sessions with **Sarah** and **Bob**. The conversation with **Mike** had a dominance ratio of 1.72x — you did most of the talking there.

**Commitment follow-through** is at **78%** this month (7 completed / 9 resolved). The **design review notes** for Sarah and the **scope document** for the Meridian project are overdue.

**Relationships needing attention:** Your calls with **Bob Johnson** show a frequency drop — 1 meeting this month vs weekly last quarter. Trajectory: **cooling**. Consider a longer catch-up.

**Coach highlight:** *(Pull the strongest coach_note from the period, with its data_points trigger and threshold.)*"

Display dominance_ratio per call alongside talk_ratio. Use follow-through formula from scoring-methodology.md. Show "--" for NULL values.
