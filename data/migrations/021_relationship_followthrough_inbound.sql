-- 021_relationship_followthrough_inbound.sql
--
-- Adds the inbound direction of commitment follow-through and clears the stale
-- outbound values that the old (broken) formula produced.
--
-- Background: commitment_follow_through is NOT a SQL-view computation. v_contact_health
-- only READS the latest STORED relationship_scores.commitment_follow_through
-- (ORDER BY score_date DESC LIMIT 1). The value is derived by Claude per
-- skills/conversation-intelligence/references/scoring-methodology.md and written by
-- transcripts.py _add_analysis. The old formula divided by an 'overdue' status that
-- NO code ever writes, so stored values were bimodal (1.0 or NULL) — wrong — and they
-- gate relationship_depth/sentiment.
--
-- ALTER stays FIRST: with the migration ledger this file runs exactly once, but even
-- outside the ledger a re-run hits "duplicate column" on the ALTER and the runner
-- skips the rest of the file (belt-and-suspenders). This file defines NO views.

-- 1. Inbound direction (contact -> user). New column defaults to NULL, so no backfill
--    is needed for it; it populates on the next analysis run.
ALTER TABLE relationship_scores ADD COLUMN commitment_follow_through_inbound REAL;

-- 2. Backfill: NULL the stale outbound values computed by the old broken formula.
--    They re-derive on the next analysis via the corrected formula; until then the
--    read path displays "—" instead of surfacing a skewed number as fact.
UPDATE relationship_scores SET commitment_follow_through = NULL;
