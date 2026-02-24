---
description: Import a meeting transcript and extract commitments, metrics, and coaching insights
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: [paste transcript text, or provide a file path]
---

# Import Call Transcript

Import a meeting transcript into Software of You. Database at `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`.

## Step 1: Get the Transcript

- **If $ARGUMENTS contains a file path** → Read the file
- **If $ARGUMENTS contains transcript text** → Use it directly
- **If no arguments** → Ask: "Paste your transcript here, or give me a file path. I can handle any format — Fathom, Otter, Zoom, or just plain text with speaker names."

## Step 2: Identify Participants

Parse speaker labels from the transcript. Then match to existing contacts:

```sql
SELECT id, name, email FROM contacts WHERE name LIKE ? OR name LIKE ?;
```

For each speaker:
- If a clear match → link automatically
- If ambiguous → ask the user: "Is 'Sarah' the same as Sarah Chen at Meridian Labs?"
- If no match → ask: "I don't have a contact for 'Mike'. Want to create one, or skip?"

Ask the user which speaker is them (if not obvious from context).

## Step 3: Process the Transcript

**Read scoring references first:**
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/conversation-intelligence/references/scoring-methodology.md` — formulas, thresholds, NULL conditions
- `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/conversation-intelligence/references/coaching-guidelines.md` — SBI+T framework, threshold checklist

Run the full analysis pipeline:

**3a. Save the transcript:**

**Calculate duration from timestamps (MANDATORY — never estimate):**
- Parse the first and last timestamp in the transcript to compute `duration_minutes`
- Transcript formats vary — look for `HH:MM:SS`, `MM:SS`, `0:00` / `1:23:45`, or relative timestamps like `[00:00]`, `(12:34)`, speaker lines with times, etc.
- Duration = last timestamp minus first timestamp, rounded to nearest minute
- If the transcript has **no timestamps at all**, set `duration_minutes = NULL` — do NOT guess or estimate a number
- **Show your work:** Before storing, output the first timestamp found, the last timestamp found, and the calculated duration. Example: "Timestamps: first `0:00`, last `31:42` → 32 minutes". If no timestamps: "No timestamps found in transcript → duration NULL".

```sql
INSERT INTO transcripts (title, source, raw_text, duration_minutes, occurred_at, processed_at)
VALUES (?, ?, ?, ?, ?, datetime('now'));
```
Generate a title from the content if one wasn't provided.

**3b. Save participants:**
```sql
INSERT INTO transcript_participants (transcript_id, contact_id, speaker_label, is_user)
VALUES (?, ?, ?, ?);
```

**3c. Extract commitments:**
Analyze the transcript for things people said they'd do. For each:
```sql
INSERT INTO commitments (transcript_id, owner_contact_id, is_user_commitment, description, deadline_mentioned, deadline_date)
VALUES (?, ?, ?, ?, ?, ?);
```

**3d. Calculate metrics per participant (MANDATORY — derive from actual transcript data, never estimate):**

All metrics MUST be computed by counting/measuring the actual transcript text. Do NOT estimate, approximate, or invent numbers.

| Metric | How to calculate | If not calculable |
|--------|-----------------|-------------------|
| `word_count` | Count actual words in each speaker's segments | Always calculable — every transcript has words |
| `talk_ratio` | Each speaker's `word_count / total_word_count` as a decimal (0.0–1.0) | Always calculable from word counts |
| `question_count` | Count sentences ending in `?` in each speaker's segments | Always calculable — count the `?` marks |
| `interruption_count` | Count explicit overlap markers only: `[overlapping]`, `<crosstalk>`, `[cross-talk]`. Do NOT estimate from punctuation or speaker change patterns. | Set to `0` if format doesn't contain overlap markers |
| `longest_monologue_seconds` | Find longest consecutive block per speaker. If timestamps exist, use them. If not, estimate from word count at ~150 words/minute | Use word-count estimation only for this field, and state you estimated it |

**Show your work (MANDATORY):** Before storing ANY metrics, output a calculation summary the user can verify. Example:

> **Metrics calculated from transcript:**
> - Kerry: 1,247 words, 8 questions, talk ratio 0.56
> - Sarah: 983 words, 12 questions, talk ratio 0.44
> - Total: 2,230 words across 32 minutes
> - Longest monologue: Kerry, 4:12–6:48 (2m36s)
> - Dominance ratio: Kerry 1.12x (balanced for 2-person call), Sarah 0.88x

If you cannot show how you got a number, you must not store it — use NULL instead.

```sql
INSERT INTO conversation_metrics (transcript_id, contact_id, talk_ratio, word_count, question_count, interruption_count, longest_monologue_seconds)
VALUES (?, ?, ?, ?, ?, ?, ?);
```

**3e. Generate insights:**

Generate a **relationship pulse** (how is this relationship going, based on all historical data):
```sql
INSERT INTO communication_insights (transcript_id, contact_id, insight_type, content, sentiment, data_points)
VALUES (?, ?, 'relationship_pulse', ?, ?, ?);
-- data_points JSON: {"meetings_90d":N, "talk_ratio_avg":N, "dominance_avg":N, "follow_through_user":N, "follow_through_contact":N, "depth":"level", "trajectory":"label"}
```

Generate a **coach note** (must reference a specific moment from THIS call):
```sql
INSERT INTO communication_insights (transcript_id, contact_id, insight_type, content, sentiment, data_points)
VALUES (?, ?, 'coach_note', ?, ?, ?);
-- data_points JSON: {"trigger":"threshold_name", "value":N, "threshold":N, "context":"meeting type"}
-- A coach note must cross at least one threshold from scoring-methodology.md. No threshold = no coach note.
```

Check for **pattern alerts** (only if 3+ transcripts with same contact exist):
```sql
SELECT COUNT(*) FROM transcripts t
JOIN transcript_participants tp ON tp.transcript_id = t.id
WHERE tp.contact_id = ?;
```

If a pattern triggers, INSERT with data_points:
```sql
INSERT INTO communication_insights (transcript_id, contact_id, insight_type, content, sentiment, data_points)
VALUES (?, ?, 'pattern_alert', ?, 'needs_attention', ?);
-- data_points JSON: {"pattern":"pattern_name", "values":[...], "dates":[...]}
-- Only generate if a pattern rule from scoring-methodology.md triggers. No rule triggered = no pattern_alert row.
```

**3f. Update relationship scores:**
```sql
-- Compute all values using formulas from scoring-methodology.md:
-- meeting_frequency = COUNT(transcripts in 90d) / 13.0
-- talk_ratio_avg = AVG(user talk_ratio) across 90d transcripts
-- commitment_follow_through = completed / (completed + overdue) in 90d (user direction)
-- relationship_depth = first matching threshold (Trusted > Collaborative > Professional > Transactional)
-- trajectory = 45d window comparison (NULL if insufficient data)
-- topic_diversity = NULL (deprecated)
-- notes = depth reasoning: "{Level} — {meetings} meetings in 90d, follow-through user:{pct}% contact:{pct}%, dominance {ratio}x"
INSERT INTO relationship_scores (contact_id, score_date, meeting_frequency, talk_ratio_avg, commitment_follow_through, topic_diversity, relationship_depth, trajectory, notes)
VALUES (?, date('now'), ?, ?, ?, NULL, ?, ?, ?);
```

**3g. Log activity and create CRM interactions (if CRM installed):**
```sql
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('transcript', ?, 'imported', json_object('title', ?, 'participants', ?));

-- If CRM installed, log as interaction for each participant
INSERT INTO contact_interactions (contact_id, type, direction, subject, summary, occurred_at)
VALUES (?, 'meeting', 'outbound', ?, ?, ?);
```

**3h. Extract call intelligence (always, for every call):**

Analyze the transcript for structured intelligence. Populate what's present, omit what isn't — sales/discovery calls will be rich in all four blocks, internal meetings might only have pain points. Store as JSON in `transcripts.call_intelligence`.

| Block | What to extract | JSON key |
|-------|----------------|----------|
| **Org/Team Intel** | Team size, budget context, company scale, decision-making structure | `org_intel` |
| **Pain Points** | Problems/challenges the other party described, with severity (high=critical, medium=moderate) | `pain_points` |
| **Tech Stack** | Tools, platforms, systems mentioned with category labels | `tech_stack` |
| **Key Concerns** | Objections, worries, risks raised — note whether addressed and how | `key_concerns` |

JSON structure:
```json
{
  "org_intel": { "team_size": "12-20", "context": "Small team, $100M+ projects" },
  "pain_points": [
    { "title": "Recurring report workflows", "detail": "quarterly asset management reports take weeks to compile manually", "severity": "high" }
  ],
  "tech_stack": [
    { "name": "Yardi", "category": "Accounting" }
  ],
  "key_concerns": [
    { "title": "Data privacy", "detail": "doesn't want proprietary data leaking", "addressed": true, "response": "Claude Enterprise siloing" }
  ]
}
```

Save it:
```sql
UPDATE transcripts SET call_intelligence = ? WHERE id = ?;
```

## Step 4: Present Results

Present structured blocks first (at-a-glance), then narrative prose (deeper context).

### 4a. Stats Grid (always present, 2×2 layout):

| Stat | Source | Fallback |
|------|--------|----------|
| **Org/Team Size** | `call_intelligence.org_intel.team_size` | "—" if not discussed |
| **Talk Ratio** | `conversation_metrics.talk_ratio` + dominance_ratio | Always available from 3d — show ratio and dominance: "You: 62% (dominance 1.24x — balanced)" or "You: 78% (dominance 1.56x — dominant)" |
| **Questions Asked** | `conversation_metrics.question_count` | Always available from 3d — include depth assessment (e.g., "8 questions — strong discovery") |
| **Commitments** | Count from `commitments` for this transcript | Always available from 3c — include yours/theirs breakdown |

### 4b. Pain Points Uncovered (if any in `call_intelligence.pain_points`):

- Bulleted list, **bold title** + description
- 🔴 prefix for `severity: "high"` (critical), 🟡 prefix for `severity: "medium"` (moderate)

### 4c. Current Tech Stack (if any in `call_intelligence.tech_stack`):

- Show as labeled items: **Tool Name** (Category)
- Group by category if multiple tools share one

### 4d. Key Concerns Raised (if any in `call_intelligence.key_concerns`):

- Each with **bold title**, description, and resolution status
- ✅ Addressed: show how (e.g., "✅ **Data privacy** — addressed via Claude Enterprise siloing")
- ⚠️ Unaddressed: flag for follow-up (e.g., "⚠️ **Timeline pressure** — not directly addressed, follow up")

### 4e. Narrative briefing (always present, after structured blocks):

"Imported your **32-minute call** with **Sarah Chen** about the **rebrand project**.

**Commitments:** You said you'd **send the updated proposal by Friday** and **schedule a follow-up with design**. Sarah is going to **share the brand guidelines doc**.

**Relationship pulse:** Relationship depth: **Collaborative** — 6 meetings in 90 days, follow-through user:85% contact:80%, dominance 0.9x (balanced). Trajectory: **Strengthening** — frequency up from 3 meetings last quarter.

**Coach's note:** You asked Sarah what worried her most about the timeline, then **stayed quiet while she worked through it**. That space led to the most productive part of the call. More of that."

End with: "Use `/commitments` to see all open items, or `/relationship-pulse Sarah` for the full picture."
