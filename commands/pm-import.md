---
skill: pm-import
description: Import a PM conversation or session debrief — extract decisions, prompts, and architecture notes
user-invocable: true
---

# /pm-import — Import PM Conversation or Session Debrief

Import a project management conversation from Gemini, ChatGPT, Claude, or any AI tool. Also handles **structured session debriefs** from Gemini Gems — compact summaries that capture session progress without pasting the full conversation.

## Flow

### 1. Get the conversation text

If the user didn't paste text with the command, ask:

> Paste a conversation or session debrief. I'll extract the intelligence and link it to a project.

Wait for the pasted text.

### 2. Detect source

Look at the text format to auto-detect the source:
- Starts with `## Session Debrief:` or `## Debrief:` → `gemini_debrief` (**fast path — skip to step 2b**)
- Lines starting with `You` followed by content → `gemini_web`
- Lines with `User:` / `Assistant:` or `Human:` / `Claude:` → `claude`
- Lines with `User:` / `ChatGPT:` → `chatgpt`
- If no clear pattern → `manual`

### 2b. Debrief fast path (source = `gemini_debrief`)

When a structured debrief is detected, the text is **already organized by category**. Handle it differently:

1. **Extract project name from the header** — `## Session Debrief: {Project Name}` or `## Debrief: {Project Name}`
2. **Auto-match to a project** — fuzzy match the project name against existing projects:
   ```sql
   SELECT id, name FROM projects WHERE status IN ('active', 'planning') ORDER BY name;
   ```
   If a clear match is found (case-insensitive, substring), link automatically without asking. If ambiguous, ask. If no match, ask if they want to create the project.
3. **Extract the date** — look for a `Date:` line near the top. Use it for `occurred_at`. If missing, use `datetime('now')`.
4. **Skip message parsing** — debriefs are not conversations. Store the full text as `raw_text` with `message_count = 1`.
5. **Continue to step 5** (store) then **step 6** (analyze). The structured sections make extraction straightforward:
   - `### What was done` → feeds into `summary`
   - `### Decisions` → maps directly to `intelligence.decisions`
   - `### Architecture` → maps to `intelligence.architecture_notes`
   - `### Prompts used` → maps to `intelligence.claude_prompts`
   - `### Open items` → maps to `intelligence.action_items`
   - `### Blockers` → maps to `intelligence.action_items` (with status `blocked`)
   - `### Bugs fixed` → maps to `intelligence.topics_discussed` + relevant `decisions`

Then **skip to step 7** (store analysis).

### 3. Parse messages (conversation imports only)

Split the conversation into individual messages. Parsing rules:

**Gemini web format:**
- `You` on its own line (or `You said:`) starts a user message
- `Gemini` on its own line (or `Gemini said:`) starts a model message
- Everything between labels is the message content

**Claude format:**
- `Human:` or `User:` starts a user message
- `Assistant:` or `Claude:` starts a model message

**ChatGPT format:**
- `User:` starts a user message
- `ChatGPT:` or `Assistant:` starts a model message

**Fallback:** If no pattern matches, store the entire text as a single user message.

For each message, INSERT into `pm_messages` with:
- `conversation_id` — the pm_conversation id
- `role` — 'user' or 'model'
- `content` — the message text (trimmed)
- `sequence_num` — 1-indexed order

### 4. Link to project

Query active projects:
```sql
SELECT id, name, status FROM projects WHERE status IN ('active', 'planning') ORDER BY name;
```

If projects exist, show them as a numbered list and ask:
> Which project is this conversation for? (number, or "skip" to leave unlinked)

If no projects exist, mention they can link it later.

**Note:** For debriefs (step 2b), project linking is already handled — skip this step.

### 5. Store the conversation

```sql
INSERT INTO pm_conversations (title, project_id, source, raw_text, message_count, occurred_at, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'));
```

- `title` — for debriefs: use "Session debrief — {date}" or the first bullet from "What was done". For conversations: generate from the first user message (~60 chars or a summary phrase).
- `project_id` — from step 2b (debrief) or step 4 (conversation)
- `source` — from step 2
- `raw_text` — the full pasted text
- `message_count` — count of parsed messages (1 for debriefs)
- `occurred_at` — from the debrief `Date:` line, or ask the user, or default to `datetime('now')`

### 6. Analyze the conversation

Read through ALL messages and extract:

**Decisions** — any explicit choices made ("let's go with X", "we'll use Y", "decided to Z"):
```json
{"description": "...", "context": "why this was decided", "message_index": N}
```

**Action items** — tasks assigned or agreed upon ("need to build X", "TODO: Y", "next step is Z"):
```json
{"description": "...", "status": "pending", "assignee": "claude|user|other"}
```

**Claude prompts** — any prompts written for Claude CLI / Cursor / other coding tools. These are typically code blocks or detailed instructions starting with phrases like "paste this into Claude", "use this prompt", or contained in markdown code blocks that are clearly prompts:
```json
{"prompt_text": "the full prompt", "purpose": "what it's meant to accomplish", "outcome": null}
```

**Architecture notes** — technical decisions about structure, patterns, tools, database design, API design:
```json
{"topic": "e.g. database schema", "detail": "the specific note"}
```

**Topics discussed** — list of high-level topics covered (e.g., ["search", "auth", "database migration"])

Build the intelligence JSON:
```json
{
  "decisions": [...],
  "action_items": [...],
  "claude_prompts": [...],
  "architecture_notes": [...],
  "topics_discussed": [...]
}
```

### 7. Store analysis

```sql
UPDATE pm_conversations
SET intelligence = ?,
    summary = ?,
    processed_at = datetime('now'),
    updated_at = datetime('now')
WHERE id = ?;
```

- `summary` — 2-3 sentence overview of what was discussed and decided

### 7b. Decompose intelligence into structured records

After storing the intelligence JSON, create real database records so items are queryable via MCP tools. **This step is idempotent** — check for duplicates before inserting.

For each category in the `intelligence` JSON, create records in the corresponding table. Use the conversation ID (`cid`) for provenance tracking.

**Decisions → `decisions` table:**
```sql
-- For each decision in intelligence.decisions:
-- First check for duplicates:
SELECT id FROM decisions WHERE title = ? AND project_id = ?;
-- If no match, insert:
INSERT INTO decisions (title, decision, context, rationale, project_id, decided_at, status)
VALUES (
  ?, -- title: truncate description to ~80 chars
  ?, -- decision: the full description
  ?, -- context: the context field if present
  ?, -- rationale: append provenance "[pm-import:cid=N]"
  ?, -- project_id
  ?, -- decided_at: use conversation occurred_at
  'decided'
);
```

**Action items → `tasks` table:**
```sql
-- For each item in intelligence.action_items:
SELECT id FROM tasks WHERE title = ? AND project_id = ?;
-- If no match:
INSERT INTO tasks (project_id, title, description, status, priority)
VALUES (
  ?, -- project_id
  ?, -- title: the description, truncated to ~80 chars
  ?, -- description: full text + "\n[pm-import:cid=N]"
  'todo',
  'medium'
);
```

**Architecture notes → `standalone_notes` table:**
```sql
-- For each item in intelligence.architecture_notes:
SELECT id FROM standalone_notes WHERE title = ? AND linked_projects LIKE ?;
-- If no match:
INSERT INTO standalone_notes (title, content, tags, linked_projects)
VALUES (
  ?, -- title: "Architecture: {topic}"
  ?, -- content: the detail text + "\n\n[pm-import:cid=N]"
  '["architecture","pm-import"]',
  ? -- linked_projects: JSON array with project_id, e.g. '[3]'
);
```

**Claude prompts → `standalone_notes` table:**
```sql
-- For each item in intelligence.claude_prompts:
SELECT id FROM standalone_notes WHERE title = ? AND linked_projects LIKE ?;
-- If no match:
INSERT INTO standalone_notes (title, content, tags, linked_projects)
VALUES (
  ?, -- title: "Claude Prompt: {purpose}"
  ?, -- content: the full prompt_text + "\n\n[pm-import:cid=N]"
  '["claude-prompt","pm-import"]',
  ? -- linked_projects: JSON array with project_id, e.g. '[3]'
);
```

**After decomposition, report the counts:**
> Decomposed into: {N} decisions, {N} tasks, {N} architecture notes, {N} Claude prompts

### 8. Log activity

```sql
INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
VALUES ('pm_conversation', ?, 'imported', ?, datetime('now'));
```

If linked to a project:
```sql
INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
VALUES ('project', ?, 'pm_conversation_added', ?, datetime('now'));
```

### 9. Present results

Show a structured summary:

> **Imported:** {title}
> **Source:** {source} · **Messages:** {count} · **Project:** {project_name or "Unlinked"}
>
> **Summary:** {summary}
>
> | Category | Count |
> |----------|-------|
> | Decisions | N |
> | Action Items | N |
> | Claude Prompts | N |
> | Architecture Notes | N |
>
> **Decisions:**
> - {decision 1}
> - {decision 2}
>
> **Action Items:**
> - [ ] {item 1} (assignee)
> - [ ] {item 2} (assignee)
>
> **Claude Prompts:** {count} captured — use `/pm-report {project}` to see full prompts
>
> **Next:** Import another conversation or run `/pm-report {project}` to generate the full intelligence report.
