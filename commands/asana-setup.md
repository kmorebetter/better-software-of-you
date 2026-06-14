---
description: Connect your Asana workspaces (paste a Personal Access Token to mirror tasks across all projects)
allowed-tools: ["Bash", "Read"]
---

# Connect Asana

Asana mirrors your workspaces, projects, users, and **tasks across every project you can see** into the local DB. The first sync grabs the last 90 days of task activity; subsequent syncs are incremental via `modified_since`.

Asana uses long-lived **Personal Access Tokens (PATs)** — generated from your Asana account. No OAuth round-trip. One PAT covers every workspace you're in.

## Step 1: Check current state

```bash
${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/.venv/bin/python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/src')
from software_of_you import asana_auth
import json
data = asana_auth.load_token() or {}
if data.get('access_token'):
    info = asana_auth.me(data['access_token'])
    print(json.dumps({
        'connected': bool(info.get('ok')),
        'user': data.get('user_name'),
        'email': data.get('user_email'),
        'workspaces': data.get('workspaces', []),
        'error': info.get('error'),
    }))
else:
    print(json.dumps({'connected': False}))
"
```

**If `connected: true`:** Tell the user "Asana is connected as **[name]**, with access to: **[workspace names]**." Offer `/auto-sync run` to refresh, or jump to whatever they're after. **Stop.**

**If not connected:** Continue.

## Step 2: Walk the user through getting a PAT

Tell them — exactly this, no embellishment:

> Asana doesn't have a one-click connect for personal tokens, but it's quick:
>
> **1.** Go to **https://app.asana.com/0/my-apps**
> **2.** Scroll to **Personal access tokens** and click **+ New access token**.
> **3.** Name it anything (e.g. *"Software of You"*) and pick a service (any is fine for personal use).
> **4.** Click **Create token**.
> **5.** Copy the token. **Asana shows it only once** — once you close that dialog, you can't see it again.
>
> Paste it here when ready.

## Step 3: Save and verify

When the user pastes a token, run:

```bash
${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/.venv/bin/python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/src')
from software_of_you import asana_auth
import json
print(json.dumps(asana_auth.save_token('PASTE_TOKEN_HERE')))
"
```

Replace `PASTE_TOKEN_HERE` with what they pasted.

**On success** (`{"ok": true, "user_name": "...", "workspaces": [...]}`): tell them "Connected as **[user_name]**. I see **N** workspace(s): [list]. Pulling tasks now — first sync may take a minute since it's grabbing the last 90 days."

**On failure** (`{"ok": false, "error": "..."}`): explain the error and ask them to verify. Common cause: token typo (PATs are very long).

## Step 4: First sync

```bash
${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/.venv/bin/python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/src')
from software_of_you.asana_sync import sync_asana
import json
result = sync_asana()
# Trim per-project list for readability if it's huge
if 'workspaces' in result:
    print(json.dumps({k: v for k, v in result.items() if k not in ('workspaces',)}, indent=2))
    print('---workspaces---')
    print(json.dumps(result['workspaces'], indent=2))
else:
    print(json.dumps(result, indent=2))
"
```

Report conversationally:
- Workspaces found (named)
- Users synced + how many auto-linked to existing contacts
- Projects pulled (per workspace)
- Tasks touched in this sync window

Then mention the new nudges that just became live:
- Your overdue Asana tasks (URGENT)
- Tasks you delegated that are overdue (URGENT)
- Tasks due in the next 3 days (SOON)
- Unassigned tasks (AWARENESS)

Suggest:
- `/nudges` to see what surfaced
- Linking a soy project to its Asana counterpart: `UPDATE projects SET linked_asana_project_gid = '<asana_gid>' WHERE id = <soy_project_id>;` (or use `/project edit` if available)

## Step 5: Make sure auto-sync is on

```bash
ls "${HOME}/Library/LaunchAgents/you.softwareof.sync.plist" 2>/dev/null
```

If the agent isn't installed, run `/auto-sync on`. The 8am/12pm/6pm sync now picks up Asana alongside Gmail, Calendar, and Slack.

## Disconnecting

```bash
${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/.venv/bin/python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT:-$(pwd)}/mcp-server/src')
from software_of_you import asana_auth
asana_auth.revoke_token()
print('disconnected')
"
```

Already-synced data is kept (delete via SQL if you really want it gone).
