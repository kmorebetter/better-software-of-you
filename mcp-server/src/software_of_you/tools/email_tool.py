"""Email tool — search and browse synced Gmail data."""

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def email(
        action: str,
        query: str = "",
        contact_id: int = 0,
        contact_name: str = "",
        thread_id: str = "",
        limit: int = 20,
    ) -> dict:
        """Search and browse synced emails from Gmail.

        Actions:
          inbox    — Recent inbox threads (grouped by thread)
          unread   — Unread emails only
          search   — Search emails by subject, snippet, or sender (query required)
          from     — Emails from a specific contact (contact_id or contact_name required)
          thread   — Get all emails in a thread (thread_id required)

        Auto-syncs Gmail if data is stale (>15 min). Emails are read-only —
        this tool doesn't send emails, it reads what's been synced.
        """
        _auto_sync()

        if action == "inbox":
            return _inbox(limit)
        elif action == "unread":
            return _unread(limit)
        elif action == "search":
            return _search(query, limit)
        elif action == "from":
            return _from_contact(contact_id, contact_name, limit)
        elif action == "thread":
            return _thread(thread_id)
        else:
            return {"error": f"Unknown action: {action}. Use: inbox, unread, search, from, thread"}


def _auto_sync():
    try:
        rows = execute("SELECT value FROM soy_meta WHERE key = 'gmail_last_synced'")
        if rows:
            from datetime import datetime
            last = datetime.fromisoformat(rows[0]["value"])
            if (datetime.now() - last).total_seconds() < 900:
                return
        from software_of_you.google_sync import sync_gmail
        sync_gmail()
    except Exception:
        pass


def _inbox(limit):
    # Get latest email per thread
    rows = execute(
        """SELECT e.thread_id, e.subject, e.snippet, e.from_name, e.from_address,
                  e.direction, e.received_at, e.is_read, e.is_starred,
                  c.name as contact_name, c.id as contact_id,
                  COUNT(*) OVER (PARTITION BY e.thread_id) as thread_count
           FROM emails e
           LEFT JOIN contacts c ON e.contact_id = c.id
           WHERE e.id IN (SELECT MAX(id) FROM emails GROUP BY thread_id)
           ORDER BY e.received_at DESC LIMIT ?""",
        (limit,),
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "suggestions": ["Offer to show a specific thread", "Highlight threads needing response"],
            "presentation": "Show as thread list with contact name, subject, snippet, time. Mark unread in bold.",
        },
    }


def _unread(limit):
    rows = execute(
        """SELECT e.*, c.name as contact_name
           FROM emails e LEFT JOIN contacts c ON e.contact_id = c.id
           WHERE e.is_read = 0 ORDER BY e.received_at DESC LIMIT ?""",
        (limit,),
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show unread emails with sender, subject, time.",
        },
    }


def _search(query, limit):
    if not query:
        return {"error": "Search query is required."}

    pattern = f"%{query}%"
    rows = execute(
        """SELECT e.*, c.name as contact_name
           FROM emails e LEFT JOIN contacts c ON e.contact_id = c.id
           WHERE e.subject LIKE ? OR e.snippet LIKE ? OR e.from_name LIKE ? OR e.from_address LIKE ?
           ORDER BY e.received_at DESC LIMIT ?""",
        (pattern, pattern, pattern, pattern, limit),
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "query": query,
        "_context": {"presentation": "Show matching emails with highlighted terms."},
    }


def _from_contact(contact_id, contact_name, limit):
    if contact_name and not contact_id:
        rows = execute("SELECT id FROM contacts WHERE name LIKE ?", (f"%{contact_name}%",))
        if len(rows) == 1:
            contact_id = rows[0]["id"]
        elif len(rows) > 1:
            return {"error": "Multiple contacts match.", "matches": rows_to_dicts(rows)}
        else:
            return {"error": "Contact not found."}

    if not contact_id:
        return {"error": "contact_id or contact_name required."}

    rows = execute(
        """SELECT e.*, c.name as contact_name
           FROM emails e LEFT JOIN contacts c ON e.contact_id = c.id
           WHERE e.contact_id = ? ORDER BY e.received_at DESC LIMIT ?""",
        (contact_id, limit),
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {"presentation": "Show email history with this contact chronologically."},
    }


def _thread(thread_id):
    if not thread_id:
        return {"error": "thread_id is required."}

    rows = execute(
        """SELECT e.*, c.name as contact_name
           FROM emails e LEFT JOIN contacts c ON e.contact_id = c.id
           WHERE e.thread_id = ? ORDER BY e.received_at ASC""",
        (thread_id,),
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show full thread as a conversation: each message with sender, direction, time, and snippet.",
        },
    }
