#!/bin/bash
# Bootstrap Software of You — creates DB and runs migrations if needed.
# Safe to run multiple times (all migrations are idempotent).

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DB_PATH="$PLUGIN_ROOT/data/soy.db"

mkdir -p "$PLUGIN_ROOT/data"
mkdir -p "$PLUGIN_ROOT/output"

for f in "$PLUGIN_ROOT"/data/migrations/*.sql; do
  sqlite3 "$DB_PATH" < "$f" 2>/dev/null
done

# Quick status
CONTACTS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM contacts;" 2>/dev/null || echo "0")
MODULES=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM modules WHERE enabled=1;" 2>/dev/null || echo "0")
echo "ready|$CONTACTS|$MODULES"
