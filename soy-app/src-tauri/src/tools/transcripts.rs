use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

pub fn definition() -> Value {
    json!({
        "name": "transcripts",
        "description": "Browse meeting transcripts and manage commitments extracted from calls. View transcript details, participants, metrics, and track commitment follow-through.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "get", "commitments", "complete_commitment"],
                    "description": "Action to perform"
                },
                "transcript_id": {
                    "type": "integer",
                    "description": "Transcript ID (required for get, optional filter for commitments)"
                },
                "contact_id": {
                    "type": "integer",
                    "description": "Contact ID (optional filter for commitments)"
                },
                "commitment_id": {
                    "type": "integer",
                    "description": "Commitment ID (required for complete_commitment)"
                }
            },
            "required": ["action"]
        }
    })
}

pub fn execute(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let action = args["action"].as_str().ok_or("Missing action")?;

    match action {
        "list" => list_transcripts(db),
        "get" => get_transcript(db, args),
        "commitments" => list_commitments(db, args),
        "complete_commitment" => complete_commitment(db, args),
        _ => Err(format!("Unknown transcripts action: {}", action)),
    }
}

fn list_transcripts(db: &Arc<Database>) -> Result<Value, String> {
    let transcripts = db.query_json(
        "SELECT t.id, t.title, t.source, t.duration_minutes, t.occurred_at,
                t.summary, t.processed_at,
                GROUP_CONCAT(DISTINCT c.name) AS participant_names
         FROM transcripts t
         LEFT JOIN transcript_participants tp ON tp.transcript_id = t.id AND tp.is_user = 0
         LEFT JOIN contacts c ON c.id = tp.contact_id
         GROUP BY t.id
         ORDER BY t.occurred_at DESC LIMIT 20",
        &[],
    )?;

    let count = if let Value::Array(ref rows) = transcripts { rows.len() } else { 0 };

    Ok(json!({
        "transcripts": transcripts,
        "count": count
    }))
}

fn get_transcript(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let transcript_id = args["transcript_id"].as_i64().ok_or("transcript_id is required.")?;

    // Get the transcript record
    let transcript_rows = db.query_json(
        "SELECT * FROM transcripts WHERE id = ?1",
        &[&transcript_id],
    )?;

    let transcript = match transcript_rows {
        Value::Array(ref rows) if !rows.is_empty() => rows[0].clone(),
        _ => return Err(format!("No transcript found with id {}", transcript_id)),
    };

    // Participants
    let participants = db.query_json(
        "SELECT tp.id, tp.speaker_label, tp.is_user, tp.contact_id, c.name AS contact_name
         FROM transcript_participants tp
         LEFT JOIN contacts c ON c.id = tp.contact_id
         WHERE tp.transcript_id = ?1",
        &[&transcript_id],
    ).unwrap_or(json!([]));

    // Conversation metrics
    let metrics = db.query_json(
        "SELECT cm.contact_id, cm.talk_ratio, cm.word_count, cm.question_count,
                cm.interruption_count, cm.longest_monologue_seconds,
                c.name AS contact_name
         FROM conversation_metrics cm
         LEFT JOIN contacts c ON c.id = cm.contact_id
         WHERE cm.transcript_id = ?1",
        &[&transcript_id],
    ).unwrap_or(json!([]));

    // Commitments
    let commitments = db.query_json(
        "SELECT com.id, com.description, com.status, com.is_user_commitment,
                com.deadline_date, com.deadline_mentioned, com.completed_at,
                c.name AS owner_name
         FROM commitments com
         LEFT JOIN contacts c ON c.id = com.owner_contact_id
         WHERE com.transcript_id = ?1",
        &[&transcript_id],
    ).unwrap_or(json!([]));

    // Communication insights
    let insights = db.query_json(
        "SELECT id, insight_type, content, sentiment, data_points
         FROM communication_insights
         WHERE transcript_id = ?1",
        &[&transcript_id],
    ).unwrap_or(json!([]));

    Ok(json!({
        "transcript": transcript,
        "participants": participants,
        "metrics": metrics,
        "commitments": commitments,
        "insights": insights
    }))
}

fn list_commitments(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let commitments = if let Some(transcript_id) = args["transcript_id"].as_i64() {
        db.query_json(
            "SELECT com.id, com.description, com.status, com.is_user_commitment,
                    com.deadline_date, com.deadline_mentioned, com.created_at,
                    c.name AS owner_name, t.title AS from_call,
                    CASE WHEN com.deadline_date IS NOT NULL AND com.deadline_date < date('now') THEN 1 ELSE 0 END AS overdue,
                    CASE WHEN com.deadline_date IS NOT NULL AND com.deadline_date < date('now')
                         THEN CAST(julianday('now') - julianday(com.deadline_date) AS INTEGER)
                         ELSE NULL END AS days_overdue
             FROM commitments com
             LEFT JOIN contacts c ON c.id = com.owner_contact_id
             LEFT JOIN transcripts t ON t.id = com.transcript_id
             WHERE com.transcript_id = ?1 AND com.status IN ('open', 'overdue')
             ORDER BY com.deadline_date ASC NULLS LAST",
            &[&transcript_id],
        )?
    } else if let Some(contact_id) = args["contact_id"].as_i64() {
        db.query_json(
            "SELECT com.id, com.description, com.status, com.is_user_commitment,
                    com.deadline_date, com.deadline_mentioned, com.created_at,
                    c.name AS owner_name, t.title AS from_call,
                    CASE WHEN com.deadline_date IS NOT NULL AND com.deadline_date < date('now') THEN 1 ELSE 0 END AS overdue,
                    CASE WHEN com.deadline_date IS NOT NULL AND com.deadline_date < date('now')
                         THEN CAST(julianday('now') - julianday(com.deadline_date) AS INTEGER)
                         ELSE NULL END AS days_overdue
             FROM commitments com
             LEFT JOIN contacts c ON c.id = com.owner_contact_id
             LEFT JOIN transcripts t ON t.id = com.transcript_id
             WHERE (com.owner_contact_id = ?1 OR com.is_user_commitment = 1)
               AND com.status IN ('open', 'overdue')
             ORDER BY com.deadline_date ASC NULLS LAST",
            &[&contact_id],
        )?
    } else {
        db.query_json(
            "SELECT com.id, com.description, com.status, com.is_user_commitment,
                    com.deadline_date, com.deadline_mentioned, com.created_at,
                    c.name AS owner_name, t.title AS from_call,
                    CASE WHEN com.deadline_date IS NOT NULL AND com.deadline_date < date('now') THEN 1 ELSE 0 END AS overdue,
                    CASE WHEN com.deadline_date IS NOT NULL AND com.deadline_date < date('now')
                         THEN CAST(julianday('now') - julianday(com.deadline_date) AS INTEGER)
                         ELSE NULL END AS days_overdue
             FROM commitments com
             LEFT JOIN contacts c ON c.id = com.owner_contact_id
             LEFT JOIN transcripts t ON t.id = com.transcript_id
             WHERE com.status IN ('open', 'overdue')
             ORDER BY com.deadline_date ASC NULLS LAST",
            &[],
        )?
    };

    let (count, overdue_count) = if let Value::Array(ref rows) = commitments {
        let oc = rows.iter().filter(|r| r["overdue"].as_i64() == Some(1)).count();
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

fn complete_commitment(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let commitment_id = args["commitment_id"].as_i64().ok_or("commitment_id is required.")?;

    // Verify it exists
    let rows = db.query_json(
        "SELECT id, description FROM commitments WHERE id = ?1",
        &[&commitment_id],
    )?;

    let description = match rows {
        Value::Array(ref r) if !r.is_empty() => {
            r[0]["description"].as_str().unwrap_or("").to_string()
        }
        _ => return Err(format!("No commitment found with id {}", commitment_id)),
    };

    db.execute(
        "UPDATE commitments SET status = 'completed', completed_at = datetime('now'), updated_at = datetime('now') WHERE id = ?1",
        &[&commitment_id],
    )?;

    let _ = db.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES ('commitment', ?1, 'completed', ?2, datetime('now'))",
        &[&commitment_id, &description.as_str()],
    );

    Ok(json!({
        "status": "completed",
        "commitment_id": commitment_id,
        "message": "Commitment marked complete."
    }))
}
