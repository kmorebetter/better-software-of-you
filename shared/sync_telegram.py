#!/usr/bin/env python3
"""Bidirectional sync between local SoY SQLite and Cloudflare D1 for Telegram bot.

Push: Snapshots of local context (projects, tasks, notes, contacts) → D1 telegram_context
Pull: Backlog items captured via Telegram → local SoY database

Usage:
    python3 shared/sync_telegram.py push
    python3 shared/sync_telegram.py pull
    python3 shared/sync_telegram.py sync       # push then pull
    python3 shared/sync_telegram.py status
"""

import json
import os
import sqlite3
import sys
import urllib.request
import urllib.error

PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
DB_PATH = os.path.join(PLUGIN_ROOT, "data", "soy.db")

TELEGRAM_INBOX_PROJECT = "Telegram Inbox"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _get_cf_credentials(conn):
    """Get Cloudflare credentials from soy_meta."""
    rows = conn.execute(
        "SELECT key, value FROM soy_meta WHERE key IN "
        "('cf_account_id', 'cf_d1_database_id', 'cf_api_token')"
    ).fetchall()
    creds = {r["key"]: r["value"] for r in rows}
    required = ["cf_account_id", "cf_d1_database_id", "cf_api_token"]
    missing = [k for k in required if k not in creds]
    if missing:
        return None
    return creds


def _d1_query(creds, sql, params=None):
    """Execute a read query on D1 via Cloudflare REST API."""
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{creds['cf_account_id']}"
        f"/d1/database/{creds['cf_d1_database_id']}/query"
    )
    body = {"sql": sql}
    if params:
        body["params"] = params
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {creds['cf_api_token']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("success") and result.get("result"):
                results = result["result"]
                if isinstance(results, list) and len(results) > 0:
                    return results[0].get("results", [])
                return []
            return []
    except Exception as e:
        return {"error": str(e)}


def _d1_execute(creds, sql, params=None):
    """Execute a write statement on D1."""
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{creds['cf_account_id']}"
        f"/d1/database/{creds['cf_d1_database_id']}/query"
    )
    body = {"sql": sql}
    if params:
        body["params"] = params
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {creds['cf_api_token']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("success", False)
    except Exception:
        return False


# ── Push: Local → D1 Context Cache ──


def cmd_push(args):
    """Push context snapshots from local SoY to D1."""
    conn = _get_db()
    creds = _get_cf_credentials(conn)
    if not creds:
        print(json.dumps({"error": "Cloudflare not configured"}))
        sys.exit(1)

    pushed = {}

    # Projects (active/planning)
    projects = conn.execute(
        "SELECT p.id, p.name, p.status, p.client_id, "
        "c.name as client, "
        "(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status != 'done') as open_tasks, "
        "(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status = 'done') as done_tasks "
        "FROM projects p "
        "LEFT JOIN contacts c ON c.id = p.client_id "
        "WHERE p.status IN ('active', 'planning') "
        "ORDER BY p.name"
    ).fetchall()
    projects_data = [dict(p) for p in projects]
    ok = _d1_execute(
        creds,
        "INSERT INTO telegram_context (key, value, updated_at) VALUES ('projects', ?, datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
        [json.dumps(projects_data)],
    )
    pushed["projects"] = len(projects_data) if ok else "error"

    # Tasks (open, up to 100)
    tasks = conn.execute(
        "SELECT t.id, t.title, t.status, t.priority, t.due_date, p.name as project_name "
        "FROM tasks t "
        "LEFT JOIN projects p ON p.id = t.project_id "
        "WHERE t.status != 'done' "
        "ORDER BY CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, t.id "
        "LIMIT 100"
    ).fetchall()
    tasks_data = [dict(t) for t in tasks]
    ok = _d1_execute(
        creds,
        "INSERT INTO telegram_context (key, value, updated_at) VALUES ('tasks', ?, datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
        [json.dumps(tasks_data)],
    )
    pushed["tasks"] = len(tasks_data) if ok else "error"

    # Notes (last 50)
    notes = conn.execute(
        "SELECT n.id, n.title, SUBSTR(n.content, 1, 200) as content, n.tags, "
        "n.linked_projects as project_name "
        "FROM standalone_notes n "
        "ORDER BY n.created_at DESC "
        "LIMIT 50"
    ).fetchall()
    notes_data = [dict(n) for n in notes]
    ok = _d1_execute(
        creds,
        "INSERT INTO telegram_context (key, value, updated_at) VALUES ('notes', ?, datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
        [json.dumps(notes_data)],
    )
    pushed["notes"] = len(notes_data) if ok else "error"

    # Contacts (active, top 50)
    contacts = conn.execute(
        "SELECT c.id, c.name, c.company, c.role, c.email "
        "FROM contacts c "
        "WHERE c.status = 'active' "
        "ORDER BY c.name "
        "LIMIT 50"
    ).fetchall()
    contacts_data = [dict(c) for c in contacts]
    ok = _d1_execute(
        creds,
        "INSERT INTO telegram_context (key, value, updated_at) VALUES ('contacts', ?, datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
        [json.dumps(contacts_data)],
    )
    pushed["contacts"] = len(contacts_data) if ok else "error"

    # Meta
    meta = {
        "total_projects": len(projects_data),
        "total_open_tasks": len(tasks_data),
        "total_contacts": len(contacts_data),
        "total_notes": len(notes_data),
        "last_sync": conn.execute("SELECT datetime('now') as now").fetchone()["now"],
    }
    _d1_execute(
        creds,
        "INSERT INTO telegram_context (key, value, updated_at) VALUES ('meta', ?, datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
        [json.dumps(meta)],
    )
    pushed["meta"] = True

    # Update local sync timestamp
    conn.execute(
        "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) "
        "VALUES ('telegram_last_context_push', datetime('now'), datetime('now'))"
    )
    conn.commit()
    conn.close()

    print(json.dumps({"ok": True, "pushed": pushed}))


# ── Pull: D1 Backlog → Local SoY ──


def _fuzzy_match_project(conn, project_name):
    """Find a project by fuzzy name match. Returns project_id or None."""
    if not project_name:
        return None

    # Exact match first
    row = conn.execute(
        "SELECT id FROM projects WHERE LOWER(name) = LOWER(?)", (project_name,)
    ).fetchone()
    if row:
        return row["id"]

    # Partial match
    row = conn.execute(
        "SELECT id FROM projects WHERE LOWER(name) LIKE LOWER(?)",
        (f"%{project_name}%",),
    ).fetchone()
    if row:
        return row["id"]

    return None


def _get_or_create_inbox_project(conn):
    """Get or create the 'Telegram Inbox' project for uncategorized items."""
    row = conn.execute(
        "SELECT id FROM projects WHERE name = ?", (TELEGRAM_INBOX_PROJECT,)
    ).fetchone()
    if row:
        return row["id"]

    conn.execute(
        "INSERT INTO projects (name, status, description, created_at, updated_at) "
        "VALUES (?, 'active', 'Items captured via Telegram bot', datetime('now'), datetime('now'))",
        (TELEGRAM_INBOX_PROJECT,),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM projects WHERE name = ?", (TELEGRAM_INBOX_PROJECT,)
    ).fetchone()
    return row["id"]


def cmd_pull(args):
    """Pull backlog items from D1 to local SoY."""
    conn = _get_db()
    creds = _get_cf_credentials(conn)
    if not creds:
        print(json.dumps({"error": "Cloudflare not configured"}))
        sys.exit(1)

    # Fetch unsynced backlog items
    items = _d1_query(
        creds,
        "SELECT id, type, project_name, project_id, title, content, tags, priority "
        "FROM telegram_backlog WHERE synced_to_soy = 0 ORDER BY created_at",
    )
    if isinstance(items, dict) and "error" in items:
        print(json.dumps({"error": f"Failed to query D1: {items['error']}"}))
        sys.exit(1)

    if not items:
        conn.execute(
            "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) "
            "VALUES ('telegram_last_backlog_pull', datetime('now'), datetime('now'))"
        )
        conn.commit()
        conn.close()
        print(json.dumps({"pulled": 0, "message": "No pending backlog items"}))
        return

    counts = {"tasks": 0, "notes": 0, "errors": 0}
    inbox_project_id = None

    for item in items:
        try:
            # Resolve project
            project_id = item.get("project_id")
            if not project_id and item.get("project_name"):
                project_id = _fuzzy_match_project(conn, item["project_name"])

            if item["type"] == "task":
                if not project_id:
                    if inbox_project_id is None:
                        inbox_project_id = _get_or_create_inbox_project(conn)
                    project_id = inbox_project_id

                conn.execute(
                    "INSERT INTO tasks (project_id, title, description, status, priority, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'todo', ?, datetime('now'), datetime('now'))",
                    (project_id, item["title"], item.get("content"), item.get("priority", "medium")),
                )
                local_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

                # Record sync
                conn.execute(
                    "INSERT INTO telegram_synced_items (remote_id, type, local_entity_type, local_entity_id) "
                    "VALUES (?, 'task', 'task', ?)",
                    (item["id"], local_id),
                )

                # Log activity
                conn.execute(
                    "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
                    "VALUES ('task', ?, 'created', ?, datetime('now'))",
                    (local_id, json.dumps({"source": "telegram", "title": item["title"]})),
                )

                counts["tasks"] += 1

            elif item["type"] == "note":
                # Create standalone note
                tags = item.get("tags")
                # Resolve linked_projects as project name if we have a match
                linked_projects = None
                if project_id:
                    proj_row = conn.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()
                    if proj_row:
                        linked_projects = proj_row["name"]
                conn.execute(
                    "INSERT INTO standalone_notes (title, content, tags, linked_projects, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
                    (item["title"], item.get("content"), tags, linked_projects),
                )
                local_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

                conn.execute(
                    "INSERT INTO telegram_synced_items (remote_id, type, local_entity_type, local_entity_id) "
                    "VALUES (?, 'note', 'standalone_note', ?)",
                    (item["id"], local_id),
                )

                conn.execute(
                    "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
                    "VALUES ('standalone_note', ?, 'created', ?, datetime('now'))",
                    (local_id, json.dumps({"source": "telegram", "title": item["title"]})),
                )

                counts["notes"] += 1

            # Mark as synced in D1
            _d1_execute(
                creds,
                "UPDATE telegram_backlog SET synced_to_soy = 1, synced_at = datetime('now'), local_entity_id = ? WHERE id = ?",
                [local_id, item["id"]],
            )

        except Exception as e:
            counts["errors"] += 1
            sys.stderr.write(f"Error syncing item {item.get('id')}: {e}\n")

    # Update timestamps
    conn.execute(
        "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) "
        "VALUES ('telegram_last_backlog_pull', datetime('now'), datetime('now'))"
    )
    conn.commit()
    conn.close()

    total = counts["tasks"] + counts["notes"]
    print(json.dumps({"pulled": total, "details": counts}))


def cmd_sync(args):
    """Full sync: push context then pull backlog."""
    # Push first
    cmd_push([])
    # Then pull (re-open connection)
    print("---")
    cmd_pull([])


def cmd_status(args):
    """Show sync status."""
    conn = _get_db()

    last_push = conn.execute(
        "SELECT value FROM soy_meta WHERE key = 'telegram_last_context_push'"
    ).fetchone()
    last_pull = conn.execute(
        "SELECT value FROM soy_meta WHERE key = 'telegram_last_backlog_pull'"
    ).fetchone()

    synced = conn.execute(
        "SELECT type, COUNT(*) as count FROM telegram_synced_items GROUP BY type"
    ).fetchall()
    synced_counts = {r["type"]: r["count"] for r in synced}

    conn.close()

    # Check D1 for pending items
    creds_conn = _get_db()
    creds = _get_cf_credentials(creds_conn)
    pending_count = 0
    if creds:
        pending = _d1_query(
            creds,
            "SELECT COUNT(*) as count FROM telegram_backlog WHERE synced_to_soy = 0",
        )
        if isinstance(pending, list) and pending:
            pending_count = pending[0].get("count", 0)
    creds_conn.close()

    print(json.dumps({
        "last_context_push": last_push["value"] if last_push else None,
        "last_backlog_pull": last_pull["value"] if last_pull else None,
        "synced_items": synced_counts,
        "pending_in_d1": pending_count,
    }))


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: sync_telegram.py <push|pull|sync|status>"}))
        sys.exit(1)

    command = sys.argv[1]
    rest = sys.argv[2:]

    if command == "push":
        cmd_push(rest)
    elif command == "pull":
        cmd_pull(rest)
    elif command == "sync":
        cmd_sync(rest)
    elif command == "status":
        cmd_status(rest)
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
