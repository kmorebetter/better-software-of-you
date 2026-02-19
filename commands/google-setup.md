---
description: Connect your Google account (Gmail + Calendar)
allowed-tools: ["Bash", "Read", "Write"]
---

# Connect Google Account

This sets up Gmail and Google Calendar access for Software of You.

## Step 1: Check Current Status

Run:
```
python3 "${CLAUDE_PLUGIN_ROOT}/shared/google_auth.py" status
```

If already authenticated, tell the user: "Your Google account is already connected ([email]). Want to reconnect or revoke access?"

## Step 2: Check for Credentials

Check if `${CLAUDE_PLUGIN_ROOT}/config/google_credentials.json` exists.

**If credentials exist** → skip to Step 3.

**If no credentials** → walk the user through getting them:

Tell the user:

"To connect Gmail and Calendar, you need Google OAuth credentials. This is a one-time setup that takes about 2 minutes:

1. Go to https://console.cloud.google.com/apis/credentials
2. Create a new project (or use an existing one)
3. Click **Create Credentials** → **OAuth client ID**
4. Choose **Desktop app** as the application type
5. Name it anything (e.g., 'Software of You')
6. Click **Create**
7. Click **Download JSON** on the credential you just created
8. Tell me where you saved the file, or paste the contents here

You also need to enable the Gmail and Calendar APIs:
- https://console.cloud.google.com/apis/library/gmail.googleapis.com
- https://console.cloud.google.com/apis/library/calendar-json.googleapis.com

Click **Enable** on each one."

When the user provides the credentials (file path or pasted JSON):
- Read/parse the JSON
- Save it to `${CLAUDE_PLUGIN_ROOT}/config/google_credentials.json`
- Make sure the `config/` directory exists first

## Step 3: Run the OAuth Flow

Tell the user: "Opening Google in your browser. Sign in and click **Allow** — I'll wait here."

Run:
```
python3 "${CLAUDE_PLUGIN_ROOT}/shared/google_auth.py" auth
```

This opens the browser, user authenticates, and the token is saved automatically.

## Step 4: Verify

Run status check again:
```
python3 "${CLAUDE_PLUGIN_ROOT}/shared/google_auth.py" status
```

Confirm: "Google connected as [email]. Gmail and Calendar are ready to use.

Try:
- `/gmail` — see your recent emails
- `/email <contact>` — draft and send an email
- `/calendar` — see your upcoming events"

## If Something Goes Wrong

- **"Port 8089 already in use"** → another process is using that port. Ask the user to close it or wait a moment.
- **"Token exchange failed"** → the credentials might be wrong. Ask the user to re-download them.
- **"Access denied"** → the user didn't click Allow, or the APIs aren't enabled.
