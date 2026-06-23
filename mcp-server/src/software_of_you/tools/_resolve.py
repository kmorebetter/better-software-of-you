"""Shared contact resolution helper.

A single fuzzy-name resolver used by interactions, projects, and slack sync.
Previously each call site duplicated a ``SELECT ... WHERE name LIKE ?`` and
silently returned ``None`` on multiple matches — quietly dropping or
mis-attributing the link. This helper surfaces the ambiguity so callers that
can report it (e.g. the interactions tool) no longer lose information.
"""

from software_of_you.db import execute, rows_to_dicts


def resolve_contact_by_name(name: str):
    """Resolve a contact by fuzzy name match.

    Returns:
      - ``{"id": int, "name": str}`` on exactly one match
      - ``{"ambiguous": [{"id", "name"}, ...]}`` on multiple matches
      - ``None`` when the name is empty or nothing matches
    """
    if not name:
        return None

    rows = execute(
        "SELECT id, name FROM contacts WHERE name LIKE ?",
        (f"%{name}%",),
    )
    if len(rows) == 1:
        return {"id": rows[0]["id"], "name": rows[0]["name"]}
    if len(rows) > 1:
        return {"ambiguous": rows_to_dicts(rows)}
    return None
