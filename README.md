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

### Gmail
- View, search, and triage your inbox
- Compose and send emails (always shows draft, always confirms)
- AI email summaries and prioritization
- Emails auto-link to contacts

### Google Calendar
- View today's schedule, this week's events
- Create events with attendees linked to contacts
- Check availability and find free time
- Events auto-link to contacts and projects

### Conversation Intelligence
- Import meeting transcripts (paste or file — Fathom, Otter, Zoom, anything)
- Extract commitments — what you owe others, what they owe you
- Communication metrics — talk ratio, questions, interruptions
- AI coaching grounded in specific moments from your calls
- Relationship scoring and trajectory tracking over time

### Cross-Module Intelligence
Modules enhance each other automatically:
- Contact summaries include project history, email threads, and meeting history
- Project briefs include client context, interaction history, and scheduled meetings
- Email threads link to contacts and projects
- Calendar events link to contacts via attendees
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
| `/import` | Import data — paste text, CSV, file path, anything |
| `/search` | Natural language search across all data |
| `/note` | Add a note to any contact or project |
| `/tag` | Create and manage tags |
| `/log` | View your activity timeline |
| `/import-call` | Import a meeting transcript |
| `/commitments` | View and manage commitments from conversations |
| `/communication-review` | Your communication patterns and coaching |
| `/relationship-pulse` | Deep relationship view with conversation history |
| `/gmail` | View, search, and triage your Gmail inbox |
| `/email` | Compose and send emails (always confirms first) |
| `/calendar` | View and create Google Calendar events |
| `/google-setup` | Connect your Google account |
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
