# Scoring Methodology

Single source of truth for every computed value in Conversation Intelligence. All other files reference this — none define their own formulas.

## Metrics

### meeting_frequency

Meetings per week with a contact over the last 90 days.

```sql
SELECT COUNT(*) / 13.0 AS meetings_per_week
FROM transcripts t
JOIN transcript_participants tp ON tp.transcript_id = t.id
WHERE tp.contact_id = ?
  AND t.occurred_at >= date('now', '-90 days');
```

**NULL when:** No transcripts exist for this contact.

### commitment_follow_through

Percentage of resolved commitments that were completed (not overdue) in the last 90 days. Computed bidirectionally — user→contact and contact→user are separate values.

```sql
-- User's follow-through (commitments user made to this contact)
SELECT CAST(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS REAL)
     / NULLIF(SUM(CASE WHEN status IN ('completed', 'overdue') THEN 1 ELSE 0 END), 0)
FROM commitments
WHERE is_user_commitment = 1
  AND transcript_id IN (
    SELECT transcript_id FROM transcript_participants WHERE contact_id = ?
  )
  AND (completed_at >= date('now', '-90 days') OR (status = 'overdue' AND updated_at >= date('now', '-90 days')));

-- Contact's follow-through (commitments they made to user)
SELECT CAST(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS REAL)
     / NULLIF(SUM(CASE WHEN status IN ('completed', 'overdue') THEN 1 ELSE 0 END), 0)
FROM commitments
WHERE owner_contact_id = ?
  AND is_user_commitment = 0
  AND (completed_at >= date('now', '-90 days') OR (status = 'overdue' AND updated_at >= date('now', '-90 days')));
```

Open-not-yet-due commitments are excluded from the calculation.

**NULL when:** No resolved (completed or overdue) commitments exist in 90 days.

### talk_ratio_avg

Average of the user's talk_ratio across all transcripts with this contact in the last 90 days.

```sql
SELECT AVG(cm.talk_ratio) AS talk_ratio_avg
FROM conversation_metrics cm
JOIN transcript_participants tp
  ON tp.transcript_id = cm.transcript_id AND tp.is_user = 1
JOIN transcripts t ON t.id = cm.transcript_id
JOIN transcript_participants tp2
  ON tp2.transcript_id = t.id AND tp2.contact_id = ?
WHERE t.occurred_at >= date('now', '-90 days')
  AND (cm.contact_id IS NULL OR cm.contact_id = (
    SELECT contact_id FROM transcript_participants WHERE transcript_id = cm.transcript_id AND is_user = 1 LIMIT 1
  ));
```

Simpler approach — get the user's metrics rows for transcripts involving this contact:

```sql
SELECT AVG(cm.talk_ratio)
FROM conversation_metrics cm
JOIN transcripts t ON t.id = cm.transcript_id
WHERE t.occurred_at >= date('now', '-90 days')
  AND cm.transcript_id IN (
    SELECT transcript_id FROM transcript_participants WHERE contact_id = ?
  )
  AND cm.contact_id IN (
    SELECT contact_id FROM transcript_participants WHERE transcript_id = cm.transcript_id AND is_user = 1
  );
```

**NULL when:** No conversation_metrics exist for transcripts with this contact.

### dominance_ratio

How much the user dominates relative to an equal share. **Computed at display time, not stored.**

```
dominance_ratio = talk_ratio / (1.0 / participant_count)
```

- `1.0` = perfectly balanced for the meeting size
- `>1.5` = dominant (talking more than 1.5× their fair share)
- `<0.5` = unusually quiet
- Accounts for meeting size: 60% in a 1:1 is different from 60% in a 5-person call

For a single call, use that call's participant count. For averages across calls, compute per-call then average.

**Not stored in the database.** Always compute from `talk_ratio` and `participant_count` at the time of display.

### topic_diversity

**DEPRECATED — always NULL.** Cannot be computed reliably from transcript data.

```sql
-- Always set to NULL
topic_diversity = NULL
```

### interruption_count

Only count explicit overlap markers in the transcript text:
- `[overlapping]`
- `<crosstalk>`
- `[cross-talk]`
- `[inaudible, overlapping]`

**Do NOT estimate from punctuation patterns.** Do NOT infer interruptions from speaker changes mid-sentence. If the transcript format doesn't contain overlap markers, store `0`.

---

## Relationship Depth

Assess using the first matching level (top = most stringent):

| Level | Criteria |
|-------|----------|
| **Trusted** | All Collaborative criteria met, PLUS: 10+ meetings in 90 days, follow-through >80% in both directions (user→contact AND contact→user), AND `call_intelligence` has `org_intel` or `key_concerns` data |
| **Collaborative** | 6+ meetings in 90 days, dominance_ratio 0.6–1.8 in 1:1 meetings, follow-through >60% in both directions |
| **Professional** | 3+ meetings in 90 days, commitments exist in both directions (user made some AND contact made some) |
| **Transactional** | Default. Fewer than 3 meetings, OR no commitments exchanged |

### Depth reasoning (mandatory)

Every depth assessment must output its reasoning in the `notes` field of relationship_scores. Format:

```
{Level} — {meetings} meetings in 90d, follow-through user:{pct}% contact:{pct}%, dominance {ratio}x{qualifier}
```

Examples:
- `Professional — 4 meetings in 90d, commitments both directions, but dominance 1.72x (imbalanced)`
- `Collaborative — 7 meetings in 90d, dominance 1.1x in 1:1s, follow-through user:75% contact:68%`
- `Transactional — 2 meetings in 90d, no commitments from contact`
- `Trusted — 12 meetings in 90d, follow-through user:88% contact:82%, org_intel captured`

---

## Trajectory

Compare current 45-day window vs previous 45-day window.

| Label | Rule |
|-------|------|
| **Strengthening** | Meeting frequency up >30%, OR depth level increased, OR follow-through improved >15 percentage points |
| **Stable** | All metrics within ±20% of previous window |
| **Cooling** | Meeting frequency down >30%, OR days since last meeting > 2× their usual cadence |
| **At Risk** | No meetings in 30+ days AND (overdue commitments exist OR follow-through <50%) |
| **NULL** | Insufficient data for comparison — first score ever, all meetings fall in one window, or fewer than 2 meetings total |

### Computing windows

```sql
-- Current window: last 45 days
SELECT COUNT(*) as current_meetings
FROM transcripts t
JOIN transcript_participants tp ON tp.transcript_id = t.id
WHERE tp.contact_id = ?
  AND t.occurred_at >= date('now', '-45 days');

-- Previous window: 45-90 days ago
SELECT COUNT(*) as previous_meetings
FROM transcripts t
JOIN transcript_participants tp ON tp.transcript_id = t.id
WHERE tp.contact_id = ?
  AND t.occurred_at >= date('now', '-90 days')
  AND t.occurred_at < date('now', '-45 days');

-- Days since last meeting
SELECT julianday('now') - julianday(MAX(t.occurred_at)) as days_since_last
FROM transcripts t
JOIN transcript_participants tp ON tp.transcript_id = t.id
WHERE tp.contact_id = ?;

-- Usual cadence (average days between meetings in last 90d)
SELECT AVG(gap) FROM (
  SELECT julianday(t.occurred_at) - julianday(LAG(t.occurred_at) OVER (ORDER BY t.occurred_at)) as gap
  FROM transcripts t
  JOIN transcript_participants tp ON tp.transcript_id = t.id
  WHERE tp.contact_id = ?
    AND t.occurred_at >= date('now', '-90 days')
  ORDER BY t.occurred_at
);
```

---

## Sentiment

Applied to relationship_pulse insights and relationship_scores.

| Value | When |
|-------|------|
| `positive` | Balanced dominance (0.6–1.5), follow-through >80% both directions, strengthening trajectory |
| `neutral` | First interaction, insufficient data, OR all metrics in normal range without strong signals |
| `needs_attention` | Follow-through <60% either direction, cooling or at_risk trajectory, overdue commitments exist, dominance >2.0 or <0.4 |

---

## data_points (mandatory JSON)

Every insight row in `communication_insights` MUST have a `data_points` JSON value. No evidence = no insight row.

### relationship_pulse

```json
{
  "meetings_90d": 6,
  "talk_ratio_avg": 0.45,
  "dominance_avg": 0.9,
  "follow_through_user": 0.85,
  "follow_through_contact": 0.75,
  "depth": "collaborative",
  "trajectory": "strengthening"
}
```

### coach_note

```json
{
  "trigger": "talk_dominance",
  "value": 1.72,
  "threshold": 1.5,
  "context": "1:1 meeting"
}
```

Trigger values: `talk_dominance`, `question_distribution`, `question_quality`, `monologue_length`, `commitment_balance`, `response_latency`.

### pattern_alert

```json
{
  "pattern": "declining_follow_through",
  "values": [0.90, 0.75, 0.60],
  "dates": ["2026-01-15", "2026-02-01", "2026-02-15"]
}
```

Pattern values: `rising_dominance`, `declining_follow_through`, `frequency_drop`, `recurring_unresolved_item`.

---

## Pattern Alert Rules

Only generate a pattern_alert when 3+ calls exist with the same contact AND a rule triggers.

| Pattern | Trigger |
|---------|---------|
| `rising_dominance` | dominance_ratio increased by >0.5 over 3+ consecutive calls |
| `declining_follow_through` | Follow-through dropped >20 percentage points over 3+ scoring periods |
| `frequency_drop` | meetings/week down >50% compared to previous 90-day period |
| `recurring_unresolved_item` | Same topic mentioned in 3+ calls with no commitment created for it |

**No rule triggered = no pattern_alert row.** Do not generate pattern_alert insights when there is nothing to flag.

---

## Coach Note Thresholds

A coach note must cross at least one threshold to be generated. See `coaching-guidelines.md` for the full framework (SBI+T format, tone, and structure).

| Check | Threshold | When to flag |
|-------|-----------|-------------|
| Talk dominance | dominance_ratio > 1.5 in collaborative meeting | Note with exact number |
| Question distribution | First-half questions > 3× second-half | Fading engagement pattern |
| Question quality | >70% closed questions (is/are/did/do/can/will) vs open (what/how/why/tell me) | Note the ratio |
| Monologue length | Any turn >450 words or >180 seconds | Note the duration |
| Commitment balance | User made >3× more commitments than other party | Overcommitment risk |
| Response latency | 0–1s response to every question (requires timestamps) | Note the pattern |

**No threshold crossed = no coach_note.** Output: "Straightforward call — no standout coaching moments."
