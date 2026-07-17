---
name: health-monitor
description: Run system health checks, auto-repair issues, and generate health dashboard. Use for /patrol, /health, or when diagnosing system problems.
---

# Health Monitor

Self-healing health checks for Software of You. Validates infrastructure, auto-repairs what it can, and generates a visual health dashboard.

## When to Use

- `/patrol` — run all checks, auto-fix issues, generate health dashboard
- `/health` — quick status check (read-only, no repairs)
- When something seems broken (missing views, stale data, auth errors)
- Before generating views or dashboards (validates infrastructure first)

## How It Works

Run the health check script:

```bash
# Full patrol with auto-repair + dashboard
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/scripts/health_check.py" --fix --dashboard

# Read-only check
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/scripts/health_check.py"

# JSON output for programmatic use
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/scripts/health_check.py" --fix --json
```

## What It Checks

| Check | What | Auto-Fix |
|-------|------|----------|
| **Database integrity** | 33 required tables + 8 required views exist, SQLite integrity_check passes, no FK violations | Runs bootstrap to recreate missing tables/views |
| **OAuth tokens** | Token files exist, not expired, have refresh tokens | Auto-refreshes expired tokens |
| **HTML views** | Core views (dashboard, contacts, week-view, email-hub, nudges, timeline) exist with content | Flags missing views in `soy_meta` for regeneration |
| **Backups** | Backup directory has files, latest is < 48h old | Creates fresh backup |
| **Sync freshness** | Gmail, Calendar, Transcripts synced within 60m | Reports staleness (sync via pipeline) |

## After Patrol

If the patrol flags HTML views for regeneration, regenerate them:

```sql
SELECT value FROM soy_meta WHERE key = 'views_need_regeneration';
```

If this returns a list, generate those views using the dashboard-generation skill.

## Backup Enforcement

Before any destructive database operation (wipe, reset, drop), always call:

```python
from scripts.health_check import enforce_backup_before_destructive
enforce_backup_before_destructive("database_wipe")
```

Or via bash:
```bash
python3 -c "from scripts.health_check import enforce_backup_before_destructive; enforce_backup_before_destructive('your_operation')"
```

## Health Dashboard

The patrol generates `output/health.html` showing:
- Overall system status (Healthy / Needs Attention / Critical)
- Per-check status with details
- OAuth token expiry times
- Sync freshness per service
- Auto-repairs performed
