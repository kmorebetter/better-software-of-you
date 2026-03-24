use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

pub fn definition() -> Value {
    json!({
        "name": "system_status",
        "description": "Get the system status: database stats, installed modules, onboarding stage, and user profile.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status"],
                    "description": "Action (currently only 'status')"
                }
            }
        }
    })
}

pub fn execute(db: &Arc<Database>, _args: &Value) -> Result<Value, String> {
    // Core counts
    let contact_count = scalar_count(db, "SELECT COUNT(*) AS count FROM contacts WHERE status = 'active'");
    let email_count = scalar_count(db, "SELECT COUNT(*) AS count FROM emails");
    let transcript_count = scalar_count(db, "SELECT COUNT(*) AS count FROM transcripts");
    let calendar_count = scalar_count(db, "SELECT COUNT(*) AS count FROM calendar_events WHERE date(start_time) >= date('now')");
    let note_count = scalar_count(db, "SELECT COUNT(*) AS count FROM notes");
    let interaction_count = scalar_count(db, "SELECT COUNT(*) AS count FROM contact_interactions");

    // Installed modules
    let modules = db.query_json(
        "SELECT name, version, enabled FROM modules ORDER BY name",
        &[],
    ).unwrap_or(json!([]));

    // User profile
    let profile = db.query_json(
        "SELECT category, key, value FROM user_profile ORDER BY category, key",
        &[],
    ).unwrap_or(json!([]));

    // Inbox unrouted count (if inbox module installed)
    let inbox_unrouted = scalar_count(db, "SELECT COUNT(*) AS count FROM inbox WHERE routed_to IS NULL");

    // Meta info
    let meta = db.query_json(
        "SELECT key, value FROM soy_meta WHERE key IN ('schema_version', 'platform_version', 'created_at', 'gmail_last_synced', 'calendar_last_synced', 'profile_setup_completed')",
        &[],
    ).unwrap_or(json!([]));

    // Determine onboarding stage
    let stage = if contact_count == 0 {
        "fresh"
    } else if contact_count < 5 {
        "has_contacts"
    } else {
        "active"
    };

    // Check if Google is connected (has an active google account)
    let google_connected = scalar_count(db, "SELECT COUNT(*) AS count FROM google_accounts WHERE status = 'active'") > 0;

    Ok(json!({
        "stats": {
            "contacts": contact_count,
            "emails": email_count,
            "transcripts": transcript_count,
            "upcoming_calendar_events": calendar_count,
            "notes": note_count,
            "interactions": interaction_count,
            "inbox_unrouted": inbox_unrouted
        },
        "modules": modules,
        "profile": profile,
        "meta": meta,
        "onboarding_stage": stage,
        "google_connected": google_connected
    }))
}

fn scalar_count(db: &Arc<Database>, sql: &str) -> i64 {
    db.query_json(sql, &[])
        .ok()
        .and_then(|v| {
            if let Value::Array(rows) = v {
                rows.first().and_then(|r| r["count"].as_i64())
            } else {
                None
            }
        })
        .unwrap_or(0)
}
