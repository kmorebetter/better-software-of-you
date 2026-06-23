"""Regression tests for U13 review findings.

- The bash migration runner must abort a migration file on first error
  (``sqlite3 -bail``), matching Python's ``executescript``. Otherwise an
  edited 021 re-run would run past its guard ALTER and execute the
  destructive backfill UPDATE, wiping re-derived metric values on the plugin
  path only (cross-mode divergence + data loss).
- View filenames derived from contact names / model titles must be whitelisted
  so a name containing ``/`` or ``..`` can't crash the write or escape VIEWS_DIR.
"""

import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from software_of_you.tools import contacts, transcripts
from software_of_you.tools.views import _safe_slug

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = REPO_ROOT / "shared" / "bootstrap.sh"
PLUGIN_MIGRATIONS = REPO_ROOT / "data" / "migrations"

_bash_available = bool(shutil.which("bash")) and bool(shutil.which("sqlite3")) and BOOTSTRAP.exists()


def _bootstrap(plugin_root: Path, data_home: Path) -> subprocess.CompletedProcess:
    env = dict(
        os.environ,
        XDG_DATA_HOME=str(data_home),
        CLAUDE_PLUGIN_ROOT=str(plugin_root),  # isolate — don't touch the real repo
    )
    return subprocess.run(
        ["bash", str(BOOTSTRAP)], env=env, capture_output=True, text=True, timeout=120
    )


@pytest.mark.skipif(not _bash_available, reason="needs bash + sqlite3 + bootstrap.sh")
def test_bash_021_rerun_does_not_wipe_followthrough(tmp_path):
    plugin_root = tmp_path / "plugin"
    (plugin_root / "data").mkdir(parents=True)
    shutil.copytree(PLUGIN_MIGRATIONS, plugin_root / "data" / "migrations")
    data_home = tmp_path / "xdg"
    data_home.mkdir()

    r1 = _bootstrap(plugin_root, data_home)
    assert r1.returncode == 0, f"first bootstrap failed: {r1.stderr}"
    db = data_home / "software-of-you" / "soy.db"
    assert db.exists()

    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO contacts (name, type, status) VALUES ('Ann', 'individual', 'active')")
    cid = conn.execute("SELECT id FROM contacts WHERE name = 'Ann'").fetchone()[0]
    conn.execute(
        "INSERT INTO relationship_scores (contact_id, score_date, commitment_follow_through) "
        "VALUES (?, date('now'), 0.8)",
        (cid,),
    )
    # Force a 021 re-run by corrupting its recorded checksum.
    conn.execute("UPDATE schema_migrations SET checksum = 'FORCE_RERUN' WHERE filename LIKE '021_%'")
    conn.commit()
    conn.close()

    r2 = _bootstrap(plugin_root, data_home)
    assert r2.returncode == 0, f"second bootstrap failed: {r2.stderr}"

    conn = sqlite3.connect(db)
    val = conn.execute(
        "SELECT commitment_follow_through FROM relationship_scores WHERE contact_id = ?", (cid,)
    ).fetchone()[0]
    conn.close()
    # With -bail the dup-column ALTER aborts the file before the backfill UPDATE,
    # so the re-derived value survives. Without it, the UPDATE would NULL it.
    assert val == 0.8, f"021 backfill wiped a re-derived value on the bash path (got {val!r})"


def test_safe_slug_strips_path_chars():
    assert _safe_slug("a/b/../c") == "a-b-c"
    assert _safe_slug("../../etc/passwd") == "etc-passwd"
    assert _safe_slug("Sarah O'Brien (Acme)") == "sarah-o-brien-acme"
    assert _safe_slug("", "contact") == "contact"
    assert _safe_slug("///", "contact") == "contact"
    for name in ["a/b", "..", "../x", "x/../../y", "..\\..\\win"]:
        s = _safe_slug(name)
        assert "/" not in s and "\\" not in s and ".." not in s


def test_add_analysis_skips_constraint_violations_at_execute(soy_db):
    """A row that constructs fine but violates a DB constraint at INSERT time
    (here: a participant with a non-existent contact_id → FK violation) must be
    skipped and counted, not roll back the whole analysis. Regression for the
    M4 execute-layer gap (execute_lenient)."""
    contacts._add("Ann", "", "", "Acme", "", "individual", "active", None)
    cid = soy_db.execute("SELECT id FROM contacts WHERE name = 'Ann'")[0]["id"]
    tid = transcripts._import("hello world", "T", "paste", None)["result"]["transcript_id"]

    participants = json.dumps([
        {"contact_id": cid, "speaker_label": "You", "is_user": 1},      # valid
        {"contact_id": 999999, "speaker_label": "Ghost", "is_user": 0},  # FK violation
    ])
    res = transcripts._add_analysis(tid, participants, "", "", "", "", "", "", 0)

    # No exception, success reported, and the bad row is counted as skipped.
    assert res["result"]["analysis_stored"] is True
    assert res["result"]["skipped"] >= 1
    # The valid participant was still stored (one bad row didn't nuke the rest).
    stored = soy_db.execute(
        "SELECT COUNT(*) AS c FROM transcript_participants WHERE transcript_id = ?", (tid,)
    )[0]["c"]
    assert stored == 1
