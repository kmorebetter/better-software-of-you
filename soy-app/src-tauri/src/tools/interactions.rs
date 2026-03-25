use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

pub fn definition() -> Value {
    json!({
        "name": "interactions",
        "description": "Log interactions with contacts and manage follow-ups. Track calls, meetings, messages, and schedule follow-up reminders.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["log", "list", "follow_up", "complete_follow_up", "list_follow_ups"],
                    "description": "Action to perform"
                },
                "contact_id": {
                    "type": "integer",
                    "description": "Contact ID (required for log/follow_up, optional filter for list/list_follow_ups)"
                },
                "contact_name": {
                    "type": "string",
                    "description": "Contact name — used to look up contact_id if not provided"
                },
                "interaction_type": {
                    "type": "string",
                    "enum": ["email", "call", "meeting", "message", "other"],
                    "description": "Type of interaction (default: meeting)"
                },
                "direction": {
                    "type": "string",
                    "enum": ["inbound", "outbound"],
                    "description": "Direction (default: outbound)"
                },
                "subject": {
                    "type": "string",
                    "description": "Subject/title of the interaction (required for log)"
                },
                "summary": {
                    "type": "string",
                    "description": "Summary or notes about the interaction"
                },
                "occurred_at": {
                    "type": "string",
                    "description": "When it happened (ISO date/datetime, default: now)"
                },
                "due_date": {
                    "type": "string",
                    "description": "Follow-up due date (YYYY-MM-DD, required for follow_up)"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for follow-up (required for follow_up)"
                },
                "follow_up_id": {
                    "type": "integer",
                    "description": "Follow-up ID (required for complete_follow_up)"
                }
            },
            "required": ["action"]
        }
    })
}

pub fn execute(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let action = args["action"].as_str().ok_or("Missing action")?;

    match action {
        "log" => log_interaction(db, args),
        "list" => list_interactions(db, args),
        "follow_up" => create_follow_up(db, args),
        "complete_follow_up" => complete_follow_up(db, args),
        "list_follow_ups" => list_follow_ups(db, args),
        _ => Err(format!("Unknown interactions action: {}", action)),
    }
}

/// Resolve a contact by ID or name. Returns (id, name) or an error.
fn resolve_contact(db: &Arc<Database>, args: &Value) -> Result<(i64, String), Value> {
    if let Some(cid) = args["contact_id"].as_i64() {
        let rows = db.query_json(
            "SELECT id, name FROM contacts WHERE id = ?1",
            &[&cid],
        ).map_err(|e| json!({"error": e}))?;
        if let Value::Array(ref r) = rows {
            if let Some(row) = r.first() {
                let name = row["name"].as_str().unwrap_or("").to_string();
                return Ok((cid, name));
            }
        }
        return Err(json!({"error": format!("No contact found with id {}", cid)}));
    }

    if let Some(name) = args["contact_name"].as_str() {
        let pattern = format!("%{}%", name);
        let rows = db.query_json(
            "SELECT id, name FROM contacts WHERE name LIKE ?1",
            &[&pattern.as_str()],
        ).map_err(|e| json!({"error": e}))?;
        if let Value::Array(ref r) = rows {
            if r.len() == 1 {
                let cid = r[0]["id"].as_i64().unwrap_or(0);
                let resolved_name = r[0]["name"].as_str().unwrap_or("").to_string();
                return Ok((cid, resolved_name));
            } else if r.len() > 1 {
                return Err(json!({
                    "error": "Multiple contacts match. Please specify.",
                    "matches": rows
                }));
            }
        }
        return Err(json!({"error": "Contact not found. Provide a valid contact_id or contact_name."}));
    }

    Err(json!({"error": "contact_id or contact_name is required."}))
}

fn log_interaction(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let (contact_id, contact_name) = resolve_contact(db, args).map_err(|e| e.to_string())?;

    let subject = args["subject"].as_str().ok_or("Subject is required for logging an interaction.")?;
    let interaction_type = args["interaction_type"].as_str().unwrap_or("meeting");
    let direction = args["direction"].as_str().unwrap_or("outbound");
    let summary = args["summary"].as_str().unwrap_or("");

    if let Some(occurred_at) = args["occurred_at"].as_str() {
        db.execute(
            "INSERT INTO contact_interactions (contact_id, type, direction, subject, summary, occurred_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            &[&contact_id, &interaction_type, &direction, &subject, &summary, &occurred_at],
        )?;
    } else {
        db.execute(
            "INSERT INTO contact_interactions (contact_id, type, direction, subject, summary) VALUES (?1, ?2, ?3, ?4, ?5)",
            &[&contact_id, &interaction_type, &direction, &subject, &summary],
        )?;
    }

    let details = format!("{}: {}", interaction_type, subject);
    let _ = db.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES ('contact', ?1, 'interaction_logged', ?2, datetime('now'))",
        &[&contact_id, &details.as_str()],
    );

    Ok(json!({
        "status": "logged",
        "contact_id": contact_id,
        "contact_name": contact_name,
        "type": interaction_type,
        "subject": subject,
        "message": format!("Logged {} with {}.", interaction_type, contact_name)
    }))
}

fn list_interactions(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let interactions = if let Some(contact_id) = args["contact_id"].as_i64() {
        db.query_json(
            "SELECT ci.id, ci.type, ci.direction, ci.subject, ci.summary, ci.occurred_at, c.name AS contact_name
             FROM contact_interactions ci
             JOIN contacts c ON c.id = ci.contact_id
             WHERE ci.contact_id = ?1
             ORDER BY ci.occurred_at DESC LIMIT 20",
            &[&contact_id],
        )?
    } else {
        db.query_json(
            "SELECT ci.id, ci.type, ci.direction, ci.subject, ci.summary, ci.occurred_at, c.name AS contact_name
             FROM contact_interactions ci
             JOIN contacts c ON c.id = ci.contact_id
             ORDER BY ci.occurred_at DESC LIMIT 20",
            &[],
        )?
    };

    let count = if let Value::Array(ref rows) = interactions { rows.len() } else { 0 };

    Ok(json!({
        "interactions": interactions,
        "count": count
    }))
}

fn create_follow_up(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let (contact_id, contact_name) = resolve_contact(db, args).map_err(|e| e.to_string())?;

    let due_date = args["due_date"].as_str().ok_or("due_date (YYYY-MM-DD) is required.")?;
    let reason = args["reason"].as_str().ok_or("reason is required.")?;

    let follow_up_id = db.execute(
        "INSERT INTO follow_ups (contact_id, due_date, reason) VALUES (?1, ?2, ?3)",
        &[&contact_id, &due_date, &reason],
    )?;

    let details = format!("Due {}: {}", due_date, reason);
    let _ = db.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES ('contact', ?1, 'follow_up_created', ?2, datetime('now'))",
        &[&contact_id, &details.as_str()],
    );

    Ok(json!({
        "status": "created",
        "follow_up_id": follow_up_id,
        "contact_name": contact_name,
        "due_date": due_date,
        "reason": reason,
        "message": format!("Follow-up scheduled with {} for {}.", contact_name, due_date)
    }))
}

fn complete_follow_up(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let follow_up_id = args["follow_up_id"].as_i64().ok_or("follow_up_id is required.")?;

    // Verify it exists and get contact info
    let rows = db.query_json(
        "SELECT f.id, f.contact_id, f.reason, c.name AS contact_name FROM follow_ups f JOIN contacts c ON c.id = f.contact_id WHERE f.id = ?1",
        &[&follow_up_id],
    )?;

    let (contact_id, contact_name, reason) = match rows {
        Value::Array(ref r) if !r.is_empty() => {
            let row = &r[0];
            (
                row["contact_id"].as_i64().unwrap_or(0),
                row["contact_name"].as_str().unwrap_or("").to_string(),
                row["reason"].as_str().unwrap_or("").to_string(),
            )
        }
        _ => return Err(format!("No follow-up found with id {}", follow_up_id)),
    };

    db.execute(
        "UPDATE follow_ups SET status = 'completed', completed_at = datetime('now') WHERE id = ?1",
        &[&follow_up_id],
    )?;

    let _ = db.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES ('contact', ?1, 'follow_up_completed', ?2, datetime('now'))",
        &[&contact_id, &reason.as_str()],
    );

    Ok(json!({
        "status": "completed",
        "follow_up_id": follow_up_id,
        "contact_name": contact_name,
        "message": format!("Follow-up with {} marked complete.", contact_name)
    }))
}

fn list_follow_ups(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let follow_ups = if let Some(contact_id) = args["contact_id"].as_i64() {
        db.query_json(
            "SELECT f.id, f.contact_id, f.due_date, f.reason, f.status, f.created_at,
                    c.name AS contact_name,
                    CASE WHEN f.due_date < date('now') THEN 1 ELSE 0 END AS overdue,
                    CASE WHEN f.due_date < date('now')
                         THEN CAST(julianday('now') - julianday(f.due_date) AS INTEGER)
                         ELSE NULL END AS days_overdue
             FROM follow_ups f
             JOIN contacts c ON c.id = f.contact_id
             WHERE f.contact_id = ?1 AND f.status = 'pending'
             ORDER BY f.due_date ASC",
            &[&contact_id],
        )?
    } else {
        db.query_json(
            "SELECT f.id, f.contact_id, f.due_date, f.reason, f.status, f.created_at,
                    c.name AS contact_name,
                    CASE WHEN f.due_date < date('now') THEN 1 ELSE 0 END AS overdue,
                    CASE WHEN f.due_date < date('now')
                         THEN CAST(julianday('now') - julianday(f.due_date) AS INTEGER)
                         ELSE NULL END AS days_overdue
             FROM follow_ups f
             JOIN contacts c ON c.id = f.contact_id
             WHERE f.status = 'pending'
             ORDER BY f.due_date ASC",
            &[],
        )?
    };

    let (count, overdue_count) = if let Value::Array(ref rows) = follow_ups {
        let oc = rows.iter().filter(|r| r["overdue"].as_i64() == Some(1)).count();
        (rows.len(), oc)
    } else {
        (0, 0)
    };

    Ok(json!({
        "follow_ups": follow_ups,
        "count": count,
        "overdue_count": overdue_count
    }))
}
