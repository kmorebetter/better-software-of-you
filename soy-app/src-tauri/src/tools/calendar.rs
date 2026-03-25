use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

pub fn definition() -> Value {
    json!({
        "name": "calendar",
        "description": "Browse synced calendar events. View today's schedule, upcoming meetings, events with specific contacts, and find free time slots.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["today", "tomorrow", "week", "schedule", "with", "free"],
                    "description": "Action to perform"
                },
                "contact_id": {
                    "type": "integer",
                    "description": "Contact ID (for 'with' action)"
                },
                "contact_name": {
                    "type": "string",
                    "description": "Contact name lookup (for 'with' action)"
                },
                "date_str": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (for 'schedule' and 'free' actions)"
                },
                "title": {
                    "type": "string",
                    "description": "Event title (for 'schedule' action — creating a new event)"
                },
                "start_time": {
                    "type": "string",
                    "description": "Event start time ISO datetime (for 'schedule' action)"
                },
                "end_time": {
                    "type": "string",
                    "description": "Event end time ISO datetime (for 'schedule' action)"
                },
                "description": {
                    "type": "string",
                    "description": "Event description"
                },
                "location": {
                    "type": "string",
                    "description": "Event location"
                }
            },
            "required": ["action"]
        }
    })
}

pub fn execute(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let action = args["action"].as_str().ok_or("Missing action")?;

    match action {
        "today" => today(db),
        "tomorrow" => tomorrow(db),
        "week" => week(db),
        "schedule" => schedule(db, args),
        "with" => with_contact(db, args),
        "free" => free(db, args),
        _ => Err(format!("Unknown calendar action: {}", action)),
    }
}

fn today(db: &Arc<Database>) -> Result<Value, String> {
    let events = db.query_json(
        "SELECT id, title, description, location, start_time, end_time, all_day, status, attendees, contact_ids
         FROM calendar_events
         WHERE date(start_time) = date('now', 'localtime') AND status != 'cancelled'
         ORDER BY start_time ASC",
        &[],
    )?;

    let count = if let Value::Array(ref rows) = events { rows.len() } else { 0 };

    Ok(json!({
        "events": events,
        "count": count,
        "date": "today"
    }))
}

fn tomorrow(db: &Arc<Database>) -> Result<Value, String> {
    let events = db.query_json(
        "SELECT id, title, description, location, start_time, end_time, all_day, status, attendees, contact_ids
         FROM calendar_events
         WHERE date(start_time) = date('now', 'localtime', '+1 day') AND status != 'cancelled'
         ORDER BY start_time ASC",
        &[],
    )?;

    let count = if let Value::Array(ref rows) = events { rows.len() } else { 0 };

    Ok(json!({
        "events": events,
        "count": count,
        "date": "tomorrow"
    }))
}

fn week(db: &Arc<Database>) -> Result<Value, String> {
    let events = db.query_json(
        "SELECT id, title, description, location, start_time, end_time, all_day, status, attendees, contact_ids
         FROM calendar_events
         WHERE date(start_time) BETWEEN date('now', 'localtime') AND date('now', 'localtime', '+6 days')
           AND status != 'cancelled'
         ORDER BY start_time ASC",
        &[],
    )?;

    let count = if let Value::Array(ref rows) = events { rows.len() } else { 0 };

    Ok(json!({
        "events": events,
        "count": count,
        "date": "next 7 days"
    }))
}

fn schedule(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    // If title + start_time are provided, create a new event
    if let (Some(title), Some(start_time), Some(end_time)) = (
        args["title"].as_str(),
        args["start_time"].as_str(),
        args["end_time"].as_str(),
    ) {
        let description = args["description"].as_str().unwrap_or("");
        let location = args["location"].as_str().unwrap_or("");

        let event_id = db.execute(
            "INSERT INTO calendar_events (title, start_time, end_time, description, location, synced_at)
             VALUES (?1, ?2, ?3, ?4, ?5, datetime('now'))",
            &[&title, &start_time, &end_time, &description, &location],
        )?;

        let details = format!("Created event: {}", title);
        let _ = db.execute(
            "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES ('calendar_event', ?1, 'created', ?2, datetime('now'))",
            &[&event_id, &details.as_str()],
        );

        return Ok(json!({
            "status": "created",
            "event_id": event_id,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "message": format!("Event '{}' created.", title)
        }));
    }

    // Otherwise, show events for a specific date
    let date_str = args["date_str"].as_str().ok_or("date_str (YYYY-MM-DD) is required for viewing a schedule, or provide title/start_time/end_time to create an event.")?;

    let events = db.query_json(
        "SELECT id, title, description, location, start_time, end_time, all_day, status, attendees, contact_ids
         FROM calendar_events
         WHERE date(start_time) = ?1 AND status != 'cancelled'
         ORDER BY start_time ASC",
        &[&date_str],
    )?;

    let count = if let Value::Array(ref rows) = events { rows.len() } else { 0 };

    Ok(json!({
        "events": events,
        "count": count,
        "date": date_str
    }))
}

fn with_contact(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
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

    let cid_pattern = format!("%{}%", contact_id);
    let events = db.query_json(
        "SELECT id, title, description, location, start_time, end_time, all_day, status, attendees, contact_ids
         FROM calendar_events
         WHERE contact_ids LIKE ?1 AND status != 'cancelled'
         ORDER BY start_time DESC LIMIT 20",
        &[&cid_pattern.as_str()],
    )?;

    let count = if let Value::Array(ref rows) = events { rows.len() } else { 0 };

    Ok(json!({
        "events": events,
        "count": count,
        "contact_id": contact_id
    }))
}

fn free(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    // Use provided date or default to today
    let date_expr = if let Some(date_str) = args["date_str"].as_str() {
        date_str.to_string()
    } else {
        // Get today's date via a query to avoid depending on system locale
        let result = db.query_json("SELECT date('now', 'localtime') AS today", &[])?;
        if let Value::Array(ref rows) = result {
            rows.first()
                .and_then(|r| r["today"].as_str())
                .unwrap_or("today")
                .to_string()
        } else {
            "today".to_string()
        }
    };

    let events = db.query_json(
        "SELECT start_time, end_time, title FROM calendar_events
         WHERE date(start_time) = ?1 AND status != 'cancelled'
         ORDER BY start_time ASC",
        &[&date_expr.as_str()],
    )?;

    let count = if let Value::Array(ref rows) = events { rows.len() } else { 0 };

    Ok(json!({
        "events": events,
        "count": count,
        "date": date_expr,
        "instructions": "Calculate free slots between events. Assume work day is 9 AM to 6 PM. Show gaps as available time blocks."
    }))
}
