"""Cross-module search tool."""

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, rows_to_dicts, get_installed_modules


def register(server: FastMCP) -> None:
    @server.tool()
    def search(query: str, module: str = "") -> dict:
        """Search across all modules for a keyword or phrase.

        Searches contacts, projects, interactions, emails, transcripts,
        decisions, journal entries, and notes. Returns results grouped by type.

        Args:
            query: The search term
            module: Optional — limit search to a specific module (contacts, projects, etc.)
        """
        if not query:
            return {"error": "A search query is required."}

        pattern = f"%{query}%"
        modules = get_installed_modules()
        results = {}

        # Always search contacts
        if not module or module == "contacts":
            rows = execute(
                """SELECT id, name, company, role, email, 'contact' as result_type
                   FROM contacts WHERE name LIKE ? OR company LIKE ? OR email LIKE ? OR notes LIKE ?
                   LIMIT 10""",
                (pattern, pattern, pattern, pattern),
            )
            if rows:
                results["contacts"] = rows_to_dicts(rows)

        # Projects
        if (not module or module == "projects") and "project-tracker" in modules:
            rows = execute(
                """SELECT p.id, p.name, p.status, c.name as client_name, 'project' as result_type
                   FROM projects p LEFT JOIN contacts c ON p.client_id = c.id
                   WHERE p.name LIKE ? OR p.description LIKE ?
                   LIMIT 10""",
                (pattern, pattern),
            )
            if rows:
                results["projects"] = rows_to_dicts(rows)

            rows = execute(
                """SELECT t.id, t.title, t.status, p.name as project_name, 'task' as result_type
                   FROM tasks t JOIN projects p ON p.id = t.project_id
                   WHERE t.title LIKE ? OR t.description LIKE ?
                   LIMIT 10""",
                (pattern, pattern),
            )
            if rows:
                results["tasks"] = rows_to_dicts(rows)

        # Interactions
        if (not module or module == "interactions") and "crm" in modules:
            rows = execute(
                """SELECT ci.id, ci.subject, ci.type, c.name as contact_name, ci.occurred_at, 'interaction' as result_type
                   FROM contact_interactions ci JOIN contacts c ON c.id = ci.contact_id
                   WHERE ci.subject LIKE ? OR ci.summary LIKE ?
                   ORDER BY ci.occurred_at DESC LIMIT 10""",
                (pattern, pattern),
            )
            if rows:
                results["interactions"] = rows_to_dicts(rows)

        # Emails
        if (not module or module == "emails") and "gmail" in modules:
            rows = execute(
                """SELECT id, subject, from_name, snippet, received_at, 'email' as result_type
                   FROM emails WHERE subject LIKE ? OR snippet LIKE ? OR from_name LIKE ?
                   ORDER BY received_at DESC LIMIT 10""",
                (pattern, pattern, pattern),
            )
            if rows:
                results["emails"] = rows_to_dicts(rows)

        # Transcripts
        if (not module or module == "transcripts") and "conversation-intelligence" in modules:
            rows = execute(
                """SELECT id, title, summary, occurred_at, 'transcript' as result_type
                   FROM transcripts WHERE title LIKE ? OR raw_text LIKE ? OR summary LIKE ?
                   ORDER BY occurred_at DESC LIMIT 10""",
                (pattern, pattern, pattern),
            )
            if rows:
                results["transcripts"] = rows_to_dicts(rows)

        # Decisions
        if (not module or module == "decisions") and "decision-log" in modules:
            rows = execute(
                """SELECT id, title, status, decided_at, 'decision' as result_type
                   FROM decisions WHERE title LIKE ? OR context LIKE ? OR decision LIKE ?
                   ORDER BY decided_at DESC LIMIT 10""",
                (pattern, pattern, pattern),
            )
            if rows:
                results["decisions"] = rows_to_dicts(rows)

        # Journal
        if (not module or module == "journal") and "journal" in modules:
            rows = execute(
                """SELECT id, entry_date, mood, substr(content, 1, 150) as preview, 'journal' as result_type
                   FROM journal_entries WHERE content LIKE ?
                   ORDER BY entry_date DESC LIMIT 10""",
                (pattern,),
            )
            if rows:
                results["journal"] = rows_to_dicts(rows)

        # Notes
        if (not module or module == "notes") and "notes" in modules:
            rows = execute(
                """SELECT id, title, substr(content, 1, 150) as preview, tags, 'note' as result_type
                   FROM standalone_notes WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                   ORDER BY updated_at DESC LIMIT 10""",
                (pattern, pattern, pattern),
            )
            if rows:
                results["notes"] = rows_to_dicts(rows)

        total = sum(len(v) for v in results.values())
        return {
            "result": results,
            "total_matches": total,
            "query": query,
            "_context": {
                "presentation": "Group results by type. Show the most relevant matches first. Link to entity details where possible.",
            },
        }
