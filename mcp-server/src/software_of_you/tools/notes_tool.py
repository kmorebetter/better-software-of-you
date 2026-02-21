"""Notes tool — standalone notes with auto cross-referencing and hashtag tags."""

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, execute_many, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def notes(
        action: str,
        title: str = "",
        content: str = "",
        tags: str = "",
        linked_contacts: str = "",
        linked_projects: str = "",
        note_id: int = 0,
        query: str = "",
        pinned: bool = False,
    ) -> dict:
        """Manage standalone notes with auto cross-referencing.

        Actions:
          add    — Create a note (content required; title, tags optional)
          edit   — Update a note (note_id required)
          list   — List recent notes (pinned first)
          search — Search notes by content or tags (query required)
          pin    — Toggle pin status (note_id required)

        Tags are extracted from #hashtags in content, or pass as JSON array.
        linked_contacts/linked_projects are JSON arrays of IDs.
        These are separate from entity-attached notes (the polymorphic notes table).
        """
        if action == "add":
            return _add(title, content, tags, linked_contacts, linked_projects, pinned)
        elif action == "edit":
            return _edit(note_id, title, content, tags, linked_contacts, linked_projects)
        elif action == "list":
            return _list()
        elif action == "search":
            return _search(query)
        elif action == "pin":
            return _pin(note_id)
        else:
            return {"error": f"Unknown action: {action}. Use: add, edit, list, search, pin"}


def _add(title, content, tags, linked_contacts, linked_projects, pinned):
    if not content:
        return {"error": "Content is required for a note."}

    nid = execute_many([
        (
            """INSERT INTO standalone_notes (title, content, tags, linked_contacts, linked_projects, pinned)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title or None, content, tags or None,
             linked_contacts or None, linked_projects or None, 1 if pinned else 0),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('note', last_insert_rowid(), 'created', ?)""",
            (f"Note: {title or content[:50]}",),
        ),
    ])

    return {
        "result": {"note_id": nid, "title": title, "pinned": pinned},
        "_context": {
            "suggestions": [
                "Extract #hashtags from content as tags if not provided",
                "Detect contact/project names in content and auto-link",
            ],
            "presentation": "Confirm note saved. Mention tags and links if any.",
        },
    }


def _edit(note_id, title, content, tags, linked_contacts, linked_projects):
    if not note_id:
        return {"error": "note_id is required."}

    updates = []
    params = []
    for field, value in [
        ("title", title), ("content", content), ("tags", tags),
        ("linked_contacts", linked_contacts), ("linked_projects", linked_projects),
    ]:
        if value:
            updates.append(f"{field} = ?")
            params.append(value)

    if not updates:
        return {"error": "No fields to update."}

    updates.append("updated_at = datetime('now')")
    params.append(note_id)

    execute_many([
        (f"UPDATE standalone_notes SET {', '.join(updates)} WHERE id = ?", tuple(params)),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('note', ?, 'updated', 'Note updated')""",
            (note_id,),
        ),
    ])

    return {
        "result": {"note_id": note_id, "updated": True},
        "_context": {"presentation": "Note updated."},
    }


def _list():
    rows = execute(
        """SELECT id, title, substr(content, 1, 150) as preview, tags, pinned, created_at, updated_at
           FROM standalone_notes
           ORDER BY pinned DESC, updated_at DESC LIMIT 20"""
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show notes with title, preview, tags as pills. Pin icon for pinned.",
        },
    }


def _search(query):
    if not query:
        return {"error": "Search query is required."}

    pattern = f"%{query}%"
    rows = execute(
        """SELECT id, title, substr(content, 1, 150) as preview, tags, pinned, created_at
           FROM standalone_notes
           WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
           ORDER BY pinned DESC, updated_at DESC LIMIT 10""",
        (pattern, pattern, pattern),
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "query": query,
        "_context": {"presentation": "Show matching notes with highlighted preview."},
    }


def _pin(note_id):
    if not note_id:
        return {"error": "note_id is required."}

    rows = execute("SELECT pinned FROM standalone_notes WHERE id = ?", (note_id,))
    if not rows:
        return {"error": f"No note with id {note_id}."}

    new_pinned = 0 if rows[0]["pinned"] else 1
    execute_many([
        (
            "UPDATE standalone_notes SET pinned = ?, updated_at = datetime('now') WHERE id = ?",
            (new_pinned, note_id),
        ),
    ])

    return {
        "result": {"note_id": note_id, "pinned": bool(new_pinned)},
        "_context": {"presentation": f"Note {'pinned' if new_pinned else 'unpinned'}."},
    }
