use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

pub fn definition() -> Value {
    json!({
        "name": "get_overview",
        "description": "Get a dashboard overview: contact counts, pending follow-ups, today's calendar events, unread emails, open commitments, and recent activity.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    })
}

pub fn execute(db: &Arc<Database>) -> Result<Value, String> {
    // Contact count + recent 5
    let contact_count = db.query_json(
        "SELECT COUNT(*) AS count FROM contacts WHERE status = 'active'",
        &[],
    ).unwrap_or(json!([]));

    let recent_contacts = db.query_json(
        "SELECT id, name, company, role, updated_at FROM contacts WHERE status = 'active' ORDER BY updated_at DESC LIMIT 5",
        &[],
    ).unwrap_or(json!([]));

    // Pending follow-ups (ordered by due_date)
    let follow_ups = db.query_json(
        "SELECT f.id, f.due_date, f.reason, c.name AS contact_name, c.id AS contact_id
         FROM follow_ups f JOIN contacts c ON c.id = f.contact_id
         WHERE f.status = 'pending' ORDER BY f.due_date ASC LIMIT 10",
        &[],
    ).unwrap_or(json!([]));

    // Calendar events for today and tomorrow
    let calendar_events = db.query_json(
        "SELECT id, title, start_time, end_time, location, description
         FROM calendar_events
         WHERE date(start_time) BETWEEN date('now') AND date('now', '+1 day')
         ORDER BY start_time ASC LIMIT 10",
        &[],
    ).unwrap_or(json!([]));

    // Unread email count
    let unread_emails = db.query_json(
        "SELECT COUNT(*) AS count FROM emails WHERE direction = 'inbound' AND read_at IS NULL",
        &[],
    ).unwrap_or(json!([]));

    // Open commitment count
    let open_commitments = db.query_json(
        "SELECT COUNT(*) AS count FROM commitments WHERE status IN ('open', 'overdue')",
        &[],
    ).unwrap_or(json!([]));

    // Nudge summary from computed view (may not exist)
    let nudge_summary = db.query_json(
        "SELECT tier, count FROM v_nudge_summary",
        &[],
    ).unwrap_or(json!([]));

    // Recent activity log (last 15)
    let recent_activity = db.query_json(
        "SELECT al.entity_type, al.entity_id, al.action, al.details, al.created_at,
                CASE al.entity_type WHEN 'contact' THEN (SELECT name FROM contacts WHERE id = al.entity_id) ELSE NULL END AS entity_name
         FROM activity_log al ORDER BY al.created_at DESC LIMIT 15",
        &[],
    ).unwrap_or(json!([]));

    // Extract scalar count values
    let total_contacts = scalar_count(&contact_count);
    let total_unread = scalar_count(&unread_emails);
    let total_commitments = scalar_count(&open_commitments);

    Ok(json!({
        "contacts": {
            "total": total_contacts,
            "recent": recent_contacts
        },
        "follow_ups": follow_ups,
        "calendar": calendar_events,
        "emails": {
            "unread_count": total_unread
        },
        "commitments": {
            "open_count": total_commitments
        },
        "nudges": nudge_summary,
        "recent_activity": recent_activity
    }))
}

fn scalar_count(result: &Value) -> i64 {
    if let Value::Array(rows) = result {
        if let Some(row) = rows.first() {
            return row["count"].as_i64().unwrap_or(0);
        }
    }
    0
}
