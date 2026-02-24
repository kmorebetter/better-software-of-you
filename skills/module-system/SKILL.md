---
name: module-system
description: Use when checking which modules are installed, resolving cross-module features, or handling module-aware queries. This skill explains how modules discover each other and activate enhanced features.
version: 1.0.0
---

# Module System

Software of You uses a modular architecture where each module adds domain-specific functionality, and modules automatically enhance each other when both are present.

## When to Use

- Before running any command that might use module-specific tables
- When generating summaries that could include cross-module data
- When a user asks about a feature that requires a specific module

## Module Detection

Check installed modules:
```sql
SELECT name, version, enabled FROM modules WHERE enabled = 1;
```

Read manifests from `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/modules/*/manifest.json` for enhancement details.

## Cross-Module Enhancement Rules

**When both CRM and Project Tracker are installed:**

1. **Contact views should include projects** — when showing a contact summary or detail, also query:
   ```sql
   SELECT p.name, p.status, p.priority FROM projects p WHERE p.client_id = ?;
   ```

2. **Project views should include client context** — when showing a project, also query:
   ```sql
   SELECT c.name, c.email, c.company FROM contacts c WHERE c.id = ?;
   SELECT * FROM contact_interactions WHERE contact_id = ? ORDER BY occurred_at DESC LIMIT 5;
   ```

3. **Search should span both** — natural language search should always check contacts AND projects AND tasks.

4. **Activity log should resolve names** — the timeline should show entity names from whichever module owns that entity type.

## When a Module is NOT Installed

- Never reference its tables (they won't exist — the query will error)
- Never show features that depend on it
- Optionally hint: "You could see [feature] if you add the [module name] module."
- Handle gracefully — the experience should feel complete with whatever modules are present

## Adding Future Modules

New modules follow this pattern:
1. `manifest.json` in `modules/{name}/` declaring features and enhancements
2. Migration `.sql` in `data/migrations/` creating module tables
3. Command `.md` files in `commands/` for module-specific slash commands
4. Registration via `INSERT OR REPLACE INTO modules` in the migration

The SessionStart hook auto-detects new modules and runs their migrations.
