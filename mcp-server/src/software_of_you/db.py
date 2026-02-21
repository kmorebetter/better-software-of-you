"""Database connection, migrations, and backup for Software of You.

All data lives in ~/.local/share/software-of-you/soy.db — shared with
the Claude Code plugin. Migrations are bundled in this package and are
idempotent (safe to re-run every startup).
"""

import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DATA_HOME = os.environ.get(
    "XDG_DATA_HOME",
    os.path.join(os.path.expanduser("~"), ".local", "share"),
)
DATA_DIR = Path(DATA_HOME) / "software-of-you"
DB_PATH = DATA_DIR / "soy.db"
BACKUP_DIR = DATA_DIR / "backups"
VIEWS_DIR = DATA_DIR / "views"
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

MAX_BACKUPS = 5


def ensure_dirs() -> None:
    """Create data directories if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    VIEWS_DIR.mkdir(parents=True, exist_ok=True)


def get_connection(readonly: bool = False) -> sqlite3.Connection:
    """Get a database connection with WAL mode and row factory."""
    ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    if not readonly:
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def backup_db() -> Path | None:
    """Create a rolling backup of the database. Returns backup path or None."""
    if not DB_PATH.exists():
        return None

    ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"soy_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)

    # Keep only MAX_BACKUPS most recent
    backups = sorted(BACKUP_DIR.glob("soy_*.db"), key=lambda p: p.stat().st_mtime)
    for old in backups[:-MAX_BACKUPS]:
        old.unlink()

    return backup_path


def _get_contact_count(conn: sqlite3.Connection) -> int:
    """Get contact count for data loss detection."""
    try:
        row = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def run_migrations(conn: sqlite3.Connection | None = None) -> None:
    """Run all bundled migrations in order. Idempotent.

    Backs up the database before running, and auto-restores if
    data loss is detected (contact count drops to zero).
    """
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True

    # Snapshot contact count before migrations
    count_before = _get_contact_count(conn)

    # Backup before running migrations
    if count_before > 0:
        backup_db()

    # Run each migration file in order
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for sql_file in migration_files:
        sql = sql_file.read_text()
        try:
            conn.executescript(sql)
        except sqlite3.OperationalError as e:
            # Silently skip known-safe errors (e.g., ALTER TABLE column already exists)
            err = str(e).lower()
            if "duplicate column" in err or "already exists" in err:
                continue
            print(f"Migration warning ({sql_file.name}): {e}", file=sys.stderr)

    # Data loss detection: if we had contacts before but now have zero, restore
    count_after = _get_contact_count(conn)
    if count_before > 0 and count_after == 0:
        print("Data loss detected after migrations — restoring from backup.", file=sys.stderr)
        if close_after:
            conn.close()
        _restore_latest_backup()
        if close_after:
            conn = get_connection()
    elif close_after:
        conn.close()


def _restore_latest_backup() -> bool:
    """Restore the most recent backup. Returns True if restored."""
    backups = sorted(BACKUP_DIR.glob("soy_*.db"), key=lambda p: p.stat().st_mtime)
    if not backups:
        return False
    latest = backups[-1]
    shutil.copy2(latest, DB_PATH)
    return True


def init_db() -> None:
    """Initialize database and run all migrations. Safe to call every startup."""
    ensure_dirs()
    conn = get_connection()
    run_migrations(conn)
    conn.close()


def execute(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Execute a read query and return rows."""
    conn = get_connection(readonly=True)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def execute_write(sql: str, params: tuple = ()) -> int:
    """Execute a write query and return lastrowid."""
    conn = get_connection()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def execute_many(statements: list[tuple[str, tuple]]) -> int:
    """Execute multiple write statements in a single transaction.

    Returns the lastrowid of the final statement.
    """
    conn = get_connection()
    try:
        last_id = 0
        for sql, params in statements:
            cursor = conn.execute(sql, params)
            last_id = cursor.lastrowid
        conn.commit()
        return last_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dict_from_row(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    """Convert a list of sqlite3.Row to list of dicts."""
    return [dict(r) for r in rows]


def get_installed_modules() -> list[str]:
    """Return list of enabled module names."""
    rows = execute("SELECT name FROM modules WHERE enabled = 1")
    return [r["name"] for r in rows]
