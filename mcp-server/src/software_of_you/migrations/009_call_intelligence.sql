-- Call Intelligence: structured JSON for pain points, tech stack, concerns, org intel.
-- Stored alongside the narrative summary (which stays plain text).
-- ALTER TABLE will fail silently on re-run (column already exists) — bootstrap swallows stderr.

ALTER TABLE transcripts ADD COLUMN call_intelligence TEXT;
