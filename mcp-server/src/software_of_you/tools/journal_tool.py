"""Journal tool — daily entries with mood/energy tracking."""

from datetime import date

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, execute_many, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def journal(
        action: str,
        content: str = "",
        mood: str = "",
        energy: int = 0,
        entry_date: str = "",
        linked_contacts: str = "",
        linked_projects: str = "",
        query: str = "",
    ) -> dict:
        """Daily journal with mood and energy tracking.

        Actions:
          write  — Write or append to today's journal entry (content required)
          today  — Read today's entry
          read   — Read entry for a specific date (entry_date required, YYYY-MM-DD)
          week   — Read entries from the past 7 days
          search — Search journal entries (query required)

        Mood is free text (e.g., "great", "tired", "focused").
        Energy is 1-5 (1=drained, 5=fired up). 0 means not specified.
        linked_contacts/linked_projects are JSON arrays of IDs.

        When writing, cross-reference: detect contact names and project names
        mentioned in the content and auto-link them.
        """
        if action == "write":
            return _write(content, mood, energy, entry_date, linked_contacts, linked_projects)
        elif action == "today":
            return _read(date.today().isoformat())
        elif action == "read":
            return _read(entry_date)
        elif action == "week":
            return _week()
        elif action == "search":
            return _search(query)
        else:
            return {"error": f"Unknown action: {action}. Use: write, today, read, week, search"}


def _write(content, mood, energy, entry_date, linked_contacts, linked_projects):
    if not content:
        return {"error": "Content is required for a journal entry."}

    today = entry_date or date.today().isoformat()

    # Check if entry exists for this date
    existing = execute(
        "SELECT id, content FROM journal_entries WHERE entry_date = ?", (today,)
    )

    if existing:
        # Append to existing entry
        old_content = existing[0]["content"]
        new_content = f"{old_content}\n\n{content}"
        eid = existing[0]["id"]

        updates = ["content = ?"]
        params = [new_content]
        if mood:
            updates.append("mood = ?")
            params.append(mood)
        if energy:
            updates.append("energy = ?")
            params.append(energy)
        if linked_contacts:
            updates.append("linked_contacts = ?")
            params.append(linked_contacts)
        if linked_projects:
            updates.append("linked_projects = ?")
            params.append(linked_projects)
        updates.append("updated_at = datetime('now')")
        params.append(eid)

        execute_many([
            (f"UPDATE journal_entries SET {', '.join(updates)} WHERE id = ?", tuple(params)),
            (
                """INSERT INTO activity_log (entity_type, entity_id, action, details)
                   VALUES ('journal', ?, 'appended', ?)""",
                (eid, f"Added to {today} entry"),
            ),
        ])

        return {
            "result": {"entry_id": eid, "date": today, "appended": True},
            "_context": {
                "presentation": f"Appended to your {today} journal entry.",
                "suggestions": ["Show the full entry if they want to review it"],
            },
        }
    else:
        eid = execute_many([
            (
                """INSERT INTO journal_entries (content, mood, energy, entry_date, linked_contacts, linked_projects)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (content, mood or None, energy or None, today,
                 linked_contacts or None, linked_projects or None),
            ),
            (
                """INSERT INTO activity_log (entity_type, entity_id, action, details)
                   VALUES ('journal', last_insert_rowid(), 'created', ?)""",
                (f"Journal entry for {today}",),
            ),
        ])

        return {
            "result": {"entry_id": eid, "date": today, "mood": mood, "energy": energy},
            "_context": {
                "suggestions": [
                    "Suggest mood/energy if not provided",
                    "Ask if they want to link contacts or projects mentioned",
                ],
                "presentation": f"Journal entry saved for {today}.",
            },
        }


def _read(entry_date):
    if not entry_date:
        return {"error": "entry_date (YYYY-MM-DD) is required."}

    rows = execute("SELECT * FROM journal_entries WHERE entry_date = ?", (entry_date,))
    if not rows:
        return {
            "result": None,
            "_context": {
                "presentation": f"No journal entry for {entry_date}.",
                "suggestions": ["Offer to write one"],
            },
        }

    return {
        "result": rows_to_dicts(rows)[0],
        "_context": {
            "presentation": "Show the entry content with mood and energy if set.",
        },
    }


def _week():
    rows = execute(
        """SELECT id, entry_date, mood, energy, substr(content, 1, 200) as preview
           FROM journal_entries
           WHERE entry_date >= date('now', '-7 days')
           ORDER BY entry_date DESC"""
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "suggestions": ["Offer to show full entry for any day", "Summarize mood/energy trends"],
            "presentation": "Show as a week timeline with mood indicators.",
        },
    }


def _search(query):
    if not query:
        return {"error": "Search query is required."}

    rows = execute(
        """SELECT id, entry_date, mood, energy, substr(content, 1, 200) as preview
           FROM journal_entries WHERE content LIKE ?
           ORDER BY entry_date DESC LIMIT 10""",
        (f"%{query}%",),
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "query": query,
        "_context": {"presentation": "Show matching entries with date and preview."},
    }
