# Software of You

Your AI-powered personal platform. Contacts, projects, and more — all local, all yours.

**You're already paying for AI. Stop paying for everything else.**

Software of You runs inside Claude Code as a plugin. Your Claude subscription is the runtime. No servers, no API keys, no monthly fees. Your data stays on your machine.

## Setup

1. Download and unzip the `software-of-you` folder
2. Open Claude Code in the folder:
   ```
   cd software-of-you
   claude
   ```
3. That's it. The system initializes automatically on first run.

Type `/help-soy` to see available commands, or just start talking:

> "Add a contact for Jane Smith, she works at Acme Corp as a designer"

> "Create a project called Website Redesign for Jane"

> "Show me my dashboard"

## What's Included

### Contacts & CRM
- Add, edit, search, and manage contacts
- Log interactions (calls, emails, meetings)
- Track follow-ups with due dates
- AI relationship summaries
- AI follow-up message drafting

### Project Tracker
- Create and manage projects with status tracking
- Task management with priorities and assignments
- Milestone tracking with target dates
- AI project brief generation
- AI status reports

### Cross-Module Intelligence
When both modules are installed, they enhance each other automatically:
- Contact summaries include project history
- Project briefs include client context and interaction history
- Search spans all data across all modules

## Commands

| Command | What it does |
|---------|-------------|
| `/contact` | Add, edit, list, or find contacts |
| `/contact-summary` | AI relationship brief for a contact |
| `/follow-up` | Draft follow-ups or manage reminders |
| `/project` | Add, edit, list, or manage projects and tasks |
| `/project-brief` | AI project brief with full context |
| `/project-status` | Quick project status check |
| `/dashboard` | Generate a visual HTML dashboard |
| `/view` | Generate specialized module views |
| `/search` | Natural language search across all data |
| `/note` | Add a note to any contact or project |
| `/tag` | Create and manage tags |
| `/log` | View your activity timeline |
| `/status` | System overview |
| `/setup` | First-run setup (runs automatically) |
| `/add-module` | Install a new module |
| `/help-soy` | Full help |

Or just ask naturally — Software of You understands context.

## Your Data

All data lives in `data/soy.db` — a single SQLite file on your machine. No cloud sync, no third-party servers. Back it up however you back up your files.

## Adding Modules

New modules can be added with `/add-module`. Each module is a folder containing a manifest, database migration, and command files. Drop it in, and the system detects it automatically on next session start.

## Requirements

- Claude Code (CLI or Desktop app)
- Claude Pro, Max, or Team subscription
- macOS, Linux, or Windows with Python 3 available

## The Auto-Improvement Hook

Every time Anthropic updates the Claude model, your apps get smarter automatically. You don't update anything. The intelligence layer improves for free.
