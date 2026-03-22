"""Semantic search across all modules via sqlite-vec embeddings."""

import json
from mcp.server.fastmcp import FastMCP
from software_of_you.db import execute, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def semantic_search(
        query: str,
        entity_types: str = "",
        limit: int = 10,
    ) -> dict:
        """Search by meaning across all modules using embeddings.

        Requires embeddings to be configured (run /embed setup first).
        Falls back to keyword search if embeddings aren't enabled.

        Args:
            query: Natural language search query
            entity_types: Comma-separated filter (e.g., 'transcript,note'). Empty = all.
            limit: Max results (default 10)
        """
        if not query:
            return {"error": "A search query is required."}

        # Check if embeddings are configured
        config_rows = execute(
            "SELECT key, value FROM soy_meta WHERE key LIKE 'embedding_%'"
        )
        config = {r["key"]: r["value"] for r in config_rows}

        if not config.get("embedding_provider"):
            return {
                "result": [],
                "search_mode": "unavailable",
                "note": "Semantic search not configured. Run /embed setup to enable. Using keyword search for now.",
                "_context": {
                    "presentation": "Let the user know semantic search isn't set up. Suggest /embed setup. Fall back to the regular search tool."
                },
            }

        provider = config["embedding_provider"]
        model = config.get("embedding_model", "nomic-embed-text")
        endpoint = config.get("embedding_endpoint", "http://localhost:11434")

        try:
            import httpx
            import sqlite_vec  # noqa: F401 — needed to load the extension

            embedding = _get_embedding(query, provider, model, endpoint, config)
            if embedding is None:
                return {"error": "Failed to generate embedding for query. Is the embedding provider running?"}

            embedding_json = json.dumps(embedding)

            # Build query with optional type filter
            if entity_types:
                types = [t.strip() for t in entity_types.split(",") if t.strip()]
                placeholders = ",".join("?" * len(types))
                sql = f"""
                    SELECT e.entity_type, e.entity_id, v.distance
                    FROM vec_embeddings v
                    JOIN embeddings e ON e.id = v.id
                    WHERE v.embedding MATCH ?
                      AND e.entity_type IN ({placeholders})
                    ORDER BY v.distance
                    LIMIT ?
                """
                params = (embedding_json, *types, limit)
            else:
                sql = """
                    SELECT e.entity_type, e.entity_id, v.distance
                    FROM vec_embeddings v
                    JOIN embeddings e ON e.id = v.id
                    WHERE v.embedding MATCH ?
                    ORDER BY v.distance
                    LIMIT ?
                """
                params = (embedding_json, limit)

            rows = execute(sql, params)
            results = _fetch_entities(rows_to_dicts(rows))

            return {
                "result": results,
                "total_matches": len(results),
                "query": query,
                "search_mode": "semantic",
            }

        except ImportError:
            return {
                "error": "sqlite-vec not installed. Run: pip install 'software-of-you[embeddings]'",
            }
        except Exception as ex:
            return {"error": f"Semantic search failed: {ex}"}


def _get_embedding(text: str, provider: str, model: str, endpoint: str, config: dict) -> list[float] | None:
    """Get embedding vector from configured provider."""
    import httpx

    if provider == "ollama":
        resp = httpx.post(
            f"{endpoint}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=30.0,
        )
        if resp.status_code == 200:
            return resp.json().get("embedding")
    elif provider == "openai":
        api_key_rows = execute("SELECT value FROM soy_meta WHERE key = 'embedding_api_key'")
        if not api_key_rows:
            return None
        resp = httpx.post(
            f"{endpoint}/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key_rows[0]['value']}"},
            json={"model": model, "input": text},
            timeout=30.0,
        )
        if resp.status_code == 200:
            return resp.json()["data"][0]["embedding"]
    return None


def _fetch_entities(matches: list[dict]) -> list[dict]:
    """Fetch actual content for matched entities."""
    entity_queries = {
        "contact": "SELECT id, name, company, role FROM contacts WHERE id = ?",
        "transcript": "SELECT id, title, summary FROM transcripts WHERE id = ?",
        "email": "SELECT id, subject, from_name, snippet FROM emails WHERE id = ?",
        "note": "SELECT id, title, substr(content, 1, 150) as preview FROM standalone_notes WHERE id = ?",
        "journal": "SELECT id, entry_date, substr(content, 1, 150) as preview FROM journal_entries WHERE id = ?",
        "decision": "SELECT id, title, status FROM decisions WHERE id = ?",
        "inbox": "SELECT id, substr(content, 1, 150) as preview FROM inbox WHERE id = ?",
    }
    results = []
    for match in matches:
        etype = match["entity_type"]
        eid = match["entity_id"]
        query = entity_queries.get(etype)
        if query:
            rows = execute(query, (eid,))
            if rows:
                entity = rows_to_dicts(rows)[0]
                entity["_type"] = etype
                entity["_distance"] = match.get("distance")
                results.append(entity)
    return results
