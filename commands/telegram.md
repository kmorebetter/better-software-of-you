---
description: Manage the Telegram bot — start, stop, status
allowed-tools: ["Bash", "Read"]
---

# Telegram Bot Management

Manage your local SoY Telegram bot — start it, check status, or stop it.

## Parse Arguments

Check `$ARGUMENTS` for the subcommand:
- `start` or no argument → start the bot
- `stop` → stop the bot
- `status` → show bot status and stats

## Subcommand: start (default)

Start the local Telegram bot. It runs as a foreground process using long-polling.

**Recommended:** run in a tmux session so it persists:

```bash
# Check if already running
if pgrep -f "telegram_bot.py" > /dev/null 2>&1; then
    echo "Bot is already running (PID: $(pgrep -f telegram_bot.py))"
else
    echo "Starting bot... (suggest running in tmux for persistence)"
    python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/telegram_bot.py"
fi
```

Tell the user:
- The bot runs in the foreground — use tmux or a separate terminal
- It only works while their machine is on and the process is running
- Send `/stop` from Telegram or Ctrl-C in terminal to shut down

## Subcommand: stop

```bash
pkill -f "telegram_bot.py" 2>/dev/null && echo "Bot stopped." || echo "Bot not running."
```

Or tell the user they can send `/stop` from Telegram.

## Subcommand: status

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/setup_telegram.py" status
```

Also check if the bot process is running:
```bash
pgrep -f "telegram_bot.py" > /dev/null 2>&1 && echo "Bot process: RUNNING (PID: $(pgrep -f telegram_bot.py))" || echo "Bot process: NOT RUNNING"
```

Present a summary:
- Bot username and mode (local)
- Whether the bot process is currently running
- Session count, message count, error count
- Setup date

## Telegram Bot Commands Reference

### Standard commands
- `/start` — welcome message and command list
- `/status` — project overview with task counts
- `/tasks [project]` — open tasks, optionally filtered by project
- `/notes [search]` — recent notes, optionally filtered

### Dev session commands
- `/new <slug> <instruction>` — create a new project from scratch and start a dev session. Slug becomes the directory name (`~/wkspaces/<slug>`) and GitHub repo name. Auto-scaffolds `index.html`, `package.json`, `.gitignore`, and `CLAUDE.md`. Creates a private GitHub repo via `gh`. Spawns a dev session on a `dev/<id>` branch. On completion, deploys a Vercel preview and connects Vercel↔GitHub for auto-deploys on merge. Optional `--model opus` flag (default: sonnet). Example: `/new acme-landing Build a modern landing page with hero and contact form`
- `/delete <project>` — delete a project with multi-step confirmation. Resolves by fuzzy name or numeric ID. Shows project stats (tasks, sessions, URLs) and requires typing the project name to confirm. Removes Vercel deployment, database records (tasks, sessions, activity), and workspace directory. Optionally deletes the GitHub repo with a second confirmation prompt. Blocks deletion if active dev sessions exist.
- `/dev <project> <instruction>` — spawn a background Claude Code session in a project workspace on an isolated `dev/<id>` branch. Resolves project by fuzzy name match. Optional `--model opus` flag (default: sonnet). Max 3 concurrent sessions. 10-minute timeout. Blocks concurrent sessions on the same workspace. Auto-creates a GitHub repo if the workspace has no remote. Pushes the dev branch and includes a GitHub commit link for code review. Auto-deploys a Vercel preview on completion.
- `/sessions` — list recent 10 dev sessions with status, deploy status, review status, duration, and instruction preview
- `/session <id>` — full output of a session including branch, GitHub commit link, preview URL, and review status (matched by 8-char ID prefix)
- `/approve <id>` — merge a completed session's branch into main and delete the branch
- `/reject <id>` — discard a session's branch (delete it without merging)
- `/kill <id>` — kill a running dev session (also kills its active deploy)

### System commands
- `/debug` — bot diagnostics (uptime, message count, active dev sessions)
- `/errors` — recent error log
- `/stop` — shut down the bot (also kills active dev sessions)
