"""Intelligence tools — meeting prep, nudges, commitments, relationship pulse, weekly review.

These wrap the pre-computed SQL views (from migration 014) and enrich
with cross-references. They are the "second brain" layer — the reason
a CEO uses this instead of just searching her email.
"""

import json
from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, rows_to_dicts


def _auto_sync_all() -> None:
    """Check freshness and sync stale services. Logs failures to stderr."""
    try:
        from software_of_you.google_sync import sync_service
        from datetime import datetime

        for key, service, threshold in [
            ("gmail_last_synced", "gmail", 900),
            ("calendar_last_synced", "calendar", 900),
            ("transcripts_last_scanned", "transcripts", 3600),
        ]:
            rows = execute("SELECT value FROM soy_meta WHERE key = ?", (key,))
            if rows:
                last = datetime.fromisoformat(rows[0]["value"])
                if (datetime.now() - last).total_seconds() < threshold:
                    continue
            sync_service(service)
    except Exception as e:
        import sys
        print(f"Auto-sync failed: {e}", file=sys.stderr)


def _auto_sync_slack() -> None:
    """Check Slack freshness and sync if stale. Logs failures to stderr."""
    try:
        from datetime import datetime
        rows = execute("SELECT value FROM soy_meta WHERE key = 'slack_last_synced'", ())
        if rows:
            last = datetime.fromisoformat(rows[0]["value"])
            if (datetime.now() - last).total_seconds() < 900:
                return
        from software_of_you.slack_sync import sync_slack
        sync_slack()
    except Exception as e:
        import sys
        print(f"Slack auto-sync failed: {e}", file=sys.stderr)


def register(server: FastMCP) -> None:

    @server.tool()
    def meeting_prep(
        event_id: int = 0,
        hours_ahead: int = 4,
        contact_name: str = "",
    ) -> dict:
        """Get a meeting prep brief for an upcoming calendar event.

        Includes: attendees, relationship history, open commitments,
        recent email threads, and topics from past transcripts.

        Args:
            event_id: Specific calendar event ID (0 = find next upcoming)
            hours_ahead: Look-ahead window in hours when event_id is 0
            contact_name: Find next event with this attendee
        """
        _auto_sync_all()

        # Find the event
        if event_id:
            events = execute(
                "SELECT * FROM v_meeting_prep WHERE event_id = ?", (event_id,)
            )
        elif contact_name:
            # Find next event with this attendee in the attendees JSON
            pattern = f"%{contact_name}%"
            events = execute(
                """SELECT * FROM v_meeting_prep
                   WHERE minutes_until > 0
                     AND (attendees LIKE ? OR title LIKE ?)
                   ORDER BY minutes_until ASC LIMIT 1""",
                (pattern, pattern),
            )
        else:
            events = execute(
                """SELECT * FROM v_meeting_prep
                   WHERE minutes_until > 0 AND minutes_until < ?
                   ORDER BY minutes_until ASC LIMIT 1""",
                (hours_ahead * 60,),
            )

        if not events:
            return {
                "result": None,
                "_context": {
                    "empty_state": f"No upcoming meetings in the next {hours_ahead} hours.",
                    "suggestions": ["Check tomorrow's calendar", "Add a calendar event"],
                },
            }

        event = rows_to_dicts(events)[0]

        # Parse attendee contact IDs
        contact_ids = []
        try:
            contact_ids = json.loads(event.get("contact_ids") or "[]")
        except (json.JSONDecodeError, TypeError):
            pass

        # Build per-attendee briefs
        attendee_briefs = []
        for cid in contact_ids:
            brief = {"contact_id": cid}

            # Relationship health
            health = execute("SELECT * FROM v_contact_health WHERE id = ?", (cid,))
            if health:
                h = rows_to_dicts(health)[0]
                brief["name"] = h.get("name", "")
                brief["company"] = h.get("company", "")
                brief["days_silent"] = h.get("days_silent")
                brief["relationship_depth"] = h.get("relationship_depth")
                brief["trajectory"] = h.get("trajectory")

            # Open commitments with this person
            commits = execute(
                "SELECT description, deadline_date, days_overdue, urgency FROM v_commitment_status WHERE owner_contact_id = ? LIMIT 5",
                (cid,),
            )
            if commits:
                brief["open_commitments"] = rows_to_dicts(commits)

            # Recent emails (last 14 days)
            emails = execute(
                """SELECT subject, direction, received_at FROM emails
                   WHERE contact_id = ? AND received_at > datetime('now', '-14 days')
                   ORDER BY received_at DESC LIMIT 5""",
                (cid,),
            )
            if emails:
                brief["recent_emails"] = rows_to_dicts(emails)

            # Recent Slack messages
            try:
                slack_msgs = execute(
                    """SELECT content, channel_name, received_at FROM slack_messages
                       WHERE contact_id = ? AND received_at > datetime('now', '-14 days')
                       ORDER BY received_at DESC LIMIT 5""",
                    (cid,),
                )
                if slack_msgs:
                    brief["recent_slack"] = rows_to_dicts(slack_msgs)
            except Exception:
                pass  # Slack table may not exist yet

            # Last transcript mention
            transcripts = execute(
                """SELECT t.title, t.occurred_at FROM transcripts t
                   JOIN transcript_participants tp ON tp.transcript_id = t.id
                   WHERE tp.contact_id = ?
                   ORDER BY t.occurred_at DESC LIMIT 1""",
                (cid,),
            )
            if transcripts:
                brief["last_meeting"] = rows_to_dicts(transcripts)[0]

            attendee_briefs.append(brief)

        return {
            "result": {
                "event": event,
                "attendee_briefs": attendee_briefs,
                "attendee_count": len(attendee_briefs),
            },
            "_context": {
                "presentation": "Lead with the meeting title and time. Then per attendee: relationship context, open commitments (flag overdue ones), and recent communication. End with 2-3 suggested talking points based on the data.",
                "suggestions": ["Flag any overdue commitments prominently"],
            },
        }

    @server.tool()
    def nudges(
        tier: str = "all",
        limit: int = 20,
    ) -> dict:
        """Surface what needs attention — overdue follow-ups, stale relationships, missed commitments.

        Args:
            tier: Filter by urgency: urgent, soon, awareness, or all
            limit: Max items to return
        """
        _auto_sync_all()
        _auto_sync_slack()

        # Summary counts
        summary_rows = execute("SELECT * FROM v_nudge_summary")
        summary = rows_to_dicts(summary_rows) if summary_rows else []

        # Nudge items
        if tier and tier != "all":
            items = execute(
                "SELECT * FROM v_nudge_items WHERE tier = ? ORDER BY days_value ASC LIMIT ?",
                (tier, limit),
            )
        else:
            items = execute(
                "SELECT * FROM v_nudge_items ORDER BY CASE tier WHEN 'urgent' THEN 0 WHEN 'soon' THEN 1 ELSE 2 END, days_value ASC LIMIT ?",
                (limit,),
            )

        nudge_list = rows_to_dicts(items) if items else []

        if not nudge_list:
            return {
                "result": {"items": [], "summary": summary},
                "_context": {
                    "empty_state": "Nothing urgent — you're all caught up.",
                    "presentation": "Celebrate this! It's rare.",
                },
            }

        return {
            "result": {"items": nudge_list, "summary": summary, "count": len(nudge_list)},
            "_context": {
                "presentation": "Group by urgency tier. Lead with urgent items. For each: what it is, who it involves, how overdue. Keep it scannable.",
                "suggestions": ["Offer to take action on the top item"],
            },
        }

    @server.tool()
    def commitments_view(
        status: str = "open",
        contact_id: int = 0,
    ) -> dict:
        """Show commitments — promises made in meetings, tracked automatically.

        Args:
            status: Filter: open, overdue, completed, all
            contact_id: Filter by person (0 = all people)
        """
        _auto_sync_all()  # Commitments come from transcripts

        if contact_id:
            rows = execute(
                "SELECT * FROM v_commitment_status WHERE owner_contact_id = ? ORDER BY days_overdue DESC",
                (contact_id,),
            )
        elif status == "overdue":
            rows = execute(
                "SELECT * FROM v_commitment_status WHERE urgency = 'overdue' OR days_overdue > 0 ORDER BY days_overdue DESC"
            )
        elif status == "all":
            rows = execute(
                "SELECT * FROM v_commitment_status ORDER BY deadline_date ASC"
            )
        else:
            rows = execute(
                "SELECT * FROM v_commitment_status WHERE status IN ('open', 'overdue') ORDER BY days_overdue DESC"
            )

        items = rows_to_dicts(rows) if rows else []

        if not items:
            return {
                "result": {"items": [], "count": 0},
                "_context": {
                    "empty_state": "No open commitments." if status != "all" else "No commitments recorded yet.",
                    "suggestions": ["Import a meeting transcript to extract commitments"],
                },
            }

        return {
            "result": {"items": items, "count": len(items)},
            "_context": {
                "presentation": "Group by person. For each: the commitment, when it was made, deadline, days overdue. Flag urgent ones.",
            },
        }

    @server.tool()
    def relationship_pulse(
        contact_id: int = 0,
        threshold_days: int = 14,
    ) -> dict:
        """Deep relationship health check — who's warm, who's cooling, who's gone silent.

        Args:
            contact_id: Specific contact for deep dive (0 = show all, ranked by staleness)
            threshold_days: Days silent to flag as cooling
        """
        _auto_sync_all()
        _auto_sync_slack()

        if contact_id:
            rows = execute("SELECT * FROM v_contact_health WHERE id = ?", (contact_id,))
            if not rows:
                return {"error": f"No contact with id {contact_id}."}

            contact = rows_to_dicts(rows)[0]

            # Enrich with recent Slack
            try:
                slack_count = execute(
                    "SELECT COUNT(*) as n FROM slack_messages WHERE contact_id = ? AND received_at > datetime('now', '-30 days')",
                    (contact_id,),
                )
                contact["slack_messages_30d"] = slack_count[0]["n"] if slack_count else 0
            except Exception:
                contact["slack_messages_30d"] = 0

            return {
                "result": contact,
                "_context": {
                    "presentation": "Full relationship profile. Lead with how the relationship is doing (warm/cooling/cold based on days_silent vs threshold). Show communication breakdown: emails, Slack, meetings. Flag open commitments and next meeting.",
                },
            }
        else:
            # All contacts ranked by staleness
            rows = execute(
                "SELECT * FROM v_contact_health WHERE days_silent IS NOT NULL ORDER BY days_silent DESC"
            )
            contacts = rows_to_dicts(rows) if rows else []

            cooling = [c for c in contacts if (c.get("days_silent") or 0) >= threshold_days]
            warm = [c for c in contacts if (c.get("days_silent") or 0) < threshold_days]

            return {
                "result": {
                    "cooling": cooling,
                    "warm": warm,
                    "cooling_count": len(cooling),
                    "warm_count": len(warm),
                },
                "_context": {
                    "presentation": f"Show cooling relationships first ({len(cooling)} contacts silent for {threshold_days}+ days). Then warm ones. For each: name, company, days silent, last interaction type.",
                },
            }

    @server.tool()
    def weekly_review(
        week_offset: int = 0,
    ) -> dict:
        """Aggregated week-in-review across all modules.

        Args:
            week_offset: 0 = current week (Mon-Sun), -1 = last week
        """
        _auto_sync_all()
        _auto_sync_slack()

        # Calculate ISO week boundaries
        from datetime import datetime, timedelta
        today = datetime.now()
        # Monday of target week
        monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        monday_str = monday.strftime("%Y-%m-%d")
        sunday = monday + timedelta(days=6)
        sunday_str = sunday.strftime("%Y-%m-%d")
        next_monday_str = (sunday + timedelta(days=1)).strftime("%Y-%m-%d")
        next_sunday_str = (sunday + timedelta(days=7)).strftime("%Y-%m-%d")

        data = {"week_start": monday_str, "week_end": sunday_str}

        # Meetings held
        meetings = execute(
            """SELECT id, title, start_time, end_time, attendees, contact_ids
               FROM calendar_events
               WHERE date(start_time) BETWEEN ? AND ? AND status != 'cancelled'
               ORDER BY start_time ASC""",
            (monday_str, sunday_str),
        )
        data["meetings"] = {"items": rows_to_dicts(meetings), "count": len(meetings)}

        # Commitments made this week (view has created_at)
        new_commits = execute(
            """SELECT * FROM v_commitment_status
               WHERE created_at BETWEEN ? AND ?""",
            (monday_str, sunday_str + " 23:59:59"),
        )
        # Completed this week (query commitments table directly — view doesn't expose completed_at)
        completed_commits = execute(
            """SELECT c.id, c.description, c.completed_at, co.name as owner_name
               FROM commitments c
               LEFT JOIN contacts co ON c.owner_contact_id = co.id
               WHERE c.status = 'completed'
                 AND c.completed_at BETWEEN ? AND ?""",
            (monday_str, sunday_str + " 23:59:59"),
        )
        data["commitments"] = {
            "made": len(new_commits) if new_commits else 0,
            "completed": len(completed_commits) if completed_commits else 0,
            "new_items": rows_to_dicts(new_commits) if new_commits else [],
        }

        # Relationships warming/cooling
        health_rows = execute("SELECT * FROM v_contact_health WHERE last_activity IS NOT NULL")
        contacts = rows_to_dicts(health_rows) if health_rows else []
        warming = [c for c in contacts if c.get("last_activity", "") >= monday_str]
        cooling = [c for c in contacts
                   if c.get("last_activity", "") < monday_str
                   and (c.get("days_silent") or 0) >= 14]
        data["relationships"] = {
            "warming": [{"name": c["name"], "company": c.get("company"), "last_activity": c["last_activity"]} for c in warming[:10]],
            "cooling": [{"name": c["name"], "company": c.get("company"), "days_silent": c["days_silent"]} for c in cooling[:10]],
        }

        # Decisions
        try:
            decisions = execute(
                "SELECT title, context, status, decided_at FROM decisions WHERE decided_at BETWEEN ? AND ?",
                (monday_str, sunday_str + " 23:59:59"),
            )
            data["decisions"] = rows_to_dicts(decisions) if decisions else []
        except Exception:
            data["decisions"] = []

        # Next week preview
        next_meetings = execute(
            """SELECT title, start_time, attendees FROM calendar_events
               WHERE date(start_time) BETWEEN ? AND ? AND status != 'cancelled'
               ORDER BY start_time ASC""",
            (next_monday_str, next_sunday_str),
        )
        upcoming_commits = execute(
            """SELECT * FROM v_commitment_status
               WHERE status IN ('open', 'overdue')
                 AND deadline_date BETWEEN ? AND ?""",
            (next_monday_str, next_sunday_str),
        )
        data["next_week"] = {
            "meetings": rows_to_dicts(next_meetings) if next_meetings else [],
            "pending_commitments": rows_to_dicts(upcoming_commits) if upcoming_commits else [],
        }

        return {
            "result": data,
            "_context": {
                "presentation": "Narrative weekly review. Lead with headline stats (N meetings, N commitments made/completed). Then: key meetings and takeaways, commitment status, relationship changes, decisions. End with next week preview and what to watch for.",
            },
        }
