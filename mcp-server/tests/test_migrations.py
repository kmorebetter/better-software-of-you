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

from pathlib import Path

from software_of_you import db as db_module

# Bundled MCP copy lives next to db.py; the plugin copy lives at the repo root.
MCP_004 = db_module.MIGRATIONS_DIR / "004_gmail_module.sql"
REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_004 = REPO_ROOT / "data" / "migrations" / "004_gmail_module.sql"

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


def test_004_files_are_byte_identical():
    """Guard: the plugin and MCP copies of 004 must not drift apart."""
    assert MCP_004.exists(), f"missing MCP 004 at {MCP_004}"
    assert PLUGIN_004.exists(), f"missing plugin 004 at {PLUGIN_004}"
    assert MCP_004.read_bytes() == PLUGIN_004.read_bytes(), (
        "004_gmail_module.sql diverged between data/migrations and the bundled "
        "MCP copy — keep them byte-identical"
    )
