# CEO Desktop MCP Server — Design Spec

**Date:** 2026-03-12
**Status:** Approved
**Target:** Claude Desktop via MCP (stdio transport)
**User:** Non-technical CEO managing direct reports and strategic initiatives

---

## Problem

Software of You exists as a Claude Code plugin — powerful but requires a technical user. A CEO client needs the same "second brain" capability (relationship tracking, commitment surfacing, meeting prep) through Claude Desktop, which she already uses for daily work. Claude Desktop extends via MCP servers, not plugins.

## Goal

Ship a self-contained MCP server that:
1. Syncs her Gmail, Google Calendar, Gemini meeting transcripts, and Slack channels into a local SQLite database
2. Provides intelligence tools that surface what matters (nudges, meeting prep, commitments, relationship health)
3. Installs with a single script and requires no technical knowledge to use after setup

## Architecture

```
Claude Desktop
  │ (stdio)
  ▼
software-of-you MCP Server (Python, FastMCP)
  ├── Data Tools (14 existing: contacts, interactions, projects,
  │    email, calendar, transcripts, decisions, journal, notes,
  │    search, overview, profile, system, views)
  ├── Intelligence Tools (5 new: meeting_prep, nudges, commitments,
  │    relationship_pulse, weekly_review)
  ├── Slack Tool (1 new: search, recent, thread, channels)
  ├── Sync Layer (Google: existing | Slack: new)
  └── SQLite DB (~/.local/share/software-of-you/soy.db)
```

The MCP server is a standalone Python package in `mcp-server/`. It shares the same SQLite database and migration system as the Claude Code plugin but has no dependency on plugin infrastructure (no commands, agents, skills, or hooks).

### What carries over from the existing MCP server

- All 14 tool modules in `tools/`
- `db.py` — connection management, migrations, backups, data loss detection
- `google_auth.py` — OAuth2 flow, multi-account token management
- `google_sync.py` — Gmail, Calendar, and Gemini transcript sync
- All 16 migrations (including computed SQL views in 014)
  - **Pre-implementation fix:** migrations 011-014 are missing from `mcp-server/migrations/`. These must be copied from `data/migrations/` before building. The intelligence tools depend on the computed views in 014.
- `SERVER_INSTRUCTIONS` in `server.py` (will be rewritten)

### What gets built

| Component | File(s) | Lines (est.) | Description |
|-----------|---------|-------------|-------------|
| Intelligence tools | `tools/intelligence.py` | ~200 | 5 tools wrapping computed SQL views |
| Slack sync | `slack_sync.py` | ~200 | Channel message sync via Slack API |
| Slack auth | `slack_auth.py` | ~100 | OAuth2 flow for Slack workspace |
| Slack tool | `tools/slack_tool.py` | ~100 | Search, recent, thread, channels |
| Slack migration | `migrations/017_slack_module.sql` | ~30 | `slack_messages` + `slack_channels` tables |
| CEO system prompt | `server.py` (update) | ~80 | Executive-tuned instructions |
| Computed views update | `migrations/018_slack_views.sql` | ~30 | Add Slack to `v_contact_health` last_activity |
| Install script | `install.sh` | ~120 | One-command setup + Claude Desktop config (macOS/Linux) |
| Missing migrations | Copy 011-014 from `data/migrations/` | 0 | Pre-implementation file copy |

### What gets dropped (Claude Code only)

- 51 slash commands (`commands/`)
- 4 agents (`agents/`)
- 5 skills (`skills/`)
- SessionStart hook (`hooks/`)
- `.claude-plugin/` manifest
- `tools/views.py` — **drop for v1**. HTML view generation has no use in Claude Desktop. If needed later, re-add. Tool count becomes 13 existing + 5 intelligence + 1 Slack = 19 total.

---

## Intelligence Tools

Five new tools in `tools/intelligence.py`. Each queries pre-computed SQL views and returns structured results with `_context` presentation guidance.

### `meeting_prep`

**Trigger:** "Prep me for my 2pm" / "What do I need to know before my meeting with X?"

**Parameters:**
- `event_id: int = 0` — specific event (Claude resolves "my 2pm" to an ID by calling `calendar` tool first, or passes 0)
- `hours_ahead: int = 4` — look-ahead window when event_id is 0: finds next upcoming event within this window
- `contact_name: str = ""` — alternative lookup: find next event with this attendee

**Resolution logic:** When `event_id=0` and no `contact_name`, find the soonest event within `hours_ahead`. When `contact_name` is given, find the next event whose attendees JSON contains a matching name. Claude handles the natural language → parameter mapping.

**Returns:**
- Event details (title, time, location, attendees)
- Per-attendee brief: relationship health from `v_contact_health`, open commitments from `v_commitment_status`, recent email/Slack threads, last meeting topics
- Suggested talking points

**Data sources:** `v_meeting_prep`, `v_contact_health`, `v_commitment_status`, `emails`, `slack_messages`, `transcripts`

### `nudges`

**Trigger:** "What should I be on top of?" / morning briefing

**Parameters:**
- `tier: str = "all"` — filter: urgent, soon, awareness, or all
- `limit: int = 20`

**Returns:**
- Nudge items ranked by urgency tier from `v_nudge_items`
- Summary counts per tier from `v_nudge_summary`
- Categories: overdue follow-ups, stale relationships, missed commitments, upcoming deadlines
- **Threshold note:** `v_nudge_items` uses 30 days for `cold_contact` nudge type (awareness tier). This is intentional — nudges are a broader safety net. `relationship_pulse` uses a tighter `threshold_days` default of 14 for "cooling" detection. These serve different purposes.

**Data sources:** `v_nudge_items`, `v_nudge_summary`

### `commitments`

**Trigger:** "What did I promise this week?" / "What's overdue?"

**Parameters:**
- `status: str = "open"` — open, overdue, completed, all
- `contact_id: int = 0` — filter by person
- `days: int = 14` — look-back window for recent commitments

**Returns:**
- Commitments with owner name, source transcript, deadline, days overdue, urgency tier
- Grouped by person when no filter

**Data sources:** `v_commitment_status`

### `relationship_pulse`

**Trigger:** "How's my relationship with Sarah?" / "Who am I losing touch with?"

**Parameters:**
- `contact_id: int = 0` — specific contact for deep dive
- `threshold_days: int = 14` — days silent to flag as cooling

**Returns:**
- Single contact: full health profile (days silent, email/interaction counts, depth score, trajectory, open commitments, next meeting)
- No contact: list of relationships ranked by staleness

**Data sources:** `v_contact_health`, `emails`, `slack_messages`, `transcripts`

**Implementation note:** `v_contact_health` currently calculates `days_silent` and `last_activity` from emails, interactions, and transcripts only. After Slack integration, update `014_computed_views.sql` (or add a new migration `018_slack_views.sql`) to incorporate `slack_messages` into the `last_activity` and `days_silent` calculations via a UNION in the view definition. Without this, a contact with active Slack threads would still appear "silent."

### `weekly_review`

**Trigger:** "Give me my weekly review" / Friday conversations

**Parameters:**
- `week_offset: int = 0` — 0 = current week, -1 = last week

**Week boundaries:** Monday 00:00 through Sunday 23:59 (ISO week). `week_offset=0` is the current ISO week; `-1` is last week.

**Returns:**
- Meetings held with key attendees (from `calendar_events` in the date range)
- Commitments made vs. completed (from `v_commitment_status`, filtered by `created_at` / `completed_at` in range)
- Relationships that warmed or cooled (compare `days_silent` from `v_contact_health` — contacts with new activity this week = warming; contacts with `last_activity` before the week window who were active the prior week = cooling)
- Decisions made or deferred (from `decisions` where `decided_at` in range)
- Next week preview (next 7 days of `calendar_events` + pending commitments with deadlines in range)

**Data sources:** `v_contact_health`, `v_commitment_status`, `calendar_events`, `decisions`, `activity_log`

---

## Slack Integration

### Schema: `017_slack_module.sql`

```sql
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
```

### Sync: `slack_sync.py`

- Uses Slack Web API via stdlib `urllib` (same pattern as Google sync)
- Auth: Bot token stored at `~/.local/share/software-of-you/slack_token.json`
- Syncs `conversations.list` → `slack_channels` (channels only, no DMs by default)
- Syncs `conversations.history` for monitored channels → `slack_messages`
- Auto-links to contacts: first try Slack profile email vs `contacts.email` (requires `users:read.email` scope — works on Business+ plans). Fallback: fuzzy match `sender_name` against `contacts.name`. Unmatched senders stay `contact_id = NULL` and can be manually linked later via the `contacts` tool.
- Dedup via `INSERT OR IGNORE` on `slack_message_id`
- Freshness: `soy_meta` key `slack_last_synced`, threshold 15 minutes

### Auth: `slack_auth.py`

- Slack App with Bot Token scopes: `channels:history`, `channels:read`, `users:read`, `users:read.email`
- OAuth2 flow: open browser → user approves → redirect to localhost → capture token
- Token stored at `~/.local/share/software-of-you/slack_token.json`

### Tool: `tools/slack_tool.py`

```python
@server.tool()
def slack(
    action: str,        # search, recent, thread, channels
    query: str = "",    # search: search term
    channel: str = "",  # recent: channel name or slack_channel_id
    contact_id: int = 0,# recent: filter by linked contact
    thread_ts: str = "",# thread: Slack thread timestamp
    days: int = 7,      # search/recent: look-back window
) -> dict:
    """Search and browse Slack messages.

    Actions:
      search   — Full-text search across synced messages (query required)
      recent   — Recent messages in a channel or from a contact (channel or contact_id required)
      thread   — Get a full thread (thread_ts required)
      channels — List monitored channels (no params needed)
    """
```

### Privacy

- Channels only by default (no DMs)
- `is_monitored` flag per channel — user controls which channels sync
- DMs can be enabled per-channel if explicitly requested
- System prompt instructs Claude not to make personal inferences from message patterns

---

## System Prompt (CEO Persona)

The `SERVER_INSTRUCTIONS` in `server.py` gets rewritten to include:

### Core Behavior (kept from existing)
- Be the interface — users talk naturally, you call tools
- Cross-reference everything — connections are the value
- Never fabricate data — NULL over fiction
- Human-readable dates

### Executive Context (new)
- Lead with what matters, don't bury the headline
- Proactive surfacing — don't wait to be asked
- Synthesize across data sources (email + Slack + meetings + commitments)
- Brevity by default, expand only when asked

### Behavioral Patterns (new)
- **Morning briefing:** Today's calendar + overdue commitments + cold relationships + messages needing response
- **Meeting prep:** Attendees + relationship context + open commitments + recent threads + talking points
- **Weekly review:** Meetings held + commitments made/completed + relationships warming/cooling + decisions + next week preview

### Privacy Rules (new)
- Never share data across organizational boundaries without context
- Slack data is work-context only
- When uncertain, say so rather than guess

---

## Auto-Sync Behavior

All intelligence tools check data freshness before responding:

| Service | Freshness key | Threshold | Triggered by |
|---------|--------------|-----------|-------------|
| Gmail | `gmail_last_synced` | 15 min | `meeting_prep`, `nudges`, `relationship_pulse`, `weekly_review`, `get_overview` |
| Calendar | `calendar_last_synced` | 15 min | `meeting_prep`, `weekly_review`, `get_overview` |
| Transcripts | `transcripts_last_scanned` | 60 min | `meeting_prep`, `commitments`, `weekly_review` |
| Slack | `slack_last_synced` | 15 min | `meeting_prep`, `nudges`, `relationship_pulse`, `weekly_review`, `slack` tool |

Sync failures are silent — the tool proceeds with cached data. The `_context` field notes when data may be stale (e.g., "Gmail sync failed — showing cached data from 2 hours ago").

## Error Handling

All intelligence tools follow this pattern for edge cases:

- **Empty DB (zero contacts):** Return `_context` with onboarding prompt ("No contacts yet. Try 'Add a contact named ...' to get started.")
- **Auth expired (Google/Slack):** Return data from cache + `_context.auth_warning` prompting re-auth. Never block the response.
- **Computed view returns zero rows:** Return empty result + `_context.empty_state` with a contextual message ("No overdue commitments — you're all caught up." / "No upcoming meetings in the next 4 hours.")
- **Sync failure:** Log to stderr, continue with stale data, note in `_context`.

---

## Installation

### `install.sh`

1. Verify Python 3.10+
2. `pip install -e .` (or from PyPI later)
3. Run `python3 -m software_of_you migrate` (creates DB, runs all migrations)
4. Detect Claude Desktop config location:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Linux: `~/.config/Claude/claude_desktop_config.json`
   - If config file doesn't exist, create it with just the MCP server entry
5. Inject MCP server config (parse existing JSON, merge `mcpServers`, don't overwrite other servers)
6. Print restart instructions

### Claude Desktop Config

```json
{
  "mcpServers": {
    "software-of-you": {
      "command": "python3",
      "args": ["-m", "software_of_you"]
    }
  }
}
```

### First-Run Onboarding (in Claude Desktop)

1. Server boots, `system_status` detects zero contacts + no Google/Slack
2. Greeting + "Let's get connected"
3. Google OAuth (browser opens, user approves, localhost redirect captures token automatically)
4. Slack OAuth (same browser-based flow)
5. First sync runs automatically
6. "I found N contacts from your email. Here's what needs your attention today."

---

## Dependencies

```toml
[project]
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.2.0",
    "jinja2>=3.1",
]
```

No new dependencies. Slack API uses stdlib `urllib` (same as Google sync).

---

## Out of Scope (v1)

- `.mcpb` Desktop Extension packaging (queued for follow-up experiment)
- DM sync (privacy — opt-in later)
- Slack message sending (read-only for v1)
- HTML view generation in Claude Desktop
- Windows support
- Multi-user / server-hosted deployment

---

## Follow-Up: `.mcpb` Packaging

After v1 works end-to-end in Claude Desktop, package as a Desktop Extension:
- Bundle Python + dependencies into `.mcpb` archive
- One-click install from Claude Desktop's extension browser
- Spec at github.com/anthropics/mcpb (v0.1)
