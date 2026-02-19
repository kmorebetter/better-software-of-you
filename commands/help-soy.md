---
description: Show available Software of You commands and help
allowed-tools: ["Bash", "Read"]
---

# Software of You — Help

Check installed modules by querying `${CLAUDE_PLUGIN_ROOT}/data/soy.db`:
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

## Natural Language

You can also just talk naturally:
- "Who are my contacts at Acme?"
- "What projects are overdue?"
- "Add a note to John: met at conference, great conversation"
- "Show me everything about the Website Redesign project"

Software of You understands context — just ask.
