---
description: Surface what needs your attention — contacts going cold, overdue commitments, stale projects, and more
allowed-tools: ["Bash", "Read"]
---

# Nudges — What Needs Your Attention

This is proactive pattern detection — not a data dump. Scan all data and surface things that need attention, like a smart advisor saying "hey, you might want to look at this."

## Step 1: Check installed modules

Query the database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`:

```sql
SELECT name FROM modules WHERE enabled = 1;
```

## Step 2: Run all applicable checks

Only run checks for installed modules. Run all queries in a single efficient `sqlite3` heredoc call.

### Always check:

**Contacts going cold** — contacts with no activity in 30+ days that previously had regular activity:

```sql
SELECT c.name, c.company, c.email,
  MAX(al.created_at) as last_activity,
  CAST(julianday('now') - julianday(MAX(al.created_at)) AS INTEGER) as days_silent
FROM contacts c
JOIN activity_log al ON al.entity_type = 'contact' AND al.entity_id = c.id
WHERE c.status = 'active'
GROUP BY c.id
HAVING days_silent > 30
ORDER BY days_silent DESC
LIMIT 5;
```

### If CRM installed:

**Overdue follow-ups:**

```sql
SELECT f.reason, f.due_date, c.name as contact_name,
  CAST(julianday('now') - julianday(f.due_date) AS INTEGER) as days_overdue
FROM follow_ups f
JOIN contacts c ON c.id = f.contact_id
WHERE f.status = 'pending' AND f.due_date < date('now')
ORDER BY f.due_date ASC;
```

**Follow-ups due soon (next 3 days):**

```sql
SELECT f.reason, f.due_date, c.name as contact_name
FROM follow_ups f
JOIN contacts c ON c.id = f.contact_id
WHERE f.status = 'pending' AND f.due_date BETWEEN date('now') AND date('now', '+3 days')
ORDER BY f.due_date ASC;
```

### If Project Tracker installed:

**Stale projects** — active but no activity in 14+ days:

```sql
SELECT p.name, p.status, p.target_date,
  MAX(al.created_at) as last_activity,
  CAST(julianday('now') - julianday(MAX(al.created_at)) AS INTEGER) as days_stale
FROM projects p
LEFT JOIN activity_log al ON al.entity_type = 'project' AND al.entity_id = p.id
WHERE p.status IN ('active', 'planning')
GROUP BY p.id
HAVING days_stale > 14 OR last_activity IS NULL
ORDER BY days_stale DESC;
```

**Overdue tasks:**

```sql
SELECT t.title, t.due_date, p.name as project_name,
  CAST(julianday('now') - julianday(t.due_date) AS INTEGER) as days_overdue
FROM tasks t
JOIN projects p ON p.id = t.project_id
WHERE t.status NOT IN ('done') AND t.due_date < date('now')
ORDER BY t.due_date ASC
LIMIT 8;
```

**Projects approaching target date (within 7 days):**

```sql
SELECT p.name, p.target_date,
  (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status != 'done') as open_tasks
FROM projects p
WHERE p.status = 'active' AND p.target_date BETWEEN date('now') AND date('now', '+7 days');
```

### If Conversation Intelligence installed:

**Overdue commitments:**

```sql
SELECT com.description, com.deadline_date,
  CASE WHEN com.is_user_commitment = 1 THEN 'You' ELSE c.name END as owner,
  CAST(julianday('now') - julianday(com.deadline_date) AS INTEGER) as days_overdue
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
WHERE com.status IN ('open', 'overdue') AND com.deadline_date < date('now')
ORDER BY com.deadline_date ASC;
```

**Commitments due soon (next 3 days):**

```sql
SELECT com.description, com.deadline_date,
  CASE WHEN com.is_user_commitment = 1 THEN 'You' ELSE c.name END as owner
FROM commitments com
LEFT JOIN contacts c ON c.id = com.owner_contact_id
WHERE com.status = 'open' AND com.deadline_date BETWEEN date('now') AND date('now', '+3 days');
```

### If Decision Log installed:

**Decisions without outcomes (older than 90 days):**

```sql
SELECT d.title, d.decided_at,
  CAST(julianday('now') - julianday(d.decided_at) AS INTEGER) as days_ago
FROM decisions d
WHERE d.status = 'decided' AND d.outcome IS NULL
  AND julianday('now') - julianday(d.decided_at) > 90
ORDER BY d.decided_at ASC;
```

### If Calendar installed:

**Today's meetings (prep reminder):**

```sql
SELECT title, start_time, attendees, location
FROM calendar_events
WHERE date(start_time) = date('now') AND status != 'cancelled'
ORDER BY start_time ASC;
```

## Step 3: Present Results

Group findings by urgency:

**Red — Needs attention now** (overdue items)
- Overdue follow-ups, overdue commitments, overdue tasks

**Yellow — Coming up** (next 3 days)
- Follow-ups due soon, commitments due soon, approaching deadlines, today's meetings

**Blue — Worth checking in on** (patterns)
- Contacts going cold, stale projects, decisions without outcomes

Present each nudge as a concise, actionable sentence. Examples:

- "**Jake Morrison** has gone quiet — 34 days since your last interaction. Usually you connect weekly."
- "You committed to **send Sarah the updated proposal** 5 days ago — still open."
- "The **Meridian Rebrand** has had no activity in 18 days."
- "2 decisions from December have no recorded outcome. Run `/decision revisit` to check in."

End with a count: "**3 urgent, 2 upcoming, 4 worth a look.** Run any command above to take action."

If nothing needs attention: "All clear. No overdue items, no cold contacts, projects are moving. Nice work."

**Style:** Direct, concise, actionable. Each nudge should suggest what to do about it. Don't use emoji in the actual nudges — use the colored markers only for the section headers.
