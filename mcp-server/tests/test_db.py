"""Tests for insert_with_log and the create-path call sites that use it.

These guard the bug where ``execute_many`` returned the *final* statement's
``lastrowid`` — the activity_log row's id, not the entity's — so create paths
handed back the wrong id. ``insert_with_log`` captures and returns the entity's
rowid while still running the log insert on the same connection (so an inline
``last_insert_rowid()`` in the log resolves to the entity).
"""

from software_of_you.tools import contacts, projects, transcripts


def test_insert_with_log_returns_entity_id_not_log_id(soy_db):
    # Pre-insert several activity_log rows so its rowids diverge from contacts'.
    # Without the fix, the create path would return one of these log rowids.
    conn = soy_db.get_connection()
    try:
        for i in range(5):
            conn.execute(
                """INSERT INTO activity_log (entity_type, entity_id, action, details)
                   VALUES ('seed', ?, 'seed', 'divergence padding')""",
                (i,),
            )
        conn.commit()
    finally:
        conn.close()

    # 'individual' is a valid contacts.type (CHECK allows individual|company).
    result = contacts._add("Ann", "", "", "Acme", "", "individual", "active", None)
    contact_id = result["result"]["contact_id"]

    rows = soy_db.execute("SELECT id FROM contacts WHERE name = 'Ann'")
    assert len(rows) == 1
    expected_id = rows[0]["id"]

    # The returned id must be the contact's id, not the log row's id.
    assert contact_id == expected_id

    # And the activity_log row for the create must reference that same contact id.
    log_rows = soy_db.execute(
        """SELECT entity_id FROM activity_log
           WHERE entity_type = 'contact' AND action = 'created'"""
    )
    assert len(log_rows) == 1
    assert log_rows[0]["entity_id"] == expected_id


def test_create_then_get_roundtrips(soy_db):
    result = contacts._add("Bob", "bob@acme.com", "", "Acme", "", "individual", "active", None)
    contact_id = result["result"]["contact_id"]

    got = contacts._get(contact_id)
    assert "error" not in got
    assert got["result"]["id"] == contact_id
    assert got["result"]["name"] == "Bob"


def test_transcript_import_without_occurred_at(soy_db):
    # occurred_at is NOT NULL with no default; passing None must COALESCE to now().
    result = transcripts._import("hello world", "Test", "paste", None)
    assert "error" not in result
    tid = result["result"]["transcript_id"]

    rows = soy_db.execute("SELECT occurred_at FROM transcripts WHERE id = ?", (tid,))
    assert len(rows) == 1
    assert rows[0]["occurred_at"] is not None


def test_project_task_milestone_ids(soy_db):
    # Pre-seed activity_log so its rowids run ahead of the entity tables. Under
    # the old bug, the create paths returned the activity_log row's id; here that
    # would be a large, wrong number rather than the actual task/milestone rowid.
    conn = soy_db.get_connection()
    try:
        for i in range(10):
            conn.execute(
                """INSERT INTO activity_log (entity_type, entity_id, action, details)
                   VALUES ('seed', ?, 'seed', 'divergence padding')""",
                (i,),
            )
        conn.commit()
    finally:
        conn.close()

    proj = projects._add("Launch", "", 0, "", "active", "high", "", "")
    project_id = proj["result"]["project_id"]
    prows = soy_db.execute("SELECT id FROM projects WHERE name = 'Launch'")
    assert len(prows) == 1
    assert project_id == prows[0]["id"]

    task = projects._add_task(project_id, "Write spec", "", "medium", "")
    task_id = task["result"]["task_id"]
    # Returned id must be the task's rowid (resolving to the right row), not the
    # activity_log row's id that the old execute_many path leaked.
    trows = soy_db.execute("SELECT id FROM tasks WHERE title = 'Write spec'")
    assert len(trows) == 1
    assert task_id == trows[0]["id"]
    trow = soy_db.execute(
        "SELECT project_id, title FROM tasks WHERE id = ?", (task_id,)
    )
    assert trow[0]["project_id"] == project_id
    assert trow[0]["title"] == "Write spec"

    milestone = projects._add_milestone(project_id, "Beta", "", "")
    milestone_id = milestone["result"]["milestone_id"]
    mids = soy_db.execute("SELECT id FROM milestones WHERE name = 'Beta'")
    assert len(mids) == 1
    assert milestone_id == mids[0]["id"]
    mrows = soy_db.execute(
        "SELECT project_id, name FROM milestones WHERE id = ?", (milestone_id,)
    )
    assert mrows[0]["project_id"] == project_id
    assert mrows[0]["name"] == "Beta"
