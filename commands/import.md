---
description: Import data from any source — paste text, provide a file path, or describe what to import
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: [paste data directly, or provide a file path, or just say what you want to import]
---

# Import Data

The user wants to import data into Software of You. Their input: $ARGUMENTS

You are an expert at parsing unstructured data into structured records. The user can provide data in ANY format — your job is to figure out what it is, extract the right fields, and insert it into the correct tables.

## Step 1: Determine the Input Type

- **Pasted text in the arguments** → Parse it directly
- **A file path** → Read the file first, then parse its contents
- **No arguments** → Ask the user: "What would you like to import? You can paste contacts, project lists, notes — anything. Or give me a file path to a CSV, text file, or vCard."

Supported input formats (non-exhaustive — handle anything reasonable):
- Freeform text (email signatures, LinkedIn profiles, business card text, meeting notes)
- CSV or TSV data (with or without headers)
- vCard files (.vcf)
- JSON data
- Markdown lists or tables
- Email headers/threads
- Pasted spreadsheet rows
- Multiple records at once (batch import)

## Step 2: Dispatch Decision

**Count the records** in the input (estimate if needed).

**If ≤ 3 records** → Handle inline (proceed to Step 3 directly).

**If > 3 records OR a file path is provided** → Delegate to a sub-agent:

> "Got it — [N records / file]. Handing this to a focused import agent. I'll have results in a moment."

Spawn a sub-agent (use the `general-purpose` agent type) with this prompt:

```
You are a data import specialist for Software of You, a personal data platform backed by SQLite.

DATABASE: /Users/kmo/.local/share/software-of-you/soy.db (use sqlite3 CLI)
DB COMMAND: sqlite3 "/Users/kmo/.local/share/software-of-you/soy.db"

INPUT DATA:
[paste the full raw input here]

YOUR JOB:
1. Identify entity types (contacts, projects, tasks, notes, interactions)
2. Map fields to schema (see field mapping rules below)
3. Check for duplicates before inserting:
   SELECT id, name, email FROM contacts WHERE name LIKE '%<name>%' OR email = '<email>';
4. Insert each record with activity_log in one transaction
5. Return a structured summary: how many inserted, how many skipped (duplicates), any errors

FIELD MAPPING:
Contacts: name, email, phone, company, role, notes, type ('person'|'company')
Projects: name, description, status (idea/planning/active/paused/completed/cancelled), priority (low/medium/high/urgent), target_date, client_id
Tasks: title, description, status (todo/in_progress/done), priority, due_date, project_id
Notes: content, entity_type, entity_id

RULES:
- Use INSERT OR IGNORE for contacts (dedup by email)
- Always INSERT into activity_log after each record:
  INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
  VALUES ('<type>', last_insert_rowid(), 'created', json_object('source','import'), datetime('now'));
- Set updated_at = datetime('now') on all records
- For ambiguous duplicates (same name, different email), flag them — do not auto-merge
- Return results as: INSERTED: N, SKIPPED: N, FLAGGED: [list of ambiguous records]
```

Wait for the sub-agent to complete. Present its results as the Step 5 summary.

---

## Step 3: Identify What the Data Is

*(Only reached for ≤ 3 records or when handling inline)*

Look at the data and determine which entity type(s) it contains:

**Contacts** — look for: names, emails, phone numbers, company names, job titles, LinkedIn URLs, addresses
**Projects** — look for: project names, descriptions, status, deadlines, client references
**Tasks** — look for: task titles, assignments, due dates, priorities, project references
**Notes** — look for: freeform text about a person or project
**Interactions** — look for: meeting notes, call summaries, email threads with dates and participants

A single import can contain multiple entity types. For example, a meeting note might contain a new contact AND an interaction AND follow-up items.

## Step 4: Map Fields

Map the extracted data to the database schema. Be flexible with field names:

**Contact field mapping:**
- "Full Name" / "Name" / "Contact" → `name`
- "Email" / "E-mail" / anything@domain → `email`
- "Phone" / "Mobile" / "Cell" → `phone`
- "Company" / "Organisation" / "Org" → `company`
- "Title" / "Role" / "Position" → `role`
- Company entity (not a person) → `type = 'company'`

**Project field mapping:**
- "Project" / "Name" → `name`
- "Client" / "Customer" → look up contact by name, set `client_id`
- "Status" / "State" → idea, planning, active, paused, completed, cancelled
- "Priority" → low, medium, high, urgent
- "Due" / "Deadline" / "Target" → `target_date`

**Handle duplicates:** Before inserting a contact, check:
```sql
SELECT id, name, email FROM contacts WHERE name LIKE ? OR email = ?;
```
If a match is found, ask: "I found an existing contact [name]. Update it with the new info, or create a separate entry?"

## Step 5: Insert + Confirm

Use the database at `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`.

For each record, run INSERT and activity_log in one call:
```sql
INSERT INTO contacts (name, email, phone, company, role, updated_at)
VALUES (?, ?, ?, ?, ?, datetime('now'));
INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
VALUES ('contact', last_insert_rowid(), 'created', json_object('name', ?, 'source', 'import'), datetime('now'));
```

After all inserts, present a clear summary:

```
Imported 3 contacts (1 skipped — duplicate):

| Name | Company | Email |
|------|---------|-------|
| Jane Smith | Acme Corp | jane@acme.com |
| Bob Johnson | Widgets Inc | bob@widgets.io |

Want to tag these, add notes, or link them to a project?
```

If the sub-agent flagged ambiguous records, present those separately and ask the user to resolve them one at a time.
