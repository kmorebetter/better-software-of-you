---
title: Verify commitment completion before closing — evidence over assumption
date: 2026-06-23
category: best-practices
module: commitments
problem_type: best_practice
component: assistant
severity: high
related_components:
  - database
applies_when:
  - "asked to close, clean up, or triage overdue items that have no completion signal in the data"
  - "tempted to infer completion from the age or staleness of a commitment"
  - "a recurring topic in a later transcript could be mistaken for proof an item was done"
  - "a digitally-traceable action (email to send, meeting to book) can be checked against Gmail or Calendar"
  - "a keyword match across sources is ambiguous (same name, different referent)"
symptoms:
  - "open commitments exist with status never advanced past 'open' and follow-through stored NULL"
  - "no column or signal in the database indicates whether an overdue item was actually completed"
  - "pressure to bulk-mark old items 'done' to shrink an overdue count"
tags:
  - "data-integrity"
  - "no-fabrication"
  - "commitments"
  - "evidence-based"
  - "transcript-cross-reference"
  - "gmail-verification"
  - "overdue-triage"
---

# Verify commitment completion before closing — evidence over assumption

## Context

You're asked to triage a backlog of items whose status the system cannot directly verify — overdue commitments, open tasks, stale follow-ups — in a store that records *creation* but never records *completion*. In Software of You, commitments are extracted from Granola transcripts and imported `status='open'`; nothing in the pipeline ever flips one to done, and follow-through is stored `NULL`, not `0%`. So when the user asks "which of these 27 overdue commitments are still accurate?", the database alone cannot answer. There is no field that says "done."

This collides head-on with the project's hardest rule (CLAUDE.md → "Data Integrity: Never Fabricate"): **never fabricate any value; if you can't show how you got a number, don't store it; NULL over fiction.** The tempting shortcut — mark old overdue items "done" because they're weeks past deadline — manufactures a status the data doesn't support. That is fabrication, and it's the one thing this system can't afford.

A prior decision sets the stage (session history): when the bulk import surfaced 27 past-deadline items as overdue, an auto-hide fix was tried (migration `022` excluded any commitment whose deadline predated its own `created_at`, dropping the overdue count to 0) and then **deliberately reversed** at the user's direction — *"import the overdue items, we'll just need to go through them to see what's real and what's not."* The overdue feed is intentionally the live triage surface; the items are meant to be **shown and worked**, not hidden. This doc is the procedure for working them.

## Guidance

**Close only on evidence. The absence of evidence is not evidence of completion.** The conservative default — leave it open — is the *correct* default, because a false "done" is strictly worse than a lingering open item: a lingering open item costs a glance; a fabricated "done" silently drops a real obligation and poisons trust in every other status. Make the backlog look honest, not clean.

Work the backlog with three techniques, in this order:

**1. Cross-reference each stale item against later source records — skeptically.**
When the source data is recurring (weekly standups, repeating threads), search *later* records (Granola transcripts — the authoritative source; the built-in Gemini path is empty) for quotable evidence that the item was completed, continued, or superseded. The critical, counterintuitive rule:

> **A topic merely recurring in a later meeting is NOT proof it was completed — it often means the item is still open.**

Treat every keyword hit as a potential collision until you've read enough surrounding context to confirm it refers to *this* commitment and not a namesake. Offload this to a dedicated subagent and instruct it explicitly to be skeptical of keyword collisions and to return *quotable* evidence (the actual sentence), not a match count. Sort each item into **still-live** (quotable continuation), **done** (quotable completion), or **no evidence either way** — and leave the last bucket open.

**2. Verify digitally-traceable items against primary sources.**
If a commitment implies a digital artifact — an email that should have been sent, a call that should have been booked, an invite that should exist — go look for the artifact directly via the Gmail and Google Calendar MCP tools. This yields *hard* evidence: either the artifact exists (close it) or it doesn't (leave it open). It's the highest-confidence path; use it for any item that names a traceable action.

**3. Close only on evidence, and log the evidence in the same operation.**
When — and only when — you have quotable or primary-source proof, set `status='completed'`, `completed_at`, `updated_at`, **and** insert an `activity_log` row whose `details` field **quotes the specific evidence** (the calendar event date, the email subject and date, the verbatim transcript line). A closure without recorded evidence is indistinguishable from a guess. Everything not closed stays open/unknown — and it's fine, even expected, to hand 1–2 genuinely ambiguous items back to the user for a one-line confirmation rather than deciding for them.

## Why This Matters

This platform is only as trustworthy as its least-defensible number. A single fabricated "done" — even a plausible one — teaches the user that the status column can lie, and from then on they second-guess *every* status, every metric, every nudge. The whole value proposition (cross-referenced, trustworthy personal data) collapses. Conservative triage with a logged audit trail does the opposite: every closure is independently checkable, and the open items that remain are *honestly* open.

One downstream consequence to remember (session history): the `follow_through` figure in `relationship_scores` is a **persisted value, not a view-computed ratio**. Marking a commitment completed updates the source rows that the scoring write-path reads, but it does **not** recompute automatically. After a triage pass that closes items, recompute and re-store follow-through for the affected contacts — but only when enough data exists to derive it honestly (otherwise it stays `NULL`, never `0%`).

## When to Apply

Apply this whenever you're asked to **close, complete, or update the status of items in a store that has no direct completion signal** — and the only "evidence" on offer is age, plausibility, or assumption. Concretely:

- Triaging overdue or stale commitments, tasks, or follow-ups that were imported open and never closed.
- Any "clean up / archive / mark done what's no longer relevant" request over records the system didn't itself complete.
- Any time the shortcut is "it's old, so it's probably handled" — that's exactly the moment to switch to evidence-based triage.

Do **not** apply the heavyweight cross-referencing when a real completion signal already exists (a `completed_at` the user set, a synced "done" state from an integration). Use the signal. This method fills the gap *where no signal exists*; it doesn't override one that does.

## Examples

**Keyword-collision catches (why "be skeptical" is not abstract).** In the actual run, four plausible matches were correctly rejected after reading context:
- "**Sage**" matched website-launch *messaging*, not the Sage accounting tool the commitment was about.
- "**Jeffrey**" matched a newly-hired technician, not the procurement contact named in the task.
- "**Alicia / We Work**" matched a Vancouver expansion discussion, not the Amazon-badge task.
- "**Emma's plant list**" turned out to be a CPP install list, not the JLL RFP it superficially resembled.

Each of these, taken at face value, would have produced a false closure.

**Evidence-backed closures (what real proof looks like).** Three items were closed, each on hard primary-source evidence:
- An **SEO-workflow demo** — the session demonstrably occurred and its output was emailed (found in Gmail).
- A "**send the next invite**" task — the invite exists on Google Calendar.
- A "**book the follow-up call**" task — the call was created and held (calendar event).

**The asymmetry is the proof the method works.** Of 17 stale items cross-referenced: **3** had quotable continuation evidence (still-live), **0** could be confirmed done from transcripts, and **14** had no evidence either way and were left open. Net result across the backlog: **0 false closures; 3 evidence-backed closures with audit trail; open 99→96, overdue 27→24; 2 ambiguous items deliberately left open** for one-line user confirmation. A triage that closes almost nothing, but defensibly, is a success — not a failure.

**Anti-patterns — do not do these:**
- ❌ Marking old overdue items "done" because they're weeks past deadline. (Fabrication — age is not evidence.)
- ❌ Treating a topic reappearing in a later meeting as proof it was completed. (It frequently means the opposite — still open.)
- ❌ Closing an item without recording the evidence in `activity_log`. (No audit trail → the closure is untrustworthy and indistinguishable from a guess.)

**SQL — evidence-logged closure (the only correct way to close):**

```sql
-- Close ONLY the verified item.
UPDATE commitments
SET status       = 'completed',
    completed_at = datetime('now'),
    updated_at   = datetime('now')
WHERE id = 42;

-- Same operation: write the proof into the audit trail.
INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
VALUES (
  'commitment', 42, 'completed',
  'Closed on primary-source evidence: Google Calendar event "AI SEO Convo" held 2026-06-24; SEO output emailed (Gmail subject "Some SEO Findings for you", 2026-06-22).',
  datetime('now')
);
```

The `details` string is the heart of the pattern: it quotes the specific artifact (event title and date, email subject and date) so any later reader can re-verify the closure without trusting your judgment. If you can't write a sentence like that, you don't have grounds to close — leave it open.

## Related
- `CLAUDE.md` → "Data Integrity: Never Fabricate" (the governing principle: "NULL over fiction", "if you can't show how you got a number, don't store it").
- Auto memory `soy-ingest-data-integrity-rules` — direct precursor: follow-through stays NULL not 0%; pre-import overdue items are SHOWN and triaged manually (migration `022` auto-hide was reverted and deleted).
- Auto memory `soy-transcript-source-granola` — transcripts come from Granola via MCP; the built-in Gemini path is empty. Use Granola for the cross-reference step.
- `data/migrations/021_relationship_followthrough_inbound.sql` — header documents that imported commitments carry no completion signal (root-cause anchor).
- `data/migrations/014_computed_views.sql` — `v_commitment_status` and `v_nudge_items` are the read layer for the overdue triage surface (`days_overdue`, `urgency`, owner, source call).
- `data/migrations/001_core_schema.sql` — `activity_log` table (the evidence-logging target).
- Skills `/commitments` and `/nudges` — the user-facing surfaces this convention governs.
