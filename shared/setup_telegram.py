#!/usr/bin/env python3
"""Interactive setup for the SoY Telegram Bot.

Validates bot token, sets Cloudflare env vars, registers webhook,
applies D1 schema, and pushes initial context.

Usage:
    python3 shared/setup_telegram.py setup
    python3 shared/setup_telegram.py status
    python3 shared/setup_telegram.py unregister
"""

import json
import os
import secrets
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
    required = ["cf_account_id", "cf_d1_database_id", "cf_api_token", "cf_pages_project"]
    missing = [k for k in required if k not in creds]
    if missing:
        return None, missing
    return creds, []


def _telegram_api(token, method, data=None):
    """Call a Telegram Bot API method."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    if data:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "description": f"HTTP {e.code}: {body[:300]}"}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def _cf_api(method, path, creds, data=None):
    """Call Cloudflare API."""
    url = f"https://api.cloudflare.com/client/v4{path}"
    payload = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {creds['cf_api_token']}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"success": False, "errors": [{"message": f"HTTP {e.code}: {body[:300]}"}]}
    except Exception as e:
        return {"success": False, "errors": [{"message": str(e)}]}


def _d1_execute(creds, sql, params=None):
    """Execute a SQL statement on D1."""
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


def cmd_setup(args):
    """Interactive setup flow. Expects args: bot_token, owner_id, anthropic_key."""
    conn = _get_db()
    creds, missing = _get_cf_credentials(conn)
    if not creds:
        print(json.dumps({
            "error": "Cloudflare not configured",
            "missing": missing,
            "hint": "Run Cloudflare Pages setup first (cf_account_id, cf_d1_database_id, cf_api_token, cf_pages_project must be in soy_meta)",
        }))
        sys.exit(1)

    # Parse arguments
    if len(args) < 3:
        print(json.dumps({
            "error": "Usage: setup_telegram.py setup <bot_token> <owner_id> <anthropic_api_key>",
        }))
        sys.exit(1)

    bot_token = args[0]
    owner_id = args[1]
    anthropic_key = args[2]

    steps = []

    # Step 1: Validate bot token
    me = _telegram_api(bot_token, "getMe")
    if not me.get("ok"):
        print(json.dumps({
            "error": "Invalid bot token",
            "detail": me.get("description", "Unknown error"),
        }))
        sys.exit(1)
    bot_username = me["result"]["username"]
    bot_name = me["result"].get("first_name", bot_username)
    steps.append({"step": "validate_token", "ok": True, "bot": f"@{bot_username}"})

    # Step 2: Get owner name
    owner_row = conn.execute(
        "SELECT value FROM user_profile WHERE category = 'identity' AND key = 'name'"
    ).fetchone()
    owner_name = owner_row["value"] if owner_row else "SoY User"

    # Step 3: Generate webhook secret
    webhook_secret = secrets.token_hex(32)

    # Step 4: Set Cloudflare Pages environment variables
    project_name = creds["cf_pages_project"]
    env_vars = {
        "TELEGRAM_BOT_TOKEN": {"type": "secret_text", "value": bot_token},
        "TELEGRAM_OWNER_ID": {"type": "secret_text", "value": str(owner_id)},
        "TELEGRAM_WEBHOOK_SECRET": {"type": "secret_text", "value": webhook_secret},
        "ANTHROPIC_API_KEY": {"type": "secret_text", "value": anthropic_key},
        "SOY_OWNER_NAME": {"type": "plain_text", "value": owner_name},
    }

    env_result = _cf_api(
        "PATCH",
        f"/accounts/{creds['cf_account_id']}/pages/projects/{project_name}",
        creds,
        {
            "deployment_configs": {
                "production": {"env_vars": env_vars},
                "preview": {"env_vars": env_vars},
            }
        },
    )
    if not env_result.get("success"):
        errors = env_result.get("errors", [])
        print(json.dumps({
            "error": "Failed to set Cloudflare env vars",
            "detail": errors[0].get("message") if errors else "Unknown error",
        }))
        sys.exit(1)
    steps.append({"step": "set_env_vars", "ok": True})

    # Step 5: Apply D1 schema
    schema_path = os.path.join(PLUGIN_ROOT, "cloudflare", "telegram-schema.sql")
    if os.path.exists(schema_path):
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        # Strip comments, then split into statements
        lines = [line for line in schema_sql.splitlines() if not line.strip().startswith("--")]
        cleaned = "\n".join(lines)
        statements = [s.strip() for s in cleaned.split(";") if s.strip()]
        schema_ok = True
        for stmt in statements:
            if not _d1_execute(creds, stmt):
                schema_ok = False
                break
        steps.append({"step": "apply_d1_schema", "ok": schema_ok})
        if not schema_ok:
            print(json.dumps({
                "error": "Failed to apply D1 schema (some statements failed)",
                "steps": steps,
                "hint": "Schema may be partially applied. You can re-run setup safely.",
            }))
            sys.exit(1)
    else:
        steps.append({"step": "apply_d1_schema", "ok": False, "detail": "Schema file not found"})

    # Step 6: Register webhook
    webhook_url = f"https://{project_name}.pages.dev/api/telegram"
    webhook_result = _telegram_api(bot_token, "setWebhook", {
        "url": webhook_url,
        "secret_token": webhook_secret,
        "allowed_updates": ["message"],
    })
    if not webhook_result.get("ok"):
        print(json.dumps({
            "error": "Failed to register webhook",
            "detail": webhook_result.get("description", "Unknown error"),
            "steps": steps,
        }))
        sys.exit(1)
    steps.append({"step": "register_webhook", "ok": True, "url": webhook_url})

    # Step 7: Push initial context
    try:
        sync_path = os.path.join(PLUGIN_ROOT, "shared", "sync_telegram.py")
        if os.path.exists(sync_path):
            import subprocess
            result = subprocess.run(
                [sys.executable, sync_path, "push"],
                capture_output=True, text=True, timeout=30,
            )
            steps.append({
                "step": "push_context",
                "ok": result.returncode == 0,
                "detail": result.stdout.strip()[:200] if result.stdout else None,
            })
    except Exception as e:
        steps.append({"step": "push_context", "ok": False, "detail": str(e)})

    # Step 8: Store metadata locally (NOT secrets)
    conn.execute(
        "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('telegram_bot_username', ?, datetime('now'))",
        (bot_username,),
    )
    conn.execute(
        "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('telegram_webhook_url', ?, datetime('now'))",
        (webhook_url,),
    )
    conn.execute(
        "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('telegram_setup_at', datetime('now'), datetime('now'))",
    )

    # Log activity
    conn.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
        "VALUES ('telegram_bot', 0, 'setup_completed', ?, datetime('now'))",
        (json.dumps({"bot": f"@{bot_username}", "webhook": webhook_url}),),
    )
    conn.commit()
    conn.close()

    steps.append({"step": "store_metadata", "ok": True})

    print(json.dumps({
        "ok": True,
        "bot": f"@{bot_username}",
        "bot_name": bot_name,
        "webhook_url": webhook_url,
        "steps": steps,
    }))


def cmd_status(args):
    """Check Telegram bot setup status."""
    conn = _get_db()

    meta_keys = [
        "telegram_bot_username",
        "telegram_webhook_url",
        "telegram_setup_at",
        "telegram_last_context_push",
        "telegram_last_backlog_pull",
    ]
    rows = conn.execute(
        "SELECT key, value FROM soy_meta WHERE key IN ({})".format(
            ",".join("?" for _ in meta_keys)
        ),
        meta_keys,
    ).fetchall()
    meta = {r["key"]: r["value"] for r in rows}

    # Check module registration
    module = conn.execute(
        "SELECT name, version, enabled FROM modules WHERE name = 'telegram-bot'"
    ).fetchone()

    # Count synced items
    synced = conn.execute(
        "SELECT type, COUNT(*) as count FROM telegram_synced_items GROUP BY type"
    ).fetchall()
    synced_counts = {r["type"]: r["count"] for r in synced}

    conn.close()

    # Check webhook info if we have a token configured
    webhook_info = None
    bot_username = meta.get("telegram_bot_username")

    print(json.dumps({
        "configured": "telegram_bot_username" in meta,
        "bot": f"@{bot_username}" if bot_username else None,
        "webhook_url": meta.get("telegram_webhook_url"),
        "setup_at": meta.get("telegram_setup_at"),
        "last_context_push": meta.get("telegram_last_context_push"),
        "last_backlog_pull": meta.get("telegram_last_backlog_pull"),
        "module": dict(module) if module else None,
        "synced_items": synced_counts,
    }))


def cmd_unregister(args):
    """Unregister the webhook (disable the bot without deleting data)."""
    conn = _get_db()

    # We need the bot token to unregister — check if we have webhook info
    bot_username = conn.execute(
        "SELECT value FROM soy_meta WHERE key = 'telegram_bot_username'"
    ).fetchone()

    if not bot_username:
        print(json.dumps({"error": "No Telegram bot configured"}))
        sys.exit(1)

    # We can't unregister without the token, and we don't store it locally.
    # The user needs to pass it, or we use the Telegram deleteWebhook via CF env.
    if len(args) < 1:
        print(json.dumps({
            "error": "Bot token required to unregister",
            "usage": "setup_telegram.py unregister <bot_token>",
        }))
        sys.exit(1)

    bot_token = args[0]
    result = _telegram_api(bot_token, "deleteWebhook")

    if result.get("ok"):
        conn.execute(
            "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
            "VALUES ('telegram_bot', 0, 'webhook_unregistered', '{}', datetime('now'))"
        )
        conn.commit()

    conn.close()
    print(json.dumps({
        "ok": result.get("ok", False),
        "detail": result.get("description", ""),
    }))


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: setup_telegram.py <setup|status|unregister> [args]"}))
        sys.exit(1)

    command = sys.argv[1]
    rest = sys.argv[2:]

    if command == "setup":
        cmd_setup(rest)
    elif command == "status":
        cmd_status(rest)
    elif command == "unregister":
        cmd_unregister(rest)
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
