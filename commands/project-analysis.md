---
skill: project-analysis
description: AI-powered project analysis — feature ideation, risk forecasting, and recommendations
user-invocable: true
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: <project name or id>
---

# /project-analysis — AI-Powered Project Analysis

Generate a deep analysis for a project: feature ideas, bug/security forecasts, and actionable recommendations — all grounded in actual project data. This is token-expensive by design (gathers everything) and manually triggered.

## Step 1: Resolve Project

If an argument was provided, match it against project names:
```sql
SELECT id, name, status, description FROM projects WHERE name LIKE '%' || '$ARGUMENTS' || '%' OR id = '$ARGUMENTS';
```

If no argument, show all projects:
```sql
SELECT id, name, status FROM projects ORDER BY name;
```

If no projects exist, tell the user: "No projects found. Create one first with `/project add`."

## Step 2: Gather ALL Project Data

This is the expensive step — collect everything the system knows about this project. Run as a single heredoc for efficiency.

### Core project data:
```sql
-- Project details
SELECT * FROM projects WHERE id = ?;

-- Project health (computed view)
SELECT * FROM v_project_health WHERE project_id = ?;

-- All tasks with full details
SELECT * FROM tasks WHERE project_id = ?
ORDER BY CASE status WHEN 'in_progress' THEN 1 WHEN 'todo' THEN 2 WHEN 'blocked' THEN 3 WHEN 'done' THEN 4 END;

-- Milestones
SELECT * FROM milestones WHERE project_id = ? ORDER BY target_date ASC NULLS LAST;

-- Notes
SELECT content, created_at FROM notes
WHERE entity_type = 'project' AND entity_id = ?
ORDER BY created_at DESC LIMIT 20;

-- Activity log (last 50)
SELECT action, details, created_at FROM activity_log
WHERE entity_type = 'project' AND entity_id = ?
ORDER BY created_at DESC LIMIT 50;

-- Tags
SELECT t.name, t.color FROM tags t
JOIN entity_tags et ON et.tag_id = t.id
WHERE et.entity_type = 'project' AND et.entity_id = ?;
```

### PM Conversations (if pm-intelligence module installed):
```sql
-- All PM conversations with full intelligence JSON
SELECT id, title, source, summary, intelligence, occurred_at, message_count
FROM pm_conversations WHERE project_id = ?
ORDER BY occurred_at ASC;

-- PM overview stats
SELECT * FROM v_pm_overview WHERE project_id = ?;
```

### CRM data (if client exists):
```sql
-- Client contact
SELECT * FROM contacts WHERE id = ?;

-- Interactions with client
SELECT * FROM contact_interactions WHERE contact_id = ?
ORDER BY occurred_at DESC LIMIT 20;

-- Open commitments
SELECT com.*, t.title as from_call
FROM commitments com
LEFT JOIN transcripts t ON t.id = com.transcript_id
WHERE com.status IN ('open', 'overdue')
AND (com.owner_contact_id = ?
  OR com.transcript_id IN (
    SELECT transcript_id FROM transcript_participants WHERE contact_id = ?));
```

### Email data (if Gmail module installed and client exists):
```sql
SELECT id, subject, snippet, from_name, direction, received_at
FROM emails WHERE contact_id = ?
ORDER BY received_at DESC LIMIT 30;
```

### Existing structured records (for deduplication context):
```sql
-- Decisions already tracked — don't recommend things already decided
SELECT id, title, decision, status FROM decisions WHERE project_id = ?;

-- Tasks already created — don't recommend things already tasked
SELECT id, title, status, priority FROM tasks WHERE project_id = ?;

-- Notes (architecture + prompts) — context for what's already documented
SELECT id, title, tags FROM standalone_notes WHERE linked_projects LIKE '%' || ? || '%';
```

Use these to avoid recommending features/fixes that already exist as records. If a recommendation maps to an existing task or decision, skip it or note "Already tracked as task #{id}" in the rationale.

### Previous analysis (for comparison):
```sql
SELECT id, summary, feature_ideas, bug_forecasts, recommendations, created_at
FROM project_analyses WHERE project_id = ?
ORDER BY created_at DESC LIMIT 1;
```

## Step 3: Perform Analysis

Using ALL gathered data, produce three categories of analysis. **Grounding rule (non-negotiable):** every single item MUST cite specific data from the project — a decision name, architecture note, PM session date, task name, activity log entry, email subject, etc. If an insight cannot be grounded in actual project data, do not include it.

### A. Feature Ideas (3-7 items)

Based on:
- Architecture notes and decisions from PM conversations
- Topics discussed across sessions (from `intelligence` JSON)
- What's been built (completed tasks and milestones)
- Trajectory of the project (what direction conversations are heading)
- Gaps visible in the task list (areas mentioned but not tasked)

Each item:
- `title`: Short, actionable feature name
- `description`: What this feature would do and why it matters
- `priority`: low / medium / high / critical
- `area`: Affected area (e.g., "auth", "API", "UI", "database", "infrastructure")
- `rationale`: Why this makes sense for the project right now
- `grounded_in`: Specific citations (e.g., "Decision 'Use WebSocket for real-time' from Feb 15 PM session", "Architecture note: 'Event-driven architecture for notifications'")

### B. Bug & Security Forecasts (3-7 items)

Based on:
- Architecture decisions and their implications
- Tech stack choices (from PM conversations)
- Task patterns (especially blocked tasks — what blocks them hints at fragility)
- Areas with high churn (many tasks created/completed in same area)
- Missing test coverage (look for testing tasks or lack thereof)
- Common vulnerability patterns for the tech stack discussed

Each item:
- `title`: Short description of the potential issue
- `description`: What could go wrong and how
- `severity`: low / medium / high / critical
- `likelihood`: low / medium / high
- `priority`: Derived from severity × likelihood
- `area`: Affected area
- `rationale`: Why this is a concern for THIS project specifically
- `grounded_in`: Specific citations (e.g., "Task 'API auth middleware' blocked for 5 days", "No testing tasks found in 47 total tasks", "Architecture note mentions 'direct DB access from frontend'")

### C. Recommendations (3-7 items)

Categories: `process`, `priority`, `technical_debt`, `architecture`, `testing`

Based on:
- Task completion patterns and velocity
- Overdue items and blocked work
- Decision patterns (lots of reversals? missing decisions for key areas?)
- Client interaction patterns (communication gaps?)
- Missing project infrastructure (no CI/CD tasks? no documentation tasks?)

Each item:
- `title`: Actionable recommendation
- `description`: What to do and why
- `priority`: low / medium / high / critical
- `area`: Category from above
- `rationale`: Why this matters now
- `grounded_in`: Specific citations

### Executive Summary

Write 2-3 sentences summarizing the project's current state and the key findings from all three categories. Ground it in the data.

## Step 4: Store Results

Build a data snapshot for staleness detection:
```json
{
  "task_count": N,
  "completed_tasks": N,
  "milestone_count": N,
  "pm_conversation_count": N,
  "activity_entries_analyzed": N,
  "email_count": N
}
```

Insert the analysis:
```sql
INSERT INTO project_analyses (project_id, summary, feature_ideas, bug_forecasts, recommendations, data_snapshot)
VALUES (?, ?, ?, ?, ?, ?);
```

Then insert each individual item into `project_analysis_items` with the `analysis_id` from the insert above.

Log to activity_log:
```sql
INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
VALUES ('project', ?, 'analysis_generated', ?, datetime('now'));
```

## Step 5: Generate HTML

Write an interactive HTML page to `output/analysis-{slug}.html` where slug is the project name lowercased with spaces → hyphens.

### Design System

- Tailwind CSS via CDN, Lucide icons, Inter font
- Background: `bg-zinc-50`, Cards: `bg-white rounded-xl shadow-sm border border-zinc-200`
- Read the design references:
  - `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/template-base.html`
  - `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/component-patterns.md`
  - `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/skills/dashboard-generation/references/delight-patterns.md`

### Page Layout

```
Header
├── Project name + "Project Analysis" subtitle
├── Analysis date + staleness indicator (if previous analysis exists: "Updated from X days ago")
└── Data snapshot pills (N tasks analyzed, N conversations, N emails)

Executive Summary Card (full width)
├── 2-3 sentence summary
└── Stat pills: N feature ideas · N risk flags · N recommendations

Three-column grid (responsive → stacks on mobile)
├── Column 1: Feature Ideas (blue/indigo accent)
│   └── Cards sorted by priority
├── Column 2: Bug & Security Forecasts (red/amber accent)
│   └── Cards sorted by severity × likelihood
└── Column 3: Recommendations (emerald/green accent)
    └── Cards sorted by priority

Evidence Trail (collapsible <details>)
└── All data sources cited, grouped by type
```

### Item Card Design

Each card in the columns:
```html
<div class="analysis-item" data-id="{item.id}" data-status="{item.status}">
  <!-- Title row -->
  <div class="flex items-start justify-between mb-2">
    <h4 class="font-semibold text-sm">{title}</h4>
    <span class="priority-badge">{priority}</span>
  </div>

  <!-- Description -->
  <p class="text-sm text-zinc-600 mb-2">{description}</p>

  <!-- For bug forecasts: severity + likelihood badges -->
  <!-- Severity badge + Likelihood badge (if applicable) -->

  <!-- Rationale -->
  <p class="text-xs text-zinc-500 mb-2">{rationale}</p>

  <!-- Evidence citation -->
  <div class="flex items-start gap-1 text-xs text-zinc-400">
    <i data-lucide="link" class="w-3 h-3 mt-0.5 flex-shrink-0"></i>
    <span>{grounded_in}</span>
  </div>

  <!-- Action buttons -->
  <div class="flex gap-2 mt-3 pt-3 border-t border-zinc-100">
    <button onclick="convertToTask({item.id})" class="convert-btn text-xs px-3 py-1.5 bg-zinc-900 text-white rounded-lg hover:bg-zinc-700 transition">
      Convert to Task
    </button>
    <button onclick="dismissItem({item.id})" class="dismiss-btn text-xs px-3 py-1.5 text-zinc-500 hover:text-zinc-700 hover:bg-zinc-100 rounded-lg transition">
      Dismiss
    </button>
  </div>
</div>
```

### Priority/Severity Badges

- Critical: `bg-red-50 text-red-700 border border-red-200`
- High: `bg-amber-50 text-amber-700 border border-amber-200`
- Medium: `bg-blue-50 text-blue-700 border border-blue-200`
- Low: `bg-zinc-50 text-zinc-600 border border-zinc-200`

### Column Accent Colors

- Feature Ideas: Header uses `bg-indigo-50 text-indigo-700`, icon `lightbulb`
- Bug Forecasts: Header uses `bg-red-50 text-red-700`, icon `shield-alert`
- Recommendations: Header uses `bg-emerald-50 text-emerald-700`, icon `compass`

### JavaScript (Interactive — follows audition board pattern)

Include these functions inline in a `<script>` tag:

```javascript
const API_BASE = window.location.origin;

async function convertToTask(itemId) {
  const btn = document.querySelector(`[data-id="${itemId}"] .convert-btn`);
  btn.disabled = true;
  btn.textContent = 'Converting...';
  try {
    const res = await fetch(`${API_BASE}/api/analysis-items/${itemId}/convert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    if (res.ok) {
      const data = await res.json();
      btn.textContent = 'Converted ✓';
      btn.className = 'convert-btn text-xs px-3 py-1.5 bg-emerald-100 text-emerald-700 rounded-lg cursor-default';
      // Hide dismiss button
      const dismissBtn = document.querySelector(`[data-id="${itemId}"] .dismiss-btn`);
      if (dismissBtn) dismissBtn.style.display = 'none';
      // Update card state
      document.querySelector(`[data-id="${itemId}"]`).dataset.status = 'converted';
      showToast(`Task created: ${data.title || 'New task'}`);
    } else {
      const err = await res.json();
      btn.textContent = err.error || 'Error';
      btn.disabled = false;
      setTimeout(() => { btn.textContent = 'Convert to Task'; }, 2000);
    }
  } catch (e) {
    btn.textContent = 'Server offline';
    btn.disabled = false;
    setTimeout(() => { btn.textContent = 'Convert to Task'; }, 2000);
  }
}

async function dismissItem(itemId) {
  const card = document.querySelector(`[data-id="${itemId}"]`);
  const btn = card.querySelector('.dismiss-btn');
  const currentStatus = card.dataset.status;
  const newStatus = currentStatus === 'dismissed' ? 'open' : 'dismissed';

  try {
    const res = await fetch(`${API_BASE}/api/analysis-items/${itemId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
      card.dataset.status = newStatus;
      if (newStatus === 'dismissed') {
        card.style.opacity = '0.4';
        btn.textContent = 'Restore';
        showToast('Item dismissed');
      } else {
        card.style.opacity = '1';
        btn.textContent = 'Dismiss';
        showToast('Item restored');
      }
    }
  } catch (e) {
    showToast('Server offline — try again');
  }
}

function showToast(msg) {
  const toast = document.createElement('div');
  toast.className = 'fixed bottom-6 right-6 bg-zinc-900 text-white text-sm px-4 py-2.5 rounded-xl shadow-lg z-50 transition-opacity duration-300';
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 2500);
}
```

### Dark Mode

Include dark mode support. The server automatically injects dark mode CSS, but the page should use Tailwind's `dark:` classes for any inline color overrides that the injected CSS wouldn't cover. Use the same dark mode init script pattern as other pages:

```html
<script>(function(){var s=localStorage.getItem('soy-dark-mode');if(s==='dark'||(s!=='light'&&window.matchMedia('(prefers-color-scheme:dark)').matches)){document.documentElement.classList.add('dark')}})();</script>
```

### Converted/Dismissed Item States

Items with `status = 'converted'`:
- Convert button shows "Converted ✓" in emerald
- Dismiss button hidden
- Card has subtle emerald left border

Items with `status = 'dismissed'`:
- Card at `opacity: 0.4`
- Dismiss button text shows "Restore"

Pre-render these states in the HTML based on the stored status, so the page looks correct before any JS runs.

## Step 6: Register View

```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename, created_at, updated_at)
VALUES ('project_analysis', 'project', ?, ?, 'analysis-{slug}.html', datetime('now'), datetime('now'))
ON CONFLICT(filename) DO UPDATE SET
  entity_name = excluded.entity_name,
  updated_at = datetime('now');
```

## Step 7: Open and Confirm

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/open_page.sh" analysis-{slug}.html
```

Tell the user:
> Project analysis for **{project name}** generated.
> {N} feature ideas · {N} risk forecasts · {N} recommendations
> View at: `output/analysis-{slug}.html`

If previous analysis existed, also note: "Previous analysis was from {date} — this replaces it with fresh data."
