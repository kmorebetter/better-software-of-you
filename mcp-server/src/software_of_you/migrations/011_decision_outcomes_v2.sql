-- Decision Outcomes v2 — Grounded outcome tracking
-- Adds process/outcome quality separation (Annie Duke's "Resulting" framework)
-- A good decision process can produce a bad outcome (bad luck) and vice versa.
-- Conflating them is "resulting" — judging the process by the result.
--
-- All ALTER TABLE statements are idempotent: bootstrap runs with 2>/dev/null,
-- so "duplicate column" errors are silently ignored on re-runs.

-- How certain were you when you made this decision? (1=very uncertain, 10=very certain)
ALTER TABLE decisions ADD COLUMN confidence_level INTEGER CHECK (confidence_level BETWEEN 1 AND 10);

-- Scheduled review dates — set automatically at decision log time
-- These drive nudges; they're milestones, not deadlines.
ALTER TABLE decisions ADD COLUMN review_30_date TEXT;   -- 30-day check-in: early signals
ALTER TABLE decisions ADD COLUMN review_90_date TEXT;   -- 90-day review: assess the outcome
ALTER TABLE decisions ADD COLUMN review_180_date TEXT;  -- 180-day review: full retrospective

-- Process quality: was your DECISION PROCESS sound?
-- Did you consider the right options? Did you have enough information?
-- Rated at outcome review time, NOT at decision time.
-- 1=poor process, 5=excellent process
-- This is independent of whether the outcome was good or bad.
ALTER TABLE decisions ADD COLUMN process_quality INTEGER CHECK (process_quality BETWEEN 1 AND 5);

-- Outcome quality: how did it actually turn out?
-- Rated at outcome review time.
-- 1=very bad outcome, 5=very good outcome
-- This is independent of whether the process was good or bad.
ALTER TABLE decisions ADD COLUMN outcome_quality INTEGER CHECK (outcome_quality BETWEEN 1 AND 5);

-- What was within your control? (structured reflection, filled at review time)
ALTER TABLE decisions ADD COLUMN within_control TEXT;

-- What was outside your control? (external factors that affected the outcome)
ALTER TABLE decisions ADD COLUMN external_factors TEXT;

-- What would you do differently about the PROCESS next time?
-- (Not "what would you do to get a better outcome" — that's hindsight bias)
ALTER TABLE decisions ADD COLUMN would_do_differently TEXT;
