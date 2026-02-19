---
description: Import a meeting transcript and extract commitments, metrics, and coaching insights
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: [paste transcript text, or provide a file path]
---

# Import Call Transcript

Import a meeting transcript into Software of You. Database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

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

Run the full analysis pipeline:

**3a. Save the transcript:**
```sql
INSERT INTO transcripts (title, source, raw_text, occurred_at, processed_at)
VALUES (?, ?, ?, ?, datetime('now'));
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

**3d. Calculate metrics per participant:**
```sql
INSERT INTO conversation_metrics (transcript_id, contact_id, talk_ratio, word_count, question_count, interruption_count, longest_monologue_seconds)
VALUES (?, ?, ?, ?, ?, ?, ?);
```

**3e. Generate insights:**

Generate a **relationship pulse** (how is this relationship going, based on all historical data):
```sql
INSERT INTO communication_insights (transcript_id, contact_id, insight_type, content, sentiment)
VALUES (?, ?, 'relationship_pulse', ?, ?);
```

Generate a **coach note** (must reference a specific moment from THIS call):
```sql
INSERT INTO communication_insights (transcript_id, contact_id, insight_type, content, sentiment)
VALUES (?, ?, 'coach_note', ?, ?);
```

Check for **pattern alerts** (only if 3+ transcripts with same contact exist):
```sql
SELECT COUNT(*) FROM transcripts t
JOIN transcript_participants tp ON tp.transcript_id = t.id
WHERE tp.contact_id = ?;
```

**3f. Update relationship scores:**
```sql
INSERT INTO relationship_scores (contact_id, score_date, meeting_frequency, talk_ratio_avg, commitment_follow_through, relationship_depth, trajectory, notes)
VALUES (?, date('now'), ?, ?, ?, ?, ?, ?);
```

**3g. Log activity and create CRM interactions (if CRM installed):**
```sql
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('transcript', ?, 'imported', json_object('title', ?, 'participants', ?));

-- If CRM installed, log as interaction for each participant
INSERT INTO contact_interactions (contact_id, type, direction, subject, summary, occurred_at)
VALUES (?, 'meeting', 'outbound', ?, ?, ?);
```

## Step 4: Present Results

Use the narrative briefing style:

"Imported your **32-minute call** with **Sarah Chen** about the **rebrand project**.

**Commitments:** You said you'd **send the updated proposal by Friday** and **schedule a follow-up with design**. Sarah is going to **share the brand guidelines doc**.

**Relationship pulse:** This is your **6th meeting** this quarter. Conversations have shifted from project logistics to team concerns — that signals **growing trust**. Open commitment follow-through with Sarah is at **85%**.

**Coach's note:** You asked Sarah what worried her most about the timeline, then **stayed quiet while she worked through it**. That space led to the most productive part of the call. More of that."

End with: "Use `/commitments` to see all open items, or `/relationship-pulse Sarah` for the full picture."
