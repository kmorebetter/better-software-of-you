"""Google OAuth2 for Software of You MCP server.

Ported from shared/google_auth.py. Handles the full OAuth flow using
only stdlib — no pip install required beyond the MCP SDK.
"""

import base64
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from software_of_you.db import DATA_DIR

TOKEN_FILE = DATA_DIR / "google_token.json"

# Embedded OAuth credentials (Desktop app — not secret per Google's design)
DEFAULT_CREDENTIALS = {
    "client_id": "50587301029-pb96imk0vvadpg8n5oa2q8ac1lfk5f9o.apps.googleusercontent.com",
    "client_secret": "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",
}

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/userinfo.email",
]

REDIRECT_PORTS = [8089, 8090, 8091, 8092]
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"


def load_token() -> dict | None:
    if not TOKEN_FILE.exists():
        return None
    return json.loads(TOKEN_FILE.read_text())


def save_token(token_data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    token_data["saved_at"] = int(time.time())
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))


def is_token_expired(token_data: dict) -> bool:
    if not token_data:
        return True
    saved_at = token_data.get("saved_at", 0)
    expires_in = token_data.get("expires_in", 3600)
    return time.time() > (saved_at + expires_in - 60)


def refresh_access_token(token_data: dict) -> dict | None:
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        return None

    params = urllib.parse.urlencode({
        "client_id": DEFAULT_CREDENTIALS["client_id"],
        "client_secret": DEFAULT_CREDENTIALS["client_secret"],
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()

    try:
        req = urllib.request.Request(TOKEN_ENDPOINT, data=params)
        with urllib.request.urlopen(req, timeout=10) as resp:
            new_data = json.loads(resp.read().decode())
        new_data["refresh_token"] = refresh_token
        save_token(new_data)
        return new_data
    except urllib.error.URLError as e:
        print(f"Token refresh failed: {e}", file=sys.stderr)
        return None


def get_valid_token() -> str | None:
    """Get a valid access token, refreshing if needed."""
    token_data = load_token()
    if not token_data:
        return None

    if is_token_expired(token_data):
        token_data = refresh_access_token(token_data)

    if token_data:
        return token_data.get("access_token")
    return None


class _OAuthHandler(BaseHTTPRequestHandler):
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
            <h1 style="font-size:1.5rem;font-weight:600">Connected!</h1>
            <p style="color:#71717a">You can close this tab and return to Claude.</p>
            </div></body></html>""")
        elif "error" in params:
            _OAuthHandler.error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body>Auth failed: {params['error'][0]}</body></html>".encode())

    def log_message(self, format, *args):
        pass


def run_auth_flow(scopes=None) -> dict:
    """Run the full OAuth flow. Opens browser, returns result dict."""
    scopes = scopes or DEFAULT_SCOPES

    # PKCE
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

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
        "client_id": DEFAULT_CREDENTIALS["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(auth_params)}"

    webbrowser.open(auth_url)

    _OAuthHandler.auth_code = None
    _OAuthHandler.error = None

    while _OAuthHandler.auth_code is None and _OAuthHandler.error is None:
        server.handle_request()

    server.server_close()

    if _OAuthHandler.error:
        raise RuntimeError(f"Authorization failed: {_OAuthHandler.error}")

    # Exchange code for tokens
    token_params = urllib.parse.urlencode({
        "client_id": DEFAULT_CREDENTIALS["client_id"],
        "client_secret": DEFAULT_CREDENTIALS["client_secret"],
        "code": _OAuthHandler.auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }).encode()

    req = urllib.request.Request(TOKEN_ENDPOINT, data=token_params)
    with urllib.request.urlopen(req, timeout=10) as resp:
        token_data = json.loads(resp.read().decode())

    save_token(token_data)
    return {"success": True, "message": "Google account connected successfully."}


def revoke_token() -> None:
    """Revoke the current token and delete the file."""
    token_data = load_token()
    if not token_data:
        return

    token = token_data.get("access_token", token_data.get("refresh_token"))
    params = urllib.parse.urlencode({"token": token}).encode()

    try:
        req = urllib.request.Request(REVOKE_ENDPOINT, data=params)
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.URLError:
        pass

    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
