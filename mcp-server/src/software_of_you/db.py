"""Database connection, migrations, and backup for Software of You.

All data lives in ~/.local/share/software-of-you/soy.db — shared with
the Claude Code plugin. Migrations are bundled in this package and are
idempotent (safe to re-run every startup).
"""

import hashlib
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
    """Create a rolling, crash-consistent backup of the database.

    Uses SQLite's online backup API rather than ``shutil.copy2`` of the ``.db``
    file alone. The database runs in WAL mode (set persistently in
    ``get_connection``), so committed-but-uncheckpointed rows live in the
    ``-wal`` sidecar — a raw copy of ``.db`` silently drops them. ``backup``
    reads through the live WAL, capturing a complete, openable snapshot.

    Returns the backup path, or None if the DB does not exist yet.
    """
    if not DB_PATH.exists():
        return None

    ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"soy_{timestamp}.db"

    src = sqlite3.connect(str(DB_PATH))
    try:
        dst = sqlite3.connect(str(backup_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    # Backups carry the same data as the DB — keep them owner-only (L1 parity).
    os.chmod(backup_path, 0o600)

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


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply all bundled migrations against ``conn``, tracked by a ledger.

    A ``schema_migrations`` ledger (filename + sha256 checksum + applied_at)
    records which migration files have run. On each launch we skip files whose
    checksum already matches the ledger and execute (or re-execute) the rest.

    RECORD-AS-YOU-RUN — NOT seed-all-as-applied. The unified migration tree is
    a *superset*: an existing plugin DB has never run the slack migrations, and
    an existing MCP DB has never run pipeline_runs/health_checks. A blanket
    "mark everything applied" seed on an existing DB would skip that genuinely
    needed work. Instead, on a pre-ledger DB's first ledgered launch we run the
    full set once and record each file as we go. That single re-run is safe
    because every migration is idempotent (``CREATE ... IF NOT EXISTS`` /
    ``DROP VIEW IF EXISTS`` + ``CREATE`` / ``INSERT OR REPLACE`` / guarded
    ``ALTER``) and the one non-idempotent abort (the 004 ALTER) is already
    fixed; the ledger then skips every file on all subsequent launches.

    Loud on real failure: an *expected* idempotency error (``duplicate column``
    / ``already exists``) is treated as success — we stop executing the rest of
    that file quietly but STILL record it as applied. Any *other* sqlite error
    (``OperationalError``, ``IntegrityError``, or any ``sqlite3.Error``) prints
    a prominent ``MIGRATION FAILED`` to stderr, is NOT recorded, and is
    re-raised so the failure surfaces instead of being silently swallowed.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "filename TEXT PRIMARY KEY, checksum TEXT, applied_at TEXT)"
    )
    conn.commit()

    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        file_bytes = sql_file.read_bytes()
        checksum = hashlib.sha256(file_bytes).hexdigest()

        row = conn.execute(
            "SELECT checksum FROM schema_migrations WHERE filename = ?",
            (sql_file.name,),
        ).fetchone()
        if row is not None and row[0] == checksum:
            # Already applied with the same content — skip, do not re-execute.
            continue

        sql = file_bytes.decode("utf-8")
        try:
            conn.executescript(sql)
        except sqlite3.Error as e:
            err = str(e).lower()
            if "duplicate column" in err or "already exists" in err:
                # Expected idempotency error: the schema already has this object.
                # Stop executing the rest of this file quietly, but the file is
                # effectively applied — record it so we don't keep re-running it.
                pass
            else:
                # Genuine failure — be loud, do not record, re-raise.
                print(
                    f"MIGRATION FAILED ({sql_file.name}): {e}",
                    file=sys.stderr,
                )
                raise

        conn.execute(
            "INSERT OR REPLACE INTO schema_migrations "
            "(filename, checksum, applied_at) VALUES (?, ?, datetime('now'))",
            (sql_file.name, checksum),
        )
        conn.commit()


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

    # Run each migration file in order, tracked by the schema_migrations ledger.
    # On a genuine failure _apply_migrations re-raises (loud); close the live
    # connection first so a fatal abort doesn't leak it (init_db's trailing
    # close() never runs on the exception path).
    try:
        _apply_migrations(conn)
    except Exception:
        conn.close()
        raise

    # Data loss detection: if we had contacts before but now have zero, restore
    count_after = _get_contact_count(conn)
    if count_before > 0 and count_after == 0:
        print("Data loss detected after migrations — restoring from backup.", file=sys.stderr)
        # The restore overwrites DB_PATH on disk, so NO connection may be open
        # over the live file during the copy — otherwise we copy a backup over a
        # file a caller still holds a (now-stale, WAL-mode) handle to and corrupt
        # it. Close the live connection here regardless of who opened it
        # (close_after True for our own conn, False for an init_db-owned one);
        # _restore_latest_backup then owns the checkpoint, copy, and a fresh
        # reopen + re-migrate on the restored file, mirroring the bash path.
        conn.close()
        _restore_latest_backup()
        # The caller's handle (if any) is now stale and must not be reused for
        # a copy/write; init_db's trailing close() on it is a safe no-op.
    elif close_after:
        conn.close()


def _restore_latest_backup() -> bool:
    """Restore the most recent backup over DB_PATH and re-run migrations.

    The caller MUST have closed every connection to the live DB before calling
    this — the restore overwrites DB_PATH (and clears its WAL sidecars) on disk.

    Steps: checkpoint+drop any stale ``-wal``/``-shm`` left by the dead
    connection (so they can't re-clobber the restored file on the next open),
    copy the latest backup over DB_PATH, then reopen a fresh connection to
    re-apply migrations on the restored data (parity with bootstrap.sh).
    Returns True if a backup was restored.
    """
    backups = sorted(BACKUP_DIR.glob("soy_*.db"), key=lambda p: p.stat().st_mtime)
    if not backups:
        return False
    latest = backups[-1]

    # Remove stale WAL sidecars from the now-closed connection. If left in place,
    # SQLite would replay them into the freshly-restored .db on next open,
    # re-clobbering exactly the rows we just recovered.
    for sidecar in (
        DB_PATH.with_name(DB_PATH.name + "-wal"),
        DB_PATH.with_name(DB_PATH.name + "-shm"),
    ):
        if sidecar.exists():
            sidecar.unlink()

    shutil.copy2(latest, DB_PATH)

    # Re-run migrations on the restored DB to pick up any new schema, then close.
    # The restored backup may predate the current ledger state, so the ledgered
    # runner re-checks every file by checksum and re-applies whatever is missing.
    conn = get_connection()
    try:
        _apply_migrations(conn)
    finally:
        conn.close()
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


def insert_with_log(
    entity_sql: str,
    entity_params: tuple,
    log_sql: str,
    log_params: tuple = (),
) -> int:
    """Insert an entity row and its activity_log row in one transaction,
    returning the ENTITY's rowid.

    This replaces the create-path use of ``execute_many``, which returned the
    *last* statement's ``lastrowid`` — the activity_log row's id, not the
    entity's — so callers handed back the wrong id on every create. Here the
    entity's id is captured immediately after its insert and returned.

    ``log_sql`` is run unchanged on the same connection, so an inline
    ``last_insert_rowid()`` in the log still resolves to the entity just
    inserted (its FK was always correct; only the Python return value was not).
    """
    conn = get_connection()
    try:
        cursor = conn.execute(entity_sql, entity_params)
        entity_id = cursor.lastrowid
        conn.execute(log_sql, log_params)
        conn.commit()
        return entity_id
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
