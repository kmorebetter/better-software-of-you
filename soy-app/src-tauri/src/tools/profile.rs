use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

pub fn definition() -> Value {
    json!({
        "name": "get_profile",
        "description": "Get a complete profile for a contact — full record plus their interactions, emails, follow-ups, calendar events, transcripts, and open commitments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "integer",
                    "description": "Contact ID (use this or contact_name)"
                },
                "contact_name": {
                    "type": "string",
                    "description": "Contact name to search for (use this or contact_id)"
                }
            }
        }
    })
}

pub fn execute(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    // Resolve contact ID (by ID or by name LIKE search)
    let contact_id: i64 = if let Some(id) = args["contact_id"].as_i64() {
        id
    } else if let Some(name) = args["contact_name"].as_str() {
        let pattern = format!("%{}%", name);
        let rows = db.query_json(
            "SELECT id FROM contacts WHERE name LIKE ?1 ORDER BY updated_at DESC LIMIT 1",
            &[&pattern.as_str()],
        )?;
        match rows {
            Value::Array(ref r) if !r.is_empty() => {
                r[0]["id"].as_i64().ok_or("Contact id missing")?
            }
            _ => return Err(format!("No contact found matching '{}'", name)),
        }
    } else {
        return Err("Provide contact_id or contact_name".to_string());
    };

    // Full contact record
    let contact_rows = db.query_json("SELECT * FROM contacts WHERE id = ?1", &[&contact_id])?;
    let contact = match contact_rows {
        Value::Array(ref rows) if !rows.is_empty() => rows[0].clone(),
        _ => return Err(format!("No contact found with id {}", contact_id)),
    };

    // Tags
    let tags = db.query_json(
        "SELECT t.name, t.color FROM tags t JOIN entity_tags et ON et.tag_id = t.id WHERE et.entity_type = 'contact' AND et.entity_id = ?1",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Notes
    let notes = db.query_json(
        "SELECT id, content, created_at FROM notes WHERE entity_type = 'contact' AND entity_id = ?1 ORDER BY created_at DESC",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Interactions (last 30)
    let interactions = db.query_json(
        "SELECT id, type, direction, subject, summary, occurred_at FROM contact_interactions WHERE contact_id = ?1 ORDER BY occurred_at DESC LIMIT 30",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Pending follow-ups
    let follow_ups = db.query_json(
        "SELECT id, due_date, reason, status FROM follow_ups WHERE contact_id = ?1 AND status = 'pending' ORDER BY due_date ASC",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Emails (last 20)
    let emails = db.query_json(
        "SELECT id, subject, direction, received_at, snippet FROM emails WHERE contact_id = ?1 ORDER BY received_at DESC LIMIT 20",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Calendar events (upcoming + last 5 past)
    let calendar_events = db.query_json(
        "SELECT ce.id, ce.title, ce.start_time, ce.end_time, ce.location
         FROM calendar_events ce
         JOIN calendar_event_contacts cec ON cec.event_id = ce.id
         WHERE cec.contact_id = ?1
         ORDER BY ce.start_time DESC LIMIT 10",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Transcripts (most recent 10)
    let transcripts = db.query_json(
        "SELECT t.id, t.title, t.occurred_at, t.summary
         FROM transcripts t
         JOIN transcript_participants tp ON tp.transcript_id = t.id
         WHERE tp.contact_id = ?1
         ORDER BY t.occurred_at DESC LIMIT 10",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Open commitments
    let commitments = db.query_json(
        "SELECT id, description, deadline_date, status, is_user_commitment FROM commitments WHERE owner_contact_id = ?1 AND status IN ('open', 'overdue') ORDER BY deadline_date ASC",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Health / relationship score from computed view
    let health = db.query_json(
        "SELECT days_silent, emails_total AS email_count, interactions_total AS interaction_count, relationship_depth, trajectory FROM v_contact_health WHERE id = ?1",
        &[&contact_id],
    ).unwrap_or(json!([]));

    let health_row = if let Value::Array(ref rows) = health {
        rows.first().cloned().unwrap_or(Value::Null)
    } else {
        Value::Null
    };

    Ok(json!({
        "contact": contact,
        "tags": tags,
        "notes": notes,
        "interactions": interactions,
        "follow_ups": follow_ups,
        "emails": emails,
        "calendar_events": calendar_events,
        "transcripts": transcripts,
        "commitments": commitments,
        "health": health_row
    }))
}
