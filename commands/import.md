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

## Step 2: Identify What the Data Is

Look at the data and determine which entity type(s) it contains:

**Contacts** — look for: names, emails, phone numbers, company names, job titles, LinkedIn URLs, addresses
**Projects** — look for: project names, descriptions, status, deadlines, client references
**Tasks** — look for: task titles, assignments, due dates, priorities, project references
**Notes** — look for: freeform text about a person or project
**Interactions** — look for: meeting notes, call summaries, email threads with dates and participants

A single import can contain multiple entity types. For example, a meeting note might contain a new contact AND an interaction AND follow-up items.

## Step 3: Map Fields

Map the extracted data to the database schema. Be flexible with field names:

**Contact field mapping (examples):**
- "Full Name" / "Name" / "Contact" / person's name → `name`
- "Email" / "E-mail" / "Email Address" / anything@domain → `email`
- "Phone" / "Mobile" / "Cell" / "Tel" / +1-xxx pattern → `phone`
- "Company" / "Organisation" / "Organization" / "Org" / "Employer" → `company`
- "Title" / "Role" / "Position" / "Job Title" → `role`
- If the data is clearly a company (not a person), set `type = 'company'`

**Project field mapping:**
- "Project" / "Project Name" / "Name" → `name`
- "Client" / "Customer" / "For" → look up contact by name, set `client_id`
- "Status" / "State" → map to: idea, planning, active, paused, completed, cancelled
- "Priority" / "Importance" → map to: low, medium, high, urgent
- "Due" / "Deadline" / "Target" / "Due Date" → `target_date`

**Handle duplicates:** Before inserting a contact, check if one with the same name or email already exists:
```sql
SELECT id, name, email FROM contacts WHERE name LIKE ? OR email = ?;
```
If a match is found, ask the user: "I found an existing contact [name]. Update it with the new info, or create a separate entry?"

## Step 4: Insert the Data

Use the database at `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`.

For each record, run the INSERT and activity_log together in one sqlite3 call:
```sql
INSERT INTO contacts (name, email, phone, company, role) VALUES (?, ?, ?, ?, ?);
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('contact', last_insert_rowid(), 'created', json_object('name', ?, 'source', 'import'));
```

For batch imports (multiple records), process them one at a time so each gets its own activity log entry.

## Step 5: Confirm

After importing, present a clear summary:

"Imported X contacts, Y projects, Z notes:

| Name | Company | Email |
|------|---------|-------|
| Jane Smith | Acme Corp | jane@acme.com |
| ... | ... | ... |

Want to tag these contacts, add notes, or link them to projects?"

## Examples of What Users Might Paste

**LinkedIn profile text:**
"Jane Smith · Head of Design at Acme Corp · San Francisco Bay Area · 500+ connections · jane.smith@acme.com"

**Email signature:**
"Best regards, Bob Johnson | CTO, Widgets Inc | bob@widgets.io | +1 (555) 123-4567 | widgets.io"

**CSV dump:**
"Name,Email,Company\nJane Smith,jane@acme.com,Acme Corp\nBob Johnson,bob@widgets.io,Widgets Inc"

**Messy freeform text:**
"Met Sarah at the conference - she's a PM at Google, sarah.connor@google.com, said she's interested in our API project. Also talked to Mike from Stripe (mike@stripe.com) about payments integration."

**Business card (OCR text):**
"ACME CORPORATION Jane Smith Head of Design jane@acme.com +1 555 867 5309 123 Main St, San Francisco CA"

All of these should be parseable. Extract what you can, ask about anything ambiguous.
