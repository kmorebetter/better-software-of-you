"""Tests for L5 (day-count rounding) in the SHADOWING migrations.

U10 added rounding (``+ 0.5`` before ``CAST(... AS INTEGER)``) to the day-count
columns in ``014_computed_views.sql``. But migrations 016 and 020 *redefine* the
highest-traffic views and run AFTER 014, so their day-counts truncated until L5.

Migration apply order is 014 → 016 → 020, last-writer-wins per view name:

* ``v_contact_health``  — live copy is **020** (includes ``slack_messages``)
* ``v_nudge_items``     — live copy is **020** (includes ``slack_messages``)
* ``v_discovery_candidates`` — live copy is **016** (includes ``google_accounts``);
  this is the ONLY runtime guard on 016's rounding, hence the dedicated test.

Each test seeds an activity ~1.92 days in the past/future (``-46 hours`` =
1.9167 d). Truncation yields 1; rounding yields 2. The ``soy_db`` fixture (see
conftest) provides an isolated temp DB with all migrations applied.
"""

from software_of_you.tools import contacts


# ─────────────────────────────────────────────────────────────────────────
# v_contact_health.days_silent  (shadowed by migration 020)
# ─────────────────────────────────────────────────────────────────────────


def test_contact_health_days_silent_rounds(soy_db):
    # Last activity ~1.92 days ago must round to 2, not truncate to 1.
    cid = contacts._add("Riley", "", "", "", "", "individual", "active", None)[
        "result"
    ]["contact_id"]
    soy_db.execute_write(
        """INSERT INTO contact_interactions
               (contact_id, type, direction, summary, occurred_at)
           VALUES (?, 'call', 'outbound', 'Sync', datetime('now', '-46 hours'))""",
        (cid,),
    )

    rows = soy_db.execute(
        "SELECT days_silent FROM v_contact_health WHERE id = ?", (cid,)
    )
    assert len(rows) == 1
    assert rows[0]["days_silent"] == 2


# ─────────────────────────────────────────────────────────────────────────
# v_nudge_items.days_value  (shadowed by migration 020)
# ─────────────────────────────────────────────────────────────────────────


def test_nudge_items_days_value_rounds(soy_db):
    # An overdue follow-up ~1.92 days past due surfaces in the urgent
    # follow_up branch; its days_value must round to 2.
    cid = contacts._add("Morgan", "", "", "", "", "individual", "active", None)[
        "result"
    ]["contact_id"]
    fid = soy_db.execute_write(
        """INSERT INTO follow_ups (contact_id, due_date, reason, status)
           VALUES (?, datetime('now', '-46 hours'), 'Reply to proposal', 'pending')""",
        (cid,),
    )

    rows = soy_db.execute(
        """SELECT days_value FROM v_nudge_items
           WHERE nudge_type = 'follow_up' AND entity_id = ?""",
        (fid,),
    )
    assert len(rows) == 1
    assert rows[0]["days_value"] == 2


# ─────────────────────────────────────────────────────────────────────────
# v_discovery_candidates.days_since_last  (shadowed by migration 016)
# This is the ONLY runtime guard on 016's rounding.
# ─────────────────────────────────────────────────────────────────────────


def test_discovery_candidates_days_since_last_rounds(soy_db):
    # A frequent inbound emailer not in the CRM, last seen ~1.92 days ago,
    # must surface in v_discovery_candidates with days_since_last rounded to 2.
    # The address must clear every NOT LIKE filter and not be a contact or a
    # connected google_account. HAVING email_count >= 2, so seed two emails.
    addr = "frequent.person@example-domain.test"
    soy_db.execute_write(
        """INSERT INTO emails (gmail_id, thread_id, contact_id, direction,
                               from_address, from_name, received_at)
           VALUES ('g1', 'thr-1', NULL, 'inbound', ?, 'Frequent Person',
                   datetime('now', '-46 hours'))""",
        (addr,),
    )
    soy_db.execute_write(
        """INSERT INTO emails (gmail_id, thread_id, contact_id, direction,
                               from_address, from_name, received_at)
           VALUES ('g2', 'thr-2', NULL, 'inbound', ?, 'Frequent Person',
                   datetime('now', '-5 days'))""",
        (addr,),
    )

    rows = soy_db.execute(
        "SELECT days_since_last FROM v_discovery_candidates WHERE from_address = ?",
        (addr,),
    )
    assert len(rows) == 1
    # MAX(received_at) is the -46h email → ~1.92 days → rounds to 2 (not 1).
    assert rows[0]["days_since_last"] == 2
