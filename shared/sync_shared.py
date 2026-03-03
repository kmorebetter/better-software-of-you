#!/usr/bin/env python3
"""Sync client changes from Cloudflare D1 back to local SoY database.

Pulls task completions, notes, comments, and task suggestions that clients
have added via published shared pages.

Usage:
    python3 shared/sync_shared.py pull [token]
    python3 shared/sync_shared.py status
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


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _get_cf_credentials(conn):
    """Get Cloudflare credentials from soy_meta."""
    rows = conn.execute(
        "SELECT key, value FROM soy_meta WHERE key IN "
        "('cf_account_id', 'cf_d1_database_id', 'cf_api_token', 'cf_pages_project')"
    ).fetchall()
    creds = {r["key"]: r["value"] for r in rows}
    required = ["cf_account_id", "cf_d1_database_id", "cf_api_token"]
    missing = [k for k in required if k not in creds]
    if missing:
        return None
    return creds


def _d1_query(creds, sql, params=None):
    """Execute a read query on D1 via Cloudflare REST API. Returns rows."""
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


def _pull_for_page(conn, creds, page):
    """Pull all unsynced changes for a single shared page. Returns counts."""
    token = page["token"]
    page_id = page["id"]
    project_id = page["project_id"]
    counts = {"task_completions": 0, "notes": 0, "comments": 0, "suggestions": 0}

    # ── Task completions ──
    tasks = _d1_query(
        creds,
        "SELECT id, client_completed, client_completed_by, client_completed_at "
        "FROM tasks WHERE page_token = ? AND synced_to_soy = 0 AND client_completed = 1",
        [token],
    )
    if isinstance(tasks, dict) and "error" in tasks:
        return {"error": tasks["error"]}

    for t in tasks:
        # Record as a note on the task for user review (don't auto-change task status)
        conn.execute(
            "INSERT INTO notes (entity_type, entity_id, content, source, created_at) "
            "VALUES ('task', ?, ?, 'shared_page', datetime('now'))",
            (
                t["id"],
                f"Client {t.get('client_completed_by', 'unknown')} marked this task as done "
                f"on the shared page (at {t.get('client_completed_at', 'unknown time')})",
            ),
        )
        conn.execute(
            "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
            "VALUES ('task', ?, 'client_completed', ?, datetime('now'))",
            (t["id"], json.dumps({"by": t.get("client_completed_by"), "via": "shared_page", "token": token})),
        )
        # Mark synced in D1
        _d1_execute(creds, "UPDATE tasks SET synced_to_soy = 1 WHERE id = ?", [t["id"]])
        counts["task_completions"] += 1

    # ── Notes ──
    notes = _d1_query(
        creds,
        "SELECT id, section_id, content, author_name, created_at "
        "FROM notes WHERE page_token = ? AND synced_to_soy = 0",
        [token],
    )
    if isinstance(notes, list):
        for n in notes:
            conn.execute(
                "INSERT INTO notes (entity_type, entity_id, content, source, created_at) "
                "VALUES ('project', ?, ?, 'shared_page', datetime('now'))",
                (
                    project_id,
                    f"[Shared page note - {n.get('section_id', 'unknown section')}] "
                    f"{n.get('author_name', 'Client')}: {n['content']}",
                ),
            )
            conn.execute(
                "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
                "VALUES ('project', ?, 'shared_page_note', ?, datetime('now'))",
                (project_id, json.dumps({"by": n.get("author_name"), "section": n.get("section_id"), "token": token})),
            )
            _d1_execute(creds, "UPDATE notes SET synced_to_soy = 1 WHERE id = ?", [n["id"]])
            counts["notes"] += 1

    # ── Comments ──
    comments = _d1_query(
        creds,
        "SELECT id, content, author_name, author_type, created_at "
        "FROM comments WHERE page_token = ? AND synced_to_soy = 0",
        [token],
    )
    if isinstance(comments, list):
        for c in comments:
            conn.execute(
                "INSERT INTO notes (entity_type, entity_id, content, source, created_at) "
                "VALUES ('project', ?, ?, 'shared_page', datetime('now'))",
                (
                    project_id,
                    f"[Shared page comment] {c.get('author_name', 'Client')} "
                    f"({c.get('author_type', 'client')}): {c['content']}",
                ),
            )
            _d1_execute(creds, "UPDATE comments SET synced_to_soy = 1 WHERE id = ?", [c["id"]])
            counts["comments"] += 1

    # ── Suggestions ──
    suggestions = _d1_query(
        creds,
        "SELECT id, title, description, suggested_by, created_at "
        "FROM suggestions WHERE page_token = ? AND synced_to_soy = 0",
        [token],
    )
    if isinstance(suggestions, list):
        for s in suggestions:
            conn.execute(
                "INSERT INTO task_suggestions "
                "(shared_page_id, project_id, title, description, suggested_by, status, remote_id) "
                "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                (page_id, project_id, s["title"], s.get("description"), s.get("suggested_by", "Client"), s["id"]),
            )
            conn.execute(
                "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
                "VALUES ('task_suggestion', last_insert_rowid(), 'received', ?, datetime('now'))",
                (json.dumps({"title": s["title"], "by": s.get("suggested_by"), "token": token}),),
            )
            _d1_execute(creds, "UPDATE suggestions SET synced_to_soy = 1 WHERE id = ?", [s["id"]])
            counts["suggestions"] += 1

    # Update sync timestamp
    conn.execute(
        "UPDATE shared_pages SET last_synced_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
        (page_id,),
    )

    total = sum(counts.values())
    if total > 0:
        conn.execute(
            "INSERT INTO shared_page_sync_log (shared_page_id, direction, items_synced, details) "
            "VALUES (?, 'pull', ?, ?)",
            (page_id, total, json.dumps(counts)),
        )

    conn.commit()
    return counts


def cmd_pull(args):
    """Pull client changes from D1."""
    conn = _get_db()
    creds = _get_cf_credentials(conn)
    if not creds:
        print(json.dumps({"error": "Cloudflare not configured"}))
        sys.exit(1)

    token_filter = args[0] if args else None

    if token_filter:
        pages = conn.execute(
            "SELECT id, token, project_id, title FROM shared_pages WHERE token = ? AND status = 'active'",
            (token_filter,),
        ).fetchall()
    else:
        pages = conn.execute(
            "SELECT id, token, project_id, title FROM shared_pages WHERE status = 'active'"
        ).fetchall()

    if not pages:
        print(json.dumps({"pulled": 0, "message": "No active shared pages found"}))
        conn.close()
        return

    total_counts = {"task_completions": 0, "notes": 0, "comments": 0, "suggestions": 0}
    errors = []

    for page in pages:
        try:
            counts = _pull_for_page(conn, creds, page)
            if isinstance(counts, dict) and "error" in counts:
                errors.append({"token": page["token"], "error": counts["error"]})
            else:
                for k, v in counts.items():
                    total_counts[k] += v
        except Exception as e:
            errors.append({"token": page["token"], "error": str(e)})
            conn.rollback()

    # Update meta timestamp
    conn.execute(
        "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) "
        "VALUES ('shared_pages_last_synced', datetime('now'), datetime('now'))"
    )
    conn.commit()
    conn.close()

    total = sum(total_counts.values())
    print(json.dumps({
        "pulled": total,
        "details": total_counts,
        "pages_checked": len(pages),
        "errors": errors,
    }))


def cmd_status(args):
    """Show sync status for shared pages."""
    conn = _get_db()

    last_sync = conn.execute(
        "SELECT value FROM soy_meta WHERE key = 'shared_pages_last_synced'"
    ).fetchone()

    pages = conn.execute(
        "SELECT token, title, status, last_published_at, last_synced_at FROM shared_pages ORDER BY last_published_at DESC"
    ).fetchall()

    pending_suggestions = conn.execute(
        "SELECT COUNT(*) as count FROM task_suggestions WHERE status = 'pending'"
    ).fetchone()

    recent_log = conn.execute(
        "SELECT sp.title, l.direction, l.items_synced, l.created_at "
        "FROM shared_page_sync_log l JOIN shared_pages sp ON sp.id = l.shared_page_id "
        "ORDER BY l.created_at DESC LIMIT 10"
    ).fetchall()

    print(json.dumps({
        "last_sync": last_sync["value"] if last_sync else None,
        "pages": [dict(p) for p in pages],
        "pending_suggestions": pending_suggestions["count"],
        "recent_syncs": [dict(r) for r in recent_log],
    }))
    conn.close()


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: sync_shared.py <pull|status> [args]"}))
        sys.exit(1)

    command = sys.argv[1]
    rest = sys.argv[2:]

    if command == "pull":
        cmd_pull(rest)
    elif command == "status":
        cmd_status(rest)
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
