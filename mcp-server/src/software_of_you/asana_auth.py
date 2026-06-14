"""Asana auth — slim wrapper for the MCP server.

Asana Personal Access Tokens (PATs) are long-lived. No OAuth refresh.
Token is generated at https://app.asana.com/0/my-apps and stored at
``~/.local/share/software-of-you/tokens/asana_token.json``.
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
TOKEN_PATH = TOKENS_DIR / "asana_token.json"

ASANA_API = "https://app.asana.com/api/1.0"


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


def me(token: str) -> dict:
    """Verify the token via /users/me; returns Asana response dict."""
    req = urllib.request.Request(
        f"{ASANA_API}/users/me?opt_fields=name,email,gid,workspaces.name,workspaces.gid",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return {"ok": True, **data.get("data", {})}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
            err = body.get("errors", [{}])[0].get("message", f"http_{e.code}")
        except Exception:
            err = f"http_{e.code}"
        return {"ok": False, "error": err}
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"network: {e.reason}"}


def save_token(token: str) -> dict:
    """Verify and persist a token. Returns dict with ok + user info."""
    if not token:
        return {"ok": False, "error": "Empty token."}

    info = me(token)
    if not info.get("ok"):
        return {"ok": False, "error": f"Asana rejected the token: {info.get('error', 'unknown')}"}

    TOKENS_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        os.chmod(TOKENS_DIR, 0o700)
    except OSError:
        pass

    workspaces = info.get("workspaces", [])
    payload = {
        "access_token": token,
        "user_gid": info.get("gid"),
        "user_name": info.get("name"),
        "user_email": info.get("email"),
        "workspaces": [
            {"gid": w.get("gid"), "name": w.get("name")} for w in workspaces
        ],
        "saved_at": int(time.time()),
    }
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(payload, f, indent=2)

    return {
        "ok": True,
        "user_name": info.get("name"),
        "user_email": info.get("email"),
        "user_gid": info.get("gid"),
        "workspaces": payload["workspaces"],
    }


def revoke_token() -> bool:
    """Remove the local token file."""
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
        return True
    return False
