---
title: Signals Engine — a restraint-first pattern for proactively surfacing what a user should know
date: 2026-07-17
category: architecture-patterns
module: signals-engine
problem_type: architecture_pattern
component: background_job
severity: medium
applies_when:
  - Building a proactive feature that surfaces items to a user without being asked (briefings, nudges, notifications, digests)
  - A system already computes candidate "things worth attention" but risks overwhelming the user with all of them
  - You need surfaced items to persist state across runs (already-seen, acted, dismissed, snoozed) rather than re-alerting each cycle
  - Deterministic detection must be paired with model-written prose without letting the model invent facts
tags: [proactive-surfacing, notifications, signals, restraint, state-ledger, deduplication, attention-inbox, no-fabrication]
---

# Signals Engine — a restraint-first pattern for proactively surfacing what a user should know

## Context

Turning a passive data store into a partner that "speaks first" is mostly a relevance-and-restraint
problem, not a detection problem. The naive version — run some queries on a schedule and show the
results — fails in two predictable ways: it floods the user (a feed that pings 20×/day gets muted),
and it has no memory (the same overdue item re-alerts every run, and there's no notion of "you already
told me that / I already handled it"). Detection is the easy 20%; the durable value is in scoring,
restraint, and state.

This pattern was extracted from building the "Signals Engine" for a local personal-data platform
(`scripts/signals.py` + migration `022_signals.sql`), where candidate signals derive from pre-computed
SQL views and are surfaced via a morning brief, an email, and an in-session summary.

## Guidance

Model the feature as an **attention inbox** the *system* writes to, with a fixed pipeline:

```
detect (deterministic) → score → state-ledger / dedup → restraint threshold → synthesize (model) → deliver → feedback
```

1. **Detect deterministically, and carry the evidence.** Candidate signals come only from queries/views
   over real data. Each candidate stores a `source_ref` (the rows/ids that produced it) so nothing is
   invented and every surfaced item is auditable.

2. **Score = urgency × importance × novelty** (a tunable weighted blend, all in `[0,1]`). Keep it
   deterministic so ranking is explainable:
   - *urgency* — time-decay (overdue days, minutes-until-meeting, tier).
   - *importance* — who/what it concerns (client vs. not, relationship depth, project value).
   - *novelty* — new vs. already-surfaced; decays as `surfaced_count` rises so unacted repeats fade.

3. **Keep a state ledger keyed by a stable `signal_key` — this is the differentiator.** A recurring
   condition (the same overdue commitment) **updates one row** instead of creating a new alert each run.
   The ledger tracks `status ∈ {new, surfaced, acted, dismissed, snoozed, resolved}`, `first_seen`,
   `last_surfaced`, `surfaced_count`, and `snooze_until`.

4. **Auto-resolve on absence.** When a previously-active signal is no longer detected, the underlying
   condition cleared (you replied, closed the commitment) → mark it `resolved`. This is implicit
   positive feedback and needs no explicit user action.

5. **Restraint over recall.** Only the top *N* (≈3–5) cross the push threshold into the brief;
   everything else stays pull-based (dashboard/feed). The push channel is sacred — protect it.

6. **Synthesize with the model, deliver deterministically.** The model turns the top scored signals
   into short grounded prose ("You promised X the SOW Monday; it's 3 days late and they emailed
   yesterday"), never a raw row dump — but the *floor* (a deterministic list) is what guarantees
   delivery even if the model step is unavailable.

7. **Filter automation/noise at the source.** One burst of bot/notification mail can dominate a naive
   feed. Drop obvious automation and penalize unknown senders so real people always outrank role
   addresses.

## Why This Matters

- **Trust is destroyed by noise, not by missing one item.** Surfacing 3 right things beats surfacing
  20 possibly-relevant ones. Restraint is the feature.
- **State/memory is what separates a partner from a cron job.** Without a dedup ledger you cannot do
  novelty, cannot avoid repetition, and cannot learn what the user ignores. The `signal_key` +
  `surfaced_count` + `status` machinery is the whole point, not an add-on.
- **Determinism keeps it honest and cheap.** Detection and scoring in SQL/code means every number is
  auditable (no fabrication) and the model is only spent on the few items that survive restraint.
- **A deterministic floor guarantees delivery.** Pairing a guaranteed deterministic brief with optional
  model enrichment means an unavailable/hung model never results in *nothing* being delivered.

## When to Apply

- Any "morning brief", digest, nudge feed, or notification system where the system decides what to
  surface.
- When the same candidates recur across runs and you need "already told you / already handled" memory.
- When deterministic detectors exist (or can be written as views) and a model is used only for phrasing.

Do **not** reach for the full ledger when the feed is genuinely stateless and one-shot (a live search
result), or when every candidate must always be shown (a legal/compliance list where restraint is wrong).

## Examples

**State ledger keyed by a stable signal_key** (migration `022_signals.sql`, trimmed):

```sql
CREATE TABLE IF NOT EXISTS signals (
    signal_key      TEXT NOT NULL UNIQUE,   -- "<type>:<entity_id>[:<sub>]" — recurrence updates one row
    signal_type     TEXT NOT NULL,
    source_ref      TEXT,                   -- JSON: rows/ids that produced it (integrity trail)
    urgency REAL, importance REAL, novelty REAL, score REAL,
    status          TEXT NOT NULL DEFAULT 'new',  -- new|surfaced|acted|dismissed|snoozed|resolved
    first_seen TEXT, last_surfaced TEXT, surfaced_count INTEGER NOT NULL DEFAULT 0,
    snooze_until TEXT
);
```

**Novelty decay + weighted score** (deterministic, tunable):

```python
def _novelty(surfaced_count):            # unacted repeats slowly fade
    return max(0.3, 1.0 - 0.15 * (surfaced_count or 0))

def _score(urgency, importance, novelty):
    return 0.5*urgency + 0.3*importance + 0.2*novelty
```

**Upsert dedup + auto-resolve** (the heart of the memory):

```python
detected = set()
for c in candidates:                     # each carries source_ref
    detected.add(c["signal_key"])
    # existing key → UPDATE (recompute novelty from surfaced_count); else INSERT as 'new'
# anything active but no longer detected → the condition cleared:
#   UPDATE signals SET status='resolved' WHERE status IN ('new','surfaced') AND signal_key NOT IN detected
```

**Restraint on delivery** — the brief pulls only the top few and marks them surfaced:

```
signals.py top --n 5 --surface     # push channel: top 5 only, increments surfaced_count
signals.py summary                 # in-session: read-only one-liner, no state change
```

**Before / after:** a first cut ranked four `vercel[bot]` PR-notification emails as the top "unanswered"
items. Adding a source-level automation filter (drop `[bot]` / `noreply` / `notifications@`, penalize
unlinked senders) moved a real 16-day-overdue commitment back to the top — the same detectors, made
useful purely by restraint.

## Related

- `docs/solutions/architecture-patterns/deterministic-render-cached-judgment.md` — the same
  "deterministic core, model only for judgment" split applied to view generation: compute
  deterministically, spend the model only where phrasing/judgment is required, and cache its output
  keyed by a data fingerprint so it re-runs only on change.
- `docs/solutions/best-practices/verify-scheduled-jobs-fire-and-bound-headless.md` — delivery
  hardening: the scheduled model step must be time-bounded and swapped in only on success, so it can
  never block or corrupt the deterministic floor.
