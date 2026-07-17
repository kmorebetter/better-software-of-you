Manage automatic background syncing (Gmail, Calendar, Transcripts) at 8am/12pm/6pm **and** a weekday
7:53am morning brief (what needs attention + today's calendar, emailed to you with a refreshed dashboard).

**Subcommands:**
- `on` — Enable the schedule (installs the sync + brief launchd agents)
- `off` — Disable the schedule (removes both agents)
- `status` — Show agent status and recent sync/brief activity
- `run` — Trigger an immediate sync now
- `times` — Show the current schedule

**How it works:** Uses macOS launchd to run the sync script and morning brief at scheduled times, even if Claude Code isn't open. If your Mac is asleep at a scheduled time, the job runs when it wakes up.

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

3. Create the installed plists by copying **both** templates and replacing placeholders — the
   3×/day sync agent AND the morning-brief agent (fresh pull → deterministic render → Signals Engine
   → grounded brief emailed to you + dashboard):
   ```bash
   DATA_DIR="${HOME}/.local/share/software-of-you"
   mkdir -p "${HOME}/Library/LaunchAgents" "${DATA_DIR}/logs"

   for agent in sync brief; do
     sed -e "s|__PLUGIN_ROOT__|${PLUGIN_ROOT}|g" \
         -e "s|__HOME__|${HOME}|g" \
         -e "s|__DATA_DIR__|${DATA_DIR}|g" \
         "${PLUGIN_ROOT}/shared/you.softwareof.${agent}.plist" \
         > "${HOME}/Library/LaunchAgents/you.softwareof.${agent}.plist"
   done
   ```

4. Load both agents (use modern launchctl API):
   ```bash
   DOMAIN_TARGET="gui/$(id -u)"
   for agent in sync brief; do
     launchctl bootout "${DOMAIN_TARGET}/you.softwareof.${agent}" 2>/dev/null || true
     launchctl bootstrap "${DOMAIN_TARGET}" "${HOME}/Library/LaunchAgents/you.softwareof.${agent}.plist"
   done
   ```

5. Confirm to the user:
   > Auto-sync enabled. Gmail, Calendar, and Transcripts will sync at **8:00 AM**, **12:00 PM**, and **6:00 PM** daily.
   > A **morning brief** (what needs your attention + today's calendar) will land in your inbox at **7:53 AM** on weekdays, and your dashboard will refresh with it.
   >
   > Use `/auto-sync status` to check on it, or `/auto-sync off` to disable.

### Subcommand: `off`

1. Unload and remove both agents:
   ```bash
   DOMAIN_TARGET="gui/$(id -u)"
   for agent in sync brief; do
     launchctl bootout "${DOMAIN_TARGET}/you.softwareof.${agent}" 2>/dev/null || true
     rm -f "${HOME}/Library/LaunchAgents/you.softwareof.${agent}.plist"
   done
   ```

2. Confirm:
   > Auto-sync disabled. Background syncing and the morning brief have been turned off. Your data will only sync when you're in a Claude Code session.

### Subcommand: `status`

1. Check whether each agent is installed and loaded:
   ```bash
   ls -la "${HOME}/Library/LaunchAgents/you.softwareof.sync.plist" 2>/dev/null
   ls -la "${HOME}/Library/LaunchAgents/you.softwareof.brief.plist" 2>/dev/null
   launchctl list | grep softwareof 2>/dev/null
   ```

2. Show recent sync + brief activity:
   ```bash
   LOG_DIR="${HOME}/.local/share/software-of-you/logs"
   tail -n 10 "${LOG_DIR}/sync.log" 2>/dev/null
   tail -n 5 "${LOG_DIR}/launchd-brief.log" 2>/dev/null
   ```

3. Present as a clean status report:
   - **Sync agent:** Active / Inactive — 8:00 AM, 12:00 PM, 6:00 PM
   - **Brief agent:** Active / Inactive — 7:53 AM weekdays (email + dashboard)
   - **Recent activity:** last few entries from each log

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
