"""Slack tool — search and browse synced Slack messages, manage connection."""

from datetime import datetime

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
        days: int = 30,
    ) -> dict:
        """Search and browse synced Slack messages.

        Actions:
          search   — keyword match in message text (last `days`)
          recent   — recent messages by channel name/id or contact_id
          thread   — all messages in a thread (thread_ts required)
          channels — list synced Slack channels with allowlist + counts

        Auto-syncs Slack if data is stale (>15 min). Read-only.
        """
        _auto_sync()

        if action == "search":
            return _search(query, days)
        if action == "recent":
            return _recent(channel, contact_id, days)
        if action == "thread":
            return _thread(thread_ts)
        if action == "channels":
            return _channels()
        return {
            "error": f"Unknown action: {action}. Use: search, recent, thread, channels",
        }

    @server.tool()
    def slack_setup(token: str = "") -> dict:
        """Connect Slack or check current connection.

        Pass a Slack user token (xoxp-...) or bot token (xoxb-...) to connect.
        With no token, returns the current connection status.
        Triggers an initial sync after a successful connection.
        """
        from software_of_you import slack_auth

        if not token:
            data = slack_auth.load_token()
            if data and data.get("access_token"):
                return {
                    "result": {
                        "connected": True,
                        "team": data.get("team"),
                        "user": data.get("user"),
                        "url": data.get("url"),
                    },
                    "_context": {
                        "presentation": "Confirm Slack is connected. Offer to search messages, list channels, or run a sync.",
                    },
                }
            return {
                "result": {
                    "connected": False,
                    "message": "No Slack token saved. Pass a xoxp- or xoxb- token to connect.",
                },
                "_context": {
                    "presentation": "Walk the user through generating a Slack user token from api.slack.com/apps and pass it back as the `token` argument.",
                },
            }

        result = slack_auth.save_token(token)
        if not result.get("ok"):
            return {
                "error": result.get("error", "Slack rejected the token."),
                "_context": {
                    "presentation": "Explain the Slack rejection and ask the user to verify the token.",
                },
            }

        from software_of_you.slack_sync import sync_slack
        sync_result = sync_slack()

        return {
            "result": {
                "connected": True,
                "team": result.get("team"),
                "user": result.get("user"),
                "url": result.get("url"),
                "sync": sync_result,
            },
            "_context": {
                "presentation": "Report the workspace name and the sync results (users linked, channels found, messages synced).",
                "suggestions": [
                    "Allowlist a channel to start mirroring it",
                    "Search Slack messages",
                ],
            },
        }


def _auto_sync() -> None:
    """Sync Slack if data is stale (>15 min). Best-effort; swallow errors."""
    try:
        rows = execute("SELECT value FROM soy_meta WHERE key = 'slack_last_synced'")
        if rows:
            last = datetime.fromisoformat(rows[0]["value"])
            if (datetime.now() - last).total_seconds() < 900:
                return
        from software_of_you.slack_sync import sync_slack
        sync_slack()
    except Exception:
        pass


def _search(query: str, days: int) -> dict:
    if not query:
        return {"error": "Search query is required."}

    pattern = f"%{query}%"
    rows = execute(
        """SELECT sm.id, sm.slack_ts, sm.text, sm.sent_at, sm.direction,
                  sm.permalink, sm.has_link, sm.has_file,
                  sc.name AS channel_name, sc.channel_type, sc.slack_channel_id,
                  c.name AS contact_name, sm.contact_id
           FROM slack_messages sm
           JOIN slack_channels sc ON sc.id = sm.channel_id
           LEFT JOIN contacts c ON c.id = sm.contact_id
           WHERE sm.text LIKE ?
             AND sm.sent_at >= datetime('now', ?)
           ORDER BY sm.sent_at DESC
           LIMIT 50""",
        (pattern, f"-{days} days"),
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "query": query,
        "_context": {
            "presentation": "Show matching Slack messages with sender, channel, time, and a content snippet. Include permalinks where present.",
        },
    }


def _recent(channel: str, contact_id: int, days: int) -> dict:
    if contact_id:
        rows = execute(
            """SELECT sm.id, sm.slack_ts, sm.text, sm.sent_at, sm.direction,
                      sm.permalink, sc.name AS channel_name, sc.channel_type,
                      c.name AS contact_name
               FROM slack_messages sm
               JOIN slack_channels sc ON sc.id = sm.channel_id
               LEFT JOIN contacts c ON c.id = sm.contact_id
               WHERE sm.contact_id = ?
                 AND sm.sent_at >= datetime('now', ?)
               ORDER BY sm.sent_at DESC
               LIMIT 50""",
            (contact_id, f"-{days} days"),
        )
    elif channel:
        rows = execute(
            """SELECT sm.id, sm.slack_ts, sm.text, sm.sent_at, sm.direction,
                      sm.permalink, sc.name AS channel_name, sc.channel_type,
                      c.name AS contact_name
               FROM slack_messages sm
               JOIN slack_channels sc ON sc.id = sm.channel_id
               LEFT JOIN contacts c ON c.id = sm.contact_id
               WHERE (sc.name LIKE ? OR sc.slack_channel_id = ?)
                 AND sm.sent_at >= datetime('now', ?)
               ORDER BY sm.sent_at DESC
               LIMIT 50""",
            (f"%{channel}%", channel, f"-{days} days"),
        )
    else:
        rows = execute(
            """SELECT sm.id, sm.slack_ts, sm.text, sm.sent_at, sm.direction,
                      sm.permalink, sc.name AS channel_name, sc.channel_type,
                      c.name AS contact_name
               FROM slack_messages sm
               JOIN slack_channels sc ON sc.id = sm.channel_id
               LEFT JOIN contacts c ON c.id = sm.contact_id
               WHERE sm.sent_at >= datetime('now', ?)
               ORDER BY sm.sent_at DESC
               LIMIT 50""",
            (f"-{days} days",),
        )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show recent Slack messages with sender, channel, and time.",
        },
    }


def _thread(thread_ts: str) -> dict:
    if not thread_ts:
        return {"error": "thread_ts is required."}

    rows = execute(
        """SELECT sm.id, sm.slack_ts, sm.text, sm.sent_at, sm.direction,
                  sm.permalink, sc.name AS channel_name,
                  c.name AS contact_name
           FROM slack_messages sm
           JOIN slack_channels sc ON sc.id = sm.channel_id
           LEFT JOIN contacts c ON c.id = sm.contact_id
           WHERE sm.thread_ts = ? OR sm.slack_ts = ?
           ORDER BY sm.sent_at ASC""",
        (thread_ts, thread_ts),
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show the thread as a conversation: each message with sender, time, and content.",
        },
    }


def _channels() -> dict:
    rows = execute(
        """SELECT sc.id, sc.slack_channel_id, sc.name, sc.channel_type,
                  sc.is_allowlisted, sc.allowlisted_at, sc.last_synced_ts,
                  sc.is_archived, sc.member_count,
                  (SELECT COUNT(*) FROM slack_messages sm WHERE sm.channel_id = sc.id) AS message_count,
                  (SELECT MAX(sm.sent_at) FROM slack_messages sm WHERE sm.channel_id = sc.id) AS last_message_at
           FROM slack_channels sc
           ORDER BY
             CASE sc.channel_type WHEN 'im' THEN 0 WHEN 'mpim' THEN 1 ELSE 2 END,
             sc.name ASC"""
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show channels grouped by type (DMs first, then MPIMs, then channels). Indicate which are allowlisted, message counts, and most-recent activity.",
            "suggestions": [
                "Allowlist a public/private channel to start mirroring it",
                "Show recent messages in a specific channel",
            ],
        },
    }
