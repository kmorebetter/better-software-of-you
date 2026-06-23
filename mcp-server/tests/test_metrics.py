"""Tests for the bidirectional commitment-follow-through metric (U5 / H2, M3).

``commitment_follow_through`` is NOT a SQL-view computation — ``v_contact_health``
only READS the latest STORED ``relationship_scores.commitment_follow_through``
(``ORDER BY score_date DESC LIMIT 1``). The value is derived by Claude per
``skills/conversation-intelligence/references/scoring-methodology.md`` and written by
``transcripts.py`` ``_add_analysis``. The old formula divided by an ``overdue`` status
no code ever writes, so stored values were bimodal (1.0 or NULL) — wrong — and they
gate relationship_depth/sentiment.

These guard:
  1. migration 021 adds ``commitment_follow_through_inbound``;
  2. the write path stores BOTH directions independently;
  3. migration 021 backfills (NULLs) the stale outbound values;
  4. the scoring doc no longer defines the metric against an ``overdue`` status.
"""

import json
from pathlib import Path

from software_of_you.tools import contacts, transcripts

SCORING_DOC = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "conversation-intelligence"
    / "references"
    / "scoring-methodology.md"
)


def test_inbound_column_exists_after_migrations(soy_db):
    """After all migrations, relationship_scores has the inbound column."""
    cols = {row["name"] for row in soy_db.execute("PRAGMA table_info(relationship_scores)")}
    assert "commitment_follow_through" in cols
    assert "commitment_follow_through_inbound" in cols


def test_write_path_stores_both_directions(soy_db):
    """_add_analysis must persist outbound AND inbound follow-through, independently."""
    # FK enforcement is ON (PRAGMA foreign_keys=ON), so the relationship_scores row
    # needs a real contact and the analysis needs a real transcript.
    contact = contacts._add("Dana", "dana@acme.com", "", "Acme", "", "individual", "active", None)
    contact_id = contact["result"]["contact_id"]

    imported = transcripts._import("hello world", "Sync call", "paste", None)
    tid = imported["result"]["transcript_id"]

    # Distinct values for the two directions so we prove they don't collapse.
    scores = json.dumps([
        {
            "contact_id": contact_id,
            "meeting_frequency": 0.5,
            "talk_ratio_avg": 0.4,
            "commitment_follow_through": 0.75,
            "commitment_follow_through_inbound": 0.25,
            "relationship_depth": "professional",
            "trajectory": "stable",
            "notes": "Professional — 4 meetings in 90d, follow-through user:75% contact:25%",
        }
    ])

    # _add_analysis is all-positional, 9 args, no defaults.
    result = transcripts._add_analysis(tid, None, None, None, None, scores, None, None, None)
    assert result["result"]["analysis_stored"] is True

    rows = soy_db.execute(
        """SELECT commitment_follow_through, commitment_follow_through_inbound
           FROM relationship_scores WHERE contact_id = ?""",
        (contact_id,),
    )
    assert len(rows) == 1
    assert rows[0]["commitment_follow_through"] == 0.75
    assert rows[0]["commitment_follow_through_inbound"] == 0.25


def test_write_path_one_sided_relationship_keeps_null(soy_db):
    """A one-sided relationship stores one real value and NULL for the other —
    never echoes the same number into both columns (the LIMIT 1 read trap)."""
    contact = contacts._add("Lee", "lee@acme.com", "", "Acme", "", "individual", "active", None)
    contact_id = contact["result"]["contact_id"]
    imported = transcripts._import("text", "1:1", "paste", None)
    tid = imported["result"]["transcript_id"]

    scores = json.dumps([
        {
            "contact_id": contact_id,
            "commitment_follow_through": 0.6,
            # inbound omitted entirely -> s.get(...) returns None -> stored NULL
            "relationship_depth": "professional",
            "trajectory": "stable",
            "notes": "one-sided",
        }
    ])
    transcripts._add_analysis(tid, None, None, None, None, scores, None, None, None)

    rows = soy_db.execute(
        """SELECT commitment_follow_through, commitment_follow_through_inbound
           FROM relationship_scores WHERE contact_id = ?""",
        (contact_id,),
    )
    assert len(rows) == 1
    assert rows[0]["commitment_follow_through"] == 0.6
    assert rows[0]["commitment_follow_through_inbound"] is None


def test_migration_021_backfills_stale_outbound_to_null(tmp_db_paths):
    """A pre-existing relationship_scores row with a legacy follow-through value
    must read NULL after migration 021 runs (so the installed base stops surfacing
    the old skewed number). Apply migrations 001-020, insert a stale row, THEN apply
    021 — inserting after 021 would prove nothing because the backfill already ran.
    """
    from software_of_you import db as db_module

    conn = db_module.get_connection()
    try:
        # Apply every migration EXCEPT 021, in filename order.
        for sql_file in sorted(db_module.MIGRATIONS_DIR.glob("*.sql")):
            if sql_file.name.startswith("021"):
                continue
            conn.executescript(sql_file.read_text())
        conn.commit()

        # The inbound column must not exist yet (021 hasn't run).
        cols_before = {r[1] for r in conn.execute("PRAGMA table_info(relationship_scores)")}
        assert "commitment_follow_through_inbound" not in cols_before

        # FK enforcement is ON — create a real contact first. (Only `name` is
        # required; `type`/`status` have defaults.)
        conn.execute("INSERT INTO contacts (name) VALUES ('Stale')")
        contact_id = conn.execute("SELECT id FROM contacts WHERE name = 'Stale'").fetchone()[0]
        conn.execute(
            """INSERT INTO relationship_scores
               (contact_id, score_date, commitment_follow_through)
               VALUES (?, date('now'), 1.0)""",
            (contact_id,),
        )
        conn.commit()

        stale = conn.execute(
            "SELECT commitment_follow_through FROM relationship_scores WHERE contact_id = ?",
            (contact_id,),
        ).fetchone()[0]
        assert stale == 1.0

        # Now apply the REAL 021 file (exercises the actual migration, not hand-copied SQL).
        migration_021 = next(db_module.MIGRATIONS_DIR.glob("021_*.sql"))
        conn.executescript(migration_021.read_text())
        conn.commit()

        # Inbound column now exists; the stale outbound value is NULLed.
        cols_after = {r[1] for r in conn.execute("PRAGMA table_info(relationship_scores)")}
        assert "commitment_follow_through_inbound" in cols_after

        backfilled = conn.execute(
            "SELECT commitment_follow_through FROM relationship_scores WHERE contact_id = ?",
            (contact_id,),
        ).fetchone()[0]
        assert backfilled is None
    finally:
        conn.close()


def test_scoring_doc_followthrough_no_longer_uses_overdue_status():
    """The follow-through section of the scoring doc must no longer define the
    metric against an 'overdue' status (the old broken denominator). 'overdue'
    legitimately survives elsewhere (Trajectory At-Risk, Sentiment) — a different
    metric, out of U5's scope — so we scope the guard to the follow-through section.
    """
    content = SCORING_DOC.read_text()

    # The old denominator string appeared ONLY in the follow-through section.
    assert "IN ('completed', 'overdue')" not in content
    assert "IN ('completed','overdue')" not in content

    # Scope to the commitment_follow_through section and assert the corrected
    # predicate replaced the overdue-status one.
    start = content.index("### commitment_follow_through")
    end = content.index("### talk_ratio_avg")
    section = content[start:end]
    assert "status = 'open' AND deadline_date < date('now')" in section
    assert "BIDIRECTIONAL" in section
    assert "commitment_follow_through_inbound" in section
