# Software of You

Personal data platform — track relationships, projects, decisions, and conversations through natural language in Claude Desktop.

All your data stays on your machine. No cloud. No accounts. Just you and Claude.

## Quick Start

### 1. Buy a license

Purchase at [softwareofyou.com](https://softwareofyou.com). You'll get a license key by email.

### 2. Install

Open Terminal (Mac/Linux) or Command Prompt (Windows):

**Mac (recommended):**
```
brew install pipx
pipx install software-of-you
```

**Windows / Linux:**
```
pip3 install software-of-you
```

> If you get an "externally-managed-environment" error on Mac, use the `pipx` method above.

### 3. Activate

```
software-of-you setup
```

Enter your license key when prompted. This initializes the database and configures Claude Desktop automatically.

### 4. Use it

Restart Claude Desktop. Then just talk:

- "Add a contact named Sarah Chen, VP of Engineering at Acme"
- "What's on my calendar this week?"
- "Log a decision: we're switching to Postgres"
- "When did I last talk to Daniel?"

## What it does

Software of You gives Claude access to your personal data:

- **Contacts & Relationships** — your professional network, interaction history, follow-ups
- **Email & Calendar** — synced from Gmail, searchable and cross-referenced
- **Projects & Tasks** — track what you're working on, milestones, deadlines
- **Conversations** — import call transcripts, extract commitments and insights
- **Decisions & Journal** — structured decision log, daily entries with mood tracking
- **Notes** — standalone notes with auto cross-referencing
- **Dashboards** — generate visual HTML pages for any contact, project, or overview

## Prerequisites

- **Claude Desktop** with a Pro or Max subscription
- **Python 3.10+** — check with: `python3 --version`
- **A license key** from [softwareofyou.com](https://softwareofyou.com)

Don't have Python? Install it from [python.org/downloads](https://python.org/downloads).

## Commands

```
software-of-you setup      # Activate license + configure Claude Desktop
software-of-you status     # Show license, database, and connection status
software-of-you uninstall  # Remove from Claude Desktop + deactivate license
```

## Google connection

Say "connect my Google account" in Claude Desktop to enable email and calendar sync.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `command not found` | Try: `python3 -m software_of_you setup` |
| `externally-managed-environment` | Use `pipx install software-of-you` instead of `pip3` |
| `Python not found` | Install from [python.org/downloads](https://python.org/downloads) |
| License won't activate | Check your key, ensure internet connection |
| Claude Desktop doesn't see it | Restart Claude Desktop after setup |

Need help? Contact hello@softwareofyou.com

## Data storage

All data lives locally at `~/.local/share/software-of-you/`. Nothing leaves your machine. Uninstalling preserves your data — reinstall anytime to pick up where you left off.
