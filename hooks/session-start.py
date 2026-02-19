#!/usr/bin/env python3
"""SessionStart hook for Software of You.

Runs on every Claude Code session start:
1. Creates database if it doesn't exist
2. Runs all migrations (idempotent)
3. Detects installed modules from manifests
4. Resolves cross-module enhancements
5. Outputs session context for Claude
"""

import os
import sys
import json
import shutil
import subprocess
import glob

PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
DB_PATH = os.path.join(PLUGIN_ROOT, "data", "soy.db")
MIGRATIONS_DIR = os.path.join(PLUGIN_ROOT, "data", "migrations")
MODULES_DIR = os.path.join(PLUGIN_ROOT, "modules")


def find_sqlite3():
    """Find sqlite3 binary on the system."""
    path = shutil.which("sqlite3")
    if path:
        return path
    for candidate in ["/usr/bin/sqlite3", "/usr/local/bin/sqlite3", "/opt/homebrew/bin/sqlite3"]:
        if os.path.isfile(candidate):
            return candidate
    return None


SQLITE3 = find_sqlite3()


def run_sql(sql):
    """Execute SQL against the database."""
    if not SQLITE3:
        return "", 1
    try:
        result = subprocess.run(
            [SQLITE3, DB_PATH],
            input=sql,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip(), result.returncode
    except (subprocess.TimeoutExpired, OSError) as e:
        return str(e), 1


def run_migrations():
    """Run all migration files in sorted order. All are idempotent."""
    migration_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    if not migration_files:
        return False, "No migration files found"
    errors = []
    for mf in migration_files:
        try:
            with open(mf, "r") as f:
                sql = f.read()
            _, rc = run_sql(sql)
            if rc != 0:
                errors.append(os.path.basename(mf))
        except (IOError, OSError) as e:
            errors.append(f"{os.path.basename(mf)} ({e})")
    if errors:
        return False, f"Migration issues: {', '.join(errors)}"
    return True, "OK"


def detect_modules():
    """Read module manifests and return installed module info."""
    modules = {}
    manifest_files = glob.glob(os.path.join(MODULES_DIR, "*/manifest.json"))
    for mf in manifest_files:
        try:
            with open(mf, "r") as f:
                manifest = json.load(f)
            name = manifest.get("name")
            if name:
                modules[name] = manifest
        except (json.JSONDecodeError, IOError, KeyError):
            continue
    return modules


def resolve_enhancements(modules):
    """Determine which cross-module enhancements are active."""
    active = []
    for name, manifest in modules.items():
        for enh in manifest.get("enhancements", []):
            req = enh.get("requires_module", "")
            if req in modules:
                desc = enh.get("description", f"{name} + {req}")
                display = manifest.get("display_name", name)
                active.append(f"{display}: {desc}")
    return active


def output_result(context):
    """Print the hook output in Claude Code's expected format."""
    result = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    print(json.dumps(result))


def main():
    if not SQLITE3:
        output_result(
            "Software of You: sqlite3 not found. Please install SQLite to use this plugin. "
            "On macOS it should be pre-installed. On Linux: apt install sqlite3"
        )
        sys.exit(0)

    # Ensure data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Run migrations (creates DB if needed)
    success, msg = run_migrations()

    # Detect modules and resolve enhancements
    modules = detect_modules()
    module_names = [m.get("display_name", m.get("name", "unknown")) for m in modules.values()]
    enhancements = resolve_enhancements(modules)

    # Build context message
    parts = [f"Software of You ready. Database: {DB_PATH}."]
    if module_names:
        parts.append(f"Modules: {', '.join(module_names)} ({len(module_names)} installed).")
    else:
        parts.append("No modules detected.")
    if enhancements:
        parts.append(f"Active cross-module features: {'; '.join(enhancements)}.")
    if not success:
        parts.append(f"Warning: {msg}")

    output_result(" ".join(parts))
    sys.exit(0)


if __name__ == "__main__":
    main()
