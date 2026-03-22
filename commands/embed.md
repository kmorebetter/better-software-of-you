---
description: Set up, run, or check status of semantic search embeddings
allowed-tools: ["Bash", "Read", "Write"]
---

# Semantic Search Embeddings

Manage the embedding pipeline for semantic search. This is opt-in — SoY works fine without it. FTS5 keyword search is always available as the default.

## Determine Subcommand

Parse the user's input after `/embed`:
- `/embed setup` → Run Setup
- `/embed run` → Run Batch Embedding
- `/embed status` → Show Status
- `/embed` (no args) → Show status, suggest setup if not configured

## Setup

Interactive setup for the embedding provider.

1. **Check existing config:**
   ```sql
   SELECT key, value FROM soy_meta WHERE key LIKE 'embedding_%';
   ```
   If config exists, warn: "You already have embeddings configured ([provider], [model]). Switching providers will require re-embedding all records. Continue?"

2. **Ask provider choice:**
   - **Ollama** (local, free, private) — requires Ollama running locally
   - **OpenAI** (cloud, paid, fast) — requires API key

3. **If Ollama:**
   - Check if running: `curl -s http://localhost:11434/api/tags`
   - Check if model is pulled: look for `nomic-embed-text` in the response
   - If not pulled: `ollama pull nomic-embed-text`
   - Store config:
     ```sql
     INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES
       ('embedding_provider', 'ollama', datetime('now')),
       ('embedding_model', 'nomic-embed-text', datetime('now')),
       ('embedding_dimensions', '768', datetime('now')),
       ('embedding_endpoint', 'http://localhost:11434', datetime('now'));
     ```

4. **If OpenAI:**
   - Ask for API key
   - Store config:
     ```sql
     INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES
       ('embedding_provider', 'openai', datetime('now')),
       ('embedding_model', 'text-embedding-3-small', datetime('now')),
       ('embedding_dimensions', '1536', datetime('now')),
       ('embedding_endpoint', 'https://api.openai.com', datetime('now')),
       ('embedding_api_key', '<api_key>', datetime('now'));
     ```

5. **Create or recreate vec_embeddings table:**
   If switching providers (existing config with different dimensions), drop old tables first:
   ```sql
   DROP TABLE IF EXISTS vec_embeddings;
   DELETE FROM embeddings;
   ```

   Then create with correct dimensions:
   ```sql
   CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0(
       id INTEGER PRIMARY KEY,
       embedding float[<dimensions>]
   );
   ```
   Where `<dimensions>` is 768 (Ollama) or 1536 (OpenAI).

   **Note:** This requires `sqlite-vec` to be installed. If not available:
   ```
   pip install sqlite-vec
   ```

6. Confirm: "Semantic search configured with [provider] ([model], [dimensions]d). Run `/embed run` to index your existing records."

## Run Batch Embedding

Embed all records that don't have embeddings yet.

1. **Check config exists** in `soy_meta`. If not: "Run `/embed setup` first."

2. **For each entity type, find unembedded records:**

   | Entity Type | What to Embed | Source Table |
   |-------------|---------------|--------------|
   | contact | name + company + role + notes | contacts |
   | transcript | summary | transcripts |
   | email | subject + snippet | emails |
   | note | title + content | standalone_notes |
   | journal | content | journal_entries |
   | decision | title + context + decision | decisions |
   | inbox | content | inbox |

   Query pattern:
   ```sql
   SELECT id FROM <source_table>
   WHERE id NOT IN (SELECT entity_id FROM embeddings WHERE entity_type = '<type>');
   ```

3. **Batch process** 10 records at a time:
   - Generate embedding via configured provider (Ollama API or OpenAI API)
   - Compute SHA256 hash of the content being embedded
   - Insert into `embeddings` (metadata) and `vec_embeddings` (vector)
   - 100ms delay between batches (Ollama) or respect rate limits (OpenAI)

4. **Report:** "Embedded 45 new records (12 notes, 8 transcripts, 25 emails). 340 total."

## Status

Show the current state of the embedding pipeline.

```sql
-- Provider config
SELECT key, value FROM soy_meta WHERE key LIKE 'embedding_%' AND key != 'embedding_api_key';

-- Embedding counts by type
SELECT entity_type, COUNT(*) as embedded FROM embeddings GROUP BY entity_type;

-- Total vs pending
SELECT
  (SELECT COUNT(*) FROM embeddings) as total_embedded,
  (SELECT COUNT(*) FROM contacts WHERE status = 'active') +
  (SELECT COUNT(*) FROM transcripts) +
  (SELECT COUNT(*) FROM emails) +
  (SELECT COUNT(*) FROM standalone_notes) +
  (SELECT COUNT(*) FROM journal_entries) +
  (SELECT COUNT(*) FROM decisions) +
  (SELECT COUNT(*) FROM inbox WHERE routed_to IS NULL OR routed_to != 'dismissed')
  as total_records;
```

Present as a clean summary:
```
Semantic Search Status
Provider: Ollama (nomic-embed-text, 768d)
Embedded: 340 / 892 records (38%)
  contacts: 21, transcripts: 16, emails: 280, notes: 4, journal: 10, decisions: 5, inbox: 4
Pending: 552 records — run /embed run to index them
```

If not configured: "Semantic search not set up. Run `/embed setup` to get started. Note: FTS5 keyword search is always available via `/search`."
