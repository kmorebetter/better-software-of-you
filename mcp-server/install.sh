#!/bin/bash
set -e

echo ""
echo "  S O F T W A R E  of  Y O U"
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Installing..."
echo ""

# Check Python version
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$("$cmd" -c "import sys; print(sys.version_info.major)")
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)")
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  ✗ Python 3.10+ is required but not found."
    echo "  Install from: https://www.python.org/downloads/"
    exit 1
fi

echo "  ✓ Python $version found ($PYTHON)"

# Install into a virtual environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "  Creating virtual environment..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

# Activate and install
source "$VENV_DIR/bin/activate"
echo "  Installing from: $SCRIPT_DIR"
pip install -e "$SCRIPT_DIR" --quiet

echo "  ✓ Package installed (venv at .venv/)"

# Run setup (--no-license for personal deployment)
echo ""
python -m software_of_you setup --no-license

echo ""
echo "  ════════════════════════════════════════"
echo "  Next: Restart Claude Desktop, then say hello!"
echo ""
