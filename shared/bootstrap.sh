#!/bin/bash
# Bootstrap Software of You — creates DB and runs migrations if needed.
# Safe to run multiple times (all migrations are idempotent).
#
# Data lives in ~/.local/share/software-of-you/ so it survives
# repo re-downloads and updates. A symlink in data/soy.db points
# to the real location.

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/software-of-you"
DB_REAL="$DATA_HOME/soy.db"
DB_LINK="$PLUGIN_ROOT/data/soy.db"
TOKEN_REAL="$DATA_HOME/google_token.json"
TOKEN_LINK="$PLUGIN_ROOT/config/google_token.json"

# Create directories
mkdir -p "$DATA_HOME"
mkdir -p "$PLUGIN_ROOT/data"
mkdir -p "$PLUGIN_ROOT/config"
mkdir -p "$PLUGIN_ROOT/output"

# --- Database ---

# If there's a real file (not symlink) in data/soy.db, migrate it out
if [ -f "$DB_LINK" ] && [ ! -L "$DB_LINK" ]; then
  mv "$DB_LINK" "$DB_REAL"
fi

# Create symlink if needed
if [ ! -e "$DB_LINK" ]; then
  ln -sf "$DB_REAL" "$DB_LINK"
fi

# --- Google Token ---

# If there's a real token file (not symlink), migrate it out
if [ -f "$TOKEN_LINK" ] && [ ! -L "$TOKEN_LINK" ]; then
  mv "$TOKEN_LINK" "$TOKEN_REAL"
fi

# Create symlink if needed (only if real token exists)
if [ -f "$TOKEN_REAL" ] && [ ! -e "$TOKEN_LINK" ]; then
  ln -sf "$TOKEN_REAL" "$TOKEN_LINK"
fi

# --- Run Migrations ---

for f in "$PLUGIN_ROOT"/data/migrations/*.sql; do
  sqlite3 "$DB_REAL" < "$f" 2>/dev/null
done

# Quick status
CONTACTS=$(sqlite3 "$DB_REAL" "SELECT COUNT(*) FROM contacts;" 2>/dev/null || echo "0")
MODULES=$(sqlite3 "$DB_REAL" "SELECT COUNT(*) FROM modules WHERE enabled=1;" 2>/dev/null || echo "0")
echo "ready|$CONTACTS|$MODULES|$DATA_HOME"
