---
description: Show system status and installed modules
allowed-tools: ["Bash", "Read"]
---

# System Status

Query the database at `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db` and present a clear status overview.

Run these queries:

1. **Installed modules:** `SELECT name, version, installed_at, enabled FROM modules;`
2. **Contact count:** `SELECT COUNT(*) FROM contacts WHERE status = 'active';`
3. **Recent activity:** `SELECT * FROM activity_log ORDER BY created_at DESC LIMIT 5;`

If the project-tracker module is installed (check modules table), also query:
- `SELECT COUNT(*) FROM projects WHERE status IN ('active', 'planning');`
- `SELECT status, COUNT(*) FROM tasks GROUP BY status;`

If the CRM module is installed, also query:
- `SELECT COUNT(*) FROM follow_ups WHERE status = 'pending' AND due_date <= date('now', '+7 days');`

Read module manifests from `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/modules/*/manifest.json` to identify active cross-module enhancements (where both modules in an enhancement pair are installed).

Present the results as a clean, scannable summary. Group by: Modules, Data Counts, Recent Activity, Active Enhancements. If any section is empty, skip it — don't show zeroes for modules that aren't installed.
