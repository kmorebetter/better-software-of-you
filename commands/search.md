---
description: Natural language search across all your data
allowed-tools: ["Bash", "Read"]
argument-hint: <what you're looking for>
---

# Natural Language Search

The user wants to search their Software of You data. Their query: $ARGUMENTS

Translate their natural language query into SQL against `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

## Available Tables

**Always available:** contacts, tags, entity_tags, notes, activity_log, modules

**If CRM module installed:** contact_interactions, contact_relationships, follow_ups

**If Project Tracker installed:** projects, tasks, milestones

**If Gmail module installed:** emails (subject, snippet, from_address, from_name, to_addresses, date, is_read, label_ids)

**If Calendar module installed:** calendar_events (title, description, attendees, location, start_time, end_time, status)

**If Conversation Intelligence module installed:** transcripts (title, summary, raw_text, source, recorded_at), commitments (description, status, due_date, contact_id), communication_insights (content, insight_type, contact_id)

Check which modules are installed first: `SELECT name FROM modules WHERE enabled = 1;`

## Search Strategy

1. Parse the user's intent
2. Construct appropriate SQL (use LIKE for text, JOINs for relationships)
3. Search across all relevant tables — cast a wide net
4. Present results with context, grouped by entity type

## Examples

- "Who works at Acme?" → search contacts by company
- "What's overdue?" → check projects past target_date, tasks past due_date, follow_ups past due_date
- "Everything about John" → contacts matching John + their notes, interactions, projects, tasks
- "What happened last week?" → activity_log for the past 7 days
- "Show me my VIP clients" → contacts with 'vip' tag

**Email searches (Gmail module):**
- "emails from Sarah" → `WHERE from_address LIKE '%sarah%' OR from_name LIKE '%sarah%'`
- "emails about the proposal" → `WHERE subject LIKE '%proposal%' OR snippet LIKE '%proposal%'`
- "unread emails" → `WHERE is_read = 0`

**Calendar searches (Calendar module):**
- "meetings next week" → `WHERE start_time BETWEEN date('now') AND date('now', '+7 days')`
- "meetings with John" → `WHERE attendees LIKE '%john%' OR title LIKE '%john%'`
- "what's on my calendar today" → `WHERE date(start_time) = date('now')`

**Transcript & commitment searches (Conversation Intelligence module):**
- "what did Sarah commit to?" → search commitments JOIN contacts WHERE contacts.name LIKE '%sarah%'
- "coaching notes" → search communication_insights WHERE insight_type = 'coach_note'
- "transcript about onboarding" → `WHERE title LIKE '%onboarding%' OR summary LIKE '%onboarding%'`
- "open commitments" → search commitments WHERE status != 'completed'

If nothing found, say so clearly and suggest alternative searches or broader terms.
