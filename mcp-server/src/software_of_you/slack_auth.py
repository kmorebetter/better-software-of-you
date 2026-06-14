"""Slack auth — slim wrapper for the MCP server.

Reads the same token file that ``shared/slack_auth.py`` writes:
``~/.local/share/software-of-you/tokens/slack_token.json``.

Slack tokens (xoxp- user, xoxb- bot) are long-lived. No OAuth refresh.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DATA_HOME = os.environ.get(
    "XDG_DATA_HOME",
    os.path.join(os.path.expanduser("~"), ".local", "share"),
)
TOKENS_DIR = Path(DATA_HOME) / "software-of-you" / "tokens"
TOKEN_PATH = TOKENS_DIR / "slack_token.json"

SLACK_API = "https://slack.com/api"


def load_token() -> dict | None:
    if not TOKEN_PATH.exists():
        return None
    try:
        return json.loads(TOKEN_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def get_token() -> str | None:
    data = load_token()
    return data.get("access_token") if data else None


def is_connected() -> bool:
    return bool(get_token())


def auth_test(token: str) -> dict:
    """Verify the token via auth.test; returns Slack response dict."""
    req = urllib.request.Request(
        f"{SLACK_API}/auth.test",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"http_{e.code}"}
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"network: {e.reason}"}


def save_token(token: str) -> dict:
    """Verify and persist a token. Returns dict with ok + workspace info."""
    if not token or not token.startswith(("xoxp-", "xoxb-", "xoxe.")):
        return {
            "ok": False,
            "error": "Token must start with xoxp- (user), xoxb- (bot), or xoxe. (refresh).",
        }

    info = auth_test(token)
    if not info.get("ok"):
        return {"ok": False, "error": f"Slack rejected the token: {info.get('error', 'unknown')}"}

    TOKENS_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        os.chmod(TOKENS_DIR, 0o700)
    except OSError:
        pass

    payload = {
        "access_token": token,
        "team_id": info.get("team_id"),
        "team": info.get("team"),
        "user_id": info.get("user_id"),
        "user": info.get("user"),
        "url": info.get("url"),
        "saved_at": int(time.time()),
    }
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(payload, f, indent=2)

    return {
        "ok": True,
        "team": info.get("team"),
        "user": info.get("user"),
        "user_id": info.get("user_id"),
        "url": info.get("url"),
    }


def revoke_token() -> bool:
    """Remove the local token file. Returns True if anything was removed."""
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
        return True
    return False
