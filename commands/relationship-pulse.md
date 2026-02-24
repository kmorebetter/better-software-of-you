---
description: Deep relationship view combining CRM data with conversation intelligence
allowed-tools: ["Bash", "Read"]
argument-hint: <contact name>
---

# Relationship Pulse

Provide a comprehensive view of a relationship, combining CRM data with conversation intelligence. Database at `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`.

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
SELECT *, data_points FROM communication_insights WHERE contact_id = ?
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

This is the "how are things with Sarah?" command. Present as a comprehensive but readable briefing **grounded in computed values from scoring-methodology.md**.

**Ground every claim in data.** Use the computed depth, trajectory, follow-through percentages, and dominance ratios — never vibes-based language like "a sign of growing trust" or "well-balanced."

"Here's where things stand with **Sarah Chen** (CTO, Meridian Labs).

**Relationship depth: Collaborative** — 7 meetings in 90 days, dominance 1.1x in 1:1s, follow-through user:75% contact:68%. *(Show the depth reasoning from the `notes` field of the latest relationship_score.)*

**Trajectory: Strengthening** — meeting frequency up 40% vs previous 45 days (4 meetings current vs 3 previous).

**Communication patterns:** Your talk ratio with Sarah averages **45%** (dominance 0.9x — balanced for 1:1 meetings). You ask about **3 questions per call**. Interruptions: 0 (format doesn't support detection).

**Open commitments:** You owe Sarah the **updated proposal** (due Friday). She's sending the **brand guidelines doc**. Follow-through: you **75%**, Sarah **68%** — both above the collaborative threshold.

**Active projects together:** The **Rebrand** project is in progress, high priority, targeting end of March.

**Coach's take:** *(Pull the latest coach_note content. If the coach note includes data_points, reference the trigger and threshold.)* In your last call, your dominance ratio was 1.72x — above the 1.5 threshold. You talked through the entire requirements section without checking in. Try pausing every 2-3 minutes to ask her reaction."

Show depth reasoning from the `notes` field. Display dominance_ratio alongside talk_ratio_avg. Show follow-through percentages for both directions (user and contact). Use "--" for any NULL values.
