"""Calendar tool — browse synced calendar events."""

import json

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def calendar(
        action: str,
        contact_id: int = 0,
        contact_name: str = "",
        date_str: str = "",
    ) -> dict:
        """Browse synced calendar events.

        Actions:
          today    — Today's events
          tomorrow — Tomorrow's events
          week     — Events for the next 7 days
          schedule — Events for a specific date (date_str required, YYYY-MM-DD)
          with     — Events with a specific contact (contact_id or contact_name)
          free     — Free time slots today (gaps between events)

        Auto-syncs calendar if data is stale (>15 min). Events are linked
        to contacts via attendee email matching.
        """
        _auto_sync()

        if action == "today":
            return _day("date('now')")
        elif action == "tomorrow":
            return _day("date('now', '+1 day')")
        elif action == "week":
            return _week()
        elif action == "schedule":
            return _schedule(date_str)
        elif action == "with":
            return _with_contact(contact_id, contact_name)
        elif action == "free":
            return _free()
        else:
            return {"error": f"Unknown action: {action}. Use: today, tomorrow, week, schedule, with, free"}


def _auto_sync():
    try:
        rows = execute("SELECT value FROM soy_meta WHERE key = 'calendar_last_synced'")
        if rows:
            from datetime import datetime
            last = datetime.fromisoformat(rows[0]["value"])
            if (datetime.now() - last).total_seconds() < 900:
                return
        from software_of_you.google_sync import sync_calendar
        sync_calendar()
    except Exception:
        pass


def _enrich_events(events):
    """Resolve contact_ids to names for each event."""
    for event in events:
        if event.get("contact_ids"):
            try:
                ids = json.loads(event["contact_ids"])
                if ids:
                    ph = ",".join("?" * len(ids))
                    contacts = execute(f"SELECT id, name, company FROM contacts WHERE id IN ({ph})", tuple(ids))
                    event["linked_contacts"] = rows_to_dicts(contacts)
            except (json.JSONDecodeError, TypeError):
                pass
    return events


def _day(date_expr):
    rows = execute(
        f"""SELECT * FROM calendar_events
            WHERE date(start_time) = {date_expr} AND status != 'cancelled'
            ORDER BY start_time ASC"""
    )
    events = _enrich_events(rows_to_dicts(rows))

    return {
        "result": events,
        "count": len(events),
        "_context": {
            "suggestions": [
                "Highlight the next upcoming event",
                "Offer to show contact details for attendees",
            ],
            "presentation": "Show timeline with times, titles, locations, and attendee names.",
        },
    }


def _week():
    rows = execute(
        """SELECT * FROM calendar_events
           WHERE date(start_time) BETWEEN date('now') AND date('now', '+6 days')
             AND status != 'cancelled'
           ORDER BY start_time ASC"""
    )
    events = _enrich_events(rows_to_dicts(rows))

    # Group by day
    by_day = {}
    for e in events:
        day = e["start_time"][:10]
        by_day.setdefault(day, []).append(e)

    return {
        "result": events,
        "by_day": by_day,
        "count": len(events),
        "_context": {
            "presentation": "Show events grouped by day. Use day headers (Monday, Tuesday, etc.).",
        },
    }


def _schedule(date_str):
    if not date_str:
        return {"error": "date_str (YYYY-MM-DD) is required."}

    rows = execute(
        "SELECT * FROM calendar_events WHERE date(start_time) = ? AND status != 'cancelled' ORDER BY start_time ASC",
        (date_str,),
    )
    events = _enrich_events(rows_to_dicts(rows))

    return {
        "result": events,
        "count": len(events),
        "date": date_str,
        "_context": {"presentation": f"Show events for {date_str}."},
    }


def _with_contact(contact_id, contact_name):
    if contact_name and not contact_id:
        rows = execute("SELECT id FROM contacts WHERE name LIKE ?", (f"%{contact_name}%",))
        if len(rows) == 1:
            contact_id = rows[0]["id"]
        elif len(rows) > 1:
            return {"error": "Multiple contacts match.", "matches": rows_to_dicts(rows)}
        else:
            return {"error": "Contact not found."}

    if not contact_id:
        return {"error": "contact_id or contact_name required."}

    rows = execute(
        "SELECT * FROM calendar_events WHERE contact_ids LIKE ? AND status != 'cancelled' ORDER BY start_time DESC LIMIT 20",
        (f"%{contact_id}%",),
    )
    events = _enrich_events(rows_to_dicts(rows))

    return {
        "result": events,
        "count": len(events),
        "_context": {"presentation": "Show meeting history with this contact."},
    }


def _free():
    rows = execute(
        """SELECT start_time, end_time, title FROM calendar_events
           WHERE date(start_time) = date('now') AND status != 'cancelled'
           ORDER BY start_time ASC"""
    )

    events = rows_to_dicts(rows)
    # Calculate gaps (simplified — returns the event schedule for Claude to derive gaps)
    return {
        "result": {
            "events": events,
            "count": len(events),
        },
        "_context": {
            "instructions": [
                "Calculate free slots between events.",
                "Assume work day is 9 AM to 6 PM.",
                "Show gaps as available time blocks.",
            ],
            "presentation": "Show free time slots between meetings today.",
        },
    }
