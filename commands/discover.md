---
description: Discover frequent email contacts who aren't in your CRM yet — find who's missing from your network
allowed-tools: ["Bash", "Read"]
---

# Contact Discovery

Scan your synced emails for people you interact with frequently who aren't tracked as contacts yet. Surfaces the top candidates based on email volume, recency, and whether they appear in calendar events.

**Requires:** Gmail module installed and synced.

## Step 1: Check Prerequisites

```sql
SELECT name FROM modules WHERE enabled = 1;
```

If the results do not include `gmail`, tell the user: "Contact discovery requires Gmail to be connected. Run `/google-setup` to get started."

Also check if there are any emails synced:
```sql
SELECT COUNT(*) FROM emails;
```

If zero emails, tell the user: "No emails synced yet. Run `/gmail` to pull in your recent messages first."

## Step 2: Find Unknown Senders — Use Computed View

All discovery candidate data comes from the `v_discovery_candidates` view (defined in `data/migrations/014_computed_views.sql`). This view pre-computes email counts, thread counts, recency, and relevance scores — Claude does NOT calculate these values.

```sql
-- All candidates with pre-computed scores
SELECT from_address, from_name, email_count, thread_count,
  last_email, first_email, days_since_last, relevance_score
FROM v_discovery_candidates
LIMIT 15;
```

Also check for two-way communication. For each candidate, check if you've also sent them emails (boosts their score):

```sql
-- Check outbound emails to discovered addresses
SELECT e.to_addresses, COUNT(*) as outbound_count
FROM emails e
WHERE e.direction = 'outbound'
  AND e.contact_id IS NULL
GROUP BY e.to_addresses;
```

Note: `to_addresses` may contain multiple comma-separated recipients. When checking for two-way communication, parse each discovered inbound address and check if it appears anywhere in the outbound `to_addresses` values using LIKE matching (`to_addresses LIKE '%' || ? || '%'`), not exact equality.

Check calendar events for attendees not in contacts (if `calendar` module is in the installed modules list from Step 1):
```sql
SELECT attendees FROM calendar_events
WHERE start_time > datetime('now', '-30 days')
  AND attendees IS NOT NULL AND attendees != '';
```

Parse attendee emails from these events and cross-reference against `contacts.email`. Any emails that appear in calendar events AND in the email results above are especially strong candidates — they're people you both email and meet with.

## Step 3: Score and Rank Candidates

The `v_discovery_candidates` view pre-computes a `relevance_score` for each candidate based on:

- **Email volume**: +1 per email (capped at 10)
- **Thread diversity**: +2 per distinct thread (capped at 10)
- **Recency**: +5 if last email within 7 days, +3 if within 14 days, +1 if within 30 days

Add these bonuses based on Step 2 cross-referencing (not in the view):
- **Calendar presence**: +5 if they appear in any calendar event
- **Two-way communication**: +3 if you have both inbound and outbound emails

Sort by adjusted score descending. Present the top 10.

## Step 4: Present Results

Show results conversationally, not as raw data. Format as a markdown table:

```
## People You Might Want to Track

| # | Name / Email | Emails | Last Contact | Why Add? |
|---|-------------|--------|-------------|----------|
| 1 | Alex Rivera (alex@meridian.co) | 8 emails, 4 threads | 2 days ago | Frequent + recent + in calendar |
| 2 | jen@acmecorp.com | 5 emails, 3 threads | 5 days ago | Active two-way conversation |
| 3 | Tom Walsh (tom@ext.io) | 4 emails, 2 threads | 12 days ago | Calendar attendee |
```

**For each candidate:**
- Show `from_name` if available, otherwise just the email
- Show email count and thread count
- Show how long ago the last email was (human-readable)
- Show a brief "Why add?" reason based on the scoring factors

**After the table, prompt action:**

> Want to add any of these? Just say "Add #1" or "Add Alex Rivera as a contact" and I'll create them with the email pre-filled.

## Step 5: Handle Add Requests

If the user responds with "add #N" or mentions a name/email from the results:

Use `from_name` as the name if available. If only an email exists, ask the user for the name.

**All of the following must run in a single `sqlite3` heredoc call** (required for `last_insert_rowid()` to work correctly):

```sql
-- Insert contact, link emails, and log activity — all in one call
INSERT INTO contacts (name, email, status, created_at, updated_at)
VALUES (?, ?, 'active', datetime('now'), datetime('now'));

UPDATE emails SET contact_id = last_insert_rowid()
WHERE from_address = ? AND contact_id IS NULL;

UPDATE emails SET contact_id = (SELECT id FROM contacts WHERE email = ?)
WHERE to_addresses LIKE '%' || ? || '%' AND contact_id IS NULL;

INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
VALUES ('contact', (SELECT id FROM contacts WHERE email = ?), 'contact_created', 'Added via contact discovery from email history', datetime('now'));
```

Note: The outbound email UPDATE uses LIKE matching because `to_addresses` may contain multiple comma-separated recipients. The activity_log uses a subquery instead of `last_insert_rowid()` since the UPDATEs run between the INSERT and the log.

After running, count the linked emails:
```sql
SELECT COUNT(*) FROM emails WHERE contact_id = (SELECT id FROM contacts WHERE email = ?);
```

Tell the user: "Added **{name}** and linked {N} existing emails to their profile."

Then suggest: "Want to add more, or run `/entity-page {name}` to see what I know about them?"
