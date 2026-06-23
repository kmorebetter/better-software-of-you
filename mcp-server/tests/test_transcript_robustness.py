"""Tests for transcript-ingest robustness and weekly_review accuracy (U8 / M4, M5).

M4 — ``_add_analysis`` previously wrapped each WHOLE section for-loop in a single
``except (json.JSONDecodeError, KeyError): pass``, so ONE malformed item dropped the
ENTIRE category while the function still reported ``analysis_stored: True``. The fix
guards the per-item build individually: a single bad item is skipped (not the whole
category), a ``skipped`` counter accumulates across all sections, and it is returned
in ``result["result"]["skipped"]`` so partial data loss is visible.

M5 — "commitments made this week" was counted from ``v_commitment_status``, which
filters ``status IN ('open','overdue')``. A commitment made AND completed in the same
week was therefore excluded from "made". The fix counts from the base ``commitments``
table by ``created_at``, independent of status.
"""

import json

from mcp.server.fastmcp import FastMCP

from software_of_you.tools import contacts, intelligence, transcripts


# ---------------------------------------------------------------------------
# M4 — per-item robustness in _add_analysis
# ---------------------------------------------------------------------------

def test_one_malformed_commitment_does_not_drop_the_others(soy_db):
    """4 valid commitments + 1 malformed (missing required ``description``) → the
    4 valid ones are stored and ``skipped`` reports the single bad item, instead
    of the old behavior where one bad item nuked the whole category silently."""
    imported = transcripts._import("hello world", "Sync call", "paste", None)
    tid = imported["result"]["transcript_id"]

    # The malformed item sits in the MIDDLE on purpose: the old code appended to a
    # shared statements list incrementally inside one try, so a bad item dropped
    # itself AND every item after it in the same section. With the bad item middle,
    # old code stores only 2; the per-item guard stores all 4. So `stored == 4`
    # genuinely proves the fix (not just the presence of the `skipped` key).
    commitments_data = json.dumps([
        {"description": "Send the proposal"},
        {"description": "Schedule the kickoff"},
        # malformed: missing the required "description" key → KeyError on build
        {"is_user_commitment": 1},
        {"description": "Share the deck"},
        {"description": "Follow up on pricing"},
    ])

    # _add_analysis is all-positional, 9 args; commitments_data is the 4th.
    result = transcripts._add_analysis(tid, None, None, commitments_data, None, None, None, None, None)

    assert result["result"]["analysis_stored"] is True

    # The count is the load-bearing assertion: with the bad item in the middle,
    # the OLD single-try-per-section code aborts after 2 appends and stores 2;
    # the per-item guard stores all 4.
    stored = soy_db.execute(
        "SELECT COUNT(*) AS n FROM commitments WHERE transcript_id = ?", (tid,)
    )
    assert stored[0]["n"] == 4

    # And the skip is surfaced so partial loss is visible, not reported as success.
    assert result["result"]["skipped"] >= 1


def test_all_malformed_category_does_not_nuke_other_valid_categories(soy_db):
    """An ENTIRELY malformed commitments category stores 0 commitments and counts
    every bad item in ``skipped`` — while a VALID participants category in the SAME
    call is still stored. Proves one bad category no longer drops the rest."""
    imported = transcripts._import("hello world", "Team sync", "paste", None)
    tid = imported["result"]["transcript_id"]

    # Every commitment is missing the required "description" → all skipped.
    bad_commitments = json.dumps([
        {"owner_contact_id": None},
        {"is_user_commitment": 0},
        {"deadline_mentioned": "Friday"},
    ])
    # Valid participants (speaker_label present; contact_id is nullable, no FK).
    good_participants = json.dumps([
        {"speaker_label": "A", "is_user": 1},
        {"speaker_label": "B"},
    ])

    result = transcripts._add_analysis(
        tid, good_participants, None, bad_commitments, None, None, None, None, None
    )

    assert result["result"]["analysis_stored"] is True
    # All 3 malformed commitments were skipped.
    assert result["result"]["skipped"] >= 3

    n_commitments = soy_db.execute(
        "SELECT COUNT(*) AS n FROM commitments WHERE transcript_id = ?", (tid,)
    )[0]["n"]
    assert n_commitments == 0  # the bad category stored nothing...

    n_participants = soy_db.execute(
        "SELECT COUNT(*) AS n FROM transcript_participants WHERE transcript_id = ?", (tid,)
    )[0]["n"]
    assert n_participants == 2  # ...but the valid category survived.


# ---------------------------------------------------------------------------
# M5 — weekly_review "made this week" counts status-independently
# ---------------------------------------------------------------------------

def _get_weekly_review(monkeypatch):
    """Register the intelligence tools on a throwaway FastMCP server and return the
    ``weekly_review`` callable. Stub the auto-sync hooks so the test is deterministic
    and never reaches the network."""
    monkeypatch.setattr(intelligence, "_auto_sync_all", lambda: None)
    monkeypatch.setattr(intelligence, "_auto_sync_slack", lambda: None)
    server = FastMCP("test")
    intelligence.register(server)
    return server._tool_manager._tools["weekly_review"].fn


def test_commitment_made_and_completed_same_week_is_counted_as_made(soy_db, monkeypatch):
    """A commitment created AND completed in the current week must count in
    weekly_review's "made this week" total — not just "completed". The old query
    read v_commitment_status (status IN open/overdue) and excluded it."""
    # commitments.transcript_id is NOT NULL with FK enforcement ON.
    imported = transcripts._import("text", "1:1", "paste", None)
    tid = imported["result"]["transcript_id"]

    # Created AND completed right now (this ISO week), with status='completed'.
    # Use execute_write — db.execute opens a read-only connection and never commits.
    soy_db.execute_write(
        """INSERT INTO commitments
           (transcript_id, description, status, created_at, completed_at)
           VALUES (?, ?, 'completed', datetime('now'), datetime('now'))""",
        (tid, "Made and done this week"),
    )

    weekly_review = _get_weekly_review(monkeypatch)
    result = weekly_review(week_offset=0)

    commits = result["result"]["commitments"] if "result" in result else result["commitments"]
    assert commits["made"] >= 1, "same-week made+completed commitment must count as 'made'"
    assert commits["completed"] >= 1, "and it should still count as 'completed'"
    # Regression invariant from the plan: made >= completed for same-week activity.
    assert commits["made"] >= commits["completed"]
