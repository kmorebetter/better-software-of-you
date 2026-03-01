"""Google OAuth2 for Software of You MCP server.

Ported from shared/google_auth.py. Handles the full OAuth flow using
only stdlib — no pip install required beyond the MCP SDK.

Supports multiple Google accounts. Tokens are stored per-account in
the tokens/ directory. Legacy single-token files are auto-migrated.
"""

import base64
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from software_of_you.db import DATA_DIR, execute, execute_write, execute_many

TOKENS_DIR = DATA_DIR / "tokens"
LEGACY_TOKEN_FILE = DATA_DIR / "google_token.json"

# Backward compat alias
TOKEN_FILE = LEGACY_TOKEN_FILE

# Embedded OAuth credentials (Desktop app type — obfuscated to stay out of scrapers)
_K = b"software-of-you"
def _d(e):
    raw = base64.b64decode(e)
    return bytes([c ^ _K[i % len(_K)] for i, c in enumerate(raw)]).decode()

DEFAULT_CREDENTIALS = {
    "client_id": _d("Rl9TTEBSQlQdXV8ACQ1MRQYLH0cXBARJHwEVF1oaEl0XTBYCQwlLBFNLQABbEh8WB1kGHQpKAwNYCgoHEAAIABIPBktOAAs="),
    "client_secret": _d("NCAlJyc5Xz9iQidoHS0CRxcpIRw2MC19KiMbGl4mJTAeBiU="),
}

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]

REDIRECT_PORTS = [8089, 8090, 8091, 8092]
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"


# ── Helpers ──────────────────────────────────────────────────────────────


def _email_to_filename(email: str) -> str:
    """Convert email to token filename: foo@bar.com → foo_bar.com.json

    Strips path separators for defense-in-depth (email comes from Google API,
    but we sanitize anyway).
    """
    safe = email.replace("@", "_").replace("/", "_").replace("\\", "_").replace("..", "_")
    return safe + ".json"


def _token_path_for(email: str):
    """Full path to an account's token file."""
    return TOKENS_DIR / _email_to_filename(email)


def derive_label(email: str) -> str:
    """Extract display label from email: kmo@betterstory.co → betterstory.co"""
    return email.split("@")[1] if "@" in email else email


def _get_user_email(access_token: str):
    """Fetch email and name from Google userinfo API."""
    try:
        req = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            info = json.loads(resp.read().decode())
            return info.get("email"), info.get("name")
    except urllib.error.URLError:
        return None, None


# ── Token Management (per-account aware) ─────────────────────────────────


def load_token(email: str | None = None) -> dict | None:
    """Load saved token from disk. If email given, load from tokens/ dir."""
    if email:
        path = _token_path_for(email)
    else:
        path = LEGACY_TOKEN_FILE
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_token(token_data: dict, email: str | None = None) -> None:
    """Save token to disk. If email given, save to tokens/ dir."""
    if email:
        TOKENS_DIR.mkdir(parents=True, exist_ok=True)
        path = _token_path_for(email)
    else:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = LEGACY_TOKEN_FILE
    token_data["saved_at"] = int(time.time())
    path.write_text(json.dumps(token_data, indent=2))


def is_token_expired(token_data: dict) -> bool:
    if not token_data:
        return True
    saved_at = token_data.get("saved_at", 0)
    expires_in = token_data.get("expires_in", 3600)
    return time.time() > (saved_at + expires_in - 60)


def refresh_access_token(token_data: dict, email: str | None = None) -> dict | None:
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
        save_token(new_data, email=email)
        return new_data
    except urllib.error.URLError as e:
        print(f"Token refresh failed: {e}", file=sys.stderr)
        return None


def get_valid_token(email: str | None = None) -> str | None:
    """Get a valid access token, refreshing if needed.

    Resolution order:
    1. If email specified, use that account's token
    2. Check google_accounts table — prefer primary, then any active
    3. Fall back to legacy single token file
    """
    # If specific email requested, go directly to that account
    if email:
        token_data = load_token(email=email)
        if not token_data:
            return None
        if is_token_expired(token_data):
            token_data = refresh_access_token(token_data, email=email)
        return token_data.get("access_token") if token_data else None

    # Try active accounts from DB (primary first)
    accounts = list_accounts()
    if accounts:
        sorted_accounts = sorted(
            [a for a in accounts if a["status"] == "active"],
            key=lambda a: (not a["is_primary"], a["id"]),
        )
        for acct in sorted_accounts:
            acct_email = acct["email"]
            token_data = load_token(email=acct_email)
            if token_data:
                if is_token_expired(token_data):
                    token_data = refresh_access_token(token_data, email=acct_email)
                if token_data:
                    return token_data.get("access_token")

    # Fall back to legacy token
    token_data = load_token()
    if not token_data:
        return None
    if is_token_expired(token_data):
        token_data = refresh_access_token(token_data)
    if token_data:
        return token_data.get("access_token")
    return None


# ── Account Management ───────────────────────────────────────────────────


def list_accounts() -> list[dict]:
    """Query google_accounts table. Returns list of dicts."""
    try:
        rows = execute(
            "SELECT id, email, label, display_name, token_file, is_primary, connected_at, last_synced_at, status "
            "FROM google_accounts ORDER BY is_primary DESC, connected_at ASC"
        )
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def register_account(email: str, display_name: str | None, token_file: str) -> dict:
    """Register or update an account in the google_accounts table.

    The first account registered is automatically set as primary.
    """
    label = derive_label(email)

    # Check if this is the first account
    existing = execute("SELECT COUNT(*) as cnt FROM google_accounts")
    is_primary = 1 if (not existing or existing[0]["cnt"] == 0) else 0

    execute_write(
        """INSERT INTO google_accounts (email, label, display_name, token_file, is_primary)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(email) DO UPDATE SET
             display_name = excluded.display_name,
             token_file = excluded.token_file,
             status = 'active'""",
        (email, label, display_name, token_file, is_primary),
    )
    return {"email": email, "label": label, "is_primary": bool(is_primary)}


def migrate_legacy_token() -> str | None:
    """Detect old google_token.json, migrate to per-account token, register in DB.

    Returns the migrated account email or None.
    """
    if not LEGACY_TOKEN_FILE.exists():
        return None

    # Already have accounts? Check if legacy is already migrated
    accounts = list_accounts()
    if accounts:
        for acct in accounts:
            if _token_path_for(acct["email"]).exists():
                if LEGACY_TOKEN_FILE.exists():
                    LEGACY_TOKEN_FILE.unlink()
                return acct["email"]

    # Load the legacy token and get the email
    token_data = load_token()
    if not token_data:
        return None

    if is_token_expired(token_data):
        token_data = refresh_access_token(token_data)
    if not token_data:
        return None

    access_token = token_data.get("access_token")
    if not access_token:
        return None

    email, display_name = _get_user_email(access_token)
    if not email:
        return None

    # Move token to per-account path
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    token_file = _email_to_filename(email)
    save_token(token_data, email=email)

    # Register in DB
    register_account(email, display_name, token_file)

    # Backfill account_id on existing emails and calendar_events
    try:
        acct_rows = execute(
            "SELECT id FROM google_accounts WHERE email = ?", (email,)
        )
        if acct_rows:
            account_id = acct_rows[0]["id"]
            execute_many([
                ("UPDATE emails SET account_id = ? WHERE account_id IS NULL", (account_id,)),
                ("UPDATE calendar_events SET account_id = ? WHERE account_id IS NULL", (account_id,)),
            ])
    except sqlite3.OperationalError:
        pass

    # Remove legacy file
    if LEGACY_TOKEN_FILE.exists():
        LEGACY_TOKEN_FILE.unlink()

    return email


# ── OAuth Flow ───────────────────────────────────────────────────────────


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
    """Run the full OAuth flow. Opens browser, returns result dict.

    After getting the token, auto-detects the account email,
    saves to per-account path, and registers in the DB.
    """
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

    # Auto-detect email and save per-account
    token_data["saved_at"] = int(time.time())
    access_token = token_data.get("access_token")
    email, display_name = _get_user_email(access_token) if access_token else (None, None)

    if email:
        save_token(token_data, email=email)
        token_file = _email_to_filename(email)
        acct_info = register_account(email, display_name, token_file)
        return {
            "success": True,
            "message": f"Connected as {email}. Label: {acct_info['label']}.",
            "email": email,
            "label": acct_info["label"],
            "is_primary": acct_info["is_primary"],
        }
    else:
        save_token(token_data)
        return {"success": True, "message": "Google account connected successfully."}


def revoke_token(email: str | None = None) -> None:
    """Revoke the current token and delete the file."""
    if email:
        token_data = load_token(email=email)
    else:
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

    if email:
        path = _token_path_for(email)
        if path.exists():
            path.unlink()
        # Mark disconnected in DB
        try:
            execute_write(
                "UPDATE google_accounts SET status = 'disconnected' WHERE email = ?",
                (email,),
            )
        except sqlite3.OperationalError:
            pass
    else:
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
