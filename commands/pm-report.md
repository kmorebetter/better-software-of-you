---
skill: pm-report
description: Generate a PM intelligence report — decisions, prompts, architecture notes, and progress for a project
user-invocable: true
---

# /pm-report — PM Intelligence Report

Generate an HTML report showing all PM conversation intelligence for a project — decisions, Claude prompts, architecture notes, action items, and a progress narrative.

## Flow

### 1. Resolve the project

If an argument was provided, match it against project names:
```sql
SELECT id, name FROM projects WHERE name LIKE '%' || ? || '%' ORDER BY name;
```

If no argument, show projects that have PM conversations:
```sql
SELECT p.id, p.name, v.conversation_count, v.total_decisions, v.total_claude_prompts
FROM v_pm_overview v
JOIN projects p ON p.id = v.project_id
WHERE v.conversation_count > 0
ORDER BY v.latest_conversation_at DESC;
```

If no PM conversations exist for any project, tell the user:
> No PM conversations imported yet. Use `/pm-import` to import a Gemini or AI conversation first.

### 2. Gather data

```sql
-- Project overview stats
SELECT * FROM v_pm_overview WHERE project_id = ?;

-- All conversations for this project
SELECT * FROM pm_conversations WHERE project_id = ? ORDER BY occurred_at ASC;

-- All messages (for context in narrative)
SELECT pm.*, pc.title AS conversation_title
FROM pm_messages pm
JOIN pm_conversations pc ON pc.id = pm.conversation_id
WHERE pc.project_id = ?
ORDER BY pc.occurred_at ASC, pm.sequence_num ASC;

-- Project details
SELECT * FROM projects WHERE id = ?;
```

### 3. Extract intelligence — structured records first, JSON fallback

**Primary source: structured database records** (created by pm-import Step 7b or backfill):
```sql
-- Decisions from the decisions table
SELECT id, title, decision, context, rationale, status, decided_at
FROM decisions WHERE project_id = ?
ORDER BY decided_at ASC;

-- Tasks from the tasks table (action items)
SELECT id, title, description, status, priority, created_at
FROM tasks WHERE project_id = ?
ORDER BY CASE status WHEN 'in_progress' THEN 1 WHEN 'todo' THEN 2 WHEN 'blocked' THEN 3 WHEN 'done' THEN 4 END;

-- Architecture notes from standalone_notes
SELECT id, title, content, created_at
FROM standalone_notes
WHERE linked_projects LIKE '%' || ? || '%' AND tags LIKE '%architecture%'
ORDER BY created_at ASC;

-- Claude prompts from standalone_notes
SELECT id, title, content, created_at
FROM standalone_notes
WHERE linked_projects LIKE '%' || ? || '%' AND tags LIKE '%claude-prompt%'
ORDER BY created_at ASC;
```

**Fallback: intelligence JSON blobs** — for any conversation whose items haven't been decomposed into records yet, extract from the `intelligence` JSON as before. This keeps the report backwards-compatible with projects that haven't been backfilled.

Merge both sources into unified lists:
- All decisions → unified decisions log (show live status from `decisions` table)
- All action items → unified tracker (show live status from `tasks` table)
- All Claude prompts → prompt gallery
- All architecture notes → grouped by topic
- All topics → combined topic cloud (from JSON `topics_discussed` arrays)

### 4. Generate progress narrative

Read through all conversations chronologically and write a 3-5 paragraph narrative covering:
- How the project started and what the initial goals were
- Key turning points and decisions
- Current state and what's been accomplished
- What's next / open items

Ground every statement in the actual conversation data. Don't fabricate progress.

### 5. Generate HTML report

Write to `output/pm-report-{slug}.html` where slug is the project name lowercased with spaces replaced by hyphens.

**Design system:** Tailwind CSS, Lucide icons, Inter font, white background, card-based layout.

**Layout:**
- Fixed left sidebar with navigation links to each section
- Main content area with sections

**Sections:**

#### Header
- Project name, conversation count, date range
- Source badges (gemini_web, claude, etc.)

#### Stats Grid (4 columns)
- Conversations count
- Total decisions
- Claude prompts generated
- Days since last PM session

#### Conversation Timeline
Chronological cards for each conversation:
- Title, date, source badge, message count
- Summary text
- Decision count badge, action item count badge
- Expandable/collapsible with `<details>` tags

#### Decisions Log
Table or card list of all decisions across all conversations:
- Decision description
- Context/reasoning
- Source conversation + message index
- Date

#### Action Items Tracker
Table of all action items:
- Description
- Assignee (badge: user / claude / other)
- Status (pending / done)
- Source conversation

#### Claude Prompts Gallery
Each prompt in its own card:
- Purpose description
- Full prompt text in a `<pre><code>` block with monospace font
- Outcome (if recorded)
- Source conversation

#### Architecture Notes
Grouped by topic:
- Topic heading
- Detail text
- Source conversation

#### Progress Narrative
The AI-generated narrative from step 4, in prose paragraphs.

### 6. Register the view

```sql
INSERT OR REPLACE INTO generated_views (filename, entity_type, entity_id, entity_name, view_type, created_at, updated_at)
VALUES (?, 'project', ?, ?, 'pm_report', datetime('now'), datetime('now'));
```

### 7. Open in browser

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/open_page.sh" pm-report-{slug}.html
```

### 8. Confirm

> PM Intelligence Report generated for **{project name}**.
> {conversation_count} conversations · {decisions} decisions · {prompts} Claude prompts
> View at: `output/pm-report-{slug}.html`
