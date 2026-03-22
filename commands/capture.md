---
description: Quick capture — write it down, route it later
allowed-tools: ["Bash", "Read", "Write"]
---

# Quick Capture

Capture whatever the user said after `/capture` into the inbox. Speed is everything — this should feel instant.

## Workflow

1. Take the user's input (everything after `/capture`) as the content. If empty, ask: "What do you want to capture?"

2. Extract #hashtags from the content:
   - Find all `#word` patterns
   - Store as JSON array: `["tag1", "tag2"]`

3. Match contact names against active contacts:
   ```sql
   SELECT id, name FROM contacts
   WHERE status = 'active'
     AND LENGTH(SUBSTR(name, 1, INSTR(name || ' ', ' ') - 1)) >= 3
     AND LOWER(SUBSTR(name, 1, INSTR(name || ' ', ' ') - 1)) IN (<extracted_words_lowered>);
   ```
   Store matches as JSON array: `[{"id": 5, "name": "Jake Smith"}]`
   Only match words with 3+ characters to avoid false positives.

4. Insert into the database (single sqlite3 call):
   ```bash
   sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" <<SQL
   INSERT INTO inbox (content, tags, matched_contacts, created_at, updated_at)
   VALUES ('<content_escaped>', '<tags_json>', '<contacts_json>', datetime('now'), datetime('now'));
   INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
   VALUES ('inbox', last_insert_rowid(), 'captured', 'Quick capture: <first 80 chars>', datetime('now'));
   SQL
   ```

5. Confirm to the user:
   - "Captured." (always)
   - If contacts matched: "I noticed you mentioned [Name] — want me to route this to their record?"
   - If content starts with "Decision:" or describes a choice: "This looks like a decision — want me to route it to the decision log?"
   - If content is reflective/emotional: "This reads like a journal entry — want me to route it there?"
   - Otherwise: just confirm, don't over-suggest

6. Do NOT sync data, generate views, or do anything else. Capture is fast and minimal.
