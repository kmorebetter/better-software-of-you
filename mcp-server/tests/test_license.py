"""Tests for U9: OAuth callback escaping (M1), secrets-at-rest 0600 (L1),
and license hardening — TEST-key gating + anchored offline grace (L2).

All network calls are monkeypatched; nothing here reaches Lemon Squeezy or
Google. No secret value is ever printed or logged.
"""

import io
import json
import os
import urllib.error
from datetime import datetime, timedelta

import pytest

from software_of_you import google_auth, license as license_mod, slack_auth


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def license_paths(tmp_path, monkeypatch):
    """Point license.py at an isolated temp dir.

    ``license.py`` binds ``DATA_DIR`` / ``LICENSE_PATH`` at import time, so the
    db-path fixture in conftest is not enough — patch the module constants too.
    """
    data_dir = tmp_path / "software-of-you"
    data_dir.mkdir(parents=True, exist_ok=True)
    license_path = data_dir / "license.json"
    monkeypatch.setattr(license_mod, "DATA_DIR", data_dir)
    monkeypatch.setattr(license_mod, "LICENSE_PATH", license_path)
    # Default: TEST-key bypass is OFF unless a test opts in.
    monkeypatch.delenv(license_mod.TEST_LICENSE_ENV, raising=False)
    return license_path


def _mode(path) -> str:
    return oct(os.stat(path).st_mode & 0o777)


# ── M1: OAuth callback escapes hostile error param ─────────────────────────


def _render_error_callback(handler_cls, error_value: str) -> bytes:
    """Drive a BaseHTTPRequestHandler subclass's do_GET for the error branch
    without a real socket, capturing the bytes written to wfile."""
    handler = handler_cls.__new__(handler_cls)  # skip socket __init__
    handler.path = "/?error=" + error_value
    handler.wfile = io.BytesIO()
    # Stub the response-writing machinery — we only care about the HTML body.
    handler.send_response = lambda *a, **k: None
    handler.send_header = lambda *a, **k: None
    handler.end_headers = lambda *a, **k: None
    handler.do_GET()
    return handler.wfile.getvalue()


def test_google_callback_escapes_hostile_error():
    hostile = "</body><script>alert(1)</script>"
    body = _render_error_callback(google_auth._OAuthHandler, hostile)
    assert b"<script>alert(1)</script>" not in body
    assert b"&lt;script&gt;" in body


def test_slack_callback_escapes_hostile_error():
    # Parity check — the already-fixed sibling must stay fixed.
    hostile = "</body><script>alert(2)</script>"
    body = _render_error_callback(slack_auth._OAuthHandler, hostile)
    assert b"<script>alert(2)</script>" not in body
    assert b"&lt;script&gt;" in body


# ── L2: TEST-key bypass requires explicit opt-in ───────────────────────────


def test_test_key_does_not_autoactivate_without_optin(license_paths, monkeypatch):
    """With the opt-in env var UNSET, a TEST* key must NOT bypass the API."""
    monkeypatch.delenv(license_mod.TEST_LICENSE_ENV, raising=False)
    assert license_mod._is_test_key("TEST123") is False

    # It should fall through to the API path — stub the API to reject it.
    def _boom(url, data):
        raise urllib.error.HTTPError(url, 403, "invalid", {}, None)

    monkeypatch.setattr(license_mod, "_post", _boom)
    with pytest.raises(RuntimeError):
        license_mod.activate_license("TEST123")
    # No license file should have been written.
    assert not license_paths.exists()


def test_test_key_activates_with_optin(license_paths, monkeypatch):
    """With the opt-in env var SET, a TEST* key activates locally (no network)."""
    monkeypatch.setenv(license_mod.TEST_LICENSE_ENV, "1")

    def _no_network(url, data):  # pragma: no cover - must never be called
        raise AssertionError("API must not be called for an opted-in TEST key")

    monkeypatch.setattr(license_mod, "_post", _no_network)
    assert license_mod._is_test_key("TEST123") is True
    data = license_mod.activate_license("TEST123")
    assert data["status"] == "active"
    assert data["test_mode"] is True
    assert license_mod.is_activated() is True


# ── L2: offline grace requires & is anchored to a prior activation ─────────


def _network_down(url, data):
    raise urllib.error.URLError("network down")


def test_grace_denied_without_prior_activation(license_paths, monkeypatch):
    """A network error with NO prior activation must not grant access."""
    monkeypatch.setattr(license_mod, "_post", _network_down)
    with pytest.raises(RuntimeError):
        license_mod.activate_license("REAL-KEY-0001")
    assert not license_paths.exists()
    assert license_mod.is_activated() is False


def test_grace_granted_and_anchored_with_prior_activation(license_paths, monkeypatch):
    """With a prior real activation, grace is granted and anchored to that
    activation — and repeated failures do not extend the grace window."""
    # Seed a prior REAL (non-test) successful activation 1 day ago.
    anchor_dt = datetime.now() - timedelta(days=1)
    prior = {
        "license_key": "REAL-KEY-0001",
        "instance_id": "inst-123",
        "instance_name": "host-darwin",
        "product_id": 42,
        "customer_name": "",
        "customer_email": "",
        "activated_at": anchor_dt.isoformat(),
        "status": "active",
    }
    license_paths.write_text(json.dumps(prior, indent=2) + "\n")

    # First network failure → grace granted, anchored to the prior activation.
    monkeypatch.setattr(license_mod, "_post", _network_down)
    result1 = license_mod.activate_license("REAL-KEY-0001")
    assert result1["status"] == "pending"
    grace1 = result1["grace_expires"]
    expected = (anchor_dt + timedelta(days=license_mod.GRACE_PERIOD_DAYS)).isoformat()
    assert grace1 == expected
    assert license_mod.is_activated() is True  # within the 3-day window

    # Second failure must NOT push the expiry out — it stays anchored.
    result2 = license_mod.activate_license("REAL-KEY-0001")
    assert result2["grace_expires"] == grace1


def test_grace_not_granted_from_prior_test_record(license_paths, monkeypatch):
    """A prior TEST-mode record is not a real activation — it must not seed
    offline grace for a normal key."""
    prior = {
        "license_key": "TESTABC",
        "instance_id": "test",
        "status": "active",
        "test_mode": True,
        "activated_at": datetime.now().isoformat(),
    }
    license_paths.write_text(json.dumps(prior, indent=2) + "\n")
    monkeypatch.setattr(license_mod, "_post", _network_down)
    with pytest.raises(RuntimeError):
        license_mod.activate_license("REAL-KEY-0002")


def test_grace_expires_after_anchor_window(license_paths, monkeypatch):
    """An anchor older than the grace window yields an already-expired grace —
    access is not open indefinitely."""
    old_anchor = datetime.now() - timedelta(days=license_mod.GRACE_PERIOD_DAYS + 2)
    prior = {
        "license_key": "REAL-KEY-0003",
        "instance_id": "inst-9",
        "status": "active",
        "activated_at": old_anchor.isoformat(),
    }
    license_paths.write_text(json.dumps(prior, indent=2) + "\n")
    monkeypatch.setattr(license_mod, "_post", _network_down)
    result = license_mod.activate_license("REAL-KEY-0003")
    assert result["status"] == "pending"
    # Grace already lapsed because it is anchored to the old activation.
    assert license_mod.is_activated() is False


# ── L1: secret files are written 0600 ──────────────────────────────────────


def test_license_file_is_0600_on_test_activation(license_paths, monkeypatch):
    monkeypatch.setenv(license_mod.TEST_LICENSE_ENV, "1")
    monkeypatch.setattr(
        license_mod, "_post",
        lambda url, data: (_ for _ in ()).throw(AssertionError("no network")),
    )
    license_mod.activate_license("TEST999")
    assert _mode(license_paths) == "0o600"


def test_license_file_is_0600_on_real_activation(license_paths, monkeypatch):
    def _ok(url, data):
        return {
            "instance": {"id": "inst-1"},
            "meta": {"product_id": None, "customer_name": "", "customer_email": ""},
        }

    monkeypatch.setattr(license_mod, "_post", _ok)
    license_mod.activate_license("REAL-KEY-1234")
    assert _mode(license_paths) == "0o600"


def test_google_token_file_is_0600(tmp_path, monkeypatch):
    data_dir = tmp_path / "software-of-you"
    tokens_dir = data_dir / "tokens"
    monkeypatch.setattr(google_auth, "DATA_DIR", data_dir)
    monkeypatch.setattr(google_auth, "TOKENS_DIR", tokens_dir)
    monkeypatch.setattr(google_auth, "LEGACY_TOKEN_FILE", data_dir / "google_token.json")
    google_auth.save_token({"access_token": "x", "refresh_token": "y"}, email="a@b.com")
    saved = tokens_dir / google_auth._email_to_filename("a@b.com")
    assert _mode(saved) == "0o600"


def test_slack_token_file_is_0600(tmp_path, monkeypatch):
    data_dir = tmp_path / "software-of-you"
    data_dir.mkdir(parents=True, exist_ok=True)
    token_path = data_dir / "slack_token.json"
    monkeypatch.setattr(slack_auth, "DATA_DIR", data_dir)
    monkeypatch.setattr(slack_auth, "TOKEN_PATH", token_path)
    slack_auth.save_token({"access_token": "x"})
    assert _mode(token_path) == "0o600"
