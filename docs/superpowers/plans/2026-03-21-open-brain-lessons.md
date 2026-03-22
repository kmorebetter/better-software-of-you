# Open Brain Lessons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 5 features adapted from OB1's actionability model: Quick Capture Inbox, Cross-Module Synthesis, Proactive Surfacing Loop, FTS5 Search, and Semantic Search (sqlite-vec).

**Architecture:** Each feature adds a migration + command (+ optional MCP tool). Features 1-4a are zero-dependency. Feature 4b is opt-in with sqlite-vec. All features read from SoY's pre-computed views and write to the shared SQLite database.

**Tech Stack:** SQLite, Python (FastMCP), Bash, Markdown commands

**Spec:** `~/Desktop/soy-openbrain-lessons-spec.md`

**Key codebase patterns to follow:**
- Migrations: `data/migrations/NNN_name.sql` — idempotent, `CREATE TABLE IF NOT EXISTS`, `INSERT OR IGNORE` for module registration
- MCP tools: `mcp-server/src/software_of_you/tools/foo_tool.py` — `register(server: FastMCP)` function, `@server.tool()` decorator, action-dispatch pattern, uses `execute`/`execute_write`/`execute_many`/`rows_to_dicts` from `software_of_you.db`
- Commands: `commands/foo.md` — YAML frontmatter (`description`, `allowed-tools`), workflow steps, SQL via `sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db"`
- Module manifests: `modules/name/manifest.json` — see `modules/notes/manifest.json` for the format
- Views: `v_nudge_items` is rebuilt in each migration that extends it — `DROP VIEW IF EXISTS` + full recreate with all UNION ALLs

**Last existing migration:** `019_email_opportunities.sql`

---

## File Map

### New files (11)

| File | Responsibility |
|------|---------------|
| `data/migrations/020_inbox_module.sql` | Inbox table, module registration, v_nudge_items rebuild with inbox UNION ALL |
| `modules/inbox/manifest.json` | Inbox module manifest |
| `mcp-server/src/software_of_you/tools/inbox_tool.py` | MCP tool for capture/list/route/dismiss/count |
| `commands/capture.md` | `/capture` slash command |
| `commands/inbox.md` | `/inbox` slash command |
| `data/migrations/021_proactive.sql` | Proactive briefings dedup table |
| `commands/proactive.md` | `/proactive` slash command (designed for `/loop`) |
| `data/migrations/022_fts5_search.sql` | FTS5 virtual table + triggers for auto-indexing |
| `data/migrations/023_semantic_search.sql` | Embeddings metadata table (vec table created at setup time) |
| `mcp-server/src/software_of_you/tools/semantic_search_tool.py` | MCP tool for semantic search with fallback |
| `commands/embed.md` | `/embed` slash command (setup/run/status) |

### Modified files (4)

| File | Change |
|------|--------|
| `mcp-server/src/software_of_you/server.py` | Register `inbox_tool` and `semantic_search_tool` |
| `mcp-server/src/software_of_you/tools/search_tool.py` | Add FTS5 path + semantic search hybrid mode |
| `mcp-server/pyproject.toml` | Add `[project.optional-dependencies] embeddings` |
| `commands/weekly-review.md` | Add Step 4b: Cross-Module Synthesis section + HTML |

---

## Task 1: Inbox Migration

**Files:**
- Create: `data/migrations/020_inbox_module.sql`

This is the foundation. Creates the inbox table, registers the module, and rebuilds `v_nudge_items` + `v_nudge_summary` with the inbox UNION ALL.

- [ ] **Step 1: Create the migration file**

```sql
-- Quick Capture Inbox
-- Capture thoughts fast, route them later.

-- ═══════════════════════════════════════════════════════════════
-- inbox table
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    routed_to TEXT,
    routed_entity_id INTEGER,
    routed_at TEXT,
    tags TEXT DEFAULT '[]',
    matched_contacts TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_inbox_unrouted ON inbox(created_at DESC) WHERE routed_to IS NULL;
CREATE INDEX IF NOT EXISTS idx_inbox_routed ON inbox(routed_to) WHERE routed_to IS NOT NULL;

-- Module registration
INSERT OR IGNORE INTO modules (name, version, description, enabled, created_at)
VALUES ('inbox', '1.0.0', 'Quick capture inbox — write first, route later', 1, datetime('now'));
```

Then rebuild `v_nudge_items` and `v_nudge_summary`. **CRITICAL:** The view must be dropped and fully recreated — you cannot just append a UNION ALL.

```sql
-- ═══════════════════════════════════════════════════════════════
-- v_nudge_items: Rebuild with inbox UNION ALL added
-- IMPORTANT: Dump the current view from the LIVE DATABASE, not from
-- a migration file. Multiple migrations (014, 016, 019) have built
-- this view incrementally. Get the canonical definition with:
--   sqlite3 data/soy.db "SELECT sql FROM sqlite_master WHERE name='v_nudge_items';"
-- Then add the inbox UNION ALL below before the untracked contacts section.
-- ═══════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_nudge_items;
-- CREATE VIEW v_nudge_items AS
-- <paste the FULL current view definition here>
-- ...then before the final untracked_contact UNION ALL, add:
```

The inbox UNION ALL to insert:

```sql
-- Unrouted inbox items (AWARENESS / SOON — never urgent)
UNION ALL
SELECT
    'unrouted_inbox' AS nudge_type,
    i.id AS entity_id,
    CASE
        WHEN julianday('now') - julianday(i.created_at) > 3 THEN 'soon'
        ELSE 'awareness'
    END AS tier,
    substr(i.content, 1, 60) AS entity_name,
    NULL AS contact_id,
    NULL AS project_id,
    'Inbox item captured ' || CAST(ROUND(julianday('now') - julianday(i.created_at)) AS INTEGER) || ' days ago — needs routing' AS description,
    i.created_at AS relevant_date,
    CAST(ROUND(julianday('now') - julianday(i.created_at)) AS INTEGER) AS days_value,
    i.matched_contacts AS extra_context,
    'inbox' AS icon
FROM inbox i
WHERE i.routed_to IS NULL
    AND julianday('now') - julianday(i.created_at) > 1
```

Also rebuild `v_nudge_summary`:

```sql
DROP VIEW IF EXISTS v_nudge_summary;
CREATE VIEW IF NOT EXISTS v_nudge_summary AS
SELECT tier, COUNT(*) AS count FROM v_nudge_items GROUP BY tier;
```

- [ ] **Step 2: Run bootstrap and verify**

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/bootstrap.sh"
```

Expected: `ready|21|11|...` (module count goes from 10 to 11)

- [ ] **Step 3: Verify the table and view**

```bash
sqlite3 data/soy.db "PRAGMA table_info(inbox);"
sqlite3 data/soy.db "SELECT COUNT(*) FROM inbox;"
sqlite3 data/soy.db "SELECT nudge_type FROM v_nudge_items GROUP BY nudge_type;"
```

Expected: `inbox` table exists with 8 columns. Nudge types include existing types (no `unrouted_inbox` yet since the table is empty, but the query shouldn't error).

- [ ] **Step 4: Commit**

```bash
git add data/migrations/020_inbox_module.sql
git commit -m "feat: add inbox table and module registration (migration 020)"
```

---

## Task 2: Inbox Module Manifest

**Files:**
- Create: `modules/inbox/manifest.json`

- [ ] **Step 1: Create the manifest**

```json
{
  "name": "inbox",
  "display_name": "Inbox",
  "version": "1.0.0",
  "description": "Quick capture inbox — write first, route later. Capture thoughts, extract #hashtags, match contact names, and route to the right module when ready.",
  "migration": "020_inbox_module.sql",
  "tables": ["inbox"],
  "entities": ["inbox_item"],
  "commands": ["capture", "inbox"],
  "standalone_features": [
    "Quick capture from natural language",
    "Auto-extract #hashtags as tags",
    "Auto-match contact names from content",
    "Route items to any module when ready",
    "Unrouted items surface in /nudges after 24 hours"
  ],
  "enhancements": [
    {
      "requires_module": "crm",
      "features": ["Auto-detect contact names in captured content", "Route inbox items directly to contact records"],
      "description": "Inbox captures automatically detect and link to contacts mentioned in your text."
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add modules/inbox/manifest.json
git commit -m "feat: add inbox module manifest"
```

---

## Task 3: Inbox MCP Tool

**Files:**
- Create: `mcp-server/src/software_of_you/tools/inbox_tool.py`
- Modify: `mcp-server/src/software_of_you/server.py`

- [ ] **Step 1: Create the inbox tool**

Write `mcp-server/src/software_of_you/tools/inbox_tool.py` following the exact pattern from the spec (the full Python code in the spec's "MCP Tool" section). Key points:
- `register(server: FastMCP)` function
- `@server.tool()` decorator on `inbox()` function
- Actions: `capture`, `list`, `route`, `dismiss`, `count`
- People matching: first-name token match, 3+ chars, parameterized SQL
- `execute_many()` for INSERT + activity_log in one transaction
- `_context` field on capture response for Claude presentation hints

**Edge case handling in `_capture()`:** Truncate content to 10,000 characters if longer, and include `"truncated": true` in the response. Add early in the function:
```python
truncated = False
if len(content) > 10000:
    content = content[:10000]
    truncated = True
```

Reference: The full implementation is in the spec at `~/Desktop/soy-openbrain-lessons-spec.md`, "MCP Tool" section under Feature 1.

- [ ] **Step 2: Register in server.py**

Add to `mcp-server/src/software_of_you/server.py` after the existing tool registrations (after line 106, before the intelligence tools section):

```python
from software_of_you.tools.inbox_tool import register as register_inbox
register_inbox(server)
```

- [ ] **Step 3: Verify the tool loads**

```bash
cd /Users/kerrymorrison/Projects/PersonalProjects/better-software-of-you/mcp-server
python -c "from software_of_you.tools.inbox_tool import register; print('OK')"
```

Expected: `OK` (no import errors)

- [ ] **Step 4: Commit**

```bash
git add mcp-server/src/software_of_you/tools/inbox_tool.py mcp-server/src/software_of_you/server.py
git commit -m "feat: add inbox MCP tool with capture/list/route/dismiss/count actions"
```

---

## Task 4: Capture and Inbox Commands

**Files:**
- Create: `commands/capture.md`
- Create: `commands/inbox.md`

- [ ] **Step 1: Create `/capture` command**

Write `commands/capture.md`:

```yaml
---
description: Quick capture — write it down, route it later
allowed-tools: ["Bash", "Read", "Write"]
---
```

Workflow:
1. Take whatever the user typed after `/capture` as the content
2. Extract #hashtags from content with regex
3. Match contact names against active contacts (first-name match, 3+ chars, case-insensitive)
4. INSERT into inbox table + activity_log in a single `sqlite3` heredoc call
5. Confirm capture. If contacts matched, mention them. If content clearly belongs somewhere, suggest routing.
6. Keep it fast — no view generation, no syncing. Just capture and confirm.

SQL pattern for the command:
```bash
sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" <<'SQL'
INSERT INTO inbox (content, tags, matched_contacts, created_at, updated_at)
VALUES ('<content>', '<tags_json>', '<contacts_json>', datetime('now'), datetime('now'));
INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
VALUES ('inbox', last_insert_rowid(), 'captured', 'Quick capture: <first 80 chars>', datetime('now'));
SQL
```

Note: The command uses Bash/SQL directly. Contact matching happens via a separate SELECT query before the INSERT. The MCP tool does the same thing programmatically for Claude Desktop clients.

- [ ] **Step 2: Create `/inbox` command**

Write `commands/inbox.md`:

```yaml
---
description: Review and route unrouted inbox items
allowed-tools: ["Bash", "Read", "Write"]
---
```

Workflow:
1. Query unrouted items: `SELECT id, content, tags, matched_contacts, created_at FROM inbox WHERE routed_to IS NULL ORDER BY created_at DESC LIMIT 30;`
2. If no items: "Your inbox is clear — nothing to route."
3. For each item, suggest a routing destination based on content analysis
4. Present as a numbered list with suggestions
5. Offer batch routing if 3+ items have the same obvious destination
6. For each routed item: UPDATE inbox SET routed_to/routed_entity_id/routed_at + INSERT activity_log

- [ ] **Step 3: Verify commands are discoverable**

```bash
ls -la commands/capture.md commands/inbox.md
head -5 commands/capture.md commands/inbox.md
```

Expected: Both files exist with correct YAML frontmatter.

- [ ] **Step 4: Commit**

```bash
git add commands/capture.md commands/inbox.md
git commit -m "feat: add /capture and /inbox commands"
```

---

## Task 5: Cross-Module Synthesis in Weekly Review

**Files:**
- Modify: `commands/weekly-review.md`

- [ ] **Step 1: Read the current weekly-review.md fully**

Understand the existing structure:
- Step 0: Auto-sync
- Step 1: Read design system
- Step 2: Check modules & gather data (this week data + looking ahead data)
- Step 3: Generate HTML
- Step 4: Write, register, and open

The synthesis section goes between Step 2 and Step 3 (after data gathering, before HTML generation).

- [ ] **Step 2: Add Step 2b: Cross-Module Synthesis**

Insert after the "Looking Ahead Data" section (after line 218) and before "## Step 3: Generate HTML" (line 220):

````markdown
## Step 2b: Cross-Module Synthesis

After gathering all per-module data, perform a synthesis pass to find connections across entities. This is where the review's unique value comes from — it surfaces things no single module would reveal.

### Synthesis Data

Run these queries to build the cross-reference dataset:

**Contacts with recent activity + linked projects/commitments/meetings:**
```sql
SELECT
    c.id AS contact_id,
    c.name AS contact_name,
    ch.days_silent,
    ch.last_activity,
    ch.open_commitments_theirs,
    ch.open_commitments_yours,
    ch.next_meeting_date,
    ch.active_projects,
    ch.relationship_depth,
    ch.trajectory,
    p.id AS project_id,
    p.name AS project_name,
    ph.completion_pct,
    ph.days_to_target,
    ph.overdue_tasks
FROM contacts c
JOIN v_contact_health ch ON ch.contact_id = c.id
LEFT JOIN projects p ON p.client_id = c.id AND p.status IN ('active', 'on-hold')
LEFT JOIN v_project_health ph ON ph.project_id = p.id
WHERE
    ch.last_activity > datetime('now', '-7 days')
    OR ch.next_meeting_date BETWEEN date('now') AND date('now', '+7 days')
    OR ch.open_commitments_yours > 0
    OR ch.open_commitments_theirs > 0
ORDER BY ch.days_silent ASC;
```

**Journal entries mentioning contact names** (if Journal installed):
```sql
SELECT je.id, je.entry_date, je.content, c.id AS mentioned_contact_id, c.name AS mentioned_contact
FROM journal_entries je
JOIN contacts c ON je.content LIKE '%' || SUBSTR(c.name, 1, INSTR(c.name || ' ', ' ') - 1) || '%'
WHERE je.entry_date > date('now', '-7 days')
  AND c.status = 'active'
  AND LENGTH(SUBSTR(c.name, 1, INSTR(c.name || ' ', ' ') - 1)) >= 3;
```

**Open decisions linked to active projects** (if Decision Log installed):
```sql
SELECT d.id, d.title, d.status, d.project_id, p.name AS project_name
FROM decisions d
JOIN projects p ON d.project_id = p.id
WHERE d.status IN ('open', 'exploring')
  AND p.status = 'active';
```

### Synthesis Patterns

Read the combined result set and look for these specific cross-entity connections. Surface a maximum of 5 connections, prioritized by urgency:

1. **People x Projects** — Contact touched this week + linked project near deadline
2. **Commitments x Calendar** — Open commitment + meeting with that person coming next week
3. **Journal x Contacts** — Journal mentions a person + that contact's health is declining
4. **Decisions x Projects** — Open decision linked to active project with blockers
5. **Cold contacts x Upcoming meetings** — Contact 30+ days silent + meeting next week

If no cross-entity connections found (e.g., user has fewer than 3 contacts), skip this section entirely in the HTML.

### HTML for Connections Section

Add between the "This Week" and "Looking Ahead" columns (or as a full-width section between them):

```html
<section id="connections" class="lg:col-span-5 mb-6 delight-section">
  <div class="flex items-center gap-2 mb-4">
    <h2 class="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Connections</h2>
    <div class="flex-1 h-px bg-zinc-200"></div>
  </div>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
    <!-- Each connection is a card: -->
    <div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-4 delight-card">
      <div class="flex items-center gap-2 mb-2">
        <i data-lucide="ICON1" class="w-4 h-4 text-zinc-400"></i>
        <span class="text-zinc-300">×</span>
        <i data-lucide="ICON2" class="w-4 h-4 text-zinc-400"></i>
      </div>
      <p class="text-sm text-zinc-700 font-medium">Entity A → Entity B</p>
      <p class="text-xs text-zinc-500 mt-1">Why it matters (1 sentence)</p>
      <p class="text-xs text-blue-600 mt-2">Suggested action</p>
    </div>
  </div>
</section>
```
````

- [ ] **Step 3: Verify the command still parses correctly**

```bash
head -5 commands/weekly-review.md
grep -c "^## Step" commands/weekly-review.md
```

Expected: YAML frontmatter intact, step count increases by 1.

- [ ] **Step 4: Commit**

```bash
git add commands/weekly-review.md
git commit -m "feat: add cross-module synthesis section to weekly review"
```

---

## Task 6: Proactive Surfacing Migration

**Files:**
- Create: `data/migrations/021_proactive.sql`

- [ ] **Step 1: Create the migration**

```sql
-- Proactive Surfacing Loop
-- Dedup table to prevent repeated briefings within the same time window.
-- This is a platform feature, not a module — no module registration needed.

CREATE TABLE IF NOT EXISTS proactive_briefings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    briefing_type TEXT NOT NULL,     -- 'morning', 'pre_meeting', 'midday', 'evening'
    briefing_key TEXT NOT NULL,      -- dedup key: local date for daily, google_event_id for pre-meeting
    summary TEXT,                    -- what was surfaced (for review)
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(briefing_type, briefing_key)
);

CREATE INDEX IF NOT EXISTS idx_proactive_created ON proactive_briefings(created_at DESC);
```

- [ ] **Step 2: Run bootstrap and verify**

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/bootstrap.sh"
sqlite3 data/soy.db "PRAGMA table_info(proactive_briefings);"
```

Expected: Table exists with 5 columns.

- [ ] **Step 3: Commit**

```bash
git add data/migrations/021_proactive.sql
git commit -m "feat: add proactive_briefings dedup table (migration 021)"
```

---

## Task 7: Proactive Command

**Files:**
- Create: `commands/proactive.md`

- [ ] **Step 1: Create the command**

Write `commands/proactive.md` with the full time-aware proactive surfacing workflow from the spec. Key implementation details:

```yaml
---
description: Proactive intelligence loop — run via /loop 15m /proactive
allowed-tools: ["Bash", "Read", "Write"]
---
```

The command workflow:

1. **Get current context** — query local hour via `strftime('%H', 'now', 'localtime')`, today's local date, already-sent briefings, and imminent meetings
2. **Route to appropriate briefing** based on time window:
   - Morning (6-9): nudge summary, top urgent items, today's meetings, email queue, unrouted inbox count
   - Pre-meeting (any time, meeting within 30 min): contact health, commitments, relationship context
   - Midday (11-1): only NEW urgent items since morning, inbox count, aging emails
   - Evening (5-7): day's activity summary, remaining urgent items
   - Default: only pre-meeting or new urgent items — otherwise do nothing
3. **Dedup via proactive_briefings** — `INSERT OR IGNORE` with `briefing_type` + `briefing_key` (local date or event ID)
4. **All time comparisons use `'localtime'` modifier**

Important: most invocations should be no-ops. Midday skips output if nothing is new. Default does nothing unless a meeting is imminent.

- [ ] **Step 2: Verify command is discoverable**

```bash
head -5 commands/proactive.md
```

- [ ] **Step 3: Commit**

```bash
git add commands/proactive.md
git commit -m "feat: add /proactive command for time-aware intelligence surfacing"
```

---

## Task 8: FTS5 Search Migration

**Files:**
- Create: `data/migrations/022_fts5_search.sql`

- [ ] **Step 1: Create the migration**

```sql
-- FTS5 Full-Text Search
-- Porter stemmer handles "hiring" → "hire", "scaling" → "scale".
-- Ships with SQLite — zero dependencies.

-- FTS5 virtual table covering all searchable content
CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
    entity_type,
    entity_id UNINDEXED,
    title,
    content,
    tokenize='porter unicode61'
);

-- Populate FTS from existing data (idempotent: DELETE + re-INSERT on each run)
-- This block runs on every bootstrap but is fast for small datasets.

DELETE FROM search_fts;

-- Contacts
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'contact', id, name, COALESCE(company, '') || ' ' || COALESCE(role, '') || ' ' || COALESCE(notes, '')
FROM contacts WHERE status = 'active';

-- Standalone notes
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'note', id, COALESCE(title, ''), content
FROM standalone_notes;

-- Journal entries
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'journal', id, entry_date, content
FROM journal_entries;

-- Decisions
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'decision', id, title, COALESCE(context, '') || ' ' || COALESCE(decision, '')
FROM decisions;

-- Transcripts (summary, not raw_text)
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'transcript', id, COALESCE(title, ''), COALESCE(summary, '')
FROM transcripts;

-- Emails (subject + snippet)
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'email', id, COALESCE(subject, ''), COALESCE(snippet, '')
FROM emails;

-- Inbox items
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'inbox', id, '', content
FROM inbox WHERE routed_to IS NULL OR routed_to != 'dismissed';
```

Note: The `DELETE + re-INSERT` approach is simple and correct for the current data scale (~hundreds of rows). If performance becomes an issue later, switch to incremental INSERT triggers.

- [ ] **Step 2: Run bootstrap and verify**

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/bootstrap.sh"
sqlite3 data/soy.db "SELECT entity_type, COUNT(*) FROM search_fts GROUP BY entity_type;"
```

Expected: Rows from contacts, notes, transcripts, emails, etc.

- [ ] **Step 3: Test a FTS5 query**

```bash
sqlite3 data/soy.db "SELECT entity_type, entity_id, title, snippet(search_fts, 3, '<b>', '</b>', '...', 20) FROM search_fts WHERE search_fts MATCH 'operations' LIMIT 5;"
```

Expected: Results from matching content (Porter stemmer will match "operate", "operations", "operating", etc.)

- [ ] **Step 4: Commit**

```bash
git add data/migrations/022_fts5_search.sql
git commit -m "feat: add FTS5 full-text search with Porter stemmer (migration 022)"
```

---

## Task 9: Integrate FTS5 into Search Tool

**Files:**
- Modify: `mcp-server/src/software_of_you/tools/search_tool.py`

- [ ] **Step 1: Read the current search_tool.py**

The current implementation at `mcp-server/src/software_of_you/tools/search_tool.py` uses `LIKE '%term%'` queries across each module's tables separately.

- [ ] **Step 2: Add FTS5 search path**

Add a helper function that checks if FTS5 is available and runs the FTS query:

```python
def _fts_search(query: str, limit: int = 10) -> list[dict] | None:
    """Try FTS5 search. Returns None if FTS5 table doesn't exist."""
    try:
        rows = execute(
            """SELECT entity_type, entity_id, title,
                      snippet(search_fts, 3, '', '', '...', 30) as snippet,
                      rank
               FROM search_fts
               WHERE search_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit),
        )
        return rows_to_dicts(rows)
    except Exception:
        return None  # FTS5 table doesn't exist or query syntax error
```

Modify the main `search()` function to try FTS5 first, then fall back to LIKE:

```python
# At the top of the search function, try FTS5
fts_results = _fts_search(query)
if fts_results is not None:
    # FTS5 available — use it as primary, supplement with LIKE for entity types FTS missed
    # Group FTS results by entity_type
    ...
    return {
        "result": results,
        "total_matches": total,
        "query": query,
        "search_mode": "fts5",
        "_context": { ... },
    }

# Fall through to existing LIKE-based search
```

Keep the existing LIKE search as the fallback (don't remove it). Add a `search_mode` field to the response (`"fts5"` or `"keyword"`).

- [ ] **Step 3: Verify the tool still loads**

```bash
cd /Users/kerrymorrison/Projects/PersonalProjects/better-software-of-you/mcp-server
python -c "from software_of_you.tools.search_tool import register; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add mcp-server/src/software_of_you/tools/search_tool.py
git commit -m "feat: add FTS5 search path to search tool with LIKE fallback"
```

---

## Task 10: Semantic Search Migration

**Files:**
- Create: `data/migrations/023_semantic_search.sql`

- [ ] **Step 1: Create the migration**

This migration only creates the metadata table. The `vec_embeddings` virtual table is created at setup time by `/embed setup` since the dimension depends on the configured provider.

```sql
-- Semantic Search (Optional)
-- Metadata table for tracking which entities have been embedded.
-- The vec_embeddings virtual table is created by /embed setup.

CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    embedded_at TEXT DEFAULT (datetime('now')),
    UNIQUE(entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_embeddings_type ON embeddings(entity_type);
```

- [ ] **Step 2: Run bootstrap and verify**

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/bootstrap.sh"
sqlite3 data/soy.db "PRAGMA table_info(embeddings);"
```

- [ ] **Step 3: Commit**

```bash
git add data/migrations/023_semantic_search.sql
git commit -m "feat: add embeddings metadata table for semantic search (migration 023)"
```

---

## Task 11: Semantic Search MCP Tool

**Files:**
- Create: `mcp-server/src/software_of_you/tools/semantic_search_tool.py`
- Modify: `mcp-server/src/software_of_you/server.py`
- Modify: `mcp-server/pyproject.toml`

- [ ] **Step 1: Add optional dependency to pyproject.toml**

Add after the `dependencies` section:

```toml
[project.optional-dependencies]
embeddings = ["sqlite-vec>=0.1.0", "httpx>=0.27"]
```

- [ ] **Step 2: Create the semantic search tool**

Write `mcp-server/src/software_of_you/tools/semantic_search_tool.py`:

```python
"""Semantic search across all modules via sqlite-vec embeddings."""

import json
from mcp.server.fastmcp import FastMCP
from software_of_you.db import execute, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def semantic_search(
        query: str,
        entity_types: str = "",
        limit: int = 10,
    ) -> dict:
        """Search by meaning across all modules using embeddings.

        Requires embeddings to be configured (run /embed setup first).
        Falls back to keyword search if embeddings aren't enabled.

        Args:
            query: Natural language search query
            entity_types: Comma-separated filter (e.g., 'transcript,note'). Empty = all.
            limit: Max results (default 10)
        """
        if not query:
            return {"error": "A search query is required."}

        # Check if embeddings are configured
        config_rows = execute(
            "SELECT key, value FROM soy_meta WHERE key LIKE 'embedding_%'"
        )
        config = {r["key"]: r["value"] for r in config_rows}

        if not config.get("embedding_provider"):
            return {
                "result": [],
                "search_mode": "unavailable",
                "note": "Semantic search not configured. Run /embed setup to enable. Using keyword search for now.",
                "_context": {
                    "presentation": "Let the user know semantic search isn't set up. Suggest /embed setup. Fall back to the regular search tool."
                },
            }

        # Get embedding for query
        provider = config["embedding_provider"]
        model = config.get("embedding_model", "nomic-embed-text")
        endpoint = config.get("embedding_endpoint", "http://localhost:11434")

        try:
            import httpx
            import sqlite_vec

            embedding = _get_embedding(query, provider, model, endpoint)
            if embedding is None:
                return {"error": "Failed to generate embedding for query. Is the embedding provider running?"}

            # Search vec_embeddings
            embedding_json = json.dumps(embedding)
            type_filter = ""
            if entity_types:
                types = [t.strip() for t in entity_types.split(",")]
                placeholders = ",".join("?" * len(types))
                type_filter = f"AND e.entity_type IN ({placeholders})"

            sql = f"""
                SELECT e.entity_type, e.entity_id, v.distance
                FROM vec_embeddings v
                JOIN embeddings e ON e.id = v.id
                WHERE v.embedding MATCH ?
                {type_filter}
                ORDER BY v.distance
                LIMIT ?
            """
            params = (embedding_json, *([t.strip() for t in entity_types.split(",")] if entity_types else []), limit)

            rows = execute(sql, params)
            results = _fetch_entities(rows_to_dicts(rows))

            return {
                "result": results,
                "total_matches": len(results),
                "query": query,
                "search_mode": "semantic",
            }

        except ImportError:
            return {
                "error": "sqlite-vec not installed. Run: pip install 'software-of-you[embeddings]'",
            }
        except Exception as ex:
            return {"error": f"Semantic search failed: {ex}"}


def _get_embedding(text: str, provider: str, model: str, endpoint: str) -> list[float] | None:
    """Get embedding vector from configured provider."""
    import httpx

    if provider == "ollama":
        resp = httpx.post(
            f"{endpoint}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=30.0,
        )
        if resp.status_code == 200:
            return resp.json().get("embedding")
    elif provider == "openai":
        api_key_rows = execute("SELECT value FROM soy_meta WHERE key = 'embedding_api_key'")
        if not api_key_rows:
            return None
        resp = httpx.post(
            f"{endpoint}/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key_rows[0]['value']}"},
            json={"model": model, "input": text},
            timeout=30.0,
        )
        if resp.status_code == 200:
            return resp.json()["data"][0]["embedding"]
    return None


def _fetch_entities(matches: list[dict]) -> list[dict]:
    """Fetch actual content for matched entities."""
    results = []
    entity_queries = {
        "contact": "SELECT id, name, company, role FROM contacts WHERE id = ?",
        "transcript": "SELECT id, title, summary FROM transcripts WHERE id = ?",
        "email": "SELECT id, subject, from_name, snippet FROM emails WHERE id = ?",
        "note": "SELECT id, title, substr(content, 1, 150) as preview FROM standalone_notes WHERE id = ?",
        "journal": "SELECT id, entry_date, substr(content, 1, 150) as preview FROM journal_entries WHERE id = ?",
        "decision": "SELECT id, title, status FROM decisions WHERE id = ?",
        "inbox": "SELECT id, substr(content, 1, 150) as preview FROM inbox WHERE id = ?",
    }
    for match in matches:
        etype = match["entity_type"]
        eid = match["entity_id"]
        query = entity_queries.get(etype)
        if query:
            rows = execute(query, (eid,))
            if rows:
                entity = rows_to_dicts(rows)[0]
                entity["_type"] = etype
                entity["_distance"] = match.get("distance")
                results.append(entity)
    return results
```

- [ ] **Step 3: Register in server.py (conditional import)**

Add after the Slack tool registration:

```python
# Register semantic search (optional — requires sqlite-vec)
try:
    from software_of_you.tools.semantic_search_tool import register as register_semantic
    register_semantic(server)
except ImportError:
    pass  # sqlite-vec not installed
```

- [ ] **Step 4: Verify import**

```bash
cd /Users/kerrymorrison/Projects/PersonalProjects/better-software-of-you/mcp-server
python -c "from software_of_you.tools.semantic_search_tool import register; print('OK')"
```

Expected: `OK` (the tool imports fine; sqlite-vec is only needed at runtime when the action is called)

- [ ] **Step 5: Commit**

```bash
git add mcp-server/src/software_of_you/tools/semantic_search_tool.py mcp-server/src/software_of_you/server.py mcp-server/pyproject.toml
git commit -m "feat: add semantic search MCP tool with Ollama/OpenAI embedding support"
```

---

## Task 12: Embed Command

**Files:**
- Create: `commands/embed.md`

- [ ] **Step 1: Create the command**

Write `commands/embed.md`:

```yaml
---
description: Set up, run, or check status of semantic search embeddings
allowed-tools: ["Bash", "Read", "Write"]
---
```

Subcommands (determined from user input after `/embed`):

**`/embed setup`:**
1. Ask user: Ollama (local, free) or OpenAI (cloud, requires API key)?
2. If Ollama: check if running (`curl -s http://localhost:11434/api/tags`), check if model is pulled
3. If OpenAI: ask for API key, store in `soy_meta` as `embedding_api_key`
4. Store provider config in `soy_meta` (provider, model, dimensions, endpoint)
5. Create `vec_embeddings` virtual table with correct dimensions:
   - Ollama nomic-embed-text: `float[768]`
   - OpenAI text-embedding-3-small: `float[1536]`
6. If switching providers (existing config detected): warn about re-embedding, drop old tables, recreate

**`/embed run`:**
1. Check config exists in `soy_meta`
2. For each entity type, find records not yet in `embeddings` table
3. Batch embed 10 at a time with 100ms delay
4. Insert into `vec_embeddings` + `embeddings` for each
5. Report: "Embedded 45 new records (12 notes, 8 transcripts, 25 emails). 340 total."

**`/embed status`:**
1. Show: provider, model, dimensions, total embedded, total pending by entity type

- [ ] **Step 2: Commit**

```bash
git add commands/embed.md
git commit -m "feat: add /embed command for semantic search setup and batch embedding"
```

---

## Task 13: Final Verification

- [ ] **Step 1: Run bootstrap to verify all migrations**

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/bootstrap.sh"
```

Expected: `ready|21|11|...` — 11 modules (inbox added), all migrations pass.

- [ ] **Step 2: Verify all new tables exist**

```bash
sqlite3 data/soy.db ".tables" | tr ' ' '\n' | sort | grep -E "inbox|proactive|search_fts|embeddings"
```

Expected: `embeddings`, `inbox`, `proactive_briefings`, `search_fts`

- [ ] **Step 3: Verify v_nudge_items includes inbox**

```bash
sqlite3 data/soy.db "SELECT sql FROM sqlite_master WHERE name='v_nudge_items';" | grep -c "unrouted_inbox"
```

Expected: `1`

- [ ] **Step 4: Verify MCP server loads all tools**

```bash
cd /Users/kerrymorrison/Projects/PersonalProjects/better-software-of-you/mcp-server
python -c "from software_of_you.server import create_server; s = create_server(); print('Tools loaded:', len(s._tools) if hasattr(s, '_tools') else 'OK')"
```

Expected: No import errors.

- [ ] **Step 5: Verify all commands exist**

```bash
ls -la commands/capture.md commands/inbox.md commands/proactive.md commands/embed.md
```

Expected: All 4 files exist.

- [ ] **Step 6: Functional test — capture an inbox item**

```bash
sqlite3 data/soy.db <<'SQL'
INSERT INTO inbox (content, tags, matched_contacts, created_at, updated_at)
VALUES ('Test capture — met someone at coffee', '[]', '[]', datetime('now'), datetime('now'));
SQL
sqlite3 data/soy.db "SELECT id, content FROM inbox WHERE content LIKE '%Test capture%';"
```

Expected: Row inserted and queryable.

- [ ] **Step 7: Functional test — FTS5 search**

```bash
sqlite3 data/soy.db "SELECT entity_type, title FROM search_fts WHERE search_fts MATCH 'operations' LIMIT 3;"
```

Expected: Results from FTS5 index.

- [ ] **Step 8: Clean up test data**

```bash
sqlite3 data/soy.db "DELETE FROM inbox WHERE content LIKE '%Test capture%';"
```

- [ ] **Step 9: Final commit (if any uncommitted changes remain)**

```bash
git status
# Only stage files from this plan — do NOT use git add -A
git add data/migrations/020_inbox_module.sql data/migrations/021_proactive.sql data/migrations/022_fts5_search.sql data/migrations/023_semantic_search.sql modules/inbox/manifest.json mcp-server/src/software_of_you/tools/inbox_tool.py mcp-server/src/software_of_you/tools/semantic_search_tool.py mcp-server/src/software_of_you/server.py mcp-server/src/software_of_you/tools/search_tool.py mcp-server/pyproject.toml commands/capture.md commands/inbox.md commands/proactive.md commands/embed.md commands/weekly-review.md
git commit -m "feat: complete Open Brain lessons — inbox, synthesis, proactive loop, FTS5, semantic search"
```
