---
description: Quick read-only system health check (no repairs)
allowed-tools: ["Bash", "Read"]
---

# Health — Read-Only Status Check

Run the health check in read-only mode (no repairs, no dashboard):

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/scripts/health_check.py"
```

Report the results conversationally — overall status (Healthy / Needs Attention / Critical)
and any issues per check (database, OAuth, HTML views, backups, sync freshness). Do not
attempt any repairs; if something needs fixing, suggest running `/patrol`.

See the `health-monitor` skill for details on each check.
