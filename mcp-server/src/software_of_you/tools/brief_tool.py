"""Brief tool — morning, midday, and EOD intelligence briefs."""

from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute


def register(server: FastMCP) -> None:
    @server.tool()
    def brief(period: str = "auto") -> dict:
        """Generate an intelligence brief for the current time of day.

        Periods:
          auto     — detect from current hour (default)
          morning  — overnight emails, today's calendar, open commitments
          midday   — new since 6am, afternoon meetings, urgent items
          eod      — day summary, what happened, what's still open

        Call this when the user asks for a brief, summary, "what's going on",
        or "catch me up". Also call proactively on first message of the day.
        """
        if period == "auto":
            hour = datetime.now().hour
            if hour < 11:
                period = "morning"
            elif hour < 17:
                period = "midday"
            else:
                period = "eod"

        now = datetime.now()

        if period == "morning":
            since = (now - timedelta(hours=14)).isoformat()
            window_label = "overnight"
        elif period == "midday":
            since = now.replace(hour=6, minute=0, second=0).isoformat()
            window_label = "since 6am"
        else:
            since = now.replace(hour=12, minute=0, second=0).isoformat()
            window_label = "since noon"

        # Unread emails
        unread = execute("""
            SELECT e.subject, e.from_name, e.from_address, e.received_at,
                   ga.label as account
            FROM emails e
            LEFT JOIN google_accounts ga ON e.account_id = ga.id
            WHERE e.is_read = 0
            ORDER BY e.received_at DESC LIMIT 15
        """)

        # New emails in window
        new_emails = execute("""
            SELECT e.subject, e.from_name, e.received_at, ga.label as account
            FROM emails e
            LEFT JOIN google_accounts ga ON e.account_id = ga.id
            WHERE e.received_at > ? AND e.direction = 'inbound'
            ORDER BY e.received_at DESC LIMIT 15
        """, (since,))

        # Today's meetings
        today_start = now.replace(hour=0, minute=0, second=0).isoformat()
        today_end = now.replace(hour=23, minute=59, second=59).isoformat()
        today_events = execute("""
            SELECT title, start_time, end_time, attendees, ga.label as account
            FROM calendar_events ce
            LEFT JOIN google_accounts ga ON ce.account_id = ga.id
            WHERE start_time BETWEEN ? AND ? AND status != 'cancelled'
            ORDER BY start_time ASC
        """, (today_start, today_end))

        # Open commitments — yours first, then by urgency
        commitments = execute("""
            SELECT c.description, c.deadline_mentioned, c.is_user_commitment,
                   con.name as owner, p.name as project
            FROM commitments c
            LEFT JOIN contacts con ON c.owner_contact_id = con.id
            LEFT JOIN projects p ON c.linked_project_id = p.id
            WHERE c.status = 'open'
            ORDER BY c.is_user_commitment DESC, c.deadline_mentioned ASC NULLS LAST
            LIMIT 15
        """)

        # Urgent projects
        urgent_projects = execute("""
            SELECT name, priority, description
            FROM projects
            WHERE status = 'active' AND priority IN ('urgent', 'high')
            ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 END
        """)

        return {
            "result": {
                "period": period,
                "window": window_label,
                "generated_at": now.isoformat(),
                "unread_count": len(unread),
                "unread_emails": [dict(r) for r in unread],
                "new_emails": [dict(r) for r in new_emails],
                "new_email_count": len(new_emails),
                "today_meetings": [dict(r) for r in today_events],
                "meeting_count": len(today_events),
                "open_commitments": [dict(r) for r in commitments],
                "commitment_count": len(commitments),
                "urgent_projects": [dict(r) for r in urgent_projects],
            },
            "_context": {
                "presentation": (
                    f"Present as a {'morning' if period == 'morning' else 'midday' if period == 'midday' else 'end-of-day'} brief. "
                    "Lead with today's calendar, then urgent unread emails (highlight anything that needs a response), "
                    "then your open commitments, then active project status. "
                    "Be concise — this is a briefing, not a dump. Flag anything time-sensitive."
                ),
                "suggestions": [
                    "Offer to pull up a specific email thread",
                    "Offer to prep for the next meeting",
                    "Surface any commitments due today",
                ],
            },
        }
