---
description: Manage the Telegram bot — sync, status, backlog
allowed-tools: ["Bash", "Read"]
---

# Telegram Bot Management

Manage your SoY Telegram bot — sync context, pull backlog items, check status.

## Parse Arguments

Check `$ARGUMENTS` for the subcommand:
- `sync` or no argument → full sync (push context + pull backlog)
- `push` → push local context to D1 for the bot
- `pull` → pull backlog items from D1 to local SoY
- `status` → show sync status and pending items
- `webhook` → check webhook health

## Subcommand: sync (default)

Push fresh context and pull any pending backlog items:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/sync_telegram.py" push
```

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/sync_telegram.py" pull
```

Parse both JSON outputs. Report:
- How many projects/tasks/contacts/notes were pushed
- How many tasks and notes were pulled from backlog
- Any errors

## Subcommand: push

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/sync_telegram.py" push
```

Report what was pushed.

## Subcommand: pull

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/sync_telegram.py" pull
```

Report what was pulled. If tasks were created, list them with their projects.

## Subcommand: status

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/sync_telegram.py" status
```

Also check local setup info:
```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" "SELECT key, value FROM soy_meta WHERE key LIKE 'telegram_%'"
```

Present a summary:
- Bot username and webhook URL
- Last context push (how long ago)
- Last backlog pull (how long ago)
- Pending items in D1
- Total synced items by type

## Subcommand: webhook

Check webhook health via Telegram API. Requires the bot token from Cloudflare env (not stored locally), so tell the user to check manually:

```
curl -s "https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo" | python3 -m json.tool
```

## Auto-Sync Integration

This module's context push and backlog pull are integrated into SoY's auto-sync flow:
- Context push: if `telegram_last_context_push` is >30 min stale
- Backlog pull: if `telegram_last_backlog_pull` is >15 min stale

These run automatically before view generation alongside Gmail/Calendar sync.
