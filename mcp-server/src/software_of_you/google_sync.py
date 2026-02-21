"""Gmail and Calendar sync using Google APIs.

Uses only stdlib (urllib) — no google-api-python-client needed.
Syncs data into the shared SQLite database.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from software_of_you.db import execute, execute_many
from software_of_you.google_auth import get_valid_token

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def _api_get(url: str, token: str) -> dict:
    """Make an authenticated GET request to a Google API."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _get_user_email(token: str) -> str | None:
    """Get the authenticated user's email address."""
    try:
        info = _api_get("https://www.googleapis.com/oauth2/v2/userinfo", token)
        return info.get("email")
    except Exception:
        return None


def sync_gmail(token: str | None = None) -> dict:
    """Sync recent emails from Gmail."""
    token = token or get_valid_token()
    if not token:
        return {"error": "Not authenticated with Google."}

    user_email = _get_user_email(token)
    synced = 0

    try:
        # Fetch recent message list
        url = f"{GMAIL_API}/messages?maxResults=50&q=newer_than:7d"
        data = _api_get(url, token)
        messages = data.get("messages", [])

        statements = []
        for msg_ref in messages:
            msg_id = msg_ref["id"]

            # Check if already synced
            existing = execute("SELECT id FROM emails WHERE gmail_id = ?", (msg_id,))
            if existing:
                continue

            # Fetch full message
            try:
                msg = _api_get(f"{GMAIL_API}/messages/{msg_id}?format=metadata&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Subject", token)
            except Exception:
                continue

            headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            from_addr = headers.get("from", "")
            to_addr = headers.get("to", "")
            subject = headers.get("subject", "(no subject)")

            # Parse from name/address
            from_name = from_addr
            from_email = from_addr
            if "<" in from_addr:
                parts = from_addr.split("<")
                from_name = parts[0].strip().strip('"')
                from_email = parts[1].rstrip(">").strip()

            # Determine direction
            direction = "outbound" if user_email and from_email.lower() == user_email.lower() else "inbound"

            # Try to match contact
            contact_match_email = from_email if direction == "inbound" else to_addr
            # Extract email from "Name <email>" format
            if "<" in contact_match_email:
                contact_match_email = contact_match_email.split("<")[1].rstrip(">").strip()

            contact_rows = execute(
                "SELECT id FROM contacts WHERE email = ?",
                (contact_match_email,),
            )
            contact_id = contact_rows[0]["id"] if contact_rows else None

            snippet = msg.get("snippet", "")
            thread_id = msg.get("threadId", "")
            labels = ",".join(msg.get("labelIds", []))
            is_read = "UNREAD" not in msg.get("labelIds", [])
            is_starred = "STARRED" in msg.get("labelIds", [])

            # Parse date
            internal_date = msg.get("internalDate", "0")
            received_at = datetime.fromtimestamp(int(internal_date) / 1000).isoformat()

            statements.append((
                """INSERT OR IGNORE INTO emails
                   (gmail_id, thread_id, contact_id, direction, from_address, to_addresses,
                    subject, snippet, labels, is_read, is_starred, received_at, from_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (msg_id, thread_id, contact_id, direction, from_email, to_addr,
                 subject, snippet, labels, 1 if is_read else 0, 1 if is_starred else 0,
                 received_at, from_name),
            ))
            synced += 1

        if statements:
            execute_many(statements)

        # Update sync timestamp
        execute_many([(
            "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('gmail_last_synced', datetime('now'), datetime('now'))",
            (),
        )])

        return {"synced": synced, "total_checked": len(messages)}

    except urllib.error.URLError as e:
        print(f"Gmail sync failed: {e}", file=sys.stderr)
        return {"error": str(e), "synced": synced}


def sync_calendar(token: str | None = None) -> dict:
    """Sync calendar events (next 14 days + last 7 days)."""
    token = token or get_valid_token()
    if not token:
        return {"error": "Not authenticated with Google."}

    synced = 0
    now = datetime.now()
    time_min = (now - timedelta(days=7)).isoformat() + "Z"
    time_max = (now + timedelta(days=14)).isoformat() + "Z"

    try:
        url = (
            f"{CALENDAR_API}/calendars/primary/events"
            f"?timeMin={urllib.parse.quote(time_min)}"
            f"&timeMax={urllib.parse.quote(time_max)}"
            f"&singleEvents=true&orderBy=startTime&maxResults=100"
        )
        data = _api_get(url, token)
        events = data.get("items", [])

        statements = []
        for event in events:
            event_id = event.get("id", "")
            if not event_id:
                continue

            title = event.get("summary", "(no title)")
            description = event.get("description", "")
            location = event.get("location", "")

            start = event.get("start", {})
            end = event.get("end", {})
            start_time = start.get("dateTime", start.get("date", ""))
            end_time = end.get("dateTime", end.get("date", ""))
            all_day = "date" in start and "dateTime" not in start

            status = event.get("status", "confirmed")
            attendees_raw = event.get("attendees", [])
            attendees = json.dumps([
                {"email": a.get("email", ""), "name": a.get("displayName", ""), "status": a.get("responseStatus", "")}
                for a in attendees_raw
            ]) if attendees_raw else None

            # Match attendees to contacts
            contact_ids = []
            for a in attendees_raw:
                email = a.get("email", "")
                if email:
                    rows = execute("SELECT id FROM contacts WHERE email = ?", (email,))
                    if rows:
                        contact_ids.append(rows[0]["id"])
            contact_ids_str = json.dumps(contact_ids) if contact_ids else None

            statements.append((
                """INSERT INTO calendar_events
                   (google_event_id, title, description, location, start_time, end_time,
                    all_day, status, attendees, contact_ids)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(google_event_id) DO UPDATE SET
                     title=excluded.title, description=excluded.description,
                     location=excluded.location, start_time=excluded.start_time,
                     end_time=excluded.end_time, status=excluded.status,
                     attendees=excluded.attendees, contact_ids=excluded.contact_ids,
                     synced_at=datetime('now')""",
                (event_id, title, description or None, location or None,
                 start_time, end_time, 1 if all_day else 0, status,
                 attendees, contact_ids_str),
            ))
            synced += 1

        if statements:
            execute_many(statements)

        execute_many([(
            "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('calendar_last_synced', datetime('now'), datetime('now'))",
            (),
        )])

        return {"synced": synced, "total_events": len(events)}

    except urllib.error.URLError as e:
        print(f"Calendar sync failed: {e}", file=sys.stderr)
        return {"error": str(e), "synced": synced}


def sync_service(service: str) -> dict:
    """Sync a specific service. Used by auto-sync."""
    token = get_valid_token()
    if not token:
        return {"error": "Not authenticated."}

    if service == "gmail":
        return sync_gmail(token)
    elif service == "calendar":
        return sync_calendar(token)
    else:
        return {"error": f"Unknown service: {service}"}
