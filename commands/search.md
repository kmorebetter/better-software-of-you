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

If nothing found, say so clearly and suggest alternative searches or broader terms.
