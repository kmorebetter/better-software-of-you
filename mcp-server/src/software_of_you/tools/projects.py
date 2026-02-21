"""Projects tool — manage projects, tasks, and milestones."""

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, execute_many, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def projects(
        action: str,
        name: str = "",
        description: str = "",
        client_id: int = 0,
        client_name: str = "",
        status: str = "active",
        priority: str = "medium",
        start_date: str = "",
        target_date: str = "",
        project_id: int = 0,
        title: str = "",
        task_id: int = 0,
        task_status: str = "",
        due_date: str = "",
        milestone_name: str = "",
        milestone_date: str = "",
    ) -> dict:
        """Manage projects, tasks, and milestones.

        Actions:
          add          — Create a project (name required; client_id or client_name optional)
          edit         — Update a project (project_id required)
          list         — List projects (optional status filter)
          get          — Get project details with tasks and milestones (project_id required)
          add_task     — Add a task to a project (project_id, title required)
          update_task  — Update task status (task_id, task_status required)
          add_milestone — Add a milestone (project_id, milestone_name required)

        When showing projects, always include the client contact link if one exists.
        """
        if action == "add":
            return _add(name, description, client_id, client_name, status, priority, start_date, target_date)
        elif action == "edit":
            return _edit(project_id, name, description, client_id, status, priority, target_date)
        elif action == "list":
            return _list(status)
        elif action == "get":
            return _get(project_id)
        elif action == "add_task":
            return _add_task(project_id, title, description, priority, due_date)
        elif action == "update_task":
            return _update_task(task_id, task_status)
        elif action == "add_milestone":
            return _add_milestone(project_id, milestone_name, description, milestone_date)
        else:
            return {"error": f"Unknown action: {action}. Use: add, edit, list, get, add_task, update_task, add_milestone"}


def _resolve_client(client_id, client_name):
    if client_id:
        return client_id
    if client_name:
        rows = execute("SELECT id FROM contacts WHERE name LIKE ?", (f"%{client_name}%",))
        if len(rows) == 1:
            return rows[0]["id"]
    return None


def _add(name, description, client_id, client_name, status, priority, start_date, target_date):
    if not name:
        return {"error": "Project name is required."}

    cid = _resolve_client(client_id, client_name)

    pid = execute_many([
        (
            """INSERT INTO projects (name, description, client_id, status, priority, start_date, target_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, description or None, cid, status, priority, start_date or None, target_date or None),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('project', last_insert_rowid(), 'created', ?)""",
            (f"Project: {name}",),
        ),
    ])

    client_info = None
    if cid:
        rows = execute("SELECT name, company FROM contacts WHERE id = ?", (cid,))
        if rows:
            client_info = {"id": cid, "name": rows[0]["name"], "company": rows[0]["company"]}

    return {
        "result": {"project_id": pid, "name": name, "status": status},
        "client": client_info,
        "_context": {
            "suggestions": [
                "Suggest adding tasks to break the project down",
                "Suggest setting a target date if not provided",
            ],
            "presentation": "Confirm project created. Mention client if linked.",
        },
    }


def _edit(project_id, name, description, client_id, status, priority, target_date):
    if not project_id:
        return {"error": "project_id is required."}

    updates = []
    params = []
    for field, value in [
        ("name", name), ("description", description), ("status", status),
        ("priority", priority), ("target_date", target_date),
    ]:
        if value:
            updates.append(f"{field} = ?")
            params.append(value)
    if client_id:
        updates.append("client_id = ?")
        params.append(client_id)

    if not updates:
        return {"error": "No fields to update."}

    updates.append("updated_at = datetime('now')")
    params.append(project_id)

    execute_many([
        (f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", tuple(params)),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('project', ?, 'updated', ?)""",
            (project_id, f"Updated: {', '.join(f.split(' =')[0] for f in updates[:-1])}"),
        ),
    ])

    return {
        "result": {"project_id": project_id, "updated": True},
        "_context": {"presentation": "Confirm what was changed."},
    }


def _list(status):
    if status and status not in ("all", "active"):
        rows = execute(
            """SELECT p.id, p.name, p.status, p.priority, p.target_date,
                      c.name as client_name
               FROM projects p LEFT JOIN contacts c ON p.client_id = c.id
               WHERE p.status = ? ORDER BY p.updated_at DESC""",
            (status,),
        )
    else:
        rows = execute(
            """SELECT p.id, p.name, p.status, p.priority, p.target_date,
                      c.name as client_name
               FROM projects p LEFT JOIN contacts c ON p.client_id = c.id
               WHERE p.status IN ('active', 'planning')
               ORDER BY p.priority DESC, p.updated_at DESC"""
        )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show as a table with name, client, status, priority, target date.",
        },
    }


def _get(project_id):
    if not project_id:
        return {"error": "project_id is required."}

    project = execute(
        """SELECT p.*, c.name as client_name, c.company as client_company
           FROM projects p LEFT JOIN contacts c ON p.client_id = c.id
           WHERE p.id = ?""",
        (project_id,),
    )
    if not project:
        return {"error": f"No project with id {project_id}."}

    tasks = execute(
        "SELECT * FROM tasks WHERE project_id = ? ORDER BY sort_order, due_date ASC NULLS LAST",
        (project_id,),
    )
    milestones = execute(
        "SELECT * FROM milestones WHERE project_id = ? ORDER BY target_date ASC NULLS LAST",
        (project_id,),
    )

    task_stats = {"todo": 0, "in_progress": 0, "done": 0, "blocked": 0}
    for t in tasks:
        s = t["status"]
        if s in task_stats:
            task_stats[s] += 1

    return {
        "result": rows_to_dicts(project)[0],
        "tasks": rows_to_dicts(tasks),
        "milestones": rows_to_dicts(milestones),
        "task_stats": task_stats,
        "_context": {
            "suggestions": [
                "Show task breakdown with status indicators",
                "Highlight overdue tasks and milestones",
            ],
            "presentation": "Show project overview with inline task checklist.",
        },
    }


def _add_task(project_id, title, description, priority, due_date):
    if not project_id or not title:
        return {"error": "project_id and title are required."}

    tid = execute_many([
        (
            "INSERT INTO tasks (project_id, title, description, priority, due_date) VALUES (?, ?, ?, ?, ?)",
            (project_id, title, description or None, priority, due_date or None),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('project', ?, 'task_added', ?)""",
            (project_id, title),
        ),
    ])

    return {
        "result": {"task_id": tid, "project_id": project_id, "title": title},
        "_context": {"presentation": "Confirm task added to project."},
    }


def _update_task(task_id, task_status):
    if not task_id or not task_status:
        return {"error": "task_id and task_status are required."}

    rows = execute(
        "SELECT t.*, p.name as project_name FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.id = ?",
        (task_id,),
    )
    if not rows:
        return {"error": f"No task with id {task_id}."}

    task = rows_to_dicts(rows)[0]
    completed_clause = ", completed_at = datetime('now')" if task_status == "done" else ""

    execute_many([
        (
            f"UPDATE tasks SET status = ?, updated_at = datetime('now'){completed_clause} WHERE id = ?",
            (task_status, task_id),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('project', ?, 'task_updated', ?)""",
            (task["project_id"], f"{task['title']}: {task_status}"),
        ),
    ])

    return {
        "result": {"task_id": task_id, "status": task_status, "project": task["project_name"]},
        "_context": {"presentation": f"Task '{task['title']}' → {task_status}."},
    }


def _add_milestone(project_id, milestone_name, description, milestone_date):
    if not project_id or not milestone_name:
        return {"error": "project_id and milestone_name are required."}

    mid = execute_many([
        (
            "INSERT INTO milestones (project_id, name, description, target_date) VALUES (?, ?, ?, ?)",
            (project_id, milestone_name, description or None, milestone_date or None),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('project', ?, 'milestone_added', ?)""",
            (project_id, milestone_name),
        ),
    ])

    return {
        "result": {"milestone_id": mid, "project_id": project_id, "name": milestone_name},
        "_context": {"presentation": "Confirm milestone added."},
    }
