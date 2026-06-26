---
title: Keep derived views fresh with a read-only renderer plus standing refresh rules
date: 2026-06-26
category: architecture-patterns
module: contacts
problem_type: architecture_pattern
component: tooling
severity: medium
related_components:
  - assistant
  - development_workflow
applies_when:
  - "a derived artifact (HTML pages, reports, exports) is generated from a source-of-truth store and must stay current"
  - "some of the refresh is pure transformation and some needs model synthesis (summaries, scoring, judgment)"
  - "someone asks to make updates happen automatically / whenever X"
  - "you are tempted to put model-required work into a settings.json hook"
tags:
  - "rendered-views"
  - "freshness"
  - "deterministic-renderer"
  - "hooks-vs-instructions"
  - "standing-rules"
  - "contact-pages"
---

# Keep derived views fresh with a read-only renderer plus standing refresh rules

## Context

Software of You renders a per-contact HTML "intelligence sheet" (the *Your People* pages) from the SQLite database. The first build was an ad-hoc script in a scratch dir; the moment new interactions land, those pages are stale. The user asked for "rules and tooling to keep these contact sheets updated."

The trap: reaching for a single `settings.json` hook to "regenerate on every change." It doesn't work, because the refresh has **two fundamentally different kinds of work** mixed together:

1. **Deterministic transformation** — read the DB, emit HTML. Pure, cheap, no model needed.
2. **Model-required synthesis** — turn a new transcript into relationship context, talk-ratio scoring, coach notes. This *needs the model*; a shell hook cannot produce it.

A hook fired by the harness can do (1) but never (2). Conflating them produces a hook that silently does nothing useful for the part that matters.

## Guidance

**Split the refresh by what each part actually requires, then wire each to the right mechanism.**

**1. Deterministic rendering → a pure, read-only script.**
Put the DB→artifact transformation in one idempotent script that rebuilds *everything* from the source of truth (`scripts/build_contact_pages.py`). Make it: read-only (never mutates data), grounded (missing values render as `—`, never invented), and path-portable (resolve root from `CLAUDE_PLUGIN_ROOT` else the script's own location). Because it is read-only and idempotent, it is **safe to invoke from anywhere, any number of times** — which is what lets you trigger it freely.

**2. Model-required synthesis → a standing instruction, NOT a hook.**
The part that needs the model (refreshing each contact's interaction-derived context notes, computing scores/insights) belongs in the project instruction file (`CLAUDE.md`) as a standing behavior the model performs, plus the ingestion command (`/import-call`) that already runs the analysis. Do not try to encode it as a `settings.json` hook — the harness executes hooks, the model isn't in that loop.

**3. Wire the deterministic renderer at multiple trigger points:**
- **Ingestion** — a final step in the command that ingests new data (`/import-call`): after the model writes the synthesis, run the renderer.
- **Scheduled** — append it to the existing background sync job (`scheduled_sync.sh`) so views stay fresh hands-off between sessions (deterministic part only — the scheduled job has no model).
- **On-demand** — a thin command (`/contact-pages`) that bootstraps, builds, and opens the result.

The net effect: the cheap deterministic part runs automatically and everywhere; the expensive model part runs only where a model is genuinely in the loop.

## Why This Matters

- **Manually-built views drift from the source of truth the instant they're generated.** A standing renderer wired to real events is the only thing that keeps them honest over time.
- **Hooks can't think.** "Whenever X, synthesize Y" is a category error if Y needs the model. Recognizing which half of a refresh is deterministic vs model-required is the whole decision. Deterministic → script/hook; synthesis → standing instruction the model follows.
- **Read-only + idempotent = free to trigger.** Because the renderer never writes data and always rebuilds from scratch, you can attach it to three triggers without worrying about ordering, partial state, or double-runs.

## When to Apply

Any time a derived artifact must track a source-of-truth store: dashboards, contact/entity pages, exported reports, generated docs. It applies most sharply when the "make it auto-update" request bundles pure transformation with work that needs judgment/synthesis — split them and route each correctly. Skip the ceremony for a one-off artifact nobody needs kept current.

## Examples

**The implementation (this session):**
- `scripts/build_contact_pages.py` — read-only renderer, all pages + index from the DB, gaps as `—`.
- Trigger 1 — `commands/import-call.md` Step 3i: after analysis, refresh participant context notes (model) → run the renderer (deterministic).
- Trigger 2 — `shared/scheduled_sync.sh`: rebuild sheets after each 3×/day sync.
- Trigger 3 — `commands/contact-pages.md` (`/contact-pages`): on-demand bootstrap → build → open.
- Standing rule — `CLAUDE.md` → "Enrich contacts from interactions": the model refreshes `notes` using `WHO:/RELATIONSHIP:/STATE:/Basis:` labels so the brief renders structured, not as a wall.

**Anti-pattern — a hook for the synthesis half:**
```jsonc
// settings.json — WRONG: a hook cannot synthesize relationship context
{ "hooks": { "PostToolUse": [{ "matcher": "Write",
  "hooks": [{ "type": "command", "command": "regenerate_contact_context.sh" }] }] } }
```
There is no deterministic `regenerate_contact_context.sh` — that work needs the model. The synthesis belongs in `CLAUDE.md`; only the rendering belongs in a script/hook.

**Gotcha — hooks fire on tool events, not on script side effects.** A `PostToolUse`/`Write` hook (e.g. an "open the file in the browser" hook) fires when the model uses the **Write tool**, but NOT when a file is created by a Bash-run script. So script-generated artifacts must be opened/handled explicitly; don't assume a Write-matched hook covers them.

## Related
- `CLAUDE.md` → "Enrich contacts from interactions" — the standing synthesis rule this renderer pairs with.
- Auto memory `soy-enrich-from-interactions` — the upstream preference (relationship value = interaction context, not firmographics).
- `commands/entity-page.md` — the complementary *model-built* single-contact brief (deep, bespoke); this pattern is the *deterministic batch* counterpart.
- `docs/solutions/best-practices/verify-commitment-completion-before-closing.md` — sibling learning from the same work; the renderer surfaces only evidence-grounded values, consistent with the no-fabrication rule.
