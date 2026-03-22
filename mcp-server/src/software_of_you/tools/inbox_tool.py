"""Quick capture inbox — write first, route later."""

import json
import re

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, execute_many, rows_to_dicts

ALLOWED_DESTINATIONS = {
    "contact",
    "project",
    "decision",
    "journal",
    "note",
    "interaction",
    "commitment",
}


def register(server: FastMCP) -> None:
    @server.tool()
    def inbox(
        action: str,
        content: str = "",
        inbox_id: int = 0,
        destination: str = "",
        entity_id: int = 0,
        status: str = "unrouted",
    ) -> dict:
        """Quick capture inbox — write it down, route it later.

        Actions:
          capture  — Capture a thought (content required). Extracts #hashtags and matches names against contacts.
          list     — List inbox items. status: 'unrouted' (default), 'routed', 'dismissed', 'all'. Newest first, limit 30.
          route    — Route an item to a module (inbox_id, destination, entity_id required).
                     destination: 'contact', 'project', 'decision', 'journal', 'note', 'interaction', 'commitment'.
          dismiss  — Mark an item as dismissed (inbox_id required).
          count    — Count of unrouted items (for proactive surfacing).
        """
        if action == "capture":
            return _capture(content)
        elif action == "list":
            return _list(status)
        elif action == "route":
            return _route(inbox_id, destination, entity_id)
        elif action == "dismiss":
            return _dismiss(inbox_id)
        elif action == "count":
            return _count()
        else:
            return {"error": f"Unknown action: {action}. Use: capture, list, route, dismiss, count"}


def _capture(content: str) -> dict:
    if not content or not content.strip():
        return {"error": "Content is required to capture an inbox item."}

    content = content.strip()
    truncated = False
    if len(content) > 10_000:
        content = content[:10_000]
        truncated = True

    # Extract #hashtags
    tags = re.findall(r"#(\w+)", content)

    # Match contact names: extract words 3+ chars, query for first-name match
    words = set(
        w.lower()
        for w in re.findall(r"[A-Za-z]+", content)
        if len(w) >= 3
    )

    matched_contacts = []
    if words:
        placeholders = ",".join("?" for _ in words)
        rows = execute(
            f"""SELECT id, name FROM contacts WHERE status = 'active'
                AND LENGTH(SUBSTR(name, 1, INSTR(name || ' ', ' ') - 1)) >= 3
                AND LOWER(SUBSTR(name, 1, INSTR(name || ' ', ' ') - 1)) IN ({placeholders})""",
            tuple(words),
        )
        matched_contacts = rows_to_dicts(rows)

    tags_json = json.dumps(tags)
    contacts_json = json.dumps(matched_contacts)

    nid = execute_many([
        (
            """INSERT INTO inbox (content, tags, matched_contacts)
               VALUES (?, ?, ?)""",
            (content, tags_json, contacts_json),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('inbox', last_insert_rowid(), 'captured', ?)""",
            (f"Inbox: {content[:80]}",),
        ),
    ])

    result = {
        "id": nid,
        "content": content,
        "tags": tags,
        "matched_contacts": matched_contacts,
        "status": "captured",
    }
    if truncated:
        result["truncated"] = True

    return {
        "result": result,
        "_context": {
            "suggestions": [
                "If contact names were matched, mention them",
                "If tags were extracted, show them as pills",
                "Suggest routing later with: inbox route",
            ],
            "presentation": "Confirm captured. Show tags and matched contacts if any.",
        },
    }


def _list(status: str) -> dict:
    if status == "unrouted":
        where = "WHERE routed_to IS NULL"
    elif status == "routed":
        where = "WHERE routed_to IS NOT NULL AND routed_to != 'dismissed'"
    elif status == "dismissed":
        where = "WHERE routed_to = 'dismissed'"
    elif status == "all":
        where = ""
    else:
        return {"error": f"Invalid status: {status}. Use: unrouted, routed, dismissed, all"}

    rows = execute(
        f"""SELECT id, content, tags, matched_contacts, routed_to,
                   routed_entity_id, routed_at, created_at, updated_at
            FROM inbox
            {where}
            ORDER BY created_at DESC LIMIT 30"""
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "filter": status,
        "_context": {
            "presentation": "Show items with content preview, tags, age. Group by status if mixed.",
        },
    }


def _route(inbox_id: int, destination: str, entity_id: int) -> dict:
    if not inbox_id:
        return {"error": "inbox_id is required."}
    if destination not in ALLOWED_DESTINATIONS:
        return {
            "error": f"Invalid destination: {destination}. "
            f"Allowed: {', '.join(sorted(ALLOWED_DESTINATIONS))}"
        }
    if not entity_id:
        return {"error": "entity_id is required."}

    rows = execute("SELECT id, routed_to FROM inbox WHERE id = ?", (inbox_id,))
    if not rows:
        return {"error": f"No inbox item with id {inbox_id}."}
    if rows[0]["routed_to"] is not None:
        return {"error": f"Item {inbox_id} is already routed to '{rows[0]['routed_to']}'."}

    execute_many([
        (
            """UPDATE inbox
               SET routed_to = ?, routed_entity_id = ?, routed_at = datetime('now'),
                   updated_at = datetime('now')
               WHERE id = ?""",
            (destination, entity_id, inbox_id),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('inbox', ?, 'routed', ?)""",
            (inbox_id, f"Routed to {destination} #{entity_id}"),
        ),
    ])

    return {
        "result": {
            "inbox_id": inbox_id,
            "routed_to": destination,
            "entity_id": entity_id,
            "status": "routed",
        },
        "_context": {
            "presentation": f"Confirm routed to {destination}.",
        },
    }


def _dismiss(inbox_id: int) -> dict:
    if not inbox_id:
        return {"error": "inbox_id is required."}

    rows = execute("SELECT id, routed_to FROM inbox WHERE id = ?", (inbox_id,))
    if not rows:
        return {"error": f"No inbox item with id {inbox_id}."}
    if rows[0]["routed_to"] is not None:
        return {"error": f"Item {inbox_id} is already routed/dismissed ('{rows[0]['routed_to']}')."}

    execute_many([
        (
            """UPDATE inbox SET routed_to = 'dismissed', routed_at = datetime('now'),
                   updated_at = datetime('now')
               WHERE id = ?""",
            (inbox_id,),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('inbox', ?, 'dismissed', 'Inbox item dismissed')""",
            (inbox_id,),
        ),
    ])

    return {
        "result": {"inbox_id": inbox_id, "status": "dismissed"},
        "_context": {"presentation": "Confirm dismissed."},
    }


def _count() -> dict:
    rows = execute("SELECT COUNT(*) as count FROM inbox WHERE routed_to IS NULL")
    count = rows[0]["count"] if rows else 0

    return {
        "result": {"unrouted": count},
        "_context": {
            "presentation": "Mention count naturally, e.g. 'You have 3 unrouted inbox items.'",
            "proactive": count > 0,
        },
    }
