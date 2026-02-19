---
description: First-run setup for Software of You
allowed-tools: ["Bash", "Read", "Write"]
---

# Software of You — Setup

Check if the database exists at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

**If the database does NOT exist:**

1. Run each migration file in order:
   ```
   sqlite3 "${CLAUDE_PLUGIN_ROOT}/data/soy.db" < "${CLAUDE_PLUGIN_ROOT}/data/migrations/001_core_schema.sql"
   ```
   Then run any additional migration files (002, 003, etc.) found in the migrations directory.

2. Welcome the user warmly. Tell them:
   - Software of You is set up and ready
   - List the installed modules (query the `modules` table)
   - Where their data lives (the database path)
   - Suggest first steps: add a contact, create a project, or explore with /help-soy

**If the database already exists:**

Tell the user it's already set up. Show a quick status summary (contact count, project count) and suggest /status for full details or /help-soy for available commands.
