-- 023_entity_narratives.sql — stored per-contact narrative + stable slugs
--
-- Enables the deterministic renderer (scripts/render.py) to rebuild the whole
-- interface without Claude: structural pages come from the computed views, and
-- the ONLY model-authored parts of an entity page (relationship prose, company
-- intel, discovery questions, next action) are cached here. Claude rewrites a
-- narrative only when that contact's underlying data has changed since
-- generated_at (compared via data_fingerprint) — so tokens are spent only where
-- judgment actually changed, not on every rebuild.
--
-- Also adds contacts.slug: a slug FROZEN at first render so renaming a contact
-- never orphans contact-<oldslug>.html or the inbound links pointing at it.
--
-- ALTER stays FIRST (belt-and-suspenders: on a bare re-run outside the migration
-- ledger it raises "duplicate column" and the runner skips the rest of the file).

ALTER TABLE contacts ADD COLUMN slug TEXT;

CREATE TABLE IF NOT EXISTS entity_narratives (
    contact_id            INTEGER PRIMARY KEY REFERENCES contacts(id) ON DELETE CASCADE,
    relationship_context  TEXT,
    company_intel         TEXT,
    discovery_questions   TEXT,   -- JSON array of question strings
    next_action           TEXT,
    generated_at          TEXT,
    data_fingerprint      TEXT,   -- hash of the contact's source-data state at generation time
    updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_contacts_slug ON contacts(slug);
