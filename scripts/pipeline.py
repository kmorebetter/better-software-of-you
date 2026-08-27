#!/usr/bin/env python3
"""Software of You — Daily Pipeline Orchestrator.

Runs data ingestion, analysis, and view generation as a fault-tolerant
pipeline with parallel execution where possible.

Phases:
  1. Sync (parallel): Gmail, Calendar, Transcripts
  2. Analysis: Process new transcripts via Claude headless
  3. Views: Regenerate dashboards via Claude headless

Usage:
    # Data sync only (no Claude needed)
    python3 scripts/pipeline.py

    # Full pipeline including Claude-powered analysis and views
    python3 scripts/pipeline.py --with-claude

    # Specify trigger source for logging
    python3 scripts/pipeline.py --trigger cron

    # Skip sync, just run analysis + views
    python3 scripts/pipeline.py --skip-sync --with-claude
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# --- Paths ---
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
MCP_SRC = PROJECT_ROOT / "mcp-server" / "src"
# Prefer MCP venv if it exists, otherwise system Python with PYTHONPATH
_venv_python = PROJECT_ROOT / "mcp-server" / ".venv" / "bin" / "python3"
SYNC_PYTHON = str(_venv_python) if _venv_python.exists() else sys.executable
DATA_HOME = os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
DATA_DIR = Path(DATA_HOME) / "software-of-you"
DB_PATH = DATA_DIR / "soy.db"
LOG_DIR = DATA_DIR / "logs"


# --- Database helpers ---

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_run(conn, trigger="manual"):
    cur = conn.execute(
        "INSERT INTO pipeline_runs (trigger) VALUES (?)", (trigger,)
    )
    conn.commit()
    return cur.lastrowid


def create_phase(conn, run_id, phase):
    cur = conn.execute(
        "INSERT INTO pipeline_phases (run_id, phase) VALUES (?, ?)",
        (run_id, phase),
    )
    conn.commit()
    return cur.lastrowid


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _duration_since(start_str):
    if not start_str:
        return None
    start = datetime.fromisoformat(start_str)
    now = datetime.fromisoformat(_now())
    return (now - start).total_seconds()


def update_phase(conn, phase_id, status, result=None, error=None):
    now = _now()
    if status == "running":
        conn.execute(
            "UPDATE pipeline_phases SET status=?, started_at=? WHERE id=?",
            (status, now, phase_id),
        )
    else:
        row = conn.execute(
            "SELECT started_at FROM pipeline_phases WHERE id=?", (phase_id,)
        ).fetchone()
        duration = _duration_since(row["started_at"]) if row else None
        conn.execute(
            "UPDATE pipeline_phases SET status=?, completed_at=?, duration_seconds=?, result=?, error=? WHERE id=?",
            (status, now, duration, json.dumps(result) if result else None, error, phase_id),
        )
    conn.commit()


def complete_run(conn, run_id, status, summary=None):
    now = _now()
    row = conn.execute(
        "SELECT started_at FROM pipeline_runs WHERE id=?", (run_id,)
    ).fetchone()
    duration = _duration_since(row["started_at"]) if row else None
    conn.execute(
        "UPDATE pipeline_runs SET status=?, completed_at=?, duration_seconds=?, summary=? WHERE id=?",
        (status, now, duration, summary, run_id),
    )
    conn.commit()


# --- Phase runners ---

def run_sync_phase(service):
    """Run a single sync service via the MCP venv Python. Returns (service, result_dict)."""
    try:
        env = {**os.environ, "PYTHONPATH": str(MCP_SRC)}
        result = subprocess.run(
            [
                SYNC_PYTHON, "-c",
                f"import json; from software_of_you.google_sync import sync_service; print(json.dumps(sync_service('{service}')))",
            ],
            capture_output=True, text=True, timeout=120,
            cwd=str(PROJECT_ROOT / "mcp-server"),
            env=env,
        )
        if result.returncode != 0:
            return service, {"error": result.stderr.strip()[:500]}
        # Parse the last line of stdout as JSON (skip any debug output)
        lines = result.stdout.strip().splitlines()
        for line in reversed(lines):
            try:
                return service, json.loads(line)
            except json.JSONDecodeError:
                continue
        return service, {"error": "No JSON output", "stdout": result.stdout[:500]}
    except subprocess.TimeoutExpired:
        return service, {"error": "Timeout after 120s"}
    except Exception as e:
        return service, {"error": str(e)}


def run_claude_phase(prompt, timeout=300):
    """Run a Claude headless prompt. Returns result dict."""
    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--allowedTools", "Bash,Read,Write,Edit,Grep,Glob",
            ],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        return {
            "exit_code": result.returncode,
            "output_length": len(result.stdout),
            "error": result.stderr.strip()[:500] if result.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timeout after {timeout}s"}
    except FileNotFoundError:
        return {"error": "claude CLI not found — install Claude Code or use --skip-claude"}
    except Exception as e:
        return {"error": str(e)}


# --- Main pipeline ---

def run_pipeline(trigger="manual", with_claude=False, skip_sync=False):
    """Execute the full pipeline. Returns summary dict."""
    # Ensure migration has run
    conn = get_db()
    try:
        conn.execute("SELECT 1 FROM pipeline_runs LIMIT 0")
    except sqlite3.OperationalError:
        # Table doesn't exist yet — run bootstrap
        bootstrap = PROJECT_ROOT / "shared" / "bootstrap.sh"
        subprocess.run(["bash", str(bootstrap)], capture_output=True)
        conn.close()
        conn = get_db()

    run_id = create_run(conn, trigger)
    results = {}
    any_failed = False

    print(f"Pipeline run #{run_id} started ({trigger})")

    # ── Phase 1: Parallel data sync ──────────────────────────────────
    if not skip_sync:
        services = ["gmail", "calendar", "transcripts"]
        phase_ids = {}
        for svc in services:
            pid = create_phase(conn, run_id, f"{svc}_sync")
            phase_ids[svc] = pid
            update_phase(conn, pid, "running")

        print(f"  Syncing: {', '.join(services)} (parallel)")

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(run_sync_phase, svc): svc for svc in services}
            for future in as_completed(futures):
                svc = futures[future]
                try:
                    _, result = future.result()
                except Exception as e:
                    result = {"error": str(e)}

                has_error = "error" in result and result["error"]
                status = "failed" if has_error else "completed"
                if has_error:
                    any_failed = True

                update_phase(conn, phase_ids[svc], status, result=result, error=result.get("error"))
                results[f"{svc}_sync"] = result

                icon = "x" if has_error else "ok"
                detail = result.get("error", "") or f"synced={result.get('synced', result.get('imported', '?'))}"
                print(f"    [{icon}] {svc}: {detail}")
    else:
        print("  Skipping sync (--skip-sync)")

    # ── Phase 2: Transcript analysis ─────────────────────────────────
    if with_claude:
        phase_id = create_phase(conn, run_id, "transcript_analysis")
        update_phase(conn, phase_id, "running")
        print("  Analyzing new transcripts...")

        prompt = (
            "Check for unanalyzed transcripts: "
            "SELECT id, title FROM transcripts WHERE processed_at IS NULL AND source='gemini'. "
            "If any exist, analyze each one: extract commitments, coaching insights, and key metrics. "
            "Mark each as processed. If none exist, just report 'No new transcripts to analyze.' "
            "Be concise."
        )
        result = run_claude_phase(prompt, timeout=300)
        has_error = result.get("error")
        update_phase(conn, phase_id, "failed" if has_error else "completed", result=result, error=has_error)
        results["transcript_analysis"] = result
        if has_error:
            any_failed = True
        print(f"    [{'x' if has_error else 'ok'}] transcript analysis")
    else:
        phase_id = create_phase(conn, run_id, "transcript_analysis")
        update_phase(conn, phase_id, "skipped", result={"reason": "no --with-claude flag"})
        print("  Skipping transcript analysis (no --with-claude)")

    # ── Phase 3: View regeneration (deterministic — no Claude needed) ─
    # The renderer builds the whole site in ~1-2s from the computed views; it
    # runs regardless of --with-claude (structure never needs the model). Narrative
    # refresh for stale contacts is a separate, interactive concern (see build-all).
    phase_id = create_phase(conn, run_id, "view_generation")
    update_phase(conn, phase_id, "running")
    print("  Rendering views (deterministic)...")
    try:
        render_py = str(PROJECT_ROOT / "scripts" / "render.py")
        proc = subprocess.run(
            [SYNC_PYTHON, render_py, "all"],
            capture_output=True, text=True, timeout=120, cwd=str(PROJECT_ROOT),
        )
        try:
            # render.py prints one (multi-line, indented) JSON summary object.
            result = json.loads(proc.stdout.strip()) if proc.stdout.strip() else {}
        except (json.JSONDecodeError, ValueError):
            result = {"stdout": proc.stdout[:300]}
        if proc.returncode != 0:
            result["error"] = proc.stderr.strip()[:500] or "render.py returned non-zero"
    except subprocess.TimeoutExpired:
        result = {"error": "Timeout after 120s"}
    except Exception as e:
        result = {"error": str(e)}
    has_error = result.get("error")
    update_phase(conn, phase_id, "failed" if has_error else "completed", result=result, error=has_error)
    results["view_generation"] = result
    if has_error:
        any_failed = True
    print(f"    [{'x' if has_error else 'ok'}] view generation ({result.get('count', '?')} pages)")

    # ── Finalize ─────────────────────────────────────────────────────
    # Determine overall status
    phases = conn.execute(
        "SELECT status FROM pipeline_phases WHERE run_id=?", (run_id,)
    ).fetchall()
    statuses = [p["status"] for p in phases]

    if all(s in ("completed", "skipped") for s in statuses):
        overall = "completed"
    elif any(s == "completed" for s in statuses) and any(s == "failed" for s in statuses):
        overall = "partial"
    elif all(s == "failed" for s in statuses if s != "skipped"):
        overall = "failed"
    else:
        overall = "completed"

    summary = json.dumps(results, default=str)
    complete_run(conn, run_id, overall, summary)

    # Also log to activity_log
    conn.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
        ("pipeline", run_id, "pipeline_completed", summary),
    )
    conn.commit()

    row = conn.execute(
        "SELECT duration_seconds FROM pipeline_runs WHERE id=?", (run_id,)
    ).fetchone()
    duration = row["duration_seconds"] if row else 0

    print(f"\nPipeline #{run_id} {overall} in {duration:.1f}s")
    conn.close()
    return {"run_id": run_id, "status": overall, "duration": duration, "phases": results}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Software of You — Daily Pipeline")
    parser.add_argument("--trigger", default="manual", help="Trigger source (manual, cron, interactive)")
    parser.add_argument("--with-claude", action="store_true", help="Run Claude-powered phases (analysis, views)")
    parser.add_argument("--skip-sync", action="store_true", help="Skip data sync, run analysis/views only")
    args = parser.parse_args()

    result = run_pipeline(
        trigger=args.trigger,
        with_claude=args.with_claude,
        skip_sync=args.skip_sync,
    )
    print(json.dumps(result, indent=2))
