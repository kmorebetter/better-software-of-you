---
description: Your communication review — patterns, metrics, and coaching across conversations
allowed-tools: ["Bash", "Read"]
argument-hint: [week | month | <contact name>]
---

# Communication Review

Provide a communication assessment based on conversation data. Database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

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

**Commitment follow-through:**
```sql
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
  SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue
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

"This week you had **4 calls** totalling about **2 hours 15 minutes**. Your average talk ratio was **58%** — a bit high, meaning you were talking more than listening in most conversations.

You asked **12 questions** across those calls, mostly in your sessions with **Sarah** and **Bob**. The conversation with **Mike** was more one-directional — you did most of the talking there.

**Commitment follow-through** is at **78%** this month — you've completed 7 of 9 commitments on time, but the **design review notes** for Sarah and the **scope document** for the Meridian project are overdue.

**Relationships needing attention:** Your calls with **Bob Johnson** have been declining in frequency — down to once this month from weekly last quarter. The conversations have narrowed to just status updates. Consider a longer catch-up.

**Coach highlight:** The best moment this week was in your call with Sarah — you asked her what worried her about the rebrand, then gave her space to think. That led to the most substantive part of the conversation. Try that same approach with Mike next time — he had something to say about the timeline but didn't get the room."
