---
title: Deterministic rendering with cached judgment — spend the model only where data changed
date: 2026-07-17
category: architecture-patterns
module: view-rendering
problem_type: architecture_pattern
component: service_object
severity: medium
applies_when:
  - Generating many similar artifacts (HTML pages, docs, reports) where most of each is structural
  - Model generation is the slow/expensive step and a full rebuild is currently cost-prohibitive
  - Only a few parts of each artifact genuinely need model judgment (prose, synthesis, narrative)
  - Renaming or adding one entity currently forces regenerating everything
tags: [deterministic-rendering, templating, jinja, code-vs-model, data-fingerprint, caching, cost-reduction, no-fabrication]
---

# Deterministic rendering with cached judgment — spend the model only where data changed

## Context

A system was generating ~59 HTML pages by having the model write each page token-by-token — including
the identical sidebar/CSS baked into every file. A full rebuild cost ~40 model runs, and renaming one
entity invalidated the whole site. The insight: **almost none of a page needs a model.** Structure,
layout, counts, tables, and navigation are deterministic functions of the data; only a handful of
fields (a relationship narrative, a synthesized summary) require judgment. Letting the model author
structure is the expensive mistake.

Extracted from porting a project's HTML generation to `scripts/render.py` (a deterministic Jinja
renderer) plus an `entity_narratives` cache.

## Guidance

Split every artifact into two layers and treat them completely differently:

1. **Structure → deterministic code.** Render the shell, layout, tables, stats, navigation, and every
   value that traces to the data using a template engine fed by queries (ideally pre-computed views).
   No model. A full rebuild is then a script call measured in seconds, and every number is auditable
   (NULL renders as "—", never a guess).

2. **Judgment → model, cached and fingerprinted.** The few genuinely model-authored fields
   (narrative, synthesis) are written once and **stored**, keyed to the entity. Store a
   `data_fingerprint` — a hash of the entity's underlying data state — alongside the cached prose. On
   rebuild, the renderer slots the cached prose in for free; the model is re-invoked for an entity
   **only when its fingerprint changed** (its data actually moved).

3. **One component owns the fingerprint.** The routine that saves model output also computes and stores
   the fingerprint, using the *same* function the staleness check uses. Callers (the model) supply only
   prose; they never compute or guess freshness. This keeps "is it stale?" and "mark it fresh" in
   perfect agreement.

4. **Freeze identity so rebuilds are safe.** Derive each artifact's filename/id from a slug frozen at
   creation, not recomputed from a mutable name — so a rename never orphans a file or its inbound links,
   and regenerating the world is idempotent.

5. **Escape at the boundary; keep one trusted channel.** With autoescape on, only a single explicit
   raw-HTML channel exists, and any data spliced into it is escaped first. Deterministic rendering makes
   this enforceable in one place instead of per-page.

## Why This Matters

- **Cost collapses.** Full-site rebuild went from ~40 model runs to one ~1.5s script call; the model is
  spent only on entities whose data changed since last time.
- **Correctness improves.** Numbers come from queries, not generation, so fabrication is structurally
  impossible for the deterministic layer. The model's surface area shrinks to prose, where its
  strengths actually lie.
- **Rebuilds become free and safe.** "Regenerate everything" stops being a scary, expensive operation,
  so freshness stops drifting. Frozen slugs remove the rename-cascade fragility.
- **The template lives once.** No more N copies of the sidebar/CSS drifting apart across generated files.

## When to Apply

- Dashboards, entity pages, catalogs, report suites — anything with a repeated shell and per-item data.
- Any pipeline where "have the model write the page" is the current approach and rebuilds are rationed
  because of it.

Do **not** force this when each artifact is genuinely bespoke prose end-to-end (a one-off essay), or
when there is no deterministic structure to extract — the split only pays off when structure dominates.

## Examples

**Deterministic builder from a computed view** (no model in the loop):

```python
rows = rows_to_dicts(execute("""
    SELECT id, name, company, days_silent, relationship_depth, next_meeting
    FROM v_contact_health WHERE status='active' ORDER BY days_silent DESC"""))
# → assemble a table section → render Jinja template → write file → register. Milliseconds.
```

**Fingerprint owned by the save path, matching the staleness check:**

```python
def _fingerprint(row):                      # same function both sides use
    payload = (row["emails_total"], row["interactions_total"],
               row["transcripts_total"], row["last_activity"])
    return hashlib.sha1(repr(payload).encode()).hexdigest()[:16]

# save-narrative: store prose + _current_fingerprint(cid); re-render that one page.
# stale check: recompute fingerprint; stale iff (no row) or (stored != current).
```

**The staleness contract in practice:**

```
render.py all                # rebuild ALL structure deterministically (seconds)
render.py stale-narratives   # → the few entities whose data changed → model writes prose for those only
echo '{...}' | render.py save-narrative   # model supplies prose; renderer owns the fingerprint + re-renders
```

**Before / after:** before, a contact rename meant regenerating ~59 model-authored pages; after, it's
one deterministic pass with a frozen slug, and the model runs for zero contacts unless their data moved.

## Related

- `docs/solutions/architecture-patterns/signals-engine-proactive-surfacing.md` — the same
  "deterministic core, model only for judgment" split applied to proactive surfacing.
- `docs/solutions/best-practices/verify-scheduled-jobs-fire-and-bound-headless.md` — when the model
  step runs on a schedule, bound it so it can't block the deterministic output.
