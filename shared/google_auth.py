#!/usr/bin/env python3
"""Google OAuth2 helper for Software of You.

Handles the full OAuth flow for Google APIs (Gmail, Calendar, etc.)
using the "Desktop app" OAuth type. No pip install required — uses
only Python standard library + urllib for token exchange.

Usage:
    # Start auth flow (opens browser, saves token)
    python3 google_auth.py auth --scopes gmail.readonly,gmail.send,calendar.readonly,calendar.events

    # Get a valid access token (refreshes if expired)
    python3 google_auth.py token

    # Check if authenticated
    python3 google_auth.py status

    # Revoke access
    python3 google_auth.py revoke
"""

import os
import sys
import json
import time
import hashlib
import base64
import secrets
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
TOKEN_FILE = os.path.join(USER_DATA_DIR, "google_token.json")

# Fall back to config/ if token exists there (pre-migration)
_LEGACY_TOKEN = os.path.join(CONFIG_DIR, "google_token.json")
if os.path.exists(_LEGACY_TOKEN) and not os.path.islink(_LEGACY_TOKEN) and not os.path.exists(TOKEN_FILE):
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    os.rename(_LEGACY_TOKEN, TOKEN_FILE)

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


def load_credentials():
    """Load OAuth client credentials. Config file overrides embedded defaults."""
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            data = json.load(f)
        if "installed" in data:
            data = data["installed"]
        if "client_id" in data:
            # Merge with defaults to fill in any missing fields (e.g. client_secret)
            merged = dict(DEFAULT_CREDENTIALS)
            merged.update(data)
            return merged
    return dict(DEFAULT_CREDENTIALS)


def load_token():
    """Load saved token from disk."""
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)


def save_token(token_data):
    """Save token to disk."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    token_data["saved_at"] = int(time.time())
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)


def is_token_expired(token_data):
    """Check if the access token has expired."""
    if not token_data:
        return True
    saved_at = token_data.get("saved_at", 0)
    expires_in = token_data.get("expires_in", 3600)
    # Add 60-second buffer
    return time.time() > (saved_at + expires_in - 60)


def refresh_access_token(token_data, credentials):
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
        save_token(new_data)
        return new_data
    except urllib.error.URLError as e:
        print(json.dumps({"error": f"Token refresh failed: {e}"}))
        return None


def get_valid_token():
    """Get a valid access token, refreshing if needed."""
    credentials = load_credentials()
    if not credentials:
        return None

    token_data = load_token()
    if not token_data:
        return None

    if is_token_expired(token_data):
        token_data = refresh_access_token(token_data, credentials)

    if token_data:
        return token_data.get("access_token")
    return None


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
    """Run the full OAuth authorization flow."""
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
        save_token(token_data)
        print(json.dumps({
            "success": True,
            "message": "Google account connected successfully.",
            "scopes": scopes,
        }))
    except urllib.error.URLError as e:
        print(json.dumps({"error": f"Token exchange failed: {e}"}))
        sys.exit(1)


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

    print(json.dumps(status))


def revoke_token():
    """Revoke the current access token."""
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

    # Remove local token file
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)

    print(json.dumps({"message": "Google access revoked. Token removed."}))


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: google_auth.py [auth|token|status|revoke]"}))
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
        token = get_valid_token()
        if token:
            print(token)
        else:
            print(json.dumps({"error": "Not authenticated. Run /google-setup first."}))
            sys.exit(1)

    elif command == "status":
        check_status()

    elif command == "revoke":
        revoke_token()

    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
