#!/usr/bin/env python3
"""Software of You — Self-Healing Health Monitor.

Validates system integrity, auto-repairs what it can, and generates
a health dashboard. Designed to run autonomously via /patrol or cron.

Usage:
    python3 scripts/health_check.py              # Run all checks, print report
    python3 scripts/health_check.py --fix        # Auto-repair issues found
    python3 scripts/health_check.py --dashboard   # Generate health dashboard HTML
    python3 scripts/health_check.py --json        # Output as JSON
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# --- Paths ---
PROJECT_ROOT = Path(__file__).parent.parent
DATA_HOME = os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
DATA_DIR = Path(DATA_HOME) / "software-of-you"
DB_PATH = DATA_DIR / "soy.db"
BACKUP_DIR = DATA_DIR / "backups"
TOKENS_DIR = DATA_DIR / "tokens"
OUTPUT_DIR = DATA_DIR / "output"
MCP_SRC = PROJECT_ROOT / "mcp-server" / "src"

MAX_BACKUPS = 5
SYNC_STALE_MINUTES = 60
BACKUP_STALE_HOURS = 48

# --- Expected infrastructure ---

REQUIRED_TABLES = [
    "soy_meta", "contacts", "tags", "entity_tags", "notes", "activity_log",
    "modules", "generated_views", "contact_interactions", "contact_relationships",
    "follow_ups", "projects", "tasks", "milestones", "emails", "calendar_events",
    "transcripts", "transcript_participants", "commitments", "conversation_metrics",
    "communication_insights", "relationship_scores", "decisions", "journal_entries",
    "standalone_notes", "transcript_sources", "user_profile", "google_accounts",
    "pipeline_runs", "pipeline_phases", "health_checks",
]

REQUIRED_VIEWS = [
    "v_contact_health", "v_commitment_status", "v_commitment_triage",
    "v_nudge_items", "v_nudge_summary", "v_discovery_candidates",
    "v_meeting_prep", "v_project_health", "v_email_response_queue",
]

CORE_HTML_VIEWS = [
    "dashboard.html", "contacts.html", "week-view.html",
    "email-hub.html", "nudges.html", "timeline.html",
]


# --- DB helpers ---

def get_db():
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def log_check(conn, check_type, status, details=None):
    try:
        conn.execute(
            "INSERT INTO health_checks (check_type, status, details) VALUES (?, ?, ?)",
            (check_type, status, json.dumps(details) if details else None),
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Table might not exist yet


# --- Check 1: Database integrity ---

def check_database(conn, fix=False):
    """Verify all required tables, views, and basic integrity."""
    results = {"status": "ok", "issues": [], "repairs": []}

    # Check tables
    existing = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    missing_tables = [t for t in REQUIRED_TABLES if t not in existing]
    if missing_tables:
        results["issues"].append(f"Missing tables: {', '.join(missing_tables)}")
        if fix:
            bootstrap = PROJECT_ROOT / "shared" / "bootstrap.sh"
            subprocess.run(["bash", str(bootstrap)], capture_output=True)
            results["repairs"].append("Ran bootstrap to create missing tables")

    # Check views
    existing_views = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view'"
    ).fetchall()}
    missing_views = [v for v in REQUIRED_VIEWS if v not in existing_views]
    if missing_views:
        results["issues"].append(f"Missing views: {', '.join(missing_views)}")
        if fix:
            migration = PROJECT_ROOT / "data" / "migrations" / "014_computed_views.sql"
            if migration.exists():
                conn.executescript(migration.read_text())
                results["repairs"].append("Re-ran computed views migration")

    # Check contact count (data loss detection)
    count = conn.execute("SELECT COUNT(*) as c FROM contacts").fetchone()["c"]
    if count == 0:
        results["issues"].append("No contacts found — possible data loss")
        results["status"] = "warning"

    # SQLite integrity check
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        results["issues"].append(f"SQLite integrity check: {integrity}")
        results["status"] = "failed"

    # Foreign key violations
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        results["issues"].append(f"{len(fk_violations)} foreign key violations")
        results["status"] = "warning"

    if not results["issues"]:
        results["status"] = "ok"
    elif results["status"] == "ok":
        results["status"] = "warning"

    log_check(conn, "database_integrity", results["status"], results)
    return results


# --- Check 2: OAuth tokens ---

def check_oauth(conn, fix=False):
    """Verify OAuth tokens exist and are valid. Auto-refresh if expired."""
    results = {"status": "ok", "accounts": [], "issues": [], "repairs": []}

    # Check if any tokens exist
    if not TOKENS_DIR.exists() or not list(TOKENS_DIR.glob("*.json")):
        legacy = DATA_DIR / "google_token.json"
        if not legacy.exists():
            results["status"] = "warning"
            results["issues"].append("No Google tokens found — not connected")
            log_check(conn, "oauth_tokens", results["status"], results)
            return results

    # Check each token file
    for token_file in sorted(TOKENS_DIR.glob("*.json")):
        account_name = token_file.stem
        try:
            token_data = json.loads(token_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            results["issues"].append(f"{account_name}: corrupt token file ({e})")
            results["status"] = "failed"
            continue

        saved_at = token_data.get("saved_at", 0)
        expires_in = token_data.get("expires_in", 3600)
        expires_at = saved_at + expires_in
        now = time.time()
        is_expired = now > (expires_at - 60)
        has_refresh = "refresh_token" in token_data

        account_info = {
            "account": account_name,
            "expired": is_expired,
            "has_refresh_token": has_refresh,
            "expires_in_minutes": max(0, int((expires_at - now) / 60)),
        }

        if is_expired and has_refresh and fix:
            # Try auto-refresh via the auth module
            try:
                env = {**os.environ, "PYTHONPATH": str(MCP_SRC)}
                email = account_name.replace("_", "@", 1)  # Reverse filename convention
                result = subprocess.run(
                    [sys.executable, "-c",
                     f"from software_of_you.google_auth import get_valid_token; t = get_valid_token(email='{email}'); print('refreshed' if t else 'failed')"],
                    capture_output=True, text=True, timeout=15, env=env,
                )
                if "refreshed" in result.stdout:
                    account_info["expired"] = False
                    results["repairs"].append(f"{account_name}: token refreshed")
                else:
                    results["issues"].append(f"{account_name}: refresh failed")
                    results["status"] = "warning"
            except Exception as e:
                results["issues"].append(f"{account_name}: refresh error ({e})")
                results["status"] = "warning"
        elif is_expired:
            results["issues"].append(f"{account_name}: token expired ({account_info['expires_in_minutes']}m ago)")
            if results["status"] == "ok":
                results["status"] = "warning"

        results["accounts"].append(account_info)

    if not results["issues"]:
        results["status"] = "ok"

    log_check(conn, "oauth_tokens", results["status"], results)
    return results


# --- Check 3: HTML views ---

def check_html_views(conn, fix=False):
    """Validate core HTML views exist and have content."""
    results = {"status": "ok", "missing": [], "empty": [], "repairs": []}

    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        results["issues"] = ["Output directory did not exist — created"]

    for view_name in CORE_HTML_VIEWS:
        path = OUTPUT_DIR / view_name
        if not path.exists():
            results["missing"].append(view_name)
        elif path.stat().st_size < 100:
            results["empty"].append(view_name)

    issues = results["missing"] + results["empty"]
    if issues:
        results["status"] = "warning"
        if fix:
            # Flag for regeneration — actual generation requires Claude
            results["needs_regeneration"] = issues
            results["repairs"].append(f"Flagged {len(issues)} views for regeneration")
            # Store flag in soy_meta for next Claude session to pick up
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                    ("views_need_regeneration", json.dumps(issues)),
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass

    log_check(conn, "html_views", results["status"], results)
    return results


# --- Check 4: Backups ---

def check_backups(conn, fix=False):
    """Verify backups exist and are recent."""
    results = {"status": "ok", "issues": [], "repairs": [], "backup_count": 0, "latest": None}

    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        results["issues"].append("Backup directory did not exist — created")

    backups = sorted(BACKUP_DIR.glob("soy*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    results["backup_count"] = len(backups)

    if not backups:
        results["status"] = "warning"
        results["issues"].append("No backups found")
        if fix:
            create_backup()
            results["repairs"].append("Created initial backup")
    else:
        latest = backups[0]
        results["latest"] = latest.name
        age_hours = (time.time() - latest.stat().st_mtime) / 3600
        results["latest_age_hours"] = round(age_hours, 1)
        if age_hours > BACKUP_STALE_HOURS:
            results["status"] = "warning"
            results["issues"].append(f"Latest backup is {age_hours:.0f}h old (threshold: {BACKUP_STALE_HOURS}h)")
            if fix:
                create_backup()
                results["repairs"].append("Created fresh backup")

    log_check(conn, "backups", results["status"], results)
    return results


def create_backup():
    """Create a database backup, pruning old ones."""
    if not DB_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"soy_{ts}.db"
    shutil.copy2(str(DB_PATH), str(dest))

    # Prune old backups
    backups = sorted(BACKUP_DIR.glob("soy*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[MAX_BACKUPS:]:
        old.unlink()
    return dest


def enforce_backup_before_destructive(operation_name):
    """Call before any destructive database operation. Returns backup path."""
    print(f"[health] Creating backup before {operation_name}...")
    path = create_backup()
    if path:
        print(f"[health] Backup saved: {path.name}")
    else:
        print("[health] WARNING: Backup failed — database may not exist")
    return path


# --- Check 5: Sync freshness ---

def check_sync_freshness(conn):
    """Check how recently Gmail, Calendar, and transcripts were synced."""
    results = {"status": "ok", "services": {}, "issues": []}

    keys = {
        "gmail": "gmail_last_synced",
        "calendar": "calendar_last_synced",
        "transcripts": "transcripts_last_scanned",
    }

    for service, key in keys.items():
        row = conn.execute("SELECT value FROM soy_meta WHERE key=?", (key,)).fetchone()
        if not row or not row["value"]:
            results["services"][service] = {"last_synced": None, "stale": True}
            results["issues"].append(f"{service}: never synced")
        else:
            try:
                synced = datetime.fromisoformat(row["value"].replace("Z", "+00:00"))
                # SQLite stores naive UTC timestamps — compare with naive UTC
                if synced.tzinfo is not None:
                    synced = synced.replace(tzinfo=None)
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                age_minutes = (now - synced).total_seconds() / 60
                is_stale = age_minutes > SYNC_STALE_MINUTES
                results["services"][service] = {
                    "last_synced": row["value"],
                    "age_minutes": round(age_minutes),
                    "stale": is_stale,
                }
                if is_stale:
                    results["issues"].append(f"{service}: synced {age_minutes:.0f}m ago")
            except (ValueError, TypeError):
                results["services"][service] = {"last_synced": row["value"], "stale": True}
                results["issues"].append(f"{service}: invalid timestamp")

    if any(s.get("stale") for s in results["services"].values()):
        results["status"] = "warning"

    log_check(conn, "sync_freshness", results["status"], results)
    return results


# --- Health Dashboard HTML ---

def generate_health_dashboard(all_results):
    """Generate an HTML health dashboard."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    overall = "ok"
    for r in all_results.values():
        if r.get("status") == "failed":
            overall = "failed"
            break
        if r.get("status") == "warning" and overall == "ok":
            overall = "warning"

    status_colors = {"ok": "#22c55e", "warning": "#f59e0b", "failed": "#ef4444"}
    status_icons = {"ok": "check-circle", "warning": "alert-triangle", "failed": "x-circle"}
    status_labels = {"ok": "Healthy", "warning": "Needs Attention", "failed": "Critical"}

    def status_badge(s):
        c = status_colors.get(s, "#94a3b8")
        return f'<span style="color:{c};font-weight:600">{status_labels.get(s, s)}</span>'

    def card(title, check_key, body_html):
        s = all_results.get(check_key, {}).get("status", "ok")
        c = status_colors.get(s, "#94a3b8")
        return f'''
        <div style="border:1px solid #e4e4e7;border-radius:12px;padding:24px;border-left:4px solid {c}">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <h3 style="font-size:1rem;font-weight:600;margin:0">{title}</h3>
            {status_badge(s)}
          </div>
          {body_html}
        </div>'''

    # Database card
    db = all_results.get("database", {})
    db_issues = db.get("issues", [])
    db_repairs = db.get("repairs", [])
    db_body = "<p style='color:#71717a;margin:0'>All tables, views, and integrity checks passed.</p>" if not db_issues else ""
    if db_issues:
        db_body = "<ul style='margin:4px 0;padding-left:20px;color:#71717a'>" + "".join(f"<li>{i}</li>" for i in db_issues) + "</ul>"
    if db_repairs:
        db_body += "<p style='color:#22c55e;margin:4px 0'>Repairs: " + ", ".join(db_repairs) + "</p>"

    # OAuth card
    oauth = all_results.get("oauth", {})
    accounts = oauth.get("accounts", [])
    oauth_body = ""
    if not accounts:
        oauth_body = "<p style='color:#71717a;margin:0'>No Google accounts connected.</p>"
    else:
        oauth_body = "<table style='width:100%;font-size:0.875rem;color:#71717a'><thead><tr><th style='text-align:left;padding:4px 8px'>Account</th><th style='text-align:left;padding:4px 8px'>Status</th><th style='text-align:left;padding:4px 8px'>Expires</th></tr></thead><tbody>"
        for a in accounts:
            exp = f"{a['expires_in_minutes']}m" if not a["expired"] else "<span style='color:#ef4444'>Expired</span>"
            st = "<span style='color:#22c55e'>Valid</span>" if not a["expired"] else "<span style='color:#ef4444'>Expired</span>"
            oauth_body += f"<tr><td style='padding:4px 8px'>{a['account']}</td><td style='padding:4px 8px'>{st}</td><td style='padding:4px 8px'>{exp}</td></tr>"
        oauth_body += "</tbody></table>"
    oauth_repairs = oauth.get("repairs", [])
    if oauth_repairs:
        oauth_body += "<p style='color:#22c55e;margin:4px 0'>Repairs: " + ", ".join(oauth_repairs) + "</p>"

    # HTML views card
    views = all_results.get("html_views", {})
    missing = views.get("missing", [])
    empty = views.get("empty", [])
    views_body = "<p style='color:#71717a;margin:0'>All core views present.</p>" if not missing and not empty else ""
    if missing:
        views_body = f"<p style='color:#71717a;margin:0'>Missing: {', '.join(missing)}</p>"
    if empty:
        views_body += f"<p style='color:#71717a;margin:0'>Empty: {', '.join(empty)}</p>"

    # Backups card
    bk = all_results.get("backups", {})
    bk_body = f"<p style='color:#71717a;margin:0'>{bk.get('backup_count', 0)} backups. Latest: {bk.get('latest', 'none')} ({bk.get('latest_age_hours', '?')}h ago)</p>"

    # Sync card
    sync = all_results.get("sync_freshness", {})
    services = sync.get("services", {})
    sync_body = "<table style='width:100%;font-size:0.875rem;color:#71717a'><thead><tr><th style='text-align:left;padding:4px 8px'>Service</th><th style='text-align:left;padding:4px 8px'>Last Sync</th><th style='text-align:left;padding:4px 8px'>Age</th></tr></thead><tbody>"
    for svc, info in services.items():
        age = f"{info.get('age_minutes', '?')}m" if info.get("last_synced") else "Never"
        stale_mark = " ⚠" if info.get("stale") else ""
        sync_body += f"<tr><td style='padding:4px 8px'>{svc}</td><td style='padding:4px 8px'>{info.get('last_synced', '—')}</td><td style='padding:4px 8px'>{age}{stale_mark}</td></tr>"
    sync_body += "</tbody></table>"

    # Recent repairs
    repairs_body = ""
    all_repairs = []
    for section, data in all_results.items():
        for r in data.get("repairs", []):
            all_repairs.append(f"{section}: {r}")
    if all_repairs:
        repairs_body = f'''
        <div style="border:1px solid #e4e4e7;border-radius:12px;padding:24px;border-left:4px solid #22c55e;margin-top:16px">
          <h3 style="font-size:1rem;font-weight:600;margin:0 0 12px">Auto-Repairs This Run</h3>
          <ul style="margin:0;padding-left:20px;color:#71717a">{"".join(f"<li>{r}</li>" for r in all_repairs)}</ul>
        </div>'''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>System Health — Software of You</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>body{{font-family:'Inter',system-ui,sans-serif}}</style>
</head>
<body style="background:#fafafa;color:#18181b;padding:32px;max-width:800px;margin:0 auto">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:32px">
    <div>
      <h1 style="font-size:1.5rem;font-weight:700;margin:0">System Health</h1>
      <p style="color:#71717a;margin:4px 0 0;font-size:0.875rem">Last checked: {now}</p>
    </div>
    <div style="padding:8px 16px;border-radius:8px;background:{status_colors[overall]}15;border:1px solid {status_colors[overall]}30">
      {status_badge(overall)}
    </div>
  </div>
  <div style="display:grid;gap:16px">
    {card("Database Integrity", "database", db_body)}
    {card("OAuth Tokens", "oauth", oauth_body)}
    {card("HTML Views", "html_views", views_body)}
    {card("Backups", "backups", bk_body)}
    {card("Sync Freshness", "sync_freshness", sync_body)}
  </div>
  {repairs_body}
  <p style="text-align:center;color:#a1a1aa;font-size:0.75rem;margin-top:32px">Software of You — Health Monitor</p>
</body>
</html>"""

    output_path = OUTPUT_DIR / "health.html"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    return output_path


# --- Master patrol ---

def run_patrol(fix=False, dashboard=False, as_json=False):
    """Run all health checks. Returns combined results."""
    quiet = as_json  # Suppress status lines when outputting JSON

    def log(msg, **kwargs):
        if not quiet:
            print(msg, **kwargs)

    # Ensure DB and migration exist
    bootstrap = PROJECT_ROOT / "shared" / "bootstrap.sh"
    subprocess.run(["bash", str(bootstrap)], capture_output=True)

    conn = get_db()
    if not conn:
        if as_json:
            print(json.dumps({"overall": "failed", "error": "Database not found"}))
        else:
            print("CRITICAL: Database not found at", DB_PATH)
        return {"overall": "failed", "error": "Database not found"}

    results = {}

    log("Running health checks...")

    # 1. Database
    log("  [1/5] Database integrity...", end=" ", flush=True)
    results["database"] = check_database(conn, fix=fix)
    log(results["database"]["status"])

    # 2. OAuth
    log("  [2/5] OAuth tokens...", end=" ", flush=True)
    results["oauth"] = check_oauth(conn, fix=fix)
    log(results["oauth"]["status"])

    # 3. HTML views
    log("  [3/5] HTML views...", end=" ", flush=True)
    results["html_views"] = check_html_views(conn, fix=fix)
    log(results["html_views"]["status"])

    # 4. Backups
    log("  [4/5] Backups...", end=" ", flush=True)
    results["backups"] = check_backups(conn, fix=fix)
    log(results["backups"]["status"])

    # 5. Sync freshness
    log("  [5/5] Sync freshness...", end=" ", flush=True)
    results["sync_freshness"] = check_sync_freshness(conn)
    log(results["sync_freshness"]["status"])

    # Overall status
    statuses = [r["status"] for r in results.values()]
    if "failed" in statuses:
        overall = "failed"
    elif "warning" in statuses:
        overall = "warning"
    else:
        overall = "ok"

    # Count repairs
    all_repairs = []
    for data in results.values():
        all_repairs.extend(data.get("repairs", []))

    log(f"\nOverall: {overall}" + (f" ({len(all_repairs)} auto-repairs)" if all_repairs else ""))

    if dashboard or fix:
        path = generate_health_dashboard(results)
        log(f"Dashboard: {path}")

    conn.close()

    if as_json:
        print(json.dumps({"overall": overall, "checks": results}, indent=2, default=str))

    return {"overall": overall, "checks": results, "repairs": all_repairs}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Software of You — Health Monitor")
    parser.add_argument("--fix", action="store_true", help="Auto-repair issues")
    parser.add_argument("--dashboard", action="store_true", help="Generate health dashboard HTML")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    args = parser.parse_args()

    run_patrol(fix=args.fix, dashboard=args.dashboard or args.fix, as_json=args.as_json)
