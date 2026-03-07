#!/usr/bin/env bash
# Morning Brief — run via cron, launchd, or manually.
# 1. Runs the pipeline (sync data)
# 2. Generates a daily briefing using Claude Code in headless mode.
#
# Usage:
#   ./scripts/morning-brief.sh          # run now
#   crontab: 53 7 * * 1-5 /path/to/morning-brief.sh
#
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATE=$(date +%Y-%m-%d)
OUTPUT_DIR="${PLUGIN_ROOT}/output"
mkdir -p "$OUTPUT_DIR"

cd "$PLUGIN_ROOT"

# Step 1: Run pipeline to sync all data
echo "Running data pipeline..."
python3 scripts/pipeline.py --trigger cron 2>&1 | tee "${OUTPUT_DIR}/pipeline-${DATE}.log"

# Step 2: Generate the brief via Claude headless
PROMPT="You are Software of You. Data has already been synced. Generate a concise morning briefing for Kerry covering:
1. Today's calendar with attendee context (who they are, last interaction)
2. Email triage — what needs attention. Skip all Benji's financial emails and gigi@benjis.com forwards.
3. Current or overdue commitments (use v_commitment_triage — only 'current' and 'overdue' items)
4. Nudges from v_nudge_summary
Keep it to 4-5 things I need to know. Save to ${OUTPUT_DIR}/daily-brief-${DATE}.md"

echo "Generating brief..."
claude -p "$PROMPT" \
  --allowedTools "Bash,Read,Write,Edit,Grep,Glob" \
  2>"${OUTPUT_DIR}/morning-brief-${DATE}.log" || true

echo "Brief saved to ${OUTPUT_DIR}/daily-brief-${DATE}.md"
