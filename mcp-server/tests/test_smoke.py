"""Smoke test — verifies the isolated-DB fixture and migration runner work."""


def test_migrations_create_core_tables(soy_db):
    rows = soy_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'"
    )
    assert len(rows) == 1


def test_isolated_db_is_under_tmp(soy_db):
    # Guard: the suite must never point at the real user data dir.
    assert "software-of-you" in str(soy_db.DB_PATH)
    assert "/.local/share/software-of-you/soy.db" not in str(soy_db.DB_PATH)
