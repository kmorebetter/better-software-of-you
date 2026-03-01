#!/bin/bash
# Bootstrap Software of You — creates DB and runs migrations if needed.
# Safe to run multiple times (all migrations are idempotent).
#
# Data lives in ~/.local/share/software-of-you/ so it survives
# repo re-downloads and updates. Symlinks point to the real location:
#   data/soy.db → ~/.local/share/software-of-you/soy.db
#   output/     → ~/.local/share/software-of-you/output/

if ! command -v sqlite3 &>/dev/null; then
  echo "error|sqlite3 not found|Install sqlite3 to use Software of You"
  exit 1
fi

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/software-of-you"
DB_REAL="$DATA_HOME/soy.db"
DB_LINK="$PLUGIN_ROOT/data/soy.db"
TOKEN_REAL="$DATA_HOME/google_token.json"
TOKEN_LINK="$PLUGIN_ROOT/config/google_token.json"
OUTPUT_REAL="$DATA_HOME/output"
OUTPUT_LINK="$PLUGIN_ROOT/output"

# Create directories
mkdir -p "$DATA_HOME"
mkdir -p "$DATA_HOME/tokens"
mkdir -p "$OUTPUT_REAL"
mkdir -p "$PLUGIN_ROOT/data"
mkdir -p "$PLUGIN_ROOT/config"

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

# --- Output Directory ---

# If there's a real directory (not symlink) at output/, migrate its contents out
if [ -d "$OUTPUT_LINK" ] && [ ! -L "$OUTPUT_LINK" ]; then
  cp -a "$OUTPUT_LINK"/. "$OUTPUT_REAL"/ 2>/dev/null
  rm -rf "$OUTPUT_LINK"
fi

# Create symlink if needed
if [ ! -e "$OUTPUT_LINK" ]; then
  ln -sf "$OUTPUT_REAL" "$OUTPUT_LINK"
fi

# --- Auto-Backup (before any changes) ---

BACKUP_DIR="$DATA_HOME/backups"
mkdir -p "$BACKUP_DIR"

if [ -f "$DB_REAL" ]; then
  DB_SIZE=$(wc -c < "$DB_REAL" | tr -d ' ')
  # Only backup if DB has real data (>50KB = beyond empty schema)
  if [ "$DB_SIZE" -gt 51200 ]; then
    cp "$DB_REAL" "$BACKUP_DIR/soy-$(date +%Y%m%d-%H%M%S).db"
    # Keep only the 5 most recent backups
    ls -t "$BACKUP_DIR"/soy-*.db 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null
  fi
fi

# --- Run Migrations ---

for f in "$PLUGIN_ROOT"/data/migrations/*.sql; do
  sqlite3 "$DB_REAL" < "$f" 2>/dev/null
done

# --- Data Loss Detection ---

CONTACTS=$(sqlite3 "$DB_REAL" "SELECT COUNT(*) FROM contacts;" 2>/dev/null || echo "0")
MODULES=$(sqlite3 "$DB_REAL" "SELECT COUNT(*) FROM modules WHERE enabled=1;" 2>/dev/null || echo "0")

# Check if we lost data: DB existed with backups but now has 0 contacts
if [ "$CONTACTS" = "0" ]; then
  LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/soy-*.db 2>/dev/null | head -1)
  if [ -n "$LATEST_BACKUP" ]; then
    BACKUP_CONTACTS=$(sqlite3 "$LATEST_BACKUP" "SELECT COUNT(*) FROM contacts;" 2>/dev/null || echo "0")
    if [ "$BACKUP_CONTACTS" -gt 0 ]; then
      echo "WARNING: Database has 0 contacts but backup has $BACKUP_CONTACTS. Restoring from backup."
      cp "$LATEST_BACKUP" "$DB_REAL"
      # Re-run migrations on restored DB to pick up any new tables
      for f in "$PLUGIN_ROOT"/data/migrations/*.sql; do
        sqlite3 "$DB_REAL" < "$f" 2>/dev/null
      done
      CONTACTS=$(sqlite3 "$DB_REAL" "SELECT COUNT(*) FROM contacts;" 2>/dev/null || echo "0")
    fi
  fi
fi

# Quick status
echo "ready|$CONTACTS|$MODULES|$DATA_HOME"
