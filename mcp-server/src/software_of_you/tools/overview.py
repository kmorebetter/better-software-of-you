"""Overview tool — all-module dashboard aggregate in one call."""

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, rows_to_dicts, get_installed_modules


def register(server: FastMCP) -> None:
    @server.tool()
    def get_overview() -> dict:
        """Get a complete dashboard overview across all modules in one call.

        Returns aggregate data for building a dashboard or answering
        "what's going on?" questions. Includes contact stats, projects,
        follow-ups, recent activity, upcoming events, unread emails,
        and open commitments — depending on what modules are installed.

        Auto-syncs Gmail and Calendar if stale (>15 min).
        """
        modules = get_installed_modules()
        data = {"modules": modules}

        # Contact stats (always)
        data["contacts"] = {
            "total": execute("SELECT COUNT(*) as n FROM contacts")[0]["n"],
            "active": execute("SELECT COUNT(*) as n FROM contacts WHERE status = 'active'")[0]["n"],
            "recent": rows_to_dicts(execute(
                "SELECT id, name, company, role, updated_at FROM contacts WHERE status = 'active' ORDER BY updated_at DESC LIMIT 5"
            )),
        }

        # Projects
        if "project-tracker" in modules:
            data["projects"] = {
                "by_status": rows_to_dicts(execute("SELECT status, COUNT(*) as count FROM projects GROUP BY status")),
                "active": rows_to_dicts(execute(
                    """SELECT p.id, p.name, p.status, p.priority, p.target_date, c.name as client_name
                       FROM projects p LEFT JOIN contacts c ON p.client_id = c.id
                       WHERE p.status IN ('active', 'planning') ORDER BY p.priority DESC LIMIT 8"""
                )),
                "overdue_tasks": rows_to_dicts(execute(
                    """SELECT t.title, t.due_date, p.name as project_name FROM tasks t
                       JOIN projects p ON p.id = t.project_id
                       WHERE t.due_date < date('now') AND t.status NOT IN ('done')
                       ORDER BY t.due_date ASC LIMIT 5"""
                )),
                "task_stats": rows_to_dicts(execute("SELECT status, COUNT(*) as count FROM tasks GROUP BY status")),
            }

        # Follow-ups (CRM)
        if "crm" in modules:
            data["follow_ups"] = rows_to_dicts(execute(
                """SELECT f.id, f.due_date, f.reason, f.status, c.name as contact_name, c.id as contact_id
                   FROM follow_ups f JOIN contacts c ON c.id = f.contact_id
                   WHERE f.status = 'pending' ORDER BY f.due_date ASC LIMIT 8"""
            ))

        # Calendar events
        if "calendar" in modules:
            _auto_sync("calendar")
            data["calendar"] = {
                "today": rows_to_dicts(execute(
                    """SELECT id, title, start_time, end_time, location, attendees, contact_ids
                       FROM calendar_events
                       WHERE date(start_time) = date('now') AND status != 'cancelled'
                       ORDER BY start_time ASC"""
                )),
                "tomorrow": rows_to_dicts(execute(
                    """SELECT id, title, start_time, end_time, location
                       FROM calendar_events
                       WHERE date(start_time) = date('now', '+1 day') AND status != 'cancelled'
                       ORDER BY start_time ASC"""
                )),
                "week_count": execute(
                    """SELECT COUNT(*) as n FROM calendar_events
                       WHERE start_time BETWEEN datetime('now') AND datetime('now', '+7 days')
                       AND status != 'cancelled'"""
                )[0]["n"],
            }

        # Email stats
        if "gmail" in modules:
            _auto_sync("gmail")
            data["email"] = {
                "unread": execute("SELECT COUNT(*) as n FROM emails WHERE is_read = 0")[0]["n"],
                "starred": execute("SELECT COUNT(*) as n FROM emails WHERE is_starred = 1 AND is_read = 0")[0]["n"],
                "needs_response": rows_to_dicts(execute(
                    """SELECT e.thread_id, e.subject, e.from_name, e.received_at, c.name as contact_name
                       FROM emails e LEFT JOIN contacts c ON e.contact_id = c.id
                       WHERE e.direction = 'inbound'
                         AND e.thread_id NOT IN (
                           SELECT thread_id FROM emails
                           WHERE direction = 'outbound' AND received_at > e.received_at)
                         AND e.received_at > datetime('now', '-7 days')
                       GROUP BY e.thread_id ORDER BY e.received_at DESC LIMIT 5"""
                )),
            }

        # Open commitments
        if "conversation-intelligence" in modules:
            data["commitments"] = {
                "open": execute("SELECT COUNT(*) as n FROM commitments WHERE status IN ('open', 'overdue')")[0]["n"],
                "overdue": execute("SELECT COUNT(*) as n FROM commitments WHERE status = 'overdue' OR (status = 'open' AND deadline_date < date('now'))")[0]["n"],
            }

        # Recent activity (always)
        data["activity"] = rows_to_dicts(execute(
            """SELECT al.*, CASE al.entity_type
                   WHEN 'contact' THEN (SELECT name FROM contacts WHERE id = al.entity_id)
                   WHEN 'project' THEN (SELECT name FROM projects WHERE id = al.entity_id)
                   ELSE al.entity_type || ' #' || al.entity_id
                 END as entity_name
               FROM activity_log al ORDER BY al.created_at DESC LIMIT 15"""
        ))

        return {
            "result": data,
            "_context": {
                "presentation": "Present as a conversational dashboard summary. Lead with what needs attention (overdue items, unread emails, upcoming meetings). Use natural language, not data dumps.",
                "suggestions": [
                    "Highlight overdue follow-ups and commitments",
                    "Mention today's upcoming meetings",
                    "Offer to generate an HTML dashboard view",
                ],
            },
        }


def _auto_sync(service: str) -> None:
    """Check freshness and sync if stale. Silently fails."""
    try:
        key = f"{service}_last_synced"
        rows = execute("SELECT value FROM soy_meta WHERE key = ?", (key,))
        if rows:
            from datetime import datetime
            last = datetime.fromisoformat(rows[0]["value"])
            diff = (datetime.now() - last).total_seconds()
            if diff < 900:  # 15 minutes
                return

        # Sync
        from software_of_you.google_sync import sync_service
        sync_service(service)
    except Exception:
        pass  # Silently use cached data
