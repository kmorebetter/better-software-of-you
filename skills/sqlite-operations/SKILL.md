---
name: sqlite-operations
description: Use when performing any database read or write operation in Software of You. This skill provides the schema reference, computed-view guidance, query patterns, and conventions for interacting with the SQLite database.
---

# SQLite Operations

This skill provides reference material for all database operations in Software of You.

## When to Use

- Any time you need to read or write data
- When constructing queries for search, reporting, or cross-module features
- When generating dashboard data

## Reads: Computed Views First

For any read, check whether a computed view already provides the number before writing an
ad-hoc query. The 8 `v_*` views (per-contact health, project health, commitment status,
nudges, meeting prep, discovery candidates, email queue) do the deterministic math — use
their columns directly rather than re-deriving counts, days-silent, or overdue tiers. See
`references/query-patterns.md` (its "Computed Views First" section) and the "Computed Views"
rule in the project's CLAUDE.md. Fall back to ad-hoc joins only for data no view covers.

## Key References

- `references/schema.sql` — schema reference (all 34 tables + 8 computed views) generated from the live DB; authoritative migrations live in `data/migrations/`
- `references/query-patterns.md` — computed-view guidance plus common ad-hoc query patterns

## Conventions

- Always use `sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db"` for operations
- All datetimes are ISO-8601 text via `datetime('now')`
- Always INSERT into `activity_log` after any data modification
- Always SET `updated_at = datetime('now')` on updates
- Use `LIKE '%term%'` for text search (case-insensitive by default in SQLite)
- Use `json_object()` for structured details in activity_log
