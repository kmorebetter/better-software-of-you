---
description: View, search, and triage your Gmail inbox
allowed-tools: ["Bash", "Read"]
argument-hint: [inbox | unread | search <query> | from <name> | summary]
---

# Gmail

Read and triage emails from the user's Gmail account. Database at `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`.

## Step 1: Check Authentication

Get a valid access token:
```
ACCESS_TOKEN=$(python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/google_auth.py" token)
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

**Update the sync timestamp** so other commands know data is fresh:
```sql
INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('gmail_last_synced', datetime('now'), datetime('now'));
```

## Step 6: Present as a Natural Language Briefing

**Do NOT show a table of emails.** Instead, synthesize the emails into a conversational briefing — like a personal assistant summarizing your inbox. The style should be warm, scannable, and actionable.

### Format

Write a natural paragraph that weaves together the key emails. Use **bold** for the important keywords, topics, and names so the user can scan quickly. Use regular weight for connecting context.

### Example Output

"Hi Kerry, you have **onboarding tasks** and **interview updates** for the FinOps role, newly shared **sales proposals** to review, and **meeting notes** from a technician interview, while **Gigi Presentey** granted you access to finance resources and **BMO** provided a **lending timeline** for Benji's."

### Rules

- Lead with the user's name if known (check contacts or Google account info)
- Group related emails into themes, don't list them one by one
- Bold the **key topics**, **action items**, **people**, and **organizations**
- Keep connecting text in normal weight for flow and context
- Mention who sent important items by name (use contact names from the database when available, not just email addresses)
- Prioritize: action-required items first, FYI items second, newsletters/noise last (or skip noise entirely)
- Keep it to 2-4 sentences for a typical inbox check
- End with a suggestion if there's something urgent: "You might want to reply to the BMO timeline first — it looks time-sensitive."

### When the user asks for more detail

If they ask about a specific email or thread ("tell me more about the BMO email"), then show the full subject, sender, date, and snippet/body preview. But the default view is always the narrative summary.

## "from <name>" Shortcut

When the user says `/gmail from Jane`:
1. Look up Jane in contacts: `SELECT email FROM contacts WHERE name LIKE '%Jane%';`
2. Search Gmail for emails from that address
3. Summarize in narrative form: "From **Jane Smith**, you have a reply about the **design specs** from earlier today and a **project timeline** she shared on Monday."
