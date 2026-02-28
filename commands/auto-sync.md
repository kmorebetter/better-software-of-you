Manage automatic background syncing (Gmail, Calendar, Transcripts) on a schedule — 3x/day at 8am, 12pm, 6pm.

**Subcommands:**
- `on` — Enable the auto-sync schedule (installs launchd agent)
- `off` — Disable the auto-sync schedule (removes launchd agent)
- `status` — Show schedule status and recent sync log
- `run` — Trigger an immediate sync now
- `times` — Show the current sync schedule

**How it works:** Uses macOS launchd to run the sync script at scheduled times, even if Claude Code isn't open. If your Mac is asleep at a scheduled time, the sync runs when it wakes up.

---

## Implementation

Parse the user's subcommand from `$ARGUMENTS`. Default to `status` if no argument given.

### Subcommand: `on`

1. Resolve the plugin root:
   ```bash
   PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(pwd)}"
   ```

2. Ensure the sync script is executable:
   ```bash
   chmod +x "${PLUGIN_ROOT}/shared/scheduled_sync.sh"
   ```

3. Create the installed plist by copying the template and replacing placeholders:
   ```bash
   PLIST_SRC="${PLUGIN_ROOT}/shared/you.softwareof.sync.plist"
   PLIST_DST="${HOME}/Library/LaunchAgents/you.softwareof.sync.plist"
   DATA_DIR="${HOME}/.local/share/software-of-you"

   mkdir -p "${HOME}/Library/LaunchAgents"
   mkdir -p "${DATA_DIR}/logs"

   sed -e "s|__PLUGIN_ROOT__|${PLUGIN_ROOT}|g" \
       -e "s|__HOME__|${HOME}|g" \
       -e "s|__DATA_DIR__|${DATA_DIR}|g" \
       "${PLIST_SRC}" > "${PLIST_DST}"
   ```

4. Load the agent (use modern launchctl API):
   ```bash
   DOMAIN_TARGET="gui/$(id -u)"
   launchctl bootout "${DOMAIN_TARGET}/you.softwareof.sync" 2>/dev/null || true
   launchctl bootstrap "${DOMAIN_TARGET}" "${PLIST_DST}"
   ```

5. Confirm to the user:
   > Auto-sync enabled. Gmail, Calendar, and Transcripts will sync at **8:00 AM**, **12:00 PM**, and **6:00 PM** daily.
   >
   > Use `/auto-sync status` to check on it, or `/auto-sync off` to disable.

### Subcommand: `off`

1. Unload and remove:
   ```bash
   PLIST_DST="${HOME}/Library/LaunchAgents/you.softwareof.sync.plist"
   DOMAIN_TARGET="gui/$(id -u)"
   launchctl bootout "${DOMAIN_TARGET}/you.softwareof.sync" 2>/dev/null || true
   rm -f "${PLIST_DST}"
   ```

2. Confirm:
   > Auto-sync disabled. Background syncing has been turned off. Your data will only sync when you're in a Claude Code session.

### Subcommand: `status`

1. Check if the plist is installed:
   ```bash
   PLIST_DST="${HOME}/Library/LaunchAgents/you.softwareof.sync.plist"
   ls -la "${PLIST_DST}" 2>/dev/null
   launchctl list | grep softwareof 2>/dev/null
   ```

2. Show last 5 sync log entries:
   ```bash
   LOG_FILE="${HOME}/.local/share/software-of-you/logs/sync.log"
   tail -n 10 "${LOG_FILE}" 2>/dev/null
   ```

3. Present as a clean status report:
   - **Schedule:** Active / Inactive
   - **Next sync times:** 8:00 AM, 12:00 PM, 6:00 PM
   - **Recent syncs:** show last few entries from the log

### Subcommand: `run`

1. Run the sync script directly:
   ```bash
   PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(pwd)}"
   bash "${PLUGIN_ROOT}/shared/scheduled_sync.sh"
   ```

2. Show the result from the log:
   ```bash
   tail -n 5 "${HOME}/.local/share/software-of-you/logs/sync.log"
   ```

3. Present the results conversationally — how many emails synced, calendar events updated, transcripts found.

### Subcommand: `times`

Show the current schedule:

> **Auto-sync schedule:**
> | Time | Purpose |
> |------|---------|
> | 8:00 AM | Morning sync — catch overnight emails and calendar updates |
> | 12:00 PM | Midday sync — pick up morning activity |
> | 6:00 PM | Evening sync — capture afternoon emails and meetings |
>
> Syncs: Gmail (last 7 days), Calendar (±14 days), Gemini transcripts
