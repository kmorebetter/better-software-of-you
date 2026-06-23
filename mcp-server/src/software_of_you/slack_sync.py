"""Slack message sync for Software of You.

Uses only stdlib (urllib) — no slack-sdk needed.
Syncs channels and messages into the shared SQLite database.

Pattern mirrors google_sync.py.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from software_of_you.db import execute, execute_many, execute_write, rows_to_dicts
from software_of_you.slack_auth import get_bot_token
from software_of_you.tools._resolve import resolve_contact_by_name

SLACK_API = "https://slack.com/api"


def _should_mark_synced(failed: int) -> bool:
    """Only advance the freshness timestamp on a fully-clean sync.

    When channels were dropped (``failed > 0``) the timestamp must NOT advance,
    so auto-sync retries on the next call instead of waiting out the freshness
    window.
    """
    return failed == 0


def _api_get(method: str, token: str, params: dict | None = None) -> dict:
    """Make an authenticated GET request to the Slack API.

    Args:
        method: Slack API method name (e.g., 'conversations.list')
        token: Bot access token
        params: Optional query parameters

    Returns:
        Parsed JSON response dict
    """
    url = f"{SLACK_API}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    if not data.get("ok"):
        error = data.get("error", "unknown")
        raise RuntimeError(f"Slack API error ({method}): {error}")

    return data


def _match_contact(sender_name: str | None, sender_email: str | None) -> int | None:
    """Try to match a Slack user to an existing contact.

    Resolution order:
    1. Exact email match
    2. Fuzzy name match (LIKE %name%)

    Returns contact_id or None.
    """
    if sender_email:
        rows = execute(
            "SELECT id FROM contacts WHERE email = ?", (sender_email,)
        )
        if rows:
            return rows[0]["id"]

    # Fuzzy name fallback. On an ambiguous multi-match the helper returns an
    # ambiguous result rather than a unique id; here we intentionally leave the
    # message unlinked (preserving prior behavior) rather than guess.
    match = resolve_contact_by_name(sender_name or "")
    if match and "id" in match:
        return match["id"]

    return None


def sync_channels(token: str | None = None) -> dict:
    """Sync Slack channels list.

    Fetches all conversations the bot has access to and upserts
    into the slack_channels table.

    Args:
        token: Bot access token (fetched automatically if not provided)

    Returns:
        Result dict with sync count
    """
    token = token or get_bot_token()
    if not token:
        return {"error": "Not connected to Slack."}

    synced = 0

    try:
        data = _api_get("conversations.list", token, {
            "types": "public_channel,private_channel,im,mpim",
            "limit": "200",
        })

        channels = data.get("channels", [])
        statements = []

        for ch in channels:
            channel_id = ch.get("id", "")
            name = ch.get("name") or ch.get("user", "DM")
            is_dm = 1 if ch.get("is_im") or ch.get("is_mpim") else 0

            statements.append((
                """INSERT INTO slack_channels (slack_channel_id, name, is_dm)
                   VALUES (?, ?, ?)
                   ON CONFLICT(slack_channel_id) DO UPDATE SET
                     name = excluded.name,
                     is_dm = excluded.is_dm""",
                (channel_id, name, is_dm),
            ))
            synced += 1

        if statements:
            execute_many(statements)

        return {"synced": synced}

    except Exception as e:
        print(f"Slack channel sync failed: {e}", file=sys.stderr)
        return {"error": str(e), "synced": synced}


def sync_messages(token: str | None = None, days: int = 7) -> dict:
    """Sync recent Slack messages from monitored channels.

    Fetches message history for each monitored channel, matches senders
    to contacts, and inserts into slack_messages table.

    Args:
        token: Bot access token (fetched automatically if not provided)
        days: Number of days of history to fetch (default 7)

    Returns:
        Result dict with sync counts
    """
    token = token or get_bot_token()
    if not token:
        return {"error": "Not connected to Slack."}

    synced = 0
    failed = 0
    errors = []

    try:
        # Get monitored channels
        channels = execute(
            "SELECT slack_channel_id, name FROM slack_channels WHERE is_monitored = 1"
        )

        if not channels:
            return {"synced": 0, "message": "No monitored channels. Run sync_channels first."}

        # Build user cache for contact matching
        user_cache = {}
        try:
            user_data = _api_get("users.list", token, {"limit": "200"})
            for member in user_data.get("members", []):
                uid = member.get("id", "")
                profile = member.get("profile", {})
                user_cache[uid] = {
                    "name": profile.get("real_name") or member.get("name", ""),
                    "email": profile.get("email"),
                    "is_bot": member.get("is_bot", False),
                }
        except Exception as e:
            print(f"Failed to fetch Slack users: {e}", file=sys.stderr)

        # Calculate oldest timestamp
        oldest = (datetime.now() - timedelta(days=days)).timestamp()

        for ch in channels:
            channel_id = ch["slack_channel_id"]
            channel_name = ch["name"]

            try:
                history = _api_get("conversations.history", token, {
                    "channel": channel_id,
                    "oldest": str(oldest),
                    "limit": "100",
                })

                messages = history.get("messages", [])
                statements = []

                for msg in messages:
                    # Skip bot messages, system messages, and subtypes
                    if msg.get("subtype") or msg.get("bot_id"):
                        continue

                    sender_id = msg.get("user", "")
                    msg_ts = msg.get("ts", "")
                    if not msg_ts:
                        continue

                    # Composite ID: channel_id + message timestamp
                    composite_id = f"{channel_id}_{msg_ts}"

                    # Look up sender info
                    user_info = user_cache.get(sender_id, {})
                    if user_info.get("is_bot"):
                        continue

                    sender_name = user_info.get("name", "")
                    sender_email = user_info.get("email")
                    contact_id = _match_contact(sender_name, sender_email)

                    content = msg.get("text", "")
                    thread_ts = msg.get("thread_ts")
                    is_thread_parent = 1 if msg.get("reply_count", 0) > 0 else 0

                    # Convert Slack timestamp to ISO datetime
                    received_at = datetime.fromtimestamp(float(msg_ts)).isoformat()

                    statements.append((
                        """INSERT OR IGNORE INTO slack_messages
                           (slack_message_id, channel_id, channel_name, sender_id,
                            sender_name, content, thread_ts, is_thread_parent,
                            contact_id, received_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (composite_id, channel_id, channel_name, sender_id,
                         sender_name, content, thread_ts, is_thread_parent,
                         contact_id, received_at),
                    ))
                    synced += 1

                if statements:
                    execute_many(statements)

                # Update channel last_synced_at
                execute_write(
                    "UPDATE slack_channels SET last_synced_at = datetime('now') WHERE slack_channel_id = ?",
                    (channel_id,),
                )

            except Exception as e:
                failed += 1
                errors.append({"channel": channel_name, "error": str(e)})

        # Only advance the freshness timestamp on a fully-clean sync. If any
        # channel was dropped, leave the timestamp so auto-sync retries instead
        # of waiting out the freshness window.
        if _should_mark_synced(failed):
            execute_many([(
                "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('slack_last_synced', datetime('now'), datetime('now'))",
                (),
            )])

        result = {"synced": synced, "failed": failed, "channels_checked": len(channels)}
        if errors:
            result["errors"] = errors
        return result

    except Exception as e:
        print(f"Slack message sync failed: {e}", file=sys.stderr)
        return {"error": str(e), "synced": synced, "failed": failed}


def sync_slack(token: str | None = None) -> dict:
    """Full Slack sync: channels then messages.

    Args:
        token: Bot access token (fetched automatically if not provided)

    Returns:
        Combined result dict from both sync operations
    """
    token = token or get_bot_token()
    if not token:
        return {"error": "Not connected to Slack."}

    channels_result = sync_channels(token)
    messages_result = sync_messages(token)

    return {
        "channels": channels_result,
        "messages": messages_result,
    }
