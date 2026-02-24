---
description: Write daily journal entries with automatic cross-referencing to your contacts, projects, and events
allowed-tools: ["Bash", "Read"]
argument-hint: <journal entry text, or "today" or "week" or "read <date>">
---

# Journal

Handle journal operations based on $ARGUMENTS. Database at `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`.

## Determine the Operation

Parse the arguments to figure out what the user wants:

- **No arguments** → Check if today has an entry. If yes, show it. If no, prompt: "No entry for today yet. How's your day going?"
- **"today"** → Show today's entry (or prompt to write one)
- **"week"** → Weekly review / synthesis of last 7 days
- **"read <date or relative>"** → Show entry for that date ("yesterday", "last monday", "feb 10", "2026-02-14")
- **Anything else that looks like journal text** → Write a new entry
- **A short term that doesn't match the above** → Search journal entries

## Write an Entry

The user writes naturally. Claude processes the raw text into structured data.

### 1. Store the full content as-is

The `content` field gets the user's exact words, unedited.

### 2. Extract mood

Infer from the language. Examples:
- "rough", "hard", "exhausting" → "rough"
- "great", "amazing", "on fire" → "great"
- "calm", "steady", "fine" → "calm"
- "anxious", "stressed", "overwhelmed" → "anxious"
- Mixed signals like "rough but optimistic" → pick the dominant one, but note the nuance when confirming

Store as free text in `mood`.

### 3. Extract energy level

Map language to 1-5 scale:
- "drained", "exhausted", "wiped" → 1
- "low energy", "tired" → 2
- "fine", "okay", "normal" → 3
- "good energy", "productive" → 4
- "fired up", "buzzing", "unstoppable" → 5

If energy is not mentioned, leave NULL.

### 4. Extract highlights

Pull out the key moments, events, or takeaways as a JSON array of short strings. These should be concrete, not abstract. Example:

Input: "today was rough, back-to-back meetings with the Meridian team, but the call with Sarah went really well. Feeling optimistic about the rebrand."

Highlights: `["Back-to-back meetings with Meridian team", "Great call with Sarah", "Feeling optimistic about rebrand"]`

### 5. Cross-reference contacts

Search the contacts table for any names or companies mentioned in the entry:

```sql
SELECT id, name, company FROM contacts WHERE status = 'active';
```

Match contact names against the entry text (case-insensitive, first name matching is fine). Store matching contact IDs as a JSON array in `linked_contacts`. If no matches, store NULL.

### 6. Cross-reference projects

Search the projects table for any project names or topics mentioned:

```sql
SELECT id, name, status FROM projects;
```

Match project names against the entry text (case-insensitive, partial matching is fine — "rebrand" matches "Meridian Rebrand"). Store matching project IDs as a JSON array in `linked_projects`. If no matches, store NULL.

### 7. Set entry_date

- Default to today's date
- "yesterday" → subtract 1 day
- Specific date references → parse to YYYY-MM-DD

### 8. Auto-context from calendar (if calendar module installed)

Check if the calendar module is installed:

```sql
SELECT name FROM modules WHERE name = 'calendar' AND enabled = 1;
```

If installed, check today's meetings:

```sql
SELECT title, start_time, attendees FROM calendar_events
WHERE date(start_time) = date('now')
ORDER BY start_time;
```

Mention relevant meetings in the confirmation. Offer to add context from them.

### 9. Insert the entry

Run both statements in a single sqlite3 call:

```sql
INSERT INTO journal_entries (content, mood, energy, highlights, entry_date, linked_contacts, linked_projects, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'));
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('journal_entry', last_insert_rowid(), 'created', json_object('entry_date', ?, 'mood', ?));
```

### 10. Confirm naturally

Reflect the user's tone. Don't be artificially cheerful if they said the day was rough. Mention linked contacts and projects casually. Example:

"Journaled for today. Mood: rough but optimistic. Linked to Sarah Chen and the Meridian Rebrand project. You had 3 meetings today — sounds like a full day."

Suggest: "Want to add anything else, or read back your week so far?"

## Read Today's Entry

```sql
SELECT je.*,
  (SELECT json_group_array(c.name) FROM contacts c WHERE c.id IN (SELECT value FROM json_each(je.linked_contacts))) as contact_names,
  (SELECT json_group_array(p.name) FROM projects p WHERE p.id IN (SELECT value FROM json_each(je.linked_projects))) as project_names
FROM journal_entries je
WHERE je.entry_date = date('now')
ORDER BY je.created_at DESC;
```

Present warmly with mood, energy (as a visual if present — e.g., "Energy: 2/5"), highlights as bullet points, and linked contacts/projects.

If multiple entries exist for today, show all of them in chronological order.

If no entry exists: "No entry for today yet. How's your day going?"

## Read a Specific Date

Resolve relative dates:
- "yesterday" → `date('now', '-1 day')`
- "last monday" → calculate the date
- "feb 10" → resolve to `YYYY-MM-DD` using the current year (or most recent past occurrence)

```sql
SELECT je.*,
  (SELECT json_group_array(c.name) FROM contacts c WHERE c.id IN (SELECT value FROM json_each(je.linked_contacts))) as contact_names,
  (SELECT json_group_array(p.name) FROM projects p WHERE p.id IN (SELECT value FROM json_each(je.linked_projects))) as project_names
FROM journal_entries je
WHERE je.entry_date = ?
ORDER BY je.created_at;
```

If no entry for that date, find the nearest entries:

```sql
SELECT entry_date, substr(content, 1, 80) as preview, mood
FROM journal_entries
ORDER BY ABS(julianday(entry_date) - julianday(?))
LIMIT 3;
```

Show: "No entry for [date]. Here are your nearest entries:" with dates and previews.

## Weekly Review

Query the last 7 days:

```sql
SELECT je.*,
  (SELECT json_group_array(c.name) FROM contacts c WHERE c.id IN (SELECT value FROM json_each(je.linked_contacts))) as contact_names,
  (SELECT json_group_array(p.name) FROM projects p WHERE p.id IN (SELECT value FROM json_each(je.linked_projects))) as project_names
FROM journal_entries je
WHERE je.entry_date >= date('now', '-7 days')
ORDER BY je.entry_date, je.created_at;
```

**Synthesize a narrative, not a data dump.** Cover:

- **Mood arc** — how did the week feel overall? Any shifts?
- **Energy trend** — average, highs, lows
- **Top contacts** — who showed up most in your week?
- **Top projects** — what dominated your attention?
- **Highlights reel** — the standout moments across the week
- **Pattern notes** — anything recurring worth calling out?

Example tone: "This week started rough (Monday-Tuesday, low energy, heavy meeting load) but picked up Wednesday after the Sarah call. You mentioned the rebrand in 4 of 5 entries — it's clearly top of mind. Energy averaged 3/5. Highlight of the week: landing the client pitch on Thursday."

If fewer than 3 entries exist, note it: "Only 2 entries this week — not much to synthesize yet, but here's what you've captured."

## Search Entries

If $ARGUMENTS doesn't match a command keyword ("today", "week", "read"), search for it:

```sql
SELECT id, entry_date, mood, energy, substr(content, 1, 120) as preview, highlights
FROM journal_entries
WHERE content LIKE '%term%' OR highlights LIKE '%term%' OR mood LIKE '%term%'
ORDER BY entry_date DESC
LIMIT 10;
```

Present results with dates, mood, and a content snippet. If no results: "No journal entries mention '[term]'. Try a different search, or write a new entry?"

## Style Notes

- The journal should feel personal and reflective, not transactional
- When confirming writes, reflect the user's tone — match their energy
- Multiple entries per day are fine — append, don't overwrite existing entries
- Cross-referencing is automatic but understated — mention linked entities casually
- Always log to activity_log for every write operation
- Dates in human-readable format ("last Tuesday", "3 days ago")
