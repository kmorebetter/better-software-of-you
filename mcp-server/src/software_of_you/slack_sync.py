"""Slack sync — mirrors DMs + allowlisted channels into the local DB.

Schema lives in data/migrations/022_slack_module.sql. Token is read via
``software_of_you.slack_auth``.

Strategy:
  - users.list  → upsert slack_users; auto-link to contacts by email
  - users.conversations → upsert slack_channels (preserves is_allowlisted)
  - For each DM/MPIM (always) + allowlisted public/private channel:
      - First sync (no last_synced_ts): full history for DMs, last 90d for channels
      - Subsequent: incremental from last_synced_ts forward
      - INSERT OR IGNORE on (channel_id, slack_ts) — Slack's ts is the dedup key

Rate limits: Slack returns 429 with Retry-After. We back off and retry once.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from software_of_you.db import execute, execute_many, execute_write
from software_of_you import slack_auth

SLACK_API = "https://slack.com/api"
LINK_RE = re.compile(r"<https?://[^>|]+(\|[^>]+)?>")
DEFAULT_CHANNEL_LOOKBACK_DAYS = 90


def _api_get(method: str, token: str, params: dict | None = None, retries: int = 1) -> dict:
    """Authenticated GET to slack.com/api/<method>. Backs off once on 429."""
    url = f"{SLACK_API}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429 and retries > 0:
            wait = int(e.headers.get("Retry-After", "5"))
            time.sleep(wait)
            return _api_get(method, token, params, retries - 1)
        raise


def _paginate(method: str, token: str, params: dict, list_key: str) -> list[dict]:
    """Walk Slack cursor pagination until exhausted."""
    items: list[dict] = []
    cursor = ""
    while True:
        page_params = dict(params)
        if cursor:
            page_params["cursor"] = cursor
        data = _api_get(method, token, page_params)
        if not data.get("ok"):
            err = data.get("error", "unknown")
            raise RuntimeError(f"Slack API error on {method}: {err}")
        items.extend(data.get(list_key, []))
        cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            return items


def _ts_to_iso(ts: str) -> str:
    """Slack ts ('1774869246.329569') → ISO8601 UTC."""
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


def _build_permalink(team_url: str, channel_id: str, ts: str) -> str:
    if not team_url:
        return ""
    return f"{team_url.rstrip('/')}/archives/{channel_id}/p{ts.replace('.', '')}"


# ── User sync ────────────────────────────────────────────────────────────


def sync_users(token: str, self_user_id: str | None = None) -> dict:
    users = _paginate("users.list", token, {"limit": 200}, "members")

    statements = []
    linked = 0
    for u in users:
        uid = u.get("id")
        if not uid:
            continue
        profile = u.get("profile", {})
        email = profile.get("email") or ""
        is_bot = 1 if (u.get("is_bot") or uid == "USLACKBOT") else 0
        is_self = 1 if uid == self_user_id else 0
        deleted = 1 if u.get("deleted") else 0

        contact_id = None
        if email:
            rows = execute("SELECT id FROM contacts WHERE email = ?", (email,))
            if rows:
                contact_id = rows[0]["id"]
                linked += 1

        statements.append((
            """INSERT INTO slack_users
               (slack_user_id, name, real_name, display_name, email, title, contact_id,
                is_bot, is_self, profile_image, tz, deleted, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(slack_user_id) DO UPDATE SET
                 name=excluded.name, real_name=excluded.real_name,
                 display_name=excluded.display_name, email=excluded.email,
                 title=excluded.title,
                 contact_id=COALESCE(excluded.contact_id, slack_users.contact_id),
                 is_bot=excluded.is_bot, is_self=excluded.is_self,
                 profile_image=excluded.profile_image, tz=excluded.tz,
                 deleted=excluded.deleted, synced_at=datetime('now')""",
            (uid, u.get("name"), profile.get("real_name"), profile.get("display_name"),
             email or None, profile.get("title") or None, contact_id,
             is_bot, is_self, profile.get("image_72") or None, u.get("tz"), deleted),
        ))

    if statements:
        execute_many(statements)

    return {"users": len(users), "contacts_linked": linked}


# ── Channel sync ─────────────────────────────────────────────────────────


def sync_channels(token: str) -> dict:
    """Pull all conversations the user is in. Preserves is_allowlisted on update."""
    convos = _paginate(
        "users.conversations",
        token,
        {
            "types": "im,mpim,public_channel,private_channel",
            "limit": 200,
            "exclude_archived": "true",
        },
        "channels",
    )

    statements = []
    counts = {"im": 0, "mpim": 0, "public_channel": 0, "private_channel": 0}
    for c in convos:
        cid = c.get("id")
        if not cid:
            continue
        if c.get("is_im"):
            ctype = "im"
        elif c.get("is_mpim"):
            ctype = "mpim"
        elif c.get("is_private"):
            ctype = "private_channel"
        else:
            ctype = "public_channel"
        counts[ctype] += 1

        statements.append((
            """INSERT INTO slack_channels
               (slack_channel_id, name, channel_type, dm_user_id, member_count,
                is_archived, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(slack_channel_id) DO UPDATE SET
                 name=excluded.name, channel_type=excluded.channel_type,
                 dm_user_id=COALESCE(excluded.dm_user_id, slack_channels.dm_user_id),
                 member_count=excluded.member_count,
                 is_archived=excluded.is_archived, synced_at=datetime('now')""",
            (cid, c.get("name") or None, ctype,
             c.get("user") if ctype == "im" else None,
             c.get("num_members"),
             1 if c.get("is_archived") else 0),
        ))

    if statements:
        execute_many(statements)

    return counts


# ── Message sync ─────────────────────────────────────────────────────────


def _channels_to_sync() -> list[dict]:
    rows = execute(
        """SELECT id, slack_channel_id, channel_type, last_synced_ts, name
           FROM slack_channels
           WHERE is_archived = 0
             AND (channel_type IN ('im','mpim') OR is_allowlisted = 1)"""
    )
    return [dict(r) for r in rows]


def _self_user_id(token: str) -> str | None:
    data = slack_auth.load_token() or {}
    if data.get("user_id"):
        return data["user_id"]
    info = slack_auth.auth_test(token)
    return info.get("user_id") if info.get("ok") else None


def _team_url() -> str:
    data = slack_auth.load_token() or {}
    return data.get("url") or ""


def sync_channel_messages(
    token: str, channel: dict, self_user_id: str, team_url: str,
) -> dict:
    cid_pk = channel["id"]
    cid = channel["slack_channel_id"]
    ctype = channel["channel_type"]
    last_ts = channel.get("last_synced_ts")

    if last_ts:
        oldest = last_ts
    elif ctype in ("im", "mpim"):
        oldest = "0"  # Full DM history on first sync
    else:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=DEFAULT_CHANNEL_LOOKBACK_DAYS)
        oldest = str(cutoff.timestamp())

    params = {"channel": cid, "limit": 200, "oldest": oldest}
    try:
        messages = _paginate("conversations.history", token, params, "messages")
    except RuntimeError as e:
        return {"channel": cid, "name": channel.get("name"), "error": str(e), "synced": 0}

    statements = []
    max_ts = last_ts or "0"
    for m in messages:
        if m.get("subtype") in ("channel_join", "channel_leave", "bot_add", "bot_remove"):
            continue
        ts = m.get("ts")
        if not ts:
            continue
        if float(ts) > float(max_ts):
            max_ts = ts

        sender = m.get("user") or m.get("bot_id") or ""
        text = m.get("text", "")
        thread_ts = m.get("thread_ts")
        has_link = 1 if LINK_RE.search(text) else 0
        has_file = 1 if m.get("files") else 0

        contact_id = None
        if sender:
            rows = execute(
                "SELECT contact_id FROM slack_users WHERE slack_user_id = ?",
                (sender,),
            )
            if rows and rows[0]["contact_id"]:
                contact_id = rows[0]["contact_id"]

        direction = "outbound" if sender == self_user_id else "inbound"
        permalink = _build_permalink(team_url, cid, ts)

        reactions = m.get("reactions")
        reactions_json = json.dumps([
            {"name": r.get("name"), "count": r.get("count")} for r in reactions
        ]) if reactions else None

        statements.append((
            """INSERT OR IGNORE INTO slack_messages
               (slack_ts, channel_id, slack_user_id, contact_id, direction,
                text, thread_ts, has_link, has_file, reactions, permalink, sent_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ts, cid_pk, sender or None, contact_id, direction,
             text, thread_ts, has_link, has_file, reactions_json,
             permalink or None, _ts_to_iso(ts)),
        ))

    if statements:
        execute_many(statements)

    if max_ts != (last_ts or "0"):
        execute_write(
            "UPDATE slack_channels SET last_synced_ts = ? WHERE id = ?",
            (max_ts, cid_pk),
        )

    return {"channel": cid, "synced": len(statements), "name": channel.get("name")}


# ── Top-level orchestrator ───────────────────────────────────────────────


def sync_slack() -> dict:
    """Full Slack sync. Safe to call when no token is configured."""
    token = slack_auth.get_token()
    if not token:
        return {"status": "skipped", "reason": "Slack not connected"}

    self_id = _self_user_id(token)
    team_url = _team_url()

    try:
        users_result = sync_users(token, self_user_id=self_id)
        channels_result = sync_channels(token)
        per_channel = []
        total_msgs = 0
        for ch in _channels_to_sync():
            r = sync_channel_messages(token, ch, self_id or "", team_url)
            per_channel.append(r)
            total_msgs += r.get("synced", 0)

        execute_write(
            "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) "
            "VALUES ('slack_last_synced', datetime('now'), datetime('now'))",
        )

        return {
            "status": "ok",
            "users": users_result,
            "channels": channels_result,
            "messages_synced": total_msgs,
            "channel_results": per_channel,
        }
    except Exception as e:
        print(f"Slack sync failed: {e}", file=sys.stderr)
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    print(json.dumps(sync_slack(), indent=2))
