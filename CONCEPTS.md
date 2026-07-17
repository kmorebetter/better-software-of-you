# Concepts

Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

## Signals

### Signal
A single thing worth the user's attention — an overdue commitment, a cooling relationship, an unanswered message — that has been detected from the user's own data, scored for priority, and deduplicated so a recurring condition is one persistent item rather than a repeated alert.

A Signal has a lifecycle: it appears as new, becomes surfaced once shown to the user, and resolves automatically when the underlying condition clears (the message is answered, the commitment closed). A user may also dismiss it or snooze it. Only the highest-scoring few are pushed to the user at any time; the rest stay available on demand rather than crowding the channel. Every Signal keeps a reference to the source data that produced it, so it is auditable and never fabricated.

### Signals Engine
The subsystem that produces Signals: it detects candidates deterministically from the user's data, scores them by urgency, importance, and novelty, maintains their lifecycle in a persistent ledger, and delivers only the top few through the daily brief and the in-session summary. It is what decides, and paces, what the system proactively tells the user.

## Rendering & data

### Computed View
A pre-computed, read-only database view that performs the platform's deterministic calculations — counts, days-elapsed, urgency tiers, relationship and project health rollups — so a figure is derived once and simply read everywhere else. Display and narrative layers read a Computed View's columns directly rather than re-deriving the numbers, which keeps every figure auditable and consistent.

### Entity Narrative
The cached, model-authored prose about a contact — relationship context, background, suggested questions, next action — stored apart from the deterministic page structure. An Entity Narrative is rewritten only when the contact's underlying data has changed since it was last generated, so model effort goes to judgment rather than to structure.
