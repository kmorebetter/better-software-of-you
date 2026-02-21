"""Interactions tool — log interactions, manage follow-ups.

Extends contacts with interaction tracking, relationship management,
and follow-up scheduling.
"""

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, execute_many, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def interactions(
        action: str,
        contact_id: int = 0,
        interaction_type: str = "meeting",
        direction: str = "outbound",
        subject: str = "",
        summary: str = "",
        occurred_at: str = "",
        due_date: str = "",
        reason: str = "",
        follow_up_id: int = 0,
        contact_name: str = "",
    ) -> dict:
        """Log interactions with contacts and manage follow-ups.

        Actions:
          log               — Record an interaction (contact_id or contact_name, type, subject required)
          list              — List recent interactions (optional contact_id filter)
          follow_up         — Schedule a follow-up (contact_id, due_date, reason required)
          complete_follow_up — Mark a follow-up done (follow_up_id required)
          list_follow_ups   — List pending follow-ups (optional contact_id filter)

        Interaction types: email, call, meeting, message, other
        Directions: inbound, outbound
        """
        if action == "log":
            return _log(contact_id, contact_name, interaction_type, direction, subject, summary, occurred_at)
        elif action == "list":
            return _list(contact_id)
        elif action == "follow_up":
            return _follow_up(contact_id, contact_name, due_date, reason)
        elif action == "complete_follow_up":
            return _complete_follow_up(follow_up_id)
        elif action == "list_follow_ups":
            return _list_follow_ups(contact_id)
        else:
            return {"error": f"Unknown action: {action}. Use: log, list, follow_up, complete_follow_up, list_follow_ups"}


def _resolve_contact(contact_id, contact_name):
    """Resolve a contact by ID or name."""
    if contact_id:
        rows = execute("SELECT id, name FROM contacts WHERE id = ?", (contact_id,))
        if rows:
            return rows[0]["id"], rows[0]["name"]
        return None, None

    if contact_name:
        rows = execute(
            "SELECT id, name FROM contacts WHERE name LIKE ?",
            (f"%{contact_name}%",),
        )
        if len(rows) == 1:
            return rows[0]["id"], rows[0]["name"]
        elif len(rows) > 1:
            return None, rows_to_dicts(rows)  # ambiguous
        return None, None

    return None, None


def _log(contact_id, contact_name, interaction_type, direction, subject, summary, occurred_at):
    cid, resolved = _resolve_contact(contact_id, contact_name)
    if cid is None:
        if isinstance(resolved, list):
            return {
                "error": "Multiple contacts match. Please specify.",
                "matches": resolved,
            }
        return {"error": "Contact not found. Provide a valid contact_id or contact_name."}

    if not subject:
        return {"error": "Subject is required for logging an interaction."}

    occurred = occurred_at or "datetime('now')"
    if occurred == "datetime('now')":
        # Use SQL default
        execute_many([
            (
                """INSERT INTO contact_interactions (contact_id, type, direction, subject, summary)
                   VALUES (?, ?, ?, ?, ?)""",
                (cid, interaction_type, direction, subject, summary or None),
            ),
            (
                """INSERT INTO activity_log (entity_type, entity_id, action, details)
                   VALUES ('contact', ?, 'interaction_logged', ?)""",
                (cid, f"{interaction_type}: {subject}"),
            ),
        ])
    else:
        execute_many([
            (
                """INSERT INTO contact_interactions (contact_id, type, direction, subject, summary, occurred_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cid, interaction_type, direction, subject, summary or None, occurred_at),
            ),
            (
                """INSERT INTO activity_log (entity_type, entity_id, action, details)
                   VALUES ('contact', ?, 'interaction_logged', ?)""",
                (cid, f"{interaction_type}: {subject}"),
            ),
        ])

    return {
        "result": {"contact_id": cid, "contact_name": resolved, "type": interaction_type, "subject": subject},
        "_context": {
            "suggestions": [
                "Suggest scheduling a follow-up",
                "Ask if there are any commitments from this interaction",
            ],
            "presentation": f"Confirm: logged {interaction_type} with {resolved}.",
        },
    }


def _list(contact_id):
    if contact_id:
        rows = execute(
            """SELECT ci.*, c.name as contact_name FROM contact_interactions ci
               JOIN contacts c ON c.id = ci.contact_id
               WHERE ci.contact_id = ?
               ORDER BY ci.occurred_at DESC LIMIT 20""",
            (contact_id,),
        )
    else:
        rows = execute(
            """SELECT ci.*, c.name as contact_name FROM contact_interactions ci
               JOIN contacts c ON c.id = ci.contact_id
               ORDER BY ci.occurred_at DESC LIMIT 20"""
        )
    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show as a timeline. Use relative dates.",
        },
    }


def _follow_up(contact_id, contact_name, due_date, reason):
    cid, resolved = _resolve_contact(contact_id, contact_name)
    if cid is None:
        if isinstance(resolved, list):
            return {"error": "Multiple contacts match.", "matches": resolved}
        return {"error": "Contact not found."}

    if not due_date or not reason:
        return {"error": "Both due_date (YYYY-MM-DD) and reason are required."}

    fid = execute_many([
        (
            "INSERT INTO follow_ups (contact_id, due_date, reason) VALUES (?, ?, ?)",
            (cid, due_date, reason),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('contact', ?, 'follow_up_created', ?)""",
            (cid, f"Due {due_date}: {reason}"),
        ),
    ])

    return {
        "result": {"follow_up_id": fid, "contact_name": resolved, "due_date": due_date, "reason": reason},
        "_context": {
            "suggestions": ["Confirm the follow-up is set"],
            "presentation": f"Follow-up scheduled with {resolved} for {due_date}.",
        },
    }


def _complete_follow_up(follow_up_id):
    if not follow_up_id:
        return {"error": "follow_up_id is required."}

    rows = execute(
        """SELECT f.*, c.name as contact_name FROM follow_ups f
           JOIN contacts c ON c.id = f.contact_id WHERE f.id = ?""",
        (follow_up_id,),
    )
    if not rows:
        return {"error": f"No follow-up with id {follow_up_id}."}

    fu = rows_to_dicts(rows)[0]
    execute_many([
        (
            "UPDATE follow_ups SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
            (follow_up_id,),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('contact', ?, 'follow_up_completed', ?)""",
            (fu["contact_id"], fu["reason"]),
        ),
    ])

    return {
        "result": {"follow_up_id": follow_up_id, "contact_name": fu["contact_name"], "status": "completed"},
        "_context": {
            "suggestions": ["Ask if they want to schedule another follow-up"],
            "presentation": f"Follow-up with {fu['contact_name']} marked complete.",
        },
    }


def _list_follow_ups(contact_id):
    if contact_id:
        rows = execute(
            """SELECT f.*, c.name as contact_name FROM follow_ups f
               JOIN contacts c ON c.id = f.contact_id
               WHERE f.contact_id = ? AND f.status = 'pending'
               ORDER BY f.due_date ASC""",
            (contact_id,),
        )
    else:
        rows = execute(
            """SELECT f.*, c.name as contact_name FROM follow_ups f
               JOIN contacts c ON c.id = f.contact_id
               WHERE f.status = 'pending'
               ORDER BY f.due_date ASC"""
        )

    follow_ups = rows_to_dicts(rows)

    # Flag overdue
    from datetime import date
    today = date.today().isoformat()
    for fu in follow_ups:
        fu["overdue"] = fu["due_date"] < today

    return {
        "result": follow_ups,
        "count": len(follow_ups),
        "overdue_count": sum(1 for f in follow_ups if f["overdue"]),
        "_context": {
            "suggestions": ["Highlight overdue items", "Offer to complete follow-ups"],
            "presentation": "Show as a list grouped by urgency. Red for overdue, amber for due today.",
        },
    }
