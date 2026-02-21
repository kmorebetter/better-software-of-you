"""Decisions tool — log decisions with context, rationale, and outcomes."""

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, execute_many, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def decisions(
        action: str,
        title: str = "",
        context: str = "",
        options_considered: str = "",
        decision: str = "",
        rationale: str = "",
        outcome: str = "",
        status: str = "decided",
        project_id: int = 0,
        contact_id: int = 0,
        decision_id: int = 0,
    ) -> dict:
        """Track decisions with full context, rationale, and outcomes.

        Actions:
          log     — Record a new decision (title, decision required)
          list    — List decisions (optional status filter)
          get     — Get full decision details (decision_id required)
          outcome — Record the outcome of a decision (decision_id, outcome required)
          revisit — Mark a decision for revisiting (decision_id required)

        options_considered should be a JSON array of strings: '["Option A", "Option B"]'
        Status values: open, decided, revisit, validated, regretted
        """
        if action == "log":
            return _log(title, context, options_considered, decision, rationale, status, project_id, contact_id)
        elif action == "list":
            return _list(status)
        elif action == "get":
            return _get(decision_id)
        elif action == "outcome":
            return _outcome(decision_id, outcome, status)
        elif action == "revisit":
            return _revisit(decision_id)
        else:
            return {"error": f"Unknown action: {action}. Use: log, list, get, outcome, revisit"}


def _log(title, context, options_considered, decision, rationale, status, project_id, contact_id):
    if not title or not decision:
        return {"error": "Both title and decision text are required."}

    did = execute_many([
        (
            """INSERT INTO decisions (title, context, options_considered, decision, rationale, status, project_id, contact_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, context or None, options_considered or None, decision,
             rationale or None, status, project_id or None, contact_id or None),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('decision', last_insert_rowid(), 'logged', ?)""",
            (f"Decision: {title}",),
        ),
    ])

    return {
        "result": {"decision_id": did, "title": title, "status": status},
        "_context": {
            "suggestions": [
                "Set a reminder to check the outcome later",
                "Link to a project if relevant",
            ],
            "presentation": "Confirm the decision was logged with its rationale.",
        },
    }


def _list(status):
    if status and status not in ("all",):
        rows = execute(
            """SELECT d.id, d.title, d.status, d.decided_at,
                      p.name as project_name, c.name as contact_name
               FROM decisions d
               LEFT JOIN projects p ON d.project_id = p.id
               LEFT JOIN contacts c ON d.contact_id = c.id
               WHERE d.status = ? ORDER BY d.decided_at DESC""",
            (status,),
        )
    else:
        rows = execute(
            """SELECT d.id, d.title, d.status, d.decided_at,
                      p.name as project_name, c.name as contact_name
               FROM decisions d
               LEFT JOIN projects p ON d.project_id = p.id
               LEFT JOIN contacts c ON d.contact_id = c.id
               ORDER BY d.decided_at DESC LIMIT 20"""
        )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show as a timeline. Highlight decisions needing revisit.",
        },
    }


def _get(decision_id):
    if not decision_id:
        return {"error": "decision_id is required."}

    rows = execute(
        """SELECT d.*, p.name as project_name, c.name as contact_name
           FROM decisions d
           LEFT JOIN projects p ON d.project_id = p.id
           LEFT JOIN contacts c ON d.contact_id = c.id
           WHERE d.id = ?""",
        (decision_id,),
    )
    if not rows:
        return {"error": f"No decision with id {decision_id}."}

    return {
        "result": rows_to_dicts(rows)[0],
        "_context": {
            "suggestions": [
                "Offer to record an outcome if status is 'decided'",
                "Suggest revisiting if it's been a while",
            ],
            "presentation": "Show full decision context: what, why, what else was considered.",
        },
    }


def _outcome(decision_id, outcome, status):
    if not decision_id or not outcome:
        return {"error": "decision_id and outcome text are required."}

    new_status = status if status in ("validated", "regretted") else "validated"

    execute_many([
        (
            """UPDATE decisions SET outcome = ?, outcome_date = date('now'),
               status = ?, updated_at = datetime('now') WHERE id = ?""",
            (outcome, new_status, decision_id),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('decision', ?, 'outcome_recorded', ?)""",
            (decision_id, outcome),
        ),
    ])

    return {
        "result": {"decision_id": decision_id, "status": new_status, "outcome": outcome},
        "_context": {"presentation": "Confirm the outcome was recorded."},
    }


def _revisit(decision_id):
    if not decision_id:
        return {"error": "decision_id is required."}

    execute_many([
        (
            "UPDATE decisions SET status = 'revisit', updated_at = datetime('now') WHERE id = ?",
            (decision_id,),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('decision', ?, 'marked_revisit', 'Decision flagged for revisiting')""",
            (decision_id,),
        ),
    ])

    return {
        "result": {"decision_id": decision_id, "status": "revisit"},
        "_context": {"presentation": "Decision marked for revisiting."},
    }
