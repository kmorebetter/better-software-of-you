# Task Plan: Awareness Loop + Deterministic Renderer

## Goal
Turn Software of You from a pull-based archive into a proactive partner:
(A) scheduled refresh + a Signals Engine that surfaces the few things worth knowing, delivered by
email + brief file + dashboard + in-session; (B) port the orphaned Jinja renderer into a plugin-side
`scripts/render.py` so the whole interface rebuilds in seconds instead of 40+ agent runs.

Full plan: `~/.claude/plans/snuggly-growing-deer.md`

## Current Phase
Phase A — Awareness loop (schedulers + Signals Engine + delivery)

## Phases

### Phase A: Awareness loop
- [x] A1 `data/migrations/022_signals.sql` — signals state-ledger table (applied; table live)
- [x] A2 `scripts/signals.py` — detectors + scorer + dedup/resolve + noise filter + CLI (10 signals, dedup verified)
- [x] A3 `shared/send_email.py` — Gmail send verified (real email delivered to kmo@betterstory.co)
- [x] A4 rework `scripts/morning-brief.sh` — deterministic brief floor + optional Claude enrich; e2e run OK
- [x] A5 `shared/you.softwareof.brief.plist` — 7:53am weekday launchd template
- [x] A6 extend `commands/auto-sync.md` — on/off/status manage BOTH agents
- [x] A7 `hooks/session-start.py` — SessionStart now leads with top-signals summary (verified)
- [x] A8 turn it on — both launchd agents bootstrapped + loaded (`launchctl list` confirms)
- **Status:** COMPLETE — awareness loop live
- **Note:** morning-brief.sh references scripts/render.py (Phase B); guarded to skip if absent.

### Phase B: Deterministic renderer ("big swing")
- [x] B1 `scripts/render.py` — deterministic dashboard + 9 module views + entity pages; 26 pages in ~1.4s; XSS-tested (payload escaped), no template leaks
- [x] B2 `data/migrations/023_entity_narratives.sql` — narrative table + save-narrative round-trip verified (staleness flips off on save)
- [x] B3 stable slugs — contacts.slug frozen at first render; used for filenames
- [x] B4 wired: build-all.md rewritten to delegate; morning.md updated (+ fixed latent v_nudge_items title/context bug); pipeline.py Phase 3 deterministic (26 pages)
- [x] B5 cleanup — removed contact-cards/jeff-benjis/open-externally-test + people/ (16); generated_views reconciled (16 entity rows, 0 orphans)
- **Status:** COMPLETE — full-site rebuild is one ~1.4s script call
- **Note:** render.py adds `save-narrative` (Claude writes prose → renderer owns fingerprint + re-renders).
  Not yet covered by renderer: decision-journal/journal/notes module views (0 data today) — still Claude when data exists.

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Port renderer into plugin script (not revive MCP server / not fresh JSON) | Reuses the already-built Jinja templates + db layer; keeps the live plugin surface |
| Deliver via email + brief file + dashboard + in-session (no macOS notification) | User choice |
| launchd + headless Claude for the schedule | Local-first; 90% scaffolded already |
| Signals Engine = detect→score→state-ledger→restraint→synthesize→deliver→feedback | Restraint over recall; state/memory is the differentiator |

## Key facts (grounded)
- Migrations auto-apply via `schema_migrations` ledger (bootstrap.sh + db.py), sorted, idempotent.
- `gmail.send` already in DEFAULT_SCOPES; token at `~/.local/share/software-of-you/tokens/kmo_betterstory.co.json`.
- Detectors read: v_nudge_items (follow_up/commitment/task/cold_contact × urgent/soon/awareness),
  v_email_response_queue, v_discovery_candidates, v_meeting_prep.
- `get_valid_token(email)` in shared/google_auth.py refreshes + returns access token (urllib, no venv).

## Errors Encountered
| Error | Resolution |
|-------|------------|
| (none yet) | |
