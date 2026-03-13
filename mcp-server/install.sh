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

# Install package
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "  Installing from: $SCRIPT_DIR"
"$PYTHON" -m pip install -e "$SCRIPT_DIR" --quiet 2>/dev/null || \
    "$PYTHON" -m pip install -e "$SCRIPT_DIR" --user --quiet

echo "  ✓ Package installed"

# Run setup (--no-license for personal deployment)
echo ""
"$PYTHON" -m software_of_you setup --no-license

echo ""
echo "  ════════════════════════════════════════"
echo "  Next: Restart Claude Desktop, then say hello!"
echo ""
