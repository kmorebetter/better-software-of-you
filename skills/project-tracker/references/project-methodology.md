# Project Methodology

Single source of truth for every computed value in Project Tracker. All other files reference this — none define their own formulas.

---

## Momentum

Velocity = count of tasks completed in a 14-day window.

```sql
-- Current window: last 14 days
SELECT COUNT(*) FROM tasks
WHERE project_id = ? AND status = 'done'
  AND completed_at >= date('now', '-14 days');

-- Previous window: 14–28 days ago
SELECT COUNT(*) FROM tasks
WHERE project_id = ? AND status = 'done'
  AND completed_at >= date('now', '-28 days')
  AND completed_at < date('now', '-14 days');
```

### Classification (first match wins)

| Label | Rule |
|-------|------|
| **Stalling (override)** | No task completions in 7+ days (regardless of prior velocity) |
| **NULL** | `velocity_current = 0` AND `velocity_previous = 0` (no task completions to measure) |
| **Accelerating** | `velocity_current > velocity_previous * 1.3` |
| **Stalling** | `velocity_current < velocity_previous * 0.7` |
| **Steady** | Everything else (within ±30% of previous window) |

### Display format (mandatory)

```
Accelerating — 5 tasks completed this period vs 2 last period
Stalling — 1 task completed this period vs 4 last period
Stalling — no task completions in 9 days
Steady — 3 tasks completed this period vs 3 last period
— (NULL — no task completions to measure)
```

Always show the numbers that drove the classification.

---

## Risk Assessment

Threshold-based. First matching level wins.

| Level | Criteria |
|-------|----------|
| **High** | >=3 overdue tasks, OR >=1 missed milestone (target_date < today AND status != 'completed'), OR no activity_log entries in 14+ days on an active project |
| **Medium** | 1–2 overdue tasks, OR overdue commitments related to this project, OR target_date within 14 days AND open tasks > completed tasks |
| **Low** | All tasks on track, no overdue items, regular activity |

### Required queries

```sql
-- Overdue tasks
SELECT COUNT(*) FROM tasks
WHERE project_id = ? AND status NOT IN ('done')
  AND due_date < date('now');

-- Missed milestones
SELECT COUNT(*) FROM milestones
WHERE project_id = ? AND target_date < date('now')
  AND status != 'completed';

-- Days since last activity
SELECT CAST(julianday('now') - julianday(MAX(created_at)) AS INTEGER)
FROM activity_log
WHERE entity_type = 'project' AND entity_id = ?;

-- Overdue commitments (if Conversation Intelligence installed)
SELECT COUNT(*) FROM commitments
WHERE status = 'overdue'
  AND transcript_id IN (
    SELECT transcript_id FROM transcript_participants
    WHERE contact_id = (SELECT client_id FROM projects WHERE id = ?)
  );

-- Open vs completed tasks (for medium check)
SELECT
  SUM(CASE WHEN status != 'done' THEN 1 ELSE 0 END) as open_tasks,
  SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done_tasks
FROM tasks WHERE project_id = ?;

-- Target date proximity
SELECT target_date,
  CAST(julianday(target_date) - julianday('now') AS INTEGER) as days_remaining
FROM projects WHERE id = ?;
```

### Display format (mandatory)

Always output reasoning:

```
High — 4 overdue tasks, no activity in 16 days
Medium — 2 overdue tasks, target date in 11 days with 8/12 tasks remaining
Low — all tasks on track, last activity 2 days ago
```

---

## Action Prioritization

Ranked order. First category with items wins top priority.

| Priority | Category | Sort within |
|----------|----------|-------------|
| 1 | **Unblock blocked tasks** | By number of dependent tasks, then creation date ASC |
| 2 | **Overdue tasks** | Most days overdue first |
| 3 | **Approaching milestones** | Within 14 days, by target_date ASC |
| 4 | **Tasks due soon** | Within 7 days, by due_date ASC |
| 5 | **Follow-ups needed** | For project client, by due_date ASC |

### Required queries

```sql
-- Blocked tasks
SELECT t.id, t.title, t.created_at FROM tasks
WHERE project_id = ? AND status = 'blocked'
ORDER BY created_at ASC;

-- Overdue tasks (with days overdue)
SELECT t.id, t.title, t.due_date,
  CAST(julianday('now') - julianday(t.due_date) AS INTEGER) as days_overdue
FROM tasks
WHERE project_id = ? AND status NOT IN ('done') AND due_date < date('now')
ORDER BY days_overdue DESC;

-- Approaching milestones
SELECT m.id, m.name, m.target_date,
  CAST(julianday(m.target_date) - julianday('now') AS INTEGER) as days_until
FROM milestones
WHERE project_id = ? AND status != 'completed'
  AND target_date BETWEEN date('now') AND date('now', '+14 days')
ORDER BY target_date ASC;

-- Tasks due soon
SELECT t.id, t.title, t.due_date,
  CAST(julianday(t.due_date) - julianday('now') AS INTEGER) as days_until
FROM tasks
WHERE project_id = ? AND status NOT IN ('done', 'blocked')
  AND due_date BETWEEN date('now') AND date('now', '+7 days')
ORDER BY due_date ASC;

-- Client follow-ups (if CRM installed)
SELECT f.id, f.reason, f.due_date, c.name
FROM follow_ups f
JOIN contacts c ON c.id = f.contact_id
WHERE f.contact_id = (SELECT client_id FROM projects WHERE id = ?)
  AND f.status = 'pending'
ORDER BY f.due_date ASC;
```

### Display format

Actions must be specific and reference data:

```
1. Unblock "API integration" task — blocked since Feb 10
2. Complete "Update wireframes" — 5 days overdue
3. Milestone "Beta launch" due in 8 days — 4/7 tasks remaining
4. "Write test suite" due in 3 days
5. Follow up with Sarah Chen — pending since Feb 18
```

Not: "Follow up with client" or "Complete tasks"

---

## Client Relationship Temperature

When CRM + Conversation Intelligence are both installed, pull from `relationship_scores` — never invent.

### Data sources

```sql
-- Latest relationship score for the client
SELECT relationship_depth, trajectory, meeting_frequency,
  commitment_follow_through, notes
FROM relationship_scores
WHERE contact_id = (SELECT client_id FROM projects WHERE id = ?)
ORDER BY score_date DESC LIMIT 1;

-- Interaction frequency (interactions per week over 30 days)
SELECT COUNT(*) / 4.3 as interactions_per_week
FROM contact_interactions
WHERE contact_id = (SELECT client_id FROM projects WHERE id = ?)
  AND occurred_at >= date('now', '-30 days');
```

### Display rules

- If relationship_scores exist: show `relationship_depth`, `trajectory`, follow-through percentages, meeting_frequency
- If only CRM data (no Conversation Intelligence): show interaction frequency as interactions/week
- If no client: skip this section entirely

### Display format

```
Collaborative, strengthening — 1.6 meetings/week, follow-through user:75% contact:68%
Professional, stable — 0.8 meetings/week, interaction frequency 2.1/week
No conversation data — relationship based on interaction frequency only (1.4/week)
```

Never use: "email tone", "current dynamic", "client satisfaction signals" — these are not computable.

---

## Stale Activity Thresholds

```sql
SELECT CAST(julianday('now') - julianday(MAX(created_at)) AS INTEGER) as days_since_activity
FROM activity_log
WHERE entity_type = 'project' AND entity_id = ?;
```

| Days | Status |
|------|--------|
| 0–6 | Active |
| 7–13 | Stale (warn) |
| 14+ | High risk flag (feeds into Risk Assessment) |

Only applies to projects with status = 'active'. Paused/completed projects are not flagged.
