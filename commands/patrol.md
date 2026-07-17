---
description: Run system health checks, auto-repair issues, and open the health dashboard
allowed-tools: ["Bash", "Read"]
---

# Patrol — Health Check & Auto-Repair

Run the self-healing health check with auto-repair and dashboard generation:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/scripts/health_check.py" --fix --dashboard
```

Then report the results conversationally — overall status (Healthy / Needs Attention /
Critical), which checks passed, any issues found, and any auto-repairs performed. Don't dump
raw JSON; summarize what matters.

If the run flagged HTML views for regeneration, check the flag and offer to rebuild them:

```sql
SELECT value FROM soy_meta WHERE key = 'views_need_regeneration';
```

If it returns a list, offer to regenerate those views using the dashboard-generation skill.

Finally, open the health dashboard:

```bash
open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/health.html"
```

See the `health-monitor` skill for what each check covers and how repairs work.
