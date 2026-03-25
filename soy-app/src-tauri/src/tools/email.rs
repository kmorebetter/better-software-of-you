use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

pub fn definition() -> Value {
    json!({
        "name": "email",
        "description": "Search and browse synced emails from Gmail. Queries locally cached data — emails are synced separately via Google integration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["inbox", "unread", "search", "from", "thread"],
                    "description": "Action to perform"
                },
                "query": {
                    "type": "string",
                    "description": "Search query (required for search action)"
                },
                "contact_id": {
                    "type": "integer",
                    "description": "Contact ID (for from action)"
                },
                "contact_name": {
                    "type": "string",
                    "description": "Contact name lookup (for from action)"
                },
                "thread_id": {
                    "type": "string",
                    "description": "Thread ID (required for thread action)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default: 20)"
                }
            },
            "required": ["action"]
        }
    })
}

pub fn execute(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let action = args["action"].as_str().ok_or("Missing action")?;

    match action {
        "inbox" => inbox(db, args),
        "unread" => unread(db, args),
        "search" => search(db, args),
        "from" => from_contact(db, args),
        "thread" => thread(db, args),
        _ => Err(format!("Unknown email action: {}", action)),
    }
}

fn get_limit(args: &Value) -> i64 {
    args["limit"].as_i64().unwrap_or(20)
}

fn inbox(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let limit = get_limit(args);

    let emails = db.query_json(
        "SELECT e.thread_id, e.subject, e.snippet, e.from_name, e.from_address,
                e.direction, e.received_at, e.is_read, e.is_starred,
                c.name AS contact_name, c.id AS linked_contact_id,
                COUNT(*) OVER (PARTITION BY e.thread_id) AS thread_count
         FROM emails e
         LEFT JOIN contacts c ON e.contact_id = c.id
         WHERE e.id IN (SELECT MAX(id) FROM emails GROUP BY thread_id)
         ORDER BY e.received_at DESC LIMIT ?1",
        &[&limit],
    )?;

    let count = if let Value::Array(ref rows) = emails { rows.len() } else { 0 };

    Ok(json!({
        "emails": emails,
        "count": count
    }))
}

fn unread(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let limit = get_limit(args);

    let emails = db.query_json(
        "SELECT e.id, e.thread_id, e.subject, e.snippet, e.from_name, e.from_address,
                e.direction, e.received_at, e.is_starred,
                c.name AS contact_name
         FROM emails e
         LEFT JOIN contacts c ON e.contact_id = c.id
         WHERE e.is_read = 0
         ORDER BY e.received_at DESC LIMIT ?1",
        &[&limit],
    )?;

    let count = if let Value::Array(ref rows) = emails { rows.len() } else { 0 };

    Ok(json!({
        "emails": emails,
        "count": count
    }))
}

fn search(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let query = args["query"].as_str().ok_or("Search query is required.")?;
    let limit = get_limit(args);
    let pattern = format!("%{}%", query);

    let emails = db.query_json(
        "SELECT e.id, e.thread_id, e.subject, e.snippet, e.from_name, e.from_address,
                e.direction, e.received_at, e.is_read, e.is_starred,
                c.name AS contact_name
         FROM emails e
         LEFT JOIN contacts c ON e.contact_id = c.id
         WHERE e.subject LIKE ?1 OR e.snippet LIKE ?1 OR e.body_preview LIKE ?1 OR e.from_name LIKE ?1 OR e.from_address LIKE ?1
         ORDER BY e.received_at DESC LIMIT ?2",
        &[&pattern.as_str(), &limit],
    )?;

    let count = if let Value::Array(ref rows) = emails { rows.len() } else { 0 };

    Ok(json!({
        "emails": emails,
        "count": count,
        "query": query
    }))
}

fn from_contact(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let limit = get_limit(args);

    // Resolve contact_id from name if needed
    let contact_id = if let Some(cid) = args["contact_id"].as_i64() {
        cid
    } else if let Some(name) = args["contact_name"].as_str() {
        let pattern = format!("%{}%", name);
        let rows = db.query_json(
            "SELECT id, name FROM contacts WHERE name LIKE ?1",
            &[&pattern.as_str()],
        )?;
        match rows {
            Value::Array(ref r) if r.len() == 1 => {
                r[0]["id"].as_i64().ok_or("Invalid contact ID")?
            }
            Value::Array(ref r) if r.len() > 1 => {
                return Ok(json!({
                    "error": "Multiple contacts match.",
                    "matches": rows
                }));
            }
            _ => return Err("Contact not found.".to_string()),
        }
    } else {
        return Err("contact_id or contact_name is required.".to_string());
    };

    let emails = db.query_json(
        "SELECT e.id, e.thread_id, e.subject, e.snippet, e.from_name, e.from_address,
                e.direction, e.received_at, e.is_read, e.is_starred,
                c.name AS contact_name
         FROM emails e
         LEFT JOIN contacts c ON e.contact_id = c.id
         WHERE e.contact_id = ?1
         ORDER BY e.received_at DESC LIMIT ?2",
        &[&contact_id, &limit],
    )?;

    let count = if let Value::Array(ref rows) = emails { rows.len() } else { 0 };

    Ok(json!({
        "emails": emails,
        "count": count,
        "contact_id": contact_id
    }))
}

fn thread(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let thread_id = args["thread_id"].as_str().ok_or("thread_id is required.")?;

    let emails = db.query_json(
        "SELECT e.id, e.subject, e.snippet, e.body_preview, e.from_name, e.from_address,
                e.to_addresses, e.direction, e.received_at, e.is_read, e.is_starred,
                c.name AS contact_name
         FROM emails e
         LEFT JOIN contacts c ON e.contact_id = c.id
         WHERE e.thread_id = ?1
         ORDER BY e.received_at ASC",
        &[&thread_id],
    )?;

    let count = if let Value::Array(ref rows) = emails { rows.len() } else { 0 };

    Ok(json!({
        "emails": emails,
        "count": count,
        "thread_id": thread_id
    }))
}
