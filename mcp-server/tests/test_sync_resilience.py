"""Sync resilience tests (U7 / finding M2).

A mid-sync OAuth token expiry must refresh+retry, and partial failures must
NOT report success or advance the freshness timestamp — otherwise auto-sync
waits out the 15-minute freshness window instead of retrying the dropped items.

These tests exercise the core, network-free seams:

* the partial-failure *accounting* — the sync function returns ``failed > 0``
  when some per-item fetches fail (constructed by monkeypatching the per-item
  network call to raise on some inputs);
* the timestamp-*gating* decision — the sync function only advances
  ``<service>_last_synced`` on a fully-clean run, via the pure helper
  ``_should_mark_synced(failed)``;
* the 401 refresh+retry — a per-item 401 triggers a single token refresh and a
  single retry of that item.

Full Google/Slack API mocking is avoided: only ``_api_get`` (the per-call HTTP
seam) and ``_refresh_token`` are monkeypatched.
"""

import urllib.error

import pytest

from software_of_you import google_sync, slack_sync


# ── Pure helper: the timestamp-gating decision ───────────────────────────────


def test_should_mark_synced_only_on_clean_run():
    # Clean run advances the timestamp; any failure leaves it.
    assert google_sync._should_mark_synced(0) is True
    assert google_sync._should_mark_synced(1) is False
    assert google_sync._should_mark_synced(7) is False
    # Slack mirrors the same gate.
    assert slack_sync._should_mark_synced(0) is True
    assert slack_sync._should_mark_synced(1) is False


def _http_401(url):
    return urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)


def _last_synced(soy_db, key):
    rows = soy_db.execute("SELECT value FROM soy_meta WHERE key = ?", (key,))
    return rows[0]["value"] if rows else None


# ── Gmail: partial-failure accounting + timestamp gating ─────────────────────


def test_sync_gmail_partial_failure_does_not_advance_timestamp(soy_db, monkeypatch):
    """Some per-message fetches fail → failed > 0 and the timestamp is NOT set."""
    # The list call returns three messages; the per-message metadata fetch
    # succeeds for msg "ok" and raises for the other two.
    list_url = f"{google_sync.GMAIL_API}/messages?maxResults=50&q=newer_than:7d"

    def fake_api_get(url, token):
        if url == list_url:
            return {"messages": [{"id": "ok"}, {"id": "bad1"}, {"id": "bad2"}]}
        if "/messages/ok" in url:
            return {
                "payload": {"headers": [
                    {"name": "From", "value": "Real Person <real@example.com>"},
                    {"name": "To", "value": "me@example.com"},
                    {"name": "Subject", "value": "Hi"},
                ]},
                "snippet": "hello",
                "threadId": "t1",
                "labelIds": [],
                "internalDate": "0",
            }
        # The two "bad" messages fail with a non-auth error (no refresh).
        raise RuntimeError("boom")

    monkeypatch.setattr(google_sync, "_api_get", fake_api_get)
    # No refresh available — even if a 401 path were hit, refresh returns None.
    monkeypatch.setattr(google_sync, "_refresh_token", lambda email: None)

    result = google_sync.sync_gmail(token="tok", account_email=None)

    assert result["synced"] == 1
    assert result["failed"] == 2
    # Partial failure must NOT mark the sync fresh.
    assert _last_synced(soy_db, "gmail_last_synced") is None


def test_sync_gmail_clean_run_advances_timestamp(soy_db, monkeypatch):
    """All per-message fetches succeed → failed == 0 and the timestamp IS set."""
    list_url = f"{google_sync.GMAIL_API}/messages?maxResults=50&q=newer_than:7d"

    def fake_api_get(url, token):
        if url == list_url:
            return {"messages": [{"id": "a"}, {"id": "b"}]}
        return {
            "payload": {"headers": [
                {"name": "From", "value": "P <p@example.com>"},
                {"name": "To", "value": "me@example.com"},
                {"name": "Subject", "value": "S"},
            ]},
            "snippet": "x",
            "threadId": "t",
            "labelIds": [],
            "internalDate": "0",
        }

    monkeypatch.setattr(google_sync, "_api_get", fake_api_get)

    result = google_sync.sync_gmail(token="tok", account_email=None)

    assert result["failed"] == 0
    assert result["synced"] == 2
    assert _last_synced(soy_db, "gmail_last_synced") is not None


def test_sync_gmail_401_triggers_refresh_and_retry(soy_db, monkeypatch):
    """A per-message 401 refreshes the token once and retries the item once."""
    list_url = f"{google_sync.GMAIL_API}/messages?maxResults=50&q=newer_than:7d"
    refresh_calls = {"n": 0}
    # The item fetch raises 401 on the first attempt (with the stale token) and
    # succeeds on the retry (after the token is swapped to "fresh").
    attempts = {"item": 0}

    def fake_api_get(url, token):
        if "userinfo" in url:
            return {"email": "me@example.com"}
        if url == list_url:
            return {"messages": [{"id": "x"}]}
        attempts["item"] += 1
        if token != "fresh":
            raise _http_401(url)
        return {
            "payload": {"headers": [
                {"name": "From", "value": "P <p@example.com>"},
                {"name": "To", "value": "me@example.com"},
                {"name": "Subject", "value": "S"},
            ]},
            "snippet": "x",
            "threadId": "t",
            "labelIds": [],
            "internalDate": "0",
        }

    def fake_refresh(email):
        refresh_calls["n"] += 1
        return "fresh"

    monkeypatch.setattr(google_sync, "_api_get", fake_api_get)
    monkeypatch.setattr(google_sync, "_refresh_token", fake_refresh)

    result = google_sync.sync_gmail(token="stale", account_email=None)

    assert refresh_calls["n"] == 1  # refreshed exactly once
    assert attempts["item"] == 2  # original attempt + one retry
    assert result["synced"] == 1
    assert result["failed"] == 0
    assert _last_synced(soy_db, "gmail_last_synced") is not None


def test_sync_gmail_401_with_no_refresh_counts_as_failure(soy_db, monkeypatch):
    """401 with no refreshable token → the item is dropped and counted failed."""
    list_url = f"{google_sync.GMAIL_API}/messages?maxResults=50&q=newer_than:7d"

    def fake_api_get(url, token):
        if url == list_url:
            return {"messages": [{"id": "x"}]}
        raise _http_401(url)

    monkeypatch.setattr(google_sync, "_api_get", fake_api_get)
    monkeypatch.setattr(google_sync, "_refresh_token", lambda email: None)

    result = google_sync.sync_gmail(token="stale", account_email=None)

    assert result["synced"] == 0
    assert result["failed"] == 1
    assert _last_synced(soy_db, "gmail_last_synced") is None


# ── Slack: partial-failure accounting + timestamp gating ─────────────────────


def test_sync_messages_partial_failure_does_not_advance_timestamp(soy_db, monkeypatch):
    """A per-channel failure → failed > 0 and slack_last_synced is NOT set."""
    # Seed two monitored channels.
    conn = soy_db.get_connection()
    try:
        conn.execute(
            "INSERT INTO slack_channels (slack_channel_id, name, is_dm, is_monitored) "
            "VALUES ('C_OK', 'ok', 0, 1)"
        )
        conn.execute(
            "INSERT INTO slack_channels (slack_channel_id, name, is_dm, is_monitored) "
            "VALUES ('C_BAD', 'bad', 0, 1)"
        )
        conn.commit()
    finally:
        conn.close()

    def fake_api_get(method, token, params=None):
        if method == "users.list":
            return {"ok": True, "members": []}
        if method == "conversations.history":
            if params.get("channel") == "C_BAD":
                raise RuntimeError("channel boom")
            return {"ok": True, "messages": []}
        return {"ok": True}

    monkeypatch.setattr(slack_sync, "_api_get", fake_api_get)

    result = slack_sync.sync_messages(token="tok", days=7)

    assert result["failed"] == 1
    assert "errors" in result
    assert _last_synced(soy_db, "slack_last_synced") is None


def test_sync_messages_clean_run_advances_timestamp(soy_db, monkeypatch):
    """All channels succeed → failed == 0 and slack_last_synced IS set."""
    conn = soy_db.get_connection()
    try:
        conn.execute(
            "INSERT INTO slack_channels (slack_channel_id, name, is_dm, is_monitored) "
            "VALUES ('C_OK', 'ok', 0, 1)"
        )
        conn.commit()
    finally:
        conn.close()

    def fake_api_get(method, token, params=None):
        if method == "users.list":
            return {"ok": True, "members": []}
        if method == "conversations.history":
            return {"ok": True, "messages": []}
        return {"ok": True}

    monkeypatch.setattr(slack_sync, "_api_get", fake_api_get)

    result = slack_sync.sync_messages(token="tok", days=7)

    assert result["failed"] == 0
    assert _last_synced(soy_db, "slack_last_synced") is not None
