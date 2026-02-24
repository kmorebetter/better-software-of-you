---
description: Scan for Gemini meeting transcripts, list pending, or analyze them
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: [scan | pending | analyze <id> | analyze-all]
---

# Sync Gemini Meeting Transcripts

Automatically detect Gemini note-taker emails, fetch the full Google Doc transcript, and optionally run the full analysis pipeline. Database at `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`.

## Determine Action

Parse $ARGUMENTS:
- **"scan"** or no arguments → Step 1 (Scan)
- **"pending"** → Step 2 (Pending)
- **"analyze <id>"** → Step 3 (Analyze single)
- **"analyze-all"** → Step 4 (Analyze all pending)

---

## Step 1: Scan for New Transcripts

Run:
```
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/sync_transcripts.py" scan
```

Parse the JSON output.

**If `needs_reauth` is true:** Tell the user: "I need Google Docs access to fetch transcripts. Let me re-authorize your Google account." Then run the `/google-setup` flow.

**If `imported > 0`:** Present results conversationally:
- "Found **N new meeting transcripts** from Gemini."
- List each with title and date
- "Run `/sync-transcripts analyze <id>` to get the full analysis, or `/sync-transcripts analyze-all` to process them all."

**If `imported == 0`:** "No new Gemini transcripts found. Your Gmail is up to date."

**If errors:** Mention any failures briefly — "Couldn't fetch 1 doc (permission error)" etc.

---

## Step 2: List Pending Transcripts

Run:
```
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/sync_transcripts.py" pending
```

Present the list:
- "You have **N unanalyzed meeting transcripts:**"
- Table with ID, title, date
- "Use `/sync-transcripts analyze <id>` to analyze one, or `analyze-all` for all of them."

If none pending: "All transcripts have been analyzed. You're caught up."

---

## Step 3: Analyze Single Transcript

Fetch the raw text:
```
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/sync_transcripts.py" get <id>
```

Then follow the **exact same analysis pipeline as `/import-call`**, starting from Step 2 (Identify Participants). The raw text from the Google Doc IS the transcript. Specifically:

1. **Identify participants** — parse speaker labels, match to contacts, ask user to confirm
2. **Save participants** to `transcript_participants`
3. **Extract commitments** to `commitments` table
4. **Calculate metrics** (word count, talk ratio, question count, etc.) — show your work
5. **Generate insights** (relationship pulse, coach note, pattern alerts)
6. **Update relationship scores**
7. **Extract call intelligence** (org intel, pain points, tech stack, key concerns)
8. **Log activity** and create CRM interactions
9. **Mark as processed:**
   ```sql
   UPDATE transcripts SET processed_at = datetime('now') WHERE id = <id>;
   ```
10. **Present results** using the same format as `/import-call` Step 4

---

## Step 4: Analyze All Pending

Run the pending check first:
```
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/sync_transcripts.py" pending
```

If none pending, say so and stop.

Otherwise, iterate through each pending transcript and run the Step 3 analysis pipeline for each. Process them **sequentially** (each analysis is a full LLM pass with user interaction for participant matching).

After all are done: "Analyzed **N transcripts**. Use `/commitments` to see all open items."
