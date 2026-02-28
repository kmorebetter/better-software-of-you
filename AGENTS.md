# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## What This Project Is

**Software of You** is a personal data platform that ships in two delivery modes from one shared SQLite database at `~/.local/share/software-of-you/soy.db`:

1. **Claude Code plugin** — runs inside Claude Code CLI/Desktop as a plugin (`.claude-plugin/plugin.json`). Claude is the entire interface; users interact via natural language and slash commands defined in `commands/*.md`. The bootstrap script and hooks initialize the DB on every session.

2. **MCP server** — a distributable Python package (`mcp-server/`) users install via `pipx install software-of-you`. It registers itself into Claude Desktop's MCP config and exposes Python-based tools. Entry point: `software_of_you.cli:main`.

Both modes share the same SQLite database file path and the same migration files (the plugin uses `data/migrations/*.sql`; the MCP server bundles its own copy under `mcp-server/src/software_of_you/migrations/`). Keep these in sync when adding migrations.

## Development Commands

### MCP Server (Python package)

```bash
# Install into a local venv for development
cd mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"   # or: pip install -e .

# Build distributable
pip install hatch
hatch build                # outputs to mcp-server/dist/

# Run the CLI directly (development)
python3 -m software_of_you setup
python3 -m software_of_you status
python3 -m software_of_you serve   # starts MCP stdio server

# Activate license with a key flag (skip interactive prompt)
python3 -m software_of_you setup --key=YOUR_KEY
```

### Claude Code Plugin

```bash
# Bootstrap the database (safe to run any time; idempotent)
bash shared/bootstrap.sh

# Run all migrations manually
for f in data/migrations/*.sql; do sqlite3 data/soy.db < "$f"; done

# Inspect the database
sqlite3 data/soy.db ".tables"
sqlite3 data/soy.db "SELECT name, version FROM modules WHERE enabled=1;"

# Check Google auth status
python3 shared/google_auth.py status
```

There are no automated tests in this repo currently.

## Architecture

### Database & Paths

- Real DB: `~/.local/share/software-of-you/soy.db`
- Plugin access: `${CLAUDE_PLUGIN_ROOT}/data/soy.db` (symlink created by bootstrap)
- Output HTML: `${CLAUDE_PLUGIN_ROOT}/output/` (also a symlink into the data home)
- Google token: `${CLAUDE_PLUGIN_ROOT}/config/google_token.json` (symlink)
- Always reference the plugin root as `${CLAUDE_PLUGIN_ROOT:-$(pwd)}` — the env var is set when running as a plugin; `$(pwd)` is the fallback for standalone clones.

### Plugin Initialization Flow

On every Claude Code session start:
1. `hooks/session-start.py` runs (defined in `hooks/hooks.json`) — runs migrations, detects modules, outputs context
2. CLAUDE.md instructs Claude to run `shared/bootstrap.sh` as its first action before responding to the user

The bootstrap script also performs auto-backup (rolling 5 snapshots) and data-loss detection (restores from latest backup if contacts drop to zero after migration).

### Module System

Modules are self-contained feature packs, each in `modules/{name}/manifest.json`. A module declares:
- Which SQL tables it owns (`tables`)
- Which commands it adds (`commands`)
- Cross-module enhancements it activates when another module is also present (`enhancements[].requires_module`)

To add a new module:
1. Create `modules/{name}/manifest.json`
2. Add a numbered migration in `data/migrations/` (and mirror it to `mcp-server/src/software_of_you/migrations/`)
3. Add command `.md` files to `commands/`
4. The migration must `INSERT OR REPLACE INTO modules` to register it

Current modules: CRM, Project Tracker, Gmail, Calendar, Conversation Intelligence, Decision Log, Journal, Notes, User Profile.

### MCP Server Architecture

`mcp-server/src/software_of_you/`:
- `server.py` — `create_server()` instantiates FastMCP, registers all tools
- `cli.py` — CLI commands: `setup`, `serve`, `status`, `uninstall`
- `db.py` — DB connection, migration runner, backup, `execute`/`execute_write`/`execute_many` helpers
- `tools/` — one file per domain (`contacts.py`, `projects.py`, `transcripts.py`, etc.), each with a `register(server)` function
- `license.py` — license activation/validation against `softwareofyou.com`

Every tool returns a `_context` field with cross-references and presentation guidance that the server instructions tell Claude to use in its response.

### Commands (Plugin Mode)

`commands/*.md` files are slash commands. Each is a markdown document with a YAML front matter (`description`, `allowed-tools`, `argument-hint`). Claude reads and executes the instructions in the command file when the user types the corresponding slash command.

### Skills

`skills/` contains reference skills that Claude loads on demand:
- `sqlite-operations/` — schema reference and query patterns
- `module-system/` — cross-module enhancement rules
- `dashboard-generation/` — HTML design system (Tailwind CDN, Lucide icons, card layout)
- `conversation-intelligence/` — transcript parsing, SBI+T coaching framework, scoring methodology
- `project-tracker/` — momentum/risk scoring formulas

Each skill has a `SKILL.md` entry point that references additional files in a `references/` subdirectory.

### Auto-Sync

Before generating any HTML view or answering questions about email/calendar data, Claude should silently sync Gmail and Calendar if data is more than 15 minutes stale. This is driven by `soy_meta` timestamps (`gmail_last_synced`, `calendar_last_synced`). Google auth is managed by `shared/google_auth.py` (plugin) or `mcp-server/src/software_of_you/google_auth.py` (MCP).

## Key Conventions

- **Never fabricate data.** Every metric must be derived from source data or stored as NULL. Show derivations before storing calculated values.
- **Always log writes.** After any data modification, INSERT into `activity_log` with `entity_type`, `entity_id`, `action`, and `details`.
- **Always set `updated_at = datetime('now')`** on any record update.
- **Multi-line SQL with special characters** — use heredoc syntax: `sqlite3 "...soy.db" <<'SQL' ... SQL`
- **HTML output** — self-contained files written to `output/`, opened with `open <filepath>`. Use Tailwind CSS CDN + Lucide icons CDN + Inter font. Refer to `skills/dashboard-generation/` for the design system.
- **Module-gated tables** — always check `SELECT name FROM modules WHERE enabled=1` before querying module-specific tables. Missing tables will error.
