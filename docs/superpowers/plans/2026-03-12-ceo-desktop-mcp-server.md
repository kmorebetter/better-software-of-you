# CEO Desktop MCP Server — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Software of You as a Claude Desktop MCP server with intelligence tools and Slack integration for a non-technical CEO.

**Architecture:** Self-contained Python MCP server (`mcp-server/`) using FastMCP over stdio. 13 existing data tools + 5 new intelligence tools + 1 Slack tool. SQLite database at `~/.local/share/software-of-you/`. Google and Slack sync via stdlib `urllib`.

**Tech Stack:** Python 3.10+, FastMCP (`mcp>=1.2.0`), SQLite, stdlib `urllib` for all API calls.

**Spec:** `docs/superpowers/specs/2026-03-12-ceo-desktop-mcp-server-design.md`

**Key paths:**
- MCP server root: `/Users/kerrymorrison/Projects/PersonalProjects/better-software-of-you/mcp-server/`
- Source: `mcp-server/src/software_of_you/`
- Tools: `mcp-server/src/software_of_you/tools/`
- Migrations: `mcp-server/src/software_of_you/migrations/`
- Plugin migrations (source of truth): `data/migrations/`

---

## Chunk 1: Foundation — Migrations & Cleanup

### Task 1: Copy Missing Migrations 011-014

The MCP server is missing 4 migrations that exist in the plugin's `data/migrations/`. The computed views in 014 are critical — every intelligence tool depends on them.

**Files:**
- Copy from: `data/migrations/011_decision_outcomes_v2.sql`
- Copy from: `data/migrations/012_performance_indexes.sql`
- Copy from: `data/migrations/013_user_profiles.sql`
- Copy from: `data/migrations/014_computed_views.sql`
- Copy to: `mcp-server/src/software_of_you/migrations/`

- [ ] **Step 1: Copy the 4 missing migration files**

```bash
cp data/migrations/011_decision_outcomes_v2.sql mcp-server/src/software_of_you/migrations/
cp data/migrations/012_performance_indexes.sql mcp-server/src/software_of_you/migrations/
cp data/migrations/013_user_profiles.sql mcp-server/src/software_of_you/migrations/
cp data/migrations/014_computed_views.sql mcp-server/src/software_of_you/migrations/
```

- [ ] **Step 2: Verify all 16 migrations are present**

```bash
ls -1 mcp-server/src/software_of_you/migrations/*.sql | wc -l
# Expected: 16
ls -1 mcp-server/src/software_of_you/migrations/*.sql
# Expected: 001 through 016, no gaps
```

- [ ] **Step 3: Test migrations run cleanly on a fresh DB**

```bash
cd mcp-server
python3 -c "
from software_of_you.db import init_db, execute, DB_PATH
import os, tempfile
# Use a temp DB to test
os.environ['XDG_DATA_HOME'] = tempfile.mkdtemp()
init_db()
# Verify computed views exist
views = execute(\"SELECT name FROM sqlite_master WHERE type='view' AND name LIKE 'v_%'\")
print(f'Views found: {len(views)}')
for v in views: print(f'  {v[\"name\"]}')
assert len(views) >= 8, f'Expected 8+ views, got {len(views)}'
print('PASS: All migrations applied, computed views exist')
"
```

- [ ] **Step 4: Commit**

```bash
git add mcp-server/src/software_of_you/migrations/011_*.sql \
        mcp-server/src/software_of_you/migrations/012_*.sql \
        mcp-server/src/software_of_you/migrations/013_*.sql \
        mcp-server/src/software_of_you/migrations/014_*.sql
git commit -m "fix: copy missing migrations 011-014 to MCP server

Intelligence tools depend on computed views from 014.
These were present in the plugin but missing from the
MCP server package."
```

---

### Task 2: Remove views.py from Server Registration

HTML view generation is irrelevant for Claude Desktop. Drop it from the server to reduce tool count and avoid confusing Claude.

**Files:**
- Modify: `mcp-server/src/software_of_you/server.py` (lines 90, 105)

- [ ] **Step 1: Remove views registration from server.py**

In `server.py`, remove these two lines:
```python
# Line 90: Remove this import
from software_of_you.tools.views import register as register_views

# Line 105: Remove this call
register_views(server)
```

Do NOT delete `tools/views.py` — just unregister it. It can be re-added later.

- [ ] **Step 2: Verify server still boots**

```bash
cd mcp-server
python3 -c "
from software_of_you.server import create_server
server = create_server()
print(f'Server created: {server.name}')
print('Tool count:', len(server._tool_manager._tools))
print('PASS: Server boots without views.py')
"
```

Expected: Server boots, tool count decreases by the number of tools `views.py` registered.

- [ ] **Step 3: Commit**

```bash
git add mcp-server/src/software_of_you/server.py
git commit -m "chore: remove HTML view generation from MCP server

Claude Desktop has its own UI — views.py is Claude Code only.
File preserved but unregistered. Tool count: 13 data tools."
```

---

## Chunk 2: Intelligence Tools

### Task 3: Create intelligence.py — meeting_prep Tool

The first and most complex intelligence tool. Queries `v_meeting_prep` for the event, enriches with per-attendee data from `v_contact_health` and `v_commitment_status`.

**Files:**
- Create: `mcp-server/src/software_of_you/tools/intelligence.py`

- [ ] **Step 1: Create intelligence.py with meeting_prep**

```python
"""Intelligence tools — meeting prep, nudges, commitments, relationship pulse, weekly review.

These wrap the pre-computed SQL views (from migration 014) and enrich
with cross-references. They are the "second brain" layer — the reason
a CEO uses this instead of just searching her email.
"""

import json
from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, rows_to_dicts


def _auto_sync_all() -> None:
    """Check freshness and sync stale services. Silently fails."""
    try:
        from software_of_you.google_sync import sync_service
        from datetime import datetime

        for key, service, threshold in [
            ("gmail_last_synced", "gmail", 900),
            ("calendar_last_synced", "calendar", 900),
            ("transcripts_last_scanned", "transcripts", 3600),
        ]:
            rows = execute("SELECT value FROM soy_meta WHERE key = ?", (key,))
            if rows:
                last = datetime.fromisoformat(rows[0]["value"])
                if (datetime.now() - last).total_seconds() < threshold:
                    continue
            sync_service(service)
    except Exception:
        pass


def _auto_sync_slack() -> None:
    """Check Slack freshness and sync if stale. Silently fails."""
    try:
        from datetime import datetime
        rows = execute("SELECT value FROM soy_meta WHERE key = 'slack_last_synced'", ())
        if rows:
            last = datetime.fromisoformat(rows[0]["value"])
            if (datetime.now() - last).total_seconds() < 900:
                return
        from software_of_you.slack_sync import sync_slack
        sync_slack()
    except Exception:
        pass


def register(server: FastMCP) -> None:

    @server.tool()
    def meeting_prep(
        event_id: int = 0,
        hours_ahead: int = 4,
        contact_name: str = "",
    ) -> dict:
        """Get a meeting prep brief for an upcoming calendar event.

        Includes: attendees, relationship history, open commitments,
        recent email threads, and topics from past transcripts.

        Args:
            event_id: Specific calendar event ID (0 = find next upcoming)
            hours_ahead: Look-ahead window in hours when event_id is 0
            contact_name: Find next event with this attendee
        """
        _auto_sync_all()

        # Find the event
        if event_id:
            events = execute(
                "SELECT * FROM v_meeting_prep WHERE event_id = ?", (event_id,)
            )
        elif contact_name:
            # Find next event with this attendee in the attendees JSON
            pattern = f"%{contact_name}%"
            events = execute(
                """SELECT * FROM v_meeting_prep
                   WHERE minutes_until > 0
                     AND (attendees LIKE ? OR title LIKE ?)
                   ORDER BY minutes_until ASC LIMIT 1""",
                (pattern, pattern),
            )
        else:
            events = execute(
                """SELECT * FROM v_meeting_prep
                   WHERE minutes_until > 0 AND minutes_until < ?
                   ORDER BY minutes_until ASC LIMIT 1""",
                (hours_ahead * 60,),
            )

        if not events:
            return {
                "result": None,
                "_context": {
                    "empty_state": f"No upcoming meetings in the next {hours_ahead} hours.",
                    "suggestions": ["Check tomorrow's calendar", "Add a calendar event"],
                },
            }

        event = rows_to_dicts(events)[0]

        # Parse attendee contact IDs
        contact_ids = []
        try:
            contact_ids = json.loads(event.get("contact_ids") or "[]")
        except (json.JSONDecodeError, TypeError):
            pass

        # Build per-attendee briefs
        attendee_briefs = []
        for cid in contact_ids:
            brief = {"contact_id": cid}

            # Relationship health
            health = execute("SELECT * FROM v_contact_health WHERE id = ?", (cid,))
            if health:
                h = rows_to_dicts(health)[0]
                brief["name"] = h.get("name", "")
                brief["company"] = h.get("company", "")
                brief["days_silent"] = h.get("days_silent")
                brief["relationship_depth"] = h.get("relationship_depth")
                brief["trajectory"] = h.get("trajectory")

            # Open commitments with this person
            commits = execute(
                "SELECT description, deadline_date, days_overdue, urgency FROM v_commitment_status WHERE owner_contact_id = ? AND status IN ('open', 'overdue') LIMIT 5",
                (cid,),
            )
            if commits:
                brief["open_commitments"] = rows_to_dicts(commits)

            # Recent emails (last 14 days)
            emails = execute(
                """SELECT subject, direction, received_at FROM emails
                   WHERE contact_id = ? AND received_at > datetime('now', '-14 days')
                   ORDER BY received_at DESC LIMIT 5""",
                (cid,),
            )
            if emails:
                brief["recent_emails"] = rows_to_dicts(emails)

            # Recent Slack messages
            try:
                slack_msgs = execute(
                    """SELECT content, channel_name, received_at FROM slack_messages
                       WHERE contact_id = ? AND received_at > datetime('now', '-14 days')
                       ORDER BY received_at DESC LIMIT 5""",
                    (cid,),
                )
                if slack_msgs:
                    brief["recent_slack"] = rows_to_dicts(slack_msgs)
            except Exception:
                pass  # Slack table may not exist yet

            # Last transcript mention
            transcripts = execute(
                """SELECT t.title, t.occurred_at FROM transcripts t
                   JOIN commitments c ON c.transcript_id = t.id
                   WHERE c.owner_id = ?
                   ORDER BY t.occurred_at DESC LIMIT 1""",
                (cid,),
            )
            if transcripts:
                brief["last_meeting"] = rows_to_dicts(transcripts)[0]

            attendee_briefs.append(brief)

        return {
            "result": {
                "event": event,
                "attendee_briefs": attendee_briefs,
                "attendee_count": len(attendee_briefs),
            },
            "_context": {
                "presentation": "Lead with the meeting title and time. Then per attendee: relationship context, open commitments (flag overdue ones), and recent communication. End with 2-3 suggested talking points based on the data.",
                "suggestions": ["Flag any overdue commitments prominently"],
            },
        }
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
cd mcp-server
python3 -c "from software_of_you.tools.intelligence import register; print('PASS: intelligence.py imports')"
```

- [ ] **Step 3: Commit**

```bash
git add mcp-server/src/software_of_you/tools/intelligence.py
git commit -m "feat: add meeting_prep intelligence tool

Queries v_meeting_prep for events, enriches with per-attendee
relationship health, commitments, recent emails/Slack, and
transcript history. First of 5 intelligence tools."
```

---

### Task 4: Add nudges, commitments, relationship_pulse, weekly_review

Add the remaining 4 intelligence tools to the same file.

**Files:**
- Modify: `mcp-server/src/software_of_you/tools/intelligence.py`

- [ ] **Step 1: Add nudges tool**

Append inside the `register()` function, after `meeting_prep`:

```python
    @server.tool()
    def nudges(
        tier: str = "all",
        limit: int = 20,
    ) -> dict:
        """Surface what needs attention — overdue follow-ups, stale relationships, missed commitments.

        Args:
            tier: Filter by urgency: urgent, soon, awareness, or all
            limit: Max items to return
        """
        _auto_sync_all()
        _auto_sync_slack()

        # Summary counts
        summary_rows = execute("SELECT * FROM v_nudge_summary")
        summary = rows_to_dicts(summary_rows) if summary_rows else []

        # Nudge items
        if tier and tier != "all":
            items = execute(
                "SELECT * FROM v_nudge_items WHERE tier = ? ORDER BY days_value ASC LIMIT ?",
                (tier, limit),
            )
        else:
            items = execute(
                "SELECT * FROM v_nudge_items ORDER BY CASE tier WHEN 'urgent' THEN 0 WHEN 'soon' THEN 1 ELSE 2 END, days_value ASC LIMIT ?",
                (limit,),
            )

        nudge_list = rows_to_dicts(items) if items else []

        if not nudge_list:
            return {
                "result": {"items": [], "summary": summary},
                "_context": {
                    "empty_state": "Nothing urgent — you're all caught up.",
                    "presentation": "Celebrate this! It's rare.",
                },
            }

        return {
            "result": {"items": nudge_list, "summary": summary, "count": len(nudge_list)},
            "_context": {
                "presentation": "Group by urgency tier. Lead with urgent items. For each: what it is, who it involves, how overdue. Keep it scannable.",
                "suggestions": ["Offer to take action on the top item"],
            },
        }
```

- [ ] **Step 2: Add commitments tool**

```python
    @server.tool()
    def commitments_view(
        status: str = "open",
        contact_id: int = 0,
        days: int = 14,
    ) -> dict:
        """Show commitments — promises made in meetings, tracked automatically.

        Args:
            status: Filter: open, overdue, completed, all
            contact_id: Filter by person (0 = all people)
            days: Look-back window for recent commitments
        """
        _auto_sync_all()  # Commitments come from transcripts

        if contact_id:
            rows = execute(
                "SELECT * FROM v_commitment_status WHERE owner_contact_id = ? ORDER BY days_overdue DESC",
                (contact_id,),
            )
        elif status == "overdue":
            rows = execute(
                "SELECT * FROM v_commitment_status WHERE urgency = 'overdue' OR days_overdue > 0 ORDER BY days_overdue DESC"
            )
        elif status == "all":
            rows = execute(
                "SELECT * FROM v_commitment_status ORDER BY deadline_date ASC"
            )
        else:
            rows = execute(
                "SELECT * FROM v_commitment_status WHERE status IN ('open', 'overdue') ORDER BY days_overdue DESC"
            )

        items = rows_to_dicts(rows) if rows else []

        if not items:
            return {
                "result": {"items": [], "count": 0},
                "_context": {
                    "empty_state": "No open commitments." if status != "all" else "No commitments recorded yet.",
                    "suggestions": ["Import a meeting transcript to extract commitments"],
                },
            }

        return {
            "result": {"items": items, "count": len(items)},
            "_context": {
                "presentation": "Group by person. For each: the commitment, when it was made, deadline, days overdue. Flag urgent ones.",
            },
        }
```

- [ ] **Step 3: Add relationship_pulse tool**

```python
    @server.tool()
    def relationship_pulse(
        contact_id: int = 0,
        threshold_days: int = 14,
    ) -> dict:
        """Deep relationship health check — who's warm, who's cooling, who's gone silent.

        Args:
            contact_id: Specific contact for deep dive (0 = show all, ranked by staleness)
            threshold_days: Days silent to flag as cooling
        """
        _auto_sync_all()
        _auto_sync_slack()

        if contact_id:
            rows = execute("SELECT * FROM v_contact_health WHERE id = ?", (contact_id,))
            if not rows:
                return {"error": f"No contact with id {contact_id}."}

            contact = rows_to_dicts(rows)[0]

            # Enrich with recent Slack
            try:
                slack_count = execute(
                    "SELECT COUNT(*) as n FROM slack_messages WHERE contact_id = ? AND received_at > datetime('now', '-30 days')",
                    (contact_id,),
                )
                contact["slack_messages_30d"] = slack_count[0]["n"] if slack_count else 0
            except Exception:
                contact["slack_messages_30d"] = 0

            return {
                "result": contact,
                "_context": {
                    "presentation": "Full relationship profile. Lead with how the relationship is doing (warm/cooling/cold based on days_silent vs threshold). Show communication breakdown: emails, Slack, meetings. Flag open commitments and next meeting.",
                },
            }
        else:
            # All contacts ranked by staleness
            rows = execute(
                "SELECT * FROM v_contact_health WHERE days_silent IS NOT NULL ORDER BY days_silent DESC"
            )
            contacts = rows_to_dicts(rows) if rows else []

            cooling = [c for c in contacts if (c.get("days_silent") or 0) >= threshold_days]
            warm = [c for c in contacts if (c.get("days_silent") or 0) < threshold_days]

            return {
                "result": {
                    "cooling": cooling,
                    "warm": warm,
                    "cooling_count": len(cooling),
                    "warm_count": len(warm),
                },
                "_context": {
                    "presentation": f"Show cooling relationships first ({len(cooling)} contacts silent for {threshold_days}+ days). Then warm ones. For each: name, company, days silent, last interaction type.",
                },
            }
```

- [ ] **Step 4: Add weekly_review tool**

```python
    @server.tool()
    def weekly_review(
        week_offset: int = 0,
    ) -> dict:
        """Aggregated week-in-review across all modules.

        Args:
            week_offset: 0 = current week (Mon-Sun), -1 = last week
        """
        _auto_sync_all()
        _auto_sync_slack()

        # Calculate ISO week boundaries
        from datetime import datetime, timedelta
        today = datetime.now()
        # Monday of target week
        monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        monday_str = monday.strftime("%Y-%m-%d")
        sunday = monday + timedelta(days=6)
        sunday_str = sunday.strftime("%Y-%m-%d")
        next_monday_str = (sunday + timedelta(days=1)).strftime("%Y-%m-%d")
        next_sunday_str = (sunday + timedelta(days=7)).strftime("%Y-%m-%d")

        data = {"week_start": monday_str, "week_end": sunday_str}

        # Meetings held
        meetings = execute(
            """SELECT id, title, start_time, end_time, attendees, contact_ids
               FROM calendar_events
               WHERE date(start_time) BETWEEN ? AND ? AND status != 'cancelled'
               ORDER BY start_time ASC""",
            (monday_str, sunday_str),
        )
        data["meetings"] = {"items": rows_to_dicts(meetings), "count": len(meetings)}

        # Commitments made this week (view has created_at)
        new_commits = execute(
            """SELECT * FROM v_commitment_status
               WHERE created_at BETWEEN ? AND ?""",
            (monday_str, sunday_str + " 23:59:59"),
        )
        # Completed this week (query commitments table directly — view doesn't expose completed_at)
        completed_commits = execute(
            """SELECT c.id, c.description, c.completed_at, co.name as owner_name
               FROM commitments c
               LEFT JOIN contacts co ON c.owner_contact_id = co.id
               WHERE c.status = 'completed'
                 AND c.completed_at BETWEEN ? AND ?""",
            (monday_str, sunday_str + " 23:59:59"),
        )
        data["commitments"] = {
            "made": len(new_commits) if new_commits else 0,
            "completed": len(completed_commits) if completed_commits else 0,
            "new_items": rows_to_dicts(new_commits) if new_commits else [],
        }

        # Relationships warming/cooling
        health_rows = execute("SELECT * FROM v_contact_health WHERE last_activity IS NOT NULL")
        contacts = rows_to_dicts(health_rows) if health_rows else []
        warming = [c for c in contacts if c.get("last_activity", "") >= monday_str]
        cooling = [c for c in contacts
                   if c.get("last_activity", "") < monday_str
                   and (c.get("days_silent") or 0) >= 14]
        data["relationships"] = {
            "warming": [{"name": c["name"], "company": c.get("company"), "last_activity": c["last_activity"]} for c in warming[:10]],
            "cooling": [{"name": c["name"], "company": c.get("company"), "days_silent": c["days_silent"]} for c in cooling[:10]],
        }

        # Decisions
        try:
            decisions = execute(
                "SELECT title, context, status, decided_at FROM decisions WHERE decided_at BETWEEN ? AND ?",
                (monday_str, sunday_str + " 23:59:59"),
            )
            data["decisions"] = rows_to_dicts(decisions) if decisions else []
        except Exception:
            data["decisions"] = []

        # Next week preview
        next_meetings = execute(
            """SELECT title, start_time, attendees FROM calendar_events
               WHERE date(start_time) BETWEEN ? AND ? AND status != 'cancelled'
               ORDER BY start_time ASC""",
            (next_monday_str, next_sunday_str),
        )
        upcoming_commits = execute(
            """SELECT * FROM v_commitment_status
               WHERE status IN ('open', 'overdue')
                 AND deadline_date BETWEEN ? AND ?""",
            (next_monday_str, next_sunday_str),
        )
        data["next_week"] = {
            "meetings": rows_to_dicts(next_meetings) if next_meetings else [],
            "pending_commitments": rows_to_dicts(upcoming_commits) if upcoming_commits else [],
        }

        return {
            "result": data,
            "_context": {
                "presentation": "Narrative weekly review. Lead with headline stats (N meetings, N commitments made/completed). Then: key meetings and takeaways, commitment status, relationship changes, decisions. End with next week preview and what to watch for.",
            },
        }
```

- [ ] **Step 5: Verify all 5 tools import cleanly**

```bash
cd mcp-server
python3 -c "
from software_of_you.tools.intelligence import register
from mcp.server.fastmcp import FastMCP
server = FastMCP('test')
register(server)
tools = list(server._tool_manager._tools.keys())
print(f'Intelligence tools registered: {len(tools)}')
for t in tools: print(f'  {t}')
assert len(tools) == 5, f'Expected 5 tools, got {len(tools)}'
print('PASS')
"
```

- [ ] **Step 6: Commit**

```bash
git add mcp-server/src/software_of_you/tools/intelligence.py
git commit -m "feat: add 5 intelligence tools — meeting_prep, nudges, commitments, relationship_pulse, weekly_review

These wrap the pre-computed SQL views and enrich with
cross-references. Each includes auto-sync triggers and
presentation guidance via _context fields."
```

---

### Task 5: Register Intelligence Tools in Server

**Files:**
- Modify: `mcp-server/src/software_of_you/server.py`

- [ ] **Step 1: Add intelligence registration**

In `create_server()`, add:

```python
from software_of_you.tools.intelligence import register as register_intelligence
# ... (after other register calls)
register_intelligence(server)
```

- [ ] **Step 2: Verify total tool count**

```bash
cd mcp-server
python3 -c "
from software_of_you.server import create_server
server = create_server()
tools = list(server._tool_manager._tools.keys())
print(f'Total tools: {len(tools)}')
for t in sorted(tools): print(f'  {t}')
# Expected: 13 data tools + 5 intelligence = 18
"
```

- [ ] **Step 3: Commit**

```bash
git add mcp-server/src/software_of_you/server.py
git commit -m "feat: register intelligence tools in MCP server

18 tools total: 13 data + 5 intelligence."
```

---

## Chunk 3: Slack Integration

### Task 6: Create Slack Migration

**Files:**
- Create: `mcp-server/src/software_of_you/migrations/017_slack_module.sql`

- [ ] **Step 1: Write the migration**

```sql
-- 017: Slack integration — channels and messages

CREATE TABLE IF NOT EXISTS slack_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_message_id TEXT UNIQUE NOT NULL,
    channel_id TEXT NOT NULL,
    channel_name TEXT,
    sender_id TEXT,
    sender_name TEXT,
    content TEXT,
    thread_ts TEXT,
    is_thread_parent INTEGER DEFAULT 0,
    contact_id INTEGER,
    received_at TEXT NOT NULL,
    synced_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (contact_id) REFERENCES contacts(id)
);

CREATE TABLE IF NOT EXISTS slack_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_channel_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    is_dm INTEGER DEFAULT 0,
    is_monitored INTEGER DEFAULT 1,
    last_synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_slack_msg_contact ON slack_messages(contact_id);
CREATE INDEX IF NOT EXISTS idx_slack_msg_channel ON slack_messages(channel_id);
CREATE INDEX IF NOT EXISTS idx_slack_msg_received ON slack_messages(received_at);

-- Register the Slack module
INSERT OR IGNORE INTO modules (name, version, enabled, installed_at)
VALUES ('slack', '1.0.0', 1, datetime('now'));
```

- [ ] **Step 2: Test migration applies**

```bash
cd mcp-server
python3 -c "
from software_of_you.db import init_db, execute
import os, tempfile
os.environ['XDG_DATA_HOME'] = tempfile.mkdtemp()
init_db()
tables = execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'slack%'\")
print(f'Slack tables: {[t[\"name\"] for t in tables]}')
assert len(tables) == 2, f'Expected 2 Slack tables, got {len(tables)}'
print('PASS')
"
```

- [ ] **Step 3: Commit**

```bash
git add mcp-server/src/software_of_you/migrations/017_slack_module.sql
git commit -m "feat: add Slack migration — slack_messages and slack_channels tables"
```

---

### Task 7: Create Slack Auth

Follows the same pattern as `google_auth.py`: localhost redirect OAuth, token stored as JSON.

**Files:**
- Create: `mcp-server/src/software_of_you/slack_auth.py`

- [ ] **Step 1: Write slack_auth.py**

```python
"""Slack OAuth and token management.

Follows the same pattern as google_auth.py: browser-based OAuth flow,
localhost redirect capture, token stored at ~/.local/share/software-of-you/slack_token.json.

Requires a Slack App with Bot Token scopes:
  channels:history, channels:read, users:read, users:read.email
"""

import http.server
import json
import os
import sys
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from software_of_you.db import DATA_DIR

TOKEN_PATH = DATA_DIR / "slack_token.json"

# These must be set from a Slack App configuration.
# For the CEO deployment, Kerry creates the Slack App and sets these.
SLACK_CLIENT_ID = os.environ.get("SOY_SLACK_CLIENT_ID", "")
SLACK_CLIENT_SECRET = os.environ.get("SOY_SLACK_CLIENT_SECRET", "")

SLACK_SCOPES = "channels:history,channels:read,users:read,users:read.email"
REDIRECT_PORTS = [8093, 8094, 8095, 8096]
SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"


def load_token() -> dict | None:
    """Load stored Slack token."""
    if not TOKEN_PATH.exists():
        return None
    try:
        return json.loads(TOKEN_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_token(token_data: dict) -> None:
    """Save Slack token."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(token_data, indent=2) + "\n")


def get_bot_token() -> str | None:
    """Get the Slack bot token, or None if not connected."""
    data = load_token()
    if data is None:
        return None
    return data.get("access_token")


def is_connected() -> bool:
    """Check if Slack is connected (token exists)."""
    return get_bot_token() is not None


class _OAuthHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler to capture Slack OAuth callback."""

    code: str | None = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        _OAuthHandler.code = params.get("code", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>Slack connected! You can close this tab.</h2>")

    def log_message(self, format, *args):
        pass  # Suppress log output


def run_auth_flow() -> dict:
    """Run the Slack OAuth flow.

    Opens browser, captures redirect, exchanges code for token.
    Returns {"success": True, "team": ..., "scope": ...} or {"error": ...}.
    """
    if not SLACK_CLIENT_ID or not SLACK_CLIENT_SECRET:
        return {
            "error": "Slack app credentials not configured. Set SOY_SLACK_CLIENT_ID and SOY_SLACK_CLIENT_SECRET environment variables."
        }

    # Find available port
    port = None
    for p in REDIRECT_PORTS:
        try:
            server = http.server.HTTPServer(("127.0.0.1", p), _OAuthHandler)
            port = p
            break
        except OSError:
            continue

    if port is None:
        return {"error": f"Could not find available port in {REDIRECT_PORTS}"}

    redirect_uri = f"http://127.0.0.1:{port}"

    # Build auth URL
    params = urllib.parse.urlencode({
        "client_id": SLACK_CLIENT_ID,
        "scope": SLACK_SCOPES,
        "redirect_uri": redirect_uri,
    })
    auth_url = f"{SLACK_AUTH_URL}?{params}"

    print(f"Opening browser for Slack authorization...", file=sys.stderr)
    webbrowser.open(auth_url)

    # Wait for callback
    _OAuthHandler.code = None
    server.handle_request()
    server.server_close()

    if not _OAuthHandler.code:
        return {"error": "No authorization code received."}

    # Exchange code for token
    try:
        data = urllib.parse.urlencode({
            "client_id": SLACK_CLIENT_ID,
            "client_secret": SLACK_CLIENT_SECRET,
            "code": _OAuthHandler.code,
            "redirect_uri": redirect_uri,
        }).encode()

        req = urllib.request.Request(
            SLACK_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())

        if not result.get("ok"):
            return {"error": result.get("error", "Token exchange failed")}

        # Store token
        token_data = {
            "access_token": result.get("access_token"),
            "token_type": result.get("token_type"),
            "scope": result.get("scope"),
            "team_id": result.get("team", {}).get("id"),
            "team_name": result.get("team", {}).get("name"),
            "bot_user_id": result.get("bot_user_id"),
        }
        save_token(token_data)

        return {
            "success": True,
            "team": token_data["team_name"],
            "scope": token_data["scope"],
        }

    except Exception as e:
        return {"error": f"Token exchange failed: {e}"}


def revoke_token() -> bool:
    """Revoke Slack token and remove local file."""
    token = get_bot_token()
    if token:
        try:
            req = urllib.request.Request(
                "https://slack.com/api/auth.revoke",
                headers={"Authorization": f"Bearer {token}"},
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass

    try:
        TOKEN_PATH.unlink()
    except OSError:
        pass
    return True
```

- [ ] **Step 2: Verify import**

```bash
cd mcp-server
python3 -c "from software_of_you.slack_auth import is_connected, load_token; print('PASS')"
```

- [ ] **Step 3: Commit**

```bash
git add mcp-server/src/software_of_you/slack_auth.py
git commit -m "feat: add Slack OAuth module

Browser-based OAuth flow, same pattern as google_auth.py.
Credentials via env vars (SOY_SLACK_CLIENT_ID, SOY_SLACK_CLIENT_SECRET).
Token stored at ~/.local/share/software-of-you/slack_token.json."
```

---

### Task 8: Create Slack Sync

**Files:**
- Create: `mcp-server/src/software_of_you/slack_sync.py`

- [ ] **Step 1: Write slack_sync.py**

```python
"""Slack message sync — pull channel messages into SQLite.

Uses Slack Web API via stdlib urllib. Same pattern as google_sync.py.
Syncs only monitored channels (no DMs by default).
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from software_of_you.db import execute, execute_many, execute_write, rows_to_dicts
from software_of_you.slack_auth import get_bot_token


SLACK_API = "https://slack.com/api"


def _api_get(method: str, token: str, params: dict | None = None) -> dict:
    """Call a Slack API method (GET)."""
    url = f"{SLACK_API}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _match_contact(sender_name: str, sender_email: str | None) -> int | None:
    """Try to match a Slack user to a contact. Returns contact_id or None."""
    # Try email match first (most reliable)
    if sender_email:
        rows = execute("SELECT id FROM contacts WHERE email = ?", (sender_email,))
        if rows:
            return rows[0]["id"]

    # Fuzzy name match
    if sender_name:
        pattern = f"%{sender_name}%"
        rows = execute(
            "SELECT id FROM contacts WHERE name LIKE ? LIMIT 1", (pattern,)
        )
        if rows:
            return rows[0]["id"]

    return None


def sync_channels(token: str | None = None) -> dict:
    """Sync channel list from Slack."""
    token = token or get_bot_token()
    if not token:
        return {"error": "Not connected to Slack."}

    try:
        result = _api_get("conversations.list", token, {
            "types": "public_channel,private_channel",
            "exclude_archived": "true",
            "limit": "200",
        })

        if not result.get("ok"):
            return {"error": result.get("error", "API call failed")}

        channels = result.get("channels", [])
        statements = []
        for ch in channels:
            statements.append((
                """INSERT INTO slack_channels (slack_channel_id, name, is_dm, is_monitored)
                   VALUES (?, ?, 0, 1)
                   ON CONFLICT(slack_channel_id) DO UPDATE SET name = excluded.name""",
                (ch["id"], ch.get("name", "")),
            ))

        if statements:
            execute_many(statements)

        return {"synced": len(channels)}

    except urllib.error.URLError as e:
        return {"error": str(e)}


def sync_messages(token: str | None = None, days: int = 7) -> dict:
    """Sync recent messages from monitored Slack channels."""
    token = token or get_bot_token()
    if not token:
        return {"error": "Not connected to Slack."}

    # Get monitored channels
    channels = execute(
        "SELECT slack_channel_id, name FROM slack_channels WHERE is_monitored = 1"
    )
    if not channels:
        # First sync — get channel list first
        sync_channels(token)
        channels = execute(
            "SELECT slack_channel_id, name FROM slack_channels WHERE is_monitored = 1"
        )

    # Build user cache for contact matching
    user_cache = {}
    try:
        users_result = _api_get("users.list", token, {"limit": "200"})
        if users_result.get("ok"):
            for u in users_result.get("members", []):
                user_cache[u["id"]] = {
                    "name": u.get("real_name", u.get("name", "")),
                    "email": u.get("profile", {}).get("email"),
                }
    except Exception:
        pass  # User list is nice-to-have, not critical

    synced = 0
    oldest = (datetime.now() - timedelta(days=days)).timestamp()

    for channel in rows_to_dicts(channels):
        ch_id = channel["slack_channel_id"]
        ch_name = channel["name"]

        try:
            result = _api_get("conversations.history", token, {
                "channel": ch_id,
                "oldest": str(oldest),
                "limit": "100",
            })

            if not result.get("ok"):
                continue

            statements = []
            for msg in result.get("messages", []):
                msg_ts = msg.get("ts", "")
                if not msg_ts:
                    continue

                # Skip bot messages and system messages
                if msg.get("subtype") in ("bot_message", "channel_join", "channel_leave"):
                    continue

                sender_id = msg.get("user", "")
                user_info = user_cache.get(sender_id, {})
                sender_name = user_info.get("name", "")
                sender_email = user_info.get("email")

                contact_id = _match_contact(sender_name, sender_email)

                received_at = datetime.fromtimestamp(float(msg_ts)).isoformat()
                thread_ts = msg.get("thread_ts") if msg.get("thread_ts") != msg_ts else None
                is_parent = 1 if msg.get("reply_count", 0) > 0 else 0

                # Composite ID: channel_id + ts (ts is only unique per-channel)
                composite_id = f"{ch_id}_{msg_ts}"

                statements.append((
                    """INSERT OR IGNORE INTO slack_messages
                       (slack_message_id, channel_id, channel_name, sender_id,
                        sender_name, content, thread_ts, is_thread_parent,
                        contact_id, received_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (composite_id, ch_id, ch_name, sender_id, sender_name,
                     msg.get("text", ""), thread_ts, is_parent,
                     contact_id, received_at),
                ))
                synced += 1

            if statements:
                execute_many(statements)

            # Update channel sync time
            execute_write(
                "UPDATE slack_channels SET last_synced_at = datetime('now') WHERE slack_channel_id = ?",
                (ch_id,),
            )

        except Exception as e:
            print(f"Slack sync error for #{ch_name}: {e}", file=sys.stderr)
            continue

    # Update global sync timestamp
    execute_many([(
        "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('slack_last_synced', datetime('now'), datetime('now'))",
        (),
    )])

    return {"synced": synced, "channels_checked": len(channels)}


def sync_slack(token: str | None = None) -> dict:
    """Full Slack sync: channels + messages."""
    token = token or get_bot_token()
    if not token:
        return {"error": "Not connected to Slack."}

    ch_result = sync_channels(token)
    msg_result = sync_messages(token)

    return {
        "channels": ch_result,
        "messages": msg_result,
    }
```

- [ ] **Step 2: Verify import**

```bash
cd mcp-server
python3 -c "from software_of_you.slack_sync import sync_slack; print('PASS')"
```

- [ ] **Step 3: Commit**

```bash
git add mcp-server/src/software_of_you/slack_sync.py
git commit -m "feat: add Slack message sync

Syncs monitored channels via Slack Web API. Auto-links messages
to contacts by email then fuzzy name match. Dedup via INSERT OR IGNORE.
Same urllib pattern as Google sync — no new dependencies."
```

---

### Task 9: Create Slack Tool

**Files:**
- Create: `mcp-server/src/software_of_you/tools/slack_tool.py`

- [ ] **Step 1: Write slack_tool.py**

```python
"""Slack tool — search and browse synced Slack messages."""

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, rows_to_dicts


def register(server: FastMCP) -> None:

    @server.tool()
    def slack(
        action: str,
        query: str = "",
        channel: str = "",
        contact_id: int = 0,
        thread_ts: str = "",
        days: int = 7,
    ) -> dict:
        """Search and browse Slack messages.

        Actions:
          search   — Full-text search across synced messages (query required)
          recent   — Recent messages in a channel or from a contact
          thread   — Get a full Slack thread (thread_ts required)
          channels — List monitored channels

        Args:
            action: search, recent, thread, or channels
            query: Search term for 'search' action
            channel: Channel name or ID for 'recent' action
            contact_id: Filter by linked contact for 'recent' action
            thread_ts: Slack thread timestamp for 'thread' action
            days: Look-back window in days for search/recent
        """
        if action == "search":
            return _search(query, days)
        elif action == "recent":
            return _recent(channel, contact_id, days)
        elif action == "thread":
            return _thread(thread_ts)
        elif action == "channels":
            return _channels()
        else:
            return {"error": f"Unknown action: {action}. Use: search, recent, thread, channels"}

    @server.tool()
    def slack_setup() -> dict:
        """Connect or check Slack integration status.

        If not connected, initiates the Slack OAuth flow.
        If connected, returns status and team info.
        """
        from software_of_you.slack_auth import is_connected, load_token, run_auth_flow

        if is_connected():
            token_data = load_token()
            return {
                "result": {
                    "connected": True,
                    "team": token_data.get("team_name", ""),
                },
                "_context": {
                    "presentation": "Slack is already connected.",
                    "suggestions": ["Search Slack messages", "Check recent channel activity"],
                },
            }

        result = run_auth_flow()
        if result.get("success"):
            # Trigger initial sync
            from software_of_you.slack_sync import sync_slack
            sync_result = sync_slack()
            return {
                "result": {
                    "connected": True,
                    "team": result.get("team", ""),
                    "sync": sync_result,
                },
                "_context": {
                    "presentation": f"Slack connected to {result.get('team')}! Initial sync complete.",
                },
            }
        else:
            return {"error": result.get("error", "Slack setup failed")}


def _search(query: str, days: int) -> dict:
    if not query:
        return {"error": "Query is required for search."}

    pattern = f"%{query}%"
    rows = execute(
        """SELECT sm.*, c.name as contact_name FROM slack_messages sm
           LEFT JOIN contacts c ON sm.contact_id = c.id
           WHERE sm.content LIKE ?
             AND sm.received_at > datetime('now', ?)
           ORDER BY sm.received_at DESC LIMIT 20""",
        (pattern, f"-{days} days"),
    )
    results = rows_to_dicts(rows) if rows else []
    return {
        "result": results,
        "count": len(results),
        "_context": {
            "presentation": "Show matching messages with channel, sender, and timestamp. Group by channel if multiple.",
        },
    }


def _recent(channel: str, contact_id: int, days: int) -> dict:
    if channel:
        rows = execute(
            """SELECT sm.*, c.name as contact_name FROM slack_messages sm
               LEFT JOIN contacts c ON sm.contact_id = c.id
               WHERE (sm.channel_name = ? OR sm.channel_id = ?)
                 AND sm.received_at > datetime('now', ?)
               ORDER BY sm.received_at DESC LIMIT 30""",
            (channel, channel, f"-{days} days"),
        )
    elif contact_id:
        rows = execute(
            """SELECT sm.*, c.name as contact_name FROM slack_messages sm
               LEFT JOIN contacts c ON sm.contact_id = c.id
               WHERE sm.contact_id = ?
                 AND sm.received_at > datetime('now', ?)
               ORDER BY sm.received_at DESC LIMIT 30""",
            (contact_id, f"-{days} days"),
        )
    else:
        return {"error": "Provide a channel name or contact_id for recent messages."}

    results = rows_to_dicts(rows) if rows else []
    return {
        "result": results,
        "count": len(results),
        "_context": {
            "presentation": "Show messages chronologically. Include sender and timestamp.",
        },
    }


def _thread(thread_ts: str) -> dict:
    if not thread_ts:
        return {"error": "thread_ts is required to view a thread."}

    rows = execute(
        """SELECT sm.*, c.name as contact_name FROM slack_messages sm
           LEFT JOIN contacts c ON sm.contact_id = c.id
           WHERE sm.thread_ts = ? OR sm.slack_message_id = ?
           ORDER BY sm.received_at ASC""",
        (thread_ts, thread_ts),
    )
    results = rows_to_dicts(rows) if rows else []
    return {
        "result": results,
        "count": len(results),
        "_context": {
            "presentation": "Show the full thread in order. Distinguish the parent message from replies.",
        },
    }


def _channels() -> dict:
    rows = execute(
        "SELECT slack_channel_id, name, is_monitored, last_synced_at FROM slack_channels ORDER BY name"
    )
    channels = rows_to_dicts(rows) if rows else []
    return {
        "result": channels,
        "count": len(channels),
        "_context": {
            "presentation": "List channels. Indicate which are monitored. Offer to toggle monitoring.",
        },
    }
```

- [ ] **Step 2: Register in server.py**

Add to `create_server()` in `server.py`:

```python
from software_of_you.tools.slack_tool import register as register_slack
# ... (after other register calls)
register_slack(server)
```

- [ ] **Step 3: Verify total tool count**

```bash
cd mcp-server
python3 -c "
from software_of_you.server import create_server
server = create_server()
tools = list(server._tool_manager._tools.keys())
print(f'Total tools: {len(tools)}')
for t in sorted(tools): print(f'  {t}')
# Expected: 13 data + 5 intelligence + 2 slack (slack + slack_setup) = 20
"
```

- [ ] **Step 4: Commit**

```bash
git add mcp-server/src/software_of_you/tools/slack_tool.py mcp-server/src/software_of_you/server.py
git commit -m "feat: add Slack tool — search, recent, thread, channels + setup

Two tools: slack (query messages) and slack_setup (OAuth flow).
Total server tools: 20."
```

---

## Chunk 4: Computed Views Update & System Prompt

### Task 10: Update Computed Views for Slack

The `v_contact_health` view needs to include Slack messages in `last_activity` and `days_silent` calculations.

**Files:**
- Create: `mcp-server/src/software_of_you/migrations/018_slack_views.sql`
- Reference: `data/migrations/014_computed_views.sql` for current view definition

- [ ] **Step 1: Read the current v_contact_health view definition**

Check `data/migrations/014_computed_views.sql` for the exact SQL of `v_contact_health`. The migration needs to `DROP VIEW IF EXISTS v_contact_health` and recreate it with a UNION that includes `slack_messages`.

- [ ] **Step 2: Write migration 018**

Create `mcp-server/src/software_of_you/migrations/018_slack_views.sql` that:
1. Drops and recreates `v_contact_health` with Slack messages included in the `last_activity` calculation
2. Drops and recreates `v_nudge_items` to include Slack activity in the silence calculation

The key change: wherever the view calculates `MAX(last_email, last_interaction, last_transcript)` for `last_activity`, add `MAX(..., last_slack_message)` from:
```sql
(SELECT MAX(received_at) FROM slack_messages WHERE contact_id = c.id) as last_slack
```

- [ ] **Step 3: Test migration**

```bash
cd mcp-server
python3 -c "
from software_of_you.db import init_db, execute
import os, tempfile
os.environ['XDG_DATA_HOME'] = tempfile.mkdtemp()
init_db()
# Check that the view exists and has the right columns
cols = execute('PRAGMA table_info(v_contact_health)')
col_names = [c['name'] for c in cols]
print(f'v_contact_health columns: {col_names}')
print('PASS')
"
```

- [ ] **Step 4: Commit**

```bash
git add mcp-server/src/software_of_you/migrations/018_slack_views.sql
git commit -m "feat: update computed views to include Slack in activity calculations

v_contact_health.last_activity and days_silent now factor in
slack_messages. A contact with active Slack threads won't
appear silent."
```

---

### Task 11: Rewrite CEO System Prompt

**Files:**
- Modify: `mcp-server/src/software_of_you/server.py` (lines 9-66, `SERVER_INSTRUCTIONS`)

- [ ] **Step 1: Replace SERVER_INSTRUCTIONS**

Replace the entire `SERVER_INSTRUCTIONS` string (lines 9-66) with the CEO-tuned version from the spec. Keep the existing core behavior (data integrity, cross-referencing) and add the executive context, behavioral patterns, and privacy rules.

The new prompt should include:
- Core behavior (kept): Be the interface, cross-reference everything, never fabricate, human-readable dates
- Tool response format (kept): `_context` field guidance
- Executive context (new): Lead with what matters, proactive surfacing, synthesize across sources, brevity by default
- Morning briefing pattern (new): Calendar + overdue commitments + cold relationships + messages needing response
- Meeting prep pattern (new): Attendees + relationship context + commitments + threads + talking points
- Weekly review pattern (new): Meetings + commitments + relationships + decisions + next week
- First-run onboarding (updated): Add Slack setup step after Google
- Privacy rules (new): No cross-boundary sharing, Slack is work-context only

- [ ] **Step 2: Verify server boots with new instructions**

```bash
cd mcp-server
python3 -c "
from software_of_you.server import create_server
server = create_server()
print(f'Instructions length: {len(server._instructions)} chars')
assert 'Executive Context' in server._instructions or 'executive' in server._instructions.lower()
print('PASS: CEO prompt loaded')
"
```

- [ ] **Step 3: Commit**

```bash
git add mcp-server/src/software_of_you/server.py
git commit -m "feat: rewrite system prompt for CEO executive assistant persona

Morning briefings, meeting prep, weekly reviews. Proactive
surfacing, brevity by default, privacy rules for Slack data."
```

---

## Chunk 5: Install Script & Verification

### Task 12: Update CLI for License-Free Setup

The current `cmd_setup()` requires a license key. For the CEO deployment, we need a way to skip licensing. The simplest: `TEST-CEO` key already works (test key bypass exists in `license.py`).

**Files:**
- Modify: `mcp-server/src/software_of_you/cli.py`

- [ ] **Step 1: Add --no-license flag to setup**

In `cmd_setup()`, add support for `--no-license` that auto-activates with a test key:

```python
# After key parsing (around line 77), add:
no_license = "--no-license" in sys.argv[2:]
if no_license:
    key = "TEST-PERSONAL"
```

- [ ] **Step 2: Add a `migrate` command**

Add to `COMMANDS` dict:

```python
def cmd_migrate() -> int:
    """Run database migrations only (no license, no config)."""
    init_db()
    print(f"Database ready at {DB_PATH}")
    modules = get_installed_modules()
    print(f"Modules: {len(modules)} ({', '.join(modules)})")
    return 0
```

Update COMMANDS:
```python
COMMANDS = {
    "setup": cmd_setup,
    "serve": cmd_serve,
    "status": cmd_status,
    "uninstall": cmd_uninstall,
    "migrate": cmd_migrate,
}
```

- [ ] **Step 3: Commit**

```bash
git add mcp-server/src/software_of_you/cli.py
git commit -m "feat: add --no-license flag and migrate command to CLI

--no-license auto-activates with test key for personal deployments.
migrate command runs DB setup without license or config changes."
```

---

### Task 13: Create install.sh

**Files:**
- Create: `mcp-server/install.sh`

- [ ] **Step 1: Write install.sh**

```bash
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x mcp-server/install.sh
```

- [ ] **Step 3: Commit**

```bash
git add mcp-server/install.sh
git commit -m "feat: add install.sh for one-command setup

Checks Python 3.10+, pip installs, runs setup with --no-license,
configures Claude Desktop. Ready for CEO deployment."
```

---

### Task 14: End-to-End Verification

- [ ] **Step 1: Verify the full server boots with all 20 tools**

```bash
cd mcp-server
python3 -c "
from software_of_you.server import create_server
server = create_server()
tools = sorted(server._tool_manager._tools.keys())
print(f'Total tools: {len(tools)}')
print()
for t in tools:
    print(f'  {t}')
print()
assert len(tools) >= 19, f'Expected 19+ tools, got {len(tools)}'
print('PASS: All tools registered')
"
```

- [ ] **Step 2: Verify migrations create all tables and views**

```bash
cd mcp-server
python3 -c "
from software_of_you.db import init_db, execute
import os, tempfile
os.environ['XDG_DATA_HOME'] = tempfile.mkdtemp()
init_db()

tables = execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\")
views = execute(\"SELECT name FROM sqlite_master WHERE type='view' ORDER BY name\")

print('Tables:')
for t in tables: print(f'  {t[\"name\"]}')
print(f'Total: {len(tables)}')
print()
print('Views:')
for v in views: print(f'  {v[\"name\"]}')
print(f'Total: {len(views)}')
print()

# Check critical items
table_names = [t['name'] for t in tables]
view_names = [v['name'] for v in views]
assert 'slack_messages' in table_names, 'Missing slack_messages table'
assert 'slack_channels' in table_names, 'Missing slack_channels table'
assert 'v_contact_health' in view_names, 'Missing v_contact_health view'
assert 'v_nudge_items' in view_names, 'Missing v_nudge_items view'
assert 'v_meeting_prep' in view_names, 'Missing v_meeting_prep view'
print('PASS: All tables and views present')
"
```

- [ ] **Step 3: Test the MCP server starts on stdio**

```bash
cd mcp-server
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | timeout 5 python3 -m software_of_you serve 2>/dev/null || echo "Server responded (or timed out as expected for stdio)"
```

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: CEO Desktop MCP server — implementation complete

20 tools (13 data + 5 intelligence + 2 slack), 18 migrations,
Slack sync, CEO system prompt, install script. Ready for
Claude Desktop deployment."
```

---

## Execution Notes

**Task dependencies:**
- Tasks 1-2 (foundation) must complete before Tasks 3-5 (intelligence tools need computed views)
- Task 6 (Slack migration) must complete before Tasks 7-9 (Slack auth/sync/tool need tables)
- Task 10 (views update) depends on Task 6 (Slack tables exist)
- Task 11 (system prompt) is independent — can parallel with anything
- Tasks 12-13 (install) are independent — can parallel with Chunks 2-4
- Task 14 (verification) must be last

**Parallelizable groups:**
- Group A: Tasks 1, 2 (foundation)
- Group B: Tasks 3, 4, 5 (intelligence — sequential within group)
- Group C: Tasks 6, 7, 8, 9 (Slack — sequential within group)
- Group D: Task 10 (views update — depends on A + C.6)
- Group E: Task 11 (system prompt — independent)
- Group F: Tasks 12, 13 (install — independent of other groups, but 13 depends on 12)
- Final: Task 14 (verification — depends on all)

After Groups A complete, B+C+E+F can run in parallel. D waits for C.6. Task 14 waits for all.
