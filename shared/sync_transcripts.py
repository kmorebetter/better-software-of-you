#!/usr/bin/env python3
"""Sync Gemini meeting transcripts from Gmail → Google Docs → local DB.

Finds emails from gemini-notes@google.com, extracts Google Doc links,
fetches full doc content, and stores raw transcripts for later analysis.

Usage:
    python3 sync_transcripts.py scan      # Find new Gemini emails → fetch docs → store
    python3 sync_transcripts.py pending   # List unanalyzed transcripts
    python3 sync_transcripts.py get <id>  # Return raw text for a specific transcript
"""

import base64
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
DB_PATH = os.path.join(PLUGIN_ROOT, "data", "soy.db")

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
DOCS_API = "https://docs.googleapis.com/v1/documents"

GEMINI_SENDER = "gemini-notes@google.com"
DOC_LINK_RE = re.compile(r"https://docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_token():
    """Get a valid OAuth token via google_auth.py."""
    auth_script = os.path.join(PLUGIN_ROOT, "shared", "google_auth.py")
    import subprocess

    result = subprocess.run(
        [sys.executable, auth_script, "token"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    token = result.stdout.strip()
    # If it's JSON (error), it's not a valid token
    if token.startswith("{"):
        return None
    return token


def _api_get(url, token):
    """Authenticated GET request to a Google API."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _get_db():
    """Get a SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _decode_base64url(data):
    """Decode base64url-encoded data (Gmail body encoding)."""
    # Add padding if needed
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _extract_body_parts(payload, mime_type="text/html"):
    """Recursively walk Gmail payload parts to find the body of a given MIME type."""
    # Check this part directly
    if payload.get("mimeType") == mime_type:
        body_data = payload.get("body", {}).get("data", "")
        if body_data:
            return _decode_base64url(body_data)

    # Walk child parts
    for part in payload.get("parts", []):
        result = _extract_body_parts(part, mime_type)
        if result:
            return result

    return None


def _extract_doc_text(doc):
    """Extract plain text from a Google Docs API document response.

    Walks body.content[].paragraph.elements[].textRun.content in order.
    """
    text_parts = []
    for element in doc.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        line_parts = []
        for pe in paragraph.get("elements", []):
            text_run = pe.get("textRun")
            if text_run:
                line_parts.append(text_run.get("content", ""))
        text_parts.append("".join(line_parts))
    return "".join(text_parts).strip()


def _parse_meeting_date(subject):
    """Try to extract a date from a Gemini email subject like 'Notes: Meeting 2/21/2026'."""
    # Try common date patterns in the subject
    patterns = [
        r"(\d{1,2}/\d{1,2}/\d{4})",           # M/D/YYYY
        r"(\d{4}-\d{2}-\d{2})",                 # YYYY-MM-DD
        r"(\w+ \d{1,2},?\s*\d{4})",             # Month D, YYYY
    ]
    for pattern in patterns:
        match = re.search(pattern, subject)
        if match:
            date_str = match.group(1)
            for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y", "%B %d %Y"):
                try:
                    return datetime.strptime(date_str, fmt).isoformat()
                except ValueError:
                    continue
    return None


def _find_calendar_event(conn, meeting_date_str):
    """Find a calendar event within ±30 min of the meeting date."""
    try:
        meeting_dt = datetime.fromisoformat(meeting_date_str)
    except (ValueError, TypeError):
        return None

    window_start = (meeting_dt - timedelta(minutes=30)).isoformat()
    window_end = (meeting_dt + timedelta(minutes=30)).isoformat()

    row = conn.execute(
        """SELECT id FROM calendar_events
           WHERE start_time >= ? AND start_time <= ?
           ORDER BY ABS(julianday(start_time) - julianday(?))
           LIMIT 1""",
        (window_start, window_end, meeting_date_str),
    ).fetchone()
    return row["id"] if row else None


# ── Commands ─────────────────────────────────────────────────────────────


def cmd_scan():
    """Find new Gemini emails, fetch Google Docs, store raw transcripts."""
    token = _get_token()
    if not token:
        print(json.dumps({"error": "Not authenticated. Run /google-setup first."}))
        sys.exit(1)

    conn = _get_db()
    imported = []
    errors = []

    # Find Gemini emails not yet in transcript_sources
    gemini_emails = conn.execute(
        """SELECT e.id, e.gmail_id, e.subject, e.received_at
           FROM emails e
           WHERE e.from_address = ?
             AND e.id NOT IN (SELECT email_id FROM transcript_sources WHERE email_id IS NOT NULL)
           ORDER BY e.received_at DESC""",
        (GEMINI_SENDER,),
    ).fetchall()

    if not gemini_emails:
        print(json.dumps({"imported": 0, "transcripts": [], "errors": []}))
        conn.close()
        return

    for email in gemini_emails:
        email_id = email["id"]
        gmail_id = email["gmail_id"]
        subject = email["subject"] or ""
        received_at = email["received_at"]

        try:
            # Fetch full email body to extract the Google Doc link
            msg = _api_get(
                f"{GMAIL_API}/messages/{gmail_id}?format=full",
                token,
            )

            # Extract HTML body (preferred for link extraction)
            html_body = _extract_body_parts(msg.get("payload", {}), "text/html")
            plain_body = _extract_body_parts(msg.get("payload", {}), "text/plain")
            body_text = html_body or plain_body or ""

            # Find Google Doc link
            doc_match = DOC_LINK_RE.search(body_text)
            if not doc_match:
                errors.append({"email_id": email_id, "error": "No Google Doc link found in email body"})
                continue

            doc_id = doc_match.group(1)
            doc_url = f"https://docs.google.com/document/d/{doc_id}"

            # Fetch the Google Doc content
            try:
                doc = _api_get(f"{DOCS_API}/{doc_id}", token)
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    print(json.dumps({
                        "needs_reauth": True,
                        "error": "Google Docs scope not authorized. Re-run /google-setup to grant access.",
                        "imported": len(imported),
                        "transcripts": imported,
                        "errors": errors,
                    }))
                    conn.close()
                    return
                raise

            raw_text = _extract_doc_text(doc)
            if not raw_text:
                errors.append({"email_id": email_id, "error": "Google Doc was empty"})
                continue

            doc_title = doc.get("title", subject)

            # Parse meeting date — prefer subject, fall back to email timestamp
            meeting_date = _parse_meeting_date(subject) or received_at or datetime.now().isoformat()

            # Match to calendar event
            calendar_event_id = _find_calendar_event(conn, received_at or meeting_date)

            # Store transcript
            cursor = conn.execute(
                """INSERT INTO transcripts
                   (title, source, raw_text, occurred_at, source_email_id,
                    source_calendar_event_id, source_doc_id)
                   VALUES (?, 'gemini', ?, ?, ?, ?, ?)""",
                (doc_title, raw_text, meeting_date, email_id,
                 calendar_event_id, doc_id),
            )
            transcript_id = cursor.lastrowid

            # Store in transcript_sources for dedup
            conn.execute(
                """INSERT INTO transcript_sources
                   (transcript_id, email_id, doc_id, doc_url, source_type)
                   VALUES (?, ?, ?, ?, 'gemini')""",
                (transcript_id, email_id, doc_id, doc_url),
            )

            # Log activity
            conn.execute(
                """INSERT INTO activity_log (entity_type, entity_id, action, details)
                   VALUES ('transcript', ?, 'auto_imported',
                           json_object('title', ?, 'source', 'gemini', 'doc_id', ?))""",
                (transcript_id, doc_title, doc_id),
            )

            conn.commit()

            imported.append({
                "transcript_id": transcript_id,
                "title": doc_title,
                "date": meeting_date,
                "doc_id": doc_id,
            })

        except Exception as e:
            errors.append({"email_id": email_id, "error": str(e)})
            conn.rollback()

    conn.close()
    print(json.dumps({"imported": len(imported), "transcripts": imported, "errors": errors}))


def cmd_pending():
    """List transcripts that haven't been analyzed yet."""
    conn = _get_db()
    rows = conn.execute(
        """SELECT id, title, source, occurred_at, created_at
           FROM transcripts
           WHERE source = 'gemini' AND processed_at IS NULL
           ORDER BY occurred_at DESC""",
    ).fetchall()
    conn.close()

    transcripts = [
        {
            "id": r["id"],
            "title": r["title"],
            "date": r["occurred_at"],
            "imported_at": r["created_at"],
        }
        for r in rows
    ]
    print(json.dumps({"pending": len(transcripts), "transcripts": transcripts}))


def cmd_get(transcript_id):
    """Return raw text for a specific transcript."""
    conn = _get_db()
    row = conn.execute(
        "SELECT id, title, source, raw_text, occurred_at FROM transcripts WHERE id = ?",
        (transcript_id,),
    ).fetchone()
    conn.close()

    if not row:
        print(json.dumps({"error": f"Transcript {transcript_id} not found."}))
        sys.exit(1)

    print(json.dumps({
        "id": row["id"],
        "title": row["title"],
        "source": row["source"],
        "date": row["occurred_at"],
        "raw_text": row["raw_text"],
    }))


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: sync_transcripts.py [scan|pending|get <id>]"}))
        sys.exit(1)

    command = sys.argv[1]

    if command == "scan":
        cmd_scan()
    elif command == "pending":
        cmd_pending()
    elif command == "get":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "Usage: sync_transcripts.py get <transcript_id>"}))
            sys.exit(1)
        cmd_get(int(sys.argv[2]))
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
