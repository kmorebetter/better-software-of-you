use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

pub fn definition() -> Value {
    json!({
        "name": "inbox",
        "description": "Quick capture inbox — write first, route later. Capture thoughts, route them to contacts/projects/notes, or dismiss them.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["capture", "list", "route", "dismiss", "count"],
                    "description": "Action to perform"
                },
                "content": {
                    "type": "string",
                    "description": "Content to capture (required for capture)"
                },
                "inbox_id": {
                    "type": "integer",
                    "description": "Inbox item ID (required for route/dismiss)"
                },
                "destination": {
                    "type": "string",
                    "description": "Routing destination: contact, project, decision, journal, note, interaction, commitment (required for route)"
                },
                "entity_id": {
                    "type": "integer",
                    "description": "ID of the destination entity (required for route)"
                },
                "status": {
                    "type": "string",
                    "enum": ["unrouted", "routed", "dismissed", "all"],
                    "description": "Filter for list action (default: unrouted)"
                }
            },
            "required": ["action"]
        }
    })
}

pub fn execute(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let action = args["action"].as_str().ok_or("Missing action")?;

    match action {
        "capture" => capture(db, args),
        "list" => list(db, args),
        "route" => route(db, args),
        "dismiss" => dismiss(db, args),
        "count" => count(db),
        _ => Err(format!("Unknown inbox action: {}", action)),
    }
}

fn capture(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let content = args["content"].as_str().ok_or("Missing content for capture")?;

    // Extract #tags with simple regex-like matching
    let tags = extract_tags(content);
    let tags_json = serde_json::to_string(&tags).unwrap_or_else(|_| "[]".to_string());

    // Match contact names against the database
    let all_contacts = db.query_json(
        "SELECT id, name FROM contacts WHERE status = 'active' ORDER BY name",
        &[],
    ).unwrap_or(json!([]));

    let matched_contacts = match_contacts(content, &all_contacts);
    let matched_json = serde_json::to_string(&matched_contacts).unwrap_or_else(|_| "[]".to_string());

    let inbox_id = db.execute(
        "INSERT INTO inbox (content, tags, matched_contacts, created_at, updated_at) VALUES (?1, ?2, ?3, datetime('now'), datetime('now'))",
        &[&content, &tags_json.as_str(), &matched_json.as_str()],
    )?;

    let _ = db.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES ('inbox', ?1, 'captured', 'Inbox item captured', datetime('now'))",
        &[&inbox_id],
    );

    Ok(json!({
        "status": "captured",
        "inbox_id": inbox_id,
        "tags": tags,
        "matched_contacts": matched_contacts,
        "message": "Captured to inbox."
    }))
}

fn list(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let status = args["status"].as_str().unwrap_or("unrouted");

    let items = match status {
        "unrouted" => db.query_json(
            "SELECT id, content, tags, matched_contacts, created_at FROM inbox WHERE routed_to IS NULL ORDER BY created_at DESC LIMIT 50",
            &[],
        ),
        "routed" => db.query_json(
            "SELECT id, content, tags, routed_to, routed_entity_id, routed_at, created_at FROM inbox WHERE routed_to IS NOT NULL AND routed_to != 'dismissed' ORDER BY routed_at DESC LIMIT 50",
            &[],
        ),
        "dismissed" => db.query_json(
            "SELECT id, content, created_at, updated_at FROM inbox WHERE routed_to = 'dismissed' ORDER BY updated_at DESC LIMIT 50",
            &[],
        ),
        "all" => db.query_json(
            "SELECT id, content, tags, matched_contacts, routed_to, routed_entity_id, routed_at, created_at FROM inbox ORDER BY created_at DESC LIMIT 100",
            &[],
        ),
        _ => db.query_json(
            "SELECT id, content, tags, matched_contacts, created_at FROM inbox WHERE routed_to IS NULL ORDER BY created_at DESC LIMIT 50",
            &[],
        ),
    }.unwrap_or(json!([]));

    let count = if let Value::Array(ref rows) = items { rows.len() } else { 0 };

    Ok(json!({
        "items": items,
        "count": count,
        "status_filter": status
    }))
}

fn route(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let inbox_id = args["inbox_id"].as_i64().ok_or("Missing inbox_id for route")?;
    let destination = args["destination"].as_str().ok_or("Missing destination for route")?;
    let entity_id = args["entity_id"].as_i64();

    db.execute(
        "UPDATE inbox SET routed_to = ?1, routed_entity_id = ?2, routed_at = datetime('now'), updated_at = datetime('now') WHERE id = ?3",
        &[&destination, &entity_id, &inbox_id],
    )?;

    let _ = db.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES ('inbox', ?1, 'routed', ?2, datetime('now'))",
        &[&inbox_id, &format!("Routed to {}", destination).as_str()],
    );

    Ok(json!({
        "status": "routed",
        "inbox_id": inbox_id,
        "destination": destination,
        "entity_id": entity_id,
        "message": format!("Routed to {}.", destination)
    }))
}

fn dismiss(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let inbox_id = args["inbox_id"].as_i64().ok_or("Missing inbox_id for dismiss")?;

    db.execute(
        "UPDATE inbox SET routed_to = 'dismissed', routed_at = datetime('now'), updated_at = datetime('now') WHERE id = ?1",
        &[&inbox_id],
    )?;

    let _ = db.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES ('inbox', ?1, 'dismissed', 'Inbox item dismissed', datetime('now'))",
        &[&inbox_id],
    );

    Ok(json!({
        "status": "dismissed",
        "inbox_id": inbox_id,
        "message": "Item dismissed."
    }))
}

fn count(db: &Arc<Database>) -> Result<Value, String> {
    let result = db.query_json(
        "SELECT COUNT(*) AS count FROM inbox WHERE routed_to IS NULL",
        &[],
    ).unwrap_or(json!([]));

    let unrouted = if let Value::Array(ref rows) = result {
        rows.first().and_then(|r| r["count"].as_i64()).unwrap_or(0)
    } else {
        0
    };

    Ok(json!({
        "unrouted_count": unrouted
    }))
}

/// Extract #hashtags from content
fn extract_tags(content: &str) -> Vec<String> {
    let mut tags = Vec::new();
    let mut chars = content.chars().peekable();
    while let Some(ch) = chars.next() {
        if ch == '#' {
            let tag: String = chars
                .by_ref()
                .take_while(|c| c.is_alphanumeric() || *c == '_' || *c == '-')
                .collect();
            if !tag.is_empty() {
                tags.push(tag);
            }
        }
    }
    tags
}

/// Match contact names found in content
fn match_contacts(content: &str, contacts: &Value) -> Vec<Value> {
    let content_lower = content.to_lowercase();
    let mut matched = Vec::new();

    if let Value::Array(rows) = contacts {
        for row in rows {
            if let Some(name) = row["name"].as_str() {
                // Match if the full name appears (case-insensitive)
                if name.len() >= 3 && content_lower.contains(&name.to_lowercase()) {
                    matched.push(json!({
                        "id": row["id"],
                        "name": name
                    }));
                }
            }
        }
    }

    matched
}
