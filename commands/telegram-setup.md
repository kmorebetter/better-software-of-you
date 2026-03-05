---
description: Set up the Telegram bot for AFK access to SoY
allowed-tools: ["Bash", "Read", "AskUserQuestion"]
---

# Telegram Bot Setup

Connect a Telegram bot so you can interact with SoY from your phone — capture tasks, notes, and chat about projects while away from your computer.

## Step 1: Check Prerequisites

Verify Cloudflare is configured:
```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" "SELECT key, value FROM soy_meta WHERE key IN ('cf_account_id', 'cf_pages_project')"
```

If missing, tell the user they need to set up Cloudflare Pages first.

## Step 2: Check if Already Configured

```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" "SELECT key, value FROM soy_meta WHERE key LIKE 'telegram_%'"
```

If `telegram_bot_username` exists, show current status and ask if they want to reconfigure.

## Step 3: Collect Credentials

Use `AskUserQuestion` to guide the user through three things they need:

**Q1** (header: "Bot Token"):
"Create a Telegram bot via @BotFather and paste the token here. Steps:
1. Open Telegram, search for @BotFather
2. Send `/newbot`, pick a name and username
3. Copy the token it gives you"

**Q2** (header: "Your ID"):
"Get your Telegram user ID:
1. Search for @userinfobot in Telegram
2. Send it any message
3. It replies with your numeric ID — paste it here"

**Q3** (header: "Anthropic Key"):
"Paste your Anthropic API key (starts with `sk-ant-`). Create one at console.anthropic.com if needed."

Ask these sequentially since each requires the user to do something.

## Step 4: Run Setup

Once all three values are collected:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/setup_telegram.py" setup "<bot_token>" "<owner_id>" "<anthropic_key>"
```

Parse the JSON output.

## Step 5: Report Results

If successful, tell the user:

"Your Telegram bot is live! **@{bot_username}** is ready.

Open Telegram, find your bot, and send it a message — try something like:
- "Add a task: review the homepage layout"
- "What projects am I working on?"
- /status

Your context will sync automatically. Run `/telegram sync` anytime to force a fresh sync."

If any step failed, report the specific error and which steps succeeded.

## Step 6: Run Migration

Make sure the local migration is applied:
```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" < "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/migrations/025_telegram_bot.sql"
```
