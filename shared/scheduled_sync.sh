#!/usr/bin/env bash
# scheduled_sync.sh — Background sync runner for Software of You
#
# Called by launchd 3x/day (or manually via /auto-sync run).
# Syncs Gmail, Calendar, and transcripts using the MCP server's Python venv.
# Logs results to ~/.local/share/software-of-you/logs/sync.log

set -euo pipefail

# --- Resolve plugin root ---
if [[ -z "${CLAUDE_PLUGIN_ROOT:-}" ]]; then
    # Auto-detect: this script lives in <root>/shared/
    CLAUDE_PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi

VENV_PYTHON="${CLAUDE_PLUGIN_ROOT}/mcp-server/.venv/bin/python3"
DATA_DIR="${HOME}/.local/share/software-of-you"
LOG_DIR="${DATA_DIR}/logs"
LOG_FILE="${LOG_DIR}/sync.log"

# --- Ensure log directory exists ---
mkdir -p "${LOG_DIR}"

# --- Timestamp helper ---
timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

log() {
    echo "[$(timestamp)] $*" >> "${LOG_FILE}"
}

# --- Rotate log: keep last 500 lines ---
rotate_log() {
    if [[ -f "${LOG_FILE}" ]]; then
        local lines
        lines=$(wc -l < "${LOG_FILE}")
        if (( lines > 500 )); then
            local tmp="${LOG_FILE}.tmp"
            tail -n 500 "${LOG_FILE}" > "${tmp}"
            mv "${tmp}" "${LOG_FILE}"
        fi
    fi
}

# --- Pre-flight checks ---
if [[ ! -x "${VENV_PYTHON}" ]]; then
    log "ERROR: MCP venv Python not found at ${VENV_PYTHON}"
    exit 0  # Exit 0 so launchd doesn't mark the job as failed
fi

if [[ ! -f "${DATA_DIR}/soy.db" ]]; then
    log "SKIP: Database not found — run Software of You first"
    exit 0
fi

# --- Run sync via MCP Python ---
log "--- Sync started ---"

export CLAUDE_PLUGIN_ROOT

sync_result=$(${VENV_PYTHON} -c '
import json, os, sys

plugin_root = os.environ["CLAUDE_PLUGIN_ROOT"]
sys.path.insert(0, os.path.join(plugin_root, "mcp-server", "src"))

from software_of_you.google_auth import get_valid_token
from software_of_you.google_sync import sync_gmail, sync_calendar, sync_transcripts

token = get_valid_token()
if not token:
    print(json.dumps({"status": "skipped", "reason": "Google not connected"}))
    sys.exit(0)

results = {}
for name, fn in [("gmail", sync_gmail), ("calendar", sync_calendar), ("transcripts", sync_transcripts)]:
    try:
        results[name] = fn(token)
    except Exception as e:
        results[name] = {"error": str(e)}

print(json.dumps({"status": "ok", "results": results}))
' 2>&1) || true

if [[ -z "${sync_result}" ]]; then
    sync_result='{"status": "error", "reason": "Python process produced no output"}'
fi

log "Result: ${sync_result}"
log "--- Sync complete ---"

# --- Rotate log to prevent unbounded growth ---
rotate_log

exit 0
