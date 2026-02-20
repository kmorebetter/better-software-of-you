---
description: Initialize or verify Software of You installation
allowed-tools: ["Bash", "Read", "Write"]
---

# Software of You — Setup

## Step 1: Initialize Database

Create the data directory and run all migrations:
```bash
mkdir -p "${CLAUDE_PLUGIN_ROOT}/data"
for f in "${CLAUDE_PLUGIN_ROOT}"/data/migrations/*.sql; do
  sqlite3 "${CLAUDE_PLUGIN_ROOT}/data/soy.db" < "$f"
done
```

## Step 2: Verify

Check what's installed:
```sql
SELECT name, display_name, version FROM modules WHERE enabled = 1;
SELECT COUNT(*) as contacts FROM contacts;
SELECT COUNT(*) as projects FROM projects;
```

## Step 3: Report

Tell the user:

**If fresh install (no data):**
"Software of You is ready. You have [N] modules installed: [list]. Your database is at `data/soy.db`.

Get started:
- **Add a contact**: just tell me about someone — name, email, company
- **Connect Google**: run `/google-setup` to sync Gmail and Calendar
- **See what's possible**: try `/help-soy`"

**If existing install (has data):**
"Everything looks good. [N] contacts, [N] projects, [N] modules installed. Database at `data/soy.db`.

Google: [connected as email / not connected — run `/google-setup`]"

Check Google status:
```
python3 "${CLAUDE_PLUGIN_ROOT}/shared/google_auth.py" status 2>/dev/null
```
