#!/usr/bin/env python3
"""Setup and status for the local SoY Telegram bot.

Validates bot token, stores config in .env, deregisters any existing webhook.

Usage:
    python3 shared/setup_telegram.py setup <bot_token> <owner_id>
    python3 shared/setup_telegram.py status
    python3 shared/setup_telegram.py unregister [bot_token]
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
ENV_PATH = os.path.join(PLUGIN_ROOT, ".env")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


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


def _update_env(key, value):
    """Add or update a key in .env file."""
    lines = []
    found = False

    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)

    if not found:
        lines.append(f"{key}={value}\n")

    with open(ENV_PATH, "w") as f:
        f.writelines(lines)
    os.chmod(ENV_PATH, 0o600)


def cmd_setup(args):
    """Setup: validate token, store in .env, deregister webhook."""
    if len(args) < 2:
        print(json.dumps({
            "error": "Usage: setup_telegram.py setup <bot_token> <owner_id>",
        }))
        sys.exit(1)

    bot_token = args[0]
    owner_id = args[1]
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

    # Step 2: Deregister any existing webhook
    webhook_result = _telegram_api(bot_token, "deleteWebhook")
    steps.append({
        "step": "deregister_webhook",
        "ok": webhook_result.get("ok", False),
    })

    # Step 3: Write to .env
    _update_env("TELEGRAM_BOT_TOKEN", bot_token)
    _update_env("TELEGRAM_OWNER_ID", owner_id)
    steps.append({"step": "write_env", "ok": True})

    # Step 4: Store metadata in SoY
    conn = _get_db()
    conn.execute(
        "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) "
        "VALUES ('telegram_bot_username', ?, datetime('now'))",
        (bot_username,),
    )
    conn.execute(
        "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) "
        "VALUES ('telegram_bot_mode', 'local', datetime('now'))",
    )
    conn.execute(
        "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) "
        "VALUES ('telegram_setup_at', datetime('now'), datetime('now'))",
    )
    conn.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
        "VALUES ('telegram_bot', 0, 'setup_completed', ?, datetime('now'))",
        (json.dumps({"bot": f"@{bot_username}", "mode": "local"}),),
    )
    conn.commit()
    conn.close()
    steps.append({"step": "store_metadata", "ok": True})

    print(json.dumps({
        "ok": True,
        "bot": f"@{bot_username}",
        "bot_name": bot_name,
        "mode": "local",
        "steps": steps,
    }))


def cmd_status(args):
    """Check Telegram bot setup status."""
    conn = _get_db()

    meta_keys = [
        "telegram_bot_username",
        "telegram_bot_mode",
        "telegram_setup_at",
    ]
    rows = conn.execute(
        "SELECT key, value FROM soy_meta WHERE key IN ({})".format(
            ",".join("?" for _ in meta_keys)
        ),
        meta_keys,
    ).fetchall()
    meta = {r["key"]: r["value"] for r in rows}

    # Module info
    module = conn.execute(
        "SELECT name, version, enabled FROM modules WHERE name = 'telegram-bot'"
    ).fetchone()

    # Session stats
    session_count = conn.execute(
        "SELECT COUNT(*) as c FROM telegram_bot_sessions"
    ).fetchone()
    msg_count = conn.execute(
        "SELECT COUNT(*) as c FROM telegram_conversations"
    ).fetchone()
    error_count = conn.execute(
        "SELECT COUNT(*) as c FROM telegram_bot_errors"
    ).fetchone()

    conn.close()

    bot_username = meta.get("telegram_bot_username")

    print(json.dumps({
        "configured": "telegram_bot_username" in meta,
        "bot": f"@{bot_username}" if bot_username else None,
        "mode": meta.get("telegram_bot_mode", "unknown"),
        "setup_at": meta.get("telegram_setup_at"),
        "module": dict(module) if module else None,
        "sessions": session_count["c"] if session_count else 0,
        "messages": msg_count["c"] if msg_count else 0,
        "errors": error_count["c"] if error_count else 0,
    }))


def cmd_unregister(args):
    """Deregister webhook and clean up."""
    # Try to get token from .env or args
    bot_token = None
    if args:
        bot_token = args[0]
    elif os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                if line.strip().startswith("TELEGRAM_BOT_TOKEN="):
                    bot_token = line.strip().split("=", 1)[1]
                    break

    if not bot_token:
        print(json.dumps({
            "error": "Bot token required — pass as argument or set in .env",
        }))
        sys.exit(1)

    result = _telegram_api(bot_token, "deleteWebhook")

    if result.get("ok"):
        conn = _get_db()
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
