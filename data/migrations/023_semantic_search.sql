-- Semantic Search (Optional)
-- Metadata table for tracking which entities have been embedded.
-- The vec_embeddings virtual table is created by /embed setup
-- since its dimension depends on the configured provider
-- (768 for Ollama nomic-embed-text, 1536 for OpenAI).

CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,       -- 'contact', 'note', 'transcript', 'decision', 'journal', 'email', 'inbox'
    entity_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,      -- SHA256 of embedded content (skip re-embedding unchanged content)
    embedded_at TEXT DEFAULT (datetime('now')),
    UNIQUE(entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_embeddings_type ON embeddings(entity_type);
