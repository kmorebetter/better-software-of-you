"""Session debrief tool — structured end-of-session capture.

One call fans out to create multiple records in a single transaction:
activity_log, decisions, task updates, journal entry, and standalone note.
"""

import json
from datetime import date

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, execute_many, execute_write, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def session_debrief(
        accomplished: str,
        project_id: int = 0,
        project_name: str = "",
        decisions: str = "",
        blockers: str = "",
        next_steps: str = "",
        tasks_completed: str = "",
        tasks_started: str = "",
        mood: str = "",
        energy: int = 0,
        session_notes: str = "",
    ) -> dict:
        """Capture an end-of-session debrief. One call creates multiple records.

        Parameters:
          accomplished    — What was done this session (required).
          project_id      — SoY project ID (if known).
          project_name    — Fuzzy project name (resolved automatically).
          decisions       — Decisions made: JSON array of objects [{title, decision, rationale}] or plain text.
          blockers        — What's blocked or stuck.
          next_steps      — What to do next session.
          tasks_completed — JSON array of task IDs marked done.
          tasks_started   — JSON array of task IDs marked in_progress.
          mood            — How the session felt (free text).
          energy          — Energy level 1-5 (0 = not specified).
          session_notes   — Additional freeform notes.

        Creates:
          - activity_log entry with session summary
          - decisions records (if decisions provided)
          - task status updates (if task IDs provided)
          - journal entry (appends to today's if one exists)
          - standalone note with full debrief content
        """
        if not accomplished:
            return {"error": "accomplished is required — what did you get done?"}

        pid = _resolve_project(project_id, project_name)
        project_info = None
        if pid:
            rows = execute("SELECT id, name FROM projects WHERE id = ?", (pid,))
            if rows:
                project_info = rows_to_dicts(rows)[0]

        created = {
            "activity_log": False,
            "decisions": [],
            "tasks_completed": [],
            "tasks_started": [],
            "journal": False,
            "note": False,
        }

        # --- 1. Activity log entry ---
        summary_parts = [f"Accomplished: {accomplished}"]
        if blockers:
            summary_parts.append(f"Blockers: {blockers}")
        if next_steps:
            summary_parts.append(f"Next: {next_steps}")

        details = json.dumps({
            "accomplished": accomplished,
            "blockers": blockers or None,
            "next_steps": next_steps or None,
            "mood": mood or None,
            "energy": energy or None,
        })

        execute_write(
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('project', ?, 'dev:session_debrief', ?)""",
            (pid, details),
        )
        created["activity_log"] = True

        # --- 2. Decisions ---
        if decisions:
            decision_list = _parse_decisions(decisions)
            for d in decision_list:
                title = d.get("title", d.get("decision", "")[:80])
                decision_text = d.get("decision", d.get("title", ""))
                rationale = d.get("rationale", "")

                did = execute_many([
                    (
                        """INSERT INTO decisions (title, decision, rationale, status, project_id)
                           VALUES (?, ?, ?, 'decided', ?)""",
                        (title, decision_text, rationale or None, pid),
                    ),
                    (
                        """INSERT INTO activity_log (entity_type, entity_id, action, details)
                           VALUES ('decision', last_insert_rowid(), 'logged', ?)""",
                        (f"Session debrief: {title}",),
                    ),
                ])
                created["decisions"].append({"id": did, "title": title})

        # --- 3. Task updates ---
        if tasks_completed:
            ids = _parse_id_list(tasks_completed)
            for tid in ids:
                rows = execute(
                    "SELECT id, title, project_id FROM tasks WHERE id = ?", (tid,)
                )
                if rows:
                    execute_many([
                        (
                            "UPDATE tasks SET status = 'done', completed_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
                            (tid,),
                        ),
                        (
                            """INSERT INTO activity_log (entity_type, entity_id, action, details)
                               VALUES ('project', ?, 'task_updated', ?)""",
                            (rows[0]["project_id"], f"{rows[0]['title']}: done"),
                        ),
                    ])
                    created["tasks_completed"].append({"id": tid, "title": rows[0]["title"]})

        if tasks_started:
            ids = _parse_id_list(tasks_started)
            for tid in ids:
                rows = execute(
                    "SELECT id, title, project_id FROM tasks WHERE id = ?", (tid,)
                )
                if rows:
                    execute_many([
                        (
                            "UPDATE tasks SET status = 'in_progress', updated_at = datetime('now') WHERE id = ?",
                            (tid,),
                        ),
                        (
                            """INSERT INTO activity_log (entity_type, entity_id, action, details)
                               VALUES ('project', ?, 'task_updated', ?)""",
                            (rows[0]["project_id"], f"{rows[0]['title']}: in_progress"),
                        ),
                    ])
                    created["tasks_started"].append({"id": tid, "title": rows[0]["title"]})

        # --- 4. Journal entry (append to today's if exists) ---
        project_label = project_info["name"] if project_info else "Dev session"
        journal_content = f"## {project_label} — Session Debrief\n\n"
        journal_content += f"**Accomplished:** {accomplished}\n"
        if blockers:
            journal_content += f"**Blockers:** {blockers}\n"
        if next_steps:
            journal_content += f"**Next steps:** {next_steps}\n"
        if created["decisions"]:
            journal_content += f"**Decisions:** {', '.join(d['title'] for d in created['decisions'])}\n"

        today = date.today().isoformat()
        existing = execute(
            "SELECT id, content FROM journal_entries WHERE entry_date = ?", (today,)
        )

        if existing:
            new_content = f"{existing[0]['content']}\n\n{journal_content}"
            eid = existing[0]["id"]
            params = [new_content]
            updates = ["content = ?"]
            if mood:
                updates.append("mood = ?")
                params.append(mood)
            if energy:
                updates.append("energy = ?")
                params.append(energy)
            if pid:
                updates.append("linked_projects = ?")
                params.append(json.dumps([pid]))
            updates.append("updated_at = datetime('now')")
            params.append(eid)
            execute_write(
                f"UPDATE journal_entries SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
        else:
            eid = execute_write(
                """INSERT INTO journal_entries (content, mood, energy, entry_date, linked_projects)
                   VALUES (?, ?, ?, ?, ?)""",
                (journal_content, mood or None, energy or None, today,
                 json.dumps([pid]) if pid else None),
            )

        created["journal"] = {"entry_id": eid, "date": today, "appended": bool(existing)}

        # --- 5. Standalone note with full debrief ---
        note_parts = [f"# Session Debrief: {project_label}", ""]
        note_parts.append(f"**Accomplished:** {accomplished}")
        if blockers:
            note_parts.append(f"**Blockers:** {blockers}")
        if next_steps:
            note_parts.append(f"**Next steps:** {next_steps}")
        if session_notes:
            note_parts.append(f"\n**Notes:** {session_notes}")
        if created["decisions"]:
            note_parts.append("\n**Decisions:**")
            for d in created["decisions"]:
                note_parts.append(f"- {d['title']}")
        if created["tasks_completed"]:
            note_parts.append("\n**Completed:**")
            for t in created["tasks_completed"]:
                note_parts.append(f"- [x] {t['title']}")
        if created["tasks_started"]:
            note_parts.append("\n**Started:**")
            for t in created["tasks_started"]:
                note_parts.append(f"- [ ] {t['title']}")

        note_content = "\n".join(note_parts)
        note_title = f"Session Debrief: {project_label} ({today})"

        nid = execute_many([
            (
                """INSERT INTO standalone_notes (title, content, tags, linked_projects, pinned)
                   VALUES (?, ?, ?, ?, 0)""",
                (note_title, note_content, '["session-debrief"]',
                 json.dumps([pid]) if pid else None),
            ),
            (
                """INSERT INTO activity_log (entity_type, entity_id, action, details)
                   VALUES ('note', last_insert_rowid(), 'created', ?)""",
                (f"Session debrief note: {project_label}",),
            ),
        ])
        created["note"] = {"note_id": nid, "title": note_title}

        # Bump project updated_at
        if pid:
            execute_write(
                "UPDATE projects SET updated_at = datetime('now') WHERE id = ?",
                (pid,),
            )

        return {
            "result": {
                "debrief_saved": True,
                "project": project_info,
                "created": created,
            },
            "_context": {
                "presentation": "Summarize what was captured: X decisions logged, Y tasks updated, journal appended, note saved. Keep it brief.",
                "suggestions": [
                    "Session is wrapped up — user can close the terminal",
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


def _parse_decisions(decisions):
    """Parse decisions from JSON array or plain text."""
    if not decisions:
        return []

    # Try JSON first
    try:
        parsed = json.loads(decisions)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except (json.JSONDecodeError, TypeError):
        pass

    # Fall back to plain text — each line is a decision
    lines = [ln.strip().lstrip("- ") for ln in decisions.strip().split("\n") if ln.strip()]
    return [{"title": ln, "decision": ln} for ln in lines]


def _parse_id_list(value):
    """Parse a JSON array of IDs or comma-separated string."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [int(x) for x in parsed]
    except (json.JSONDecodeError, TypeError):
        pass

    # Comma-separated fallback
    return [int(x.strip()) for x in value.split(",") if x.strip().isdigit()]
