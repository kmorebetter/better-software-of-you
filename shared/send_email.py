#!/usr/bin/env python3
"""send_email.py — send a plain-text/HTML email via the Gmail API.

Used by the morning-brief loop to push the daily brief to the user's own inbox.
Pure stdlib: reuses the existing OAuth in shared/google_auth.py (the gmail.send
scope is already provisioned) and posts the raw message with urllib. No new
credentials, no external packages, no venv required.

Usage:
    # Body on stdin (recommended for multi-line markdown):
    echo "body" | python3 shared/send_email.py --subject "Morning Brief" [--to you@x.com]

    # Or as an argument:
    python3 shared/send_email.py --subject "..." --body "..." [--to ...] [--account ...]

Exit code is always 0 (never break the scheduled pipeline); result is printed as JSON.
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from email.mime.text import MIMEText
from email.utils import formataddr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google_auth import get_valid_token, list_accounts  # noqa: E402

GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def _default_recipient(account):
    """Send to self by default: the sending account's own address."""
    if account:
        return account
    try:
        accounts = list_accounts()
        active = [a for a in accounts if a.get("status") == "active"]
        primary = sorted(active, key=lambda a: (not a.get("is_primary"), a.get("id")))
        if primary:
            return primary[0]["email"]
    except Exception:
        pass
    return None


def send(subject, body, to=None, account=None, html=False):
    token = get_valid_token(email=account)
    if not token:
        return {"status": "error", "reason": "No valid Google token (run /google-setup)"}

    recipient = to or _default_recipient(account)
    if not recipient:
        return {"status": "error", "reason": "No recipient and no account to infer one"}

    msg = MIMEText(body, "html" if html else "plain", "utf-8")
    msg["To"] = recipient
    msg["From"] = formataddr(("Software of You", recipient))
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    req = urllib.request.Request(
        GMAIL_SEND_URL,
        data=json.dumps({"raw": raw}).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return {"status": "sent", "id": payload.get("id"), "to": recipient}
    except urllib.error.HTTPError as e:
        return {"status": "error", "reason": f"HTTP {e.code}: {e.read().decode('utf-8')[:300]}"}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def main():
    p = argparse.ArgumentParser(description="Send an email via Gmail API")
    p.add_argument("--subject", required=True)
    p.add_argument("--body", help="Body text; if omitted, read from stdin")
    p.add_argument("--to", help="Recipient; defaults to the sending account (send-to-self)")
    p.add_argument("--account", help="Sending Google account email; defaults to primary")
    p.add_argument("--html", action="store_true", help="Treat body as HTML")
    args = p.parse_args()

    body = args.body if args.body is not None else sys.stdin.read()
    result = send(args.subject, body, to=args.to, account=args.account, html=args.html)
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
