# Findings & Decisions

## Requirements
- A reusable `/morning` command: fresh pull of Gmail/Calendar/transcripts, then regenerate any dashboards required, then a today briefing.
- Run it once now. First-ever HTML build → full backfill of all 16 contact briefs + dashboard set (user chose "Everything now").

## Research Findings (how the plugin works)
- **Commands** = markdown in `commands/`, auto-discovered. Frontmatter: `description`, `allowed-tools`, optional `argument-hint`.
- **Fresh pull** = `bash shared/scheduled_sync.sh` → MCP venv (`mcp-server/.venv/bin/python3`, py3.14) → `sync_all_accounts()` (Gmail + Calendar + transcripts per active account). Logs to `~/.local/share/software-of-you/logs/sync.log`. Updates `google_accounts.last_synced_at` but NOT `soy_meta` keys → morning must stamp `gmail_last_synced` / `calendar_last_synced` / `transcripts_last_scanned`.
- **Dashboards** = `commands/build-all.md` orchestrator: incremental staleness, auto-creates pages for new contacts/projects, always-rebuilds `dashboard.html`/`nudges.html`/`timeline.html`/`weekly-review.html`/`search.html`. Output → `output/` (symlinked to `~/.local/share/software-of-you/output/`).
- **Build order matters**: transcript pages → entity pages → project pages → contacts index → module views → network-map → cross-cutting → dashboard LAST (so links resolve).
- **Computed views** for briefing (narrate, never compute): `v_meeting_prep`, `v_nudge_summary`/`v_nudge_items`, `v_commitment_status`, `v_email_response_queue`, `v_contact_health`.
- **Pending transcripts** = `python3 shared/sync_transcripts.py pending` → `source='gemini' AND processed_at IS NULL`.

## State at start of live run
- DB: 16 active contacts, 10 modules, 0 active/planning projects, 0 transcripts.
- `generated_views` EMPTY; `output/` had only stray `contact-cards.html` + `open-externally-test.html`.
- Last sync was 2026-06-23 (4 days stale at run time).

## Live sync result (this run)
- kmo@betterstory.co: gmail synced 50 (50 checked), calendar 34 events, transcripts 0. 0 pending transcripts.

## CRITICAL DATA-SHAPE DISCOVERY (changes backfill plan)
- DB actually has 250 emails, 77 calendar events (30d), 15 transcripts — NOT thin. But contact-linkage is sparse:
  - Greg Girton (id1): 4 emails, 3 transcripts. MK Marsden (id2): 2 tx. Cain Ullah(3)/Jeff Elliott(4)/Alex Somerville(5): 1 tx each.
  - **11 of 16 contacts have ZERO linked emails/calendar/transcripts** → their entity pages would be empty-state stubs.
- Most of the 250 emails / 77 events are unlinked to CRM contacts → the value lives in aggregate views (email-hub, week-view, conversations) + a handful of entity pages, NOT 16 rich briefs.
- Earlier "0 transcripts" reading was a query error (`analyzed_at` column doesn't exist); real count is 15.
- `commitments` has `owner_contact_id` (not `contact_id`).
- Build-all also produces 1 transcript-detail page per analyzed transcript (15) → full backfill ≈ 40 pages, not 25.
- Design refs present: skills/dashboard-generation/references/ (entity-page-reference.html, template-base.html, *-patterns.md).

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Delegate dashboards to build-all | Avoid logic drift between `/morning` and `/build-all` |
| Stamp soy_meta in morning.md | scheduled_sync.sh doesn't; downstream auto-sync reads these keys |
| Parallelize 16 entity pages via subagents | Independent files; heavy synthesis per contact |
| Sparse pages for thin contacts are correct | No-fabrication rule; only email/calendar data exists |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| scheduled_sync.sh printed nothing to stdout | Result is logged to sync.log, not echoed; confirmed success there |
| `v_contact_health` keyed by column `id`, not `contact_id` | Subagents corrected join after PRAGMA |
| `commitments` uses `owner_contact_id` (no `contact_id`) | Used correct column |
| transcript `conversation_metrics` rows have NULL contact_id → cartesian join in spec | Subagents dedupe to real speaker tracks + flag speaker assignment as explicit inference |

## Latent bugs found in existing command files (NOT fixed — out of scope; worth a follow-up)
- `commands/contacts.md` & dashboard "going_cold": `id NOT IN (SELECT contact_id FROM emails ...)` is poisoned by 246 emails with NULL contact_id → returns 0. Null-safe count = 11 cold contacts. Subagents shipped 11.
- `commands/week-view.md`: `date(start_time)` converts the -06:00 offset to UTC → Friday 6pm events shift to Saturday. Meeting-hours formula `SUM(CAST(...*24 AS INTEGER))` truncates per-event → wrong total (showed 8 vs real 19.6h). Subagents used local-date + correct sum.
- Email data shape: 246/250 emails have NULL contact_id (GitHub/vercel bot PR notifications, Stripe) → only Greg Girton links from email-hub; response queue is mostly bot PRs.

## Latent bugs found during 2026-06-29 morning re-run (NOT fixed — follow-up)
- `commands/week-view.md` **Monday boundary bug**: on a Monday the week-window SQL spans 14 days (e.g. Jun 22–Jul 5) instead of the true current week. Subagent corrected to Jun 29–Jul 5 for the render.
- **Duplicate calendar rows from double-sync**: event pairs with near-identical fields but different ids (91/159, 54/55, 101/167) — sync upsert isn't deduping by external event id. Subagent deduped in-view; root cause is in the sync/upsert path.
- `commands/email-hub.md` **"Needs Response" = notification wall**: query flags ~121 inbound threads as needing a reply because only 2 outbound emails exist to match against, and nearly all inbound is automated (GitHub/Vercel/Stripe). The reply queue needs a sender-type / automated-sender filter to be useful.
- Data freshness mechanics confirmed: a forced re-sync re-checks the latest 50 messages but does NOT re-stamp `emails.synced_at` for already-stored rows, and brand-new emails land with NULL contact_id → no existing entity page goes stale on a routine pull. Only aggregate + always-rebuild views need regeneration. (Good: keeps `/morning` cheap.)

## Resources
- `commands/morning.md`, `commands/build-all.md`, `commands/help-soy.md`
- `shared/scheduled_sync.sh`, `shared/sync_transcripts.py`, `shared/bootstrap.sh`
- `mcp-server/src/software_of_you/google_sync.py` (`sync_all_accounts`)
