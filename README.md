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

### Telegram Bot (AFK Access)
Interact with SoY from your phone — capture tasks, notes, and run dev sessions while away from your computer. The bot runs locally via long-polling (no webhooks, no server).

**Prerequisites:**
- Claude Code CLI (`claude`) in PATH with active subscription
- Telegram account + bot token from @BotFather
- `git` and `gh` CLI (for dev sessions)
- `vercel` CLI (optional, for preview deploys)

**Setup:**
```
/telegram-setup
```

**Starting the bot:**
```bash
python3 shared/telegram_bot.py
```
Tip: run in a tmux session so it stays alive when you close the terminal.

**Commands:**

| Command | What it does |
|---------|-------------|
| `/start` | Welcome message + command list |
| `/status` | Project overview with task counts |
| `/tasks` | Open tasks (optionally filter by project) |
| `/notes` | Recent notes |
| `/new` | Create a new project from scratch |
| `/delete` | Delete a project with multi-step confirmation |
| `/dev` | Spawn an autonomous dev session on a project |
| `/sessions` | List recent dev sessions |
| `/session` | View full output of a session |
| `/approve` | Merge a session's branch into main |
| `/reject` | Discard a session's branch |
| `/kill` | Kill a running session |
| `/debug` | Bot diagnostics |
| `/errors` | Recent error log |
| `/stop` | Shut down the bot |

Or just send natural language — the bot uses Claude to answer questions about your projects, capture tasks, and log notes.

**Security model:**
- Owner-only: only your Telegram user ID can interact with the bot
- Isolated branches: dev sessions work on `dev/<session-id>` branches, never main
- Review gate: changes require explicit `/approve` before merging
- Timeouts: sessions auto-terminate after 10-20 minutes
- Concurrent limits: max 3 active sessions
- Local-only: bot runs on your machine, no data leaves your network

**Troubleshooting:**
- *Bot not responding:* check `python3 shared/telegram_bot.py` is running, verify token with `/debug`
- *"Not authorized":* your Telegram user ID must match `TELEGRAM_OWNER_ID` in `.env`
- *Dev session hangs:* use `/kill <id>` to terminate, check `/errors` for details
- *Preview deploy fails:* ensure `vercel` CLI is installed and linked to your account

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
| `/telegram-setup` | Set up the Telegram bot for AFK access |
| `/telegram` | Manage the Telegram bot (start, stop, status) |
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
