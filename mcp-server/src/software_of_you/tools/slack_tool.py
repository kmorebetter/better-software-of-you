"""Slack tool — search and browse synced Slack messages, and manage connection."""

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def slack(
        action: str,
        query: str = "",
        channel: str = "",
        contact_id: int = 0,
        thread_ts: str = "",
        days: int = 7,
    ) -> dict:
        """Search and browse synced Slack messages.

        Actions:
          search   — Search messages by content (query required, last N days)
          recent   — Recent messages by channel name/id or contact_id (last N days)
          thread   — Get all messages in a thread (thread_ts required)
          channels — List all synced Slack channels

        Auto-syncs Slack if data is stale (>15 min). Messages are read-only —
        this tool reads what's been synced from Slack.
        """
        _auto_sync()

        if action == "search":
            return _search(query, days)
        elif action == "recent":
            return _recent(channel, contact_id, days)
        elif action == "thread":
            return _thread(thread_ts)
        elif action == "channels":
            return _channels()
        else:
            return {"error": f"Unknown action: {action}. Use: search, recent, thread, channels"}

    @server.tool()
    def slack_setup() -> dict:
        """Connect or check Slack workspace connection.

        If already connected, returns status and team info.
        If not connected, starts the OAuth flow (opens browser) and
        triggers an initial sync on success.
        """
        from software_of_you.slack_auth import is_connected, load_token

        if is_connected():
            token_data = load_token()
            return {
                "result": {
                    "connected": True,
                    "team_id": token_data.get("team_id", ""),
                    "team_name": token_data.get("team_name", ""),
                    "message": f"Slack is connected to workspace: {token_data.get('team_name', 'unknown')}.",
                },
                "_context": {
                    "presentation": "Confirm Slack is connected. Offer to search messages or list channels.",
                    "suggestions": [
                        "List Slack channels",
                        "Search recent Slack messages",
                    ],
                },
            }

        try:
            from software_of_you.slack_auth import run_auth_flow
            result = run_auth_flow()

            if result.get("success"):
                # Trigger initial sync
                from software_of_you.slack_sync import sync_slack
                sync_result = sync_slack()
                result["sync"] = sync_result

                return {
                    "result": result,
                    "_context": {
                        "presentation": "Slack is now connected. Report how many channels and messages were synced.",
                        "suggestions": [
                            "List Slack channels",
                            "Search recent messages",
                        ],
                    },
                }
            else:
                return {
                    "error": result.get("error", "Slack setup failed."),
                    "_context": {
                        "presentation": "Explain the error and suggest trying again.",
                    },
                }

        except Exception as e:
            return {
                "error": f"Slack setup failed: {e}",
                "_context": {
                    "presentation": "Explain the error and suggest trying again.",
                },
            }


def _auto_sync():
    """Auto-sync Slack messages if data is stale (>15 min)."""
    try:
        rows = execute("SELECT value FROM soy_meta WHERE key = 'slack_last_synced'")
        if rows:
            from datetime import datetime
            last = datetime.fromisoformat(rows[0]["value"])
            if (datetime.now() - last).total_seconds() < 900:
                return
        from software_of_you.slack_sync import sync_messages
        sync_messages()
    except Exception:
        pass


def _search(query, days):
    if not query:
        return {"error": "Search query is required."}

    pattern = f"%{query}%"
    rows = execute(
        """SELECT sm.*, c.name as contact_name
           FROM slack_messages sm
           LEFT JOIN contacts c ON sm.contact_id = c.id
           WHERE sm.content LIKE ?
             AND sm.received_at >= datetime('now', ?)
           ORDER BY sm.received_at DESC
           LIMIT 50""",
        (pattern, f"-{days} days"),
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "query": query,
        "_context": {
            "presentation": "Show matching Slack messages with sender, channel, time, and content snippet.",
        },
    }


def _recent(channel, contact_id, days):
    if contact_id:
        rows = execute(
            """SELECT sm.*, c.name as contact_name
               FROM slack_messages sm
               LEFT JOIN contacts c ON sm.contact_id = c.id
               WHERE sm.contact_id = ?
                 AND sm.received_at >= datetime('now', ?)
               ORDER BY sm.received_at DESC
               LIMIT 50""",
            (contact_id, f"-{days} days"),
        )
    elif channel:
        # Match by channel name or channel_id
        rows = execute(
            """SELECT sm.*, c.name as contact_name
               FROM slack_messages sm
               LEFT JOIN contacts c ON sm.contact_id = c.id
               WHERE (sm.channel_name LIKE ? OR sm.channel_id = ?)
                 AND sm.received_at >= datetime('now', ?)
               ORDER BY sm.received_at DESC
               LIMIT 50""",
            (f"%{channel}%", channel, f"-{days} days"),
        )
    else:
        # All recent messages
        rows = execute(
            """SELECT sm.*, c.name as contact_name
               FROM slack_messages sm
               LEFT JOIN contacts c ON sm.contact_id = c.id
               WHERE sm.received_at >= datetime('now', ?)
               ORDER BY sm.received_at DESC
               LIMIT 50""",
            (f"-{days} days",),
        )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show recent Slack messages with sender, channel, and time.",
            "suggestions": [
                "Offer to show a specific thread",
                "Offer to filter by channel or contact",
            ],
        },
    }


def _thread(thread_ts):
    if not thread_ts:
        return {"error": "thread_ts is required."}

    rows = execute(
        """SELECT sm.*, c.name as contact_name
           FROM slack_messages sm
           LEFT JOIN contacts c ON sm.contact_id = c.id
           WHERE sm.thread_ts = ? OR sm.slack_message_id LIKE ?
           ORDER BY sm.received_at ASC""",
        (thread_ts, f"%_{thread_ts}"),
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show thread as a conversation: each message with sender, time, and content.",
        },
    }


def _channels():
    rows = execute(
        """SELECT sc.*,
                  (SELECT COUNT(*) FROM slack_messages sm WHERE sm.channel_id = sc.slack_channel_id) as message_count
           FROM slack_channels sc
           ORDER BY sc.name ASC"""
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show channels with name, type (DM vs channel), monitoring status, and message count.",
            "suggestions": [
                "Offer to show recent messages in a specific channel",
                "Offer to toggle monitoring for a channel",
            ],
        },
    }
