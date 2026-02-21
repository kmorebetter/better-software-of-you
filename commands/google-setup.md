---
description: Connect your Google account (Gmail + Calendar)
allowed-tools: ["Bash", "Read", "Write"]
---

# Connect Google Account

This sets up Gmail and Google Calendar access for Software of You. Credentials are built in — the user just needs to sign in.

## Step 1: Check Current Status

Run:
```
python3 "${CLAUDE_PLUGIN_ROOT}/shared/google_auth.py" status
```

If already authenticated and token is valid, tell the user: "Your Google account is connected as [email]. Gmail and Calendar are ready." Then suggest `/gmail` and `/calendar`. **Stop here.**

If authenticated but token expired, skip to Step 2 (re-auth will refresh it).

## Step 2: Run the OAuth Flow

Tell the user: "Opening Google sign-in in your browser — just sign in and click Allow."

Run:
```
python3 "${CLAUDE_PLUGIN_ROOT}/shared/google_auth.py" auth
```

This opens the browser, the user authenticates, and the token is saved automatically.

## Step 3: Verify

Run status check:
```
python3 "${CLAUDE_PLUGIN_ROOT}/shared/google_auth.py" status
```

Confirm: "Connected as [email]. Gmail and Calendar are ready.

Try:
- `/gmail` — see your recent emails
- `/calendar` — see your upcoming events"

## If Something Goes Wrong

- **"Port 8089 already in use"** → another process is using that port. Ask the user to close it or wait a moment.
- **"Token exchange failed"** → try running `/google-setup` again. If it keeps failing, the OAuth app may need its consent screen published in Google Cloud Console.
- **"Access denied"** → the user didn't click Allow. Ask them to try again.

## Scope Upgrade (Google Docs access)

If the user gets a 403 error when fetching Google Docs (e.g., from `/sync-transcripts`), they need to re-authorize with the new `documents.readonly` scope.

Tell the user: "I need read access to Google Docs for transcript fetching. Re-running the sign-in flow will add this permission."

Then run the full auth flow from Step 2 above. The `prompt=consent` parameter forces Google to re-show the consent screen with all scopes, including the new Docs scope.

## Advanced: Custom OAuth Credentials

If a user wants to use their own Google Cloud project instead of the built-in one, they can place a `google_credentials.json` file in `${CLAUDE_PLUGIN_ROOT}/config/`. This overrides the embedded defaults.
