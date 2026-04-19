#!/usr/bin/env python3
"""Monday morning meeting brief helper for Benji's.

Usage:
    python3 monday_brief.py fetch-gmail          # Fetch kerry@benjis.com inbox (past 7 days)
    python3 monday_brief.py send-email           # Send compiled agenda email
        --subject "..." \
        --body "..." \
        --to "jp@benjis.com,..."
"""

import base64
import email.mime.multipart
import email.mime.text
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ACCOUNT = "kerry@benjis.com"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"

RECIPIENTS = [
    "jp@benjis.com",
    "emma@benjis.com",
    "marissa@benjis.com",
    "ops@benjis.com",
    "ximena@benjis.com",
]


def _get_token():
    import os
    import subprocess
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    result = subprocess.run(
        [sys.executable, f"{plugin_root}/shared/google_auth.py", "token", ACCOUNT],
        capture_output=True, text=True,
    )
    token = result.stdout.strip()
    if not token or token.startswith("{"):
        print(json.dumps({"error": f"No valid token for {ACCOUNT}. Run /google-setup."}))
        sys.exit(1)
    return token


def _api_get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _api_post(url, token, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def fetch_gmail():
    token = _get_token()

    q = urllib.parse.quote("newer_than:7d in:inbox")
    url = f"{GMAIL_API}/messages?maxResults=50&q={q}"
    data = _api_get(url, token)
    messages = data.get("messages", [])

    results = []
    for msg_ref in messages:
        msg_id = msg_ref["id"]
        try:
            msg = _api_get(
                f"{GMAIL_API}/messages/{msg_id}?format=metadata"
                "&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Subject&metadataHeaders=Date",
                token,
            )
        except Exception:
            continue

        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        from_addr = headers.get("from", "")
        from_name = from_addr
        from_email = from_addr
        if "<" in from_addr:
            parts = from_addr.split("<")
            from_name = parts[0].strip().strip('"')
            from_email = parts[1].rstrip(">").strip()

        # Skip emails sent by Kerry (outbound)
        if from_email.lower() == ACCOUNT.lower():
            continue

        results.append({
            "id": msg_id,
            "thread_id": msg.get("threadId", ""),
            "from_name": from_name,
            "from_email": from_email,
            "to": headers.get("to", ""),
            "subject": headers.get("subject", "(no subject)"),
            "date": headers.get("date", ""),
            "snippet": msg.get("snippet", ""),
            "labels": msg.get("labelIds", []),
        })

    print(json.dumps({"emails": results, "count": len(results)}))


def _build_raw_message(subject, body, to_addresses):
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["From"] = ACCOUNT
    msg["To"] = ", ".join(to_addresses)
    msg["Subject"] = subject
    msg.attach(email.mime.text.MIMEText(body, "html", "utf-8"))
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def send_email(subject, body, to_addresses):
    token = _get_token()
    raw = _build_raw_message(subject, body, to_addresses)
    result = _api_post(f"{GMAIL_API}/messages/send", token, {"raw": raw})
    if "id" in result:
        print(json.dumps({"success": True, "message_id": result["id"]}))
    else:
        print(json.dumps({"error": "Send failed", "response": result}))
        sys.exit(1)


def create_draft(subject, body, to_addresses):
    token = _get_token()
    raw = _build_raw_message(subject, body, to_addresses)
    result = _api_post(f"{GMAIL_API}/drafts", token, {"message": {"raw": raw}})
    if "id" in result:
        print(json.dumps({"success": True, "draft_id": result["id"]}))
    else:
        print(json.dumps({"error": "Draft creation failed", "response": result}))
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "fetch-gmail":
        fetch_gmail()

    elif cmd == "create-draft":
        args = sys.argv[2:]
        subject, body, to_addresses = "", "", RECIPIENTS
        i = 0
        while i < len(args):
            if args[i] == "--subject" and i + 1 < len(args):
                subject = args[i + 1]; i += 2
            elif args[i] == "--body" and i + 1 < len(args):
                body = args[i + 1]; i += 2
            elif args[i] == "--to" and i + 1 < len(args):
                to_addresses = [a.strip() for a in args[i + 1].split(",")]; i += 2
            else:
                i += 1
        if not subject or not body:
            print(json.dumps({"error": "--subject and --body are required"}))
            sys.exit(1)
        create_draft(subject, body, to_addresses)

    elif cmd == "send-email":
        args = sys.argv[2:]
        subject = ""
        body = ""
        to_addresses = RECIPIENTS

        i = 0
        while i < len(args):
            if args[i] == "--subject" and i + 1 < len(args):
                subject = args[i + 1]; i += 2
            elif args[i] == "--body" and i + 1 < len(args):
                body = args[i + 1]; i += 2
            elif args[i] == "--to" and i + 1 < len(args):
                to_addresses = [a.strip() for a in args[i + 1].split(",")]; i += 2
            else:
                i += 1

        if not subject or not body:
            print(json.dumps({"error": "--subject and --body are required"}))
            sys.exit(1)

        send_email(subject, body, to_addresses)

    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
