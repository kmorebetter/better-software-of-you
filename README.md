# Software of You

**Your personal CRM, project tracker, email client, and meeting analyst — powered by Claude, stored on your machine, owned by you.**

You're already paying for AI. Stop paying for everything else.

Software of You is a personal data platform that runs inside [Claude Code](https://docs.anthropic.com/en/docs/claude-code). No servers. No API keys. No monthly fees beyond your existing Claude subscription. Just talk to it — it handles the rest.

---

## Why This Exists

Every freelancer, consultant, and small operator runs the same stack: a CRM they half-use, a project tool they resent, a calendar they forget to check, and meeting notes scattered across five apps. You're paying $50–200/month for tools that don't talk to each other.

Software of You replaces all of that with a single AI-powered interface. You talk. It remembers. It connects the dots between your contacts, projects, emails, calendar, and conversations — automatically.

**The key insight:** Claude is already good enough to be the interface. You don't need dashboards, forms, or dropdown menus. You need an assistant that understands your data and acts on it.

---

## What It Does

### Contacts & Relationships
Track everyone you work with. Log interactions, set follow-ups, get AI-generated relationship summaries. Know exactly where things stand before every meeting.

### Projects & Tasks
Create projects, assign tasks, set milestones. Get AI-generated status reports and project briefs that pull in client context, email history, and meeting notes automatically.

### Gmail Integration
Search, triage, and compose emails without leaving the terminal. Emails auto-link to contacts. Multi-account support — your work and personal inboxes in one place.

### Google Calendar
See today's schedule, this week's events, find free time. Events link to contacts and projects so you always have context.

### Conversation Intelligence
Import any meeting transcript — Fathom, Otter, Zoom, Gemini, or raw text. Software of You extracts commitments, calculates talk ratios, scores communication patterns, and generates coaching insights grounded in specific moments from your calls.

### Decision Journal
Log decisions with context, options considered, and rationale. Track outcomes over time. Build a searchable record of how and why you made every important call.

### Daily Journal
Write morning pages, track mood and energy, and get automatic cross-references to contacts, projects, and events mentioned in your entries.

### Notes
Standalone notes with #hashtag tagging, pinning, and automatic entity linking. Write a note mentioning "Sarah" and it links to her contact page.

### Smart Nudges
Never let things slip. Software of You surfaces overdue commitments, cold contacts, stale projects, and upcoming deadlines — all ranked by urgency.

### Generated Views
Every module produces beautiful, self-contained HTML pages — dashboards, contact briefs, project pages, conversation analyses, weekly reviews, and more. All generated on demand, all cross-linked.

---

## Cross-Module Intelligence

This is where it gets interesting. Modules don't just coexist — they enhance each other:

- **Contact pages** pull in email threads, meeting transcripts, project history, and commitment status
- **Project briefs** include client relationship context and interaction timelines
- **Email threads** link to contacts and surface in relationship summaries
- **Calendar events** connect to contacts via attendees and appear in meeting prep
- **Search** spans everything — contacts, emails, transcripts, notes, decisions
- **Nudges** aggregate across all modules into a single attention feed

The more you use it, the more connected everything becomes.

---

## Setup

```bash
git clone https://github.com/kmorebetter/better-software-of-you.git
cd better-software-of-you
claude
```

That's it. The system initializes automatically on first run — creates the database, runs migrations, and walks you through onboarding.

To connect Gmail and Calendar:
```
/google-setup
```

Type `/help-soy` to see all commands, or just start talking naturally.

---

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
| `/entity-page` | Deep-dive page for any contact |
| `/project-page` | Deep-dive page for any project |
| `/gmail` | View, search, and triage your inbox |
| `/email` | Compose and send emails |
| `/calendar` | View and create calendar events |
| `/import-call` | Import a meeting transcript for analysis |
| `/commitments` | View and manage commitments from conversations |
| `/decision` | Log, view, and track decisions |
| `/journal` | Write daily journal entries |
| `/note` | Add standalone notes with auto cross-referencing |
| `/nudges` | See what needs your attention |
| `/search` | Natural language search across all data |
| `/morning` | Daily morning check-in routine |
| `/weekly-review` | Your week at a glance |
| `/build-all` | Regenerate all HTML views |
| `/google-setup` | Connect your Google account |
| `/help-soy` | Full command reference |

Or skip the commands entirely — just describe what you want in plain English.

---

## Your Data

All data lives in `~/.local/share/software-of-you/` — a single SQLite database on your machine. No cloud sync. No third-party servers. No telemetry. Back it up however you back up your files.

The database survives repo updates and re-clones. Your data is yours.

---

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (CLI)
- Claude Pro, Max, or Team subscription
- macOS or Linux (Windows support planned)
- Python 3 (for Google integrations)
- SQLite3

---

## The Model Upgrade Loop

Every time Anthropic ships a better Claude model, Software of You gets smarter — automatically. Better summaries, sharper analysis, more natural conversations. You don't update anything. The intelligence layer improves for free.

This is the advantage of building on an AI runtime instead of traditional software. The app you use today is the worst version it'll ever be.

---

## Philosophy

Software of You is built on a simple belief: **your personal data is your most valuable asset, and you shouldn't need 10 SaaS subscriptions to make sense of it.**

One database. One interface. Everything connected. All local.

---

Built by [@kmorebetter](https://github.com/kmorebetter) · Powered by [Claude](https://claude.ai)
