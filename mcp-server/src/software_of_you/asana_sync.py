"""Asana sync — mirrors workspaces, projects, users, and tasks into the local DB.

Schema lives in data/migrations/024_asana_module.sql. Token is read via
``software_of_you.asana_auth``.

Strategy:
  - workspaces       → GET /workspaces
  - users/workspace  → GET /users?workspace=<gid>; auto-link to contacts by email
  - projects/wksp    → GET /projects?workspace=<gid>&archived=false
  - tasks/project    → GET /tasks?project=<gid>&modified_since=<iso>
                       (first sync: 90d ago; subsequent: from last sync)

Pagination: offset cursor in response_metadata. Rate limits: 429 → Retry-After.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from software_of_you.db import execute, execute_many, execute_write
from software_of_you import asana_auth

ASANA_API = "https://app.asana.com/api/1.0"
DEFAULT_INITIAL_LOOKBACK_DAYS = 90
TASK_OPT_FIELDS = ",".join([
    "name", "notes", "completed", "completed_at",
    "due_on", "due_at", "start_on",
    "assignee.gid", "assignee.name", "assignee.email",
    "created_by.gid", "created_by.name",
    "parent.gid", "num_subtasks", "permalink_url",
    "custom_fields", "tags.gid", "tags.name",
    "modified_at", "created_at",
    "memberships.project.gid", "workspace.gid",
])
USER_OPT_FIELDS = "name,email,photo.image_60x60"
PROJECT_OPT_FIELDS = ",".join([
    "name", "notes", "archived", "color",
    "owner.gid", "due_on", "modified_at", "created_at",
])


def _api_get(path: str, token: str, params: dict | None = None, retries: int = 1) -> dict:
    """Authenticated GET. Backs off once on 429."""
    url = f"{ASANA_API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429 and retries > 0:
            wait = int(e.headers.get("Retry-After", "10"))
            time.sleep(wait)
            return _api_get(path, token, params, retries - 1)
        raise


def _paginate(path: str, token: str, params: dict) -> list[dict]:
    """Walk Asana offset pagination until exhausted."""
    items: list[dict] = []
    offset = ""
    while True:
        page_params = dict(params)
        page_params["limit"] = page_params.get("limit", 100)
        if offset:
            page_params["offset"] = offset
        data = _api_get(path, token, page_params)
        items.extend(data.get("data", []))
        offset = data.get("next_page", {}).get("offset", "") if data.get("next_page") else ""
        if not offset:
            return items


# ── Workspaces ───────────────────────────────────────────────────────────


def sync_workspaces(token: str) -> dict:
    workspaces = _paginate("/workspaces", token, {"opt_fields": "name,is_organization"})
    statements = []
    for w in workspaces:
        statements.append((
            """INSERT INTO asana_workspaces (gid, name, is_organization, synced_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(gid) DO UPDATE SET
                 name=excluded.name,
                 is_organization=excluded.is_organization,
                 synced_at=datetime('now')""",
            (w["gid"], w.get("name", "(unnamed)"), 1 if w.get("is_organization") else 0),
        ))
    if statements:
        execute_many(statements)
    return {"workspaces": len(workspaces), "list": [{"gid": w["gid"], "name": w.get("name")} for w in workspaces]}


# ── Users ─────────────────────────────────────────────────────────────────


def sync_users(token: str, workspace_gid: str, self_gid: str | None) -> dict:
    users = _paginate(
        "/users",
        token,
        {"workspace": workspace_gid, "opt_fields": USER_OPT_FIELDS},
    )
    statements = []
    linked = 0
    for u in users:
        gid = u.get("gid")
        if not gid:
            continue
        email = u.get("email")
        contact_id = None
        if email:
            rows = execute("SELECT id FROM contacts WHERE email = ?", (email,))
            if rows:
                contact_id = rows[0]["id"]
                linked += 1

        photo = (u.get("photo") or {}).get("image_60x60") if u.get("photo") else None

        statements.append((
            """INSERT INTO asana_users
               (gid, workspace_gid, name, email, contact_id, is_self, photo_url, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(gid) DO UPDATE SET
                 workspace_gid=excluded.workspace_gid,
                 name=excluded.name, email=excluded.email,
                 contact_id=COALESCE(excluded.contact_id, asana_users.contact_id),
                 is_self=excluded.is_self,
                 photo_url=excluded.photo_url,
                 synced_at=datetime('now')""",
            (gid, workspace_gid, u.get("name"), email, contact_id,
             1 if (self_gid and gid == self_gid) else 0, photo),
        ))

    if statements:
        execute_many(statements)
    return {"users": len(users), "contacts_linked": linked}


# ── Projects ──────────────────────────────────────────────────────────────


def sync_projects(token: str, workspace_gid: str) -> dict:
    projects = _paginate(
        "/projects",
        token,
        {"workspace": workspace_gid, "archived": "false", "opt_fields": PROJECT_OPT_FIELDS},
    )
    statements = []
    for p in projects:
        gid = p.get("gid")
        if not gid:
            continue
        owner = p.get("owner") or {}
        statements.append((
            """INSERT INTO asana_projects
               (gid, workspace_gid, name, notes, archived, owner_gid, color,
                due_on, modified_at, created_at, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(gid) DO UPDATE SET
                 workspace_gid=excluded.workspace_gid,
                 name=excluded.name, notes=excluded.notes,
                 archived=excluded.archived, owner_gid=excluded.owner_gid,
                 color=excluded.color, due_on=excluded.due_on,
                 modified_at=excluded.modified_at,
                 synced_at=datetime('now')""",
            (gid, workspace_gid, p.get("name", "(unnamed)"), p.get("notes"),
             1 if p.get("archived") else 0, owner.get("gid"), p.get("color"),
             p.get("due_on"), p.get("modified_at"), p.get("created_at")),
        ))
    if statements:
        execute_many(statements)
    return {"projects": len(projects)}


# ── Tasks ─────────────────────────────────────────────────────────────────


def _resolve_assignee_contact(assignee_gid: str | None) -> int | None:
    if not assignee_gid:
        return None
    rows = execute(
        "SELECT contact_id FROM asana_users WHERE gid = ?", (assignee_gid,)
    )
    return rows[0]["contact_id"] if rows and rows[0]["contact_id"] else None


def sync_project_tasks(token: str, project_gid: str, modified_since: str) -> dict:
    """Sync all tasks in one project that have been modified since the cutoff."""
    params = {
        "project": project_gid,
        "modified_since": modified_since,
        "opt_fields": TASK_OPT_FIELDS,
    }
    try:
        tasks = _paginate("/tasks", token, params)
    except urllib.error.HTTPError as e:
        return {"project_gid": project_gid, "error": f"http_{e.code}", "synced": 0}

    statements = []
    for t in tasks:
        gid = t.get("gid")
        if not gid:
            continue

        assignee = t.get("assignee") or {}
        created_by = t.get("created_by") or {}
        parent = t.get("parent") or {}
        workspace = t.get("workspace") or {}
        memberships = t.get("memberships") or []

        primary_project_gid = None
        all_project_gids = []
        for m in memberships:
            mp = (m.get("project") or {}).get("gid")
            if mp:
                all_project_gids.append(mp)
                if not primary_project_gid:
                    primary_project_gid = mp
        if not primary_project_gid:
            primary_project_gid = project_gid
            all_project_gids = [project_gid]

        assignee_gid = assignee.get("gid")
        assignee_contact_id = _resolve_assignee_contact(assignee_gid)

        custom_fields = t.get("custom_fields")
        custom_fields_json = json.dumps(custom_fields) if custom_fields else None
        tags = t.get("tags")
        tags_json = json.dumps([
            {"gid": tg.get("gid"), "name": tg.get("name")} for tg in tags
        ]) if tags else None

        statements.append((
            """INSERT INTO asana_tasks
               (gid, workspace_gid, project_gid, project_gids, name, notes,
                assignee_gid, assignee_contact_id, created_by_gid,
                completed, completed_at, due_on, due_at, start_on,
                parent_gid, num_subtasks, permalink, custom_fields, tags,
                modified_at, created_at, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(gid) DO UPDATE SET
                 workspace_gid=excluded.workspace_gid,
                 project_gid=excluded.project_gid,
                 project_gids=excluded.project_gids,
                 name=excluded.name, notes=excluded.notes,
                 assignee_gid=excluded.assignee_gid,
                 assignee_contact_id=excluded.assignee_contact_id,
                 created_by_gid=COALESCE(excluded.created_by_gid, asana_tasks.created_by_gid),
                 completed=excluded.completed, completed_at=excluded.completed_at,
                 due_on=excluded.due_on, due_at=excluded.due_at,
                 start_on=excluded.start_on,
                 parent_gid=excluded.parent_gid, num_subtasks=excluded.num_subtasks,
                 permalink=excluded.permalink,
                 custom_fields=excluded.custom_fields, tags=excluded.tags,
                 modified_at=excluded.modified_at, synced_at=datetime('now')""",
            (gid, workspace.get("gid") or "", primary_project_gid,
             json.dumps(all_project_gids), t.get("name", "(unnamed)"), t.get("notes"),
             assignee_gid, assignee_contact_id, created_by.get("gid"),
             1 if t.get("completed") else 0, t.get("completed_at"),
             t.get("due_on"), t.get("due_at"), t.get("start_on"),
             parent.get("gid"), t.get("num_subtasks", 0), t.get("permalink_url"),
             custom_fields_json, tags_json,
             t.get("modified_at") or datetime.now(tz=timezone.utc).isoformat(),
             t.get("created_at")),
        ))

    if statements:
        execute_many(statements)
    return {"project_gid": project_gid, "synced": len(statements)}


# ── Top-level orchestrator ───────────────────────────────────────────────


def sync_asana() -> dict:
    """Full Asana sync. Safe to call when no token is configured."""
    token = asana_auth.get_token()
    if not token:
        return {"status": "skipped", "reason": "Asana not connected"}

    saved = asana_auth.load_token() or {}
    self_gid = saved.get("user_gid")

    try:
        ws_result = sync_workspaces(token)

        # Compute modified_since: prefer the last-sync timestamp (with overlap),
        # otherwise default to DEFAULT_INITIAL_LOOKBACK_DAYS ago.
        last_sync = execute(
            "SELECT value FROM soy_meta WHERE key = 'asana_tasks_last_synced'"
        )
        if last_sync:
            cutoff = datetime.fromisoformat(last_sync[0]["value"]) - timedelta(minutes=15)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            modified_since = cutoff.isoformat()
        else:
            modified_since = (
                datetime.now(tz=timezone.utc) - timedelta(days=DEFAULT_INITIAL_LOOKBACK_DAYS)
            ).isoformat()

        users_total = 0
        contacts_linked = 0
        projects_total = 0
        tasks_synced = 0
        per_project = []
        per_workspace = {}

        for ws in ws_result["list"]:
            wgid = ws["gid"]
            users_r = sync_users(token, wgid, self_gid)
            users_total += users_r["users"]
            contacts_linked += users_r["contacts_linked"]

            projects_r = sync_projects(token, wgid)
            projects_total += projects_r["projects"]

            # Fetch tasks per (non-archived) project
            project_rows = execute(
                "SELECT gid, name FROM asana_projects WHERE workspace_gid = ? AND archived = 0",
                (wgid,),
            )
            ws_tasks = 0
            for p in project_rows:
                r = sync_project_tasks(token, p["gid"], modified_since)
                per_project.append({"name": p["name"], **r})
                ws_tasks += r.get("synced", 0)
            tasks_synced += ws_tasks
            per_workspace[ws["name"]] = {
                "users": users_r["users"],
                "projects": projects_r["projects"],
                "tasks_touched": ws_tasks,
            }

        # Backfill assignee_contact_id for any tasks where the assignee's
        # contact mapping was learned during this sync run.
        execute_write(
            """UPDATE asana_tasks
               SET assignee_contact_id = (
                 SELECT contact_id FROM asana_users au WHERE au.gid = asana_tasks.assignee_gid
               )
               WHERE assignee_gid IS NOT NULL AND assignee_contact_id IS NULL"""
        )

        execute_write(
            "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) "
            "VALUES ('asana_last_synced', datetime('now'), datetime('now'))"
        )
        execute_write(
            "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) "
            "VALUES ('asana_tasks_last_synced', datetime('now'), datetime('now'))"
        )

        return {
            "status": "ok",
            "workspaces": per_workspace,
            "users_synced": users_total,
            "contacts_linked": contacts_linked,
            "projects_synced": projects_total,
            "tasks_touched": tasks_synced,
            "modified_since": modified_since,
        }
    except Exception as e:
        print(f"Asana sync failed: {e}", file=sys.stderr)
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    print(json.dumps(sync_asana(), indent=2))
