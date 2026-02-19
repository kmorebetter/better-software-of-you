---
name: sqlite-operations
description: Use when performing any database read or write operation in Software of You. This skill provides the current schema, query patterns, and conventions for interacting with the SQLite database.
version: 1.0.0
---

# SQLite Operations

This skill provides reference material for all database operations in Software of You.

## When to Use

- Any time you need to read or write data
- When constructing queries for search, reporting, or cross-module features
- When generating dashboard data

## Key References

- `references/schema.sql` — current complete schema for all installed modules
- `references/query-patterns.md` — common query patterns with examples

## Conventions

- Always use `sqlite3 "${CLAUDE_PLUGIN_ROOT}/data/soy.db"` for operations
- All datetimes are ISO-8601 text via `datetime('now')`
- Always INSERT into `activity_log` after any data modification
- Always SET `updated_at = datetime('now')` on updates
- Use `LIKE '%term%'` for text search (case-insensitive by default in SQLite)
- Use `json_object()` for structured details in activity_log
