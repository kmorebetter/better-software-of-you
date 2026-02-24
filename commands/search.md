---
description: Natural language search across all your data
allowed-tools: ["Bash", "Read"]
argument-hint: <what you're looking for>
---

# Natural Language Search

The user wants to search their Software of You data. Their query: $ARGUMENTS

Translate their natural language query into SQL against `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`.

## Available Tables

**Always available:** contacts, tags, entity_tags, notes, activity_log, modules

**If CRM module installed:** contact_interactions, contact_relationships, follow_ups

**If Project Tracker installed:** projects, tasks, milestones

**If Gmail module installed:** emails (subject, snippet, from_address, from_name, to_addresses, date, is_read, label_ids)

**If Calendar module installed:** calendar_events (title, description, attendees, location, start_time, end_time, status)

**If Conversation Intelligence module installed:** transcripts (title, summary, raw_text, source, recorded_at), commitments (description, status, due_date, contact_id), communication_insights (content, insight_type, contact_id)

**If Decision Log module installed:** decisions (title, context, decision, rationale, outcome, status, decided_at)

**If Journal module installed:** journal_entries (content, highlights, mood, energy, linked_contacts, entry_date)

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

**Decision searches (Decision Log module):**
- "what decisions did I make about payments?" → `WHERE title LIKE '%payment%' OR decision LIKE '%payment%'`
- "decisions I might regret" → `WHERE status = 'regretted'`
- "decisions involving Jake" → JOIN with contacts WHERE contacts.name LIKE '%jake%'
- "recent decisions on the API project" → JOIN with projects WHERE projects.name LIKE '%api%'

**Journal searches (Journal module):**
- "journal entries about stress" → `WHERE content LIKE '%stress%' OR mood LIKE '%stress%'`
- "when did I feel energized?" → `WHERE energy >= 4`
- "journal mentioning Sarah" → `WHERE linked_contacts LIKE '%<sarah_id>%'` (after looking up Sarah's ID)
- "what did I write last week?" → `WHERE entry_date BETWEEN date('now', '-7 days') AND date('now')`

If nothing found, say so clearly and suggest alternative searches or broader terms.
