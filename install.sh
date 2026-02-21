#!/bin/bash
# Install Software of You for Claude Code
# Usage: curl -sSL https://raw.githubusercontent.com/kmorebetter/better-software-of-you/main/install.sh | bash
set -e

INSTALL_DIR="$HOME/.software-of-you"
REPO="https://github.com/kmorebetter/better-software-of-you.git"

echo ""
echo "        ╭──────────╮"
echo "        │  ◠    ◠  │"
echo "        │    ◡◡    │"
echo "        ╰────┬┬────╯"
echo "            ╱╲╱╲"
echo ""
echo "  S O F T W A R E  of  Y O U"
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Your personal data platform."
echo "  Nice to meet you! ♡"
echo ""

# Check dependencies
if ! command -v git &>/dev/null; then
  echo "  ✗ git is required. Install it first."
  echo "    Mac: xcode-select --install"
  echo "    Linux: sudo apt install git"
  exit 1
fi

if ! command -v sqlite3 &>/dev/null; then
  echo "  ✗ sqlite3 is required (usually pre-installed)."
  exit 1
fi

if ! command -v claude &>/dev/null; then
  echo "  ⚠ Claude Code not found on PATH."
  echo "    Install it from: https://claude.ai/claude-code"
  echo ""
fi

# Install or update
if [ -d "$INSTALL_DIR" ]; then
  echo "  ↻ Updating existing installation..."
  cd "$INSTALL_DIR"
  git pull --quiet origin main
  echo "  ✓ Updated to latest version."
else
  echo "  ↓ Downloading..."
  git clone --quiet "$REPO" "$INSTALL_DIR"
  echo "  ✓ Downloaded."
fi

# Run bootstrap to init DB and migrations
echo "  ◆ Initializing database..."
CLAUDE_PLUGIN_ROOT="$INSTALL_DIR" bash "$INSTALL_DIR/shared/bootstrap.sh" >/dev/null 2>&1
echo "  ✓ Database ready."

echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Get started:"
echo "    cd ~/.software-of-you && claude"
echo ""
echo "  Then just talk:"
echo "    \"Add a contact named Sarah Chen\""
echo "    \"Connect my Google account\""
echo "    \"Import this CSV of my clients\""
echo ""
