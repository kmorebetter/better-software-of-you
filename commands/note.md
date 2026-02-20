---
description: Add a note — standalone or attached to a contact/project. List, search, and pin notes.
allowed-tools: ["Bash", "Read"]
argument-hint: <note content> or <entity name> <note> or list | search <term> | pin <id>
---

# Note

Handle note operations based on $ARGUMENTS. Database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

## Determine the Operation

Parse the arguments to figure out what the user wants:

- **"list"** or **"recent"** → List recent standalone notes
- **"search \<term\>"** → Search standalone notes
- **"pin \<id\>"** → Toggle pin on a standalone note
- **First words match an entity name** → Attach note to that entity (existing behavior)
- **Anything else** → Create a standalone note

## Operation: List Recent Notes

Check if the notes module is installed:
```sql
SELECT name FROM modules WHERE name = 'notes' AND enabled = 1;
```

If not installed, tell the user: "Notes module is not installed. Run `/add-module notes` to enable it."

Query recent standalone notes:
```sql
SELECT sn.id, sn.title, substr(sn.content, 1, 120) as preview, sn.tags, sn.pinned,
  sn.created_at,
  (SELECT json_group_array(c.name) FROM contacts c WHERE sn.linked_contacts LIKE '%' || c.id || '%') as contact_names,
  (SELECT json_group_array(p.name) FROM projects p WHERE sn.linked_projects LIKE '%' || p.id || '%') as project_names
FROM standalone_notes sn
ORDER BY sn.pinned DESC, sn.created_at DESC
LIMIT 20;
```

Present as a table with: ID, title/preview, tags, linked entities, pinned status, age. Pinned notes show first with a pin indicator.

Suggest: "Use `/note search <term>` to find specific notes, or `/note pin <id>` to pin one."

## Operation: Search Notes

Check that the notes module is installed (same query as above).

```sql
SELECT sn.id, sn.title, substr(sn.content, 1, 120) as preview, sn.tags, sn.pinned,
  sn.created_at,
  (SELECT json_group_array(c.name) FROM contacts c WHERE sn.linked_contacts LIKE '%' || c.id || '%') as contact_names,
  (SELECT json_group_array(p.name) FROM projects p WHERE sn.linked_projects LIKE '%' || p.id || '%') as project_names
FROM standalone_notes sn
WHERE sn.content LIKE '%<term>%'
  OR sn.title LIKE '%<term>%'
  OR sn.tags LIKE '%<term>%'
ORDER BY sn.pinned DESC, sn.created_at DESC
LIMIT 20;
```

Present results with highlighted context. If no results: "No notes match '<term>'. Try a different search?"

## Operation: Toggle Pin

Check that the notes module is installed.

```sql
UPDATE standalone_notes SET pinned = CASE WHEN pinned = 1 THEN 0 ELSE 1 END, updated_at = datetime('now') WHERE id = <id>;
```

Then confirm:
```sql
SELECT id, title, substr(content, 1, 60) as preview, pinned FROM standalone_notes WHERE id = <id>;
```

Report: "Note #X [pinned/unpinned]." with a preview of the note.

Log the action:
```sql
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('standalone_note', <id>, 'pin_toggled', json_object('pinned', <new_value>));
```

## Operation: Attach Note to Entity (existing behavior)

If the first words of $ARGUMENTS match a known entity name, attach a note to that entity.

Search the database for matching entities:
- Search contacts by name: `SELECT id, name FROM contacts WHERE name LIKE '%<first_words>%';`
- If project-tracker installed, search projects: `SELECT id, name FROM projects WHERE name LIKE '%<first_words>%';`
- If ambiguous, ask the user to clarify

Once the entity is identified, the remainder of $ARGUMENTS (after the entity name) is the note content.

```sql
INSERT INTO notes (entity_type, entity_id, content) VALUES (?, ?, ?);
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES (?, ?, 'note_added', json_object('preview', substr(?, 1, 100)));
```

Confirm: "Note added to [entity type] '[entity name]'."

## Operation: Create Standalone Note

Check if the notes module is installed. If not, fall back to the "Attach Note to Entity" operation — try to match an entity, or tell the user to install the notes module.

### 1. Extract title

If the first sentence is short (< 60 chars) and the rest is longer, use the first sentence as the title. Otherwise, auto-generate a title from the first ~50 characters of the content.

### 2. Extract #hashtags as tags

Pull any `#word` patterns from the content. Store as a JSON array of strings (without the `#`). Remove the hashtags from the stored content if they appear at the end of the text (leave inline hashtags).

### 3. Cross-reference contacts

```sql
SELECT id, name, company FROM contacts WHERE status = 'active';
```

Match contact names against the content (case-insensitive, first name matching is fine). Store matching contact IDs as a JSON array in `linked_contacts`. If no matches, store NULL.

### 4. Cross-reference projects

```sql
SELECT id, name FROM projects;
```

Match project names against the content (case-insensitive, partial matching is fine — "rebrand" matches "Meridian Rebrand"). Store matching project IDs as a JSON array in `linked_projects`. If no matches, store NULL.

### 5. Insert the note

Run both statements in a single sqlite3 call:

```sql
INSERT INTO standalone_notes (title, content, linked_contacts, linked_projects, tags)
VALUES (?, ?, ?, ?, ?);
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('standalone_note', last_insert_rowid(), 'created', json_object('title', ?, 'preview', substr(?, 1, 100)));
```

### 6. Confirm

"Note saved: '[title]'." Mention linked contacts and projects casually if any were detected. Mention extracted tags.

Suggest: "Use `/note list` to see your notes, or `/notes-view` to generate the full notes page."

## Disambiguation

When arguments could be either a standalone note or an entity-attached note, use this priority:

1. If the notes module is NOT installed → always try to attach to an entity
2. If arguments start with "list", "recent", "search", "pin" → those operations
3. If the first 1-3 words exactly match a contact or project name → attach to that entity
4. Otherwise → create a standalone note

## Style Notes

- Notes should feel quick and effortless — capture first, organize later
- Cross-referencing is automatic and understated
- Tags are extracted, not forced — only pull #hashtags that the user explicitly wrote
- Always log to activity_log for every write operation
- Dates in human-readable format
