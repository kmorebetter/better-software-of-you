"""Contacts tool — add, edit, list, find, get contacts.

This is the foundation of Software of You. Every other module
cross-references contacts.
"""

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, execute_many, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def contacts(
        action: str,
        name: str = "",
        email: str = "",
        phone: str = "",
        company: str = "",
        role: str = "",
        contact_type: str = "individual",
        status: str = "active",
        notes: str = "",
        contact_id: int = 0,
        query: str = "",
    ) -> dict:
        """Manage contacts in the personal CRM.

        Actions:
          add    — Create a new contact (name required, everything else optional)
          edit   — Update an existing contact (contact_id required, only pass fields to change)
          list   — List contacts (optional status filter, default 'active')
          find   — Search contacts by name, email, or company (query required)
          get    — Get full details for one contact (contact_id required)

        Always cross-reference: when adding/editing, check if the company matches
        existing contacts. When getting, mention linked projects, emails, events.
        """
        if action == "add":
            return _add(name, email, phone, company, role, contact_type, status, notes)
        elif action == "edit":
            return _edit(contact_id, name, email, phone, company, role, status, notes)
        elif action == "list":
            return _list(status)
        elif action == "find":
            return _find(query or name)
        elif action == "get":
            return _get(contact_id)
        else:
            return {"error": f"Unknown action: {action}. Use: add, edit, list, find, get"}


def _add(name, email, phone, company, role, contact_type, status, notes):
    if not name:
        return {"error": "Name is required to add a contact."}

    # Check for duplicates
    existing = execute(
        "SELECT id, name, email FROM contacts WHERE name = ? OR (email = ? AND email != '')",
        (name, email),
    )
    if existing:
        dups = rows_to_dicts(existing)
        return {
            "error": "Possible duplicate found.",
            "existing": dups,
            "_context": {
                "presentation": "Ask if they want to update the existing contact or create a new one.",
            },
        }

    contact_id = execute_many([
        (
            """INSERT INTO contacts (name, email, phone, company, role, type, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, email, phone, company, role, contact_type, status, notes or None),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('contact', last_insert_rowid(), 'created',
                       json_object('name', ?, 'company', ?, 'email', ?))""",
            (name, company, email),
        ),
    ])

    # Check for others at same company
    colleagues = []
    if company:
        rows = execute(
            "SELECT id, name, role FROM contacts WHERE company = ? AND name != ?",
            (company, name),
        )
        colleagues = rows_to_dicts(rows)

    return {
        "result": {"contact_id": contact_id, "name": name, "company": company},
        "colleagues_at_company": colleagues,
        "_context": {
            "suggestions": [
                "Ask if they want to add email or phone" if not email else None,
                "Suggest setting a follow-up" if contact_type == "individual" else None,
                f"Mention {len(colleagues)} other contacts at {company}" if colleagues else None,
            ],
            "presentation": "Confirm contact was added. Mention what was stored.",
        },
    }


def _edit(contact_id, name, email, phone, company, role, status, notes):
    if not contact_id:
        return {"error": "contact_id is required to edit a contact."}

    existing = execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    if not existing:
        return {"error": f"No contact with id {contact_id}."}

    # Build SET clause from non-empty fields
    updates = []
    params = []
    for field, value in [
        ("name", name), ("email", email), ("phone", phone),
        ("company", company), ("role", role), ("status", status), ("notes", notes),
    ]:
        if value:
            updates.append(f"{field} = ?")
            params.append(value)

    if not updates:
        return {"error": "No fields to update. Pass at least one field to change."}

    updates.append("updated_at = datetime('now')")
    params.append(contact_id)

    execute_many([
        (f"UPDATE contacts SET {', '.join(updates)} WHERE id = ?", tuple(params)),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('contact', ?, 'updated', ?)""",
            (contact_id, f"Updated: {', '.join(f.split(' =')[0] for f in updates[:-1])}"),
        ),
    ])

    updated = execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    return {
        "result": rows_to_dicts(updated)[0],
        "_context": {
            "suggestions": ["Show the updated contact summary"],
            "presentation": "Confirm what was changed.",
        },
    }


def _list(status):
    if status and status != "all":
        rows = execute(
            "SELECT id, name, company, role, email, status, updated_at FROM contacts WHERE status = ? ORDER BY updated_at DESC",
            (status,),
        )
    else:
        rows = execute(
            "SELECT id, name, company, role, email, status, updated_at FROM contacts ORDER BY updated_at DESC"
        )
    contacts = rows_to_dicts(rows)
    return {
        "result": contacts,
        "count": len(contacts),
        "_context": {
            "suggestions": [
                "Offer to show details for a specific contact",
                "Suggest adding a new contact if list is short",
            ],
            "presentation": "Present as a clean list with name, company, role. Use a table for 3+ contacts.",
        },
    }


def _find(query):
    if not query:
        return {"error": "Query is required. Provide a name, email, or company to search."}

    pattern = f"%{query}%"
    rows = execute(
        """SELECT id, name, company, role, email, status FROM contacts
           WHERE name LIKE ? OR email LIKE ? OR company LIKE ?
           ORDER BY CASE WHEN name LIKE ? THEN 0 ELSE 1 END, name""",
        (pattern, pattern, pattern, pattern),
    )
    contacts = rows_to_dicts(rows)
    return {
        "result": contacts,
        "count": len(contacts),
        "_context": {
            "presentation": "Show matches. If exactly one, offer to show full details.",
        },
    }


def _get(contact_id):
    if not contact_id:
        return {"error": "contact_id is required."}

    rows = execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    if not rows:
        return {"error": f"No contact with id {contact_id}."}

    contact = rows_to_dicts(rows)[0]

    # Cross-references
    cross_refs = {}

    # Projects
    projects = execute(
        "SELECT id, name, status FROM projects WHERE client_id = ?", (contact_id,)
    )
    if projects:
        cross_refs["projects"] = rows_to_dicts(projects)

    # Recent interactions
    interactions = execute(
        """SELECT type, direction, subject, occurred_at FROM contact_interactions
           WHERE contact_id = ? ORDER BY occurred_at DESC LIMIT 5""",
        (contact_id,),
    )
    if interactions:
        cross_refs["recent_interactions"] = rows_to_dicts(interactions)

    # Follow-ups
    follow_ups = execute(
        "SELECT reason, due_date, status FROM follow_ups WHERE contact_id = ? AND status = 'pending'",
        (contact_id,),
    )
    if follow_ups:
        cross_refs["pending_follow_ups"] = rows_to_dicts(follow_ups)

    # Tags
    tags = execute(
        """SELECT t.name, t.color FROM tags t
           JOIN entity_tags et ON et.tag_id = t.id
           WHERE et.entity_type = 'contact' AND et.entity_id = ?""",
        (contact_id,),
    )
    if tags:
        cross_refs["tags"] = rows_to_dicts(tags)

    # Notes
    notes = execute(
        "SELECT content, created_at FROM notes WHERE entity_type = 'contact' AND entity_id = ? ORDER BY created_at DESC LIMIT 5",
        (contact_id,),
    )
    if notes:
        cross_refs["notes"] = rows_to_dicts(notes)

    return {
        "result": contact,
        "cross_references": cross_refs,
        "_context": {
            "suggestions": [
                "Offer to generate an entity page for a rich view",
                "Suggest logging an interaction if recent contact",
                "Mention pending follow-ups if any exist",
            ],
            "presentation": "Present the full contact profile with cross-references. Use narrative style.",
        },
    }
