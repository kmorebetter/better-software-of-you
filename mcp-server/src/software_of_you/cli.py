"""CLI for Software of You: setup, serve, status, uninstall.

Usage:
    software-of-you setup [--key=KEY]  # Activate license + configure Claude Desktop
    software-of-you serve              # Start MCP server (called by Claude Desktop)
    software-of-you status             # Show system status
    software-of-you uninstall          # Remove MCP config + deactivate license
"""

import json
import os
import platform
import sys
from pathlib import Path

from software_of_you.db import DB_PATH, DATA_DIR, init_db, execute, execute_write, get_installed_modules
from software_of_you.license import activate_license, is_activated, get_license_info, deactivate_license


def _claude_desktop_config_path() -> Path | None:
    """Find Claude Desktop config file for this platform."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
    elif system == "Linux":
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    return None


def _mcp_entry() -> dict:
    """Build the MCP server config entry using the current Python path."""
    return {
        "command": sys.executable,
        "args": ["-m", "software_of_you", "serve"],
    }


def _sync_license_to_db(info: dict) -> None:
    """Store license info in soy_meta so tools can read it."""
    try:
        for key, value in [
            ("license_status", info.get("status", "")),
            ("customer_name", info.get("customer_name", "")),
            ("customer_email", info.get("customer_email", "")),
        ]:
            execute_write(
                "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                (key, value),
            )
    except Exception:
        pass  # DB might not be ready yet during setup


def cmd_setup() -> int:
    """Set up Software of You: activate license + init DB + configure Claude Desktop."""
    print()
    print("  Software of You")
    print("  ════════════════════════════════════════")
    print()

    # Step 0: License activation
    key = None
    for arg in sys.argv[2:]:
        if arg.startswith("--key="):
            key = arg[len("--key="):]

    if key is None:
        print("  Enter your license key (from your purchase email):")
        print()
        try:
            key = input("  → ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Setup cancelled.")
            return 1

    if not key:
        print("  No license key provided. Get one at: https://softwareofyou.com")
        return 1

    print()
    print("  Activating license...")

    try:
        info = activate_license(key)
    except RuntimeError as e:
        print(f"  ✗ {e}")
        print()
        print("  Check your key and try again. If the problem persists,")
        print("  contact support at hello@softwareofyou.com")
        return 1

    if info.get("status") == "pending":
        print("  ⚠ Could not reach activation server (network issue).")
        print(f"  Granted {3}-day grace period — please retry when online.")
    else:
        name = info.get("customer_name", "")
        if name:
            print(f"  ✓ License activated for {name}")
        else:
            print("  ✓ License activated")

    print()

    # Step 1: Initialize database
    print(f"  Data directory: {DATA_DIR}")
    init_db()
    print(f"  Database ready: {DB_PATH}")

    # Sync license info into DB
    _sync_license_to_db(info)

    # Step 2: Find and update Claude Desktop config
    config_path = _claude_desktop_config_path()
    if config_path is None:
        print("\n  Could not detect Claude Desktop config location.")
        print("  Add this to your Claude Desktop config manually:\n")
        print(json.dumps({"mcpServers": {"software-of-you": _mcp_entry()}}, indent=2))
        return 0

    # Read existing config or start fresh
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            config = {}

    # Inject our MCP entry (preserve everything else)
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["software-of-you"] = _mcp_entry()

    # Write back
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"  Claude Desktop configured: {config_path}")

    # Done
    name = info.get("customer_name", "").split()[0] if info.get("customer_name") else ""
    print()
    print("  ════════════════════════════════════════")
    if name:
        print(f"  Welcome, {name}! Restart Claude Desktop to connect.")
    else:
        print("  Done! Restart Claude Desktop to connect.")
    print()
    print("  Then just start talking:")
    print('    "Add a contact named Sarah Chen"')
    print('    "What\'s on my calendar this week?"')
    print('    "Log a decision: we\'re switching to Postgres"')
    print()
    return 0


def cmd_serve() -> int:
    """Start the MCP server on stdio. Called by Claude Desktop, not users."""
    if not is_activated():
        print("Not activated. Run: software-of-you setup", file=sys.stderr)
        return 1

    # Initialize DB on every server start (migrations are idempotent)
    init_db()

    # Sync license info into soy_meta for tools to read
    info = get_license_info()
    if info:
        _sync_license_to_db(info)

    from software_of_you.server import create_server
    server = create_server()
    server.run(transport="stdio")
    return 0


def cmd_status() -> int:
    """Print system status."""
    print("Software of You — Status\n")

    # License
    info = get_license_info()
    if info and info.get("status") == "active":
        name = info.get("customer_name", "")
        label = f"active ({name})" if name else "active"
        print(f"  License:     {label}")
    elif info and info.get("status") == "pending":
        print(f"  License:     pending (grace period)")
    else:
        print("  License:     not activated")

    # Data directory
    print(f"  Data dir:    {DATA_DIR}")
    print(f"  Database:    {'exists' if DB_PATH.exists() else 'NOT FOUND'}")

    if not DB_PATH.exists():
        print("\n  Run `software-of-you setup` to initialize.")
        return 0

    # Contact count
    try:
        rows = execute("SELECT COUNT(*) as n FROM contacts")
        print(f"  Contacts:    {rows[0]['n']}")
    except Exception:
        print("  Contacts:    (error reading)")

    # Modules
    try:
        modules = get_installed_modules()
        print(f"  Modules:     {len(modules)} ({', '.join(modules) if modules else 'none'})")
    except Exception:
        print("  Modules:     (error reading)")

    # Claude Desktop config
    config_path = _claude_desktop_config_path()
    configured = False
    if config_path and config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            configured = "software-of-you" in config.get("mcpServers", {})
        except (json.JSONDecodeError, OSError):
            pass
    print(f"  Claude Desktop: {'configured' if configured else 'not configured'}")

    # Google connection
    token_path = DATA_DIR / "google_token.json"
    print(f"  Google:      {'connected' if token_path.exists() else 'not connected'}")

    return 0


def cmd_uninstall() -> int:
    """Remove MCP entry from Claude Desktop config + deactivate license."""
    # Deactivate license (frees activation slot)
    info = get_license_info()
    if info:
        print("Deactivating license...")
        deactivate_license()
        print("License deactivated.")

    config_path = _claude_desktop_config_path()
    if config_path is None or not config_path.exists():
        print("Claude Desktop config not found — nothing to remove.")
        return 0

    try:
        config = json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError):
        print("Could not read Claude Desktop config.")
        return 1

    servers = config.get("mcpServers", {})
    if "software-of-you" not in servers:
        print("Software of You is not in your Claude Desktop config.")
        return 0

    del servers["software-of-you"]
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    print("Removed Software of You from Claude Desktop config.")
    print(f"\nYour data is preserved at: {DATA_DIR}")
    print("To delete it: rm -rf " + str(DATA_DIR))
    return 0


COMMANDS = {
    "setup": cmd_setup,
    "serve": cmd_serve,
    "status": cmd_status,
    "uninstall": cmd_uninstall,
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: software-of-you <command>\n")
        print("Commands:")
        print("  setup [--key=KEY]  Activate license + configure Claude Desktop")
        print("  serve              Start MCP server (used by Claude Desktop)")
        print("  status             Show system status")
        print("  uninstall          Remove from Claude Desktop + deactivate license")
        return 0

    command = sys.argv[1]
    if command not in COMMANDS:
        print(f"Unknown command: {command}")
        print(f"Available: {', '.join(COMMANDS)}")
        return 1

    return COMMANDS[command]()
