---
description: Connect your Slack workspace (paste a user token to mirror DMs + allowlisted channels)
allowed-tools: ["Bash", "Read", "AskUserQuestion"]
---

# Connect Slack

Slack mirrors your DMs (always) and any channels you allowlist into the local DB, so they show up in dashboards, contact pages, the timeline, and nudges.

Slack requires a workspace **user token** (`xoxp-…`) — they don't expire, and they read everything *you* can read in Slack. No bot invitations, no OAuth round-trip.

## Step 1: Check current state

```bash
${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/.venv/bin/python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/src')
from software_of_you import slack_auth
import json
data = slack_auth.load_token() or {}
if data.get('access_token'):
    info = slack_auth.auth_test(data['access_token'])
    print(json.dumps({'connected': bool(info.get('ok')), 'team': data.get('team'), 'user': data.get('user'), 'url': data.get('url'), 'error': info.get('error')}))
else:
    print(json.dumps({'connected': False}))
"
```

**If `connected: true`:** Tell the user "Slack is connected to **[team]** as **[user]**." Offer to run a fresh sync (`/auto-sync run`) or list channels (`/slack-channels list`). **Stop.**

**If `connected: false` or token rejected:** Continue.

## Step 2: Walk the user through getting a token

Tell them — exactly this, no embellishment:

> Slack doesn't have a one-click connect for personal user tokens. You'll create a private Slack app for yourself; it takes 2 minutes.
>
> **1.** Go to **https://api.slack.com/apps** and click **Create New App** → **From scratch**.
> **2.** Name it anything (e.g. *"Software of You"*) and pick your workspace.
> **3.** In the left sidebar, click **OAuth & Permissions**.
> **4.** Scroll to **User Token Scopes** (NOT bot scopes) and add these:
>    - `channels:history`, `groups:history`, `im:history`, `mpim:history`
>    - `channels:read`, `groups:read`, `im:read`, `mpim:read`
>    - `users:read`, `users:read.email`
> **5.** Scroll up and click **Install to [Workspace]**, then approve.
> **6.** Copy the **User OAuth Token** (starts with `xoxp-`).
>
> Paste it here when ready.

## Step 3: Save and verify

When the user pastes a token, run:

```bash
${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/.venv/bin/python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/src')
from software_of_you import slack_auth
import json
print(json.dumps(slack_auth.save_token('PASTE_TOKEN_HERE')))
"
```

Replace `PASTE_TOKEN_HERE` with what they pasted.

**On success** (`{"ok": true, "team": "...", ...}`): tell them "Connected to **[team]** as **[user]**. Pulling your DMs and user list now — first sync may take a minute."

**On failure** (`{"ok": false, "error": "..."}`): explain the error and ask them to check the token. Common causes: didn't click Install, copied the bot token instead of user token, scopes missing.

## Step 4: First sync

```bash
${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/.venv/bin/python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/src')
from software_of_you.slack_sync import sync_slack
import json
print(json.dumps(sync_slack(), indent=2))
"
```

Report the results conversationally:
- Users synced + how many auto-linked to existing contacts
- Channels found (split by type: DMs, MPIMs, public, private)
- Messages mirrored

Then suggest:
- `/slack-channels list` — see what's available
- `/slack-channels add #channel-name` — start mirroring a channel

## Step 5: Make sure auto-sync is on

```bash
ls "${HOME}/Library/LaunchAgents/you.softwareof.sync.plist" 2>/dev/null
```

If the agent isn't installed, run `/auto-sync on`. The 8am/12pm/6pm sync now picks up Slack alongside Gmail and Calendar.

## Disconnecting

```bash
${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/.venv/bin/python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/src')
from software_of_you import slack_auth
slack_auth.revoke_token()
print('disconnected')
"
```

This removes the local token. Already-synced messages are kept (delete them via SQL if you really want them gone).
