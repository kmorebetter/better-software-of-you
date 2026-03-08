---
description: Set up the Telegram bot for AFK access to SoY
allowed-tools: ["Bash", "Read", "AskUserQuestion"]
---

# Telegram Bot Setup

Connect a Telegram bot so you can interact with SoY from your phone — capture tasks, notes, and chat about your projects while away from your computer. The bot runs locally using `claude -p` (requires Claude Code CLI with active subscription).

## Step 1: Check if Already Configured

```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" "SELECT key, value FROM soy_meta WHERE key LIKE 'telegram_%'"
```

If `telegram_bot_username` exists, show current status and ask if they want to reconfigure.

## Step 2: Collect Credentials

Use `AskUserQuestion` to guide the user through two things they need:

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

Ask these sequentially since each requires the user to do something.

## Step 3: Run Setup

Once both values are collected:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/setup_telegram.py" setup "<bot_token>" "<owner_id>"
```

Parse the JSON output.

## Step 4: Verify Telegram Tables

Bootstrap handles migrations automatically, so just verify the tables exist:

```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" ".tables" | grep telegram
```

Expected output should include `telegram_bot_sessions`, `telegram_conversations`, `telegram_dev_sessions`, etc.

If tables are missing, re-run bootstrap:
```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/bootstrap.sh"
```

## Step 5: Report Results

If successful, tell the user:

"Your Telegram bot is ready! **@{bot_username}** is configured for local mode.

To start the bot, run `/telegram start` — or in a terminal:
```
python3 shared/telegram_bot.py
```

Tip: run it in a tmux session so it stays alive when you close the terminal."

If any step failed, report the specific error and which steps succeeded.
