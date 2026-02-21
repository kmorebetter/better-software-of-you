"""System status tool — status, Google setup, backup, onboarding."""

from mcp.server.fastmcp import FastMCP

from software_of_you.db import (
    execute, DB_PATH, DATA_DIR, BACKUP_DIR,
    backup_db, get_installed_modules,
)


def register(server: FastMCP) -> None:
    @server.tool()
    def system_status(action: str = "status") -> dict:
        """System management for Software of You.

        Actions:
          status        — Show data stats, installed modules, Google connection
          setup_google  — Start Google OAuth flow (opens browser for authorization)
          revoke_google — Disconnect Google account
          backup        — Create a database backup now

        The Google connection enables email sync and calendar integration.
        Users say "connect my Google account" to trigger setup_google.
        """
        if action == "status":
            return _status()
        elif action == "setup_google":
            return _setup_google()
        elif action == "revoke_google":
            return _revoke_google()
        elif action == "backup":
            return _backup()
        else:
            return {"error": f"Unknown action: {action}. Use: status, setup_google, revoke_google, backup"}


def _get_customer_name() -> str:
    """Read customer name from soy_meta (synced from license at startup)."""
    try:
        rows = execute("SELECT value FROM soy_meta WHERE key = 'customer_name'")
        if rows and rows[0]["value"]:
            return rows[0]["value"]
    except Exception:
        pass
    return ""


def _compute_onboarding_stage(stats: dict, google_connected: bool) -> dict:
    """Compute onboarding stage and guidance from current data state.

    Stages:
      fresh         — 0 contacts, no Google
      has_contacts  — 1-2 contacts, no Google
      has_google    — Google connected, <3 contacts
      active        — 3+ contacts, Google connected
    """
    contacts = stats.get("contacts", 0)
    has_interaction = False
    has_project = False

    try:
        rows = execute("SELECT COUNT(*) as n FROM interactions")
        has_interaction = rows[0]["n"] > 0
    except Exception:
        pass

    try:
        rows = execute("SELECT COUNT(*) as n FROM projects")
        has_project = rows[0]["n"] > 0
    except Exception:
        pass

    # Determine stage
    if contacts == 0 and not google_connected:
        stage = "fresh"
        suggestions = ["Greet by name", "Ask about their first contact"]
        presentation = "Brand new setup. Be warm and brief. One question."
    elif contacts <= 2 and not google_connected:
        stage = "has_contacts"
        if not has_interaction:
            suggestions = ["Suggest logging an interaction with one of their contacts"]
        else:
            suggestions = ["Suggest connecting Google for email and calendar"]
        presentation = "Early user. Suggest one next step."
    elif google_connected and contacts < 3:
        stage = "has_google"
        suggestions = ["Suggest exploring email or calendar data", "Or adding more contacts"]
        presentation = "Google connected. Encourage exploring what synced."
    else:
        stage = "active"
        suggestions = []
        presentation = "Full capabilities. No onboarding nudges."

    # Build progress flags
    progress = {
        "contacts_added": contacts > 0,
        "interaction_logged": has_interaction,
        "google_connected": google_connected,
        "project_created": has_project,
    }

    customer_name = _get_customer_name()
    first_name = customer_name.split()[0] if customer_name else ""

    return {
        "onboarding_stage": stage,
        "customer_name": first_name,
        "onboarding_progress": progress,
        "suggestions": suggestions,
        "presentation": presentation,
    }


def _status():
    modules = get_installed_modules()

    stats = {"contacts": 0, "projects": 0, "emails": 0, "transcripts": 0}
    try:
        stats["contacts"] = execute("SELECT COUNT(*) as n FROM contacts")[0]["n"]
    except Exception:
        pass

    if "project-tracker" in modules:
        try:
            stats["projects"] = execute("SELECT COUNT(*) as n FROM projects")[0]["n"]
        except Exception:
            pass

    if "gmail" in modules:
        try:
            stats["emails"] = execute("SELECT COUNT(*) as n FROM emails")[0]["n"]
        except Exception:
            pass

    if "conversation-intelligence" in modules:
        try:
            stats["transcripts"] = execute("SELECT COUNT(*) as n FROM transcripts")[0]["n"]
        except Exception:
            pass

    # Google status
    token_path = DATA_DIR / "google_token.json"
    google_connected = token_path.exists()

    # Onboarding stage
    onboarding = _compute_onboarding_stage(stats, google_connected)

    return {
        "result": {
            "data_dir": str(DATA_DIR),
            "db_path": str(DB_PATH),
            "db_exists": DB_PATH.exists(),
            "modules": modules,
            "stats": stats,
            "google_connected": google_connected,
        },
        "_context": {
            **onboarding,
            "suggestions": onboarding["suggestions"] + [
                "Offer to connect Google if not connected" if not google_connected and onboarding["onboarding_stage"] != "fresh" else None,
                "Suggest adding contacts if count is 0" if stats["contacts"] == 0 and onboarding["onboarding_stage"] != "fresh" else None,
            ],
        },
    }


def _setup_google():
    try:
        from software_of_you.google_auth import run_auth_flow
        result = run_auth_flow()
        return {
            "result": result,
            "_context": {
                "presentation": "Tell the user Google is connected. Suggest syncing emails or checking calendar.",
            },
        }
    except Exception as e:
        return {
            "error": f"Google setup failed: {e}",
            "_context": {
                "presentation": "Explain the error and suggest trying again.",
            },
        }


def _revoke_google():
    try:
        from software_of_you.google_auth import revoke_token
        revoke_token()
        return {
            "result": {"message": "Google access revoked. Token removed."},
            "_context": {
                "presentation": "Confirm Google is disconnected. Email and calendar sync will stop.",
            },
        }
    except Exception as e:
        return {"error": f"Revoke failed: {e}"}


def _backup():
    path = backup_db()
    if path:
        return {
            "result": {"backup_path": str(path), "message": "Backup created."},
            "_context": {"presentation": "Confirm backup was created."},
        }
    return {"error": "No database to back up."}
