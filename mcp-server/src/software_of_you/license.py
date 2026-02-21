"""License activation and validation for Software of You.

Uses Lemon Squeezy's License API. No API key needed client-side —
the license key itself is the auth token. All network calls use
stdlib urllib (no new dependencies).

License data stored at ~/.local/share/software-of-you/license.json
(separate from DB because it must be checkable before DB exists).
"""

import json
import platform
import socket
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from software_of_you.db import DATA_DIR

LICENSE_PATH = DATA_DIR / "license.json"
ACTIVATE_URL = "https://api.lemonsqueezy.com/v1/licenses/activate"
VALIDATE_URL = "https://api.lemonsqueezy.com/v1/licenses/validate"
DEACTIVATE_URL = "https://api.lemonsqueezy.com/v1/licenses/deactivate"

# Set this to the actual Lemon Squeezy product ID after creating the storefront
PRODUCT_ID = None  # TODO: set after storefront is live

GRACE_PERIOD_DAYS = 3


def _instance_name() -> str:
    """Generate a human-readable instance name for this machine."""
    hostname = socket.gethostname().split(".")[0].lower()
    system = platform.system().lower()
    return f"{hostname}-{system}"


def _post(url: str, data: dict) -> dict:
    """POST form data to Lemon Squeezy API. Returns parsed JSON."""
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={"Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _is_test_key(key: str) -> bool:
    """Check if this is a test/beta key that bypasses the API."""
    return key.upper().startswith("TEST")


def activate_license(key: str) -> dict:
    """Activate a license key on this machine.

    Returns dict with customer info on success.
    Raises RuntimeError on invalid key or wrong product.

    Keys starting with "TEST" skip the API and activate locally
    (for beta testers before the storefront is live).
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if _is_test_key(key):
        license_data = {
            "license_key": key,
            "instance_id": "test",
            "instance_name": _instance_name(),
            "product_id": None,
            "customer_name": "",
            "customer_email": "",
            "activated_at": datetime.now().isoformat(),
            "status": "active",
            "test_mode": True,
        }
        LICENSE_PATH.write_text(json.dumps(license_data, indent=2) + "\n")
        return license_data

    try:
        result = _post(ACTIVATE_URL, {
            "license_key": key,
            "instance_name": _instance_name(),
        })
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            err = json.loads(body)
            msg = err.get("error", body)
        except json.JSONDecodeError:
            msg = body or str(e)
        raise RuntimeError(f"Activation failed: {msg}") from None
    except (urllib.error.URLError, OSError) as e:
        # Network error — grant grace period
        return _store_pending(key, str(e))

    # Verify product ID if configured
    meta = result.get("meta", {})
    if PRODUCT_ID is not None:
        actual_product = meta.get("product_id")
        if actual_product != PRODUCT_ID:
            raise RuntimeError(
                "This license key is for a different product."
            )

    # Store activation
    license_data = {
        "license_key": key,
        "instance_id": result.get("instance", {}).get("id", ""),
        "instance_name": _instance_name(),
        "product_id": meta.get("product_id"),
        "customer_name": meta.get("customer_name", ""),
        "customer_email": meta.get("customer_email", ""),
        "activated_at": datetime.now().isoformat(),
        "status": "active",
    }
    LICENSE_PATH.write_text(json.dumps(license_data, indent=2) + "\n")
    return license_data


def _store_pending(key: str, error: str) -> dict:
    """Store a pending activation when network is unavailable."""
    grace_expires = (datetime.now() + timedelta(days=GRACE_PERIOD_DAYS)).isoformat()
    license_data = {
        "license_key": key,
        "instance_id": "",
        "instance_name": _instance_name(),
        "product_id": None,
        "customer_name": "",
        "customer_email": "",
        "activated_at": datetime.now().isoformat(),
        "status": "pending",
        "grace_expires": grace_expires,
        "pending_reason": error,
    }
    LICENSE_PATH.write_text(json.dumps(license_data, indent=2) + "\n")
    return license_data


def is_activated() -> bool:
    """Check if a valid license exists locally (fast, no network)."""
    info = get_license_info()
    if info is None:
        return False

    status = info.get("status")
    if status == "active":
        return True

    if status == "pending":
        grace = info.get("grace_expires", "")
        if grace:
            try:
                expires = datetime.fromisoformat(grace)
                return datetime.now() < expires
            except ValueError:
                return False
    return False


def get_license_info() -> dict | None:
    """Read stored license data. Returns None if no license file."""
    if not LICENSE_PATH.exists():
        return None
    try:
        return json.loads(LICENSE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def validate_license() -> bool:
    """Re-validate license key with Lemon Squeezy (requires network).

    Returns True if valid, False otherwise. Updates local status.
    """
    info = get_license_info()
    if info is None:
        return False

    try:
        result = _post(VALIDATE_URL, {
            "license_key": info["license_key"],
            "instance_id": info.get("instance_id", ""),
        })
        valid = result.get("valid", False)
        if valid:
            info["status"] = "active"
            info.pop("grace_expires", None)
            info.pop("pending_reason", None)
            LICENSE_PATH.write_text(json.dumps(info, indent=2) + "\n")
        return valid
    except (urllib.error.URLError, OSError):
        return is_activated()  # Fall back to local check


def deactivate_license() -> bool:
    """Deactivate license on this machine. Frees the activation slot.

    Returns True if deactivated (or no license to deactivate).
    """
    info = get_license_info()
    if info is None:
        return True

    # Try remote deactivation (best effort)
    try:
        _post(DEACTIVATE_URL, {
            "license_key": info["license_key"],
            "instance_id": info.get("instance_id", ""),
        })
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        pass  # Remote deactivation is best-effort

    # Remove local license file
    try:
        LICENSE_PATH.unlink()
    except OSError:
        pass

    return True
