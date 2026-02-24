---
description: Compose and send an email through Gmail
allowed-tools: ["Bash", "Read"]
argument-hint: <contact name or email> [subject or context]
---

# Send Email

Compose and send an email through the user's Gmail account. **Always show the draft and get explicit confirmation before sending.**

## Step 1: Check Authentication

```
ACCESS_TOKEN=$(python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/google_auth.py" token)
```

If this fails: "Gmail isn't connected. Run `/google-setup` first."

## Step 2: Resolve the Recipient

Parse $ARGUMENTS for the recipient. Look up in the database at `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`:

```sql
SELECT id, name, email, company, role FROM contacts WHERE name LIKE ? OR email LIKE ?;
```

If multiple matches, ask the user to clarify. If no match but an email address was provided, use it directly.

## Step 3: Gather Context

Before drafting, gather relevant context about this recipient:

```sql
-- Recent interactions
SELECT type, subject, summary, occurred_at FROM contact_interactions
WHERE contact_id = ? ORDER BY occurred_at DESC LIMIT 5;

-- Recent notes
SELECT content, created_at FROM notes
WHERE entity_type = 'contact' AND entity_id = ? ORDER BY created_at DESC LIMIT 3;

-- Pending follow-ups
SELECT reason, due_date FROM follow_ups
WHERE contact_id = ? AND status = 'pending';
```

If project-tracker installed:
```sql
SELECT name, status FROM projects WHERE client_id = ?
AND status IN ('active', 'planning');
```

If gmail module has cached emails:
```sql
SELECT subject, snippet, received_at FROM emails
WHERE contact_id = ? ORDER BY received_at DESC LIMIT 5;
```

## Step 4: Draft the Email

If the user provided subject/context in $ARGUMENTS, incorporate it. Otherwise, draft based on the gathered context.

Draft a professional email that:
- References recent interactions or context naturally
- Has a clear purpose
- Is concise (3-6 sentences for the body)
- Includes an appropriate subject line

## Step 5: Show Draft and Confirm

Present the draft clearly:

---
**To:** Jane Smith <jane@acme.com>
**Subject:** Following up on the design review

Hi Jane,

[body]

Best,
[user's name if known]

---

**Ask explicitly:** "Ready to send this? I can also revise it, change the tone, or add/remove details."

**Wait for the user to confirm.** Do NOT send without explicit approval.

## Step 6: Send via Gmail API

Only after user confirms, send the email:

Build the raw email in RFC 2822 format, base64url-encode it, and POST:

```bash
# Build the raw email
RAW_EMAIL=$(python3 -c "
import base64
msg = 'To: {to}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}'
print(base64.urlsafe_b64encode(msg.encode()).decode())
")

# Send
curl -s -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"raw\": \"$RAW_EMAIL\"}" \
  "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
```

## Step 7: Log the Interaction

After successful send, log it in the database:

```sql
INSERT INTO contact_interactions (contact_id, type, direction, subject, summary, occurred_at)
VALUES (?, 'email', 'outbound', ?, ?, datetime('now'));
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('contact', ?, 'email_sent', json_object('to', ?, 'subject', ?));
```

Confirm: "Email sent to [name]. Logged as an interaction."
