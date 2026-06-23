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

# --- Ledgered migration runner ---
#
# Mirrors the Python runner in db.py: a schema_migrations ledger (filename +
# sha256 checksum) records which migrations have run so we skip unchanged
# already-applied files and re-run the rest. Statements stay idempotent as
# belt-and-suspenders. RECORD-AS-YOU-RUN — we never blanket-seed everything as
# applied (an existing plugin DB has never run the slack migrations; an existing
# MCP DB has never run pipeline_runs/health_checks — a blanket seed would skip
# that needed work). Loud on real failure: an expected idempotency error
# (duplicate column / already exists) is recorded and skipped; any other error
# prints MIGRATION FAILED and exits 1 instead of being swallowed by 2>/dev/null.
run_migrations_ledgered() {
  local db="$1"
  sqlite3 "$db" \
    "CREATE TABLE IF NOT EXISTS schema_migrations (filename TEXT PRIMARY KEY, checksum TEXT, applied_at TEXT);" \
    2>/dev/null
  local f cs fname prev err rc
  for f in "$PLUGIN_ROOT"/data/migrations/*.sql; do
    cs=$(shasum -a 256 "$f" | cut -d' ' -f1)
    fname=$(basename "$f")
    prev=$(sqlite3 "$db" "SELECT checksum FROM schema_migrations WHERE filename='$fname';" 2>/dev/null)
    if [ "$prev" = "$cs" ]; then
      continue  # already applied with the same content
    fi
    # -bail stops at the first error in the file, matching Python's
    # executescript (which aborts the whole script on error). Without it,
    # sqlite3 keeps going after a failed statement and would run later ones —
    # e.g. a migration whose guard ALTER fails on re-run would still execute a
    # following data-mutating statement, diverging from (and losing data the
    # MCP path preserves on) the same edited file.
    err=$(sqlite3 -bail "$db" < "$f" 2>&1)
    rc=$?
    if [ "$rc" -ne 0 ]; then
      # Expected idempotency error → record + continue; anything else → fail loud.
      if echo "$err" | grep -qiE 'duplicate column|already exists'; then
        :
      else
        echo "MIGRATION FAILED ($fname): $err" >&2
        exit 1
      fi
    fi
    sqlite3 "$db" \
      "INSERT OR REPLACE INTO schema_migrations (filename, checksum, applied_at) VALUES ('$fname', '$cs', datetime('now'));" \
      2>/dev/null
  done
}
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
    # The MCP server sets journal_mode=WAL persistently on this shared file, so
    # committed rows may live in the -wal sidecar. Checkpoint into the main .db
    # first or a raw cp silently drops them.
    sqlite3 "$DB_REAL" 'PRAGMA wal_checkpoint(TRUNCATE);' 2>/dev/null
    BACKUP_FILE="$BACKUP_DIR/soy-$(date +%Y%m%d-%H%M%S).db"
    cp "$DB_REAL" "$BACKUP_FILE"
    # Backups carry the same data as the DB — keep them owner-only.
    chmod 600 "$BACKUP_FILE" 2>/dev/null
    # Keep only the 5 most recent backups
    ls -t "$BACKUP_DIR"/soy-*.db 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null
  fi
fi

# --- Run Migrations ---

run_migrations_ledgered "$DB_REAL"

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
      # Checkpoint+truncate the WAL so the live -wal sidecar can't replay over
      # the file we're about to overwrite, then restore the backup.
      sqlite3 "$DB_REAL" 'PRAGMA wal_checkpoint(TRUNCATE);' 2>/dev/null
      cp "$LATEST_BACKUP" "$DB_REAL"
      # Re-run migrations on restored DB to pick up any new tables
      run_migrations_ledgered "$DB_REAL"
      CONTACTS=$(sqlite3 "$DB_REAL" "SELECT COUNT(*) FROM contacts;" 2>/dev/null || echo "0")
    fi
  fi
fi

# Quick status
echo "ready|$CONTACTS|$MODULES|$DATA_HOME"
