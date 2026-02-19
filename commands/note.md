---
description: Add a note to any contact, project, or entity
allowed-tools: ["Bash"]
argument-hint: <entity name> <note content>
---

# Add Note

Parse $ARGUMENTS to determine which entity the user wants to add a note to and what the note content is.

Search the database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db` for matching entities:
- Search contacts by name
- If project-tracker installed, search projects by name
- If ambiguous, ask the user to clarify

Once the entity is identified:

```sql
INSERT INTO notes (entity_type, entity_id, content) VALUES (?, ?, ?);
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES (?, ?, 'note_added', json_object('preview', substr(?, 1, 100)));
```

Confirm: "Note added to [entity type] '[entity name]'."
