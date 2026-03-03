#!/usr/bin/env bash
# open_page.sh — Open a SoY page through the server (with sidebar injection).
#
# Usage:
#   bash shared/open_page.sh dashboard.html       # standard page
#   bash shared/open_page.sh                      # hub (no args)
#   bash shared/open_page.sh --share report.html  # shared page (no sidebar)
#
# Checks if the server is running, auto-starts it if not, then opens the
# appropriate URL. Falls back to direct file open if server can't start.

set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PORT=8787
SERVER_URL="http://localhost:${PORT}"

# ── Parse arguments ──────────────────────────────────────────

SHARE_MODE=false
FILENAME=""

if [[ "${1:-}" == "--share" ]]; then
    SHARE_MODE=true
    FILENAME="${2:-}"
else
    FILENAME="${1:-}"
fi

# ── Resolve URL path ────────────────────────────────────────

resolve_url() {
    if $SHARE_MODE && [[ -n "$FILENAME" ]]; then
        echo "${SERVER_URL}/share/${FILENAME}"
        return
    fi

    case "$FILENAME" in
        ""|"hub"|"hub.html")
            echo "${SERVER_URL}/"
            ;;
        *)
            echo "${SERVER_URL}/pages/${FILENAME}"
            ;;
    esac
}

# ── Check if server is running ──────────────────────────────

server_is_running() {
    curl -sf "${SERVER_URL}/health" >/dev/null 2>&1
}

# ── Start the server ────────────────────────────────────────

start_server() {
    python3 "${PLUGIN_ROOT}/shared/soy_server.py" &
    disown

    # Wait up to 3 seconds for the server to come up
    for i in 1 2 3 4 5 6; do
        sleep 0.5
        if server_is_running; then
            return 0
        fi
    done
    return 1
}

# ── Main ────────────────────────────────────────────────────

if ! server_is_running; then
    if ! start_server; then
        # Fallback: open the file directly if server won't start
        if [[ -n "$FILENAME" && -f "${PLUGIN_ROOT}/output/${FILENAME}" ]]; then
            echo "Server unavailable — opening file directly (no sidebar)."
            open "${PLUGIN_ROOT}/output/${FILENAME}"
            exit 0
        else
            echo "Error: Server failed to start and no local file found." >&2
            exit 1
        fi
    fi
fi

URL=$(resolve_url)
open "$URL"
echo "Opened: $URL"
