"""Shared pytest fixtures for the Software of You MCP server test suite.

Tests run against an isolated temporary database — never the user's real
``~/.local/share/software-of-you/soy.db``. The ``db`` module computes its
path constants at import time from ``XDG_DATA_HOME``, so the fixtures here
monkeypatch the module-level constants to a per-test temp directory and run
migrations there. Nothing in the suite touches real user data.
"""

import pytest

from software_of_you import db as db_module


def _point_db_at(tmp_path, monkeypatch):
    """Redirect every db path constant at a temp data dir and ensure dirs."""
    data_dir = tmp_path / "software-of-you"
    monkeypatch.setattr(db_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(db_module, "DB_PATH", data_dir / "soy.db")
    monkeypatch.setattr(db_module, "BACKUP_DIR", data_dir / "backups")
    monkeypatch.setattr(db_module, "VIEWS_DIR", data_dir / "views")
    db_module.ensure_dirs()
    return data_dir


@pytest.fixture
def tmp_db_paths(tmp_path, monkeypatch):
    """Isolated, EMPTY db paths (no migrations run yet).

    Use for tests that exercise the migration runner / ledger directly and
    need to control when migrations execute.
    """
    return _point_db_at(tmp_path, monkeypatch)


@pytest.fixture
def soy_db(tmp_db_paths):
    """Isolated db with all migrations applied. Returns the db module."""
    db_module.init_db()
    return db_module
