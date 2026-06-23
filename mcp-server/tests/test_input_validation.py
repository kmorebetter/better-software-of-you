"""Tests for U10: enum validation (L4), day-count rounding (L5),
shared fuzzy resolver (L6), and the interactions occurred-at collapse (L7).

Private tool functions are imported and called directly — no MCP server is
needed. The ``soy_db`` fixture (see conftest) provides an isolated temp DB with
all migrations applied.
"""

from software_of_you.tools import contacts, interactions, projects
from software_of_you.tools._resolve import resolve_contact_by_name


# ─────────────────────────────────────────────────────────────────────────
# L4: enum validation at the tool boundary
# ─────────────────────────────────────────────────────────────────────────


def test_update_task_rejects_bad_status_and_writes_nothing(soy_db):
    proj = projects._add("Launch", "", 0, "", "active", "high", "", "")
    project_id = proj["result"]["project_id"]
    task = projects._add_task(project_id, "Write spec", "", "medium", "")
    task_id = task["result"]["task_id"]

    # "complete" is a typo — not in {todo, in_progress, done, blocked}.
    result = projects._update_task(task_id, "complete")
    assert "error" in result
    assert "task_status must be one of" in result["error"]
    assert "complete" in result["error"]

    # Nothing was written: the task keeps its original status and no completed_at.
    rows = soy_db.execute(
        "SELECT status, completed_at FROM tasks WHERE id = ?", (task_id,)
    )
    assert rows[0]["status"] == "todo"
    assert rows[0]["completed_at"] is None


def test_update_task_done_succeeds_and_stamps_completed_at(soy_db):
    proj = projects._add("Launch", "", 0, "", "active", "high", "", "")
    project_id = proj["result"]["project_id"]
    task = projects._add_task(project_id, "Ship it", "", "medium", "")
    task_id = task["result"]["task_id"]

    result = projects._update_task(task_id, "done")
    assert "error" not in result
    assert result["result"]["status"] == "done"

    rows = soy_db.execute(
        "SELECT status, completed_at FROM tasks WHERE id = ?", (task_id,)
    )
    assert rows[0]["status"] == "done"
    assert rows[0]["completed_at"] is not None


def test_contacts_add_rejects_bad_contact_type(soy_db):
    # contacts.type CHECK allows only {individual, company}.
    result = contacts._add("Zed", "", "", "", "", "robot", "active", None)
    assert "error" in result
    assert "contact_type must be one of" in result["error"]
    assert "robot" in result["error"]

    # No contact row was written.
    rows = soy_db.execute("SELECT COUNT(*) AS n FROM contacts WHERE name = 'Zed'")
    assert rows[0]["n"] == 0


def test_contacts_add_rejects_bad_status(soy_db):
    # contacts.status CHECK allows only {active, inactive, archived}.
    result = contacts._add("Yan", "", "", "", "", "individual", "deleted", None)
    assert "error" in result
    assert "status must be one of" in result["error"]


def test_projects_add_rejects_bad_priority(soy_db):
    result = projects._add("Bad", "", 0, "", "active", "critical", "", "")
    assert "error" in result
    assert "priority must be one of" in result["error"]


# ─────────────────────────────────────────────────────────────────────────
# L5: day-count rounding (round, not truncate)
# ─────────────────────────────────────────────────────────────────────────


def test_project_days_to_target_rounds(soy_db):
    # A target ~1.92 days out (+46 hours) must round to 2, not truncate to 1.
    # v_project_health.days_to_target reads
    #   CAST(julianday(target_date) - julianday('now') + 0.5 AS INTEGER).
    # We assert against v_project_health (not v_contact_health / v_nudge_items),
    # because those two are redefined in migrations 016/020 *after* 014 — so the
    # 014 rounding is shadowed there at runtime. v_project_health is owned by 014
    # only, so the rounding is observable. (See report: the 016/020 owner must
    # mirror this rounding for v_contact_health/v_nudge_items to be fixed too.)
    soy_db.execute_write(
        """INSERT INTO projects (name, status, target_date)
           VALUES ('Round', 'active', datetime('now', '+46 hours'))""",
    )

    rows = soy_db.execute(
        "SELECT days_to_target FROM v_project_health WHERE name = 'Round'"
    )
    assert len(rows) == 1
    # Truncation would give 1; rounding gives 2.
    assert rows[0]["days_to_target"] == 2


def test_commitment_days_overdue_rounds(soy_db):
    # Cross-check with v_commitment_status.days_overdue (also 014-only, not
    # shadowed). A deadline ~1.92 days past (-46 hours) must round to 2.
    cid = contacts._add("Cara", "", "", "", "", "individual", "active", None)[
        "result"
    ]["contact_id"]
    # commitments.transcript_id is a NOT NULL FK — seed a minimal transcript row
    # directly (avoid coupling to the sibling-edited transcripts.py).
    tid = soy_db.execute_write(
        """INSERT INTO transcripts (title, raw_text, source, occurred_at)
           VALUES ('Sync', 'x', 'paste', datetime('now', '-3 days'))"""
    )
    soy_db.execute_write(
        """INSERT INTO commitments (transcript_id, owner_contact_id, description, deadline_date, status)
           VALUES (?, ?, 'Send deck', datetime('now', '-46 hours'), 'open')""",
        (tid, cid),
    )

    rows = soy_db.execute(
        "SELECT days_overdue FROM v_commitment_status WHERE description = 'Send deck'"
    )
    assert len(rows) == 1
    assert rows[0]["days_overdue"] == 2


# ─────────────────────────────────────────────────────────────────────────
# L6: shared fuzzy resolver surfaces ambiguity instead of dropping it
# ─────────────────────────────────────────────────────────────────────────


def test_resolver_unique_match_returns_id(soy_db):
    cid = contacts._add("Christopher Lee", "", "", "", "", "individual", "active", None)[
        "result"
    ]["contact_id"]

    match = resolve_contact_by_name("Christopher")
    assert match is not None
    assert match.get("id") == cid
    assert match.get("name") == "Christopher Lee"


def test_resolver_multiple_matches_is_ambiguous_not_none(soy_db):
    contacts._add("Chris Adams", "", "", "", "", "individual", "active", None)
    contacts._add("Chris Baker", "", "", "", "", "individual", "active", None)

    match = resolve_contact_by_name("Chris")
    # Must surface ambiguity — not silently return None or pick one.
    assert match is not None
    assert "ambiguous" in match
    assert "id" not in match
    names = {m["name"] for m in match["ambiguous"]}
    assert names == {"Chris Adams", "Chris Baker"}


def test_resolver_no_match_returns_none(soy_db):
    assert resolve_contact_by_name("Nobody") is None
    assert resolve_contact_by_name("") is None


def test_interactions_log_reports_ambiguity(soy_db):
    contacts._add("Sam North", "", "", "", "", "individual", "active", None)
    contacts._add("Sam South", "", "", "", "", "individual", "active", None)

    result = interactions._log(0, "Sam", "meeting", "outbound", "Sync", "", "")
    assert "error" in result
    assert "Multiple contacts match" in result["error"]
    assert "matches" in result
    assert len(result["matches"]) == 2


# ─────────────────────────────────────────────────────────────────────────
# L7: interactions occurred-at collapse (single COALESCE path)
# ─────────────────────────────────────────────────────────────────────────


def test_log_without_occurred_at_defaults_to_now(soy_db):
    cid = contacts._add("Dana", "", "", "", "", "individual", "active", None)[
        "result"
    ]["contact_id"]

    result = interactions._log(cid, "", "call", "outbound", "Quick call", "", "")
    assert "error" not in result

    rows = soy_db.execute(
        "SELECT occurred_at FROM contact_interactions WHERE contact_id = ?", (cid,)
    )
    assert len(rows) == 1
    assert rows[0]["occurred_at"] is not None


def test_log_with_occurred_at_stored_verbatim(soy_db):
    cid = contacts._add("Eli", "", "", "", "", "individual", "active", None)[
        "result"
    ]["contact_id"]

    when = "2026-01-15 09:30:00"
    result = interactions._log(cid, "", "meeting", "inbound", "Kickoff", "", when)
    assert "error" not in result

    rows = soy_db.execute(
        "SELECT occurred_at FROM contact_interactions WHERE contact_id = ?", (cid,)
    )
    assert len(rows) == 1
    assert rows[0]["occurred_at"] == when
