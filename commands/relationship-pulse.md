---
description: Deep relationship view combining CRM data with conversation intelligence
allowed-tools: ["Bash", "Read"]
argument-hint: <contact name>
---

# Relationship Pulse

Provide a comprehensive view of a relationship, combining CRM data with conversation intelligence. Database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

## Gather All Data

Look up the contact:
```sql
SELECT * FROM contacts WHERE name LIKE '%$ARGUMENTS%';
```

**Conversation history:**
```sql
SELECT t.id, t.title, t.summary, t.duration_minutes, t.occurred_at
FROM transcripts t
JOIN transcript_participants tp ON tp.transcript_id = t.id
WHERE tp.contact_id = ?
ORDER BY t.occurred_at DESC;
```

**Communication metrics over time:**
```sql
SELECT cm.talk_ratio, cm.word_count, cm.question_count, cm.interruption_count, t.occurred_at
FROM conversation_metrics cm
JOIN transcripts t ON t.id = cm.transcript_id
WHERE cm.contact_id = ? ORDER BY t.occurred_at DESC;
```

**All insights for this contact:**
```sql
SELECT * FROM communication_insights WHERE contact_id = ?
ORDER BY created_at DESC;
```

**Current relationship score:**
```sql
SELECT * FROM relationship_scores WHERE contact_id = ?
ORDER BY score_date DESC LIMIT 1;
```

**Open commitments both directions:**
```sql
SELECT c.*, CASE WHEN c.is_user_commitment = 1 THEN 'You' ELSE co.name END as owner
FROM commitments c
LEFT JOIN contacts co ON co.id = c.owner_contact_id
WHERE c.status = 'open' AND (
  c.owner_contact_id = ? OR c.transcript_id IN (
    SELECT transcript_id FROM transcript_participants WHERE contact_id = ?
  )
);
```

**If CRM installed — interactions and follow-ups:**
```sql
SELECT * FROM contact_interactions WHERE contact_id = ? ORDER BY occurred_at DESC LIMIT 10;
SELECT * FROM follow_ups WHERE contact_id = ? AND status = 'pending';
```

**If Project Tracker installed — shared projects:**
```sql
SELECT * FROM projects WHERE client_id = ? AND status IN ('active', 'planning');
```

## Present as Narrative

This is the "how are things with Sarah?" command. Present as a comprehensive but readable briefing:

"Here's where things stand with **Sarah Chen** (CTO, Meridian Labs).

**The relationship is strengthening.** You've had **6 meetings** this quarter, up from 3 last quarter. Conversations have evolved from pure **project logistics** to more strategic discussions about **team structure** and **technical direction** — a sign of growing trust.

**Communication patterns:** Your talk ratio with Sarah averages **45%** — well-balanced. You ask her about **3 questions per call**, and she tends to give detailed answers. Interruptions are rare on both sides. Your best conversations with her happen when you ask open-ended questions and give her room to think.

**Open commitments:** You owe Sarah the **updated proposal** (due Friday) and she's sending you the **brand guidelines doc**. Follow-through between you is at **85%** — solid.

**Active projects together:** The **Rebrand** project is in progress, high priority, targeting end of March. There are 2 blocked tasks that came up in your last conversation.

**Coach's take:** This is one of your strongest professional relationships right now. The shift from transactional to collaborative conversations is exactly what you want. One thing to watch — you've mentioned the **database migration** in 3 separate calls without creating a task for it. Either scope it or take it off the table."
