# AGENTS.md

This file provides guidance to coding agents (Claude Code and similar) when working with code in this repository.

## What This Project Is

**Software of You** is a personal data platform that ships in two delivery modes from one shared SQLite database at `~/.local/share/software-of-you/soy.db`:

1. **Claude Code plugin** — runs inside Claude Code CLI/Desktop as a plugin (`.claude-plugin/plugin.json`). Claude is the entire interface; users interact via natural language and slash commands defined in `commands/*.md`. The bootstrap script and hooks initialize the DB on every session.

2. **MCP server** — a distributable Python package (`mcp-server/`) users install via `pipx install software-of-you`. It registers itself into Claude Desktop's MCP config and exposes Python-based tools. Entry point: `software_of_you.cli:main`.

Both modes share the same SQLite database file path and the same migration files (the plugin uses `data/migrations/*.sql`; the MCP server bundles its own copy under `mcp-server/src/software_of_you/migrations/`). The two directories must stay **byte-identical supersets** — every file present in one, present in the other, with identical bytes (a drift-guard test in `mcp-server/tests/test_migrations.py` enforces this). See "Module System" below for the migration-authoring rules (ledger, idempotency, numbering).

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

Automated tests live in `mcp-server/tests/` (pytest). Run them from the `mcp-server` directory:

```bash
cd mcp-server
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The suite uses an isolated temporary database (see `tests/conftest.py`) and never touches the real `~/.local/share/software-of-you/soy.db`.

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
2. Add a numbered migration in `data/migrations/` (and mirror the **identical bytes** to `mcp-server/src/software_of_you/migrations/`)
3. Add command `.md` files to `commands/`
4. The migration must `INSERT OR REPLACE INTO modules` (or `INSERT OR IGNORE`) to register it

#### Migration ledger & authoring rules

Migrations are tracked by a **`schema_migrations` ledger** (`filename TEXT PRIMARY KEY, checksum TEXT, applied_at TEXT`), maintained by both runners — `db.py`'s `_apply_migrations` (MCP) and `bootstrap.sh`'s `run_migrations_ledgered` (plugin). On each launch the runner computes the sha256 of each migration file and **skips** files whose checksum already matches the ledger; everything else runs and is recorded. Because the ledger is recorded as-you-run (never blanket-seeded), an existing DB's first ledgered launch runs the full superset once, then skips it forever after.

- **Both dirs are byte-identical supersets (001–020).** Mirror every shared-SQL edit into both directories in the same commit. The 017–020 range was reconciled from a numbering collision: the plugin's `017_pipeline_runs` / `018_health_checks` and the MCP-only `slack` migrations (renumbered `017_slack_module → 019_slack_module`, `018_slack_views → 020_slack_views`) are now both present, identically, in both dirs.
  - `001`–`016` — shared core + module schema and computed views.
  - `017_pipeline_runs`, `018_health_checks` — were plugin-only; now mirrored into MCP.
  - `019_slack_module`, `020_slack_views` — were MCP-only `017/018`; renumbered (via `git mv`, preserving history) and mirrored into the plugin. `020` must sort **after** `019` (creates `slack_messages`) and after `014`/`016` (base view definitions) so the slack-aware `v_contact_health` / `v_nudge_items` definitions win and reference an existing `slack_messages` table.
- **Migration files must stay idempotent.** Use `CREATE TABLE/INDEX IF NOT EXISTS`, `DROP VIEW IF EXISTS` + `CREATE VIEW`, `INSERT OR REPLACE`/`INSERT OR IGNORE`, and guarded `ALTER`. Editing a migration in place changes its checksum, so it **re-runs exactly once** under the new checksum — it must be safe to re-run. Never add a non-idempotent statement (e.g. a bare `INSERT`, or an `ALTER` that re-adds a column already in the `CREATE TABLE`) to a migration file.
- **Loud on real failure.** Expected idempotency errors (`duplicate column` / `already exists`) are recorded and skipped quietly; any other error prints `MIGRATION FAILED (<file>): <err>` and aborts (the Python runner re-raises; bootstrap exits 1) — failures surface instead of being swallowed.

Current modules: CRM, Project Tracker, Gmail, Calendar, Conversation Intelligence, Decision Log, Journal, Notes, User Profile, Slack.

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
- **Documented solutions & vocabulary** — `docs/solutions/` holds write-ups of past problems (bugs, best practices, workflow patterns), organized by category with YAML frontmatter (`module`, `tags`, `problem_type`); `CONCEPTS.md` (repo root) defines shared domain vocabulary. Relevant when implementing or debugging in a documented area.
