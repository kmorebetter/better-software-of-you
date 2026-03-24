use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

pub fn definition() -> Value {
    json!({
        "name": "search",
        "description": "Full-text search across contacts, emails, notes, transcripts, and interactions. Uses FTS5 when available, falls back to LIKE queries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "module": {
                    "type": "string",
                    "description": "Optional: limit search to a specific module (contacts, emails, notes, transcripts)"
                }
            },
            "required": ["query"]
        }
    })
}

pub fn execute(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let query = args["query"].as_str().ok_or("Missing query")?;
    let module_filter = args["module"].as_str();

    // Try FTS5 first
    let fts_result = db.query_json(
        "SELECT entity_type, entity_id, title, snippet(search_fts, 3, '<mark>', '</mark>', '...', 30) AS snippet, rank
         FROM search_fts WHERE search_fts MATCH ?1 ORDER BY rank LIMIT 20",
        &[&query],
    );

    match fts_result {
        Ok(Value::Array(ref rows)) if !rows.is_empty() => {
            let filtered = if let Some(module) = module_filter {
                let filtered_rows: Vec<Value> = rows.iter()
                    .filter(|r| r["entity_type"].as_str() == Some(module))
                    .cloned()
                    .collect();
                Value::Array(filtered_rows)
            } else {
                Value::Array(rows.clone())
            };

            let count = if let Value::Array(ref r) = filtered { r.len() } else { 0 };
            return Ok(json!({
                "results": filtered,
                "count": count,
                "query": query,
                "search_method": "fts5"
            }));
        }
        _ => {
            // FTS5 unavailable or no results — fall back to LIKE queries
            fallback_search(db, query, module_filter)
        }
    }
}

fn fallback_search(db: &Arc<Database>, query: &str, module_filter: Option<&str>) -> Result<Value, String> {
    let pattern = format!("%{}%", query);
    let mut results: Vec<Value> = Vec::new();

    let search_contacts = module_filter.map_or(true, |m| m == "contacts");
    let search_emails = module_filter.map_or(true, |m| m == "emails");
    let search_notes = module_filter.map_or(true, |m| m == "notes");
    let search_transcripts = module_filter.map_or(true, |m| m == "transcripts");

    if search_contacts {
        if let Ok(Value::Array(rows)) = db.query_json(
            "SELECT 'contact' AS entity_type, id AS entity_id, name AS title, COALESCE(company, '') || ' ' || COALESCE(role, '') AS snippet FROM contacts WHERE name LIKE ?1 OR email LIKE ?1 OR company LIKE ?1 OR notes LIKE ?1 LIMIT 10",
            &[&pattern.as_str()],
        ) {
            results.extend(rows);
        }
    }

    if search_emails {
        if let Ok(Value::Array(rows)) = db.query_json(
            "SELECT 'email' AS entity_type, id AS entity_id, subject AS title, snippet AS snippet FROM emails WHERE subject LIKE ?1 OR snippet LIKE ?1 OR body_text LIKE ?1 LIMIT 10",
            &[&pattern.as_str()],
        ) {
            results.extend(rows);
        }
    }

    if search_notes {
        if let Ok(Value::Array(rows)) = db.query_json(
            "SELECT 'note' AS entity_type, id AS entity_id, substr(content, 1, 80) AS title, entity_type || ' note' AS snippet FROM notes WHERE content LIKE ?1 LIMIT 10",
            &[&pattern.as_str()],
        ) {
            results.extend(rows);
        }
    }

    if search_transcripts {
        if let Ok(Value::Array(rows)) = db.query_json(
            "SELECT 'transcript' AS entity_type, id AS entity_id, title AS title, substr(COALESCE(summary, ''), 1, 100) AS snippet FROM transcripts WHERE title LIKE ?1 OR summary LIKE ?1 OR full_text LIKE ?1 LIMIT 10",
            &[&pattern.as_str()],
        ) {
            results.extend(rows);
        }
    }

    let count = results.len();
    Ok(json!({
        "results": results,
        "count": count,
        "query": query,
        "search_method": "like_fallback"
    }))
}
