"""Dev log tool — lightweight activity logging for development sessions."""

import json

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, execute_many, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def dev_log(
        activity_type: str,
        description: str,
        project_id: int = 0,
        project_name: str = "",
        metadata: str = "",
    ) -> dict:
        """Log a development activity — commits, deploys, test runs, code reviews, etc.

        Parameters:
          activity_type — What happened: commit, deploy, test_run, code_review, debug, refactor, feature, bugfix, etc.
          description   — What was done, in plain language.
          project_id    — SoY project ID (if known).
          project_name  — Fuzzy project name (resolved to ID automatically).
          metadata      — Optional JSON string with structured data (commit hash, branch, test counts, etc.)

        Writes to activity_log with 'dev:' prefixed actions and bumps the project's updated_at.
        """
        if not activity_type or not description:
            return {"error": "Both activity_type and description are required."}

        # Resolve project
        pid = _resolve_project(project_id, project_name)

        # Validate metadata is valid JSON if provided
        meta_parsed = None
        if metadata:
            try:
                meta_parsed = json.loads(metadata) if isinstance(metadata, str) else metadata
            except json.JSONDecodeError:
                return {"error": "metadata must be valid JSON."}

        # Build details string
        details_obj = {"description": description}
        if meta_parsed:
            details_obj["metadata"] = meta_parsed
        details = json.dumps(details_obj)

        action = f"dev:{activity_type}"

        statements = [
            (
                """INSERT INTO activity_log (entity_type, entity_id, action, details)
                   VALUES ('project', ?, ?, ?)""",
                (pid, action, details),
            ),
        ]

        # Bump project updated_at so it surfaces as recently active
        if pid:
            statements.append((
                "UPDATE projects SET updated_at = datetime('now') WHERE id = ?",
                (pid,),
            ))

        execute_many(statements)

        # Fetch project info for context
        project_info = None
        if pid:
            rows = execute(
                "SELECT id, name, status FROM projects WHERE id = ?", (pid,)
            )
            if rows:
                project_info = rows_to_dicts(rows)[0]

        return {
            "result": {
                "logged": True,
                "activity_type": activity_type,
                "description": description,
                "project_id": pid,
                "metadata": meta_parsed,
            },
            "project": project_info,
            "_context": {
                "presentation": "Brief confirmation. Don't repeat the full description back.",
                "suggestions": [
                    "Continue working — no action needed from the user",
                ],
            },
        }


def _resolve_project(project_id, project_name):
    """Resolve project by ID or fuzzy name match."""
    if project_id:
        return project_id
    if project_name:
        rows = execute(
            "SELECT id FROM projects WHERE name LIKE ?",
            (f"%{project_name}%",),
        )
        if len(rows) == 1:
            return rows[0]["id"]
    return None
