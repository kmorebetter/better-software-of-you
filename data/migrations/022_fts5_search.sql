-- FTS5 Full-Text Search
-- Porter stemmer handles word variants: "hiring" → "hire", "scaling" → "scale".
-- Ships with SQLite — zero new dependencies.
-- Rebuilds on every bootstrap (DELETE + re-INSERT). Fast at current scale.

-- FTS5 virtual table covering all searchable content
CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
    entity_type,
    entity_id UNINDEXED,
    title,
    content,
    tokenize='porter unicode61'
);

-- Rebuild index from all source tables
-- Safe to re-run: DELETE + INSERT is idempotent
DELETE FROM search_fts;

-- Contacts
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'contact', id, name, COALESCE(company, '') || ' ' || COALESCE(role, '') || ' ' || COALESCE(notes, '')
FROM contacts WHERE status = 'active';

-- Standalone notes
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'note', id, COALESCE(title, ''), content
FROM standalone_notes;

-- Journal entries
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'journal', id, entry_date, content
FROM journal_entries;

-- Decisions
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'decision', id, title, COALESCE(context, '') || ' ' || COALESCE(decision, '')
FROM decisions;

-- Transcripts (summary, not raw_text — more semantically dense)
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'transcript', id, COALESCE(title, ''), COALESCE(summary, '')
FROM transcripts;

-- Emails (subject + snippet, not full body)
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'email', id, COALESCE(subject, ''), COALESCE(snippet, '')
FROM emails;

-- Inbox items (not dismissed)
INSERT INTO search_fts (entity_type, entity_id, title, content)
SELECT 'inbox', id, '', content
FROM inbox WHERE routed_to IS NULL OR routed_to != 'dismissed';
