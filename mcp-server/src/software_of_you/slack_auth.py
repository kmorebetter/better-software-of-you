"""Slack OAuth for Software of You MCP server.

Handles the full Slack OAuth flow using only stdlib — no pip install
required beyond the MCP SDK. Pattern mirrors google_auth.py.

Credentials are provided via environment variables:
  SOY_SLACK_CLIENT_ID
  SOY_SLACK_CLIENT_SECRET
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from software_of_you.db import DATA_DIR

TOKEN_PATH = DATA_DIR / "slack_token.json"

SLACK_SCOPES = "channels:history,channels:read,users:read,users:read.email"

REDIRECT_PORTS = [8093, 8094, 8095, 8096]

SLACK_AUTH_ENDPOINT = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_ENDPOINT = "https://slack.com/api/oauth.v2.access"
SLACK_REVOKE_ENDPOINT = "https://slack.com/api/auth.revoke"


def _get_credentials() -> dict | None:
    """Read Slack OAuth credentials from environment variables."""
    client_id = os.environ.get("SOY_SLACK_CLIENT_ID")
    client_secret = os.environ.get("SOY_SLACK_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    return {"client_id": client_id, "client_secret": client_secret}


def load_token() -> dict | None:
    """Load saved Slack token from disk."""
    if not TOKEN_PATH.exists():
        return None
    try:
        return json.loads(TOKEN_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_token(token_data: dict) -> None:
    """Save Slack token to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    token_data["saved_at"] = int(time.time())
    TOKEN_PATH.write_text(json.dumps(token_data, indent=2))
    # Token file holds the Slack bot secret — restrict to owner-only read/write.
    os.chmod(TOKEN_PATH, 0o600)


def get_bot_token() -> str | None:
    """Get the Slack bot access token, or None if not connected."""
    token_data = load_token()
    if not token_data:
        return None
    return token_data.get("access_token")


def is_connected() -> bool:
    """Check if Slack is connected (token file exists and has access_token)."""
    token_data = load_token()
    return bool(token_data and token_data.get("access_token"))


# ── OAuth Flow ───────────────────────────────────────────────────────────


class _OAuthHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth redirect code."""

    auth_code = None
    error = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            _OAuthHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""<html><body style="font-family:Inter,system-ui,sans-serif;
            display:flex;justify-content:center;align-items:center;height:100vh;margin:0;
            background:#fafafa;color:#18181b"><div style="text-align:center">
            <h1 style="font-size:1.5rem;font-weight:600">Slack Connected!</h1>
            <p style="color:#71717a">You can close this tab and return to Claude.</p>
            </div></body></html>""")
        elif "error" in params:
            _OAuthHandler.error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            import html
            safe_error = html.escape(params["error"][0])
            self.wfile.write(
                f"<html><body>Slack auth failed: {safe_error}</body></html>".encode()
            )

    def log_message(self, format, *args):
        """Suppress default HTTP server logging."""
        pass


def run_auth_flow() -> dict:
    """Run the full Slack OAuth flow.

    Opens browser for authorization, captures the redirect code,
    exchanges it for a bot token, and saves to disk.

    Returns a result dict with success status and team info.
    """
    creds = _get_credentials()
    if not creds:
        return {
            "success": False,
            "error": "Slack credentials not configured. Set SOY_SLACK_CLIENT_ID and SOY_SLACK_CLIENT_SECRET environment variables.",
        }

    # Find available port
    server = None
    port = None
    for p in REDIRECT_PORTS:
        try:
            server = HTTPServer(("localhost", p), _OAuthHandler)
            port = p
            break
        except OSError:
            continue

    if server is None:
        raise RuntimeError(f"Could not bind to any port in {REDIRECT_PORTS}")

    redirect_uri = f"http://localhost:{port}"
    server.timeout = 120

    auth_params = {
        "client_id": creds["client_id"],
        "scope": SLACK_SCOPES,
        "redirect_uri": redirect_uri,
    }
    auth_url = f"{SLACK_AUTH_ENDPOINT}?{urllib.parse.urlencode(auth_params)}"

    webbrowser.open(auth_url)

    _OAuthHandler.auth_code = None
    _OAuthHandler.error = None

    while _OAuthHandler.auth_code is None and _OAuthHandler.error is None:
        server.handle_request()

    server.server_close()

    if _OAuthHandler.error:
        raise RuntimeError(f"Slack authorization failed: {_OAuthHandler.error}")

    # Exchange code for token
    token_params = urllib.parse.urlencode({
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "code": _OAuthHandler.auth_code,
        "redirect_uri": redirect_uri,
    }).encode()

    req = urllib.request.Request(SLACK_TOKEN_ENDPOINT, data=token_params)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    if not data.get("ok"):
        error_msg = data.get("error", "unknown error")
        return {"success": False, "error": f"Slack token exchange failed: {error_msg}"}

    # Extract token data
    token_data = {
        "access_token": data.get("access_token"),
        "token_type": data.get("token_type", "bot"),
        "scope": data.get("scope", ""),
        "team_id": data.get("team", {}).get("id", ""),
        "team_name": data.get("team", {}).get("name", ""),
        "bot_user_id": data.get("bot_user_id", ""),
    }

    save_token(token_data)

    return {
        "success": True,
        "message": f"Connected to Slack workspace: {token_data['team_name']}.",
        "team_id": token_data["team_id"],
        "team_name": token_data["team_name"],
    }


def revoke_token() -> bool:
    """Revoke the Slack token and remove the local file.

    Returns True if successfully revoked or file removed.
    """
    token_data = load_token()
    if not token_data:
        return False

    access_token = token_data.get("access_token")
    if access_token:
        try:
            req = urllib.request.Request(
                SLACK_REVOKE_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
                data=b"",
            )
            urllib.request.urlopen(req, timeout=10)
        except urllib.error.URLError:
            pass

    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()

    return True
