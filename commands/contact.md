---
description: Add, edit, list, or find contacts
allowed-tools: ["Bash", "Read"]
argument-hint: <name> [email] [company] or "list" or "find <query>"
---

# Contact Management

Handle contact operations based on $ARGUMENTS. Database at `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`.

## Determine the Operation

Parse the arguments to figure out what the user wants:

- **No arguments or "list"** → List contacts
- **"find <query>"** → Search contacts
- **A person's name (with optional email/company)** → Add a new contact
- **References an existing contact + changes** → Edit that contact

## Add a Contact

Extract name, email, company, role from the arguments (whatever is provided).

Run both statements in a single sqlite3 call (so `last_insert_rowid()` works correctly):

```sql
INSERT INTO contacts (name, email, company, role) VALUES (?, ?, ?, ?);
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('contact', last_insert_rowid(), 'created', json_object('name', ?));
```

Confirm with the contact details. Suggest: "Want to add a note, set a follow-up, or tag this contact?"

## List Contacts

```sql
SELECT id, name, company, email, status, updated_at
FROM contacts WHERE status = 'active'
ORDER BY updated_at DESC;
```

Present as a table if more than 2 results.

## Find/Search Contacts

```sql
SELECT id, name, company, email, role, status
FROM contacts
WHERE name LIKE '%query%' OR company LIKE '%query%' OR email LIKE '%query%' OR role LIKE '%query%';
```

## Edit a Contact

Look up the contact by name or ID, then update only the specified fields:

```sql
UPDATE contacts SET field = ?, updated_at = datetime('now') WHERE id = ?;
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('contact', ?, 'updated', json_object('field', ?, 'new_value', ?));
```

Confirm the changes.
