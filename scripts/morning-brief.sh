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

# Bounded runner: cap a command's wall-clock so a hung child (e.g. an
# unauthenticated headless `claude` under launchd) can never block delivery.
# macOS has no `timeout` builtin; prefer coreutils, else a portable kill guard.
run_bounded() {
  local secs="$1"; shift
  if command -v timeout >/dev/null 2>&1; then timeout "$secs" "$@"; return $?; fi
  if command -v gtimeout >/dev/null 2>&1; then gtimeout "$secs" "$@"; return $?; fi
  "$@" & local pid=$!
  ( sleep "$secs"; kill -0 "$pid" 2>/dev/null && kill "$pid" 2>/dev/null ) & local w=$!
  wait "$pid" 2>/dev/null; local rc=$?
  kill "$w" 2>/dev/null; return "$rc"
}

# 1. Sync fresh data + render views deterministically (pipeline Phase 1 + Phase 3;
#    no Claude). Phase 3 already regenerates the whole site, so no separate render.
echo "[brief] syncing + rendering…"
python3 scripts/pipeline.py --trigger cron >"${OUTPUT_DIR}/pipeline-${DATE}.log" 2>&1 || true

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
name_rows = q("SELECT value FROM user_profile WHERE category='identity' AND key='name'")
name = name_rows[0]["value"] if name_rows else None
events = q("SELECT title, start_time FROM calendar_events "
           "WHERE date(start_time)=date('now') AND status!='cancelled' ORDER BY start_time")

heading = f"# Morning Brief — {today}" + (f" · {name}" if name else "")
lines = [heading, ""]
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

# 5. Optional Claude enrichment — bounded so it can NEVER block delivery, and
#    written to a temp file so a killed/hung run can't corrupt the floor brief.
#    Only the deterministic floor is guaranteed; enrichment is best-effort.
if command -v claude >/dev/null 2>&1; then
  echo "[brief] enriching via Claude (bounded)…"
  ENRICHED="${BRIEF_FILE}.enriched"
  rm -f "$ENRICHED"
  PROMPT="You are Software of You. Data is already synced and today's signals are in the DB.
Read ${BRIEF_FILE} and write a concise, grounded morning brief (4-6 items max) to ${ENRICHED}.
Use ONLY facts from the DB and the current file — never invent numbers or names.
Cover: what needs attention (from the signals already listed), today's calendar with attendee
context where known, and any current/overdue commitments (use v_commitment_status).
Skip automated/notification emails."
  run_bounded 180 claude -p "$PROMPT" --allowedTools "Bash,Read,Write,Edit,Grep,Glob" \
    >"${OUTPUT_DIR}/brief-claude-${DATE}.log" 2>&1 || true
  # Swap in the enriched version only if it actually produced content.
  [[ -s "$ENRICHED" ]] && mv "$ENRICHED" "$BRIEF_FILE" || rm -f "$ENRICHED"
fi

# 6. Deliver: email to self + open the dashboard. The floor brief guarantees content.
if [[ -s "$BRIEF_FILE" ]]; then
  echo "[brief] emailing…"
  python3 shared/send_email.py --subject "Morning Brief — ${DATE}" \
    < "$BRIEF_FILE" >"${OUTPUT_DIR}/email-${DATE}.log" 2>&1 || true
fi
[[ -f "${OUTPUT_DIR}/dashboard.html" ]] && open "${OUTPUT_DIR}/dashboard.html" 2>/dev/null || true

echo "[brief] done → ${BRIEF_FILE}"
