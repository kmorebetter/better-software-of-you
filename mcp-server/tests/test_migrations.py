"""Migration regression tests — guards the U3 fix for the MCP 004 abort (C3).

Background: ``migrations/004_gmail_module.sql`` once declared ``from_name`` in
``CREATE TABLE emails`` *and* re-added it via a standalone
``ALTER TABLE emails ADD COLUMN from_name TEXT``. On a fresh DB the ALTER threw
``duplicate column``; because the runner executes each file with
``executescript`` and ``continue``-skips the rest of a file on a known-safe
error, the trailing ``idx_emails_*`` indexes and the
``INSERT OR REPLACE INTO modules ('gmail', ...)`` never ran — so gmail was
never registered and email search silently returned nothing.

These tests pin: gmail registers, the ``emails`` table + ``from_name`` column
and ``idx_emails_*`` indexes exist, migrations are idempotent, and the two
copies of 004 (plugin ``data/migrations`` and bundled MCP) stay byte-identical.
"""

import sqlite3
from pathlib import Path

import pytest

from software_of_you import db as db_module

# Bundled MCP copy lives next to db.py; the plugin copy lives at the repo root.
MCP_MIGRATIONS_DIR = db_module.MIGRATIONS_DIR
MCP_004 = MCP_MIGRATIONS_DIR / "004_gmail_module.sql"
REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_MIGRATIONS_DIR = REPO_ROOT / "data" / "migrations"
PLUGIN_004 = PLUGIN_MIGRATIONS_DIR / "004_gmail_module.sql"

EXPECTED_EMAIL_INDEXES = {
    "idx_emails_contact",
    "idx_emails_thread",
    "idx_emails_date",
    "idx_emails_gmail_id",
}


def test_gmail_module_registered(soy_db):
    """The 004 migration must register the gmail module on a fresh DB."""
    rows = soy_db.execute("SELECT 1 FROM modules WHERE name = 'gmail'")
    assert len(rows) == 1, "gmail module was not registered — migration 004 aborted"


def test_emails_table_has_from_name_column(soy_db):
    """The emails table exists and carries the from_name column."""
    cols = soy_db.execute("PRAGMA table_info(emails)")
    assert cols, "emails table does not exist"
    col_names = {row["name"] for row in cols}
    assert "from_name" in col_names


def test_emails_indexes_exist(soy_db):
    """All idx_emails_* indexes from 004 must be present."""
    rows = soy_db.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'index' AND name LIKE 'idx_emails_%'"
    )
    found = {row["name"] for row in rows}
    missing = EXPECTED_EMAIL_INDEXES - found
    assert not missing, f"missing email indexes: {sorted(missing)}"


def test_migrations_are_idempotent(soy_db):
    """Re-running every migration on the same DB raises no error and keeps
    gmail registered (the runner swallows known-safe errors per file)."""
    # soy_db already ran init_db once; run the full set again.
    db_module.init_db()

    rows = soy_db.execute("SELECT 1 FROM modules WHERE name = 'gmail'")
    assert len(rows) == 1, "gmail registration lost on second migration run"

    # from_name still single (no duplicate column / corruption from the re-run).
    cols = soy_db.execute("PRAGMA table_info(emails)")
    from_name_cols = [c for c in cols if c["name"] == "from_name"]
    assert len(from_name_cols) == 1


# ─────────────────────────────────────────────────────────────────────
# U6: schema_migrations ledger
# ─────────────────────────────────────────────────────────────────────


def test_ledger_populated(soy_db):
    """After migrations, schema_migrations has a row with a non-empty checksum
    for every migration file in the directory."""
    rows = soy_db.execute("SELECT filename, checksum FROM schema_migrations")
    ledgered = {r["filename"]: r["checksum"] for r in rows}

    expected = {p.name for p in MCP_MIGRATIONS_DIR.glob("*.sql")}
    assert expected, "no migration files found — test setup wrong"
    assert set(ledgered) == expected, (
        "ledger filenames do not match the migration directory: "
        f"missing={expected - set(ledgered)} extra={set(ledgered) - expected}"
    )
    for fname, checksum in ledgered.items():
        assert checksum, f"ledger row for {fname} has an empty checksum"
        assert len(checksum) == 64, f"{fname} checksum is not a sha256 hexdigest"


def test_idempotent_second_run_executes_nothing(soy_db):
    """A second init_db() run applies nothing new and raises no error — the
    ledger skips every already-applied file, so the applied_at timestamps are
    untouched (a re-execution would rewrite them via INSERT OR REPLACE)."""
    before = soy_db.execute(
        "SELECT filename, checksum, applied_at FROM schema_migrations "
        "ORDER BY filename"
    )

    db_module.init_db()  # second run — must be a pure no-op skip

    after = soy_db.execute(
        "SELECT filename, checksum, applied_at FROM schema_migrations "
        "ORDER BY filename"
    )
    assert [dict(r) for r in before] == [dict(r) for r in after], (
        "second migration run changed the ledger (applied_at/checksum) — the "
        "ledger should have skipped every already-applied file untouched"
    )


def test_edited_in_place_reapplies_once(soy_db):
    """A ledger row with a WRONG checksum forces exactly one re-apply, and the
    ledger is updated to the file's real checksum."""
    target = "001_core_schema.sql"
    real_checksum = soy_db.execute(
        "SELECT checksum FROM schema_migrations WHERE filename = ?", (target,)
    )[0]["checksum"]

    # Corrupt the ledger row for one file as if it were edited in place.
    db_module.execute_write(
        "UPDATE schema_migrations SET checksum = ? WHERE filename = ?",
        ("0" * 64, target),
    )

    db_module.init_db()  # should re-apply only the mismatched file

    updated = soy_db.execute(
        "SELECT checksum FROM schema_migrations WHERE filename = ?", (target,)
    )[0]["checksum"]
    assert updated == real_checksum, (
        "edited-in-place migration did not re-run / update its ledger checksum"
    )


def test_existing_install_first_ledgered_launch(soy_db):
    """The load-bearing claim of U6: an existing, POPULATED pre-ledger install
    re-runs the full superset once on its first ledgered launch without
    crashing, duplicating, or losing data.

    Record-as-you-run (not blanket-seed) means a pre-ledger DB has no ledger,
    so every file re-executes once over the already-populated schema. This is
    safe only because every migration is idempotent; the test pins that.
    """
    # Populate the DB, then drop the ledger to simulate a pre-ledger install
    # that already ran 001-020 (under the old glob-and-re-run bootstrap).
    db_module.execute_write("INSERT INTO contacts (name) VALUES ('Existing')")
    db_module.execute_write("DROP TABLE schema_migrations")

    # First ledgered launch: must re-run the full set once over populated data.
    db_module.init_db()

    contacts = soy_db.execute("SELECT COUNT(*) AS n FROM contacts")[0]["n"]
    assert contacts == 1, "the existing contact was lost on first ledgered launch"

    ledger = soy_db.execute("SELECT COUNT(*) AS n FROM schema_migrations")[0]["n"]
    expected = len(list(MCP_MIGRATIONS_DIR.glob("*.sql")))
    assert ledger == expected, (
        f"ledger should list all {expected} migrations after re-run, got {ledger}"
    )


def test_superset_tables_present(soy_db):
    """The unified superset is mirrored into the MCP dir: slack_messages
    (was MCP-only) AND pipeline_runs AND health_checks (were plugin-only)
    all exist after migrations."""
    for table in ("slack_messages", "pipeline_runs", "health_checks"):
        rows = soy_db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        )
        assert len(rows) == 1, f"superset table {table!r} missing after migrations"


def test_view_shadowing_order(soy_db):
    """020_slack_views drops+recreates v_contact_health referencing
    slack_messages; it must sort after 019_slack_module so the table exists.
    Selecting from the view must not raise 'no such table: slack_messages'."""
    # Should not raise OperationalError("no such table: slack_messages").
    soy_db.execute("SELECT * FROM v_contact_health LIMIT 0")


def test_loud_on_failure_raises(tmp_db_paths, monkeypatch, tmp_path):
    """A genuinely broken migration makes run_migrations RAISE (loud), not
    silently swallow it. Point MIGRATIONS_DIR at a dir with one valid + one
    syntactically-broken .sql file."""
    broken_dir = tmp_path / "broken_migrations"
    broken_dir.mkdir()
    (broken_dir / "001_good.sql").write_text("CREATE TABLE good (id INTEGER);\n")
    (broken_dir / "002_broken.sql").write_text("THIS IS NOT VALID SQL ;;;\n")
    monkeypatch.setattr(db_module, "MIGRATIONS_DIR", broken_dir)

    with pytest.raises(sqlite3.Error):
        db_module.init_db()

    # The broken file must NOT have been recorded as applied.
    conn = db_module.get_connection()
    try:
        rows = conn.execute(
            "SELECT filename FROM schema_migrations WHERE filename = '002_broken.sql'"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [], "a failed migration was wrongly recorded in the ledger"


# ─────────────────────────────────────────────────────────────────────
# U6: drift guard — both migration directories must be byte-identical
# ─────────────────────────────────────────────────────────────────────


def test_migration_dirs_are_byte_identical():
    """Every migration file in the plugin and MCP directories must be
    byte-identical, with equal filename sets (the unified superset)."""
    plugin_files = {p.name: p for p in PLUGIN_MIGRATIONS_DIR.glob("*.sql")}
    mcp_files = {p.name: p for p in MCP_MIGRATIONS_DIR.glob("*.sql")}

    assert plugin_files, "no plugin migrations found"
    assert set(plugin_files) == set(mcp_files), (
        "migration filename sets differ between the two directories: "
        f"plugin-only={set(plugin_files) - set(mcp_files)} "
        f"mcp-only={set(mcp_files) - set(plugin_files)}"
    )

    for name in sorted(plugin_files):
        assert plugin_files[name].read_bytes() == mcp_files[name].read_bytes(), (
            f"{name} diverged between data/migrations and the bundled MCP copy "
            "— keep them byte-identical"
        )


def test_004_files_are_byte_identical():
    """Guard: the plugin and MCP copies of 004 must not drift apart (C3)."""
    assert MCP_004.exists(), f"missing MCP 004 at {MCP_004}"
    assert PLUGIN_004.exists(), f"missing plugin 004 at {PLUGIN_004}"
    assert MCP_004.read_bytes() == PLUGIN_004.read_bytes(), (
        "004_gmail_module.sql diverged between data/migrations and the bundled "
        "MCP copy — keep them byte-identical"
    )
