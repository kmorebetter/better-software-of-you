---
description: Manage which Slack channels are mirrored — list, allowlist, or remove
allowed-tools: ["Bash"]
argument-hint: [list | add #channel | remove #channel]
---

# Slack Channels

DMs and MPIMs (group DMs) are **always** mirrored. Public and private channels are mirrored **only when you allowlist them** — Slack channels can be huge, so this keeps the noise out.

Parse `$ARGUMENTS`:
- empty or `list` → Subcommand A
- `add <name>` → Subcommand B
- `remove <name>` → Subcommand C

---

## A — List channels

```bash
sqlite3 -header -column "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" <<'SQL'
SELECT
  CASE channel_type
    WHEN 'im' THEN 'DM'
    WHEN 'mpim' THEN 'Group DM'
    WHEN 'private_channel' THEN 'Private'
    WHEN 'public_channel' THEN 'Public'
  END AS type,
  COALESCE(sc.name, '(unnamed)') AS name,
  CASE
    WHEN sc.channel_type IN ('im','mpim') THEN 'always'
    WHEN sc.is_allowlisted = 1 THEN 'on'
    ELSE 'off'
  END AS mirroring,
  (SELECT COUNT(*) FROM slack_messages sm WHERE sm.channel_id = sc.id) AS messages,
  CASE
    WHEN sc.last_synced_ts IS NOT NULL
    THEN datetime(CAST(sc.last_synced_ts AS REAL), 'unixepoch')
    ELSE '—'
  END AS last_seen
FROM slack_channels sc
WHERE sc.is_archived = 0
ORDER BY
  CASE sc.channel_type WHEN 'im' THEN 0 WHEN 'mpim' THEN 1 WHEN 'private_channel' THEN 2 ELSE 3 END,
  sc.name;
SQL
```

Present as a markdown table grouped by type. End with: "Use `/slack-channels add #name` to start mirroring a public/private channel."

If the table is empty, the user hasn't synced yet — point them at `/slack-setup`.

---

## B — Allowlist a channel

The argument may be `#marketing`, `marketing`, or a channel ID like `C0AEDMVJ938`. Strip the leading `#` if present.

```bash
NAME="<name-from-argument-without-hash>"
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" <<SQL
SELECT id, slack_channel_id, name, channel_type, is_allowlisted
FROM slack_channels
WHERE (name = '${NAME}' OR slack_channel_id = '${NAME}')
  AND channel_type IN ('public_channel', 'private_channel');
SQL
```

**No match** → say "I don't see a channel named `[name]` synced yet. Run `/auto-sync run` if you just joined it, or check the spelling against `/slack-channels list`."

**Match found**:
```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" <<SQL
UPDATE slack_channels
SET is_allowlisted = 1, allowlisted_at = datetime('now')
WHERE name = '${NAME}' OR slack_channel_id = '${NAME}';

INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
SELECT 'slack_channel', id, 'allowlisted',
       json_object('name', name, 'channel_id', slack_channel_id),
       datetime('now')
FROM slack_channels
WHERE name = '${NAME}' OR slack_channel_id = '${NAME}';
SQL
```

Then trigger a sync to pull recent history (last 90 days):
```bash
${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/.venv/bin/python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/src')
from software_of_you.slack_sync import sync_slack
import json
print(json.dumps(sync_slack(), indent=2))
"
```

Report: "Allowlisted **#[name]**. Pulled [N] messages from the last 90 days."

---

## C — Remove from allowlist

```bash
NAME="<name-from-argument-without-hash>"
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" <<SQL
UPDATE slack_channels
SET is_allowlisted = 0, allowlisted_at = NULL
WHERE (name = '${NAME}' OR slack_channel_id = '${NAME}')
  AND channel_type IN ('public_channel', 'private_channel');

INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
SELECT 'slack_channel', id, 'unallowlisted',
       json_object('name', name, 'channel_id', slack_channel_id),
       datetime('now')
FROM slack_channels
WHERE name = '${NAME}' OR slack_channel_id = '${NAME}';
SQL
```

Confirm: "Stopped mirroring **#[name]**. Existing messages are kept — they just won't be updated."

If they want to delete already-synced messages too, ask first, then run:
```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" \
  "DELETE FROM slack_messages WHERE channel_id IN (SELECT id FROM slack_channels WHERE name = '${NAME}');"
```
