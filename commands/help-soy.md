---
description: Show available Software of You commands and help
allowed-tools: ["Bash", "Read"]
---

# Software of You — Help

Check installed modules by querying `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db`:
```sql
SELECT name FROM modules WHERE enabled = 1;
```

Present available commands based on what's installed:

## Always Available
| Command | Description |
|---------|-------------|
| `/setup` | First-run setup (or re-check) |
| `/status` | System overview — modules, data counts, recent activity |
| `/search <query>` | Natural language search across all your data |
| `/note <entity> <content>` | Add a note to any contact or project |
| `/tag <action> [args]` | Create, list, or apply tags |
| `/log [timeframe]` | View your activity timeline |
| `/import` | Import data from any source — paste text, CSV, file path, anything |
| `/dashboard` | Generate a visual HTML dashboard |
| `/view <module>` | Generate a specialized module view |
| `/backup [export\|import\|status]` | Export or import your data as JSON |
| `/pages [name]` | List or open generated HTML pages |
| `/project-page <name>` | Generate a project intelligence brief |
| `/nudges` | What needs your attention — cold contacts, overdue items, stale projects |
| `/network-map` | Interactive visual map of your contact network |
| `/entity-page <name>` | Generate a contact intelligence brief |
| `/build-all` | Generate ALL views — entity pages, project pages, module views, dashboard |
| `/soul` | Generate a soul.md snapshot — your profile, patterns, and insights |
| `/help-soy` | This help page |

## If CRM Module Installed
| Command | Description |
|---------|-------------|
| `/contact <name> [email] [company]` | Add, edit, list, or find contacts |
| `/contact-summary <name>` | AI-generated relationship brief |
| `/follow-up <name> [context]` | Draft a follow-up message |

## If Project Tracker Installed
| Command | Description |
|---------|-------------|
| `/project <name> [--client name]` | Add, edit, list, or find projects |
| `/project-brief <name>` | AI-generated project brief |
| `/project-status <name>` | Quick project status report |

## If Gmail Module Installed
| Command | Description |
|---------|-------------|
| `/google-setup` | Connect your Google account (Gmail + Calendar) |
| `/gmail [inbox\|unread\|from <name>]` | View, search, and triage your inbox |
| `/email <contact> [context]` | Compose and send an email (with confirmation) |
| `/email-hub` | Generate an Email Hub page with threads, response queue, and contact stats |

## If Calendar Module Installed
| Command | Description |
|---------|-------------|
| `/calendar [today\|week\|schedule]` | View or create calendar events |
| `/week-view` | Generate a visual calendar week view |

## If Conversation Intelligence Installed
| Command | Description |
|---------|-------------|
| `/import-call` | Import a meeting transcript — paste or file path |
| `/commitments [mine\|theirs\|overdue]` | View and manage commitments from conversations |
| `/communication-review [week\|month]` | Your communication patterns and coaching |
| `/relationship-pulse <name>` | Deep relationship view with conversation history |
| `/conversations-view` | Generate a Conversations page with transcripts, commitments, and coaching |

## If Decision Log Installed
| Command | Description |
|---------|-------------|
| `/decision <description>` | Log a decision with context, options, and rationale |
| `/decision list [project]` | View recent decisions, optionally filtered by project |
| `/decision outcome <title>` | Record how a decision turned out |
| `/decision revisit` | Review old decisions that need outcome tracking |
| `/decision-journal-view` | Generate a Decision Journal page with outcomes and patterns |

## If Journal Installed
| Command | Description |
|---------|-------------|
| `/journal <entry>` | Write a journal entry with auto cross-referencing |
| `/journal today` | Read today's entry |
| `/journal week` | AI-synthesized weekly review of your entries |
| `/journal read <date>` | Read entries for a specific date |
| `/journal-view` | Generate a Journal page with mood trends and cross-references |

## If Notes Module Installed
| Command | Description |
|---------|-------------|
| `/note <content>` | Quick-capture a standalone note with auto cross-referencing |
| `/note list` | View recent standalone notes (pinned first) |
| `/note search <term>` | Search across all standalone notes |
| `/note pin <id>` | Pin or unpin a note |
| `/notes-view` | Generate a Notes page with tags, linked entities, and pinned highlights |

## Natural Language

You can also just talk naturally:
- "Who are my contacts at Acme?"
- "What projects are overdue?"
- "Add a note to John: met at conference, great conversation"
- "Show me everything about the Website Redesign project"

Software of You understands context — just ask.
