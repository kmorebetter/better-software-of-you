"""Backup/restore crash-consistency and WAL-safety tests (U4 / H1).

Background: the database runs in WAL mode (``get_connection`` sets
``journal_mode=WAL`` persistently). The old ``backup_db`` did
``shutil.copy2(DB_PATH, ...)`` of the main ``.db`` file *alone* — but committed,
uncheckpointed rows live in the ``-wal`` sidecar, so that snapshot silently
dropped them. And the data-loss auto-restore branch copied a backup over
``DB_PATH`` *without closing a caller-owned connection first*, copying over a
file a caller still held an open (WAL-mode) handle to — corruption.

These tests pin the fix:
  * ``backup_db`` uses SQLite's online backup API → captures WAL rows.
  * the restore path closes the live connection before the copy and leaves no
    stale ``-wal``/``-shm`` that re-clobbers the restored file on next open.
  * backups are mode 0o600.
  * round-trip: backup → mutate → restore recovers the original rows, clean
    ``integrity_check``.
"""

import sqlite3
import stat


def _count(soy_db, table="contacts"):
    rows = soy_db.execute(f"SELECT COUNT(*) AS n FROM {table}")
    return rows[0]["n"]


def _insert_contacts(soy_db, names):
    conn = soy_db.get_connection()
    try:
        for name in names:
            conn.execute(
                "INSERT INTO contacts (name, type, status) "
                "VALUES (?, 'individual', 'active')",
                (name,),
            )
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Round-trip: backup → mutate → restore                                        #
# --------------------------------------------------------------------------- #

def test_backup_restore_round_trip(soy_db):
    _insert_contacts(soy_db, ["Alice", "Bob", "Carol"])
    assert _count(soy_db) == 3

    backup_path = soy_db.backup_db()
    assert backup_path is not None and backup_path.exists()

    # Mutate: delete every contact (simulates data loss after the snapshot).
    conn = soy_db.get_connection()
    try:
        conn.execute("DELETE FROM contacts")
        conn.commit()
    finally:
        conn.close()
    assert _count(soy_db) == 0

    # Restore the latest backup. No connection is held open over DB_PATH here.
    restored = soy_db._restore_latest_backup()
    assert restored is True

    # The original three contacts are back...
    rows = soy_db.execute("SELECT name FROM contacts ORDER BY name")
    assert [r["name"] for r in rows] == ["Alice", "Bob", "Carol"]

    # ...and the restored DB is structurally sound.
    conn = soy_db.get_connection()
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# WAL durability: committed-but-uncheckpointed rows survive the backup         #
# --------------------------------------------------------------------------- #

def test_backup_captures_uncheckpointed_wal_rows(soy_db):
    # Hold a WAL-mode connection open with committed-but-not-checkpointed rows.
    # A naive copy of the .db alone would miss these (they live in -wal).
    conn = soy_db.get_connection()
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    conn.execute(
        "INSERT INTO contacts (name, type, status) "
        "VALUES ('WalRow', 'individual', 'active')"
    )
    conn.commit()  # committed, but deliberately NOT checkpointed
    wal_sidecar = soy_db.DB_PATH.with_name(soy_db.DB_PATH.name + "-wal")
    assert wal_sidecar.exists() and wal_sidecar.stat().st_size > 0, (
        "expected an active -wal sidecar holding uncheckpointed rows"
    )

    backup_path = soy_db.backup_db()
    conn.close()
    assert backup_path is not None

    # Open the backup directly (independent connection) and confirm the row is
    # present — proves the online backup API read through the live WAL.
    bconn = sqlite3.connect(str(backup_path))
    try:
        n = bconn.execute(
            "SELECT COUNT(*) FROM contacts WHERE name = 'WalRow'"
        ).fetchone()[0]
        assert n == 1, "backup missed a committed-but-uncheckpointed WAL row"
        assert bconn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        bconn.close()


# --------------------------------------------------------------------------- #
# Data-loss auto-restore branch (the original corruption bug)                  #
# --------------------------------------------------------------------------- #

def test_data_loss_branch_restores_via_init_db_path(soy_db, monkeypatch):
    """Simulate: contacts present, then migrations empty them.

    This drives the ``init_db`` → ``run_migrations(conn)`` path where the conn
    is *caller-owned* (``close_after`` is False). The old code only closed the
    connection when it owned it, so it would ``shutil.copy2`` a backup over
    DB_PATH while init_db still held an open WAL-mode handle — the exact
    corruption U4 fixes. We assert the restore recovers contacts AND that a
    subsequent fresh ``get_connection`` integrity-checks clean (no stale -wal/
    -shm re-clobbering the restored file on reopen).
    """
    _insert_contacts(soy_db, ["Dana", "Eve"])
    assert _count(soy_db) == 2

    # Take the backup that the restore will recover from. (run_migrations only
    # backs up when count_before > 0, but we drive run_migrations directly with
    # a forced loss below, so make the snapshot explicitly here.)
    backup_path = soy_db.backup_db()
    assert backup_path is not None

    # Force the data-loss signal without a permanently-destructive migration in
    # MIGRATIONS_DIR (the real migration set is non-destructive and is re-run
    # after restore). _get_contact_count returns >0 the first call (count_before)
    # and 0 the second (count_after) → the loss branch fires.
    real_count = soy_db._get_contact_count
    calls = {"n": 0}

    def fake_count(conn):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_count(conn)  # count_before: real (>0)
        return 0  # count_after: pretend the migrations emptied contacts

    monkeypatch.setattr(soy_db, "_get_contact_count", fake_count)

    # Drive the init_db caller-owned path explicitly: an externally-owned, open
    # WAL-mode connection handed to run_migrations.
    conn = soy_db.get_connection()
    soy_db.run_migrations(conn)
    conn.close()  # init_db's trailing close — must be a safe no-op post-restore

    # Restore brought the original contacts back.
    rows = soy_db.execute("SELECT name FROM contacts ORDER BY name")
    assert [r["name"] for r in rows] == ["Dana", "Eve"]

    # No stale WAL/SHM left to replay over the restored file on next open.
    for suffix in ("-wal", "-shm"):
        sidecar = soy_db.DB_PATH.with_name(soy_db.DB_PATH.name + suffix)
        # If present at all, it must be empty (a fresh connection may recreate an
        # empty -wal/-shm pair; what matters is no leftover *content* to replay).
        if sidecar.exists():
            assert sidecar.stat().st_size == 0

    # A subsequent fresh connection sees a clean, intact DB.
    conn = soy_db.get_connection()
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 2
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Backup file permissions (L1 parity)                                          #
# --------------------------------------------------------------------------- #

def test_backup_file_mode_is_0600(soy_db):
    _insert_contacts(soy_db, ["Frank"])
    backup_path = soy_db.backup_db()
    assert backup_path is not None

    mode = stat.S_IMODE(backup_path.stat().st_mode)
    assert mode == 0o600, f"backup mode is {oct(mode)}, expected 0o600"
