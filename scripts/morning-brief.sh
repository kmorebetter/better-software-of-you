#!/usr/bin/env bash
# Morning Brief — the daily awareness loop. Run via launchd, cron, or manually.
#
#   sync data -> regenerate views (deterministic) -> detect signals ->
#   build a grounded brief (Claude if available, deterministic fallback otherwise) ->
#   email it to self + save the file + open the dashboard.
#
# Usage:
#   ./scripts/morning-brief.sh            # run now
#   launchd: installed by /auto-sync on   (see shared/you.softwareof.brief.plist)
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATE=$(date +%Y-%m-%d)
OUTPUT_DIR="${PLUGIN_ROOT}/output"
BRIEF_FILE="${OUTPUT_DIR}/daily-brief-${DATE}.md"
VENV_PYTHON="${PLUGIN_ROOT}/mcp-server/.venv/bin/python3"
PY="python3"
[[ -x "${VENV_PYTHON}" ]] && PY="${VENV_PYTHON}"
mkdir -p "$OUTPUT_DIR"
cd "$PLUGIN_ROOT"

# 1. Sync fresh data (pure Python, no Claude).
echo "[brief] syncing…"
python3 scripts/pipeline.py --trigger cron >"${OUTPUT_DIR}/pipeline-${DATE}.log" 2>&1 || true

# 2. Regenerate views deterministically if the renderer exists (Phase B). Never blocks.
if [[ -f "${PLUGIN_ROOT}/scripts/render.py" ]]; then
  echo "[brief] rendering views…"
  "${PY}" scripts/render.py >"${OUTPUT_DIR}/render-${DATE}.log" 2>&1 || true
fi

# 3. Detect signals (deterministic; updates the state ledger).
echo "[brief] detecting signals…"
python3 scripts/signals.py detect >/dev/null 2>&1 || true

# 4. Build a deterministic brief from the top signals + today's calendar. This is
#    the guaranteed floor — the email always has real, grounded content.
python3 - "$BRIEF_FILE" <<'PY'
import json, os, sqlite3, subprocess, sys, datetime
brief_file = sys.argv[1]
root = os.getcwd()
data_home = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
db = os.path.join(data_home, "software-of-you", "soy.db")

def q(sql):
    try:
        c = sqlite3.connect(db); c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(sql).fetchall()]; c.close(); return rows
    except Exception:
        return []

top = []
try:
    out = subprocess.run(["python3", "scripts/signals.py", "top", "--n", "5", "--surface"],
                         capture_output=True, text=True, cwd=root, timeout=30)
    top = json.loads(out.stdout or "[]")
except Exception:
    top = []

today = datetime.date.today().strftime("%A, %B %-d")
events = q("SELECT title, start_time FROM calendar_events "
           "WHERE date(start_time)=date('now') AND status!='cancelled' ORDER BY start_time")

lines = [f"# Morning Brief — {today}", ""]
if top:
    lines.append("## What needs your attention")
    for s in top:
        d = f" — {s['detail']}" if s.get("detail") else ""
        lines.append(f"- **{s['title']}**{d}")
    lines.append("")
lines.append("## Today's calendar")
if events:
    for e in events:
        t = (e["start_time"] or "")[11:16]
        lines.append(f"- {t} — {e['title']}")
else:
    lines.append("- No events scheduled.")
lines.append("")
if not top:
    lines.append("_Nothing flagged — you're clear._")

open(brief_file, "w").write("\n".join(lines) + "\n")
print(brief_file)
PY

# 5. Optional Claude enrichment — only if the CLI is reachable (launchd PATH may not
#    include it). Rewrites the brief into grounded prose; failure keeps the floor brief.
if command -v claude >/dev/null 2>&1; then
  echo "[brief] enriching via Claude…"
  PROMPT="You are Software of You. Data is already synced and today's signals are in the DB.
Rewrite ${BRIEF_FILE} into a concise, grounded morning brief for Kerry (4-6 items max).
Use ONLY facts from the DB and the current file — never invent numbers or names.
Cover: what needs attention (from the signals already listed), today's calendar with attendee
context where known, and any current/overdue commitments (use v_commitment_status).
Keep the same file path. Skip automated/notification emails."
  claude -p "$PROMPT" --allowedTools "Bash,Read,Write,Edit,Grep,Glob" \
    >"${OUTPUT_DIR}/brief-claude-${DATE}.log" 2>&1 || true
fi

# 6. Deliver: email to self + open the dashboard.
if [[ -s "$BRIEF_FILE" ]]; then
  echo "[brief] emailing…"
  python3 shared/send_email.py --subject "Morning Brief — ${DATE}" \
    < "$BRIEF_FILE" >"${OUTPUT_DIR}/email-${DATE}.log" 2>&1 || true
fi
[[ -f "${OUTPUT_DIR}/dashboard.html" ]] && open "${OUTPUT_DIR}/dashboard.html" 2>/dev/null || true

echo "[brief] done → ${BRIEF_FILE}"
