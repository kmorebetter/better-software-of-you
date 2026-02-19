---
description: View, search, and triage your Gmail inbox
allowed-tools: ["Bash", "Read"]
argument-hint: [inbox | unread | search <query> | from <name> | summary]
---

# Gmail

Read and triage emails from the user's Gmail account. Database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

## Step 1: Check Authentication

Get a valid access token:
```
ACCESS_TOKEN=$(python3 "${CLAUDE_PLUGIN_ROOT}/shared/google_auth.py" token)
```

If this fails, tell the user: "Gmail isn't connected yet. Run `/google-setup` to connect your Google account."

## Step 2: Determine the Operation

Parse $ARGUMENTS:

- **No arguments or "inbox"** → Show recent emails
- **"unread"** → Show unread emails only
- **"search <query>"** → Search Gmail
- **"from <name>"** → Look up contact email, search emails from them
- **"summary"** → AI summary of inbox state

## Step 3: Fetch Emails from Gmail API

Use curl with the access token to call the Gmail API:

**List recent messages:**
```bash
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=20&q=in:inbox"
```

**Get a specific message:**
```bash
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://gmail.googleapis.com/gmail/v1/users/me/messages/{id}?format=metadata&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Subject&metadataHeaders=Date"
```

**Search messages:**
```bash
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=20&q={query}"
```

## Step 4: Auto-Link to Contacts

For each email, check if the sender/recipient matches a known contact:
```sql
SELECT id, name, email FROM contacts WHERE email = ?;
```

If a match is found, store the `contact_id` when saving to the emails table.

## Step 5: Save to Local Database

Cache fetched emails locally for fast access and cross-module queries:
```sql
INSERT OR IGNORE INTO emails (gmail_id, thread_id, contact_id, direction, from_address, to_addresses, subject, snippet, is_read, received_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
```

## Step 6: Present Results

Show emails in a clean, scannable format:

| From | Subject | Date |
|------|---------|------|
| Jane Smith (Acme) | Re: Design specs | 2 hours ago |
| bob@widgets.io | API proposal | Yesterday |

- Bold unread messages
- Show contact name if linked (not just email address)
- Group by today / yesterday / this week if showing many
- For "summary": provide AI triage — what needs attention, what can wait, key threads

## "from <name>" Shortcut

When the user says `/gmail from Jane`:
1. Look up Jane in contacts: `SELECT email FROM contacts WHERE name LIKE '%Jane%';`
2. Search Gmail for emails from that address
3. Show results with full contact context
