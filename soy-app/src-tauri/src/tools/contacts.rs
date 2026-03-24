use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

pub fn definition() -> Value {
    json!({
        "name": "contacts",
        "description": "Manage contacts — add, edit, list, find, or get a specific contact with their full context (interactions, emails, follow-ups).",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "edit", "list", "find", "get"],
                    "description": "Action to perform"
                },
                "contact_id": {
                    "type": "integer",
                    "description": "Contact ID (required for edit/get)"
                },
                "query": {
                    "type": "string",
                    "description": "Search query for find action"
                },
                "name": { "type": "string", "description": "Full name" },
                "email": { "type": "string", "description": "Email address" },
                "phone": { "type": "string", "description": "Phone number" },
                "company": { "type": "string", "description": "Company name" },
                "role": { "type": "string", "description": "Job title or role" },
                "contact_type": {
                    "type": "string",
                    "enum": ["individual", "company"],
                    "description": "Contact type (default: individual)"
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "inactive", "archived"],
                    "description": "Contact status (default: active)"
                },
                "notes": { "type": "string", "description": "Free-form notes" }
            },
            "required": ["action"]
        }
    })
}

pub fn execute(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let action = args["action"].as_str().ok_or("Missing action")?;

    match action {
        "add" => add_contact(db, args),
        "edit" => edit_contact(db, args),
        "list" => list_contacts(db, args),
        "find" => find_contacts(db, args),
        "get" => get_contact(db, args),
        _ => Err(format!("Unknown contacts action: {}", action)),
    }
}

fn add_contact(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let name = args["name"].as_str().ok_or("Missing name for add action")?;
    let email = args["email"].as_str().unwrap_or("");
    let phone = args["phone"].as_str().unwrap_or("");
    let company = args["company"].as_str().unwrap_or("");
    let role = args["role"].as_str().unwrap_or("");
    let contact_type = args["contact_type"].as_str().unwrap_or("individual");
    let status = args["status"].as_str().unwrap_or("active");
    let notes = args["notes"].as_str().unwrap_or("");

    // Check for duplicate by name or email
    let dupe_check = if !email.is_empty() {
        db.query_json(
            "SELECT id, name, email FROM contacts WHERE name = ?1 OR (email = ?2 AND email != '')",
            &[&name, &email],
        )?
    } else {
        db.query_json(
            "SELECT id, name, email FROM contacts WHERE name = ?1",
            &[&name],
        )?
    };

    if let Value::Array(ref existing) = dupe_check {
        if !existing.is_empty() {
            let existing_contact = &existing[0];
            return Ok(json!({
                "status": "duplicate",
                "message": format!("A contact named '{}' already exists.", existing_contact["name"].as_str().unwrap_or("")),
                "existing_contact": existing_contact
            }));
        }
    }

    let contact_id = db.execute(
        "INSERT INTO contacts (name, email, phone, company, role, type, status, notes, created_at, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, datetime('now'), datetime('now'))",
        &[&name, &email, &phone, &company, &role, &contact_type, &status, &notes],
    )?;

    // Log to activity_log
    let details = format!("Added contact: {}", name);
    let _ = db.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES ('contact', ?1, 'created', ?2, datetime('now'))",
        &[&contact_id, &details.as_str()],
    );

    Ok(json!({
        "status": "created",
        "contact_id": contact_id,
        "name": name,
        "message": format!("Added {} to your contacts.", name)
    }))
}

fn edit_contact(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let contact_id = args["contact_id"]
        .as_i64()
        .ok_or("Missing contact_id for edit action")?;

    // Verify contact exists
    let existing = db.query_json("SELECT id, name FROM contacts WHERE id = ?1", &[&contact_id])?;
    if let Value::Array(ref rows) = existing {
        if rows.is_empty() {
            return Err(format!("No contact found with id {}", contact_id));
        }
    }

    // Build dynamic UPDATE — only set fields that were provided
    let mut set_clauses: Vec<String> = Vec::new();
    let mut param_values: Vec<String> = Vec::new();

    macro_rules! add_field {
        ($field:expr, $col:expr) => {
            if let Some(val) = args[$field].as_str() {
                param_values.push(val.to_string());
                set_clauses.push(format!("{} = ?{}", $col, param_values.len()));
            }
        };
    }

    add_field!("name", "name");
    add_field!("email", "email");
    add_field!("phone", "phone");
    add_field!("company", "company");
    add_field!("role", "role");
    add_field!("contact_type", "type");
    add_field!("status", "status");
    add_field!("notes", "notes");

    if set_clauses.is_empty() {
        return Err("No fields to update provided".to_string());
    }

    set_clauses.push(format!("updated_at = datetime('now')"));

    let sql = format!(
        "UPDATE contacts SET {} WHERE id = ?{}",
        set_clauses.join(", "),
        param_values.len() + 1
    );

    // Build the params vec. rusqlite requires &dyn ToSql, so we use strings.
    // We execute using a helper that takes a raw SQL with string params.
    // Since Database::execute takes &[&dyn ToSql], we need to handle this carefully.
    // Build a direct SQL with literal values (safe because we're binding via SQLite).
    let mut full_params: Vec<Box<dyn rusqlite::ToSql>> = param_values
        .into_iter()
        .map(|s| Box::new(s) as Box<dyn rusqlite::ToSql>)
        .collect();
    full_params.push(Box::new(contact_id));

    let param_refs: Vec<&dyn rusqlite::ToSql> = full_params.iter().map(|b| b.as_ref()).collect();

    db.execute(&sql, &param_refs)?;

    let _ = db.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES ('contact', ?1, 'updated', 'Contact fields updated', datetime('now'))",
        &[&contact_id],
    );

    Ok(json!({
        "status": "updated",
        "contact_id": contact_id,
        "message": "Contact updated successfully."
    }))
}

fn list_contacts(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let status = args["status"].as_str().unwrap_or("active");

    let contacts = db.query_json(
        "SELECT id, name, company, role, email, status, updated_at FROM contacts WHERE status = ?1 ORDER BY updated_at DESC",
        &[&status],
    )?;

    let count = if let Value::Array(ref rows) = contacts {
        rows.len()
    } else {
        0
    };

    Ok(json!({
        "contacts": contacts,
        "count": count,
        "status_filter": status
    }))
}

fn find_contacts(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let query = args["query"].as_str().ok_or("Missing query for find action")?;
    let pattern = format!("%{}%", query);

    let contacts = db.query_json(
        "SELECT id, name, company, role, email, phone, status, updated_at
         FROM contacts
         WHERE name LIKE ?1 OR email LIKE ?1 OR company LIKE ?1 OR role LIKE ?1
         ORDER BY
           CASE WHEN name LIKE ?2 THEN 0 ELSE 1 END,
           updated_at DESC
         LIMIT 20",
        &[&pattern.as_str(), &format!("{}%", query).as_str()],
    )?;

    let count = if let Value::Array(ref rows) = contacts {
        rows.len()
    } else {
        0
    };

    Ok(json!({
        "contacts": contacts,
        "count": count,
        "query": query
    }))
}

fn get_contact(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let contact_id = args["contact_id"]
        .as_i64()
        .ok_or("Missing contact_id for get action")?;

    // Full contact record
    let contact_rows = db.query_json(
        "SELECT * FROM contacts WHERE id = ?1",
        &[&contact_id],
    )?;

    let contact = match contact_rows {
        Value::Array(ref rows) if !rows.is_empty() => rows[0].clone(),
        _ => return Err(format!("No contact found with id {}", contact_id)),
    };

    // Tags
    let tags = db.query_json(
        "SELECT t.name, t.color FROM tags t JOIN entity_tags et ON et.tag_id = t.id WHERE et.entity_type = 'contact' AND et.entity_id = ?1",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Recent interactions (last 10)
    let interactions = db.query_json(
        "SELECT type, direction, subject, summary, occurred_at FROM contact_interactions WHERE contact_id = ?1 ORDER BY occurred_at DESC LIMIT 10",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Pending follow-ups
    let follow_ups = db.query_json(
        "SELECT id, due_date, reason, status FROM follow_ups WHERE contact_id = ?1 AND status = 'pending' ORDER BY due_date ASC",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Recent emails (last 5)
    let emails = db.query_json(
        "SELECT subject, direction, received_at, snippet FROM emails WHERE contact_id = ?1 ORDER BY received_at DESC LIMIT 5",
        &[&contact_id],
    ).unwrap_or(json!([]));

    // Health stats from computed view (may not exist, handle gracefully)
    let health = db.query_json(
        "SELECT days_silent, email_count, interaction_count, relationship_depth FROM v_contact_health WHERE contact_id = ?1",
        &[&contact_id],
    ).unwrap_or(json!([]));

    Ok(json!({
        "contact": contact,
        "tags": tags,
        "interactions": interactions,
        "follow_ups": follow_ups,
        "recent_emails": emails,
        "health": if let Value::Array(ref rows) = health { rows.first().cloned().unwrap_or(Value::Null) } else { Value::Null }
    }))
}
