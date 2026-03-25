use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

pub fn definition() -> Value {
    json!({
        "name": "intelligence",
        "description": "Aggregated intelligence — meeting prep, nudges, commitment tracking, relationship health, and weekly review. Uses pre-computed views for all calculations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["meeting_prep", "nudges", "commitments_view", "relationship_pulse", "weekly_review"],
                    "description": "Action to perform"
                },
                "event_id": {
                    "type": "integer",
                    "description": "Calendar event ID (for meeting_prep)"
                },
                "contact_id": {
                    "type": "integer",
                    "description": "Contact ID (for relationship_pulse, or to scope meeting_prep)"
                },
                "contact_name": {
                    "type": "string",
                    "description": "Contact name lookup (for relationship_pulse)"
                }
            },
            "required": ["action"]
        }
    })
}

pub fn execute(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let action = args["action"].as_str().ok_or("Missing action")?;

    match action {
        "meeting_prep" => meeting_prep(db, args),
        "nudges" => nudges(db),
        "commitments_view" => commitments_view(db),
        "relationship_pulse" => relationship_pulse(db, args),
        "weekly_review" => weekly_review(db),
        _ => Err(format!("Unknown intelligence action: {}", action)),
    }
}

fn meeting_prep(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    // Get meeting info from v_meeting_prep
    let event = if let Some(event_id) = args["event_id"].as_i64() {
        let rows = db.query_json(
            "SELECT * FROM v_meeting_prep WHERE event_id = ?1",
            &[&event_id],
        )?;
        match rows {
            Value::Array(ref r) if !r.is_empty() => r[0].clone(),
            _ => return Err(format!("No event found with id {}", event_id)),
        }
    } else {
        // Get next upcoming event
        let rows = db.query_json(
            "SELECT * FROM v_meeting_prep WHERE minutes_until > 0 ORDER BY minutes_until ASC LIMIT 1",
            &[],
        )?;
        match rows {
            Value::Array(ref r) if !r.is_empty() => r[0].clone(),
            _ => return Ok(json!({
                "message": "No upcoming meetings found.",
                "events": []
            })),
        }
    };

    // Parse contact_ids from the event to gather context for all attendees
    let contact_ids_str = event["contact_ids"].as_str().unwrap_or("[]");
    let mut contacts_context: Vec<Value> = Vec::new();
    let mut open_commitments: Vec<Value> = Vec::new();
    let mut recent_emails: Vec<Value> = Vec::new();
    let mut recent_interactions: Vec<Value> = Vec::new();

    // Try to parse contact_ids JSON and accumulate data across all contacts
    if let Ok(ids) = serde_json::from_str::<Vec<i64>>(contact_ids_str) {
        for cid in &ids {
            // Contact health
            let health = db.query_json(
                "SELECT * FROM v_contact_health WHERE id = ?1",
                &[cid],
            ).unwrap_or(json!([]));
            if let Value::Array(ref rows) = health {
                for row in rows {
                    contacts_context.push(row.clone());
                }
            }

            // Open commitments for this contact
            let comms = db.query_json(
                "SELECT id, description, status, is_user_commitment, deadline_date, owner_name, urgency
                 FROM v_commitment_status
                 WHERE owner_contact_id = ?1 OR involved_contact_name LIKE '%' || (SELECT name FROM contacts WHERE id = ?1) || '%'
                 LIMIT 10",
                &[cid],
            ).unwrap_or(json!([]));
            if let Value::Array(ref rows) = comms {
                open_commitments.extend(rows.iter().cloned());
            }

            // Recent emails with this contact
            let emails = db.query_json(
                "SELECT subject, direction, received_at, snippet FROM emails
                 WHERE contact_id = ?1 ORDER BY received_at DESC LIMIT 5",
                &[cid],
            ).unwrap_or(json!([]));
            if let Value::Array(ref rows) = emails {
                recent_emails.extend(rows.iter().cloned());
            }

            // Recent interactions
            let interactions = db.query_json(
                "SELECT type, direction, subject, summary, occurred_at FROM contact_interactions
                 WHERE contact_id = ?1 ORDER BY occurred_at DESC LIMIT 5",
                &[cid],
            ).unwrap_or(json!([]));
            if let Value::Array(ref rows) = interactions {
                recent_interactions.extend(rows.iter().cloned());
            }
        }
    }

    Ok(json!({
        "event": event,
        "contacts": contacts_context,
        "open_commitments": open_commitments,
        "recent_emails": recent_emails,
        "recent_interactions": recent_interactions
    }))
}

fn nudges(db: &Arc<Database>) -> Result<Value, String> {
    // Get summary counts
    let summary = db.query_json(
        "SELECT tier, count FROM v_nudge_summary",
        &[],
    ).unwrap_or(json!([]));

    // Get all nudge items
    let urgent = db.query_json(
        "SELECT nudge_type, entity_id, entity_name, contact_id, project_id, description, relevant_date, days_value, extra_context, icon
         FROM v_nudge_items WHERE tier = 'urgent'
         ORDER BY days_value DESC",
        &[],
    ).unwrap_or(json!([]));

    let soon = db.query_json(
        "SELECT nudge_type, entity_id, entity_name, contact_id, project_id, description, relevant_date, days_value, extra_context, icon
         FROM v_nudge_items WHERE tier = 'soon'
         ORDER BY days_value ASC",
        &[],
    ).unwrap_or(json!([]));

    let awareness = db.query_json(
        "SELECT nudge_type, entity_id, entity_name, contact_id, project_id, description, relevant_date, days_value, extra_context, icon
         FROM v_nudge_items WHERE tier = 'awareness'
         ORDER BY days_value DESC",
        &[],
    ).unwrap_or(json!([]));

    let urgent_count = if let Value::Array(ref r) = urgent { r.len() } else { 0 };
    let soon_count = if let Value::Array(ref r) = soon { r.len() } else { 0 };
    let awareness_count = if let Value::Array(ref r) = awareness { r.len() } else { 0 };

    Ok(json!({
        "summary": summary,
        "urgent": urgent,
        "soon": soon,
        "awareness": awareness,
        "counts": {
            "urgent": urgent_count,
            "soon": soon_count,
            "awareness": awareness_count,
            "total": urgent_count + soon_count + awareness_count
        }
    }))
}

fn commitments_view(db: &Arc<Database>) -> Result<Value, String> {
    let commitments = db.query_json(
        "SELECT id, description, status, is_user_commitment, deadline_date, deadline_mentioned,
                owner_name, from_call, call_date, days_overdue, days_until_deadline, urgency,
                involved_contact_name
         FROM v_commitment_status
         ORDER BY
           CASE urgency WHEN 'overdue' THEN 0 WHEN 'soon' THEN 1 ELSE 2 END,
           deadline_date ASC NULLS LAST",
        &[],
    )?;

    let (count, overdue_count) = if let Value::Array(ref rows) = commitments {
        let oc = rows.iter().filter(|r| r["urgency"].as_str() == Some("overdue")).count();
        (rows.len(), oc)
    } else {
        (0, 0)
    };

    Ok(json!({
        "commitments": commitments,
        "count": count,
        "overdue_count": overdue_count
    }))
}

fn relationship_pulse(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    // Resolve contact
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

    // Get health from computed view
    let health = db.query_json(
        "SELECT * FROM v_contact_health WHERE id = ?1",
        &[&contact_id],
    )?;

    let health_data = match health {
        Value::Array(ref rows) if !rows.is_empty() => rows[0].clone(),
        _ => return Err(format!("No health data found for contact {}", contact_id)),
    };

    // Get latest communication insights
    let insights = db.query_json(
        "SELECT insight_type, content, sentiment, data_points, created_at
         FROM communication_insights
         WHERE contact_id = ?1
         ORDER BY created_at DESC LIMIT 5",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Get relationship score history
    let scores = db.query_json(
        "SELECT score_date, meeting_frequency, talk_ratio_avg, commitment_follow_through,
                relationship_depth, trajectory, notes
         FROM relationship_scores
         WHERE contact_id = ?1
         ORDER BY score_date DESC LIMIT 5",
        &[&contact_id],
    ).unwrap_or(json!([]));

    Ok(json!({
        "health": health_data,
        "insights": insights,
        "score_history": scores
    }))
}

fn weekly_review(db: &Arc<Database>) -> Result<Value, String> {
    // Interactions logged this week
    let interactions = db.query_json(
        "SELECT COUNT(*) AS count FROM contact_interactions
         WHERE occurred_at > datetime('now', '-7 days')",
        &[],
    ).unwrap_or(json!([]));
    let interactions_count = extract_count(&interactions);

    // Emails sent and received this week
    let emails_sent = db.query_json(
        "SELECT COUNT(*) AS count FROM emails
         WHERE direction = 'outbound' AND received_at > datetime('now', '-7 days')",
        &[],
    ).unwrap_or(json!([]));
    let sent_count = extract_count(&emails_sent);

    let emails_received = db.query_json(
        "SELECT COUNT(*) AS count FROM emails
         WHERE direction = 'inbound' AND received_at > datetime('now', '-7 days')",
        &[],
    ).unwrap_or(json!([]));
    let received_count = extract_count(&emails_received);

    // Commitments completed vs created this week
    let commitments_completed = db.query_json(
        "SELECT COUNT(*) AS count FROM commitments
         WHERE status = 'completed' AND completed_at > datetime('now', '-7 days')",
        &[],
    ).unwrap_or(json!([]));
    let completed_count = extract_count(&commitments_completed);

    let commitments_created = db.query_json(
        "SELECT COUNT(*) AS count FROM commitments
         WHERE created_at > datetime('now', '-7 days')",
        &[],
    ).unwrap_or(json!([]));
    let created_count = extract_count(&commitments_created);

    // Follow-ups completed this week
    let follow_ups_completed = db.query_json(
        "SELECT COUNT(*) AS count FROM follow_ups
         WHERE status = 'completed' AND completed_at > datetime('now', '-7 days')",
        &[],
    ).unwrap_or(json!([]));
    let follow_ups_done = extract_count(&follow_ups_completed);

    // New contacts this week
    let new_contacts = db.query_json(
        "SELECT COUNT(*) AS count FROM contacts
         WHERE created_at > datetime('now', '-7 days')",
        &[],
    ).unwrap_or(json!([]));
    let new_contacts_count = extract_count(&new_contacts);

    // Recent interactions for context
    let recent_interactions = db.query_json(
        "SELECT ci.type, ci.subject, ci.occurred_at, c.name AS contact_name
         FROM contact_interactions ci
         JOIN contacts c ON c.id = ci.contact_id
         WHERE ci.occurred_at > datetime('now', '-7 days')
         ORDER BY ci.occurred_at DESC LIMIT 10",
        &[],
    ).unwrap_or(json!([]));

    // Currently open items
    let open_commitments = db.query_json(
        "SELECT COUNT(*) AS count FROM commitments WHERE status IN ('open', 'overdue')",
        &[],
    ).unwrap_or(json!([]));
    let open_count = extract_count(&open_commitments);

    let pending_follow_ups = db.query_json(
        "SELECT COUNT(*) AS count FROM follow_ups WHERE status = 'pending'",
        &[],
    ).unwrap_or(json!([]));
    let pending_count = extract_count(&pending_follow_ups);

    Ok(json!({
        "week_stats": {
            "interactions_logged": interactions_count,
            "emails_sent": sent_count,
            "emails_received": received_count,
            "commitments_completed": completed_count,
            "commitments_created": created_count,
            "follow_ups_completed": follow_ups_done,
            "new_contacts": new_contacts_count
        },
        "open_items": {
            "open_commitments": open_count,
            "pending_follow_ups": pending_count
        },
        "recent_interactions": recent_interactions
    }))
}

/// Extract a count value from a single-row query result
fn extract_count(result: &Value) -> i64 {
    if let Value::Array(ref rows) = result {
        rows.first()
            .and_then(|r| r["count"].as_i64())
            .unwrap_or(0)
    } else {
        0
    }
}
