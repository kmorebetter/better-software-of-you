#!/usr/bin/env python3
"""Google OAuth2 helper for Software of You.

Handles the full OAuth flow for Google APIs (Gmail, Calendar, etc.)
using the "Desktop app" OAuth type. No pip install required — uses
only Python standard library + urllib for token exchange.

Supports multiple Google accounts. Tokens are stored per-account in
the tokens/ directory. Legacy single-token files are auto-migrated.

Usage:
    # Start auth flow (opens browser, saves token)
    python3 google_auth.py auth --scopes gmail.readonly,gmail.send,calendar.readonly,calendar.events

    # Get a valid access token (refreshes if expired)
    python3 google_auth.py token [email]

    # List connected accounts
    python3 google_auth.py accounts

    # Check if authenticated (legacy compat)
    python3 google_auth.py status

    # Revoke access
    python3 google_auth.py revoke [email]
"""

import os
import sys
import json
import time
import hashlib
import base64
import secrets
import sqlite3
import webbrowser
import urllib.request
import urllib.parse
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
CONFIG_DIR = os.path.join(PLUGIN_ROOT, "config")
CREDENTIALS_FILE = os.path.join(CONFIG_DIR, "google_credentials.json")

# Token lives in user data directory (survives repo re-downloads)
DATA_HOME = os.environ.get(
    "XDG_DATA_HOME",
    os.path.join(os.path.expanduser("~"), ".local", "share"),
)
USER_DATA_DIR = os.path.join(DATA_HOME, "software-of-you")
TOKENS_DIR = os.path.join(USER_DATA_DIR, "tokens")
LEGACY_TOKEN_FILE = os.path.join(USER_DATA_DIR, "google_token.json")
DB_PATH = os.path.join(PLUGIN_ROOT, "data", "soy.db")

# Backward compat alias
TOKEN_FILE = LEGACY_TOKEN_FILE

# Fall back to config/ if token exists there (pre-migration)
_LEGACY_TOKEN = os.path.join(CONFIG_DIR, "google_token.json")
if os.path.exists(_LEGACY_TOKEN) and not os.path.islink(_LEGACY_TOKEN) and not os.path.exists(LEGACY_TOKEN_FILE):
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    os.rename(_LEGACY_TOKEN, LEGACY_TOKEN_FILE)

# Embedded OAuth credentials (Desktop app type — obfuscated to stay out of scrapers)
_K = b"software-of-you"
def _d(e):
    raw = base64.b64decode(e)
    return bytes([c ^ _K[i % len(_K)] for i, c in enumerate(raw)]).decode()

DEFAULT_CREDENTIALS = {
    "client_id": _d("Rl9TTEBSQlQdXV8ACQ1MRQYLH0cXBARJHwEVF1oaEl0XTBYCQwlLBFNLQABbEh8WB1kGHQpKAwNYCgoHEAAIABIPBktOAAs="),
    "client_secret": _d("NCAlJyc5Xz9iQidoHS0CRxcpIRw2MC19KiMbGl4mJTAeBiU="),
}

# Default scopes for Software of You
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]

REDIRECT_PORT = 8089
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}"
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"


# ── Helpers ──────────────────────────────────────────────────────────────


def _email_to_filename(email):
    """Convert email to token filename: foo@bar.com → foo_bar.com.json

    Strips path separators for defense-in-depth (email comes from Google API,
    but we sanitize anyway).
    """
    safe = email.replace("@", "_").replace("/", "_").replace("\\", "_").replace("..", "_")
    return safe + ".json"


def _token_path_for(email):
    """Full path to an account's token file."""
    return os.path.join(TOKENS_DIR, _email_to_filename(email))


def derive_label(email):
    """Extract display label from email: kmo@betterstory.co → betterstory.co"""
    return email.split("@")[1] if "@" in email else email


def _get_db():
    """Get a SQLite connection to the shared database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _get_user_email(access_token):
    """Fetch email from Google userinfo API."""
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


# ── Credentials ──────────────────────────────────────────────────────────


def load_credentials():
    """Load OAuth client credentials. Config file overrides embedded defaults."""
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            data = json.load(f)
        if "installed" in data:
            data = data["installed"]
        if "client_id" in data:
            merged = dict(DEFAULT_CREDENTIALS)
            merged.update(data)
            return merged
    return dict(DEFAULT_CREDENTIALS)


# ── Token Management (per-account aware) ─────────────────────────────────


def load_token(email=None):
    """Load saved token from disk. If email given, load from tokens/ dir."""
    if email:
        path = _token_path_for(email)
    else:
        path = LEGACY_TOKEN_FILE
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def save_token(token_data, email=None):
    """Save token to disk. If email given, save to tokens/ dir."""
    if email:
        os.makedirs(TOKENS_DIR, exist_ok=True)
        path = _token_path_for(email)
    else:
        os.makedirs(os.path.dirname(LEGACY_TOKEN_FILE), exist_ok=True)
        path = LEGACY_TOKEN_FILE
    token_data["saved_at"] = int(time.time())
    with open(path, "w") as f:
        json.dump(token_data, f, indent=2)


def is_token_expired(token_data):
    """Check if the access token has expired."""
    if not token_data:
        return True
    saved_at = token_data.get("saved_at", 0)
    expires_in = token_data.get("expires_in", 3600)
    # Add 60-second buffer
    return time.time() > (saved_at + expires_in - 60)


def refresh_access_token(token_data, credentials, email=None):
    """Use refresh token to get a new access token."""
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        return None

    params = urllib.parse.urlencode({
        "client_id": credentials["client_id"],
        "client_secret": credentials["client_secret"],
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()

    try:
        req = urllib.request.Request(TOKEN_ENDPOINT, data=params)
        with urllib.request.urlopen(req, timeout=10) as resp:
            new_data = json.loads(resp.read().decode())
        # Preserve the refresh token (not always returned on refresh)
        new_data["refresh_token"] = refresh_token
        save_token(new_data, email=email)
        return new_data
    except urllib.error.URLError as e:
        print(json.dumps({"error": f"Token refresh failed: {e}"}), file=sys.stderr)
        return None


def get_valid_token(email=None):
    """Get a valid access token, refreshing if needed.

    Resolution order:
    1. If email specified, use that account's token
    2. Check google_accounts table — prefer primary, then any active
    3. Fall back to legacy single token file
    """
    credentials = load_credentials()
    if not credentials:
        return None

    # If specific email requested, go directly to that account
    if email:
        token_data = load_token(email=email)
        if not token_data:
            return None
        if is_token_expired(token_data):
            token_data = refresh_access_token(token_data, credentials, email=email)
        return token_data.get("access_token") if token_data else None

    # Try active accounts from DB (primary first)
    accounts = list_accounts()
    if accounts:
        # Filter to active, then sort primary first
        sorted_accounts = sorted(
            [a for a in accounts if a["status"] == "active"],
            key=lambda a: (not a["is_primary"], a["id"]),
        )
        for acct in sorted_accounts:
            acct_email = acct["email"]
            token_data = load_token(email=acct_email)
            if token_data:
                if is_token_expired(token_data):
                    token_data = refresh_access_token(token_data, credentials, email=acct_email)
                if token_data:
                    return token_data.get("access_token")

    # Fall back to legacy token
    token_data = load_token()
    if not token_data:
        return None
    if is_token_expired(token_data):
        token_data = refresh_access_token(token_data, credentials)
    if token_data:
        return token_data.get("access_token")
    return None


# ── Account Management ───────────────────────────────────────────────────


def list_accounts():
    """Query google_accounts table. Returns list of dicts."""
    if not os.path.exists(DB_PATH):
        return []
    try:
        conn = _get_db()
        rows = conn.execute(
            "SELECT id, email, label, display_name, token_file, is_primary, connected_at, last_synced_at, status "
            "FROM google_accounts ORDER BY is_primary DESC, connected_at ASC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def register_account(email, display_name, token_file):
    """Register or update an account in the google_accounts table.

    The first account registered is automatically set as primary.
    """
    conn = _get_db()
    label = derive_label(email)

    # Check if this is the first account
    existing = conn.execute("SELECT COUNT(*) FROM google_accounts").fetchone()[0]
    is_primary = 1 if existing == 0 else 0

    conn.execute(
        """INSERT INTO google_accounts (email, label, display_name, token_file, is_primary)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(email) DO UPDATE SET
             display_name = excluded.display_name,
             token_file = excluded.token_file,
             status = 'active'""",
        (email, label, display_name, token_file, is_primary),
    )
    conn.commit()
    conn.close()
    return {"email": email, "label": label, "is_primary": bool(is_primary)}


def migrate_legacy_token():
    """Detect old google_token.json, migrate to per-account token, register in DB.

    Returns the migrated account email or None.
    """
    if not os.path.exists(LEGACY_TOKEN_FILE):
        return None

    # Already have accounts? Check if legacy is already migrated
    accounts = list_accounts()
    if accounts:
        # Check if any account's token file matches legacy
        for acct in accounts:
            if os.path.exists(_token_path_for(acct["email"])):
                # Already migrated — clean up legacy if it exists
                if os.path.exists(LEGACY_TOKEN_FILE):
                    os.remove(LEGACY_TOKEN_FILE)
                return acct["email"]
        # Accounts exist but legacy file doesn't match any — migrate it

    # Load the legacy token and get the email
    token_data = load_token()
    if not token_data:
        return None

    credentials = load_credentials()
    if is_token_expired(token_data):
        token_data = refresh_access_token(token_data, credentials)
    if not token_data:
        return None

    access_token = token_data.get("access_token")
    if not access_token:
        return None

    email, display_name = _get_user_email(access_token)
    if not email:
        return None

    # Move token to per-account path
    os.makedirs(TOKENS_DIR, exist_ok=True)
    token_file = _email_to_filename(email)
    save_token(token_data, email=email)

    # Register in DB
    register_account(email, display_name, token_file)

    # Backfill account_id on existing emails and calendar_events
    try:
        conn = _get_db()
        acct_row = conn.execute(
            "SELECT id FROM google_accounts WHERE email = ?", (email,)
        ).fetchone()
        if acct_row:
            account_id = acct_row["id"]
            conn.execute(
                "UPDATE emails SET account_id = ? WHERE account_id IS NULL",
                (account_id,),
            )
            conn.execute(
                "UPDATE calendar_events SET account_id = ? WHERE account_id IS NULL",
                (account_id,),
            )
            conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        pass

    # Remove legacy file
    if os.path.exists(LEGACY_TOKEN_FILE):
        os.remove(LEGACY_TOKEN_FILE)

    return email


# ── OAuth Flow ───────────────────────────────────────────────────────────


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle the OAuth redirect callback."""

    auth_code = None
    error = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html><body style="font-family: Inter, system-ui, sans-serif; display: flex;
            justify-content: center; align-items: center; height: 100vh; margin: 0;
            background: #fafafa; color: #18181b;">
            <div style="text-align: center;">
            <h1 style="font-size: 1.5rem; font-weight: 600;">Connected!</h1>
            <p style="color: #71717a;">You can close this tab and return to Claude Code.</p>
            </div></body></html>
            """)
        elif "error" in params:
            OAuthCallbackHandler.error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body>Auth failed: {params['error'][0]}</body></html>".encode())

    def log_message(self, format, *args):
        pass  # Suppress server logs


def run_auth_flow(scopes=None):
    """Run the full OAuth authorization flow.

    After getting the token, auto-detects the account email,
    saves to per-account path, and registers in the DB.
    """
    credentials = load_credentials()

    if scopes is None:
        scopes = DEFAULT_SCOPES

    # Generate PKCE code verifier and challenge
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    # Build authorization URL
    auth_params = {
        "client_id": credentials["client_id"],
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(auth_params)}"

    # Start local server to catch the redirect
    server = HTTPServer(("localhost", REDIRECT_PORT), OAuthCallbackHandler)
    server.timeout = 120  # 2-minute timeout

    # Open browser
    webbrowser.open(auth_url)

    # Wait for the callback
    OAuthCallbackHandler.auth_code = None
    OAuthCallbackHandler.error = None

    while OAuthCallbackHandler.auth_code is None and OAuthCallbackHandler.error is None:
        server.handle_request()

    server.server_close()

    if OAuthCallbackHandler.error:
        print(json.dumps({"error": f"Authorization failed: {OAuthCallbackHandler.error}"}))
        sys.exit(1)

    # Exchange auth code for tokens
    token_params = urllib.parse.urlencode({
        "client_id": credentials["client_id"],
        "client_secret": credentials["client_secret"],
        "code": OAuthCallbackHandler.auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }).encode()

    try:
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
            label = acct_info["label"]
            is_primary = acct_info["is_primary"]

            print(json.dumps({
                "success": True,
                "message": f"Connected as {email}. Label: {label}.",
                "email": email,
                "label": label,
                "is_primary": is_primary,
                "scopes": scopes,
            }))
        else:
            # Fallback: save to legacy path
            save_token(token_data)
            print(json.dumps({
                "success": True,
                "message": "Google account connected successfully.",
                "scopes": scopes,
            }))
    except urllib.error.URLError as e:
        print(json.dumps({"error": f"Token exchange failed: {e}"}))
        sys.exit(1)


# ── CLI Commands ─────────────────────────────────────────────────────────


def check_status():
    """Check current authentication status."""
    credentials = load_credentials()
    token_data = load_token()

    status = {
        "credentials_configured": credentials is not None,
        "authenticated": False,
        "token_expired": True,
        "email": None,
    }

    if token_data:
        status["authenticated"] = True
        status["token_expired"] = is_token_expired(token_data)

        # Try to get user email
        access_token = get_valid_token()
        if access_token:
            try:
                req = urllib.request.Request(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    info = json.loads(resp.read().decode())
                    status["email"] = info.get("email")
                    status["token_expired"] = False
            except urllib.error.URLError:
                pass
    else:
        # Check if accounts are registered (may have migrated away from legacy)
        accounts = list_accounts()
        if accounts:
            primary = next((a for a in accounts if a["is_primary"] and a["status"] == "active"), None)
            acct = primary or accounts[0]
            status["authenticated"] = True
            status["email"] = acct["email"]
            # Validate the token is actually usable
            token = get_valid_token(email=acct["email"])
            status["token_expired"] = token is None

    print(json.dumps(status))


def cmd_accounts():
    """List connected Google accounts."""
    # Auto-migrate legacy token if present
    migrate_legacy_token()

    accounts = list_accounts()
    print(json.dumps({
        "accounts": accounts,
        "count": len(accounts),
    }))


def revoke_token(email=None):
    """Revoke access for a specific account or the legacy token."""
    if email:
        token_data = load_token(email=email)
    else:
        token_data = load_token()

    if not token_data:
        print(json.dumps({"message": "No token to revoke."}))
        return

    token = token_data.get("access_token", token_data.get("refresh_token"))
    params = urllib.parse.urlencode({"token": token}).encode()

    try:
        req = urllib.request.Request(REVOKE_ENDPOINT, data=params)
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.URLError:
        pass  # Revocation is best-effort

    # Remove token file
    if email:
        path = _token_path_for(email)
        if os.path.exists(path):
            os.remove(path)
        # Mark as disconnected in DB
        try:
            conn = _get_db()
            conn.execute(
                "UPDATE google_accounts SET status = 'disconnected' WHERE email = ?",
                (email,),
            )
            conn.commit()
            conn.close()
        except sqlite3.OperationalError:
            pass
        print(json.dumps({"message": f"Revoked access for {email}."}))
    else:
        if os.path.exists(LEGACY_TOKEN_FILE):
            os.remove(LEGACY_TOKEN_FILE)
        print(json.dumps({"message": "Google access revoked. Token removed."}))


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: google_auth.py [auth|token|status|revoke|accounts]"}))
        sys.exit(1)

    command = sys.argv[1]

    if command == "auth":
        scopes = None
        if len(sys.argv) > 3 and sys.argv[2] == "--scopes":
            scope_names = sys.argv[3].split(",")
            scopes = [
                f"https://www.googleapis.com/auth/{s}" if not s.startswith("https://") else s
                for s in scope_names
            ]
        run_auth_flow(scopes)

    elif command == "token":
        email = sys.argv[2] if len(sys.argv) > 2 else None
        token = get_valid_token(email=email)
        if token:
            print(token)
        else:
            print(json.dumps({"error": "Not authenticated. Run /google-setup first."}))
            sys.exit(1)

    elif command == "status":
        check_status()

    elif command == "accounts":
        cmd_accounts()

    elif command == "revoke":
        email = sys.argv[2] if len(sys.argv) > 2 else None
        revoke_token(email=email)

    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
