---
description: Connect your Google account (Gmail + Calendar)
allowed-tools: ["Bash", "Read", "Write"]
---

# Connect Google Account

This sets up Gmail and Google Calendar access for Software of You. Credentials are built in — the user just needs to sign in. Supports multiple Google accounts.

## Step 1: Check Connected Accounts

Run:
```
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/google_auth.py" accounts
```

Parse the JSON response.

**If accounts are connected:** Show a table:

| Account | Label | Primary | Last Synced |
|---------|-------|---------|-------------|
| kmo@betterstory.co | betterstory.co | Yes | 2 hours ago |
| kmo@gmail.com | gmail.com | No | 2 hours ago |

Then ask: "Want to add another Google account, or is this all set?"

If the user says it's fine, suggest `/gmail` and `/calendar`. **Stop here.**

**If no accounts connected:** Check for a legacy token:
```
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/google_auth.py" status
```

If legacy token exists, it will auto-migrate on first `accounts` call. If truly no token exists, continue to Step 2.

## Step 2: Run the OAuth Flow

Tell the user: "Opening Google sign-in in your browser — just sign in and click Allow."

Run:
```
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/google_auth.py" auth
```

This opens the browser, the user authenticates, and the token is saved automatically. The account email is auto-detected and registered in the database.

## Step 3: Verify

Run:
```
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/google_auth.py" accounts
```

Confirm: "Connected as [email]. Label: [domain]. Emails and calendar will sync from this account."

If this is the first account, it's automatically set as primary.

Then suggest:
- `/gmail` — see your recent emails
- `/calendar` — see your upcoming events
- If they want to add another account: "Run `/google-setup` again to add another Google account."

## If Something Goes Wrong

- **"Port 8089 already in use"** → another process is using that port. Ask the user to close it or wait a moment.
- **"Token exchange failed"** → try running `/google-setup` again. If it keeps failing, the OAuth app may need its consent screen published in Google Cloud Console.
- **"Access denied"** → the user didn't click Allow. Ask them to try again.

## Scope Upgrade (Google Docs access)

If the user gets a 403 error when fetching Google Docs (e.g., from `/sync-transcripts`), they need to re-authorize with the new `documents.readonly` scope.

Tell the user: "I need read access to Google Docs for transcript fetching. Re-running the sign-in flow will add this permission."

Then run the full auth flow from Step 2 above. The `prompt=consent` parameter forces Google to re-show the consent screen with all scopes, including the new Docs scope.

## Revoking Access

To disconnect a specific account:
```
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/google_auth.py" revoke <email>
```

This revokes the OAuth token, removes the local token file, and marks the account as disconnected in the database. Emails and calendar events already synced are preserved.

## Advanced: Custom OAuth Credentials

If a user wants to use their own Google Cloud project instead of the built-in one, they can place a `google_credentials.json` file in `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/config/`. This overrides the embedded defaults.
