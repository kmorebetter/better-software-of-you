#!/usr/bin/env bash
# swap-demo.sh — Switch between real and demo databases
# Usage: ./demo/swap-demo.sh start   (create demo DB and switch to it)
#        ./demo/swap-demo.sh stop    (switch back to real DB)
#
# Bootstrap always operates on $DATA_DIR/soy.db directly, so we swap
# the actual file at that path (rename real → soy-real.db, create fresh soy.db).

set -euo pipefail

DATA_DIR="$HOME/.local/share/software-of-you"
DB_PATH="$DATA_DIR/soy.db"
REAL_BACKUP="$DATA_DIR/soy-real.db"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DEMO_FLAG="$DATA_DIR/.demo_active"
SEED_SQL="$PLUGIN_ROOT/demo/seed-healthcare.sql"

case "${1:-}" in
  start)
    if [[ -f "$DEMO_FLAG" ]]; then
      echo "Demo mode is already active. Run '$0 stop' first."
      exit 1
    fi

    # Stash the real DB
    echo "→ Backing up real database..."
    if [[ -f "$DB_PATH" ]]; then
      mv "$DB_PATH" "$REAL_BACKUP" || { echo "Error: Could not back up database"; exit 1; }
    fi

    # Create fresh empty DB at the canonical path
    touch "$DB_PATH"

    # Run migrations directly (skip bootstrap's data-loss detection,
    # which would restore a backup into our intentionally empty DB)
    echo "→ Running migrations..."
    for f in "$PLUGIN_ROOT"/data/migrations/*.sql; do
      sqlite3 "$DB_PATH" < "$f" 2>/dev/null
    done

    # Seed demo data
    echo "→ Seeding healthcare demo data..."
    sqlite3 "$DB_PATH" < "$SEED_SQL"

    # Mark demo as active
    touch "$DEMO_FLAG"

    CONTACTS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM contacts;" 2>/dev/null)
    echo ""
    echo "✓ Demo mode active. ($CONTACTS contacts loaded)"
    echo "  Run '$0 stop' to restore your real data."
    ;;

  stop)
    if [[ ! -f "$DEMO_FLAG" ]]; then
      echo "Demo mode is not active."
      exit 1
    fi

    echo "→ Restoring real database..."
    if [[ -f "$REAL_BACKUP" ]]; then
      mv "$REAL_BACKUP" "$DB_PATH"
    else
      echo "Warning: Real database backup not found at $REAL_BACKUP"
    fi
    rm -f "$DEMO_FLAG"

    echo "✓ Real database restored."
    ;;

  *)
    echo "Usage: $0 {start|stop}"
    echo "  start — Create a demo DB with healthcare data"
    echo "  stop  — Switch back to your real DB"
    exit 1
    ;;
esac
