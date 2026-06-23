"""Shared enum validation at the tool boundary.

The DB enforces these sets via CHECK constraints, but a constraint violation
surfaces as an opaque IntegrityError. Validating here returns a clear,
actionable error to Claude *before* any write happens.

Only non-empty values are validated — an empty string means "not provided,
use the column default", which is always a valid member of its set.
"""

# Allowed sets mirror the DB CHECK constraints (migrations 001/002/003).
INTERACTION_TYPE = {"email", "call", "meeting", "message", "other"}
DIRECTION = {"inbound", "outbound"}
PROJECT_STATUS = {"idea", "planning", "active", "paused", "completed", "cancelled"}
PRIORITY = {"low", "medium", "high", "urgent"}
TASK_STATUS = {"todo", "in_progress", "done", "blocked"}
CONTACT_TYPE = {"individual", "company"}
CONTACT_STATUS = {"active", "inactive", "archived"}


def validate_enum(value, allowed, field):
    """Return an error dict if a non-empty value is outside its allowed set.

    Returns ``None`` when the value is empty (not provided) or valid.
    """
    if value and value not in allowed:
        allowed_str = ", ".join(sorted(allowed))
        return {"error": f"{field} must be one of: {allowed_str}; got '{value}'"}
    return None
