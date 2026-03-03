# Software of You — Project Bridge

<!-- Copy this file into your dev project repo as CLAUDE.md (or append to existing CLAUDE.md) -->
<!-- Then fill in the project mapping below -->

## Project Mapping

This repo is tracked in Software of You:
- **Project ID:** <!-- e.g., 7 -->
- **Project name:** <!-- e.g., "Acme Web Redesign" — used for fuzzy matching if ID is omitted -->

## Session Workflow

### On session start
- Check tasks: `projects(action="get", project_id=<ID>)` — review open tasks and priorities.
- Note any blockers or context from previous sessions.

### During the session
- **Log meaningful activity** with `dev_log` as you go:
  - Commits: `dev_log(activity_type="commit", description="...", project_name="...", metadata='{"branch": "...", "hash": "..."}')`
  - Test runs: `dev_log(activity_type="test_run", description="...", metadata='{"passed": N, "failed": N}')`
  - Deploys, refactors, debugging sessions — anything worth remembering.
- **Update task status** when tasks are started or completed:
  - `projects(action="update_task", task_id=<ID>, task_status="in_progress")`
  - `projects(action="update_task", task_id=<ID>, task_status="done")`
- **Log decisions** when architectural or technical choices are made:
  - `decisions(action="log", title="...", decision="...", rationale="...", project_id=<ID>)`

### On session end
- Call `session_debrief` with a summary of the session:
  ```
  session_debrief(
    project_name="...",
    accomplished="What was done",
    decisions='[{"title": "...", "decision": "...", "rationale": "..."}]',
    blockers="What's stuck",
    next_steps="What to do next",
    tasks_completed='[1, 2, 3]',
    tasks_started='[4, 5]',
    mood="focused",
    energy=4
  )
  ```

## What NOT to log
- Trivial file saves, typo fixes, or formatting changes.
- Every individual `git add` or `git status` — only log actual commits.
- Don't fabricate metadata (commit hashes, test counts) — only log what actually happened.
- Don't log the same activity twice.
